from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.lifecycle import HistoryChain
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package as verify_release_audio_timeline_package
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.release_audio_quality_observatory_semantics import RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE, RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION as RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, _avg as _avg, _baseline_drift as _baseline_drift, _basic_component as _basic_component, _build_release_entry as _build_release_entry, _build_release_entry_from_paths as _build_release_entry_from_paths, _current_timeline_id as _current_timeline_id, _default_thresholds as _default_thresholds, _delta as _delta, _external_facts_from_entry as _external_facts_from_entry, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _issue_heatmap as _issue_heatmap, _manual_rating as _manual_rating, _min as _min, _normalize_title as _normalize_title, _num as _num, _read_json_entry as _read_json_entry, _recommendation_report as _recommendation_report, _remediation_cost as _remediation_cost, _risk_register as _risk_register, _sha256_path as _sha256_path, _source_row as _source_row, _stable_config_hash as _stable_config_hash, _timeline_facts as _timeline_facts, _trend_report as _trend_report, _verification_component as _verification_component, build_observatory_documents as build_observatory_documents, build_observatory_documents_from_evidence_root as build_observatory_documents_from_evidence_root






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
            self._record_history_event(observatory_id, "observatory_created", {"config_hash": config["integrity_hash"]})
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
            self._record_history_event(observatory_id, "observatory_refreshed", {"source_hash": docs["summary"].get("source_hash"), "summary_hash": docs["summary"].get("integrity_hash")})
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
        from song_agent.domains.quality.release_audio_quality_observatory_verifier import verify_release_audio_quality_observatory_package, write_release_audio_quality_observatory_verification_report

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

    def _current_documents(self, observatory_id: str, config: ImplementationDocument) -> dict[str, ImplementationDocument]:
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

    def _write_documents(self, observatory_id: str, docs: dict[str, ImplementationDocument]) -> None:
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

    def _release_entries(self, config: ImplementationDocument, payload: ImplementationDocument) -> list[ImplementationDocument]:
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

    def _record_history_event(self, observatory_id: str, event_type: str, payload: ImplementationDocument) -> ImplementationDocument:
        chain = HistoryChain(self.history_path(observatory_id), sanitizer=sanitize_metadata, hash_mode="payload")
        rows = chain.read()
        return chain.append(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
                "event_id": f"aqoevt-{len(rows) + 1:06d}",
                "event_type": event_type,
                "created_at": now_iso(),
                "payload": payload,
            }
        )








def _build_release_entry_from_payload(row: ImplementationDocument, *, release_store: ReleaseStore) -> ImplementationDocument:
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









































def _explicit_paths(row: ImplementationDocument) -> dict[str, Path | None]:
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





def _default_window(overrides: ImplementationDocument) -> ImplementationDocument:
    window = {"max_release_count": 12, "include_hidden": False}
    window.update({key: overrides[key] for key in window if key in overrides})
    return window





def _safe_dict(value: Any) -> ImplementationDocument:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_observatory_id(value: str) -> str:
    if not re.fullmatch(r"aqo-\d{6}", value):
        raise ReleaseAudioQualityObservatoryValidationError(f"Invalid observatory_id: {value}.")
    return value

















def _read_jsonl(path: Path) -> list[ImplementationDocument]:
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


def _file_record(path: Path, root: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _readme(summary: ImplementationDocument, risks: ImplementationDocument) -> str:
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
