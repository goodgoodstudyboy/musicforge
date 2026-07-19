# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS
from song_agent.domains.trust.trust_operations_final_readiness_contracts import FINAL_READINESS_EXPORT_ENTRIES as FINAL_READINESS_EXPORT_ENTRIES, FINAL_READINESS_SINGLE_SPECS as FINAL_READINESS_SINGLE_SPECS, TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS as TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS, TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION as TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION, final_readiness_hash as final_readiness_hash, final_readiness_history_event_hash as final_readiness_history_event_hash, final_readiness_history_event_payload_hash as final_readiness_history_event_payload_hash, final_readiness_history_hash as final_readiness_history_hash, final_readiness_manifest_hash as final_readiness_manifest_hash

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

TrustOperationsFinalReadinessNotFoundError = _make_deferred_global('TrustOperationsFinalReadinessNotFoundError')
TrustOperationsFinalReadinessStateError = _make_deferred_global('TrustOperationsFinalReadinessStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_next_id = _make_deferred_global('_next_id')
_path_or_none = _make_deferred_global('_path_or_none')
_read_json_default = _make_deferred_global('_read_json_default')
_read_text = _make_deferred_global('_read_text')
_read_zip_json = _make_deferred_global('_read_zip_json')
_row_from_verification_report = _make_deferred_global('_row_from_verification_report')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsFinalReadinessNotFoundError, TrustOperationsFinalReadinessStateError, _append_jsonl, _next_id, _path_or_none, _read_json_default, _read_text
    global _read_zip_json, _row_from_verification_report, _safe_id, _sanitize, key, value
    TrustOperationsFinalReadinessNotFoundError = namespace.get('TrustOperationsFinalReadinessNotFoundError', TrustOperationsFinalReadinessNotFoundError)
    TrustOperationsFinalReadinessStateError = namespace.get('TrustOperationsFinalReadinessStateError', TrustOperationsFinalReadinessStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _next_id = namespace.get('_next_id', _next_id)
    _path_or_none = namespace.get('_path_or_none', _path_or_none)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_text = namespace.get('_read_text', _read_text)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _row_from_verification_report = namespace.get('_row_from_verification_report', _row_from_verification_report)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_change_request"




class TrustOperationsFinalReadinessStoreEvidenceMixin:
    def _single_evidence_row(self, spec: dict[str, str], payload: DomainDocument) -> tuple[DomainDocument]:
        package_path = _path_or_none(payload.get(spec["payload_path"]))
        report_path = _path_or_none(payload.get(spec["payload_report"]))
        report = _read_json_default(report_path, default={}) if report_path else {}
        manifest = _read_zip_json(package_path, spec["manifest_entry"]) if package_path else {}
        row = _row_from_verification_report(
            spec["component_type"],
            spec["component_id"],
            report,
            package_path,
            required=True,
            manifest_hash=manifest.get("integrity_hash"),
            expected_verification_package_type=spec["verification_package_type"],
            require_package=True,
        )
        summary = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_final_verification_summary",
            "component_type": spec["component_type"],
            "component_id": spec["component_id"],
            "expected_package_type": spec["package_type"],
            "expected_verification_package_type": spec["verification_package_type"],
            "status": row.get("status"),
            "package_sha256": row.get("package_sha256"),
            "package_size_bytes": row.get("package_size_bytes"),
            "manifest_hash": row.get("manifest_hash"),
            "verification_package_type": report.get("package_type"),
            "verification_report_hash": row.get("verification_report_hash"),
            "verification_status": row.get("verification_status"),
            "source_hash": report.get("source_hash"),
            "component_summary": _as_document(report.get("summary")),
        }
        summary["integrity_hash"] = final_readiness_hash(summary)
        return row, summary

    def _report_source(self, rows: list[DomainDocument]) -> DomainDocument:
        source: DomainDocument = {}
        delivery_rows = []
        for row in rows:
            component_type = str(row.get("component_type") or "")
            if component_type in {str(spec["component_type"]) for spec in DELIVERY_VERIFICATION_COMPONENTS}:
                delivery_rows.append({"component_type": component_type, "component_id": row.get("component_id"), "verification_report_hash": row.get("verification_report_hash")})
                continue
            source[f"{component_type}_verification_report_hash"] = row.get("verification_report_hash")
            source[f"{component_type}_zip_sha256"] = row.get("package_sha256")
            source[f"{component_type}_manifest_hash"] = row.get("manifest_hash")
        source["delivery_verification_set_hash"] = stable_hash({"delivery": sorted(delivery_rows, key=lambda row: (str(row.get("component_type")), str(row.get("component_id"))))})
        return source

    def _signoff_source(self, report: DomainDocument, certificate: DomainDocument, index: DomainDocument) -> DomainDocument:
        source = _as_document(report.get("source"))
        return {
            "final_readiness_report_hash": report.get("integrity_hash"),
            "final_readiness_certificate_hash": certificate.get("integrity_hash"),
            "final_evidence_index_hash": index.get("integrity_hash"),
            "hub_verification_report_hash": source.get("hub_verification_report_hash"),
            "assurance_watch_signoff_verification_report_hash": source.get("assurance_watch_signoff_verification_report_hash"),
            "delivery_verification_set_hash": source.get("delivery_verification_set_hash"),
        }

    def _ensure_report_ready(self, report: DomainDocument, index: DomainDocument) -> None:
        if report.get("integrity_hash") != final_readiness_hash(report):
            raise TrustOperationsFinalReadinessStateError("Final Readiness report integrity failed.")
        if index.get("integrity_hash") != final_readiness_hash(index):
            raise TrustOperationsFinalReadinessStateError("Final evidence index integrity failed.")
        if report.get("status") != "ready" or report.get("summary", {}).get("ready_for_signoff") is not True:
            raise TrustOperationsFinalReadinessStateError("Final Readiness report is not ready.")
        if report.get("rows") != index.get("items"):
            raise TrustOperationsFinalReadinessStateError("Final Readiness report does not match evidence index.")

    def _ensure_certificate_current(self, certificate: DomainDocument, report: DomainDocument, index: DomainDocument) -> None:
        if certificate.get("integrity_hash") != final_readiness_hash(certificate):
            raise TrustOperationsFinalReadinessStateError("Final Readiness certificate integrity failed.")
        source = _as_document(certificate.get("source"))
        if source.get("report_hash") != report.get("integrity_hash") or source.get("evidence_index_hash") != index.get("integrity_hash"):
            raise TrustOperationsFinalReadinessStateError("Final Readiness certificate is stale.")

    def _ensure_signoff_current(self, signoff: DomainDocument) -> None:
        if signoff.get("integrity_hash") != final_readiness_hash(signoff):
            raise TrustOperationsFinalReadinessStateError("Final Handoff signoff integrity failed.")
        report = self.read_report()
        certificate = self.read_certificate()
        index = self.read_evidence_index()
        self._ensure_report_ready(report, index)
        self._ensure_certificate_current(certificate, report, index)
        if signoff.get("source") != self._signoff_source(report, certificate, index):
            raise TrustOperationsFinalReadinessStateError("Final Handoff signoff source is stale. Reset before export.")

    def _change_requests_doc(self, signoff: DomainDocument) -> DomainDocument:
        rows = self.list_change_requests()
        doc = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE,
            "signoff_hash": signoff.get("integrity_hash"),
            "change_requests": rows,
            "summary": {"change_request_count": len(rows), "applied_count": sum(1 for item in rows if item.get("status") == "applied")},
        }
        doc["integrity_hash"] = final_readiness_hash(doc)
        return doc

    def _read_verification_summaries(self) -> dict[str, DomainDocument]:
        doc = _read_json_default(self.root / "verification-summaries.json", default={})
        summaries = _as_document(doc.get("summaries"))
        return {str(key): value for key, value in summaries.items() if isinstance(value, dict)}

    def _read_change_request(self, change_request_id: str) -> DomainDocument:
        request = _read_json_default(self.change_request_path(change_request_id), default={})
        if not request:
            raise TrustOperationsFinalReadinessNotFoundError(f"Final Handoff change request not found: {change_request_id}")
        return request

    def _ensure_change_request_integrity(self, request: DomainDocument) -> None:
        if request.get("integrity_hash") != final_readiness_hash(request):
            raise TrustOperationsFinalReadinessStateError("Final Handoff change request integrity failed.")

    def _history_events(self) -> list[DomainDocument]:
        if not self.history_path().exists():
            return []
        rows: list[DomainDocument] = []
        for line in _read_text(self.history_path()).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(_sanitize(item))
        return rows

    def _signoff_state(self) -> DomainDocument:
        active_hash: str | None = None
        active_id: str | None = None
        for event in self._history_events():
            event_type = event.get("event_type")
            payload = _as_document(event.get("payload"))
            signoff_hash = str(payload.get("signoff_hash") or "")
            if event_type == "final_handoff_signed" and signoff_hash:
                active_hash = signoff_hash
                active_id = str(payload.get("signoff_id") or "")
            elif event_type == "final_handoff_reset" and signoff_hash and signoff_hash == active_hash:
                active_hash = None
                active_id = None
        return {"status": "signed" if active_hash else "unsigned", "signoff_hash": active_hash, "signoff_id": active_id}

    def _ensure_unsigned(self, action: str) -> None:
        if self._signoff_state().get("status") == "signed":
            raise TrustOperationsFinalReadinessStateError(f"Final Handoff is signed. Reset with an approved Change Request before attempting to {action}.")

    def _history_has_event(self, event_type: str, signoff_hash: str) -> bool:
        for event in self._history_events():
            payload = _as_document(event.get("payload"))
            if event.get("event_type") == event_type and payload.get("signoff_hash") == signoff_hash:
                return True
        return False

    def _ensure_not_exported(self, signoff_hash: str) -> None:
        if self._history_has_event("final_handoff_exported", signoff_hash):
            raise TrustOperationsFinalReadinessStateError("Final Handoff was already exported for this signoff. Reset before rebuilding export.")

    def _ensure_not_zipped(self, signoff_hash: str) -> None:
        if self._history_has_event("final_handoff_zip_built", signoff_hash):
            raise TrustOperationsFinalReadinessStateError("Final Handoff ZIP was already built for this signoff. Reset before rebuilding ZIP.")

    def _append_history(self, event_type: str, payload: DomainDocument, *, now: str) -> None:
        events = self._history_events()
        event = {
            "event_id": _safe_id(_next_id(self.root, "tofh")),
            "event_type": event_type,
            "created_at": now,
            "payload": _sanitize(payload),
            "previous_event_hash": events[-1].get("event_hash") if events else None,
        }
        event["payload_hash"] = final_readiness_history_event_payload_hash(event)
        event["event_hash"] = final_readiness_history_event_hash(event)
        _append_jsonl(self.history_path(), event)
