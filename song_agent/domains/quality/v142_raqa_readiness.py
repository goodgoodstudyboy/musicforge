# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.lifecycle import HistoryChain
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore as ReleaseAudioQualityObservatoryStore
from song_agent.domains.quality.release_audio_quality_observatory_verifier import RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_observatory_package as verify_release_audio_quality_observatory_package, write_release_audio_quality_observatory_verification_report as write_release_audio_quality_observatory_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.release_audio_quality_action_semantics import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE, RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, ReleaseAudioQualityActionQueueError as ReleaseAudioQualityActionQueueError, ReleaseAudioQualityActionQueueValidationError as ReleaseAudioQualityActionQueueValidationError, _action_items_from_binding as _action_items_from_binding, _action_selection as _action_selection, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _read_json_entry as _read_json_entry, _recommendation_action as _recommendation_action, _risk_action as _risk_action, _selection_from_documents as _selection_from_documents, _sha256_path as _sha256_path, _source_binding_from_external as _source_binding_from_external, _with_action_selection as _with_action_selection, build_expected_action_documents_from_observatory as build_expected_action_documents_from_observatory

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
result = _make_deferred_global('result')
row = _make_deferred_global('row')
val = _make_deferred_global('val')

def bind_globals(namespace: dict[str, object]) -> None:
    global key, result, row, val
    key = namespace.get('key', key)
    result = namespace.get('result', result)
    row = namespace.get('row', row)
    val = namespace.get('val', val)
    _bind_deferred_defaults(namespace)






class ReleaseAudioQualityActionQueueNotFoundError(ReleaseAudioQualityActionQueueError):
    pass

class ReleaseAudioQualityActionQueueStateError(ReleaseAudioQualityActionQueueError):
    pass

def _execute_item(item: DomainDocument) -> DomainDocument:
    started = now_iso()
    item_id = str(item.get("item_id") or "")
    action_type = str(item.get("action_type") or "")
    execution_mode = str(item.get("execution_mode") or "")
    if execution_mode == "manual_required" or bool(item.get("requires_manual")):
        return {"item_id": item_id, "status": "manual_required", "action_type": action_type, "started_at": started, "finished_at": now_iso(), "result": {"manual_required": True}, "error": None}
    safe_actions = {"refresh_observatory", "verify_observatory", "create_audio_quality_review_task", "create_audio_fix_sprint_draft", "create_regression_response_plan_draft"}
    if action_type not in safe_actions or execution_mode != "safe":
        return {"item_id": item_id, "status": "blocked", "action_type": action_type, "started_at": started, "finished_at": now_iso(), "result": {}, "error": "Action is not safe for automatic execution."}
    created_type = {
        "refresh_observatory": "observatory_refresh_request",
        "verify_observatory": "observatory_verification_request",
        "create_audio_quality_review_task": "review_task_draft",
        "create_audio_fix_sprint_draft": "audio_fix_sprint_draft",
        "create_regression_response_plan_draft": "regression_response_plan_draft",
    }.get(action_type, "safe_action_result")
    created_id = f"{created_type}-{item_id}"
    return {"item_id": item_id, "status": "completed", "action_type": action_type, "started_at": started, "finished_at": now_iso(), "result": {"created_object_type": created_type, "created_object_id": created_id, "manual_required": action_type.startswith("create_")}, "error": None}

def _manual_action_from_item(item: DomainDocument, index: int) -> DomainDocument:
    return sanitize_metadata(
        {
            "manual_action_id": f"aqman-{index:06d}",
            "item_id": item.get("item_id"),
            "action_type": item.get("action_type"),
            "reason": item.get("inputs", {}).get("reason") if isinstance(item.get("inputs"), dict) else "Manual action required.",
            "target": item.get("target", {}),
            "status": "manual_required",
        }
    )

def _build_summary(queue: DomainDocument, source_binding: DomainDocument, items: DomainDocument, results: DomainDocument, manual_actions: DomainDocument, *, stale_reasons: list[str]) -> DomainDocument:
    item_rows = [row for row in items.get("items", []) if isinstance(row, dict)]
    result_rows = [row for row in results.get("results", []) if isinstance(row, dict)]
    manual_rows = [row for row in manual_actions.get("manual_actions", []) if isinstance(row, dict)]
    completed = sum(1 for row in result_rows if row.get("status") == "completed")
    failed = sum(1 for row in result_rows if row.get("status") == "failed")
    blocked = sum(1 for row in result_rows if row.get("status") == "blocked")
    manual_required_ids = {str(row.get("item_id")) for row in manual_rows if row.get("item_id")}
    manual_required_ids.update(str(row.get("item_id")) for row in result_rows if row.get("status") == "manual_required" and row.get("item_id"))
    manual_required = len(manual_required_ids)
    pending = max(0, len(item_rows) - len(result_rows))
    critical_unhandled = sum(1 for row in item_rows if row.get("severity") in {"critical", "blocking"} and row.get("item_id") not in {result.get("item_id") for result in result_rows if result.get("status") in {"completed", "manual_required"}})
    if stale_reasons:
        status = "stale"
        readiness = "blocked"
    elif failed or blocked:
        status = "failed"
        readiness = "blocked"
    elif pending:
        status = "pending"
        readiness = "pending"
    elif manual_required:
        status = "completed_with_manual_actions"
        readiness = "manual_actions_required"
    else:
        status = "completed"
        readiness = "ready"
    summary = sanitize_metadata(
        {
            "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
            "package_type": "release_audio_quality_action_queue_summary",
            "queue_id": queue.get("queue_id"),
            "status": status,
            "source_hash": source_binding.get("source_hash"),
            "readiness": readiness,
            "stale_reasons": stale_reasons,
            "summary": {
                "item_count": len(item_rows),
                "completed_count": completed,
                "manual_required_count": manual_required,
                "blocked_count": blocked,
                "failed_count": failed,
                "pending_count": pending,
                "critical_source_risk_count": _safe_int((source_binding.get("risk_register") or {}).get("summary", {}).get("critical_risk_count") if isinstance(source_binding.get("risk_register"), dict) else 0),
                "critical_unhandled_count": critical_unhandled,
                "release_ids": (source_binding.get("observatory") or {}).get("release_ids") or [],
            },
            "document_hashes": {
                "action_queue": queue.get("integrity_hash"),
                "source_binding": source_binding.get("integrity_hash"),
                "action_items": items.get("integrity_hash"),
                "action_results": results.get("integrity_hash"),
                "manual_actions": manual_actions.get("integrity_hash"),
            },
            "created_at": now_iso(),
        }
    )
    summary["integrity_hash"] = _integrity_hash(summary)
    return summary

def _validate_queue_id(value: str) -> str:
    if not re.fullmatch(r"aqa-\d{6}", str(value or "")):
        raise ReleaseAudioQualityActionQueueValidationError(f"Invalid queue_id: {value}.")
    return str(value)

def _validate_observatory_id(value: str) -> str:
    if not re.fullmatch(r"aqo-\d{6}", str(value or "")):
        raise ReleaseAudioQualityActionQueueValidationError(f"Invalid observatory_id: {value}.")
    return str(value)

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _semantic_hash(value: object) -> str:
    def scrub(item: object) -> object:
        if isinstance(item, dict):
            return {key: scrub(val) for key, val in sorted(item.items()) if key not in {"created_at", "updated_at", "generated_at", "integrity_hash"}}
        if isinstance(item, list):
            return [scrub(val) for val in item]
        return item

    return stable_hash(scrub(value))

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _read_jsonl(path: Path) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows

def _history_chain_ok(history: list[DomainDocument]) -> bool:
    previous: str | None = None
    for event in history:
        payload = _as_document(event.get("payload"))
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)

def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def _readme(queue: DomainDocument, summary: DomainDocument) -> str:
    data = _as_document(summary.get("summary"))
    return "\n".join(
        [
            "MusicForge Release Audio Quality Action Queue",
            f"queue_id: {queue.get('queue_id')}",
            f"status: {summary.get('status')}",
            f"item_count: {data.get('item_count')}",
            f"manual_required_count: {data.get('manual_required_count')}",
            "",
            "This package records safe and manual governance actions derived from Release Audio Quality Observatory evidence.",
            "It does not modify music, signoffs, baselines, or provider state.",
            "",
        ]
    )
