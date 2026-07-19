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
_blocker = _make_deferred_global('_blocker')
_component_id_from_report = _make_deferred_global('_component_id_from_report')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_mkdir = _make_deferred_global('_mkdir')
_next_id = _make_deferred_global('_next_id')
_now = _make_deferred_global('_now')
_payload_paths = _make_deferred_global('_payload_paths')
_read_json_default = _make_deferred_global('_read_json_default')
_read_text = _make_deferred_global('_read_text')
_row_from_verification_report = _make_deferred_global('_row_from_verification_report')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_verifier_payload = _make_deferred_global('_verifier_payload')
_walk_files = _make_deferred_global('_walk_files')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
path = _make_deferred_global('path')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsFinalReadinessNotFoundError, TrustOperationsFinalReadinessStateError, _blocker, _component_id_from_report, _file_record, _fs_path, _mkdir
    global _next_id, _now, _payload_paths, _read_json_default, _read_text, _row_from_verification_report, _safe_id, _sanitize
    global _sha256, _verifier_payload, _walk_files, _write_json, _write_readme, _write_zip, _zip_entries, entry
    global item, path
    TrustOperationsFinalReadinessNotFoundError = namespace.get('TrustOperationsFinalReadinessNotFoundError', TrustOperationsFinalReadinessNotFoundError)
    TrustOperationsFinalReadinessStateError = namespace.get('TrustOperationsFinalReadinessStateError', TrustOperationsFinalReadinessStateError)
    _blocker = namespace.get('_blocker', _blocker)
    _component_id_from_report = namespace.get('_component_id_from_report', _component_id_from_report)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _next_id = namespace.get('_next_id', _next_id)
    _now = namespace.get('_now', _now)
    _payload_paths = namespace.get('_payload_paths', _payload_paths)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_text = namespace.get('_read_text', _read_text)
    _row_from_verification_report = namespace.get('_row_from_verification_report', _row_from_verification_report)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _verifier_payload = namespace.get('_verifier_payload', _verifier_payload)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    path = namespace.get('path', path)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_change_request"




class TrustOperationsFinalReadinessStoreReadinessMixin:
    def report_path(self) -> Path:
        return self.root / "final-readiness-report.json"

    def certificate_path(self) -> Path:
        return self.root / "final-readiness-certificate.json"

    def evidence_index_path(self) -> Path:
        return self.root / "final-evidence-index.json"

    def signoff_path(self) -> Path:
        return self.root / "final-handoff-signoff.json"

    def history_path(self) -> Path:
        return self.root / "final-handoff-history.jsonl"

    def change_requests_dir(self) -> Path:
        return self.root / "change-requests"

    def change_request_path(self, change_request_id: str) -> Path:
        return self.change_requests_dir() / (_safe_id(change_request_id) + ".json")

    def export_dir(self) -> Path:
        return self.root / "export"

    def handoff_zip_path(self) -> Path:
        return self.root / "trust-operations-final-handoff.zip"

    def verification_report_path(self) -> Path:
        return self.root / "trust-operations-final-handoff-verification-report.json"

    def read_report(self, *, default: DomainDocument | None = None) -> DomainDocument:
        value = _read_json_default(self.report_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final Readiness report not found.")
        return value

    def read_certificate(self, *, default: DomainDocument | None = None) -> DomainDocument:
        value = _read_json_default(self.certificate_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final Readiness certificate not found.")
        return value

    def read_evidence_index(self, *, default: DomainDocument | None = None) -> DomainDocument:
        value = _read_json_default(self.evidence_index_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final evidence index not found.")
        return value

    def read_signoff(self, *, default: DomainDocument | None = None) -> DomainDocument:
        value = _read_json_default(self.signoff_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final Handoff signoff not found.")
        return value

    def list_change_requests(self) -> list[DomainDocument]:
        root = self.change_requests_dir()
        if not root.exists():
            return []
        return [_sanitize(row) for row in (_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))) if row]

    def summary(self) -> DomainDocument:
        state = self._signoff_state()
        return {
            "status": state.get("status") or "unsigned",
            "report": self.read_report(default={}),
            "certificate": self.read_certificate(default={}),
            "evidence_index": self.read_evidence_index(default={}),
            "signoff": self.read_signoff(default={}),
            "change_requests": self.list_change_requests(),
            "verification": _read_json_default(self.verification_report_path(), default={}),
        }

    def refresh_report(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = _verifier_payload(payload or {})
            self._ensure_unsigned("refresh final readiness")
            evidence_index, summaries = self._build_evidence_index(payload, now)
            rows = evidence_index.get("items", []) if isinstance(evidence_index.get("items"), list) else []
            blockers = []
            warnings: list[object] = []
            for row in rows:
                if row.get("required") and row.get("status") != "passed":
                    blockers.append(_blocker(str(row.get("component_type") or "evidence"), f"Required evidence is not passed: {row.get('component_type')} {row.get('component_id')}"))
            summary = {
                "required_evidence_count": sum(1 for row in rows if row.get("required")),
                "passed_evidence_count": sum(1 for row in rows if row.get("status") == "passed"),
                "failed_evidence_count": sum(1 for row in rows if row.get("status") == "failed"),
                "missing_evidence_count": sum(1 for row in rows if row.get("status") == "missing"),
                "stale_evidence_count": sum(1 for row in rows if row.get("status") == "stale"),
                "manual_required_count": 0,
                "ready_for_signoff": not blockers,
            }
            source = self._report_source(rows)
            report = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE,
                "report_id": _safe_id(str(payload.get("report_id") or _next_id(self.root, "tofr"))),
                "generated_at": now,
                "status": "ready" if not blockers else "blocked",
                "source": source,
                "summary": summary,
                "rows": rows,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = final_readiness_hash(report)
            _write_json(self.evidence_index_path(), evidence_index)
            _write_json(self.report_path(), report)
            _write_json(self.root / "verification-summaries.json", {"summaries": summaries, "integrity_hash": stable_hash({"summaries": summaries})})
            self._append_history("final_readiness_refreshed", {"report_hash": report["integrity_hash"], "evidence_index_hash": evidence_index["integrity_hash"], "status": report["status"]}, now=now)
            return {"report": _sanitize(report), "evidence_index": _sanitize(evidence_index), "verification_summaries": _sanitize(summaries)}

    def create_certificate(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned("create final readiness certificate")
            report = self.read_report()
            index = self.read_evidence_index()
            self._ensure_report_ready(report, index)
            certificate = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE,
                "certificate_id": _safe_id(str(payload.get("certificate_id") or _next_id(self.root, "tofc"))),
                "created_at": now,
                "status": "ready",
                "readiness_level": "final_ready",
                "source": {
                    "report_hash": report.get("integrity_hash"),
                    "evidence_index_hash": index.get("integrity_hash"),
                    "hub_verification_report_hash": report.get("source", {}).get("hub_verification_report_hash") if isinstance(report.get("source"), dict) else None,
                    "assurance_watch_signoff_verification_report_hash": report.get("source", {}).get("assurance_watch_signoff_verification_report_hash") if isinstance(report.get("source"), dict) else None,
                },
                "summary": {
                    "ready": True,
                    "required_evidence_count": report.get("summary", {}).get("required_evidence_count") if isinstance(report.get("summary"), dict) else None,
                    "passed_evidence_count": report.get("summary", {}).get("passed_evidence_count") if isinstance(report.get("summary"), dict) else None,
                    "blocking_findings": len(_as_list(report.get("blockers"))),
                },
                "public_summary": {
                    "statement": "Trust Operations evidence is final-ready for handoff.",
                    "generated_by": "MusicForge",
                    "version": __version__,
                },
            }
            certificate["integrity_hash"] = final_readiness_hash(certificate)
            _write_json(self.certificate_path(), certificate)
            self._append_history("final_certificate_created", {"certificate_hash": certificate["integrity_hash"], "report_hash": report.get("integrity_hash"), "evidence_index_hash": index.get("integrity_hash")}, now=now)
            return _sanitize(certificate)

    def sign(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned("sign final handoff")
            report = self.read_report()
            certificate = self.read_certificate()
            index = self.read_evidence_index()
            self._ensure_report_ready(report, index)
            self._ensure_certificate_current(certificate, report, index)
            if bool(payload.get("force")):
                raise TrustOperationsFinalReadinessStateError("Final Handoff force signoff is not supported.")
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsFinalReadinessStateError("Final Handoff signoff reason must be at least 8 characters.")
            signed_by = sanitize_sensitive_text(str(payload.get("signed_by") or "local-reviewer")[:120])
            role = sanitize_sensitive_text(str(payload.get("role") or "owner")[:80])
            signoff_id = _safe_id(str(payload.get("signoff_id") or _next_id(self.root, "tofsg")))
            source = self._signoff_source(report, certificate, index)
            decision = {"approved": True, "force": False, "exceptions": []}
            payload_hash = stable_hash({"signoff_id": signoff_id, "signed_by": signed_by, "role": role, "reason": reason, "source": source, "decision": decision})
            signoff = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE,
                "signoff_id": signoff_id,
                "status": "signed",
                "signed_at": now,
                "signed_by": signed_by,
                "role": role,
                "reason": reason,
                "source": source,
                "decision": decision,
                "payload_hash": payload_hash,
            }
            signoff["integrity_hash"] = final_readiness_hash(signoff)
            _write_json(self.signoff_path(), signoff)
            self._append_history(
                "final_handoff_signed",
                {
                    "signoff_id": signoff_id,
                    "signoff_hash": signoff["integrity_hash"],
                    "signed_by": signed_by,
                    "role": role,
                    "reason": reason,
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "certificate_hash": certificate.get("integrity_hash"),
                    "evidence_index_hash": index.get("integrity_hash"),
                },
                now=now,
            )
            return _sanitize(signoff)

    def create_change_request(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsFinalReadinessStateError("Final Handoff change request reason must be at least 8 characters.")
            state = self._signoff_state()
            cr_id = _safe_id(str(payload.get("change_request_id") or _next_id(self.change_requests_dir(), "tofcr")))
            cr = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUEST_PACKAGE_TYPE,
                "change_request_id": cr_id,
                "status": "draft",
                "created_at": now,
                "created_by": sanitize_sensitive_text(str(payload.get("created_by") or "local-operator")[:120]),
                "reason": reason,
                "source": {"target_signoff_hash": state.get("signoff_hash")},
                "approval": None,
                "applied": {"applied_at": None, "applied_reset_hash": None},
            }
            cr["integrity_hash"] = final_readiness_hash(cr)
            _write_json(self.change_request_path(cr_id), cr)
            self._append_history("change_request_created", {"change_request_id": cr_id, "change_request_hash": cr["integrity_hash"]}, now=now)
            return _sanitize(cr)

    def approve_change_request(self, change_request_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            cr = self._read_change_request(change_request_id)
            self._ensure_change_request_integrity(cr)
            if cr.get("status") != "draft":
                raise TrustOperationsFinalReadinessStateError("Only draft Final Handoff change requests can be approved.")
            cr["status"] = "approved"
            cr["approval"] = {
                "approved_at": now,
                "approved_by": sanitize_sensitive_text(str(payload.get("approved_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Final Handoff reset approved.")[:500]),
            }
            cr["integrity_hash"] = final_readiness_hash(cr)
            _write_json(self.change_request_path(change_request_id), cr)
            self._append_history("change_request_approved", {"change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]}, now=now)
            return _sanitize(cr)

    def reset_signoff(self, change_request_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            state = self._signoff_state()
            if state.get("status") != "signed":
                raise TrustOperationsFinalReadinessStateError("Final Handoff is not signed.")
            cr = self._read_change_request(change_request_id)
            self._ensure_change_request_integrity(cr)
            applied = _as_document(cr.get("applied"))
            if cr.get("status") != "approved" or applied.get("applied_at"):
                raise TrustOperationsFinalReadinessStateError("Approved unused Final Handoff change request is required.")
            source = _as_document(cr.get("source"))
            if source.get("target_signoff_hash") and source.get("target_signoff_hash") != state.get("signoff_hash"):
                raise TrustOperationsFinalReadinessStateError("Final Handoff change request does not target the current signoff.")
            applied["applied_at"] = now
            applied["applied_reset_hash"] = state.get("signoff_hash")
            cr["applied"] = applied
            cr["status"] = "applied"
            cr["integrity_hash"] = final_readiness_hash(cr)
            _write_json(self.change_request_path(change_request_id), cr)
            self._append_history("final_handoff_reset", {"signoff_hash": state.get("signoff_hash"), "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]}, now=now)
            if self.signoff_path().exists():
                os.remove(_fs_path(self.signoff_path()))
            return {"status": "reset", "change_request": _sanitize(cr)}

    def export_handoff(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            signoff = self.read_signoff(default={})
            if not signoff and self._signoff_state().get("status") == "signed":
                raise TrustOperationsFinalReadinessStateError("Final Handoff is signed but signoff file is missing. Reset with an approved Change Request before export.")
            if not signoff:
                raise TrustOperationsFinalReadinessNotFoundError("Final Handoff signoff not found.")
            self._ensure_signoff_current(signoff)
            self._ensure_not_exported(str(signoff.get("integrity_hash") or ""))
            export_dir = self.export_dir()
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir / "verification-summaries")
            report = self.read_report()
            certificate = self.read_certificate()
            index = self.read_evidence_index()
            summaries = self._read_verification_summaries()
            _write_readme(export_dir)
            _write_json(export_dir / "final-readiness-report.json", report)
            _write_json(export_dir / "final-readiness-certificate.json", certificate)
            _write_json(export_dir / "final-evidence-index.json", index)
            _write_json(export_dir / "final-handoff-signoff.json", signoff)
            (export_dir / "final-handoff-history.jsonl").write_text(_read_text(self.history_path()), encoding="utf-8")
            change_requests_doc = self._change_requests_doc(signoff)
            _write_json(export_dir / "change-requests.json", change_requests_doc)
            for summary_path, summary in summaries.items():
                _write_json(export_dir / summary_path, summary)
            manifest = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Final Readiness", "version": __version__},
                "generated_at": now,
                "source": {
                    "report_hash": report.get("integrity_hash"),
                    "certificate_hash": certificate.get("integrity_hash"),
                    "evidence_index_hash": index.get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "change_requests_hash": change_requests_doc.get("integrity_hash"),
                    "history_hash": final_readiness_history_hash(self._history_events()),
                    "verification_summaries_hash": stable_hash({"summaries": summaries}),
                },
                "summary": {"status": signoff.get("status"), "ready": report.get("status") == "ready"},
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-final-readiness-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = final_readiness_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-final-readiness-manifest.json", manifest)
            self._append_history("final_handoff_exported", {"signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_handoff_zip(self, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            signoff = self.read_signoff(default={})
            if not signoff and self._signoff_state().get("status") == "signed":
                raise TrustOperationsFinalReadinessStateError("Final Handoff is signed but signoff file is missing. Reset with an approved Change Request before building ZIP.")
            if not signoff:
                raise TrustOperationsFinalReadinessNotFoundError("Final Handoff signoff not found.")
            self._ensure_not_zipped(str(signoff.get("integrity_hash") or ""))
            export_dir = self.export_dir()
            manifest_path = export_dir / "trust-operations-final-readiness-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsFinalReadinessStateError("Final Handoff export is missing.")
            if manifest.get("source", {}).get("signoff_hash") != signoff.get("integrity_hash"):
                raise TrustOperationsFinalReadinessStateError("Final Handoff export is stale.")
            zip_path = self.handoff_zip_path()
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = final_readiness_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "signoff_hash": signoff.get("integrity_hash")}
            self._append_history("final_handoff_zip_built", {"signoff_hash": signoff.get("integrity_hash"), "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]}, now=now)
            return _sanitize(info)

    def verify_handoff_zip(self, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_final_readiness_verifier import verify_trust_operations_final_handoff_package

        payload = payload or {}
        report = verify_trust_operations_final_handoff_package(self.handoff_zip_path(), strict=bool(payload.get("strict", False)), require_signed=bool(payload.get("require_signed", True)), require_current=bool(payload.get("require_current", True)), **_verifier_payload(payload))
        _write_json(self.verification_report_path(), report)
        return report

    def _build_evidence_index(self, payload: DomainDocument, now: str) -> tuple[DomainDocument, dict[str, DomainDocument]]:
        items: list[DomainDocument] = []
        summaries: dict[str, DomainDocument] = {}
        delivery_summary_rows: list[DomainDocument] = []
        for spec in FINAL_READINESS_SINGLE_SPECS:
            row, summary = self._single_evidence_row(spec, payload)
            items.append(row)
            summaries[str(spec["summary_path"])] = summary
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            for index, report_path in enumerate(_payload_paths(payload, str(spec["payload_keys"]), str(spec["payload_key"]))):
                report = _read_json_default(report_path, default={})
                component_id = _component_id_from_report(report, str(spec["component_id_prefix"]), index)
                row = _row_from_verification_report(str(spec["component_type"]), component_id, report, None, required=True)
                items.append(row)
                delivery_summary_rows.append(row)
        delivery_summary = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_final_delivery_verification_summary",
            "component_type": "delivery",
            "status": "passed" if delivery_summary_rows and all(row.get("status") == "passed" for row in delivery_summary_rows) else "failed",
            "items": delivery_summary_rows,
            "summary": {
                "item_count": len(delivery_summary_rows),
                "passed_count": sum(1 for row in delivery_summary_rows if row.get("status") == "passed"),
                "failed_count": sum(1 for row in delivery_summary_rows if row.get("status") == "failed"),
            },
        }
        delivery_summary["integrity_hash"] = final_readiness_hash(delivery_summary)
        summaries["verification-summaries/delivery-verification-summary.json"] = delivery_summary
        evidence_index = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE,
            "created_at": now,
            "items": items,
            "summary": {
                "item_count": len(items),
                "required_count": sum(1 for row in items if row.get("required")),
                "passed_count": sum(1 for row in items if row.get("status") == "passed"),
            },
        }
        evidence_index["integrity_hash"] = final_readiness_hash(evidence_index)
        return evidence_index, summaries
