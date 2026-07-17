from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.lifecycle import HistoryChain
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_certification import ReleaseAudioCertificationStore as ReleaseAudioCertificationStore
from song_agent.domains.quality.release_audio_regression_verifier import RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE as RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE, RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION as RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION, build_regression_documents_from_bindings as build_regression_documents_from_bindings, verify_release_audio_regression_package as verify_release_audio_regression_package, write_release_audio_regression_verification_report as write_release_audio_regression_verification_report
from song_agent.domains.quality.release_audio_timeline import ReleaseAudioTimelineStore as ReleaseAudioTimelineStore
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash


class ReleaseAudioRegressionError(ValueError):
    pass


class ReleaseAudioRegressionNotFoundError(ReleaseAudioRegressionError):
    pass


class ReleaseAudioRegressionStateError(ReleaseAudioRegressionError):
    pass


class ReleaseAudioRegressionValidationError(ReleaseAudioRegressionError):
    pass


class ReleaseAudioRegressionStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        certification_store: ReleaseAudioCertificationStore | None = None,
        timeline_store: ReleaseAudioTimelineStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.certification_store = certification_store or ReleaseAudioCertificationStore(release_store=self.release_store)
        self.timeline_store = timeline_store or ReleaseAudioTimelineStore(release_store=self.release_store, certification_store=self.certification_store)
        self.lock = threading.RLock()

    def regression_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-regression"

    def config_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "regression-config.json"

    def report_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "regression-report.json"

    def matrix_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "track-regression-matrix.json"

    def issue_index_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "issue-regression-index.json"

    def quality_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "quality-delta-summary.json"

    def blocker_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "blocker-register.json"

    def baseline_binding_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "baseline-binding.json"

    def current_binding_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "current-binding.json"

    def signoff_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "regression-signoff.json"

    def history_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "regression-signoff-history.jsonl"

    def export_dir(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "export"

    def zip_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "release-audio-regression.zip"

    def verification_report_path(self, release_id: str) -> Path:
        return self.regression_dir(release_id) / "verification-report.json"

    def configure_baseline(self, release_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionStateError("Signed Release Audio Regression cannot be reconfigured. Reset signoff before changing baseline.")
            config = {
                "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
                "release_id": release_id,
                "baseline": {
                    "release_id": payload.get("baseline_release_id") or payload.get("baseline", {}).get("release_id"),
                    "timeline_zip_path": str(payload.get("baseline_timeline") or payload.get("baseline_timeline_zip_path") or ""),
                    "timeline_verification_report_path": str(payload.get("baseline_timeline_verification_report") or payload.get("baseline_timeline_verification_report_path") or ""),
                    "certification_zip_path": str(payload.get("baseline_certification") or payload.get("baseline_certification_zip_path") or ""),
                    "certification_verification_report_path": str(payload.get("baseline_certification_verification_report") or payload.get("baseline_certification_verification_report_path") or ""),
                },
                "current": {
                    "timeline_zip_path": str(payload.get("current_timeline") or payload.get("current_timeline_zip_path") or self._current_timeline_zip_path(release_id) or ""),
                    "timeline_verification_report_path": str(payload.get("current_timeline_verification_report") or payload.get("current_timeline_verification_report_path") or self._current_timeline_verification_path(release_id) or ""),
                    "certification_zip_path": str(payload.get("current_certification") or payload.get("current_certification_zip_path") or self.certification_store.zip_path(release_id)),
                    "certification_verification_report_path": str(payload.get("current_certification_verification_report") or payload.get("current_certification_verification_report_path") or self.certification_store.verification_report_path(release_id)),
                },
                "policy": _default_policy(_as_document(payload.get("policy"))),
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            config["integrity_hash"] = _integrity_hash(config)
            self.regression_dir(release_id).mkdir(parents=True, exist_ok=True)
            write_json(self.config_path(release_id), config)
            return config

    def read_config(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.config_path(release_id).exists():
            if default is not None:
                return default
            raise ReleaseAudioRegressionNotFoundError(f"Release Audio Regression config not found: {release_id}.")
        return read_json(self.config_path(release_id))

    def read_report(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.report_path(release_id).exists():
            if default is not None:
                return default
            raise ReleaseAudioRegressionNotFoundError(f"Release Audio Regression report not found: {release_id}.")
        return read_json(self.report_path(release_id))

    def refresh_report(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionStateError("Signed Release Audio Regression cannot be refreshed. Reset signoff before refreshing.")
            docs = self._build_documents(release_id)
            self._write_documents(release_id, docs)
            return docs["report"]

    def signoff(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionStateError("Release Audio Regression is already signed.")
            docs = self._build_documents(release_id)
            if docs["report"].get("status") == "failed":
                raise ReleaseAudioRegressionStateError("Release Audio Regression has blockers.")
            self._write_documents(release_id, docs)
            signoff = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
                    "signoff_id": f"rargs-{release_id}",
                    "release_id": release_id,
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-regression", 120),
                    "role": _bounded(payload.get("role") or "audio-regression-reviewer", 80),
                    "reason": _bounded(payload.get("reason") or "Release audio regression guard accepted.", 1000),
                    "source_hash": docs["report"].get("source_hash"),
                    "regression_report_hash": docs["report"].get("integrity_hash"),
                    "track_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "issue_index_hash": docs["issue_index"].get("integrity_hash"),
                    "quality_delta_hash": docs["quality"].get("integrity_hash"),
                    "blocker_register_hash": docs["blockers"].get("integrity_hash"),
                    "baseline_binding_hash": docs["baseline"].get("integrity_hash"),
                    "current_binding_hash": docs["current"].get("integrity_hash"),
                    "summary": docs["report"].get("summary", {}),
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(release_id), signoff)
            self._record_history_event(
                release_id,
                "regression_signoff_created",
                {
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "report_hash": docs["report"].get("integrity_hash"),
                    "track_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "issue_index_hash": docs["issue_index"].get("integrity_hash"),
                    "quality_delta_hash": docs["quality"].get("integrity_hash"),
                    "blocker_register_hash": docs["blockers"].get("integrity_hash"),
                    "baseline_binding_hash": docs["baseline"].get("integrity_hash"),
                    "current_binding_hash": docs["current"].get("integrity_hash"),
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason_hash": stable_hash(signoff.get("reason")),
                },
            )
            return {"status": "signed", "signoff": signoff, "report": docs["report"]}

    def export_package(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._current_docs_for_export(release_id)
            export_dir = self.export_dir(release_id)
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

            write_entry("regression-report.json", docs["report"])
            write_entry("track-regression-matrix.json", docs["matrix"])
            write_entry("issue-regression-index.json", docs["issue_index"])
            write_entry("quality-delta-summary.json", docs["quality"])
            write_entry("blocker-register.json", docs["blockers"])
            write_entry("baseline-binding.json", docs["baseline"])
            write_entry("current-binding.json", docs["current"])
            if self.signoff_path(release_id).exists():
                write_entry("regression-signoff.json", read_json(self.signoff_path(release_id)))
                write_entry("regression-signoff-history.jsonl", _read_jsonl(self.history_path(release_id)))
            write_entry("README.txt", _readme(docs["report"], docs["matrix"], docs["quality"]))
            signoff = read_json(self.signoff_path(release_id)) if self.signoff_path(release_id).exists() else {}
            manifest = sanitize_metadata(
                {
                    "package_type": RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE,
                    "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "baseline_release_id": docs["report"].get("baseline_release_id"),
                    "generated_at": now_iso(),
                    "source_hash": docs["report"].get("source_hash"),
                    "report_hash": docs["report"].get("integrity_hash"),
                    "track_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "issue_index_hash": docs["issue_index"].get("integrity_hash"),
                    "quality_delta_hash": docs["quality"].get("integrity_hash"),
                    "blocker_register_hash": docs["blockers"].get("integrity_hash"),
                    "baseline_binding_hash": docs["baseline"].get("integrity_hash"),
                    "current_binding_hash": docs["current"].get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "summary": docs["report"].get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["report"].get("status"), "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            exported = self.export_package(release_id)
            export_dir = self.export_dir(release_id)
            zip_path = self.zip_path(release_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(item.filename for item in archive.infolist())
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

    def verify_zip(self, release_id: str, **kwargs: Any) -> dict[str, Any]:
        with self.lock:
            if not self.zip_path(release_id).exists():
                self.build_zip(release_id)
            config = self.read_config(release_id)
            kwargs = self._with_default_evidence_args(config, kwargs)
            report = verify_release_audio_regression_package(self.zip_path(release_id), **kwargs)
            write_release_audio_regression_verification_report(report, self.verification_report_path(release_id))
            return report

    def gate(self, release_id: str, *, required: bool, require_signed: bool = False) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            docs = self._build_documents(release_id)
            report = docs["report"]
            if report.get("status") == "failed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Regression guard has blockers.", "report": report, "summary": report.get("summary", {})}
            if require_signed:
                signoff = read_json(self.signoff_path(release_id)) if self.signoff_path(release_id).exists() else {}
                if signoff.get("status") != "signed":
                    return {"status": "failed", "hard_block": True, "message": "Release Audio Regression signoff is missing.", "report": report}
                self._ensure_signed_export_integrity(release_id)
            return {"status": "passed", "hard_block": False, "message": "Release Audio Regression gate passed.", "report": report, "summary": report.get("summary", {})}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _build_documents(self, release_id: str) -> dict[str, ImplementationDocument]:
        config = self.read_config(release_id)
        baseline = self._binding_from_config("baseline", _as_document(config.get("baseline")))
        current = self._binding_from_config("current", _as_document(config.get("current")))
        docs = build_regression_documents_from_bindings(baseline, current, policy=_as_document(config.get("policy")))
        return {"baseline": baseline, "current": current, **docs}

    def _binding_from_config(self, kind: str, config: ImplementationDocument) -> ImplementationDocument:
        from song_agent.domains.quality.release_audio_regression_verifier import _external_facts

        facts = _external_facts(
            kind,
            timeline_path=config.get("timeline_zip_path"),
            timeline_report_path=config.get("timeline_verification_report_path"),
            certification_path=config.get("certification_zip_path"),
            certification_report_path=config.get("certification_verification_report_path"),
            required=True,
        )
        failed_checks = [check for check in facts.get("checks", []) if check.get("status") == "failed"]
        if failed_checks or not facts.get("binding"):
            raise ReleaseAudioRegressionStateError(f"{kind.title()} audio evidence is not current.")
        return facts["binding"]

    def _write_documents(self, release_id: str, docs: dict[str, ImplementationDocument]) -> None:
        root = self.regression_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        write_json(self.baseline_binding_path(release_id), docs["baseline"])
        write_json(self.current_binding_path(release_id), docs["current"])
        write_json(self.report_path(release_id), docs["report"])
        write_json(self.matrix_path(release_id), docs["matrix"])
        write_json(self.issue_index_path(release_id), docs["issue_index"])
        write_json(self.quality_path(release_id), docs["quality"])
        write_json(self.blocker_path(release_id), docs["blockers"])

    def _current_docs_for_export(self, release_id: str) -> dict[str, ImplementationDocument]:
        if self.signoff_path(release_id).exists():
            docs = {
                "report": self.read_report(release_id),
                "matrix": read_json(self.matrix_path(release_id)),
                "issue_index": read_json(self.issue_index_path(release_id)),
                "quality": read_json(self.quality_path(release_id)),
                "blockers": read_json(self.blocker_path(release_id)),
                "baseline": read_json(self.baseline_binding_path(release_id)),
                "current": read_json(self.current_binding_path(release_id)),
            }
            current = self._build_documents(release_id)
            if current["report"].get("source_hash") != docs["report"].get("source_hash") or current["report"].get("status") != docs["report"].get("status"):
                raise ReleaseAudioRegressionStateError("Release Audio Regression source is stale. Reset signoff before exporting.")
            self._ensure_signed_export_integrity(release_id, docs=docs)
            return docs
        if self._has_active_signoff(release_id):
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff history is active but signoff file is missing. Reset signoff before exporting.")
        docs = self._build_documents(release_id)
        self._write_documents(release_id, docs)
        return docs

    def _ensure_signed_export_integrity(self, release_id: str, *, docs: dict[str, ImplementationDocument] | None = None) -> None:
        if not self.signoff_path(release_id).exists():
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff is missing.")
        signoff = read_json(self.signoff_path(release_id))
        if signoff.get("status") != "signed":
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff is not signed.")
        if signoff.get("integrity_hash") != _integrity_hash(signoff):
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff integrity failed.")
        docs = docs or {
            "report": self.read_report(release_id),
            "matrix": read_json(self.matrix_path(release_id)),
            "issue_index": read_json(self.issue_index_path(release_id)),
            "quality": read_json(self.quality_path(release_id)),
            "blockers": read_json(self.blocker_path(release_id)),
            "baseline": read_json(self.baseline_binding_path(release_id)),
            "current": read_json(self.current_binding_path(release_id)),
        }
        bindings = {
            "regression_report_hash": docs["report"].get("integrity_hash"),
            "track_matrix_hash": docs["matrix"].get("integrity_hash"),
            "issue_index_hash": docs["issue_index"].get("integrity_hash"),
            "quality_delta_hash": docs["quality"].get("integrity_hash"),
            "blocker_register_hash": docs["blockers"].get("integrity_hash"),
            "baseline_binding_hash": docs["baseline"].get("integrity_hash"),
            "current_binding_hash": docs["current"].get("integrity_hash"),
        }
        for key, value in bindings.items():
            if signoff.get(key) != value:
                raise ReleaseAudioRegressionStateError(f"Release Audio Regression signoff binding mismatch: {key}.")
        rows = _read_jsonl(self.history_path(release_id)) if self.history_path(release_id).exists() else []
        if not rows or not _history_chain_ok(rows):
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff history integrity failed.")
        latest = rows[-1]
        payload = _as_document(latest.get("payload"))
        if latest.get("event_type") != "regression_signoff_created":
            raise ReleaseAudioRegressionStateError("Release Audio Regression latest history event is not signed.")
        if payload.get("signoff_hash") != signoff.get("integrity_hash"):
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff history does not match current signoff.")
        if payload.get("signoff_payload_hash") != signoff.get("payload_hash"):
            raise ReleaseAudioRegressionStateError("Release Audio Regression signoff payload history does not match current signoff.")
        history_bindings = {
            "report_hash": docs["report"].get("integrity_hash"),
            "track_matrix_hash": docs["matrix"].get("integrity_hash"),
            "issue_index_hash": docs["issue_index"].get("integrity_hash"),
            "quality_delta_hash": docs["quality"].get("integrity_hash"),
            "blocker_register_hash": docs["blockers"].get("integrity_hash"),
            "baseline_binding_hash": docs["baseline"].get("integrity_hash"),
            "current_binding_hash": docs["current"].get("integrity_hash"),
        }
        for key, value in history_bindings.items():
            if payload.get(key) != value:
                raise ReleaseAudioRegressionStateError(f"Release Audio Regression signoff history binding mismatch: {key}.")

    def _record_history_event(self, release_id: str, event_type: str, payload: ImplementationDocument) -> ImplementationDocument:
        chain = HistoryChain(self.history_path(release_id), sanitizer=sanitize_metadata, hash_mode="payload")
        rows = chain.read()
        return chain.append(
            {
                "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
                "event_id": f"rargevt-{len(rows) + 1:06d}",
                "event_type": event_type,
                "created_at": now_iso(),
                "payload": payload,
            }
        )

    def _has_active_signoff(self, release_id: str) -> bool:
        if self.signoff_path(release_id).exists():
            return True
        rows = _read_jsonl(self.history_path(release_id)) if self.history_path(release_id).exists() else []
        if not rows or not _history_chain_ok(rows):
            return False
        latest = rows[-1]
        return latest.get("event_type") == "regression_signoff_created"

    def _with_default_evidence_args(self, config: ImplementationDocument, kwargs: ImplementationDocument) -> ImplementationDocument:
        baseline = _as_document(config.get("baseline"))
        current = _as_document(config.get("current"))
        defaults = {
            "baseline_timeline_path": baseline.get("timeline_zip_path"),
            "baseline_timeline_verification_report_path": baseline.get("timeline_verification_report_path"),
            "baseline_certification_path": baseline.get("certification_zip_path"),
            "baseline_certification_verification_report_path": baseline.get("certification_verification_report_path"),
            "current_timeline_path": current.get("timeline_zip_path"),
            "current_timeline_verification_report_path": current.get("timeline_verification_report_path"),
            "current_certification_path": current.get("certification_zip_path"),
            "current_certification_verification_report_path": current.get("certification_verification_report_path"),
        }
        return {**defaults, **{key: value for key, value in kwargs.items() if value is not None}}

    def _current_timeline_zip_path(self, release_id: str) -> Path | None:
        try:
            return self.timeline_store.zip_path(release_id)
        except Exception:
            return None

    def _current_timeline_verification_path(self, release_id: str) -> Path | None:
        try:
            return self.timeline_store.verification_report_path(release_id)
        except Exception:
            return None


def _default_policy(overrides: ImplementationDocument) -> ImplementationDocument:
    policy = {
        "max_new_critical_issues": 0,
        "max_new_high_issues": 0,
        "max_rating_drop": 0.5,
        "max_average_rating_drop": 0.25,
        "max_remediation_count_increase": 0,
        "require_same_track_count": True,
        "require_track_identity_match": True,
        "require_manual_reviews": True,
        "require_real_audio": True,
        "require_current_certification_binding": True,
        "require_baseline_certification_binding": True,
        "identity_mode": "release_track_lineage",
    }
    policy.update({key: value for key, value in overrides.items() if key in policy})
    return policy


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


def _readme(report: ImplementationDocument, matrix: ImplementationDocument, quality: ImplementationDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(
        [
            "MusicForge Release Audio Regression Guard",
            f"release_id: {report.get('release_id')}",
            f"baseline_release_id: {report.get('baseline_release_id')}",
            f"status: {report.get('status')}",
            f"readiness: {report.get('readiness')}",
            f"tracks: {summary.get('track_count')}",
            f"average_manual_rating_delta: {(quality.get('metrics') or {}).get('average_manual_rating_delta')}",
            f"failed_track_count: {(matrix.get('summary') or {}).get('failed_track_count')}",
            "",
            "This package contains regression summaries only. It does not embed audio files or local workspace paths.",
            "",
        ]
    )


def _file_record(path: Path, root: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _history_chain_ok(history: list[ImplementationDocument]) -> bool:
    previous: str | None = None
    for event in history:
        payload = _as_document(event.get("payload"))
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)
