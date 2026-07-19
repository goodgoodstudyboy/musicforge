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
from song_agent.domains.trust.trust_operations_controls_contracts import BASELINE_CONTROLS as BASELINE_CONTROLS, CONTROL_EXPORT_ENTRIES as CONTROL_EXPORT_ENTRIES, TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION as TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION, _blocker_summary as _blocker_summary, _blockers_from_results as _blockers_from_results, _catalog_summary as _catalog_summary, _evaluate_control as _evaluate_control, _manual_actions_from_blockers as _manual_actions_from_blockers, _results_summary as _results_summary, control_hash as control_hash, control_manifest_hash as control_manifest_hash
from song_agent.domains.trust.trust_operations_hub_contracts import hub_manifest_hash as hub_manifest_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash
from song_agent.domains.trust.trust_operations_incident_knowledge_contracts import _classify_incident as _classify_incident, knowledge_hash as knowledge_hash, knowledge_manifest_hash as knowledge_manifest_hash

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
_ControlVerifier = _make_deferred_global('_ControlVerifier')
marker = _make_deferred_global('marker')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS, _ControlVerifier, marker, part
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _ControlVerifier = namespace.get('_ControlVerifier', _ControlVerifier)
    marker = namespace.get('marker', marker)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_CONTROL_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_control_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64




def verify_trust_operations_control_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_policy_passed: bool = False,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _ControlVerifier(
        Path(zip_path),
        strict=strict,
        require_policy_passed=require_policy_passed,
        hub_package_path=Path(hub_package_path) if hub_package_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        incident_knowledge_package_path=Path(incident_knowledge_package_path) if incident_knowledge_package_path else None,
        incident_knowledge_verification_report_path=Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()

def write_trust_operations_control_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))

def print_trust_operations_control_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Control verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"controls: {summary.get('control_count') or 0}")
    print(f"required failed: {summary.get('required_failed_count') or 0}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")

def trust_operations_control_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0

def _control_matches_external_entry(control: DomainDocument, entry: DomainDocument, fact: DomainDocument, guard: DomainDocument | None, knowledge_report: DomainDocument, incident_report: DomainDocument) -> bool:
    source = _as_document(control.get("source"))
    scope = _as_document(control.get("scope"))
    recommended = _as_document(entry.get("recommended_guard"))
    guard = guard or {}
    expected_source = {
        "source_type": "knowledge_entry",
        "knowledge_entry_id": entry.get("entry_id"),
        "knowledge_entry_hash": entry.get("integrity_hash"),
        "incident_id": entry.get("incident_id"),
        "incident_hash": entry.get("source", {}).get("incident_hash"),
        "closeout_hash": entry.get("source", {}).get("closeout_hash"),
        "source_fingerprint": entry.get("source", {}).get("source_fingerprint"),
        "knowledge_verification_report_hash": verification_hash(knowledge_report) if knowledge_report else source.get("knowledge_verification_report_hash"),
        "incident_verification_report_hash": verification_hash(incident_report) if incident_report else source.get("incident_verification_report_hash"),
        "guard_id": guard.get("guard_id"),
        "guard_hash": guard.get("integrity_hash"),
        "recommended_guard_type": recommended.get("guard_type"),
    }
    return (
        control.get("severity") == fact.get("severity")
        and control.get("category") == fact.get("category")
        and scope.get("component_type") == fact.get("component_type")
        and scope.get("component_id") == fact.get("component_id")
        and scope.get("failure_mode") == fact.get("failure_mode")
        and source == expected_source
        and control.get("source_hash") == stable_hash(expected_source)
        and control.get("evaluation", {}).get("method") == "knowledge_guard_coverage"
        and control.get("integrity_hash") == control_hash(control)
    )

def _result_projection(rows: list[DomainDocument]) -> list[DomainDocument]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"control_id": row.get("control_id"), "control_hash": row.get("control_hash"), "required": row.get("required"), "severity": row.get("severity"), "status": row.get("status"), "evaluation_method": row.get("evaluation_method")})
    return sorted(out, key=lambda item: str(item.get("control_id") or ""))

def _blocker_projection(rows: list[DomainDocument]) -> list[DomainDocument]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"control_id": row.get("control_id"), "severity": row.get("severity"), "source_result_hash": row.get("source_result_hash")})
    return sorted(out, key=lambda item: str(item.get("control_id") or ""))

def _action_projection(rows: list[DomainDocument]) -> list[DomainDocument]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"control_id": row.get("control_id"), "status": row.get("status"), "allowed_automation": row.get("allowed_automation")})
    return sorted(out, key=lambda item: str(item.get("control_id") or ""))

def _read_json_file(path: Path) -> DomainDocument:
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return _as_document(value)

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
