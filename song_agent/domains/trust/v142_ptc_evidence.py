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
from song_agent.domains.trust.v142_ptc_readiness import PublicTrustCenterStoreReadinessMixin
from song_agent.domains.trust import v142_ptc_readiness as _v142_ptc_readiness
from song_agent.domains.trust.v142_ptc_evidence_2 import PublicTrustCenterStoreEvidenceMixin
from song_agent.domains.trust import v142_ptc_evidence_2 as _v142_ptc_evidence_2
from song_agent.domains.trust.v142_ptc_lifecycle import PublicTrustCenterStoreLifecycleMixin
from song_agent.domains.trust import v142_ptc_lifecycle as _v142_ptc_lifecycle

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

PublicTrustCenterStateError = _make_deferred_global('PublicTrustCenterStateError')
ch = _make_deferred_global('ch')
char = _make_deferred_global('char')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterStateError, ch, char, item
    PublicTrustCenterStateError = namespace.get('PublicTrustCenterStateError', PublicTrustCenterStateError)
    ch = namespace.get('ch', ch)
    char = namespace.get('char', char)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


PTC_SCHEMA_VERSION = 1
PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"
PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")




def _sanitize_public_metadata(value: object, *, key: str = "") -> DomainDocument:
    if isinstance(value, dict):
        cleaned: DomainDocument = {}
        for child_key, child in value.items():
            text_key = str(child_key)
            if text_key.lower() in PTC_BLOCKED_KEYS:
                continue
            cleaned[text_key] = _sanitize_public_metadata(child, key=text_key)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_public_metadata(item, key=key) for item in value]
    if isinstance(value, str):
        text = "".join(char for char in value if char == "\n" or char == "\t" or ord(char) >= 32)
        if key in {"path", "filename", "entries"}:
            return text
        return sanitize_sensitive_text(text)
    return value

def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _verification_hash(report: DomainDocument) -> str | None:
    if not report:
        return None
    if report.get("schema_version") and "checks" in report:
        return ack_verification_hash(report)
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})

def _verification_current_status(report: DomainDocument, zip_sha256: object, zip_size_bytes: object, manifest_hash: object) -> str:
    if not report:
        return "missing"
    status = str(report.get("status") or "missing")
    if status != "passed":
        return status
    if str(report.get("zip_sha256") or "") != str(zip_sha256 or ""):
        return "failed"
    if str(report.get("zip_size_bytes") or "") != str(zip_size_bytes or ""):
        return "failed"
    if str(report.get("manifest_hash") or "") != str(manifest_hash or ""):
        return "failed"
    return "passed"

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PublicTrustCenterStateError("Resolved path escapes Public Trust Center directory.") from exc

def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "ptc-default")).strip("-_")
    if not text:
        text = "ptc-default"
    return text[:80]

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}

def _write_readme(export_dir: Path, report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Public Trust Center",
                "",
                f"Center ID: {report.get('center_id')}",
                f"Status: {summary.get('status')}",
                f"Readiness: {summary.get('readiness')}",
                "This package is offline and references public evidence packages by fingerprint only.",
                "Run verify-public-trust-center-package before relying on it.",
                "",
            ]
        ),
        encoding="utf-8",
    )
