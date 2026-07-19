# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Callable as Callable
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.v142_ptccv_readiness import _PublicTrustCenterVerifierReadinessMixin
from song_agent.domains.trust import v142_ptccv_readiness as _v142_ptccv_readiness
from song_agent.domains.trust.v142_ptccv_evidence import _PublicTrustCenterVerifierEvidenceMixin
from song_agent.domains.trust import v142_ptccv_evidence as _v142_ptccv_evidence

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

VERIFIER_BLOCKED_KEYS = _make_deferred_global('VERIFIER_BLOCKED_KEYS')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _bind_deferred_defaults(namespace)


PTC_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 250
REQUIRED_ENTRIES = {
    "trust-center-manifest.json",
    "trust-center-report.json",
    "data/trust-center-data.json",
    "data/release-index.json",
    "data/portfolio-index.json",
    "data/package-index.json",
    "data/verification-index.json",
    "data/public-package-verification-index.json",
    "data/risk-register.json",
    "data/transparency-index.json",
    "data/acknowledgement-index.json",
    "data/delivery-index.json",
    "data/distribution-index.json",
    "data/submission-index.json",
    "data/submission-evidence-index.json",
    "data/operations-index.json",
    "data/operations-package-index.json",
    "data/readiness-matrix.json",
    "data/delivery-risk-register.json",
    "data/delivery-verification-index.json",
    "index.html",
    "releases.html",
    "portfolios.html",
    "delivery.html",
    "distribution.html",
    "submissions.html",
    "operations.html",
    "evidence.html",
    "risk.html",
    "verify.html",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"trust-center-manifest.json"}




def _packages_from_sidecars(sidecars: list[object]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for item in sidecars:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "portfolio_id": item.get("portfolio_id"),
                "profile": item.get("profile"),
                "package_type": item.get("package_type"),
                "zip_sha256": item.get("zip_sha256"),
                "zip_size_bytes": item.get("zip_size_bytes"),
                "manifest_hash": item.get("manifest_hash"),
                "verification_hash": item.get("verification_hash"),
                "verification_status": item.get("verification_status"),
                "verification_report_hash": item.get("verification_report_hash"),
                "verification_report_status": item.get("verification_report_status"),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))

def _verifications_from_sidecars(sidecars: list[object]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for item in sidecars:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "portfolio_id": item.get("portfolio_id"),
                "profile": item.get("profile"),
                "package_type": item.get("package_type"),
                "zip_sha256": item.get("zip_sha256"),
                "zip_size_bytes": item.get("zip_size_bytes"),
                "manifest_hash": item.get("manifest_hash"),
                "verification_hash": item.get("verification_hash"),
                "verification_status": item.get("verification_status"),
                "verification_report_hash": item.get("verification_report_hash"),
                "verification_report_status": item.get("verification_report_status"),
                "blocker_count": item.get("blocker_count", 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))

def _delivery_payloads_from_sidecars(sidecars: dict[str, DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for path, doc in sorted(sidecars.items()):
        del path
        if not isinstance(doc, dict):
            continue
        payload = _as_document(doc.get("payload"))
        row = dict(payload)
        rows.append(row)
    return sorted(rows, key=_delivery_payload_key)

def _delivery_payloads_from_fingerprint_sidecars(sidecars: dict[str, DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for path, doc in sorted(sidecars.items()):
        del path
        if not isinstance(doc, dict):
            continue
        payload = _as_document(doc.get("payload"))
        rows.append(dict(payload))
    return sorted(rows, key=_delivery_payload_key)

def _delivery_anchor_rows_from_fingerprint_sidecars(sidecars: dict[str, DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for path, doc in sorted(sidecars.items()):
        if not isinstance(doc, dict):
            continue
        rows.append(
            {
                "path": path,
                "fingerprint_hash": doc.get("fingerprint_hash"),
                "payload_hash": doc.get("payload_hash"),
                "fingerprints_hash": stable_hash(_as_document(doc.get("fingerprints"))),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("path") or ""))

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except Exception:
        return {}

def _find_registry_current_entry(registry: DomainDocument) -> DomainDocument:
    current_id = str(registry.get("current_entry_id") or "")
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == current_id:
            return entry
    return {}

def _delivery_payloads_from_data_docs(data_docs: dict[str, DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for domain, doc_name, row_key in (
        ("release", "delivery-index.json", "releases"),
        ("distribution", "distribution-index.json", "targets"),
        ("submission", "submission-index.json", "submissions"),
        ("submission_evidence", "submission-evidence-index.json", "evidence"),
        ("operations", "operations-index.json", "operations"),
    ):
        doc = data_docs.get(doc_name, {})
        values = _as_list(doc.get(row_key))
        for item in values:
            if isinstance(item, dict):
                rows.append(_delivery_public_payload(domain, item))
    return sorted(rows, key=_delivery_payload_key)

def _delivery_public_payload(domain: str, item: DomainDocument) -> DomainDocument:
    allowed = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "status",
        "name",
        "readiness",
        "release_signoff_status",
        "release_zip_status",
        "distribution_status",
        "submission_status",
        "submission_evidence_status",
        "operations_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "portfolio_public_proof_status",
        "risk_count",
        "signoff_status",
        "profile_id",
        "platform",
        "target_name",
        "target_status",
        "track_count",
        "ready_count",
        "submitted_count",
        "accepted_count",
        "latest_feedback_status",
        "report_status",
        "report_hash",
        "signoff_hash",
        "redaction_status",
        "accepted_evidence_count",
        "attachment_count",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "package_zip_status",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "runbook_status",
        "change_request_count",
        "fingerprint_hash",
    }
    return {"domain": domain, **{key: item.get(key) for key in sorted(allowed) if key in item}}

def _delivery_summary_key(item: DomainDocument) -> tuple[str, str, str]:
    return (str(item.get("release_id") or ""), str(item.get("domain") or ""), str(item.get("entity_id") or item.get("target_id") or item.get("submission_id") or ""))

def _delivery_payload_key(item: DomainDocument) -> tuple[str, str, str, str]:
    return (str(item.get("release_id") or ""), str(item.get("domain") or ""), str(item.get("target_id") or ""), str(item.get("submission_id") or item.get("entity_id") or ""))

def _fingerprint_key(item: DomainDocument) -> tuple[str, str, str]:
    return (str(item.get("portfolio_id") or ""), str(item.get("package_type") or ""), str(item.get("profile") or ""))

def _is_forbidden_public_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/") or "/.musicforge/" in lowered

def _counts(values: list[str]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for value in values:
        rows[value] = rows.get(value, 0) + 1
    return rows

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _contains_local_path(text: str) -> bool:
    return any(pattern.search(text) for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS)

def _normalize_newlines(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")

def _redaction_findings(name: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            excerpt = match.group(0)[:120]
            if _allowed_public_false_positive(excerpt):
                continue
            findings.append({"path": name, "pattern": replacement, "excerpt": excerpt})
    if _contains_local_path(text):
        findings.append({"path": name, "pattern": "local_path", "excerpt": "local path"})
    lowered = text.lower()
    github_key_marker = "github" + "key"
    access_token_marker = "x-access" + "-token"
    secret_marker = "sk-" + "secret"
    if github_key_marker in lowered or access_token_marker in lowered or secret_marker in lowered:
        findings.append({"path": name, "pattern": "secret_marker", "excerpt": "secret marker"})
    return findings[:20]

def _allowed_public_false_positive(value: str) -> bool:
    lowered = str(value or "").lower()
    return lowered in {"sk-register", "sk-register.json"}

def _blocked_key_findings(name: str, value: object, prefix: str = "") -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": path, "pattern": "blocked_metadata_key"})
            findings.extend(_blocked_key_findings(name, child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value[:200]):
            findings.extend(_blocked_key_findings(name, child, f"{prefix}[{index}]"))
    return findings[:20]
