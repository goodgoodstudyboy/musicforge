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
import os as os
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import ACCEPTANCE_BOARD_BLOCKED_KEYS as ACCEPTANCE_BOARD_BLOCKED_KEYS, ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE as ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE, ACCEPTANCE_BOARD_PACKAGE_TYPE as ACCEPTANCE_BOARD_PACKAGE_TYPE, ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE, acceptance_board_conflict_hash as acceptance_board_conflict_hash, acceptance_board_manifest_hash as acceptance_board_manifest_hash, acceptance_board_policy_hash as acceptance_board_policy_hash, acceptance_board_report_hash as acceptance_board_report_hash, sidecar_hash as sidecar_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_contracts import distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import verification_hash as accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.domains.trust.public_trust_center_distribution_kit_core_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
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
_AcceptanceBoardVerifier = _make_deferred_global('_AcceptanceBoardVerifier')
ch = _make_deferred_global('ch')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS, _AcceptanceBoardVerifier, ch
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _AcceptanceBoardVerifier = namespace.get('_AcceptanceBoardVerifier', _AcceptanceBoardVerifier)
    ch = namespace.get('ch', ch)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_BOARD_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 160
ROOT_ENTRIES = {
    "acceptance-board-manifest.json",
    "board-report.json",
    "board-policy.json",
    "conflict-report.json",
    "board-summary.json",
    "accepted-evidence-index.json",
    "response-index.json",
    "quorum-evidence.json",
    "README.txt",
    "VERIFY.txt",
}




def verify_public_trust_center_acceptance_board_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_quorum: bool = False,
    require_no_conflicts: bool = False,
    min_accepted_count: int = 0,
    min_accepted_organizations: int = 0,
    required_roles: list[str] | None = None,
    distribution_kit_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _AcceptanceBoardVerifier(
        Path(zip_path),
        strict=strict,
        require_ready=require_ready,
        require_quorum=require_quorum,
        require_no_conflicts=require_no_conflicts,
        min_accepted_count=min_accepted_count,
        min_accepted_organizations=min_accepted_organizations,
        required_roles=required_roles or [],
        distribution_kit_path=Path(distribution_kit_path) if distribution_kit_path else None,
        accepted_evidence_dir=Path(accepted_evidence_dir) if accepted_evidence_dir else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()

def write_public_trust_center_acceptance_board_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))

def print_public_trust_center_acceptance_board_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Public Trust Center Acceptance Board verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"readiness: {summary.get('readiness') or 'unknown'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")

def public_trust_center_acceptance_board_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0

def _quorum_from_report(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    policy = _as_document(report.get("policy"))
    participants = _as_list(report.get("participants"))
    counted = [str(item.get("response_id") or "") for item in participants if isinstance(item, dict) and item.get("counts_for_quorum")]
    roles = {str(item.get("role") or "").lower(): "passed" for item in participants if isinstance(item, dict) and item.get("counts_for_quorum") and item.get("role")}
    return {"schema_version": 1, "source_hash": report.get("source_hash"), "policy_hash": policy.get("policy_hash"), "decision": {"readiness": report.get("readiness"), "quorum_status": summary.get("quorum_status"), "required_roles_status": summary.get("required_roles_status"), "conflict_status": summary.get("conflict_status")}, "counted_response_ids": counted, "required_roles": roles}

def _find_row(rows: object, key: str, value: str) -> DomainDocument:
    for item in _as_list(rows):
        if isinstance(item, dict) and str(item.get(key) or "") == value:
            return item
    return {}

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
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return _as_document(value)

def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text

def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"

def _redaction_findings(scope: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "local_path", "message": "Local path pattern found."})
    lowered = text.lower()
    for marker in ("github" + "key", "x-access-" + "token", "api_" + "key", "access_" + "token", "source_" + "path", "local_" + "path", "file_" + "path"):
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    return findings
