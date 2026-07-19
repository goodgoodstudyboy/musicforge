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

ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError = _make_deferred_global('ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError')
_change_request_actions = _make_deferred_global('_change_request_actions')
_check = _make_deferred_global('_check')
_ensure_within = _make_deferred_global('_ensure_within')
_next_id = _make_deferred_global('_next_id')
_read_json_default = _make_deferred_global('_read_json_default')
_sha256 = _make_deferred_global('_sha256')
_state_tuple = _make_deferred_global('_state_tuple')
_write_json = _make_deferred_global('_write_json')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, _change_request_actions, _check, _ensure_within, _next_id, _read_json_default, _sha256
    global _state_tuple, _write_json, _write_zip, _zip_entries, entry, key, value
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError = namespace.get('ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError', ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError)
    _change_request_actions = namespace.get('_change_request_actions', _change_request_actions)
    _check = namespace.get('_check', _check)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _next_id = namespace.get('_next_id', _next_id)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _sha256 = namespace.get('_sha256', _sha256)
    _state_tuple = namespace.get('_state_tuple', _state_tuple)
    _write_json = namespace.get('_write_json', _write_json)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
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




class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStoreEvidenceMixin:
    def build_evidence_zip(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={}) or self.refresh_evidence(portfolio_id, payload, now=now)
            self._ensure_evidence_exportable(portfolio_id, evidence, profile=profile)
            state = _state_tuple(evidence)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_evidence_zip_built"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence ZIP already exists for this source state.")
            export_dir = self.evidence_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.evidence_zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "acknowledgement-evidence-manifest.json").exists():
                self.export_evidence(portfolio_id, {"profile": profile}, now=now)
            manifest = read_json(export_dir / "acknowledgement-evidence-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-evidence-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "path": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            self._append_history(portfolio_id, profile, "ack_evidence_zip_built", {**state, "zip_sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=ACK_BLOCKED_KEYS)

    def create_change_request(self, portfolio_id: str, response_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            response = self.read_response(portfolio_id, response_id, profile=profile)
            verification = self.verify_response(portfolio_id, response_id, profile=profile, now=now)
            if response.get("status") not in {"needs_changes", "rejected"} or verification.get("status") == "failed" or self.response_is_stale(portfolio_id, response, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Only verified non-stale needs_changes/rejected acknowledgement responses can create Change Request drafts.")
            existing = self._find_change_request(portfolio_id, response_id, profile=profile)
            if existing:
                return existing
            cr_id = _next_id(self.change_requests_dir(portfolio_id, profile), "att-trans-ack-cr")
            response_payload = _as_document(response.get("response_payload"))
            cr = {
                "change_request_id": cr_id,
                "source": "transparency_acknowledgement_response",
                "response_id": response_id,
                "status": "draft",
                "reason": "External reviewer requested Transparency acknowledgement follow-up.",
                "requested_actions": _change_request_actions(response_payload),
                "created_at": now,
            }
            self.change_requests_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_requests_dir(portfolio_id, profile) / f"{cr_id}.json", cr)
            return sanitize_metadata(cr, blocked_keys=ACK_BLOCKED_KEYS)

    def list_change_requests(self, portfolio_id: str, *, profile: str = "public_summary") -> list[DomainDocument]:
        root = self.change_requests_dir(portfolio_id, profile)
        if not root.exists():
            return []
        return [_read_json_default(path, default={}) for path in sorted(root.glob("att-trans-ack-cr-*.json"))]

    def _pack_findings(self, source: DomainDocument, *, require_verified: bool) -> tuple[list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        checks: list[DomainDocument] = []
        checks.append(_check("transparency_zip_exists", bool(source.get("transparency_zip_sha256")), "Transparency ZIP exists."))
        checks.append(_check("transparency_verification_passed", source.get("transparency_verification_status") == "passed", "Transparency verification is passed."))
        checks.append(_check("transparency_event_semantics_passed", source.get("transparency_event_semantics_status") == "passed", "Transparency event semantics passed."))
        checks.append(_check("transparency_notice_semantics_passed", source.get("transparency_notice_semantics_status") == "passed", "Transparency notice semantics passed."))
        blockers = [item for item in checks if item["status"] == "failed" and (require_verified or item["check_id"] == "transparency_zip_exists")]
        warnings = [item for item in checks if item["status"] == "failed" and item not in blockers]
        return blockers, warnings, checks

    def _ensure_evidence_exportable(self, portfolio_id: str, evidence: DomainDocument, *, profile: str) -> None:
        if not evidence:
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence is missing.")
        if self.evidence_is_stale(portfolio_id, evidence, profile=profile):
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence is stale.")
        if evidence.get("status") != "current" or evidence.get("external_review_status") != "accepted":
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence is not current accepted evidence.")

    def _latest_accepted_response_id(self, portfolio_id: str, profile: str) -> str:
        for item in reversed(self.list_responses(portfolio_id, profile=profile)):
            if item.get("status") == "accepted" and item.get("verification_status") == "passed" and not item.get("stale"):
                return str(item.get("response_id") or "")
        return ""

    def _find_change_request(self, portfolio_id: str, response_id: str, *, profile: str) -> DomainDocument:
        for item in self.list_change_requests(portfolio_id, profile=profile):
            if item.get("response_id") == response_id:
                return sanitize_metadata(item, blocked_keys=ACK_BLOCKED_KEYS)
        return {}

    def _history_has_state_event(self, portfolio_id: str, profile: str, state: dict[str, str], event_type: str) -> bool:
        path = self.pack_history_path(portfolio_id, profile)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") != event_type:
                continue
            summary = _as_document(event.get("summary"))
            if all(str(summary.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: DomainDocument, *, now: str) -> None:
        path = self.pack_history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"att-trans-ack-history-{count + 1:06d}", "at": now, "type": event_type, "summary": summary}, blocked_keys=ACK_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
