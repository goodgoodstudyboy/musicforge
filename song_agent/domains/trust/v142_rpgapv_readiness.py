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
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_contracts import PORTAL_BLOCKED_KEYS as PORTAL_BLOCKED_KEYS, PORTAL_PACKAGE_TYPE as PORTAL_PACKAGE_TYPE, PORTAL_PAGES as PORTAL_PAGES, portal_manifest_hash as portal_manifest_hash, portal_report_hash as portal_report_hash, portal_verification_summary as portal_verification_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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
_PortalVerifier = _make_deferred_global('_PortalVerifier')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS, _PortalVerifier
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _PortalVerifier = namespace.get('_PortalVerifier', _PortalVerifier)
    _bind_deferred_defaults(namespace)


PORTAL_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
REQUIRED_ENTRIES = {
    "portal-manifest.json",
    "portal-report.json",
    "index.html",
    "current.html",
    "registry.html",
    "revocations.html",
    "verify.html",
    "data/portal-summary.json",
    "data/registry-summary.json",
    "data/current-attestation-summary.json",
    "data/registry-verification-summary.json",
    "data/attestation-verification-summary.json",
    "data/verification-commands.json",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"portal-manifest.json"}




def verify_release_portfolio_governance_attestation_portal(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_registry: bool = False,
    require_attestation: bool = False,
    require_accepted_evidence: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _PortalVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        require_registry=require_registry,
        require_attestation=require_attestation,
        require_accepted_evidence=require_accepted_evidence,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()

def write_release_portfolio_governance_attestation_portal_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))

def print_release_portfolio_governance_attestation_portal_verification_report(report: DomainDocument) -> None:
    summary = portal_verification_summary(report)
    print("MusicForge release portfolio governance attestation portal verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"current entry: {summary.get('current_entry_id') or 'none'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = _as_list(report.get(key))
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")

def release_portfolio_governance_attestation_portal_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0

def _is_forbidden_public_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")

def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

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
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    return False

def _redaction_findings(name: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": "local_path", "excerpt": match.group(0)[:120]})
    return findings

def _blocked_key_findings(name: str, value: object, path: str = "") -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"entry": name, "pattern": "blocked_key", "excerpt": key_path[:120]})
            findings.extend(_blocked_key_findings(name, item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{path}[{index}]"))
    return findings
