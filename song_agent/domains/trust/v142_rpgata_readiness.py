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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore as ReleasePortfolioGovernanceAttestationTransparencyStore
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency as verify_release_portfolio_governance_attestation_transparency, write_release_portfolio_governance_attestation_transparency_verification_report as write_release_portfolio_governance_attestation_transparency_verification_report
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_contracts import ACK_BLOCKED_KEYS as ACK_BLOCKED_KEYS, ACK_EVIDENCE_HASH_EXCLUDE_KEYS as ACK_EVIDENCE_HASH_EXCLUDE_KEYS, ACK_EVIDENCE_PACKAGE_TYPE as ACK_EVIDENCE_PACKAGE_TYPE, ACK_MANIFEST_HASH_EXCLUDE_KEYS as ACK_MANIFEST_HASH_EXCLUDE_KEYS, ACK_PACK_HASH_EXCLUDE_KEYS as ACK_PACK_HASH_EXCLUDE_KEYS, ACK_PACK_PACKAGE_TYPE as ACK_PACK_PACKAGE_TYPE, ACK_RESPONSE_PACKAGE_TYPE as ACK_RESPONSE_PACKAGE_TYPE, ACK_SCHEMA_VERSION as ACK_SCHEMA_VERSION, ack_evidence_hash as ack_evidence_hash, ack_manifest_hash as ack_manifest_hash, ack_pack_hash as ack_pack_hash, acknowledgement_summary as acknowledgement_summary, response_template as response_template

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

ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError = _make_deferred_global('ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError')
ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError = _make_deferred_global('ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError')
_ensure_within = _make_deferred_global('_ensure_within')
_evidence_data_documents = _make_deferred_global('_evidence_data_documents')
_evidence_id = _make_deferred_global('_evidence_id')
_evidence_public_summary = _make_deferred_global('_evidence_public_summary')
_evidence_readme = _make_deferred_global('_evidence_readme')
_file_record = _make_deferred_global('_file_record')
_next_id = _make_deferred_global('_next_id')
_pack_data_documents = _make_deferred_global('_pack_data_documents')
_pack_id = _make_deferred_global('_pack_id')
_pack_readme = _make_deferred_global('_pack_readme')
_payload_bytes = _make_deferred_global('_payload_bytes')
_read_json_default = _make_deferred_global('_read_json_default')
_require_response_source_binding = _make_deferred_global('_require_response_source_binding')
_response_payload_from_bytes = _make_deferred_global('_response_payload_from_bytes')
_response_schema = _make_deferred_global('_response_schema')
_response_stale = _make_deferred_global('_response_stale')
_safe_id = _make_deferred_global('_safe_id')
_safe_profile = _make_deferred_global('_safe_profile')
_sha256 = _make_deferred_global('_sha256')
_state_tuple = _make_deferred_global('_state_tuple')
_write_json = _make_deferred_global('_write_json')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
redaction_summary = _make_deferred_global('redaction_summary')
response_payload_hash = _make_deferred_global('response_payload_hash')
response_record_hash = _make_deferred_global('response_record_hash')
response_summary = _make_deferred_global('response_summary')
verification_hash = _make_deferred_global('verification_hash')
verify_response_document = _make_deferred_global('verify_response_document')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError, ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, _ensure_within, _evidence_data_documents, _evidence_id, _evidence_public_summary, _evidence_readme, _file_record
    global _next_id, _pack_data_documents, _pack_id, _pack_readme, _payload_bytes, _read_json_default, _require_response_source_binding
    global _response_payload_from_bytes, _response_schema, _response_stale, _safe_id, _safe_profile, _sha256, _state_tuple, _write_json
    global _write_zip, _zip_entries, entry, item, key, redaction_summary, response_payload_hash, response_record_hash
    global response_summary, verification_hash, verify_response_document
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError = namespace.get('ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError', ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError)
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError = namespace.get('ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError', ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _evidence_data_documents = namespace.get('_evidence_data_documents', _evidence_data_documents)
    _evidence_id = namespace.get('_evidence_id', _evidence_id)
    _evidence_public_summary = namespace.get('_evidence_public_summary', _evidence_public_summary)
    _evidence_readme = namespace.get('_evidence_readme', _evidence_readme)
    _file_record = namespace.get('_file_record', _file_record)
    _next_id = namespace.get('_next_id', _next_id)
    _pack_data_documents = namespace.get('_pack_data_documents', _pack_data_documents)
    _pack_id = namespace.get('_pack_id', _pack_id)
    _pack_readme = namespace.get('_pack_readme', _pack_readme)
    _payload_bytes = namespace.get('_payload_bytes', _payload_bytes)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _require_response_source_binding = namespace.get('_require_response_source_binding', _require_response_source_binding)
    _response_payload_from_bytes = namespace.get('_response_payload_from_bytes', _response_payload_from_bytes)
    _response_schema = namespace.get('_response_schema', _response_schema)
    _response_stale = namespace.get('_response_stale', _response_stale)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _safe_profile = namespace.get('_safe_profile', _safe_profile)
    _sha256 = namespace.get('_sha256', _sha256)
    _state_tuple = namespace.get('_state_tuple', _state_tuple)
    _write_json = namespace.get('_write_json', _write_json)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    redaction_summary = namespace.get('redaction_summary', redaction_summary)
    response_payload_hash = namespace.get('response_payload_hash', response_payload_hash)
    response_record_hash = namespace.get('response_record_hash', response_record_hash)
    response_summary = namespace.get('response_summary', response_summary)
    verification_hash = namespace.get('verification_hash', verification_hash)
    verify_response_document = namespace.get('verify_response_document', verify_response_document)
    _bind_deferred_defaults(namespace)


ACK_RESPONSE_HASH_FIELDS = (
    "response_id",
    "review_pack_id",
    "review_pack_source_hash",
    "portfolio_id",
    "profile",
    "transparency_zip_sha256",
    "transparency_manifest_hash",
    "transparency_feed_source_hash",
    "reviewer",
    "review_status",
    "reviewed_notice_ids",
    "reviewed_event_ids",
    "comments",
    "concerns",
    "submitted_at",
)
ACK_ALLOWED_RESPONSE_STATUSES = {"accepted", "needs_changes", "rejected"}




class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStoreReadinessMixin:
    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.transparency_store.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-transparency-ack"
        if str(profile or "public_summary") == "public_summary":
            return root
        return root / "profiles" / _safe_profile(profile)

    def pack_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack.json"

    def pack_history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "acknowledgement-pack-history.jsonl"

    def pack_export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack-export"

    def pack_zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack.zip"

    def pack_verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack-verification-report.json"

    def responses_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "responses"

    def response_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}.json"

    def response_verification_report_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}-verification-report.json"

    def evidence_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence.json"

    def evidence_export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence-export"

    def evidence_zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence.zip"

    def evidence_verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence-verification-report.json"

    def change_requests_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "change-request-drafts"

    def read_pack(self, portfolio_id: str, *, profile: str = "public_summary", default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.pack_path(portfolio_id, profile), default=default)

    def read_response(self, portfolio_id: str, response_id: str, *, profile: str = "public_summary") -> DomainDocument:
        path = self.response_path(portfolio_id, response_id, profile)
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError(f"Acknowledgement response not found: {response_id}")
        return sanitize_metadata(read_json(path), blocked_keys=ACK_BLOCKED_KEYS)

    def list_responses(self, portfolio_id: str, *, profile: str = "public_summary") -> list[DomainDocument]:
        root = self.responses_dir(portfolio_id, profile)
        if not root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("att-trans-ack-response-*.json")):
            value = _read_json_default(path, default={})
            if value:
                rows.append(response_summary(value))
        return rows

    def read_evidence(self, portfolio_id: str, *, profile: str = "public_summary", default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.evidence_path(portfolio_id, profile), default=default)

    def refresh_pack(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            require_verified = bool((payload or {}).get("require_transparency_verified", True))
            source = self.build_pack_source(portfolio_id, profile=profile)
            blockers, warnings, checks = self._pack_findings(source, require_verified=require_verified)
            feed = self.transparency_store.read_feed(portfolio_id, profile=profile, default={})
            pack = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_PACK_PACKAGE_TYPE,
                "pack_id": _pack_id(portfolio_id, profile, source),
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "ready",
                "source": source,
                "source_hash": stable_hash(source),
                "summary": {
                    "event_count": len(feed.get("events", []) if isinstance(feed.get("events"), list) else []),
                    "notice_count": len(feed.get("notices", []) if isinstance(feed.get("notices"), list) else []),
                    "latest_notice_type": (_as_document(feed.get("summary"))).get("latest_notice_type"),
                    "requires_response": True,
                },
                "response_requirements": {
                    "allowed_status": sorted(ACK_ALLOWED_RESPONSE_STATUSES),
                    "required_fields": [
                        "review_pack_id",
                        "review_pack_source_hash",
                        "transparency_zip_sha256",
                        "transparency_manifest_hash",
                        "transparency_feed_source_hash",
                        "reviewer",
                        "review_status",
                        "reviewed_notice_ids",
                    ],
                },
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            pack["integrity_hash"] = ack_pack_hash(pack)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.pack_path(portfolio_id, profile), pack)
            self._append_history(portfolio_id, profile, "ack_pack_refreshed", {"pack_id": pack["pack_id"], "source_hash": pack["source_hash"], "status": pack["status"]}, now=now)
            return sanitize_metadata(pack, blocked_keys=ACK_BLOCKED_KEYS)

    def build_pack_source(self, portfolio_id: str, *, profile: str = "public_summary") -> DomainDocument:
        self.transparency_store.attestation_store.portfolio_store.get_portfolio(portfolio_id)
        zip_path = self.transparency_store.zip_path(portfolio_id, profile)
        verification = verify_release_portfolio_governance_attestation_transparency(
            zip_path,
            strict=True,
            require_current=True,
            require_accepted_evidence=False,
            require_contiguous_chain=True,
        )
        write_release_portfolio_governance_attestation_transparency_verification_report(verification, self.transparency_store.verification_report_path(portfolio_id, profile))
        feed = self.transparency_store.read_feed(portfolio_id, profile=profile, default={})
        manifest = _read_json_default(self.transparency_store.export_dir(portfolio_id, profile) / "transparency-manifest.json", default={})
        checks = {str(item.get("check_id")): item.get("status") for item in verification.get("checks", []) if isinstance(item, dict)}
        source = {
            "portfolio_id": portfolio_id,
            "profile": profile,
            "transparency_zip_sha256": _sha256(zip_path),
            "transparency_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() and zip_path.is_file() else None,
            "transparency_manifest_hash": manifest.get("integrity_hash") or verification.get("manifest_hash"),
            "transparency_feed_source_hash": feed.get("source_hash"),
            "transparency_feed_integrity_hash": feed.get("integrity_hash"),
            "transparency_verification_status": verification.get("status") or "missing",
            "transparency_verification_hash": verification_hash(verification),
            "transparency_event_semantics_status": checks.get("transparency_event_semantics_match"),
            "transparency_notice_semantics_status": checks.get("transparency_notice_semantics_match"),
            "current_public_state_hash": (_as_document(feed.get("source"))).get("public_state_hash"),
            "current_entry_id": (_as_document(feed.get("summary"))).get("current_entry_id"),
            "current_certificate_id": (_as_document(feed.get("summary"))).get("current_certificate_id"),
            "portal_manifest_hash": (_as_document(feed.get("source"))).get("portal_manifest_hash"),
            "accepted_evidence_manifest_hash": (_as_document(feed.get("source"))).get("accepted_evidence_manifest_hash"),
            "event_ids": [str(item.get("event_id")) for item in feed.get("events", []) if isinstance(item, dict) and item.get("event_id")],
            "notice_ids": [str(item.get("notice_id")) for item in feed.get("notices", []) if isinstance(item, dict) and item.get("notice_id")],
            "warning_notice_ids": [str(item.get("notice_id")) for item in feed.get("notices", []) if isinstance(item, dict) and item.get("notice_id") and item.get("severity") in {"warning", "critical"}],
        }
        return sanitize_metadata(source, blocked_keys=ACK_BLOCKED_KEYS)

    def pack_is_stale(self, portfolio_id: str, pack: DomainDocument | None = None, *, profile: str = "public_summary") -> bool:
        data = _document_or(pack, self.read_pack(portfolio_id, profile=profile, default={}))
        if not data:
            return False
        try:
            source = self.build_pack_source(portfolio_id, profile=str(data.get("profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_pack(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={}) or self.refresh_pack(portfolio_id, {"profile": profile}, now=now)
            if self.pack_is_stale(portfolio_id, pack, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack source is stale. Refresh the pack before export.")
            if pack.get("status") == "failed":
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack has blockers and cannot be exported.")
            state = _state_tuple(pack)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_pack_exported"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack export already exists for this source state.")
            export_dir = self.pack_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            (export_dir / "forms").mkdir(parents=True, exist_ok=True)
            data_docs = _pack_data_documents(pack, self.transparency_store.read_feed(portfolio_id, profile=profile, default={}))
            _write_json(export_dir / "transparency-acknowledgement-pack.json", pack)
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            template = response_template(pack)
            _write_json(export_dir / "forms" / "response-template.json", template)
            _write_json(export_dir / "forms" / "response-schema.json", _response_schema(pack))
            (export_dir / "README.txt").write_text(_pack_readme(pack), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "acknowledgement-pack-manifest.json"]
            manifest = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_PACK_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Transparency Acknowledgement Pack", "version": __version__},
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "source_hash": pack.get("source_hash"),
                "pack": {"pack_id": pack.get("pack_id"), "integrity_hash": pack.get("integrity_hash"), "source_hash": pack.get("source_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": redaction_summary({"pack": pack, "data": data_docs, "template": template}),
            }
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-pack-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "ack_pack_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ACK_BLOCKED_KEYS)

    def build_pack_zip(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={}) or self.refresh_pack(portfolio_id, {"profile": profile}, now=now)
            if self.pack_is_stale(portfolio_id, pack, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack source is stale. Refresh the pack before ZIP.")
            state = _state_tuple(pack)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_pack_zip_built"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack ZIP already exists for this source state.")
            export_dir = self.pack_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.pack_zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "acknowledgement-pack-manifest.json").exists():
                self.export_pack(portfolio_id, {"profile": profile}, now=now)
            manifest = read_json(export_dir / "acknowledgement-pack-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-pack-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "path": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            self._append_history(portfolio_id, profile, "ack_pack_zip_built", {**state, "zip_sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=ACK_BLOCKED_KEYS)

    def import_response(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            if any(payload.get(key) for key in ("source_path", "local_path", "file_path")):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response import only accepts uploaded content; source_path/local_path/file_path are not allowed.")
            raw = _payload_bytes(payload, max_size=1024 * 1024)
            response_payload = _response_payload_from_bytes(raw)
            pack = self.read_pack(portfolio_id, profile=profile, default={})
            if not pack:
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack is missing.")
            _require_response_source_binding(response_payload)
            imported_id = _next_id(self.responses_dir(portfolio_id, profile), "att-trans-ack-response")
            external_id = str(response_payload.get("response_id") or "").strip()
            response_hash_value = response_payload_hash(response_payload)
            if response_payload.get("response_hash") and response_payload.get("response_hash") != response_hash_value:
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response_hash does not match payload.")
            verification = verify_response_document(response_payload, pack, now=now)
            stale = _response_stale(response_payload, pack)
            record = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_RESPONSE_PACKAGE_TYPE,
                "response_id": imported_id,
                "external_response_id": external_id or imported_id,
                "portfolio_id": portfolio_id,
                "profile": profile,
                "imported_at": now,
                "status": response_payload.get("review_status"),
                "verification_status": verification.get("status"),
                "stale": stale,
                "source": {
                    "review_pack_id": response_payload.get("review_pack_id"),
                    "review_pack_source_hash": response_payload.get("review_pack_source_hash"),
                    "transparency_zip_sha256": response_payload.get("transparency_zip_sha256"),
                    "transparency_manifest_hash": response_payload.get("transparency_manifest_hash"),
                    "transparency_feed_source_hash": response_payload.get("transparency_feed_source_hash"),
                },
                "response_payload": response_payload,
                "payload_hash": response_hash_value,
                "verification": verification,
                "redaction_summary": redaction_summary(response_payload),
            }
            record["integrity_hash"] = response_record_hash(record)
            self.responses_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.response_path(portfolio_id, imported_id, profile), record)
            _write_json(self.response_verification_report_path(portfolio_id, imported_id, profile), verification)
            self._append_history(portfolio_id, profile, "ack_response_imported", {"response_id": imported_id, "external_response_id": external_id, "status": record["status"], "verification_status": record["verification_status"], "stale": stale}, now=now)
            if verification.get("status") == "failed":
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response verification failed.")
            return {"response": sanitize_metadata(record, blocked_keys=ACK_BLOCKED_KEYS), "verification": verification}

    def verify_response(self, portfolio_id: str, response_id: str, *, profile: str = "public_summary", now: str | None = None) -> DomainDocument:
        record = self.read_response(portfolio_id, response_id, profile=profile)
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        payload = _as_document(record.get("response_payload"))
        return verify_response_document(payload, pack, now=now)

    def response_is_stale(self, portfolio_id: str, response: DomainDocument, *, profile: str = "public_summary") -> bool:
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        payload = _as_document(response.get("response_payload"))
        return not pack or _response_stale(payload, pack) or self.pack_is_stale(portfolio_id, pack, profile=profile)

    def refresh_evidence(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            response_id = str(payload.get("response_id") or "").strip() or self._latest_accepted_response_id(portfolio_id, profile)
            if not response_id:
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("No accepted acknowledgement response is available.")
            response = self.read_response(portfolio_id, response_id, profile=profile)
            verification = self.verify_response(portfolio_id, response_id, profile=profile, now=now)
            if response.get("status") != "accepted" or verification.get("status") == "failed" or self.response_is_stale(portfolio_id, response, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Only accepted, verified, non-stale acknowledgement responses can create evidence.")
            source = self.build_evidence_source(portfolio_id, response_id, profile=profile, response=response, verification=verification)
            public = _evidence_public_summary(response)
            evidence = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_EVIDENCE_PACKAGE_TYPE,
                "acknowledgement_id": _evidence_id(portfolio_id, profile, source),
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "updated_at": now,
                "status": "current",
                "external_review_status": "accepted",
                "source": source,
                "source_hash": stable_hash(source),
                "public_summary": public,
            }
            evidence["integrity_hash"] = ack_evidence_hash(evidence)
            _write_json(self.evidence_path(portfolio_id, profile), evidence)
            self._append_history(portfolio_id, profile, "ack_evidence_refreshed", {"acknowledgement_id": evidence["acknowledgement_id"], "source_hash": evidence["source_hash"], "response_id": response_id}, now=now)
            return sanitize_metadata(evidence, blocked_keys=ACK_BLOCKED_KEYS)

    def build_evidence_source(
        self,
        portfolio_id: str,
        response_id: str,
        *,
        profile: str = "public_summary",
        response: DomainDocument | None = None,
        verification: DomainDocument | None = None,
    ) -> DomainDocument:
        response = _document_or(response, self.read_response(portfolio_id, response_id, profile=profile))
        verification = _document_or(verification, self.verify_response(portfolio_id, response_id, profile=profile))
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        src = _as_document(response.get("source"))
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "profile": profile,
                "response_id": response.get("response_id"),
                "response_integrity_hash": response.get("integrity_hash"),
                "response_payload_hash": response.get("payload_hash"),
                "response_status": response.get("status"),
                "response_verification_status": verification.get("status"),
                "response_verification_hash": verification_hash(verification),
                "review_pack_id": pack.get("pack_id"),
                "review_pack_source_hash": pack.get("source_hash"),
                "response_review_pack_id": src.get("review_pack_id"),
                "response_review_pack_source_hash": src.get("review_pack_source_hash"),
                "transparency_zip_sha256": src.get("transparency_zip_sha256"),
                "transparency_manifest_hash": src.get("transparency_manifest_hash"),
                "transparency_feed_source_hash": src.get("transparency_feed_source_hash"),
                "response_public_summary_hash": stable_hash(_evidence_public_summary(response)),
            },
            blocked_keys=ACK_BLOCKED_KEYS,
        )

    def evidence_is_stale(self, portfolio_id: str, evidence: DomainDocument | None = None, *, profile: str = "public_summary") -> bool:
        data = _document_or(evidence, self.read_evidence(portfolio_id, profile=profile, default={}))
        if not data:
            return False
        source = _as_document(data.get("source"))
        response_id = str(source.get("response_id") or "")
        if not response_id:
            return True
        try:
            current = self.build_evidence_source(portfolio_id, response_id, profile=str(data.get("profile") or profile))
        except Exception:
            return True
        return stable_hash(current) != str(data.get("source_hash") or "")

    def export_evidence(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={}) or self.refresh_evidence(portfolio_id, payload, now=now)
            self._ensure_evidence_exportable(portfolio_id, evidence, profile=profile)
            state = _state_tuple(evidence)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_evidence_exported"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence export already exists for this source state.")
            export_dir = self.evidence_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            data_docs = _evidence_data_documents(evidence)
            _write_json(export_dir / "acknowledgement-evidence.json", evidence)
            _write_json(export_dir / "acknowledgement-evidence-summary.json", {"summary": acknowledgement_summary(evidence), "public_summary": evidence.get("public_summary")})
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            (export_dir / "README.txt").write_text(_evidence_readme(evidence), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "acknowledgement-evidence-manifest.json"]
            manifest = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_EVIDENCE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Transparency Acknowledgement Evidence", "version": __version__},
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "source_hash": evidence.get("source_hash"),
                "acknowledgement": {"acknowledgement_id": evidence.get("acknowledgement_id"), "integrity_hash": evidence.get("integrity_hash"), "source_hash": evidence.get("source_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": redaction_summary({"evidence": evidence, "data": data_docs}),
            }
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-evidence-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "ack_evidence_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ACK_BLOCKED_KEYS)
