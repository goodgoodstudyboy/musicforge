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
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_contracts import TRANSPARENCY_BLOCKED_KEYS as TRANSPARENCY_BLOCKED_KEYS, TRANSPARENCY_PACKAGE_TYPE as TRANSPARENCY_PACKAGE_TYPE, TRANSPARENCY_FEED_PACKAGE_TYPE as TRANSPARENCY_FEED_PACKAGE_TYPE, TRANSPARENCY_REPORT_PACKAGE_TYPE as TRANSPARENCY_REPORT_PACKAGE_TYPE, _build_events as _build_events, _build_notices as _build_notices, transparency_event_hash as transparency_event_hash, transparency_feed_hash as transparency_feed_hash, transparency_manifest_hash as transparency_manifest_hash, transparency_notice_hash as transparency_notice_hash, transparency_summary as transparency_summary
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

marker = _make_deferred_global('marker')

def bind_globals(namespace: dict[str, object]) -> None:
    global marker
    marker = namespace.get('marker', marker)
    _bind_deferred_defaults(namespace)


TRANSPARENCY_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 300
REQUIRED_ENTRIES = {
    "transparency-manifest.json",
    "transparency-feed.json",
    "transparency-report.json",
    "README.txt",
    "data/current-public-state.json",
    "data/package-fingerprints.json",
    "data/registry-binding-summary.json",
    "data/portal-binding-summary.json",
    "data/attestation-binding-summary.json",
    "data/accepted-evidence-binding-summary.json",
}
LEGAL_SIDECAR_ENTRIES = {"transparency-manifest.json"}




def _event_semantics(event: DomainDocument) -> DomainDocument:
    source = _as_document(event.get("source"))
    summary = _as_document(event.get("summary"))
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "severity": event.get("severity"),
        "portfolio_id": event.get("portfolio_id"),
        "attestation_profile": event.get("attestation_profile"),
        "source": {
            "public_state_hash": source.get("public_state_hash"),
            "registry_current_entry_id": source.get("registry_current_entry_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "portal_manifest_hash": source.get("portal_manifest_hash"),
            "accepted_evidence_id": source.get("accepted_evidence_id"),
        },
        "public_references": _as_document(summary.get("public_references")),
    }

def _notice_semantics(notice: DomainDocument) -> DomainDocument:
    return {
        "notice_id": notice.get("notice_id"),
        "notice_type": notice.get("notice_type"),
        "severity": notice.get("severity"),
        "portfolio_id": notice.get("portfolio_id"),
        "attestation_profile": notice.get("attestation_profile"),
        "source_event_ids": list(notice.get("source_event_ids") or []) if isinstance(notice.get("source_event_ids"), list) else [],
        "public_references": _as_document(notice.get("public_references")),
    }

def _semantic_mismatches(kind: str, expected: list[DomainDocument], actual: list[DomainDocument]) -> list[str]:
    problems: list[str] = []
    if len(actual) != len(expected):
        problems.append(f"{kind} count {len(actual)} != expected {len(expected)}")
    for index, expected_item in enumerate(expected):
        if index >= len(actual):
            problems.append(f"{kind}[{index}] missing")
            continue
        actual_item = actual[index]
        for key, expected_value in expected_item.items():
            actual_value = actual_item.get(key)
            if key == "public_references" and kind == "notice":
                if not _reference_subset_matches(expected_value, actual_value, notice_type=str(expected_item.get("notice_type") or "")):
                    problems.append(f"{kind}[{index}].{key} mismatch")
                continue
            if actual_value != expected_value:
                problems.append(f"{kind}[{index}].{key} mismatch")
    return problems

def _reference_subset_matches(expected: object, actual: object, *, notice_type: str) -> bool:
    expected_refs = _as_document(expected)
    actual_refs = _as_document(actual)
    for key, value in expected_refs.items():
        if actual_refs.get(key) != value:
            return False
    extra_keys = set(actual_refs) - set(expected_refs)
    return not extra_keys or (notice_type == "public_state_refreshed" and extra_keys <= {"previous_state_hash"})

def _is_forbidden_entry(name: str) -> bool:
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

def _redaction_findings(path: str, text: str) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": kind, "excerpt": match.group(0)[:120]})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": "sensitive_value", "pattern": replacement, "excerpt": match.group(0)[:120]})
    return rows

def _blocked_key_findings(path: str, value: object) -> list[DomainDocument]:
    rows: list[DomainDocument] = []

    def walk(current: object, trail: str) -> None:
        if isinstance(current, dict):
            for key, item in current.items():
                lowered = str(key).lower()
                if any(marker in lowered for marker in ("api_key", "access_token", "token", "secret", "password", "provider-snapshot", "renderer.json", "source_path", "local_path", "file_path")):
                    rows.append({"path": path, "type": "blocked_key", "key": f"{trail}.{key}" if trail else str(key)})
                walk(item, f"{trail}.{key}" if trail else str(key))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                walk(item, f"{trail}[{index}]")

    walk(value, "")
    return rows
