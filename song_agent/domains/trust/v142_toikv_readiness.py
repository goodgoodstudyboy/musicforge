# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_incident_knowledge_contracts import KNOWLEDGE_EXPORT_ENTRIES as KNOWLEDGE_EXPORT_ENTRIES, TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION as TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE, TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE as TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE, _classify_incident as _classify_incident, knowledge_hash as knowledge_hash, knowledge_manifest_hash as knowledge_manifest_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash

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
_KnowledgeVerifier = _make_deferred_global('_KnowledgeVerifier')
marker = _make_deferred_global('marker')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS, _KnowledgeVerifier, marker, part
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _KnowledgeVerifier = namespace.get('_KnowledgeVerifier', _KnowledgeVerifier)
    marker = namespace.get('marker', marker)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_KNOWLEDGE_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64




def verify_trust_operations_incident_knowledge_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_guards_passed: bool = False,
    require_no_open_recurrence: bool = False,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _KnowledgeVerifier(
        Path(zip_path),
        strict=strict,
        require_guards_passed=require_guards_passed,
        require_no_open_recurrence=require_no_open_recurrence,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()

def write_trust_operations_incident_knowledge_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))

def print_trust_operations_incident_knowledge_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Incident Knowledge verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"entries: {summary.get('entry_count') or 0}")
    print(f"guards: {summary.get('guard_count') or 0}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")

def trust_operations_incident_knowledge_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0

def _read_json_file(path: Path) -> DomainDocument:
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return _as_document(value)

def _entry_matches_external_fact(entry: DomainDocument, fact: DomainDocument, source_summary: DomainDocument) -> bool:
    source = _as_document(entry.get("source"))
    expected_source = {
        "incident_hash": source.get("incident_hash"),
        "closeout_hash": source.get("closeout_hash"),
        "incident_verification_report_hash": source.get("incident_verification_report_hash"),
        "hub_verification_report_hash": source.get("hub_verification_report_hash"),
        "source_fingerprint": source.get("source_fingerprint"),
    }
    expected_source_hash = stable_hash(expected_source)
    recommended = _as_document(entry.get("recommended_guard"))
    return (
        entry.get("incident_id") == fact.get("incident_id")
        and entry.get("severity") == fact.get("severity")
        and entry.get("category") == fact.get("category")
        and entry.get("component_type") == fact.get("component_type")
        and entry.get("component_id") == fact.get("component_id")
        and entry.get("failure_mode") == fact.get("failure_mode")
        and entry.get("root_cause") == fact.get("root_cause")
        and entry.get("preventive_pattern") == fact.get("preventive_pattern")
        and recommended.get("guard_type") == fact.get("recommended_guard", {}).get("guard_type")
        and recommended.get("title") == fact.get("recommended_guard", {}).get("title")
        and recommended.get("reason") == fact.get("recommended_guard", {}).get("reason")
        and source.get("closeout_hash") == fact.get("closeout_hash")
        and source.get("incident_verification_report_hash") == source_summary.get("incident_verification_report_hash")
        and source.get("hub_verification_report_hash") == source_summary.get("hub_verification_report_hash")
        and source.get("source_fingerprint") == fact.get("source_fingerprint")
        and entry.get("source_hash") == expected_source_hash
    )

def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)

def _is_forbidden_entry(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".musicforge/") or "/.musicforge/" in lowered

def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".txt", ".md", ".csv", ".html", ".jsonl"))

def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    lowered = text.lower()
    return any(marker in lowered for marker in ("github" + "key", "x-access" + "-token", "github" + "_pat_"))

def _walk_json_values(value: object, prefix: str = "$") -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_walk_json_values(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_json_values(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        rows.append((prefix, value))
    return rows

def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
