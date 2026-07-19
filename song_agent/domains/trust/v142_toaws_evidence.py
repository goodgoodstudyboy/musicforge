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
from song_agent.domains.trust.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore as TrustOperationsAssuranceWatchStore
from song_agent.domains.trust.trust_operations_continuous_assurance import TrustOperationsAssuranceStore as TrustOperationsAssuranceStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_assurance_watch_signoff_contracts import ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES as ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE, watch_signoff_hash as watch_signoff_hash, watch_signoff_history_event_hash as watch_signoff_history_event_hash, watch_signoff_history_event_payload_hash as watch_signoff_history_event_payload_hash, watch_signoff_manifest_hash as watch_signoff_manifest_hash

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

TrustOperationsAssuranceWatchSignoffNotFoundError = _make_deferred_global('TrustOperationsAssuranceWatchSignoffNotFoundError')
TrustOperationsAssuranceWatchSignoffStateError = _make_deferred_global('TrustOperationsAssuranceWatchSignoffStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_read_json_default = _make_deferred_global('_read_json_default')
_read_text = _make_deferred_global('_read_text')
_sanitize = _make_deferred_global('_sanitize')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsAssuranceWatchSignoffNotFoundError, TrustOperationsAssuranceWatchSignoffStateError, _append_jsonl, _read_json_default, _read_text, _sanitize
    TrustOperationsAssuranceWatchSignoffNotFoundError = namespace.get('TrustOperationsAssuranceWatchSignoffNotFoundError', TrustOperationsAssuranceWatchSignoffNotFoundError)
    TrustOperationsAssuranceWatchSignoffStateError = namespace.get('TrustOperationsAssuranceWatchSignoffStateError', TrustOperationsAssuranceWatchSignoffStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_text = namespace.get('_read_text', _read_text)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_change_request"




class TrustOperationsAssuranceWatchSignoffStoreEvidenceMixin:
    def _watch_queue_summary(self, queue_id: str, signoff: DomainDocument) -> DomainDocument:
        queue = self.watch_store.read_queue(queue_id)
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_assurance_watch_queue_summary",
            "queue_id": queue_id,
            "signoff_hash": signoff.get("integrity_hash"),
            "queue_hash": queue.get("integrity_hash"),
            "source_hash": queue.get("source_hash"),
            "status": queue.get("status"),
            "summary": _as_document(queue.get("summary")),
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _drift_action_pack_summary(self, queue_id: str, signoff: DomainDocument) -> DomainDocument:
        action_pack = _read_json_default(self.watch_store.action_pack_path(queue_id), default={})
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_assurance_watch_drift_action_pack_summary",
            "queue_id": queue_id,
            "signoff_hash": signoff.get("integrity_hash"),
            "action_pack_hash": action_pack.get("integrity_hash"),
            "status": action_pack.get("status"),
            "summary": _as_document(action_pack.get("summary")),
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _external_summary(self, signoff: DomainDocument) -> DomainDocument:
        source = _as_document(signoff.get("source"))
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_assurance_watch_signoff_external_verification_summary",
            "queue_id": signoff.get("queue_id"),
            "signoff_hash": signoff.get("integrity_hash"),
            "source": source,
            "items": [
                {"component_type": "assurance_watch", "zip_sha256": source.get("watch_zip_sha256"), "manifest_hash": source.get("watch_manifest_hash"), "verification_report_hash": source.get("watch_verification_report_hash"), "status": "passed"},
                {"component_type": "hub", "zip_sha256": source.get("hub_zip_sha256"), "manifest_hash": source.get("hub_manifest_hash"), "verification_report_hash": source.get("hub_verification_report_hash"), "status": "passed"},
                {"component_type": "continuous_assurance", "verification_report_hash": source.get("continuous_assurance_report_hash"), "status": "passed"},
            ],
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _change_requests_doc(self, queue_id: str, signoff: DomainDocument) -> DomainDocument:
        rows = self.list_change_requests(queue_id)
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE,
            "queue_id": queue_id,
            "signoff_hash": signoff.get("integrity_hash"),
            "change_requests": rows,
            "summary": {"change_request_count": len(rows), "applied_count": sum(1 for item in rows if item.get("status") == "applied")},
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _read_change_request(self, queue_id: str, change_request_id: str) -> DomainDocument:
        request = _read_json_default(self.change_request_path(queue_id, change_request_id), default={})
        if not request:
            raise TrustOperationsAssuranceWatchSignoffNotFoundError(f"Assurance Watch change request not found: {change_request_id}")
        return request

    def _ensure_change_request_integrity(self, request: DomainDocument) -> None:
        if request.get("integrity_hash") != watch_signoff_hash(request):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch change request integrity failed.")

    def _history_events(self, queue_id: str) -> list[DomainDocument]:
        path = self.history_path(queue_id)
        if not path.exists():
            return []
        rows: list[DomainDocument] = []
        for line in _read_text(path).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(_sanitize(item))
        return rows

    def _signoff_state(self, queue_id: str) -> DomainDocument:
        active_hash: str | None = None
        active_id: str | None = None
        for event in self._history_events(queue_id):
            event_type = event.get("event_type")
            signoff_hash = str(event.get("signoff_hash") or "")
            if event_type == "watch_signoff_created" and signoff_hash:
                active_hash = signoff_hash
                active_id = str(event.get("signoff_id") or "")
            elif event_type == "watch_signoff_reset" and signoff_hash and signoff_hash == active_hash:
                active_hash = None
                active_id = None
        return {"status": "signed" if active_hash else "unsigned", "signoff_hash": active_hash, "signoff_id": active_id}

    def _ensure_unsigned(self, queue_id: str, action: str) -> None:
        if self._signoff_state(queue_id).get("status") == "signed":
            raise TrustOperationsAssuranceWatchSignoffStateError(f"Assurance Watch signoff is signed. Reset with an approved Change Request before attempting to {action}.")

    def _history_has_event(self, queue_id: str, event_type: str, signoff_hash: str) -> bool:
        return any(item.get("event_type") == event_type and item.get("signoff_hash") == signoff_hash for item in self._history_events(queue_id))

    def _ensure_archive_not_exported(self, queue_id: str, signoff_hash: str) -> None:
        if self._history_has_event(queue_id, "watch_signoff_archive_exported", signoff_hash):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff archive was already exported for this signoff. Reset before rebuilding archive.")

    def _ensure_archive_not_zipped(self, queue_id: str, signoff_hash: str) -> None:
        if self._history_has_event(queue_id, "watch_signoff_archive_zip_built", signoff_hash):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff archive ZIP was already built for this signoff. Reset before rebuilding archive ZIP.")

    def _append_history(self, queue_id: str, payload: DomainDocument) -> None:
        events = self._history_events(queue_id)
        event = _sanitize(payload)
        event["previous_event_hash"] = events[-1].get("event_hash") if events else None
        event["payload_hash"] = watch_signoff_history_event_payload_hash(event)
        event["event_hash"] = watch_signoff_history_event_hash(event)
        _append_jsonl(self.history_path(queue_id), event)
