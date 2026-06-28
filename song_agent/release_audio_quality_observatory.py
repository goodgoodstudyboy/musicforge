from __future__ import annotations

import json
import re
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.release_audio_timeline_verifier import verify_release_audio_timeline_package
from song_agent.releases import ReleaseStore, stable_hash


RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE = "release_audio_quality_observatory"
RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION = 1


class ReleaseAudioQualityObservatoryError(ValueError):
    pass


class ReleaseAudioQualityObservatoryNotFoundError(ReleaseAudioQualityObservatoryError):
    pass


class ReleaseAudioQualityObservatoryStateError(ReleaseAudioQualityObservatoryError):
    pass


class ReleaseAudioQualityObservatoryValidationError(ReleaseAudioQualityObservatoryError):
    pass


class ReleaseAudioQualityObservatoryStore:
    def __init__(self, root: Path | str | None = None, *, release_store: ReleaseStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = Path(root) if root is not None else Path(".musicforge") / "audio-quality-observatory"
        self.root = self.root.resolve()
        self.lock = threading.RLock()

    def observatories_dir(self) -> Path:
        return self.root / "observatories"

    def observatory_dir(self, observatory_id: str) -> Path:
        return self.observatories_dir() / _validate_observatory_id(observatory_id)

    def config_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "observatory-config.json"

    def source_index_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "source-index.json"

    def evidence_fingerprints_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "evidence-fingerprints.json"

    def trend_report_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "trend-report.json"

    def heatmap_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "issue-heatmap.json"

    def baseline_drift_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "baseline-drift-report.json"

    def remediation_cost_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "remediation-cost-report.json"

    def risk_register_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "risk-register.json"

    def recommendation_report_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "recommendation-report.json"

    def summary_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "observatory-summary.json"

    def history_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "observatory-history.jsonl"

    def export_dir(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "export"

    def zip_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "release-audio-quality-observatory.zip"

    def verification_report_path(self, observatory_id: str) -> Path:
        return self.observatory_dir(observatory_id) / "verification-report.json"

    def list_observatories(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for config in sorted(self.observatories_dir().glob("*/observatory-config.json")):
            try:
                doc = read_json(config)
                summary = read_json(self.summary_path(str(doc.get("observatory_id")))) if self.summary_path(str(doc.get("observatory_id"))).exists() else {}
            except Exception:
                continue
            rows.append({"observatory": doc, "summary": summary})
        return rows

    def create(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            observatory_id = str(payload.get("observatory_id") or self._next_observatory_id())
            observatory_id = _validate_observatory_id(observatory_id)
            path = self.config_path(observatory_id)
            if path.exists():
                raise ReleaseAudioQualityObservatoryValidationError(f"Audio Quality Observatory already exists: {observatory_id}.")
            config = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
                    "observatory_id": observatory_id,
                    "name": _bounded(payload.get("name") or "Release Audio Quality Observatory", 120),
                    "scope": _safe_dict(payload.get("scope")),
                    "window": _default_window(payload.get("window") if isinstance(payload.get("window"), dict) else {}),
                    "thresholds": _default_thresholds(payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}),
                    "release_ids": [str(item) for item in payload.get("release_ids", []) if str(item).strip()],
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            config["integrity_hash"] = _integrity_hash(config)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, config)
            self._append_history_event(observatory_id, "observatory_created", {"config_hash": config["integrity_hash"]})
            return config

    def read_config(self, observatory_id: str) -> dict[str, Any]:
        path = self.config_path(observatory_id)
        if not path.exists():
            raise ReleaseAudioQualityObservatoryNotFoundError(f"Audio Quality Observatory not found: {observatory_id}.")
        return read_json(path)

    def refresh(self, observatory_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            config = self.read_config(observatory_id)
            release_entries = self._release_entries(config, payload)
            docs = build_observatory_documents(config, release_entries)
            self._write_documents(observatory_id, docs)
            self._append_history_event(observatory_id, "observatory_refreshed", {"source_hash": docs["summary"].get("source_hash"), "summary_hash": docs["summary"].get("integrity_hash")})
            return docs["summary"]

    def read_summary(self, observatory_id: str) -> dict[str, Any]:
        if not self.summary_path(observatory_id).exists():
            raise ReleaseAudioQualityObservatoryNotFoundError(f"Audio Quality Observatory summary not found: {observatory_id}.")
        return read_json(self.summary_path(observatory_id))

    def export_package(self, observatory_id: str) -> dict[str, Any]:
        with self.lock:
            config = self.read_config(observatory_id)
            docs = self._current_documents(observatory_id, config)
            export_dir = self.export_dir(observatory_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | list[dict[str, Any]] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                elif rel.endswith(".jsonl"):
                    path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in payload) + "\n", encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            write_entry("observatory-config.json", docs["config"])
            write_entry("source-index.json", docs["source_index"])
            write_entry("evidence-fingerprints.json", docs["evidence_fingerprints"])
            write_entry("trend-report.json", docs["trend_report"])
            write_entry("issue-heatmap.json", docs["issue_heatmap"])
            write_entry("baseline-drift-report.json", docs["baseline_drift"])
            write_entry("remediation-cost-report.json", docs["remediation_cost"])
            write_entry("risk-register.json", docs["risk_register"])
            write_entry("recommendation-report.json", docs["recommendation_report"])
            write_entry("observatory-summary.json", docs["summary"])
            if self.history_path(observatory_id).exists():
                write_entry("observatory-history.jsonl", _read_jsonl(self.history_path(observatory_id)))
            write_entry("README.txt", _readme(docs["summary"], docs["risk_register"]))
            manifest = sanitize_metadata(
                {
                    "package_type": RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE,
                    "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
                    "observatory_id": observatory_id,
                    "generated_at": now_iso(),
                    "source_hash": docs["summary"].get("source_hash"),
                    "config_hash": docs["config"].get("integrity_hash"),
                    "source_index_hash": docs["source_index"].get("integrity_hash"),
                    "evidence_fingerprints_hash": docs["evidence_fingerprints"].get("integrity_hash"),
                    "trend_report_hash": docs["trend_report"].get("integrity_hash"),
                    "issue_heatmap_hash": docs["issue_heatmap"].get("integrity_hash"),
                    "baseline_drift_hash": docs["baseline_drift"].get("integrity_hash"),
                    "remediation_cost_hash": docs["remediation_cost"].get("integrity_hash"),
                    "risk_register_hash": docs["risk_register"].get("integrity_hash"),
                    "recommendation_report_hash": docs["recommendation_report"].get("integrity_hash"),
                    "summary_hash": docs["summary"].get("integrity_hash"),
                    "summary": docs["summary"].get("summary", {}),
                    "files": sorted(files, key=lambda row: row["path"]),
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["summary"].get("status"), "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, observatory_id: str) -> dict[str, Any]:
        with self.lock:
            exported = self.export_package(observatory_id)
            export_dir = self.export_dir(observatory_id)
            zip_path = self.zip_path(observatory_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, observatory_id: str, **kwargs: Any) -> dict[str, Any]:
        from song_agent.release_audio_quality_observatory_verifier import verify_release_audio_quality_observatory_package, write_release_audio_quality_observatory_verification_report

        with self.lock:
            if not self.zip_path(observatory_id).exists():
                self.build_zip(observatory_id)
            kwargs.setdefault("evidence_root", self.release_store.root)
            report = verify_release_audio_quality_observatory_package(self.zip_path(observatory_id), **kwargs)
            write_release_audio_quality_observatory_verification_report(report, self.verification_report_path(observatory_id))
            return report

    def gate(self, release_id: str, *, observatory_id: str | None = None, required: bool, require_no_critical_risk: bool = True) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            observatory_id = observatory_id or self._latest_observatory_id()
            if not observatory_id:
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Observatory is missing."}
            report = self.verify_zip(observatory_id, strict=True, require_current_evidence=True, require_no_critical_risk=require_no_critical_risk)
            summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            source_releases = summary.get("release_ids") if isinstance(summary.get("release_ids"), list) else []
            if release_id not in {str(item) for item in source_releases}:
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Observatory does not cover this Release.", "verification": report}
            if report.get("status") == "failed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Observatory verification failed.", "verification": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Quality Observatory gate passed.", "verification": report, "summary": summary}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _current_documents(self, observatory_id: str, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        paths = {
            "config": self.config_path(observatory_id),
            "source_index": self.source_index_path(observatory_id),
            "evidence_fingerprints": self.evidence_fingerprints_path(observatory_id),
            "trend_report": self.trend_report_path(observatory_id),
            "issue_heatmap": self.heatmap_path(observatory_id),
            "baseline_drift": self.baseline_drift_path(observatory_id),
            "remediation_cost": self.remediation_cost_path(observatory_id),
            "risk_register": self.risk_register_path(observatory_id),
            "recommendation_report": self.recommendation_report_path(observatory_id),
            "summary": self.summary_path(observatory_id),
        }
        if all(path.exists() for path in paths.values()):
            return {key: read_json(path) for key, path in paths.items()}
        release_entries = self._release_entries(config, {})
        docs = build_observatory_documents(config, release_entries)
        self._write_documents(observatory_id, docs)
        return docs

    def _write_documents(self, observatory_id: str, docs: dict[str, dict[str, Any]]) -> None:
        root = self.observatory_dir(observatory_id)
        root.mkdir(parents=True, exist_ok=True)
        write_json(self.config_path(observatory_id), docs["config"])
        write_json(self.source_index_path(observatory_id), docs["source_index"])
        write_json(self.evidence_fingerprints_path(observatory_id), docs["evidence_fingerprints"])
        write_json(self.trend_report_path(observatory_id), docs["trend_report"])
        write_json(self.heatmap_path(observatory_id), docs["issue_heatmap"])
        write_json(self.baseline_drift_path(observatory_id), docs["baseline_drift"])
        write_json(self.remediation_cost_path(observatory_id), docs["remediation_cost"])
        write_json(self.risk_register_path(observatory_id), docs["risk_register"])
        write_json(self.recommendation_report_path(observatory_id), docs["recommendation_report"])
        write_json(self.summary_path(observatory_id), docs["summary"])

    def _release_entries(self, config: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        explicit = payload.get("releases") if isinstance(payload.get("releases"), list) else None
        if explicit is not None:
            return [_build_release_entry_from_payload(row, release_store=self.release_store) for row in explicit if isinstance(row, dict)]
        release_ids = [str(item) for item in config.get("release_ids", []) if str(item).strip()]
        releases = [self.release_store.get_release(item) for item in release_ids] if release_ids else self.release_store.list_releases(include_hidden=False)
        entries: list[dict[str, Any]] = []
        for release in releases:
            try:
                entries.append(_build_release_entry_from_paths(self.release_store.release_dir(release.release_id), release.to_dict()))
            except Exception as exc:
                entries.append({"release_id": release.release_id, "release": release.to_dict(), "status": "failed", "error": sanitize_sensitive_text(str(exc)), "components": []})
        return entries

    def _next_observatory_id(self) -> str:
        self.observatories_dir().mkdir(parents=True, exist_ok=True)
        existing = [int(match.group(1)) for path in self.observatories_dir().glob("aqo-*") if (match := re.match(r"aqo-(\d{6})$", path.name))]
        return f"aqo-{(max(existing) if existing else 0) + 1:06d}"

    def _latest_observatory_id(self) -> str | None:
        rows = []
        for config_path in self.observatories_dir().glob("*/observatory-config.json"):
            try:
                config = read_json(config_path)
            except Exception:
                continue
            rows.append((str(config.get("updated_at") or config.get("created_at") or ""), str(config.get("observatory_id") or config_path.parent.name)))
        if not rows:
            return None
        return sorted(rows, reverse=True)[0][1]

    def _append_history_event(self, observatory_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = _read_jsonl(self.history_path(observatory_id)) if self.history_path(observatory_id).exists() else []
        previous = rows[-1].get("event_hash") if rows else None
        event = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
                "event_id": f"aqoevt-{len(rows) + 1:06d}",
                "event_type": event_type,
                "created_at": now_iso(),
                "previous_event_hash": previous,
                "payload": payload,
            }
        )
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        self.history_path(observatory_id).parent.mkdir(parents=True, exist_ok=True)
        with self.history_path(observatory_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event


def build_observatory_documents(config: dict[str, Any], release_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    now = now_iso()
    config_doc = dict(config)
    config_doc["integrity_hash"] = _integrity_hash(config_doc)
    thresholds = _default_thresholds(config_doc.get("thresholds") if isinstance(config_doc.get("thresholds"), dict) else {})
    facts = [_external_facts_from_entry(entry) for entry in release_entries]
    release_rows = [_source_row(item) for item in facts]
    fingerprint_rows = [component for item in facts for component in item.get("components", [])]
    source_hash = stable_hash(
        {
            "config_hash": _stable_config_hash(config_doc),
            "release_rows": release_rows,
            "fingerprint_rows": fingerprint_rows,
            "thresholds": thresholds,
        }
    )
    source_index = {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config_doc.get("observatory_id"),
        "source_hash": source_hash,
        "release_count": len(release_rows),
        "releases": release_rows,
    }
    evidence_fingerprints = {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config_doc.get("observatory_id"),
        "source_hash": source_hash,
        "components": fingerprint_rows,
        "summary": {
            "component_count": len(fingerprint_rows),
            "failed_component_count": sum(1 for row in fingerprint_rows if row.get("status") != "passed"),
        },
    }
    trend_report = _trend_report(config_doc, facts, source_hash=source_hash)
    issue_heatmap = _issue_heatmap(config_doc, facts, source_hash=source_hash)
    baseline_drift = _baseline_drift(config_doc, facts, source_hash=source_hash)
    remediation_cost = _remediation_cost(config_doc, facts, source_hash=source_hash)
    risk_register = _risk_register(config_doc, facts, trend_report, issue_heatmap, baseline_drift, remediation_cost, thresholds=thresholds, source_hash=source_hash)
    recommendation_report = _recommendation_report(config_doc, risk_register, source_hash=source_hash)
    status = "failed" if risk_register.get("summary", {}).get("critical_risk_count", 0) else "warning" if risk_register.get("summary", {}).get("warning_risk_count", 0) else "passed"
    summary = {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "package_type": RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE,
        "observatory_id": config_doc.get("observatory_id"),
        "status": status,
        "readiness": "blocked" if status == "failed" else "warning_requires_audio_lead_review" if status == "warning" else "ready",
        "source_hash": source_hash,
        "summary": {
            "release_count": len(release_rows),
            "release_ids": [row.get("release_id") for row in release_rows if row.get("release_id")],
            "track_count": sum(int(row.get("track_count") or 0) for row in release_rows),
            "component_count": len(fingerprint_rows),
            "failed_component_count": evidence_fingerprints["summary"]["failed_component_count"],
            "critical_risk_count": risk_register["summary"]["critical_risk_count"],
            "warning_risk_count": risk_register["summary"]["warning_risk_count"],
            "average_manual_rating": trend_report["summary"]["average_manual_rating"],
            "minimum_manual_rating": trend_report["summary"]["minimum_manual_rating"],
        },
        "document_hashes": {},
        "created_at": now,
    }
    docs = {
        "config": config_doc,
        "source_index": source_index,
        "evidence_fingerprints": evidence_fingerprints,
        "trend_report": trend_report,
        "issue_heatmap": issue_heatmap,
        "baseline_drift": baseline_drift,
        "remediation_cost": remediation_cost,
        "risk_register": risk_register,
        "recommendation_report": recommendation_report,
        "summary": summary,
    }
    for key, doc in docs.items():
        if key != "summary":
            doc["integrity_hash"] = _integrity_hash(doc)
    summary["document_hashes"] = {key: doc.get("integrity_hash") for key, doc in docs.items() if key != "summary"}
    summary["integrity_hash"] = _integrity_hash(summary)
    return docs


def build_observatory_documents_from_evidence_root(config: dict[str, Any], evidence_root: Path | str) -> dict[str, dict[str, Any]]:
    root = Path(evidence_root)
    release_ids = [str(item) for item in config.get("release_ids", []) if str(item).strip()]
    candidates = [root / release_id for release_id in release_ids] if release_ids else sorted(path for path in root.glob("release-*") if path.is_dir())
    entries: list[dict[str, Any]] = []
    for release_dir in candidates:
        try:
            release_doc = read_json(release_dir / "release.json") if (release_dir / "release.json").exists() else {"release_id": release_dir.name}
            entries.append(_build_release_entry_from_paths(release_dir, release_doc))
        except Exception as exc:
            entries.append({"release_id": release_dir.name, "release": {"release_id": release_dir.name}, "status": "failed", "error": sanitize_sensitive_text(str(exc)), "components": []})
    return build_observatory_documents(config, entries)


def _build_release_entry_from_payload(row: dict[str, Any], *, release_store: ReleaseStore) -> dict[str, Any]:
    release_id = str(row.get("release_id") or "")
    release_doc = row.get("release") if isinstance(row.get("release"), dict) else {}
    if release_id and not release_doc:
        try:
            release_doc = release_store.get_release(release_id).to_dict()
        except Exception:
            release_doc = {"release_id": release_id}
    base = release_store.release_dir(release_id) if release_id else None
    paths = _explicit_paths(row)
    if not paths and base is not None:
        return _build_release_entry_from_paths(base, release_doc)
    return _build_release_entry(release_doc, paths, explicit=True)


def _build_release_entry_from_paths(release_dir: Path, release_doc: dict[str, Any]) -> dict[str, Any]:
    release_id = str(release_doc.get("release_id") or release_dir.name)
    timeline_id = _current_timeline_id(release_dir)
    paths = {
        "certification_zip": release_dir / "audio-certification" / "release-audio-certification.zip",
        "certification_verification_report": release_dir / "audio-certification" / "verification-report.json",
        "timeline_zip": release_dir / "audio-timelines" / timeline_id / "release-audio-timeline.zip" if timeline_id else None,
        "timeline_verification_report": release_dir / "audio-timelines" / timeline_id / "verification-report.json" if timeline_id else None,
        "regression_zip": release_dir / "audio-regression" / "release-audio-regression.zip",
        "regression_verification_report": release_dir / "audio-regression" / "verification-report.json",
        "regression_response_zip": release_dir / "audio-regression-response" / "release-audio-regression-response.zip",
        "regression_response_verification_report": release_dir / "audio-regression-response" / "verification-report.json",
    }
    return _build_release_entry({"release_id": release_id, **release_doc}, paths, explicit=False)


def _build_release_entry(release_doc: dict[str, Any], paths: dict[str, Path | None], *, explicit: bool) -> dict[str, Any]:
    release_id = str(release_doc.get("release_id") or "")
    components: list[dict[str, Any]] = []
    cert = _verification_component("release_audio_certification", release_id, paths.get("certification_zip"), paths.get("certification_verification_report"), verifier="certification")
    timeline = _verification_component(
        "release_audio_timeline",
        release_id,
        paths.get("timeline_zip"),
        paths.get("timeline_verification_report"),
        verifier="timeline",
        certification_zip=paths.get("certification_zip"),
        certification_report=paths.get("certification_verification_report"),
    )
    components.extend([cert, timeline])
    for component_type, zip_key, report_key in (
        ("release_audio_regression", "regression_zip", "regression_verification_report"),
        ("release_audio_regression_response", "regression_response_zip", "regression_response_verification_report"),
    ):
        component = _basic_component(component_type, release_id, paths.get(zip_key), paths.get(report_key))
        if component.get("present"):
            components.append(component)
    facts = _timeline_facts(paths.get("timeline_zip")) if timeline.get("status") == "passed" and paths.get("timeline_zip") else {"tracks": [], "issues": [], "release_id": release_id}
    status = "passed" if cert.get("status") == "passed" and timeline.get("status") == "passed" else "failed"
    return {
        "release_id": release_id,
        "release": release_doc,
        "explicit": explicit,
        "status": status,
        "components": components,
        "facts": facts,
    }


def _verification_component(
    component_type: str,
    release_id: str,
    zip_path: Path | None,
    report_path: Path | None,
    *,
    verifier: str,
    certification_zip: Path | None = None,
    certification_report: Path | None = None,
) -> dict[str, Any]:
    if not zip_path or not report_path or not Path(zip_path).exists() or not Path(report_path).exists():
        return {"component_type": component_type, "release_id": release_id, "present": False, "status": "missing", "message": f"{component_type} evidence is missing."}
    zip_path = Path(zip_path)
    report_path = Path(report_path)
    try:
        report = read_json(report_path)
        runtime = (
            verify_release_audio_certification_package(zip_path, strict=True, require_passed=True, require_signed=True, require_real_audio=True, require_manual_review=True, require_remediation_when_needed=True)
            if verifier == "certification"
            else verify_release_audio_timeline_package(
                zip_path,
                strict=True,
                require_passed=True,
                require_signed=True,
                require_real_audio=True,
                require_manual_review=True,
                require_current_certification=True,
                release_audio_certification_path=certification_zip,
                release_audio_certification_verification_report_path=certification_report,
            )
        )
        report_ok = _integrity_ok(report) and report.get("status") == "passed" and report.get("zip_sha256") == _sha256_path(zip_path) and report.get("zip_size_bytes") == zip_path.stat().st_size and report.get("manifest_hash") == runtime.get("manifest_hash")
        runtime_ok = runtime.get("status") == "passed"
        return {
            "component_type": component_type,
            "release_id": release_id,
            "present": True,
            "status": "passed" if report_ok and runtime_ok else "failed",
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_report_hash": report.get("integrity_hash"),
            "verification_status": report.get("status"),
            "runtime_status": runtime.get("status"),
            "package_type": report.get("package_type"),
        }
    except Exception as exc:
        return {"component_type": component_type, "release_id": release_id, "present": True, "status": "failed", "message": sanitize_sensitive_text(str(exc))}


def _basic_component(component_type: str, release_id: str, zip_path: Path | None, report_path: Path | None) -> dict[str, Any]:
    if not zip_path or not report_path or not Path(zip_path).exists() or not Path(report_path).exists():
        return {"component_type": component_type, "release_id": release_id, "present": False, "status": "missing"}
    zip_path = Path(zip_path)
    try:
        report = read_json(Path(report_path))
        ok = _integrity_ok(report) and report.get("status") == "passed" and report.get("zip_sha256") == _sha256_path(zip_path) and int(report.get("zip_size_bytes") or -1) == zip_path.stat().st_size
        return {
            "component_type": component_type,
            "release_id": release_id,
            "present": True,
            "status": "passed" if ok else "failed",
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": report.get("manifest_hash"),
            "verification_report_hash": report.get("integrity_hash"),
            "verification_status": report.get("status"),
            "package_type": report.get("package_type"),
        }
    except Exception as exc:
        return {"component_type": component_type, "release_id": release_id, "present": True, "status": "failed", "message": sanitize_sensitive_text(str(exc))}


def _timeline_facts(timeline_zip: Path | None) -> dict[str, Any]:
    if not timeline_zip or not Path(timeline_zip).exists():
        return {"tracks": [], "issues": []}
    with zipfile.ZipFile(Path(timeline_zip)) as archive:
        report = _read_json_entry(archive, "audio-timeline-report.json")
        track_index = _read_json_entry(archive, "track-timeline-index.json")
        taxonomy = _read_json_entry(archive, "issue-taxonomy.json")
        trend = _read_json_entry(archive, "quality-trend.json")
    tracks: list[dict[str, Any]] = []
    for row in track_index.get("tracks") or []:
        if not isinstance(row, dict):
            continue
        tracks.append(
            {
                "track_id": row.get("track_id"),
                "project_id": row.get("project_id"),
                "version_id": row.get("version_id"),
                "title": row.get("title"),
                "normalized_title": _normalize_title(row.get("title")),
                "final_export_hash": row.get("final_export_hash"),
                "manual_rating": _manual_rating(row),
                "review_status": row.get("review_status") or row.get("status"),
                "manual_review_count": int(row.get("manual_review_count") or 0),
                "real_audio_review_count": int(row.get("real_audio_review_count") or 0),
                "test_fake_count": int(row.get("test_fake_count") or 0),
                "open_issue_count": int(row.get("open_issue_count") or 0),
                "high_issue_count": int(row.get("high_issue_count") or 0),
                "critical_issue_count": int(row.get("critical_issue_count") or 0),
                "needs_fix_count": 1 if row.get("review_status") == "needs_fix" else 0,
                "rejected_count": 1 if row.get("review_status") == "rejected" else 0,
                "remediation_count": int(row.get("fix_sprint_count") or 0),
            }
        )
    issues = [item for item in taxonomy.get("issues") or [] if isinstance(item, dict)]
    return {"release_id": report.get("release_id"), "tracks": tracks, "issues": issues, "trend_summary": trend.get("summary") or {}}


def _source_row(facts: dict[str, Any]) -> dict[str, Any]:
    tracks = facts.get("facts", {}).get("tracks", []) if isinstance(facts.get("facts"), dict) else []
    return {
        "release_id": facts.get("release_id"),
        "status": facts.get("status"),
        "track_count": len(tracks),
        "average_manual_rating": _avg([_num(track.get("manual_rating")) for track in tracks if _num(track.get("manual_rating")) is not None]),
        "minimum_manual_rating": _min([_num(track.get("manual_rating")) for track in tracks if _num(track.get("manual_rating")) is not None]),
        "high_issue_count": sum(int(track.get("high_issue_count") or 0) for track in tracks),
        "critical_issue_count": sum(int(track.get("critical_issue_count") or 0) for track in tracks),
        "needs_fix_count": sum(int(track.get("needs_fix_count") or 0) for track in tracks),
        "remediation_count": sum(int(track.get("remediation_count") or 0) for track in tracks),
        "component_statuses": {row.get("component_type"): row.get("status") for row in facts.get("components", []) if row.get("present", True)},
    }


def _external_facts_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {"release_id": entry.get("release_id"), "status": entry.get("status"), "release": entry.get("release") or {}, "components": entry.get("components") or [], "facts": entry.get("facts") or {"tracks": [], "issues": []}}


def _trend_report(config: dict[str, Any], facts: list[dict[str, Any]], *, source_hash: str) -> dict[str, Any]:
    releases = [_source_row(item) for item in facts]
    ratings = [row["average_manual_rating"] for row in releases if row.get("average_manual_rating") is not None]
    min_ratings = [row["minimum_manual_rating"] for row in releases if row.get("minimum_manual_rating") is not None]
    return {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config.get("observatory_id"),
        "source_hash": source_hash,
        "release_trends": releases,
        "summary": {
            "release_count": len(releases),
            "average_manual_rating": _avg(ratings),
            "minimum_manual_rating": _min(min_ratings),
            "average_rating_delta": round(ratings[-1] - ratings[0], 4) if len(ratings) >= 2 else 0.0,
            "high_issue_count": sum(int(row.get("high_issue_count") or 0) for row in releases),
            "critical_issue_count": sum(int(row.get("critical_issue_count") or 0) for row in releases),
        },
    }


def _issue_heatmap(config: dict[str, Any], facts: list[dict[str, Any]], *, source_hash: str) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in facts:
        release_id = item.get("release_id")
        for issue in item.get("facts", {}).get("issues", []) if isinstance(item.get("facts"), dict) else []:
            issue_type = str(issue.get("issue_type") or issue.get("category") or issue.get("check_id") or "unknown")
            bucket = buckets.setdefault(issue_type, {"issue_type": issue_type, "release_ids": set(), "high_count": 0, "critical_count": 0, "open_count": 0})
            bucket["release_ids"].add(release_id)
            severity = str(issue.get("severity_max") or issue.get("severity") or "info")
            count = int(issue.get("open_count") or issue.get("count") or 1)
            bucket["open_count"] += count
            if severity == "high":
                bucket["high_count"] += count
            if severity in {"critical", "blocking"}:
                bucket["critical_count"] += count
    rows = [{**value, "release_ids": sorted(value["release_ids"])} for value in buckets.values()]
    return {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config.get("observatory_id"),
        "source_hash": source_hash,
        "issues": sorted(rows, key=lambda row: (-int(row.get("critical_count") or 0), -int(row.get("high_count") or 0), row.get("issue_type") or "")),
        "summary": {"issue_type_count": len(rows), "critical_issue_count": sum(int(row.get("critical_count") or 0) for row in rows), "high_issue_count": sum(int(row.get("high_count") or 0) for row in rows)},
    }


def _baseline_drift(config: dict[str, Any], facts: list[dict[str, Any]], *, source_hash: str) -> dict[str, Any]:
    release_rows = [_source_row(item) for item in facts]
    drift_rows: list[dict[str, Any]] = []
    if len(release_rows) >= 2:
        first = release_rows[0]
        latest = release_rows[-1]
        drift_rows.append(
            {
                "metric": "average_manual_rating",
                "baseline_value": first.get("average_manual_rating"),
                "current_value": latest.get("average_manual_rating"),
                "delta": _delta(latest.get("average_manual_rating"), first.get("average_manual_rating")),
                "status": "warning" if _delta(latest.get("average_manual_rating"), first.get("average_manual_rating")) < 0 else "passed",
            }
        )
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "drift": drift_rows, "summary": {"drift_count": len([row for row in drift_rows if row.get("status") != "passed"])}}


def _remediation_cost(config: dict[str, Any], facts: list[dict[str, Any]], *, source_hash: str) -> dict[str, Any]:
    rows = []
    for item in facts:
        source = _source_row(item)
        rows.append({"release_id": item.get("release_id"), "remediation_count": source.get("remediation_count"), "needs_fix_count": source.get("needs_fix_count"), "high_issue_count": source.get("high_issue_count"), "critical_issue_count": source.get("critical_issue_count")})
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "rows": rows, "summary": {"remediation_count": sum(int(row.get("remediation_count") or 0) for row in rows), "needs_fix_count": sum(int(row.get("needs_fix_count") or 0) for row in rows)}}


def _risk_register(config: dict[str, Any], facts: list[dict[str, Any]], trend: dict[str, Any], heatmap: dict[str, Any], drift: dict[str, Any], remediation: dict[str, Any], *, thresholds: dict[str, Any], source_hash: str) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    for item in facts:
        failed = [component for component in item.get("components", []) if component.get("present", True) and component.get("status") != "passed"]
        if failed or item.get("status") != "passed":
            risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "audio_evidence_not_current", "release_id": item.get("release_id"), "severity": "critical", "status": "failed", "message": "Release audio evidence is missing, stale, or failed.", "components": failed})
    min_rating = trend.get("summary", {}).get("minimum_manual_rating")
    if min_rating is not None and float(min_rating) < float(thresholds.get("min_manual_rating", 3.0)):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "manual_rating_floor", "severity": "critical", "status": "failed", "message": "A release has manual audio rating below policy floor.", "value": min_rating})
    rating_delta = trend.get("summary", {}).get("average_rating_delta")
    if rating_delta is not None and float(rating_delta) < -float(thresholds.get("max_average_rating_drop", 0.25)):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "quality_trend_decline", "severity": "high", "status": "warning", "message": "Average manual rating declined across the observation window.", "delta": rating_delta})
    if int(heatmap.get("summary", {}).get("critical_issue_count") or 0) > int(thresholds.get("max_critical_issue_count", 0) or 0):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "critical_issue_hotspot", "severity": "critical", "status": "failed", "message": "Critical audio issue hotspot detected."})
    if int(remediation.get("summary", {}).get("needs_fix_count") or 0) > int(thresholds.get("max_needs_fix_count", 0) or 0):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "needs_fix_backlog", "severity": "high", "status": "warning", "message": "Needs-fix backlog is present."})
    critical = [risk for risk in risks if risk.get("status") == "failed" or risk.get("severity") == "critical"]
    warnings = [risk for risk in risks if risk not in critical]
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "status": "failed" if critical else "warning" if warnings else "passed", "risks": risks, "summary": {"risk_count": len(risks), "critical_risk_count": len(critical), "warning_risk_count": len(warnings)}}


def _recommendation_report(config: dict[str, Any], risk_register: dict[str, Any], *, source_hash: str) -> dict[str, Any]:
    recommendations = []
    for risk in risk_register.get("risks") or []:
        action = "refresh_audio_evidence" if risk.get("check_id") == "audio_evidence_not_current" else "open_audio_quality_review"
        recommendations.append({"recommendation_id": f"aqrec-{len(recommendations)+1:06d}", "source_risk_id": risk.get("risk_id"), "action": action, "manual_required": True, "reason": risk.get("message")})
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "recommendations": recommendations, "summary": {"recommendation_count": len(recommendations)}}


def _explicit_paths(row: dict[str, Any]) -> dict[str, Path | None]:
    mapping = {
        "certification_zip": ("certification", "certification_zip", "certification_zip_path", "release_audio_certification"),
        "certification_verification_report": ("certification_verification_report", "certification_verification_report_path", "release_audio_certification_verification_report"),
        "timeline_zip": ("timeline", "timeline_zip", "timeline_zip_path", "release_audio_timeline"),
        "timeline_verification_report": ("timeline_verification_report", "timeline_verification_report_path", "release_audio_timeline_verification_report"),
        "regression_zip": ("regression", "regression_zip", "regression_zip_path", "release_audio_regression"),
        "regression_verification_report": ("regression_verification_report", "regression_verification_report_path", "release_audio_regression_verification_report"),
        "regression_response_zip": ("regression_response", "regression_response_zip", "regression_response_zip_path", "release_audio_regression_response"),
        "regression_response_verification_report": ("regression_response_verification_report", "regression_response_verification_report_path", "release_audio_regression_response_verification_report"),
    }
    result: dict[str, Path | None] = {}
    for key, names in mapping.items():
        value = None
        for name in names:
            if row.get(name):
                value = row.get(name)
                break
        result[key] = Path(value) if value else None
    return {key: value for key, value in result.items() if value is not None}


def _current_timeline_id(release_dir: Path) -> str | None:
    current_path = release_dir / "audio-timelines" / "current-timeline.json"
    if current_path.exists():
        try:
            current = read_json(current_path)
            if current.get("timeline_id"):
                return str(current.get("timeline_id"))
        except Exception:
            pass
    candidates = sorted((release_dir / "audio-timelines").glob("*/audio-timeline-report.json"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return candidates[0].parent.name if candidates else None


def _default_window(overrides: dict[str, Any]) -> dict[str, Any]:
    window = {"max_release_count": 12, "include_hidden": False}
    window.update({key: overrides[key] for key in window if key in overrides})
    return window


def _default_thresholds(overrides: dict[str, Any]) -> dict[str, Any]:
    thresholds = {"min_manual_rating": 3.0, "max_average_rating_drop": 0.25, "max_critical_issue_count": 0, "max_needs_fix_count": 0}
    thresholds.update({key: overrides[key] for key in thresholds if key in overrides})
    return thresholds


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_observatory_id(value: str) -> str:
    if not re.fullmatch(r"aqo-\d{6}", value):
        raise ReleaseAudioQualityObservatoryValidationError(f"Invalid observatory_id: {value}.")
    return value


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _stable_config_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key not in {"integrity_hash", "created_at", "updated_at"}})


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _file_record(path: Path, root: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _readme(summary: dict[str, Any], risks: dict[str, Any]) -> str:
    data = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    risk_summary = risks.get("summary") if isinstance(risks.get("summary"), dict) else {}
    return "\n".join(
        [
            "MusicForge Release Audio Quality Observatory",
            f"observatory_id: {summary.get('observatory_id')}",
            f"status: {summary.get('status')}",
            f"release_count: {data.get('release_count')}",
            f"critical_risk_count: {risk_summary.get('critical_risk_count')}",
            "",
            "This package contains public-safe quality summaries and fingerprints only.",
            "It does not embed audio files or local workspace paths.",
            "",
        ]
    )


def _avg(values: list[float | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else None


def _min(values: list[float | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return min(numbers) if numbers else None


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(current: Any, baseline: Any) -> float:
    current_num = _num(current)
    baseline_num = _num(baseline)
    if current_num is None or baseline_num is None:
        return 0.0
    return round(current_num - baseline_num, 4)


def _manual_rating(row: dict[str, Any]) -> float | None:
    for key in ("manual_rating", "rating", "review_rating", "latest_manual_rating"):
        value = _num(row.get(key))
        if value is not None:
            return value
    for key in ("manual_review", "review"):
        nested = row.get(key)
        if isinstance(nested, dict):
            value = _num(nested.get("rating"))
            if value is not None:
                return value
    if row.get("review_status") == "accepted":
        return 4.0
    if row.get("review_status") == "needs_fix":
        return 2.5
    if row.get("review_status") == "rejected":
        return 1.0
    return None


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
