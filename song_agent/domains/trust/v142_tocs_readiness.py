# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_controls import TrustOperationsControlStore as TrustOperationsControlStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_hub_incidents import TrustOperationsIncidentStore as TrustOperationsIncidentStore
from song_agent.domains.trust.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore as TrustOperationsIncidentKnowledgeStore
from song_agent.domains.trust.trust_operations_control_signoff_contracts import CONTROL_SIGNOFF_ARCHIVE_ENTRIES as CONTROL_SIGNOFF_ARCHIVE_ENTRIES, TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS as TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS, TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_CONTROL_SIGNOFF_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION as TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION, TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE, control_signoff_hash as control_signoff_hash, control_signoff_manifest_hash as control_signoff_manifest_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

TrustOperationsControlSignoffNotFoundError = _make_deferred_global('TrustOperationsControlSignoffNotFoundError')
TrustOperationsControlSignoffStateError = _make_deferred_global('TrustOperationsControlSignoffStateError')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_history_hash = _make_deferred_global('_history_hash')
_mkdir = _make_deferred_global('_mkdir')
_next_id = _make_deferred_global('_next_id')
_now = _make_deferred_global('_now')
_read_json_default = _make_deferred_global('_read_json_default')
_read_json_required = _make_deferred_global('_read_json_required')
_read_text = _make_deferred_global('_read_text')
_read_zip_json = _make_deferred_global('_read_zip_json')
_required = _make_deferred_global('_required')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_walk_files = _make_deferred_global('_walk_files')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsControlSignoffNotFoundError, TrustOperationsControlSignoffStateError, _file_record, _fs_path, _history_hash, _mkdir, _next_id
    global _now, _read_json_default, _read_json_required, _read_text, _read_zip_json, _required, _safe_id, _sanitize
    global _sha256, _walk_files, _write_json, _write_readme, _write_zip, _zip_entries, entry, item
    global row
    TrustOperationsControlSignoffNotFoundError = namespace.get('TrustOperationsControlSignoffNotFoundError', TrustOperationsControlSignoffNotFoundError)
    TrustOperationsControlSignoffStateError = namespace.get('TrustOperationsControlSignoffStateError', TrustOperationsControlSignoffStateError)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _history_hash = namespace.get('_history_hash', _history_hash)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _next_id = namespace.get('_next_id', _next_id)
    _now = namespace.get('_now', _now)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_json_required = namespace.get('_read_json_required', _read_json_required)
    _read_text = namespace.get('_read_text', _read_text)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _required = namespace.get('_required', _required)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)






class TrustOperationsControlSignoffStoreReadinessMixin:
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

    def read_signoff(self, hub_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        value = _read_json_default(self.signoff_path(hub_id), default=default or {})
        if not value and default is None:
            raise TrustOperationsControlSignoffNotFoundError("Trust Operations Control Signoff not found.")
        return value

    def list_exceptions(self, hub_id: str, *, include_all: bool = True) -> list[DomainDocument]:
        root = self.exceptions_dir(hub_id)
        if not root.exists():
            return []
        rows = [_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))]
        rows = [row for row in rows if row]
        if not include_all:
            rows = [row for row in rows if row.get("status") == "approved"]
        return [_sanitize(row) for row in rows]

    def list_change_requests(self, hub_id: str) -> list[DomainDocument]:
        root = self.change_requests_dir(hub_id)
        if not root.exists():
            return []
        return [_sanitize(row) for row in (_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))) if row]

    def sign(self, hub_id: str, assessment_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def request_exception(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def approve_exception(self, hub_id: str, exception_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id, "approve an exception")
            exception = self._read_exception(hub_id, exception_id)
            self._ensure_exception_integrity(exception)
            if exception.get("status") != "draft":
                raise TrustOperationsControlSignoffStateError("Only draft Control exceptions can be approved.")
            risk = _as_document(exception.get("risk"))
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

    def reject_exception(self, hub_id: str, exception_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def create_change_request(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def approve_change_request(self, hub_id: str, change_request_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def reset_signoff(self, hub_id: str, change_request_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            state = self._signoff_state(hub_id)
            if state.get("status") != "signed":
                raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff is not signed.")
            cr = self._read_change_request(hub_id, change_request_id)
            self._ensure_change_request_integrity(cr)
            if cr.get("status") != "approved" or (_as_document(cr.get("applied"))).get("applied_at"):
                raise TrustOperationsControlSignoffStateError("Approved unused Control change request is required.")
            source = _as_document(cr.get("source"))
            if source.get("current_signoff_hash") and source.get("current_signoff_hash") != state.get("signoff_hash"):
                raise TrustOperationsControlSignoffStateError("Control change request does not target the current signoff.")
            applied = _as_document(cr.get("applied"))
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

    def export_archive(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def build_archive_zip(self, hub_id: str, *, now: str | None = None) -> DomainDocument:
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

    def verify_archive_zip(self, hub_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_control_signoff_verifier import verify_trust_operations_control_signoff_archive_package

        payload = payload or {}
        signoff = self.read_signoff(hub_id, default={})
        assessment_id = str(signoff.get("assessment_id") or (_as_document(signoff.get("source"))).get("assessment_id") or "")
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

    def summary(self, hub_id: str) -> DomainDocument:
        signoff = self.read_signoff(hub_id, default={})
        state = self._signoff_state(hub_id)
        return {"hub_id": hub_id, "status": state.get("status") or "unsigned", "signoff": signoff, "exceptions": self.list_exceptions(hub_id), "change_requests": self.list_change_requests(hub_id)}

    def _signoff_source(self, hub_id: str, assessment_id: str, payload: DomainDocument) -> tuple[DomainDocument]:
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

    def _assert_optional_external_source(self, payload: DomainDocument, kind: str, source: DomainDocument) -> None:
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

    def _ensure_source_signable(self, source: DomainDocument, control_report: DomainDocument, hub_id: str, now: str) -> None:
        if control_report.get("status") != "passed":
            raise TrustOperationsControlSignoffStateError("Trust Operations Control verification failed.")
        if source.get("control_zip_sha256") != control_report.get("zip_sha256") or source.get("control_zip_size_bytes") != control_report.get("zip_size_bytes") or source.get("control_manifest_hash") != control_report.get("manifest_hash"):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control verification report is stale.")
        summary = _as_document(control_report.get("summary"))
        if int(summary.get("required_failed_count") or 0) != 0:
            raise TrustOperationsControlSignoffStateError("Trust Operations Control policy has failed required controls.")
        for exception in self.list_exceptions(hub_id):
            if exception.get("status") == "approved" and self._exception_expired(exception, now):
                raise TrustOperationsControlSignoffStateError("Approved Control exception is expired.")

    def _signoff_summary(self, hub_id: str, control_report: DomainDocument, now: str) -> DomainDocument:
        summary = _as_document(control_report.get("summary"))
        approved = [item for item in self.list_exceptions(hub_id) if item.get("status") == "approved" and not self._exception_expired(item, now)]
        return {
            "control_count": int(summary.get("control_count") or 0),
            "required_failed_count": int(summary.get("required_failed_count") or 0),
            "exception_count": len(self.list_exceptions(hub_id)),
            "approved_exception_count": len(approved),
            "critical_exception_count": sum(1 for item in approved if (_as_document(item.get("risk"))).get("severity") == "critical"),
            "high_exception_count": sum(1 for item in approved if (_as_document(item.get("risk"))).get("severity") == "high"),
        }
