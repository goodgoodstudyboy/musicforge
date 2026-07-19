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
_append_jsonl = _make_deferred_global('_append_jsonl')
_read_json_default = _make_deferred_global('_read_json_default')
_read_json_required = _make_deferred_global('_read_json_required')
_read_text = _make_deferred_global('_read_text')
_sanitize = _make_deferred_global('_sanitize')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsControlSignoffNotFoundError, TrustOperationsControlSignoffStateError, _append_jsonl, _read_json_default, _read_json_required, _read_text, _sanitize
    TrustOperationsControlSignoffNotFoundError = namespace.get('TrustOperationsControlSignoffNotFoundError', TrustOperationsControlSignoffNotFoundError)
    TrustOperationsControlSignoffStateError = namespace.get('TrustOperationsControlSignoffStateError', TrustOperationsControlSignoffStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_json_required = namespace.get('_read_json_required', _read_json_required)
    _read_text = namespace.get('_read_text', _read_text)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _bind_deferred_defaults(namespace)






class TrustOperationsControlSignoffStoreEvidenceMixin:
    def _control_result(self, hub_id: str, assessment_id: str, control_id: str) -> DomainDocument:
        results_doc = _read_json_required(self.control_store.control_results_path(hub_id, assessment_id), "Control results are missing.")
        for item in results_doc.get("results", []) if isinstance(results_doc.get("results"), list) else []:
            if isinstance(item, dict) and item.get("control_id") == control_id:
                return item
        raise TrustOperationsControlSignoffNotFoundError(f"Control result not found: {control_id}")

    def _read_exception(self, hub_id: str, exception_id: str) -> DomainDocument:
        exception = _read_json_default(self.exception_path(hub_id, exception_id), default={})
        if not exception:
            raise TrustOperationsControlSignoffNotFoundError(f"Control exception not found: {exception_id}")
        return exception

    def _read_change_request(self, hub_id: str, change_request_id: str) -> DomainDocument:
        request = _read_json_default(self.change_request_path(hub_id, change_request_id), default={})
        if not request:
            raise TrustOperationsControlSignoffNotFoundError(f"Control change request not found: {change_request_id}")
        return request

    def _ensure_exception_integrity(self, exception: DomainDocument) -> None:
        if exception.get("integrity_hash") != control_signoff_hash(exception):
            raise TrustOperationsControlSignoffStateError("Control exception integrity failed.")

    def _ensure_change_request_integrity(self, request: DomainDocument) -> None:
        if request.get("integrity_hash") != control_signoff_hash(request):
            raise TrustOperationsControlSignoffStateError("Control change request integrity failed.")

    def _exception_expired(self, exception: DomainDocument, now: str) -> bool:
        expires_at = (_as_document(exception.get("risk"))).get("expires_at")
        return bool(expires_at and str(expires_at) < str(now))

    def _ensure_signoff_current(self, hub_id: str, signoff: DomainDocument, payload: DomainDocument) -> None:
        if signoff.get("integrity_hash") != control_signoff_hash(signoff):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff integrity failed.")
        source = _as_document(signoff.get("source"))
        assessment_id = str(signoff.get("assessment_id") or source.get("assessment_id") or "")
        current_source, _control_report = self._signoff_source(hub_id, assessment_id, payload)
        if stable_hash(current_source) != signoff.get("source_hash"):
            raise TrustOperationsControlSignoffStateError("Trust Operations Control Signoff source is stale. Reset before archiving.")

    def _archive_report(self, hub_id: str, signoff: DomainDocument, now: str) -> DomainDocument:
        report: object = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE,
            "hub_id": hub_id,
            "created_at": now,
            "status": "passed",
            "signoff_hash": signoff.get("integrity_hash"),
            "source_hash": signoff.get("source_hash"),
            "summary": _as_document(signoff.get("summary")),
            "warnings": [],
        }
        report["integrity_hash"] = control_signoff_hash(report)
        return report

    def _source_summary(self, signoff: DomainDocument) -> DomainDocument:
        doc = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE,
            "hub_id": signoff.get("hub_id"),
            "source_hash": signoff.get("source_hash"),
            "source": _as_document(signoff.get("source")),
        }
        doc["integrity_hash"] = control_signoff_hash(doc)
        return doc

    def _exceptions_doc(self, hub_id: str, signoff: DomainDocument) -> DomainDocument:
        rows = self.list_exceptions(hub_id)
        doc = {"schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE, "hub_id": hub_id, "signoff_hash": signoff.get("integrity_hash"), "exceptions": rows, "summary": {"exception_count": len(rows), "approved_count": sum(1 for item in rows if item.get("status") == "approved")}}
        doc["integrity_hash"] = control_signoff_hash(doc)
        return doc

    def _change_requests_doc(self, hub_id: str, signoff: DomainDocument) -> DomainDocument:
        rows = self.list_change_requests(hub_id)
        doc = {"schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, "hub_id": hub_id, "signoff_hash": signoff.get("integrity_hash"), "change_requests": rows, "summary": {"change_request_count": len(rows), "applied_count": sum(1 for item in rows if item.get("status") == "applied")}}
        doc["integrity_hash"] = control_signoff_hash(doc)
        return doc

    def _history_events(self, hub_id: str) -> list[DomainDocument]:
        path = self.signoff_history_path(hub_id)
        if not path.exists():
            return []
        events: list[DomainDocument] = []
        for line in _read_text(path).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(_sanitize(item))
        return events

    def _signoff_state(self, hub_id: str) -> DomainDocument:
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

    def _append_history(self, hub_id: str, payload: DomainDocument) -> None:
        _append_jsonl(self.signoff_history_path(hub_id), payload)

    def _append_event(self, hub_id: str, event_type: str, payload: DomainDocument, *, now: str) -> None:
        _append_jsonl(self.events_path(hub_id), {"event_type": event_type, "created_at": now, **payload})
