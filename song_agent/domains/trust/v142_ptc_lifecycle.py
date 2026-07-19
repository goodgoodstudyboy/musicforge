# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import html as html
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
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_verification_summary_from_portfolio_dir as accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal as verify_release_portfolio_governance_attestation_portal
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry as verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore as ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, verification_hash as ack_verification_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import verify_release_portfolio_governance_attestation_transparency_acknowledgement_package as verify_release_portfolio_governance_attestation_transparency_acknowledgement_package
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency as verify_release_portfolio_governance_attestation_transparency
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_MANIFEST_HASH_EXCLUDE_KEYS as PTC_MANIFEST_HASH_EXCLUDE_KEYS, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, PTC_REPORT_HASH_EXCLUDE_KEYS as PTC_REPORT_HASH_EXCLUDE_KEYS, _DELIVERY_COLLECTION_DOMAINS as _DELIVERY_COLLECTION_DOMAINS, _delivery_item_status as _delivery_item_status, _delivery_public_payload as _delivery_public_payload, _delivery_summary_from_item as _delivery_summary_from_item, _delivery_summary_key as _delivery_summary_key, _delivery_verification_index_from_sidecars as _delivery_verification_index_from_sidecars, _delivery_verification_index_from_source as _delivery_verification_index_from_source, _fingerprint_key as _fingerprint_key, _html_shell as _html_shell, _kv as _kv, _links as _links, _package_index as _package_index, _package_verification_index_from_sidecars as _package_verification_index_from_sidecars, _package_verification_sidecars as _package_verification_sidecars, _table as _table, _verification_index as _verification_index, _verification_sidecars as _verification_sidecars, _verification_sidecars_from_docs as _verification_sidecars_from_docs, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_data_documents as public_trust_center_data_documents, public_trust_center_html_pages as public_trust_center_html_pages, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash

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

key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global key, value
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


PTC_SCHEMA_VERSION = 1
PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"
PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")




class PublicTrustCenterStoreLifecycleMixin:
    def _history_has_state_event(self, center_id: str, state: DomainDocument, event_type: str) -> bool:
        path = self.history_path(center_id)
        if not path.exists():
            return False
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") != event_type:
                continue
            payload = _as_document(event.get("payload"))
            if all(str(payload.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False
