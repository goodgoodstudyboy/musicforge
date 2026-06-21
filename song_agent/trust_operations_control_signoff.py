from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.public_trust_center_publication_monitoring import verification_hash
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.trust_operations_controls import TrustOperationsControlStore
from song_agent.trust_operations_hub import TrustOperationsHubStore
from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore


TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION = 1
TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff"
TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE = "musicforge_trust_operations_control_exception"
TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_control_change_request"
TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_report"
TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_source_verification"
TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_manifest"
TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_exceptions"
TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_change_requests"
TRUST_OPERATIONS_CONTROL_SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}
TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}

CONTROL_SIGNOFF_ARCHIVE_ENTRIES = {
    "README.txt",
    "trust-operations-control-signoff-manifest.json",
    "control-signoff.json",
    "control-signoff-history.jsonl",
    "control-exceptions.json",
    "control-change-requests.json",
    "control-signoff-report.json",
    "source-verification-summary.json",
}


class TrustOperationsControlSignoffError(ValueError):
    pass


class TrustOperationsControlSignoffNotFoundError(TrustOperationsControlSignoffError):
    pass


class TrustOperationsControlSignoffStateError(TrustOperationsControlSignoffError):
    pass


class TrustOperationsControlSignoffStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations-control-signoffs",
        *,
        control_store: TrustOperationsControlStore | None = None,
        hub_store: TrustOperationsHubStore | None = None,
        incident_store: TrustOperationsIncidentStore | None = None,
        knowledge_store: TrustOperationsIncidentKnowledgeStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.incident_store = incident_store or TrustOperationsIncidentStore(hub_store=self.hub_store)
        self.knowledge_store = knowledge_store or TrustOperationsIncidentKnowledgeStore(hub_store=self.hub_store, incident_store=self.incident_store)
        self.control_store = control_store or TrustOperationsControlStore(hub_store=self.hub_store, incident_store=self.incident_store, knowledge_store=self.knowledge_store)
        self.lock = threading.RLock()

    def hub_dir(self, hub_id: str) -> Path:
        return self.root / _safe_id(hub_id)

    def signoff_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "signoff.json"

    def signoff_history_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "signoff-history.jsonl"

    def events_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "events.jsonl"

    def exceptions_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "exceptions"

    def exception_path(self, hub_id: str, exception_id: str) -> Path:
        return self.exceptions_dir(hub_id) / (_safe_id(exception_id) + ".json")

    def change_requests_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "change-requests"

    def change_request_path(self, hub_id: str, change_request_id: str) -> Path:
        return self.change_requests_dir(hub_id) / (_safe_id(change_request_id) + ".json")

    def archive_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "archive"

    def archive_zip_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-control-signoff-archive.zip"

    def verification_report_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "verification-report.json"

    def read_signoff(self, hub_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.signoff_path(hub_id), default=default or {})
        if not value and default is None:
            raise TrustOperationsControlSignoffNotFoundError("Trust Operations Control Signoff not found.")
        return value

    def list_exceptions(self, hub_id: str, *, include_all: bool = True) -> list[dict[str, Any]]:
        root = self.exceptions_dir(hub_id)
        if not root.exists():
            return []
        rows = [_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))]
        rows = [row for row in rows if row]
        if not include_all:
            rows = [row for row in rows if row.get("status") == "approved"]
        return [_sanitize(row) for row in rows]

    def list_change_requests(self, hub_id: str) -> list[dict[str, Any]]:
        root = self.change_requests_dir(hub_id)
        if not root.exists():
            return []
        return [_sanitize(row) for row in (_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))) if row]

    def sign(self, hub_id: str, assessment_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id, "sign controls")
            source, control_report = self._signoff_source(hub_id, assessment_id, payload)
            self._ensure_source_signable(source, control_report, hub_id, now)
            summary = self._signoff_summary(hub_id, control_report, now)
            signoff_id = _safe_id(str(payload.get("signoff_id") or _next_id(self.hub_dir(hub_id), "tocs")))
            signoff = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE,
                "hub_id": hub_id,
                "assessment_id": assessment_id,
                "signoff_id": signoff_id,
                "status": "signed",
                "signed_at": now,
                "signed_by": sanitize_sensitive_text(str(payload.get("signed_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Trust Operations controls accepted.")[:500]),
                "source": source,
                "source_hash": stable_hash(source),
                "summary": summary,
            }
            signoff["integrity_hash"] = control_signoff_hash(signoff)
            _write_json(self.signoff_path(hub_id), signoff)
            self._append_history(hub_id, {"event_type": "control_signoff_signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "signoff_id": signoff_id, "assessment_id": assessment_id})
            self._append_event(hub_id, "control_signoff_signed", {"signoff_hash": signoff["integrity_hash"], "assessment_id": assessment_id}, now=now)
            return _sanitize(signoff)

    def request_exception(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id, "create an exception")
            assessment_id = _required(payload, "assessment_id")
            control_id = _required(payload, "control_id")
            assessment = self.control_store.read_assessment(hub_id, assessment_id)
            result = self._control_result(hub_id, assessment_id, control_id)
            exception_id = _safe_id(str(payload.get("exception_id") or _next_id(self.exceptions_dir(hub_id), "tocs-exc")))
            source = {
                "assessment_id": assessment_id,
                "assessment_hash": assessment.get("integrity_hash"),
                "control_id": control_id,
                "control_result_hash": result.get("integrity_hash"),
                "control_verification_report_hash": verification_hash(_read_json_default(self.control_store.verification_report_path(hub_id, assessment_id), default={})),
            }
            exception = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE,
                "exception_id": exception_id,
                "hub_id": hub_id,
                "control_id": control_id,
                "status": "draft",
                "requested_at": now,
                "requested_by": sanitize_sensitive_text(str(payload.get("requested_by") or "local-operator")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Temporary control exception requested.")[:500]),
                "scope": {"assessment_id": assessment_id, "policy_id": assessment.get("policy_id")},
                "risk": {
                    "severity": result.get("severity") or "medium",
                    "required": bool(result.get("required")),
                    "expires_at": payload.get("expires_at"),
                    "mitigation": sanitize_sensitive_text(str(payload.get("mitigation") or "")[:500]),
                },
                "source": source,
                "approval": None,
            }
            exception["integrity_hash"] = control_signoff_hash(exception)
            _write_json(self.exception_path(hub_id, exception_id), exception)
            self._append_event(hub_id, "control_exception_requested", {"exception_id": exception_id, "control_id": control_id}, now=now)
            return _sanitize(exception)

    def approve_exception(self, hub_id: str, exception_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id, "approve an exception")
            exception = self._read_exception(hub_id, exception_id)
            self._ensure_exception_integrity(exception)
            if exception.get("status") != "draft":
                raise TrustOperationsControlSignoffStateError("Only draft Control exceptions can be approved.")
            risk = exception.get("risk") if isinstance(exception.get("risk"), dict) else {}
            severity = str(risk.get("severity") or "")
            if severity in {"critical", "high"} or bool(risk.get("required")):
                raise TrustOperationsControlSignoffStateError("Critical, high, or required controls cannot be approved as exceptions.")
            exception["status"] = "approved"
            approval = {
                "approved_at": now,
                "approved_by": sanitize_sensitive_text(str(payload.get("approved_by") or "local-reviewer")[:120]),
                "decision": "approved",
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Temporary exception approved.")[:500]),
            }
            approval["approval_hash"] = stable_hash(approval)
            exception["approval"] = approval
            exception["integrity_hash"] = control_signoff_hash(exception)
            _write_json(self.exception_path(hub_id, exception_id), exception)
            self._append_event(hub_id, "control_exception_approved", {"exception_id": exception_id}, now=now)
            return _sanitize(exception)

    def reject_exception(self, hub_id: str, exception_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id, "reject an exception")
            exception = self._read_exception(hub_id, exception_id)
            self._ensure_exception_integrity(exception)
            if exception.get("status") not in {"draft", "approved"}:
                raise TrustOperationsControlSignoffStateError("Only draft or approved Control exceptions can be rejected.")
            exception["status"] = "rejected"
            exception["approval"] = {
                "approved_at": now,
                "approved_by": sanitize_sensitive_text(str(payload.get("approved_by") or "local-reviewer")[:120]),
                "decision": "rejected",
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Control exception rejected.")[:500]),
            }
            exception["integrity_hash"] = control_signoff_hash(exception)
            _write_json(self.exception_path(hub_id, exception_id), exception)
            self._append_event(hub_id, "control_exception_rejected", {"exception_id": exception_id}, now=now)
            return _sanitize(exception)

    def create_change_request(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsControlSignoffStateError("Change request reason must be at least 8 characters.")
            state = self._signoff_state(hub_id)
            change_request_id = _safe_id(str(payload.get("change_request_id") or _next_id(self.change_requests_dir(hub_id), "tocs-cr")))
            cr = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE,
                "change_request_id": change_request_id,
                "hub_id": hub_id,
                "status": "draft",
                "created_at": now,
                "created_by": sanitize_sensitive_text(str(payload.get("created_by") or "local-operator")[:120]),
                "reason": reason,
                "source": {"current_signoff_hash": state.get("signoff_hash")},
                "approval": None,
                "applied": {"applied_at": None, "applied_signoff_reset_hash": None},
            }
            cr["integrity_hash"] = control_signoff_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            return _sanitize(cr)

    def approve_change_request(self, hub_id: str, change_request_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            cr = self._read_change_request(hub_id, change_request_id)
            self._ensure_change_request_integrity(cr)
            if cr.get("status") != "draft":
                raise TrustOperationsControlSignoffStateError("Only draft Control change requests can be approved.")
            cr["status"] = "approved"
            cr["approval"] = {
                "approved_at": now,
                "approved_by": sanitize_sensitive_text(str(payload.get("approved_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Control signoff reset approved.")[:500]),
            }
            cr["integrity_hash"] = control_signoff_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            return _sanitize(cr)

    def reset_signoff(self, hub_id: str, change_request_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            state = self._signoff_state(hub_id)
            if state.get("status") != "signed":
                raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff is not signed.")
            cr = self._read_change_request(hub_id, change_request_id)
            self._ensure_change_request_integrity(cr)
            if cr.get("status") != "approved" or (cr.get("applied") if isinstance(cr.get("applied"), dict) else {}).get("applied_at"):
                raise TrustOperationsControlSignoffStateError("Approved unused Control change request is required.")
            source = cr.get("source") if isinstance(cr.get("source"), dict) else {}
            if source.get("current_signoff_hash") and source.get("current_signoff_hash") != state.get("signoff_hash"):
                raise TrustOperationsControlSignoffStateError("Control change request does not target the current signoff.")
            applied = cr.get("applied") if isinstance(cr.get("applied"), dict) else {}
            applied["applied_at"] = now
            applied["applied_signoff_reset_hash"] = state.get("signoff_hash")
            cr["applied"] = applied
            cr["status"] = "applied"
            cr["integrity_hash"] = control_signoff_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            self._append_history(hub_id, {"event_type": "control_signoff_reset", "created_at": now, "signoff_hash": state.get("signoff_hash"), "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]})
            if self.signoff_path(hub_id).exists():
                os.remove(_fs_path(self.signoff_path(hub_id)))
            self._append_event(hub_id, "control_signoff_reset", {"change_request_id": change_request_id, "signoff_hash": state.get("signoff_hash")}, now=now)
            return {"status": "reset", "change_request": _sanitize(cr)}

    def export_archive(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            signoff = self.read_signoff(hub_id, default={})
            if not signoff and self._signoff_state(hub_id).get("status") == "signed":
                raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff is signed but signoff.json is missing. Reset with an approved Change Request before archiving.")
            if not signoff:
                raise TrustOperationsControlSignoffNotFoundError("Trust Operations Control Signoff not found.")
            self._ensure_signoff_current(hub_id, signoff, payload)
            self._ensure_archive_not_exported(hub_id, str(signoff.get("integrity_hash") or ""))
            export_dir = self.archive_dir(hub_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            report = self._archive_report(hub_id, signoff, now)
            source_summary = self._source_summary(signoff)
            exceptions_doc = self._exceptions_doc(hub_id, signoff)
            change_requests_doc = self._change_requests_doc(hub_id, signoff)
            history_text = _read_text(self.signoff_history_path(hub_id))
            _write_readme(export_dir)
            _write_json(export_dir / "control-signoff.json", signoff)
            (export_dir / "control-signoff-history.jsonl").write_text(history_text, encoding="utf-8")
            _write_json(export_dir / "control-exceptions.json", exceptions_doc)
            _write_json(export_dir / "control-change-requests.json", change_requests_doc)
            _write_json(export_dir / "control-signoff-report.json", report)
            _write_json(export_dir / "source-verification-summary.json", source_summary)
            manifest = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Control Signoff", "version": __version__},
                "hub_id": hub_id,
                "generated_at": now,
                "source": {
                    "signoff_hash": signoff.get("integrity_hash"),
                    "history_hash": _history_hash(self._history_events(hub_id)),
                    "exceptions_hash": exceptions_doc.get("integrity_hash"),
                    "change_requests_hash": change_requests_doc.get("integrity_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "source_verification_summary_hash": source_summary.get("integrity_hash"),
                },
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-control-signoff-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = control_signoff_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-control-signoff-manifest.json", manifest)
            self._append_history(hub_id, {"event_type": "control_signoff_archive_exported", "created_at": now, "signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]})
            self._append_event(hub_id, "control_signoff_archive_exported", {"signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_archive_zip(self, hub_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            signoff = self.read_signoff(hub_id, default={})
            if not signoff and self._signoff_state(hub_id).get("status") == "signed":
                raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff is signed but signoff.json is missing. Reset with an approved Change Request before rebuilding archive ZIP.")
            if not signoff:
                raise TrustOperationsControlSignoffNotFoundError("Trust Operations Control Signoff not found.")
            self._ensure_archive_not_zipped(hub_id, str(signoff.get("integrity_hash") or ""))
            export_dir = self.archive_dir(hub_id)
            manifest_path = export_dir / "trust-operations-control-signoff-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff archive export is missing.")
            if manifest.get("source", {}).get("signoff_hash") != signoff.get("integrity_hash"):
                raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff archive export is stale.")
            zip_path = self.archive_zip_path(hub_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = control_signoff_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "signoff_hash": signoff.get("integrity_hash")}
            self._append_history(hub_id, {"event_type": "control_signoff_archive_zip_built", "created_at": now, "signoff_hash": signoff.get("integrity_hash"), "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]})
            self._append_event(hub_id, "control_signoff_archive_zip_built", {"signoff_hash": signoff.get("integrity_hash"), "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]}, now=now)
            return _sanitize(info)

    def verify_archive_zip(self, hub_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.trust_operations_control_signoff_verifier import verify_trust_operations_control_signoff_archive_package

        payload = payload or {}
        signoff = self.read_signoff(hub_id, default={})
        assessment_id = str(signoff.get("assessment_id") or (signoff.get("source") if isinstance(signoff.get("source"), dict) else {}).get("assessment_id") or "")
        if assessment_id:
            payload = {
                **payload,
                "control_package_path": payload.get("control_package_path") or self.control_store.zip_path(hub_id, assessment_id),
                "control_verification_report_path": payload.get("control_verification_report_path") or self.control_store.verification_report_path(hub_id, assessment_id),
            }
        report = verify_trust_operations_control_signoff_archive_package(
            self.archive_zip_path(hub_id),
            strict=bool(payload.get("strict", False)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current=bool(payload.get("require_current", True)),
            control_package_path=payload.get("control_package_path"),
            control_verification_report_path=payload.get("control_verification_report_path"),
            hub_package_path=payload.get("hub_package_path"),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
            incident_board_package_path=payload.get("incident_board_package_path"),
            incident_board_verification_report_path=payload.get("incident_board_verification_report_path"),
            incident_knowledge_package_path=payload.get("incident_knowledge_package_path"),
            incident_knowledge_verification_report_path=payload.get("incident_knowledge_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id), report)
        return report

    def summary(self, hub_id: str) -> dict[str, Any]:
        signoff = self.read_signoff(hub_id, default={})
        state = self._signoff_state(hub_id)
        return {"hub_id": hub_id, "status": state.get("status") or "unsigned", "signoff": signoff, "exceptions": self.list_exceptions(hub_id), "change_requests": self.list_change_requests(hub_id)}

    def _signoff_source(self, hub_id: str, assessment_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        control_zip = Path(payload.get("control_package_path") or self.control_store.zip_path(hub_id, assessment_id))
        control_report_path = Path(payload.get("control_verification_report_path") or self.control_store.verification_report_path(hub_id, assessment_id))
        control_report = _read_json_required(control_report_path, "Trust Operations Control verification report is required before signoff.")
        control_manifest = _read_zip_json(control_zip, "trust-operations-controls-manifest.json")
        source = {
            "assessment_id": assessment_id,
            "control_zip_sha256": _sha256(control_zip),
            "control_zip_size_bytes": os.stat(_fs_path(control_zip)).st_size if control_zip.exists() else None,
            "control_manifest_hash": control_manifest.get("integrity_hash"),
            "control_verification_report_hash": verification_hash(control_report),
            "control_verification_status": control_report.get("status"),
            "control_assessment_hash": control_report.get("source_hash"),
            "hub_zip_sha256": control_report.get("hub_zip_sha256"),
            "hub_zip_size_bytes": control_report.get("hub_zip_size_bytes"),
            "hub_manifest_hash": control_report.get("hub_manifest_hash"),
            "hub_verification_report_hash": control_report.get("hub_verification_report_hash"),
            "incident_zip_sha256": control_report.get("incident_zip_sha256"),
            "incident_zip_size_bytes": control_report.get("incident_zip_size_bytes"),
            "incident_manifest_hash": control_report.get("incident_manifest_hash"),
            "incident_verification_report_hash": control_report.get("incident_verification_report_hash"),
            "knowledge_zip_sha256": control_report.get("knowledge_zip_sha256"),
            "knowledge_zip_size_bytes": control_report.get("knowledge_zip_size_bytes"),
            "knowledge_manifest_hash": control_report.get("knowledge_manifest_hash"),
            "knowledge_verification_report_hash": control_report.get("knowledge_verification_report_hash"),
        }
        self._assert_optional_external_source(payload, "hub", source)
        self._assert_optional_external_source(payload, "incident", source)
        self._assert_optional_external_source(payload, "knowledge", source)
        return source, control_report

    def _assert_optional_external_source(self, payload: dict[str, Any], kind: str, source: dict[str, Any]) -> None:
        report_key = {"hub": "hub_verification_report_path", "incident": "incident_board_verification_report_path", "knowledge": "incident_knowledge_verification_report_path"}[kind]
        zip_key = {"hub": "hub_package_path", "incident": "incident_board_package_path", "knowledge": "incident_knowledge_package_path"}[kind]
        report_path = payload.get(report_key)
        zip_path = payload.get(zip_key)
        if report_path:
            report = _read_json_required(Path(report_path), f"{kind} verification report is missing.")
            expected_hash = source.get(f"{kind}_verification_report_hash")
            if verification_hash(report) != expected_hash:
                raise TrustOperationsControlSignoffStateError(f"Control signoff source does not match current {kind} verification report.")
        if zip_path:
            path = Path(zip_path)
            if _sha256(path) != source.get(f"{kind}_zip_sha256"):
                raise TrustOperationsControlSignoffStateError(f"Control signoff source does not match current {kind} ZIP.")

    def _ensure_source_signable(self, source: dict[str, Any], control_report: dict[str, Any], hub_id: str, now: str) -> None:
        if control_report.get("status") != "passed":
            raise TrustOperationsControlSignoffStateError("Trust Operations Control verification failed.")
        if source.get("control_zip_sha256") != control_report.get("zip_sha256") or source.get("control_zip_size_bytes") != control_report.get("zip_size_bytes") or source.get("control_manifest_hash") != control_report.get("manifest_hash"):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control verification report is stale.")
        summary = control_report.get("summary") if isinstance(control_report.get("summary"), dict) else {}
        if int(summary.get("required_failed_count") or 0) != 0:
            raise TrustOperationsControlSignoffStateError("Trust Operations Control policy has failed required controls.")
        for exception in self.list_exceptions(hub_id):
            if exception.get("status") == "approved" and self._exception_expired(exception, now):
                raise TrustOperationsControlSignoffStateError("Approved Control exception is expired.")

    def _signoff_summary(self, hub_id: str, control_report: dict[str, Any], now: str) -> dict[str, Any]:
        summary = control_report.get("summary") if isinstance(control_report.get("summary"), dict) else {}
        approved = [item for item in self.list_exceptions(hub_id) if item.get("status") == "approved" and not self._exception_expired(item, now)]
        return {
            "control_count": int(summary.get("control_count") or 0),
            "required_failed_count": int(summary.get("required_failed_count") or 0),
            "exception_count": len(self.list_exceptions(hub_id)),
            "approved_exception_count": len(approved),
            "critical_exception_count": sum(1 for item in approved if (item.get("risk") if isinstance(item.get("risk"), dict) else {}).get("severity") == "critical"),
            "high_exception_count": sum(1 for item in approved if (item.get("risk") if isinstance(item.get("risk"), dict) else {}).get("severity") == "high"),
        }

    def _control_result(self, hub_id: str, assessment_id: str, control_id: str) -> dict[str, Any]:
        results_doc = _read_json_required(self.control_store.control_results_path(hub_id, assessment_id), "Control results are missing.")
        for item in results_doc.get("results", []) if isinstance(results_doc.get("results"), list) else []:
            if isinstance(item, dict) and item.get("control_id") == control_id:
                return item
        raise TrustOperationsControlSignoffNotFoundError(f"Control result not found: {control_id}")

    def _read_exception(self, hub_id: str, exception_id: str) -> dict[str, Any]:
        exception = _read_json_default(self.exception_path(hub_id, exception_id), default={})
        if not exception:
            raise TrustOperationsControlSignoffNotFoundError(f"Control exception not found: {exception_id}")
        return exception

    def _read_change_request(self, hub_id: str, change_request_id: str) -> dict[str, Any]:
        request = _read_json_default(self.change_request_path(hub_id, change_request_id), default={})
        if not request:
            raise TrustOperationsControlSignoffNotFoundError(f"Control change request not found: {change_request_id}")
        return request

    def _ensure_exception_integrity(self, exception: dict[str, Any]) -> None:
        if exception.get("integrity_hash") != control_signoff_hash(exception):
            raise TrustOperationsControlSignoffStateError("Control exception integrity failed.")

    def _ensure_change_request_integrity(self, request: dict[str, Any]) -> None:
        if request.get("integrity_hash") != control_signoff_hash(request):
            raise TrustOperationsControlSignoffStateError("Control change request integrity failed.")

    def _exception_expired(self, exception: dict[str, Any], now: str) -> bool:
        expires_at = (exception.get("risk") if isinstance(exception.get("risk"), dict) else {}).get("expires_at")
        return bool(expires_at and str(expires_at) < str(now))

    def _ensure_signoff_current(self, hub_id: str, signoff: dict[str, Any], payload: dict[str, Any]) -> None:
        if signoff.get("integrity_hash") != control_signoff_hash(signoff):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff integrity failed.")
        source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
        assessment_id = str(signoff.get("assessment_id") or source.get("assessment_id") or "")
        current_source, _control_report = self._signoff_source(hub_id, assessment_id, payload)
        if stable_hash(current_source) != signoff.get("source_hash"):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff source is stale. Reset before archiving.")

    def _archive_report(self, hub_id: str, signoff: dict[str, Any], now: str) -> dict[str, Any]:
        report = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE,
            "hub_id": hub_id,
            "created_at": now,
            "status": "passed",
            "signoff_hash": signoff.get("integrity_hash"),
            "source_hash": signoff.get("source_hash"),
            "summary": signoff.get("summary") if isinstance(signoff.get("summary"), dict) else {},
            "warnings": [],
        }
        report["integrity_hash"] = control_signoff_hash(report)
        return report

    def _source_summary(self, signoff: dict[str, Any]) -> dict[str, Any]:
        doc = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE,
            "hub_id": signoff.get("hub_id"),
            "source_hash": signoff.get("source_hash"),
            "source": signoff.get("source") if isinstance(signoff.get("source"), dict) else {},
        }
        doc["integrity_hash"] = control_signoff_hash(doc)
        return doc

    def _exceptions_doc(self, hub_id: str, signoff: dict[str, Any]) -> dict[str, Any]:
        rows = self.list_exceptions(hub_id)
        doc = {"schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE, "hub_id": hub_id, "signoff_hash": signoff.get("integrity_hash"), "exceptions": rows, "summary": {"exception_count": len(rows), "approved_count": sum(1 for item in rows if item.get("status") == "approved")}}
        doc["integrity_hash"] = control_signoff_hash(doc)
        return doc

    def _change_requests_doc(self, hub_id: str, signoff: dict[str, Any]) -> dict[str, Any]:
        rows = self.list_change_requests(hub_id)
        doc = {"schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, "hub_id": hub_id, "signoff_hash": signoff.get("integrity_hash"), "change_requests": rows, "summary": {"change_request_count": len(rows), "applied_count": sum(1 for item in rows if item.get("status") == "applied")}}
        doc["integrity_hash"] = control_signoff_hash(doc)
        return doc

    def _history_events(self, hub_id: str) -> list[dict[str, Any]]:
        path = self.signoff_history_path(hub_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in _read_text(path).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(_sanitize(item))
        return events

    def _signoff_state(self, hub_id: str) -> dict[str, Any]:
        active_hash: str | None = None
        active_id: str | None = None
        for event in self._history_events(hub_id):
            event_type = event.get("event_type")
            signoff_hash = str(event.get("signoff_hash") or "")
            if event_type == "control_signoff_signed" and signoff_hash:
                active_hash = signoff_hash
                active_id = str(event.get("signoff_id") or "")
            elif event_type == "control_signoff_reset" and signoff_hash and signoff_hash == active_hash:
                active_hash = None
                active_id = None
        return {"status": "signed" if active_hash else "unsigned", "signoff_hash": active_hash, "signoff_id": active_id}

    def _ensure_unsigned(self, hub_id: str, action: str) -> None:
        if self._signoff_state(hub_id).get("status") == "signed":
            raise TrustOperationsControlSignoffStateError(f"Trust Operations Control Signoff is signed. Reset with an approved Change Request before attempting to {action}.")

    def _history_has_event(self, hub_id: str, event_type: str, signoff_hash: str) -> bool:
        return any(item.get("event_type") == event_type and item.get("signoff_hash") == signoff_hash for item in self._history_events(hub_id))

    def _ensure_archive_not_exported(self, hub_id: str, signoff_hash: str) -> None:
        if self._history_has_event(hub_id, "control_signoff_archive_exported", signoff_hash):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff archive was already exported for this signoff. Reset before rebuilding archive.")

    def _ensure_archive_not_zipped(self, hub_id: str, signoff_hash: str) -> None:
        if self._history_has_event(hub_id, "control_signoff_archive_zip_built", signoff_hash):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff archive ZIP was already built for this signoff. Reset before rebuilding archive ZIP.")

    def _append_history(self, hub_id: str, payload: dict[str, Any]) -> None:
        _append_jsonl(self.signoff_history_path(hub_id), payload)

    def _append_event(self, hub_id: str, event_type: str, payload: dict[str, Any], *, now: str) -> None:
        _append_jsonl(self.events_path(hub_id), {"event_type": event_type, "created_at": now, **payload})


def control_signoff_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_CONTROL_SIGNOFF_HASH_EXCLUDE_KEYS})


def control_signoff_manifest_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def _history_hash(events: list[dict[str, Any]]) -> str:
    return stable_hash({"events": events})


def _read_json_required(path: Path, message: str) -> dict[str, Any]:
    if not path.exists():
        raise TrustOperationsControlSignoffStateError(message)
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TrustOperationsControlSignoffStateError(message) from exc


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustOperationsControlSignoffStateError(f"Required ZIP entry is missing or invalid: {entry}") from exc


def _required(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise TrustOperationsControlSignoffStateError(f"{key} is required.")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"


def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"


def _read_json_default(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    try:
        if not path or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    return write_json(path, _sanitize(payload))


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text("MusicForge Trust Operations Control Signoff Archive\n\nThis package contains signed local control governance evidence.\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS)


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
