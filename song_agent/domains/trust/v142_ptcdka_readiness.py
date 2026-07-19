# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_distribution_kit import DISTRIBUTION_KIT_BLOCKED_KEYS as DISTRIBUTION_KIT_BLOCKED_KEYS, PublicTrustCenterDistributionKitStore as PublicTrustCenterDistributionKitStore, distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package, write_public_trust_center_distribution_kit_verification_report as write_public_trust_center_distribution_kit_verification_report
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import ACCEPTANCE_BLOCKED_KEYS as ACCEPTANCE_BLOCKED_KEYS, ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS as ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS as ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_PACKAGE_TYPE as ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE as ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE, accepted_evidence_hash as accepted_evidence_hash, accepted_evidence_manifest_hash as accepted_evidence_manifest_hash, verification_hash as verification_hash

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

MAX_RESPONSE_BYTES = _make_deferred_global('MAX_RESPONSE_BYTES')
PublicTrustCenterDistributionKitAcceptanceNotFoundError = _make_deferred_global('PublicTrustCenterDistributionKitAcceptanceNotFoundError')
PublicTrustCenterDistributionKitAcceptanceStateError = _make_deferred_global('PublicTrustCenterDistributionKitAcceptanceStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_binding_from_response = _make_deferred_global('_binding_from_response')
_ensure_within = _make_deferred_global('_ensure_within')
_evidence_documents = _make_deferred_global('_evidence_documents')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_is_file = _make_deferred_global('_is_file')
_next_change_request_id = _make_deferred_global('_next_change_request_id')
_next_response_id = _make_deferred_global('_next_response_id')
_payload_bytes = _make_deferred_global('_payload_bytes')
_public_response = _make_deferred_global('_public_response')
_read_json_default = _make_deferred_global('_read_json_default')
_read_zip_json = _make_deferred_global('_read_zip_json')
_reject_path_payload = _make_deferred_global('_reject_path_payload')
_require_response_binding = _make_deferred_global('_require_response_binding')
_response_binding_stale = _make_deferred_global('_response_binding_stale')
_response_binding_summary = _make_deferred_global('_response_binding_summary')
_response_payload_from_bytes = _make_deferred_global('_response_payload_from_bytes')
_response_state_status = _make_deferred_global('_response_state_status')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_write_json = _make_deferred_global('_write_json')
_write_text = _make_deferred_global('_write_text')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
redaction_summary = _make_deferred_global('redaction_summary')
response_payload_hash = _make_deferred_global('response_payload_hash')
response_record_hash = _make_deferred_global('response_record_hash')
response_summary = _make_deferred_global('response_summary')
response_template = _make_deferred_global('response_template')
verify_response_document = _make_deferred_global('verify_response_document')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_RESPONSE_BYTES, PublicTrustCenterDistributionKitAcceptanceNotFoundError, PublicTrustCenterDistributionKitAcceptanceStateError, _append_jsonl, _binding_from_response, _ensure_within, _evidence_documents, _file_record
    global _fs_path, _is_file, _next_change_request_id, _next_response_id, _payload_bytes, _public_response, _read_json_default
    global _read_zip_json, _reject_path_payload, _require_response_binding, _response_binding_stale, _response_binding_summary, _response_payload_from_bytes, _response_state_status, _safe_id
    global _sanitize, _sha256, _write_json, _write_text, _write_zip, _zip_entries, entry, redaction_summary
    global response_payload_hash, response_record_hash, response_summary, response_template, verify_response_document
    MAX_RESPONSE_BYTES = namespace.get('MAX_RESPONSE_BYTES', MAX_RESPONSE_BYTES)
    PublicTrustCenterDistributionKitAcceptanceNotFoundError = namespace.get('PublicTrustCenterDistributionKitAcceptanceNotFoundError', PublicTrustCenterDistributionKitAcceptanceNotFoundError)
    PublicTrustCenterDistributionKitAcceptanceStateError = namespace.get('PublicTrustCenterDistributionKitAcceptanceStateError', PublicTrustCenterDistributionKitAcceptanceStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _binding_from_response = namespace.get('_binding_from_response', _binding_from_response)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _evidence_documents = namespace.get('_evidence_documents', _evidence_documents)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _is_file = namespace.get('_is_file', _is_file)
    _next_change_request_id = namespace.get('_next_change_request_id', _next_change_request_id)
    _next_response_id = namespace.get('_next_response_id', _next_response_id)
    _payload_bytes = namespace.get('_payload_bytes', _payload_bytes)
    _public_response = namespace.get('_public_response', _public_response)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _reject_path_payload = namespace.get('_reject_path_payload', _reject_path_payload)
    _require_response_binding = namespace.get('_require_response_binding', _require_response_binding)
    _response_binding_stale = namespace.get('_response_binding_stale', _response_binding_stale)
    _response_binding_summary = namespace.get('_response_binding_summary', _response_binding_summary)
    _response_payload_from_bytes = namespace.get('_response_payload_from_bytes', _response_payload_from_bytes)
    _response_state_status = namespace.get('_response_state_status', _response_state_status)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _write_json = namespace.get('_write_json', _write_json)
    _write_text = namespace.get('_write_text', _write_text)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    redaction_summary = namespace.get('redaction_summary', redaction_summary)
    response_payload_hash = namespace.get('response_payload_hash', response_payload_hash)
    response_record_hash = namespace.get('response_record_hash', response_record_hash)
    response_summary = namespace.get('response_summary', response_summary)
    response_template = namespace.get('response_template', response_template)
    verify_response_document = namespace.get('verify_response_document', verify_response_document)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION = 1
ACCEPTANCE_RESPONSE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_response"
ACCEPTANCE_TEMPLATE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_template"
ACCEPTANCE_ALLOWED_RESULTS = {"accepted", "needs_changes", "rejected"}
RESPONSE_RECORD_HASH_EXCLUDE_KEYS = {"integrity_hash", "imported_at"}
RESPONSE_PAYLOAD_HASH_EXCLUDE_KEYS = {"response_hash", "payload_hash", "integrity_hash"}




class PublicTrustCenterDistributionKitAcceptanceStore:
    def __init__(self, *, distribution_kit_store: PublicTrustCenterDistributionKitStore) -> None:
        self.distribution_kit_store = distribution_kit_store
        self.lock = threading.RLock()

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.distribution_kit_store.root_dir(center_id) / "acceptance"

    def template_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "response-template.json"

    def responses_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "responses"

    def response_dir(self, center_id: str, response_id: str) -> Path:
        return self.responses_dir(center_id) / _safe_id(response_id)

    def response_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-state.json"

    def original_response_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "original-response.json"

    def response_verification_report_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-verification-report.json"

    def response_binding_summary_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-binding-summary.json"

    def change_request_dir(self, center_id: str) -> Path:
        return self.root_dir(center_id) / "change-request-drafts"

    def accepted_evidence_root(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "accepted-evidence"

    def evidence_dir(self, center_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_root(center_id) / _safe_id(evidence_id)

    def evidence_report_path(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "evidence-report.json"

    def evidence_export_dir(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "export"

    def evidence_zip_path(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "accepted-evidence.zip"

    def evidence_verification_report_path(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "accepted-evidence-verification-report.json"

    def read_response(self, center_id: str, response_id: str) -> DomainDocument:
        path = self.response_path(center_id, response_id)
        if not path.exists():
            raise PublicTrustCenterDistributionKitAcceptanceNotFoundError(f"Distribution Kit acceptance response not found: {response_id}")
        return _read_json_default(path, default={})

    def list_responses(self, center_id: str = "ptc-default") -> list[DomainDocument]:
        root = self.responses_dir(center_id)
        if not root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("*/response-state.json")):
            value = _read_json_default(path, default={})
            if value:
                rows.append(response_summary(value))
        return rows

    def read_evidence(self, center_id: str, evidence_id: str | None = None, *, default: DomainDocument | None = None) -> DomainDocument:
        if evidence_id:
            return _read_json_default(self.evidence_report_path(center_id, evidence_id), default=default)
        latest = self._latest_evidence_id(center_id)
        return _read_json_default(self.evidence_report_path(center_id, latest), default=default) if latest else dict(default or {})

    def create_response_template(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            del payload
            now = now or now_iso()
            binding = self._current_kit_binding(center_id, require_verified=True)
            template = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "template_type": ACCEPTANCE_TEMPLATE_TYPE,
                "center_id": center_id,
                "template_id": "ptcdka-template-" + stable_hash({"center_id": center_id, "kit_binding": binding})[:12],
                "created_at": now,
                "kit_binding": binding,
                "required_verification": {
                    "strict": True,
                    "deep": True,
                    "require_current": True,
                    "require_delivery_readiness": True,
                    "require_anchor_registry_current": True,
                    "require_anchor_published": True,
                    "require_anchor_not_revoked": True,
                    "require_anchor_transparency_current": True,
                    "require_anchor_checkpoint": True,
                },
                "response_template": response_template(center_id, binding),
            }
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.template_path(center_id), template)
            return _sanitize(template)

    def import_response(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            _reject_path_payload(payload)
            raw = _payload_bytes(payload, max_size=MAX_RESPONSE_BYTES)
            response_payload = _response_payload_from_bytes(raw)
            _require_response_binding(response_payload)
            external_id = str(response_payload.get("response_id") or "").strip()
            response_id = _safe_id(external_id) if external_id else _next_response_id(self.responses_dir(center_id))
            if not external_id:
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response_id is required.")
            binding = self._current_kit_binding(center_id, require_verified=True)
            payload_hash = response_payload_hash(response_payload)
            if response_payload.get("response_hash") and str(response_payload.get("response_hash")) != payload_hash:
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response_hash does not match payload.")
            verification = verify_response_document(response_payload, binding)
            stale = _response_binding_stale(response_payload, binding)
            status = _response_state_status(str(response_payload.get("result") or ""), stale, verification)
            record: object = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_RESPONSE_TYPE,
                "response_id": response_id,
                "external_response_id": external_id,
                "center_id": center_id,
                "imported_at": now,
                "reviewed_at": response_payload.get("reviewed_at"),
                "result": response_payload.get("result"),
                "status": status,
                "review_mode": response_payload.get("review_mode"),
                "source_hash": stable_hash(binding),
                "response_payload_hash": payload_hash,
                "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
                "kit_binding_status": "stale" if stale else "current",
                "verification_status": verification.get("status"),
                "accepted_evidence_id": None,
                "warnings": [],
                "kit_binding": _binding_from_response(response_payload),
                "response_payload": response_payload,
                "verification": verification,
                "redaction_summary": redaction_summary(response_payload),
            }
            record["integrity_hash"] = response_record_hash(record)
            response_dir = self.response_dir(center_id, response_id)
            response_dir.mkdir(parents=True, exist_ok=True)
            _write_json(self.original_response_path(center_id, response_id), response_payload)
            _write_json(self.response_verification_report_path(center_id, response_id), verification)
            _write_json(self.response_binding_summary_path(center_id, response_id), _response_binding_summary(record, binding))
            _write_json(self.response_path(center_id, response_id), record)
            _append_jsonl(response_dir / "events.jsonl", {"event_type": "response_imported", "created_at": now, "response_id": response_id, "status": status})
            if verification.get("status") == "failed":
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response verification failed.")
            return {"response": _sanitize(record), "verification": verification}

    def verify_response(self, center_id: str, response_id: str, *, now: str | None = None) -> DomainDocument:
        del now
        record = self.read_response(center_id, response_id)
        payload = _as_document(record.get("response_payload"))
        binding = self._current_kit_binding(center_id, require_verified=True)
        return verify_response_document(payload, binding)

    def response_is_stale(self, center_id: str, response: DomainDocument) -> bool:
        payload = _as_document(response.get("response_payload"))
        try:
            binding = self._current_kit_binding(center_id, require_verified=True)
        except Exception:
            return True
        return _response_binding_stale(payload, binding)

    def refresh_accepted_evidence(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            response_id = str(payload.get("response_id") or "").strip() or self._latest_accepted_response_id(center_id)
            if not response_id:
                raise PublicTrustCenterDistributionKitAcceptanceStateError("No accepted Distribution Kit response is available.")
            response = self.read_response(center_id, response_id)
            verification = self.verify_response(center_id, response_id, now=now)
            if response.get("result") != "accepted" or response.get("review_mode") != "external_manual" or verification.get("status") != "passed" or self.response_is_stale(center_id, response):
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Only current, external_manual, accepted responses with passed verification can create accepted evidence.")
            binding = self._current_kit_binding(center_id, require_verified=True)
            source = self._evidence_source(center_id, response, verification, binding)
            public_response = _public_response(response)
            evidence_id = "ptcdkae-" + stable_hash({"center_id": center_id, "source": source})[:12]
            evidence = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE,
                "evidence_id": evidence_id,
                "center_id": center_id,
                "response_id": response_id,
                "created_at": now,
                "updated_at": now,
                "status": "current",
                "result": "accepted",
                "review_mode": "external_manual",
                "reviewer_summary": public_response.get("reviewer", {}),
                "kit_binding": binding,
                "source": source,
                "source_hash": stable_hash(source),
                "public_response": public_response,
                "warnings": [],
            }
            evidence["integrity_hash"] = accepted_evidence_hash(evidence)
            evidence_dir = self.evidence_dir(center_id, evidence_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            _write_json(self.evidence_report_path(center_id, evidence_id), evidence)
            return _sanitize(evidence)

    def export_accepted_evidence(self, center_id: str, response_id: str | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            evidence = self.refresh_accepted_evidence(center_id, {"response_id": response_id} if response_id else {}, now=now)
            self._ensure_evidence_exportable(center_id, evidence)
            evidence_id = str(evidence.get("evidence_id") or "")
            export_dir = self.evidence_export_dir(center_id, evidence_id).resolve()
            root = self.evidence_dir(center_id, evidence_id).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            source = _as_document(evidence.get("source"))
            response_id = str(source.get("response_id") or evidence.get("response_id") or "")
            docs = _evidence_documents(
                evidence,
                response_verification_report=_read_json_default(self.response_verification_report_path(center_id, response_id), default={}),
                response_binding_summary=_read_json_default(self.response_binding_summary_path(center_id, response_id), default={}),
            )
            for name, doc in docs.items():
                if name.endswith(".json"):
                    _write_json(export_dir / name, doc)
                else:
                    _write_text(export_dir / name, str(doc))
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if _is_file(path) and path.name != "evidence-manifest.json"]
            manifest = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Distribution Kit Accepted Evidence", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": evidence.get("source_hash"),
                "evidence": {"evidence_id": evidence_id, "integrity_hash": evidence.get("integrity_hash"), "source_hash": evidence.get("source_hash")},
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "redaction_summary": redaction_summary(docs),
            }
            manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
            _write_json(export_dir / "evidence-manifest.json", manifest)
            return _sanitize(manifest)

    def build_accepted_evidence_zip(self, center_id: str, response_id: str | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            evidence = self.refresh_accepted_evidence(center_id, {"response_id": response_id} if response_id else {}, now=now)
            evidence_id = str(evidence.get("evidence_id") or "")
            export_dir = self.evidence_export_dir(center_id, evidence_id).resolve()
            root = self.evidence_dir(center_id, evidence_id).resolve()
            zip_path = self.evidence_zip_path(center_id, evidence_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "evidence-manifest.json").exists():
                self.export_accepted_evidence(center_id, response_id, now=now)
            manifest = read_json(export_dir / "evidence-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
            _write_json(export_dir / "evidence-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            return {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "evidence_id": evidence_id}

    def verify_accepted_evidence_zip(self, center_id: str, evidence_id: str | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report

        payload = payload or {}
        evidence_id = evidence_id or self._latest_evidence_id(center_id)
        if not evidence_id:
            raise PublicTrustCenterDistributionKitAcceptanceNotFoundError("Accepted evidence not found.")
        report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
            self.evidence_zip_path(center_id, evidence_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", False)),
            distribution_kit_path=self.distribution_kit_store.zip_path(center_id) if bool(payload.get("use_distribution_kit", True)) else None,
        )
        write_public_trust_center_distribution_kit_accepted_evidence_verification_report(report, self.evidence_verification_report_path(center_id, evidence_id))
        return report

    def create_change_request_draft(self, center_id: str, response_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            response = self.read_response(center_id, response_id)
            verification = self.verify_response(center_id, response_id, now=now)
            if response.get("result") not in {"needs_changes", "rejected"} or verification.get("status") == "failed" or self.response_is_stale(center_id, response):
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Only current verified needs_changes/rejected Distribution Kit responses can create draft follow-up.")
            existing = self._find_change_request(center_id, response_id)
            if existing:
                return existing
            cr_id = _next_change_request_id(self.change_request_dir(center_id))
            response_payload = _as_document(response.get("response_payload"))
            draft = {
                "draft_id": cr_id,
                "source": "distribution_kit_acceptance_response",
                "center_id": center_id,
                "response_id": response_id,
                "status": "draft",
                "result": response.get("result"),
                "reason": "External receiver requested Distribution Kit acceptance follow-up.",
                "findings": _as_list(response_payload.get("findings")),
                "created_at": now,
                "payload": sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BLOCKED_KEYS),
            }
            self.change_request_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_request_dir(center_id) / f"{cr_id}.json", draft)
            return _sanitize(draft)

    def list_change_requests(self, center_id: str = "ptc-default") -> list[DomainDocument]:
        root = self.change_request_dir(center_id)
        if not root.exists():
            return []
        return [_read_json_default(path, default={}) for path in sorted(root.glob("ptcdkcr-*.json"))]

    def summary(self, center_id: str = "ptc-default") -> DomainDocument:
        evidence = self.read_evidence(center_id, default={})
        return {
            "center_id": center_id,
            "response_count": len(self.list_responses(center_id)),
            "accepted_evidence_status": evidence.get("status") or "missing",
            "accepted_evidence_id": evidence.get("evidence_id"),
        }

    def _current_kit_binding(self, center_id: str, *, require_verified: bool) -> DomainDocument:
        zip_path = self.distribution_kit_store.zip_path(center_id)
        if not zip_path.exists() or not zip_path.is_file():
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit ZIP is missing.")
        report = self.distribution_kit_store.read_report(center_id, default={})
        manifest = _read_zip_json(zip_path, "distribution-kit-manifest.json")
        verification = _read_json_default(self.distribution_kit_store.verification_report_path(center_id), default={})
        if not verification or verification.get("zip_sha256") != _sha256(zip_path) or verification.get("manifest_hash") != manifest.get("integrity_hash"):
            verification = verify_public_trust_center_distribution_kit_package(zip_path, strict=True, deep=True, require_current=True, require_delivery_readiness=False)
            write_public_trust_center_distribution_kit_verification_report(verification, self.distribution_kit_store.verification_report_path(center_id))
        if require_verified and verification.get("status") != "passed":
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit verification must be passed before acceptance.")
        return _sanitize(
            {
                "distribution_kit_zip_sha256": _sha256(zip_path),
                "distribution_kit_zip_size_bytes": zip_path.stat().st_size,
                "distribution_kit_manifest_hash": manifest.get("integrity_hash"),
                "distribution_kit_report_hash": report.get("integrity_hash"),
                "distribution_kit_source_hash": report.get("source_hash"),
                "distribution_kit_verification_report_hash": verification_hash(verification),
                "distribution_kit_verification_status": verification.get("status"),
                "ptc_zip_sha256": (_as_document(report.get("source"))).get("ptc_zip_sha256"),
                "anchor_registry_zip_sha256": (_as_document(report.get("source"))).get("anchor_registry_zip_sha256"),
                "anchor_transparency_zip_sha256": (_as_document(report.get("source"))).get("anchor_transparency_zip_sha256"),
                "checkpoint_hash": (_as_document(report.get("source"))).get("checkpoint_hash"),
            }
        )

    def _evidence_source(self, center_id: str, response: DomainDocument, verification: DomainDocument, binding: DomainDocument) -> DomainDocument:
        response_id = str(response.get("response_id") or "")
        binding_summary = _read_json_default(self.response_binding_summary_path(center_id, response_id), default={})
        payload = _as_document(response.get("response_payload"))
        return _sanitize(
            {
                "center_id": center_id,
                "response_id": response_id,
                "response_payload_hash": response.get("response_payload_hash"),
                "raw_response_sha256": response.get("raw_response_sha256"),
                "response_integrity_hash": response.get("integrity_hash"),
                "response_verification_hash": verification_hash(verification),
                "response_verification_status": verification.get("status"),
                "response_public_summary_hash": stable_hash(_public_response(response)),
                "binding_summary_hash": stable_hash(binding_summary),
                "distribution_kit_verification_report_hash": binding.get("distribution_kit_verification_report_hash"),
                "distribution_kit_zip_sha256": binding.get("distribution_kit_zip_sha256"),
                "distribution_kit_manifest_hash": binding.get("distribution_kit_manifest_hash"),
                "distribution_kit_report_hash": binding.get("distribution_kit_report_hash"),
                "distribution_kit_source_hash": binding.get("distribution_kit_source_hash"),
                "external_response_id": response.get("external_response_id"),
                "reviewed_at": payload.get("reviewed_at"),
            }
        )

    def _ensure_evidence_exportable(self, center_id: str, evidence: DomainDocument) -> None:
        if not evidence or evidence.get("status") != "current" or evidence.get("result") != "accepted":
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Accepted evidence is not current accepted evidence.")
        source = _as_document(evidence.get("source"))
        response_id = str(source.get("response_id") or evidence.get("response_id") or "")
        response = self.read_response(center_id, response_id)
        verification = self.verify_response(center_id, response_id)
        binding = self._current_kit_binding(center_id, require_verified=True)
        current = self._evidence_source(center_id, response, verification, binding)
        if stable_hash(current) != str(evidence.get("source_hash") or ""):
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Accepted evidence is stale.")

    def _latest_accepted_response_id(self, center_id: str) -> str:
        for item in reversed(self.list_responses(center_id)):
            if item.get("result") == "accepted" and item.get("verification_status") == "passed" and item.get("kit_binding_status") == "current":
                return str(item.get("response_id") or "")
        return ""

    def _latest_evidence_id(self, center_id: str) -> str:
        root = self.accepted_evidence_root(center_id)
        if not root.exists():
            return ""
        candidates: list[tuple[float, str]] = []
        for path in root.glob("*/evidence-report.json"):
            try:
                candidates.append((path.stat().st_mtime, path.parent.name))
            except OSError:
                continue
        return sorted(candidates)[-1][1] if candidates else ""

    def _find_change_request(self, center_id: str, response_id: str) -> DomainDocument:
        for item in self.list_change_requests(center_id):
            if item.get("response_id") == response_id:
                return item
        return {}
