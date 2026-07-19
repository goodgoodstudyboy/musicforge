# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_sprints import ReviewSprint as ReviewSprint
from song_agent.domains.quality.review_tasks import validate_review_task_id as validate_review_task_id

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

SprintActionItem = _make_deferred_global('SprintActionItem')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
status = _make_deferred_global('status')

def bind_globals(namespace: dict[str, object]) -> None:
    global SprintActionItem, _LOCKS_GUARD, status
    SprintActionItem = namespace.get('SprintActionItem', SprintActionItem)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    status = namespace.get('status', status)
    _bind_deferred_defaults(namespace)


ACTION_QUEUE_SCHEMA_VERSION = 1
ACTION_QUEUE_STATUSES = {"pending", "running", "completed", "completed_with_warnings", "failed", "blocked", "archived"}
ACTION_ITEM_STATUSES = {"pending", "running", "completed", "failed", "skipped", "blocked", "manual_required", "interrupted"}
ACTION_SAFETY = {"auto_safe", "provider_safe", "manual_required", "blocked", "informational"}
ACTION_TYPES = {
    "refresh_recommendations",
    "refresh_conflicts",
    "save_recommended_context_pack",
    "generate_local_candidates",
    "generate_provider_candidates",
    "refresh_judge_report",
    "refresh_decision_report",
    "inspect_conflict",
    "manual_apply_candidate",
    "manual_resolve_task",
    "manual_add_follow_up",
    "skip_stale_task",
    "skip_archived_task",
    "no_action",
}
RECOMMENDATION_ACTION_MAP = {
    "inspect_conflict": "inspect_conflict",
    "generate_local": "generate_local_candidates",
    "generate_provider": "generate_provider_candidates",
    "refresh_decision_report": "refresh_decision_report",
    "apply_ready_candidate": "manual_apply_candidate",
    "resolve": "manual_resolve_task",
    "add_follow_up": "manual_add_follow_up",
    "skip_stale": "skip_stale_task",
    "skip_archived": "skip_archived_task",
    "no_action": "no_action",
}
_QUEUE_STORE_LOCKS: dict[str, threading.RLock] = {}




def _queue_settings(data: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "stop_on_failure": bool(data.get("stop_on_failure", False)),
            "run_provider_actions": bool(data.get("run_provider_actions", False)),
            "run_context_pack_actions": bool(data.get("run_context_pack_actions", True)),
            "run_local_actions": bool(data.get("run_local_actions", True)),
            "include_judge_actions": bool(data.get("include_judge_actions", True)),
            "max_provider_actions": _clamp_int(data.get("max_provider_actions"), 0, 20, 3),
            "max_concurrency": 1,
        }
    )

def _queue_summary(items: list[SprintActionItem]) -> dict[str, int]:
    summary = {status: 0 for status in ACTION_ITEM_STATUSES}
    for item in items:
        summary[item.status] = summary.get(item.status, 0) + 1
    summary["total"] = len(items)
    return {key: int(value) for key, value in summary.items()}

def _queue_status(items: list[SprintActionItem], *, requested: str = "pending") -> str:
    if requested == "archived":
        return "archived"
    if any(item.status == "running" for item in items):
        return "running"
    if any(item.status == "failed" for item in items):
        return "failed"
    executable = [item for item in items if item.safety in {"auto_safe", "provider_safe"}]
    if executable and all(item.status in {"completed", "skipped", "blocked"} for item in executable):
        return "completed_with_warnings" if any(item.status in {"blocked", "manual_required"} for item in items) else "completed"
    if all(item.status in {"blocked", "manual_required", "skipped"} for item in items):
        return "blocked" if any(item.status == "blocked" for item in items) else "completed_with_warnings"
    return requested if requested in ACTION_QUEUE_STATUSES else "pending"

def _with_item_id(item: SprintActionItem, item_id: str) -> SprintActionItem:
    return SprintActionItem.from_dict({**item.to_dict(), "item_id": item_id})

def _item_sort_key(item: SprintActionItem) -> tuple[int, int, int, str]:
    action_order = {
        "refresh_conflicts": 0,
        "refresh_recommendations": 1,
        "save_recommended_context_pack": 2,
        "generate_local_candidates": 3,
        "generate_provider_candidates": 4,
        "refresh_judge_report": 5,
        "refresh_decision_report": 6,
    }.get(item.action, 9)
    return (action_order, item.rank or 9999, -int(item.priority or 0), item.task_id or item.action)

def _context_ref_count(preview: object) -> int:
    if not isinstance(preview, dict):
        return 0
    return len(preview.get("asset_refs") or []) + len(preview.get("reference_refs") or [])

def _optional_task_id(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    return validate_review_task_id(str(value))

def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(high, parsed))

def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        lock = _QUEUE_STORE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _QUEUE_STORE_LOCKS[key] = lock
        return lock
