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
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_assurance_watch_contracts import ASSURANCE_WATCH_ARCHIVE_ENTRIES as ASSURANCE_WATCH_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION, watch_hash as watch_hash, watch_manifest_hash as watch_manifest_hash

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

def bind_globals(namespace: dict[str, object]) -> None:
    global key
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_ASSURANCE_WATCH_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_verification"
TRUST_OPERATIONS_ASSURANCE_WATCH_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64




def _expected_rows_and_action_pack(queue: DomainDocument, schedule: DomainDocument, run_index: DomainDocument, now: str) -> tuple[list[DomainDocument], DomainDocument]:
    rows: list[DomainDocument] = []
    actions: list[DomainDocument] = []
    queue_id = str(queue.get("queue_id") or "")
    hub_ids = _hub_ids_from_queue_or_run_index(queue, run_index)
    runs_by_hub = {str(row.get("hub_id") or ""): row for row in run_index.get("runs", []) if isinstance(row, dict)}
    cadence = _as_document(schedule.get("cadence"))
    interval_days = int(cadence.get("interval_days") or 7)
    grace_days = int(cadence.get("grace_days") or 1)
    requirements = _as_document(schedule.get("requirements"))
    require_verified = bool(requirements.get("require_latest_assurance_verified", True))
    for hub_id in hub_ids:
        run = runs_by_hub.get(hub_id, {"hub_id": hub_id, "status": "missing", "verification_status": "missing"})
        due_status, next_due_at = _due_status(str(run.get("verified_at") or run.get("created_at") or ""), now, interval_days, grace_days)
        reasons: list[str] = []
        readiness = "clear"
        drift_status = "clear"
        if not run.get("run_id"):
            due_status = "missing"
            readiness = "blocked"
            drift_status = "missing"
            reasons.append("assurance_run_missing")
        if run.get("status") not in {"passed", None}:
            readiness = "blocked"
            drift_status = "failed"
            reasons.append("assurance_run_failed")
        if require_verified and run.get("verification_status") != "passed":
            readiness = "blocked"
            drift_status = "failed" if run.get("verification_status") == "failed" else "missing"
            reasons.append("assurance_verification_not_passed")
        if due_status == "overdue":
            readiness = "blocked"
            reasons.append("assurance_overdue")
        elif due_status == "due" and readiness == "clear":
            readiness = "warning"
            reasons.append("assurance_due")
        row: DomainDocument = {
            "hub_id": hub_id,
            "latest_assurance_run_id": run.get("run_id"),
            "latest_assurance_status": run.get("status") or "missing",
            "latest_assurance_verified": run.get("verification_status") == "passed",
            "last_verified_at": run.get("verified_at"),
            "next_due_at": next_due_at,
            "due_status": due_status,
            "drift_status": drift_status,
            "readiness": readiness,
            "reasons": reasons,
            "action_ids": [],
        }
        for action_type, severity, reason in _expected_actions_for_row(row):
            action_id = f"toaa-{len(actions) + 1:06d}"
            action = {
                "action_id": action_id,
                "queue_id": queue_id,
                "hub_id": hub_id,
                "action_type": action_type,
                "status": "pending",
                "severity": severity,
                "reason": reason,
                "manual_required": True,
                "safe_to_auto_run": False,
            }
            action["integrity_hash"] = watch_hash(action)
            actions.append(action)
            row["action_ids"].append(action_id)
        row["integrity_hash"] = watch_hash(row)
        rows.append(row)
    action_pack: DomainDocument = {
        "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
        "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE,
        "queue_id": queue_id,
        "actions": actions,
        "summary": _action_summary(actions),
        "source": {"external_verification_summary_hash": _external_summary_hash_for_queue(queue)},
    }
    action_pack["status"] = "blocked" if action_pack["summary"]["blocking_count"] else "warning" if action_pack["summary"]["action_count"] else "clear"
    action_pack["integrity_hash"] = watch_hash(action_pack)
    return sorted(rows, key=lambda row: str(row.get("hub_id") or "")), action_pack

def _external_summary_hash_for_queue(queue: DomainDocument) -> str | None:
    source = _as_document(queue.get("source"))
    return source.get("external_verification_summary_hash")

def _hub_ids_from_queue_or_run_index(queue: DomainDocument, run_index: DomainDocument) -> list[str]:
    ids = [str(row.get("hub_id") or "") for row in queue.get("rows", []) if isinstance(row, dict) and row.get("hub_id")]
    if not ids:
        ids = [str(row.get("hub_id") or "") for row in run_index.get("runs", []) if isinstance(row, dict) and row.get("hub_id")]
    return sorted(dict.fromkeys(item for item in ids if item)) or ["hub"]

def _row_projection(row: DomainDocument) -> DomainDocument:
    keys = [
        "hub_id",
        "latest_assurance_run_id",
        "latest_assurance_status",
        "latest_assurance_verified",
        "last_verified_at",
        "next_due_at",
        "due_status",
        "drift_status",
        "readiness",
        "reasons",
        "action_ids",
    ]
    return {key: row.get(key) for key in keys}

def _action_summary(actions: list[DomainDocument]) -> DomainDocument:
    return {
        "action_count": len(actions),
        "blocking_count": sum(1 for action in actions if action.get("severity") in {"critical", "high"}),
        "manual_required_count": sum(1 for action in actions if action.get("manual_required")),
        "safe_auto_count": sum(1 for action in actions if action.get("safe_to_auto_run")),
    }

def _due_status(last_at: str, now: str, interval_days: int, grace_days: int) -> tuple[str, str | None]:
    base = _parse_dt(last_at)
    current = _parse_dt(now)
    if not base or not current:
        return "unknown", None
    next_due = base + timedelta(days=max(0, interval_days))
    if current <= next_due:
        return "not_due", next_due.isoformat()
    if current <= next_due + timedelta(days=max(0, grace_days)):
        return "due", next_due.isoformat()
    return "overdue", next_due.isoformat()

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def _expected_actions_for_row(row: DomainDocument) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    due_status = row.get("due_status")
    if due_status == "missing":
        actions.append(("refresh_assurance", "high", "Assurance run is missing."))
    elif due_status == "overdue":
        actions.append(("refresh_assurance", "high", "Assurance run is overdue."))
    elif due_status == "due":
        actions.append(("refresh_assurance", "medium", "Assurance run is due."))
    if "assurance_verification_not_passed" in row.get("reasons", []):
        actions.append(("verify_assurance_archive", "high", "Assurance archive verification is missing or failed."))
    if "assurance_run_failed" in row.get("reasons", []):
        actions.append(("manual_delivery_review_required", "high", "Assurance run failed and requires manual review."))
    return actions

def _external_item(summary: DomainDocument, component_type: str) -> DomainDocument:
    for item in summary.get("items", []) if isinstance(summary.get("items"), list) else []:
        if isinstance(item, dict) and item.get("component_type") == component_type:
            return item
    return {}

def _read_json_file(path: Path | None) -> DomainDocument:
    if not path:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return _as_document(value)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}

def _read_zip_json(zip_path: Path | None, entry: str) -> DomainDocument:
    if not zip_path:
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}

def _sha256_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or lower.endswith(".zip")

def _safe_check_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower() or "item"

def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    return False

def _fs_path(path: Path) -> str:
    return str(path)
