# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore, validate_review_task_id as validate_review_task_id

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

ReviewSprint = _make_deferred_global('ReviewSprint')
ReviewSprintError = _make_deferred_global('ReviewSprintError')
ReviewSprintStateError = _make_deferred_global('ReviewSprintStateError')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
candidate = _make_deferred_global('candidate')
status = _make_deferred_global('status')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReviewSprint, ReviewSprintError, ReviewSprintStateError, _LOCKS_GUARD, candidate, status
    ReviewSprint = namespace.get('ReviewSprint', ReviewSprint)
    ReviewSprintError = namespace.get('ReviewSprintError', ReviewSprintError)
    ReviewSprintStateError = namespace.get('ReviewSprintStateError', ReviewSprintStateError)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    candidate = namespace.get('candidate', candidate)
    status = namespace.get('status', status)
    _bind_deferred_defaults(namespace)


REVIEW_SPRINT_SCHEMA_VERSION = 1
REVIEW_SPRINT_SUMMARY_SCHEMA_VERSION = 1
REVIEW_SPRINT_CONFLICT_SCHEMA_VERSION = 1
REVIEW_SPRINT_RECOMMENDATION_SCHEMA_VERSION = 1
SPRINT_STATUSES = {"open", "in_progress", "blocked", "closed", "archived"}
MUTABLE_SPRINT_STATUSES = {"open", "in_progress", "blocked"}
LOCAL_STRATEGIES = {"conservative", "balanced", "bold"}
_STORE_LOCKS: dict[str, threading.RLock] = {}




def review_sprint_export_summary(
    sprint: ReviewSprint,
    summary: DomainDocument | None = None,
    conflict_report: DomainDocument | None = None,
    recommendation_report: DomainDocument | None = None,
    action_queue_summary: DomainDocument | None = None,
    judge_summary: DomainDocument | None = None,
    closeout_summary: DomainDocument | None = None,
    signoff_summary: DomainDocument | None = None,
) -> DomainDocument:
    summary = _as_document(summary)
    conflict_report = _as_document(conflict_report)
    action_queue_summary = _as_document(action_queue_summary)
    judge_summary = _as_document(judge_summary)
    closeout_summary = _as_document(closeout_summary)
    signoff_summary = _as_document(signoff_summary)
    recommendation_summary = _recommendation_summary_for_export(recommendation_report)
    counts = _document_or(summary.get("counts"), sprint.counts)
    return sanitize_metadata(
        {
            "sprint_id": sprint.sprint_id,
            "name": sprint.name,
            "status": sprint.status,
            "parent_version_id": sprint.parent_version_id,
            "task_count": len([ref for ref in sprint.task_refs if ref.get("included", True)]),
            "summary": summary,
            "conflict_count": len(conflict_report.get("conflicts", [])) if isinstance(conflict_report.get("conflicts"), list) else int(counts.get("conflict_count") or 0),
            "recommendation_summary": recommendation_summary,
            "action_queue_summary": action_queue_summary,
            "judge_summary": _judge_summary_for_export(judge_summary),
            "closeout_summary": closeout_summary,
            "signoff_summary": signoff_summary,
            "task_ids": [str(ref.get("task_id")) for ref in sorted(sprint.task_refs, key=lambda ref: int(ref.get("order") or 0)) if ref.get("included", True)],
        }
    )

def review_sprint_project_rollup(sprints: list[DomainDocument]) -> DomainDocument:
    latest = sprints[0] if sprints else {}
    closed = [sprint for sprint in sprints if sprint.get("status") == "closed"]
    counts = [sprint.get("summary", {}).get("counts", {}) for sprint in sprints if isinstance(sprint.get("summary"), dict)]
    recommendation_summaries = [sprint.get("recommendation_summary", {}) for sprint in sprints if isinstance(sprint.get("recommendation_summary"), dict)]
    action_queue_summaries = [sprint.get("action_queue_summary", {}) for sprint in sprints if isinstance(sprint.get("action_queue_summary"), dict)]
    judge_summaries = [sprint.get("judge_summary", {}) for sprint in sprints if isinstance(sprint.get("judge_summary"), dict)]
    closeout_summaries = [sprint.get("closeout_summary", {}) for sprint in sprints if isinstance(sprint.get("closeout_summary"), dict)]
    signoff_summaries = [sprint.get("signoff_summary", {}) for sprint in sprints if isinstance(sprint.get("signoff_summary"), dict)]
    return sanitize_metadata(
        {
            "latest_sprint_id": latest.get("sprint_id"),
            "closed_sprint_count": len(closed),
            "resolved_task_count": sum(int(count.get("resolved") or 0) for count in counts),
            "open_task_count": sum(int(count.get("open") or 0) for count in counts),
            "conflict_count": sum(int(count.get("conflict_count") or 0) for count in counts),
            "recommendation_count": sum(int(item.get("open_recommendation_count") or 0) for item in recommendation_summaries),
            "context_recommendation_count": sum(int(item.get("context_recommendation_count") or 0) for item in recommendation_summaries),
            "next_action": (recommendation_summaries[0].get("next_action") if recommendation_summaries else None),
            "action_queue_count": sum(int(item.get("queue_count") or 0) for item in action_queue_summaries),
            "completed_action_count": sum(int(item.get("completed_action_count") or 0) for item in action_queue_summaries),
            "failed_action_count": sum(int(item.get("failed_action_count") or 0) for item in action_queue_summaries),
            "manual_required_action_count": sum(int(item.get("manual_required_count") or 0) for item in action_queue_summaries),
            "judged_task_count": sum(int(item.get("judged_task_count") or 0) for item in judge_summaries),
            "stale_judge_count": sum(int(item.get("stale_judge_count") or 0) for item in judge_summaries),
            "judge_provider_tokens": sum(int(item.get("judge_provider_tokens") or 0) for item in judge_summaries),
            "closeout_report_count": len([item for item in closeout_summaries if item]),
            "signed_sprint_count": len([item for item in signoff_summaries if item.get("status") == "signed"]),
            "forced_close_count": len([item for item in closeout_summaries if item.get("forced")]) + len([item for item in signoff_summaries if item.get("forced")]),
            "open_blocker_count": sum(int(item.get("blocker_count") or 0) for item in closeout_summaries if item.get("status") not in {"passed", "warning"}),
            "latest_closeout_status": (closeout_summaries[0].get("status") if closeout_summaries else None),
            "latest_closeout_readiness": (closeout_summaries[0].get("readiness") if closeout_summaries else None),
        }
    )

def _recommendation_summary_for_export(report: DomainDocument | None) -> DomainDocument:
    if not isinstance(report, dict) or not report:
        return {}
    actions = [item for item in report.get("recommended_actions", []) if isinstance(item, dict)]
    sprint_level = _as_document(report.get("sprint_level_recommendation"))
    top = actions[0] if actions else {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "created_at": report.get("created_at"),
            "recommended_order": [str(item) for item in report.get("recommended_order", []) if str(item).strip()][:20] if isinstance(report.get("recommended_order"), list) else [],
            "next_action": sprint_level.get("next_action"),
            "ready_to_close": bool(sprint_level.get("ready_to_close", False)),
            "open_recommendation_count": len([item for item in actions if item.get("action") not in {"no_action", "skip_archived"}]),
            "context_recommendation_count": int((report.get("source_summary") or {}).get("context_recommendation_count") or 0) if isinstance(report.get("source_summary"), dict) else 0,
            "top_recommendation": {
                "task_id": top.get("task_id"),
                "rank": top.get("rank"),
                "action": top.get("action"),
                "score": top.get("score"),
            },
        }
    )

def _judge_summary_for_export(summary: DomainDocument | None) -> DomainDocument:
    if not isinstance(summary, dict) or not summary:
        return {}
    return sanitize_metadata(
        {
            "schema_version": summary.get("schema_version"),
            "sprint_id": summary.get("sprint_id"),
            "created_at": summary.get("created_at"),
            "judged_task_count": summary.get("judged_task_count", 0),
            "stale_judge_count": summary.get("stale_judge_count", 0),
            "recommended_candidate_count": summary.get("recommended_candidate_count", 0),
            "judge_provider_tokens": summary.get("judge_provider_tokens", 0),
            "high_risk_candidate_count": summary.get("high_risk_candidate_count", 0),
            "risk_flags": _as_list(summary.get("risk_flags")),
        }
    )

def _settings_from_dict(data: DomainDocument) -> DomainDocument:
    strategies = data.get("local_candidate_strategies")
    if isinstance(strategies, list):
        clean_strategies = [str(item).strip() for item in strategies if str(item).strip() in LOCAL_STRATEGIES]
    else:
        clean_strategies = ["balanced"]
    count = _clamp_int(data.get("provider_candidate_count"), 2, 5, 2)
    return sanitize_metadata(
        {
            "local_candidate_strategies": clean_strategies or ["balanced"],
            "provider_candidate_count": count,
            "provider_template_id": str(data.get("provider_template_id") or "provider-review-candidates")[:120],
            "generate_provider": bool(data.get("generate_provider", False)),
            "render_midi": bool(data.get("render_midi", True)),
            "stop_on_conflict": bool(data.get("stop_on_conflict", False)),
            "require_same_parent": bool(data.get("require_same_parent", True)),
        }
    )

def _task_ref_from_dict(data: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "task_id": validate_review_task_id(str(data.get("task_id") or "")),
            "order": max(1, int(data.get("order") or 1)),
            "priority": _clamp_int(data.get("priority"), 0, 100, 50),
            "lane": sanitize_sensitive_text(str(data.get("lane") or ""))[:80],
            "included": bool(data.get("included", True)),
            "notes": sanitize_sensitive_text(str(data.get("notes") or ""))[:500],
            "added_at": str(data.get("added_at") or ""),
        }
    )

def _task_ref(task: ReviewTask, order: int, *, lane: str, notes: str, now: str) -> DomainDocument:
    return _task_ref_from_dict({"task_id": task.task_id, "order": order, "priority": task.priority, "lane": lane, "included": True, "notes": notes, "added_at": now})

def _renumber_ref(ref: DomainDocument, order: int) -> DomainDocument:
    return _task_ref_from_dict({**ref, "order": order})

def _task_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        task_id = validate_review_task_id(str(item))
        if task_id in result:
            raise ReviewSprintError(f"Duplicate task id: {task_id}.")
        result.append(task_id)
    return result

def _read_project_tasks(task_store: ReviewTaskStore, project_id: str, task_ids: list[str]) -> list[ReviewTask]:
    tasks = []
    for task_id in task_ids:
        task = task_store.read_task(task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(task_id)
        tasks.append(task)
    return tasks

def _included_tasks(sprint: ReviewSprint, task_store: ReviewTaskStore, *, missing_ok: bool = False) -> list[ReviewTask]:
    tasks = []
    for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
        if not ref.get("included", True):
            continue
        try:
            task = task_store.read_task(str(ref.get("task_id") or ""))
        except FileNotFoundError:
            if missing_ok:
                continue
            raise
        if task.project_id == sprint.project_id:
            tasks.append(task)
    return tasks

def _summary_counts(tasks: list[ReviewTask], task_store: ReviewTaskStore) -> dict[str, int]:
    counts = {status: 0 for status in ("open", "candidate_ready", "applied", "resolved", "needs_more_work", "stale", "archived")}
    counts.update({"ready_candidate_count": 0, "local_candidate_count": 0, "provider_candidate_count": 0, "failed_candidate_count": 0, "conflict_count": 0, "blocking_conflict_count": 0})
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
        try:
            candidates = task_store.list_candidates(task.task_id)
        except FileNotFoundError:
            candidates = []
        counts["ready_candidate_count"] += len([candidate for candidate in candidates if candidate.status in {"ready", "applied"}])
        counts["local_candidate_count"] += len([candidate for candidate in candidates if candidate.candidate_type == "local_review_intents"])
        counts["provider_candidate_count"] += len([candidate for candidate in candidates if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")])
        counts["failed_candidate_count"] += len([candidate for candidate in candidates if candidate.status == "failed"])
    return counts

def _sprint_has_progress(tasks: list[ReviewTask], task_store: ReviewTaskStore) -> bool:
    return any(task.status != "open" or task_store.list_candidates(task.task_id) for task in tasks)

def _task_conflicts(sprint: ReviewSprint, task: ReviewTask, task_ids: set[str], task_store: ReviewTaskStore, parent_plan_hashes: dict[str, str]) -> list[DomainDocument]:
    conflicts: list[DomainDocument] = []
    if sprint.settings.get("require_same_parent", True) and sprint.parent_version_id and task.parent_version_id != sprint.parent_version_id:
        conflicts.append(_conflict("blocking", "parent_mismatch", [task.task_id], f"Task parent {task.parent_version_id} differs from sprint parent {sprint.parent_version_id}."))
    current_hash = parent_plan_hashes.get(task.parent_version_id)
    if task.status == "stale" or (current_hash and task.hashes.get("parent_plan_hash") and task.hashes.get("parent_plan_hash") != current_hash):
        conflicts.append(_conflict("blocking", "stale_task", [task.task_id], "ReviewTask is stale and must be refreshed outside the sprint."))
    if task.status == "archived":
        conflicts.append(_conflict("blocking", "archived_task", [task.task_id], "Archived ReviewTask cannot participate in sprint generation."))
    if task.status in {"applied", "resolved"}:
        conflicts.append(_conflict("info", f"task_{task.status}", [task.task_id], f"ReviewTask is already {task.status}."))
    if task.status == "needs_more_work" and task.follow_up_task_id and task.follow_up_task_id not in task_ids:
        conflicts.append(_conflict("warning", "missing_follow_up", [task.task_id], "Task needs more work but its follow-up task is not in this sprint."))
    candidates = task_store.list_candidates(task.task_id)
    if task.status == "candidate_ready":
        try:
            task_store.read_decision_report(task.task_id)
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            conflicts.append(_conflict("info", "missing_decision_report", [task.task_id], "Task has ready candidates but no Decision Report."))
    if candidates and not any(candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider") for candidate in candidates):
        conflicts.append(_conflict("info", "no_provider_candidates", [task.task_id], "Task only has local candidates."))
    return conflicts

def _pair_conflicts(left: ReviewTask, right: ReviewTask) -> list[DomainDocument]:
    if left.status not in {"open", "candidate_ready"} or right.status not in {"open", "candidate_ready"}:
        return []
    conflicts: list[DomainDocument] = []
    left_section = str(left.target.get("section_name") or "")
    right_section = str(right.target.get("section_name") or "")
    left_track = str(left.target.get("track_name") or "")
    right_track = str(right.target.get("track_name") or "")
    left_role = str(left.target.get("role") or "")
    right_role = str(right.target.get("role") or "")
    if left_section and left_section == right_section and left_track and left_track == right_track:
        conflicts.append(_conflict("warning", "same_section_track", [left.task_id, right.task_id], f"Two tasks target {left_section} / {left_track}. Apply one and refresh the other before continuing.", section_name=left_section, track_name=left_track))
    elif left_section and left_section == right_section:
        conflicts.append(_conflict("warning", "same_section", [left.task_id, right.task_id], f"Two tasks target section {left_section}.", section_name=left_section))
    if left_track and left_track == right_track and not (left_section and left_section == right_section):
        conflicts.append(_conflict("warning", "same_track", [left.task_id, right.task_id], f"Two tasks target track {left_track}.", track_name=left_track))
    if left_section and left_section == right_section and left_role and left_role == right_role:
        conflicts.append(_conflict("warning", "same_section_role", [left.task_id, right.task_id], f"Two tasks target {left_section} with role {left_role}.", section_name=left_section, role=left_role))
    left_beat = _float_or_none(left.target.get("global_marker_beat"))
    right_beat = _float_or_none(right.target.get("global_marker_beat"))
    if left_beat is not None and right_beat is not None and abs(left_beat - right_beat) < 4:
        conflicts.append(_conflict("warning", "nearby_markers", [left.task_id, right.task_id], "Two task markers are less than 4 beats apart.", marker_distance_beats=round(abs(left_beat - right_beat), 3)))
    return conflicts

def _conflict(severity: str, kind: str, task_ids: list[str], message: str, **extra: object) -> DomainDocument:
    return sanitize_metadata({"severity": severity, "kind": kind, "task_ids": task_ids, "message": message, **extra})

def _with_conflict_id(conflict: DomainDocument, index: int) -> DomainDocument:
    return {"conflict_id": f"conflict-{index:03d}", **conflict}

def _ref_order(sprint: ReviewSprint, task_id: str) -> int:
    for ref in sprint.task_refs:
        if ref.get("task_id") == task_id:
            return int(ref.get("order") or 9999)
    return 9999

def _ensure_sprint_mutable(sprint: ReviewSprint) -> None:
    if sprint.status not in MUTABLE_SPRINT_STATUSES:
        raise ReviewSprintStateError(f"Cannot modify a {sprint.status} review sprint.")

def _optional_str(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return sanitize_sensitive_text(str(value))[:160]

def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default

def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _lock_for_project(project_dir: Path) -> threading.RLock:
    key = str(project_dir.resolve())
    with _LOCKS_GUARD:
        if key not in _STORE_LOCKS:
            _STORE_LOCKS[key] = threading.RLock()
        return _STORE_LOCKS[key]

def _append_event(root: Path, event_type: str, payload: DomainDocument, now: str) -> None:
    event_path = root / "events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"timestamp": now, "event": event_type, **sanitize_metadata(payload)}, ensure_ascii=False) + "\n")
