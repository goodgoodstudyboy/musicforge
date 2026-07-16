from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
from typing import Any as Any

from song_agent.domains.studio.library_index import LibraryIndex as LibraryIndex, recommend_library_context as recommend_library_context
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_sprints import ReviewSprint as ReviewSprint, ReviewSprintStore as ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate as ReviewCandidate, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore, review_candidate_source_breakdown as review_candidate_source_breakdown


REVIEW_SPRINT_RECOMMENDATION_SCHEMA_VERSION = 1
RECOMMENDED_ACTIONS = {
    "inspect_conflict",
    "generate_local",
    "generate_provider",
    "refresh_decision_report",
    "apply_ready_candidate",
    "resolve",
    "add_follow_up",
    "skip_stale",
    "skip_archived",
    "no_action",
}


def build_review_sprint_recommendation_report(
    *,
    project_id: str,
    sprint: ReviewSprint,
    task_store: ReviewTaskStore,
    sprint_store: ReviewSprintStore,
    library_index: LibraryIndex | None = None,
    project_document: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
    task_ids = _included_task_ids(sprint)
    actions = []
    for task_id in task_ids:
        task = task_store.read_task(task_id)
        candidates = task_store.list_candidates(task.task_id)
        decision_report = _try_read_decision_report(task_store, task.task_id)
        conflicts = _task_conflicts(conflict_report, task.task_id)
        context = _context_pack_preview(
            project_id=project_id,
            sprint=sprint,
            task=task,
            library_index=library_index,
            project_document=project_document,
        )
        action = recommend_review_sprint_task_action(
            task=task,
            candidates=candidates,
            decision_report=decision_report,
            conflicts=conflicts,
            context_pack_preview=context,
            ref_order=_ref_order(sprint, task.task_id),
        )
        actions.append(action)
    actions = sorted(actions, key=lambda item: (_order_bucket(item), -int(item.get("score") or 0), -int(item.get("priority") or 0), int(item.get("sprint_order") or 9999), str(item.get("task_id") or "")))
    ranked_actions = []
    for index, action in enumerate(actions, start=1):
        ranked_actions.append({**action, "rank": index})
    recommended_order = [item["task_id"] for item in ranked_actions if item.get("action") not in {"skip_stale", "skip_archived", "no_action"}]
    report = {
        "schema_version": REVIEW_SPRINT_RECOMMENDATION_SCHEMA_VERSION,
        "project_id": project_id,
        "sprint_id": sprint.sprint_id,
        "created_at": now,
        "parent_version_id": sprint.parent_version_id,
        "recommended_order": recommended_order,
        "recommended_actions": ranked_actions,
        "sprint_level_recommendation": _sprint_level_recommendation(ranked_actions, conflict_report),
        "source_summary": {
            "task_count": len(task_ids),
            "conflict_count": len(conflict_report.get("conflicts", [])) if isinstance(conflict_report.get("conflicts"), list) else 0,
            "context_recommendation_count": len([item for item in ranked_actions if _context_ref_count(item.get("context_pack_preview")) > 0]),
        },
    }
    return sanitize_metadata(report)


def recommend_review_sprint_task_action(
    *,
    task: ReviewTask,
    candidates: list[ReviewCandidate],
    decision_report: dict[str, Any] | None,
    conflicts: list[dict[str, Any]],
    context_pack_preview: dict[str, Any] | None = None,
    ref_order: int = 9999,
) -> dict[str, Any]:
    conflict_summary = _conflict_summary(conflicts)
    provider_summary = review_candidate_source_breakdown(candidates)
    ready = [candidate for candidate in candidates if candidate.status in {"ready", "applied"}]
    local_ready = [candidate for candidate in ready if candidate.candidate_type == "local_review_intents"]
    provider_ready = [candidate for candidate in ready if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")]
    has_decision = bool(decision_report and decision_report.get("recommended_candidate_id"))
    action = _recommended_action(
        task=task,
        ready=ready,
        local_ready=local_ready,
        provider_ready=provider_ready,
        has_decision=has_decision,
        conflict_summary=conflict_summary,
    )
    score_breakdown = _score_breakdown(
        task=task,
        ready=ready,
        local_ready=local_ready,
        provider_ready=provider_ready,
        has_decision=has_decision,
        conflict_summary=conflict_summary,
    )
    score = _clamp(sum(score_breakdown.values()), 0, 100)
    reason = _action_reason(action, task, conflict_summary, provider_summary, has_decision)
    warnings = _action_warnings(task, conflict_summary, decision_report)
    return sanitize_metadata(
        {
            "task_id": task.task_id,
            "rank": 0,
            "sprint_order": ref_order,
            "priority": task.priority,
            "status": task.status,
            "action": action,
            "score": score,
            "reason": reason,
            "score_breakdown": score_breakdown,
            "target": {
                "section_name": task.target.get("section_name"),
                "track_name": task.target.get("track_name"),
                "role": task.target.get("role"),
                "global_marker_beat": task.target.get("global_marker_beat"),
            },
            "candidate_summary": {
                "ready_candidate_count": len(ready),
                "local_ready_candidate_count": len(local_ready),
                "provider_ready_candidate_count": len(provider_ready),
                "recommended_candidate_id": decision_report.get("recommended_candidate_id") if isinstance(decision_report, dict) else None,
                "provider_summary": provider_summary,
            },
            "conflicts": [_conflict_public(conflict) for conflict in conflicts],
            "context_pack_preview": context_pack_preview if isinstance(context_pack_preview, dict) else {},
            "warnings": warnings,
        }
    )


def review_task_context_recommendation_query(
    *,
    project_id: str,
    sprint: ReviewSprint,
    task: ReviewTask,
    project_document: Any | None = None,
) -> dict[str, Any]:
    request = _song_request_for_task(project_document, task)
    target = task.target if isinstance(task.target, dict) else {}
    role = str(target.get("role") or target.get("track_name") or "")
    candidate_goal = " ".join(
        item
        for item in (
            task.title,
            task.summary,
            str(target.get("section_name") or ""),
            str(target.get("track_name") or ""),
            role,
            "arrangement reference context",
        )
        if item
    )
    return sanitize_metadata(
        {
            "source": "review_sprint_task",
            "goal": "review_task_candidate_generation",
            "project_id": project_id,
            "sprint_id": sprint.sprint_id,
            "task_id": task.task_id,
            "review_task": {
                "title": task.title,
                "summary": task.summary,
                "target": {
                    "section_name": target.get("section_name"),
                    "track_name": target.get("track_name"),
                    "role": role,
                },
                "priority": task.priority,
            },
            "song_request": request,
            "candidate_goal": candidate_goal,
            "style": request.get("style") or "",
            "mood": request.get("mood") or "",
        }
    )


def recommendation_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    actions = [item for item in report.get("recommended_actions", []) if isinstance(item, dict)]
    sprint_level = report.get("sprint_level_recommendation") if isinstance(report.get("sprint_level_recommendation"), dict) else {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "sprint_id": report.get("sprint_id"),
            "created_at": report.get("created_at"),
            "recommended_order": [str(item) for item in report.get("recommended_order", []) if str(item).strip()][:20] if isinstance(report.get("recommended_order"), list) else [],
            "next_action": sprint_level.get("next_action"),
            "ready_to_close": bool(sprint_level.get("ready_to_close", False)),
            "blocking_conflict_count": int(sprint_level.get("blocking_conflict_count") or 0),
            "open_recommendation_count": len([item for item in actions if item.get("action") not in {"no_action", "skip_archived"}]),
            "context_recommendation_count": int((report.get("source_summary") or {}).get("context_recommendation_count") or 0) if isinstance(report.get("source_summary"), dict) else 0,
            "top_recommendation": _top_recommendation_summary(actions[0]) if actions else {},
        }
    )


def _recommended_action(
    *,
    task: ReviewTask,
    ready: list[ReviewCandidate],
    local_ready: list[ReviewCandidate],
    provider_ready: list[ReviewCandidate],
    has_decision: bool,
    conflict_summary: ImplementationDocument,
) -> str:
    if task.status == "stale" or conflict_summary["stale"]:
        return "skip_stale"
    if task.status == "archived":
        return "skip_archived"
    if conflict_summary["blocking_count"]:
        return "inspect_conflict"
    if task.status == "needs_more_work" and task.follow_up_task_id:
        return "add_follow_up"
    if task.status == "applied":
        return "resolve"
    if not ready:
        return "generate_local"
    if local_ready and not provider_ready:
        return "generate_provider"
    if ready and not has_decision:
        return "refresh_decision_report"
    if has_decision and task.status not in {"applied", "resolved"}:
        return "apply_ready_candidate"
    return "no_action"


def _score_breakdown(
    *,
    task: ReviewTask,
    ready: list[ReviewCandidate],
    local_ready: list[ReviewCandidate],
    provider_ready: list[ReviewCandidate],
    has_decision: bool,
    conflict_summary: ImplementationDocument,
) -> dict[str, int]:
    priority = round(int(task.priority or 0) * 0.25)
    status = {
        "open": 18,
        "candidate_ready": 24,
        "applied": 12,
        "resolved": 0,
        "needs_more_work": 10,
        "stale": -30,
        "archived": -50,
    }.get(task.status, 0)
    candidate_readiness = 18 if ready else 8
    if has_decision:
        candidate_readiness += 8
    provider_gap = 10 if local_ready and not provider_ready else (4 if provider_ready else 0)
    if conflict_summary["blocking_count"]:
        conflict = -30
    elif conflict_summary["warning_count"]:
        conflict = 4
    else:
        conflict = 12
    freshness = -40 if task.status == "stale" or conflict_summary["stale"] else 8
    target = 8 if task.target.get("section_name") and task.target.get("track_name") else (4 if task.target.get("section_name") else 0)
    return {
        "priority": priority,
        "status": status,
        "candidate_readiness": candidate_readiness,
        "provider_gap": provider_gap,
        "conflict": conflict,
        "freshness": freshness,
        "target_specificity": target,
    }


def _action_reason(action: str, task: ReviewTask, conflict_summary: ImplementationDocument, provider_summary: ImplementationDocument, has_decision: bool) -> str:
    if action == "skip_stale":
        return "ReviewTask is stale and should be refreshed outside the sprint."
    if action == "skip_archived":
        return "ReviewTask is archived and should not participate in sprint work."
    if action == "inspect_conflict":
        return "Task has blocking sprint conflicts that should be inspected before candidate work."
    if action == "add_follow_up":
        return "Task needs more work and its linked follow-up should be added to the sprint."
    if action == "resolve":
        return "Task already applied a candidate; confirm the result and resolve if it solved the feedback."
    if action == "generate_local":
        return "Task has no ready candidates, so local candidates are the next low-risk step."
    if action == "generate_provider":
        return "Task has local candidates but no ready provider candidate, so provider alternatives can improve comparison."
    if action == "refresh_decision_report":
        return "Task has ready candidates but no current Decision Report recommendation."
    if action == "apply_ready_candidate":
        return "Decision Report has a recommended ready candidate; user can inspect and manually apply it."
    if action == "no_action" and task.status == "resolved":
        return "Task is resolved."
    return sanitize_sensitive_text(f"No immediate sprint action is recommended. Decision report present: {bool(has_decision)}; warnings: {conflict_summary['warning_count']}; provider candidates: {provider_summary.get('provider_candidate_count')}.")


def _action_warnings(task: ReviewTask, conflict_summary: ImplementationDocument, decision_report: ImplementationDocument | None) -> list[str]:
    warnings = []
    if conflict_summary["warning_count"]:
        warnings.append("sprint_conflict_warning")
    if conflict_summary["blocking_count"]:
        warnings.append("blocking_conflict")
    if task.status == "needs_more_work":
        warnings.append("needs_follow_up_review")
    if isinstance(decision_report, dict):
        warnings.extend(str(item) for item in decision_report.get("risk_flags", []) if str(item))
    return sorted(set(warnings))


def _context_pack_preview(
    *,
    project_id: str,
    sprint: ReviewSprint,
    task: ReviewTask,
    library_index: LibraryIndex | None,
    project_document: Any | None,
) -> ImplementationDocument:
    query = review_task_context_recommendation_query(project_id=project_id, sprint=sprint, task=task, project_document=project_document)
    if library_index is None:
        return {"query": query, "asset_refs": [], "reference_refs": [], "warnings": ["library_index_unavailable"]}
    try:
        recommended = recommend_library_context(library_index, query)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"query": query, "asset_refs": [], "reference_refs": [], "warnings": [sanitize_sensitive_text(str(exc))[:160]]}
    recommendation = recommended.get("recommendation") if isinstance(recommended.get("recommendation"), dict) else {}
    preview = recommendation.get("context_pack_preview") if isinstance(recommendation.get("context_pack_preview"), dict) else {}
    return sanitize_metadata(
        {
            "query": recommendation.get("query") if isinstance(recommendation.get("query"), dict) else query,
            "asset_refs": preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else [],
            "reference_refs": preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else [],
            "warnings": preview.get("warnings") if isinstance(preview.get("warnings"), list) else [],
        }
    )


def _sprint_level_recommendation(actions: list[ImplementationDocument], conflict_report: ImplementationDocument) -> ImplementationDocument:
    blocking_count = len([item for item in conflict_report.get("conflicts", []) if isinstance(item, dict) and item.get("severity") == "blocking"]) if isinstance(conflict_report.get("conflicts"), list) else 0
    next_action = actions[0]["action"] if actions else "no_action"
    ready_to_close = bool(actions) and all(item.get("action") in {"resolve", "no_action", "skip_archived"} for item in actions) and not blocking_count
    reason = _sprint_reason(next_action, blocking_count, actions)
    return sanitize_metadata(
        {
            "next_action": next_action,
            "reason": reason,
            "ready_to_close": ready_to_close,
            "blocking_conflict_count": blocking_count,
        }
    )


def _sprint_reason(next_action: str, blocking_count: int, actions: list[ImplementationDocument]) -> str:
    if blocking_count:
        return "At least one ReviewTask has a blocking conflict; inspect conflicts before candidate work."
    if next_action == "generate_provider":
        return "Top tasks have local candidates but no provider alternatives."
    if next_action == "generate_local":
        return "Top tasks do not have ready candidates yet."
    if next_action == "apply_ready_candidate":
        return "Top task has a Decision Report recommendation ready for manual apply."
    if next_action == "resolve":
        return "Top task has already applied a candidate and is ready for user resolution."
    if actions:
        return f"Next recommended action is {next_action}."
    return "No ReviewTasks are available for recommendation."


def _top_recommendation_summary(action: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "task_id": action.get("task_id"),
            "rank": action.get("rank"),
            "action": action.get("action"),
            "score": action.get("score"),
            "reason": action.get("reason"),
        }
    )


def _included_task_ids(sprint: ReviewSprint) -> list[str]:
    return [str(ref.get("task_id")) for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)) if ref.get("included", True) and ref.get("task_id")]


def _ref_order(sprint: ReviewSprint, task_id: str) -> int:
    for ref in sprint.task_refs:
        if ref.get("task_id") == task_id:
            return int(ref.get("order") or 9999)
    return 9999


def _task_conflicts(conflict_report: ImplementationDocument, task_id: str) -> list[ImplementationDocument]:
    conflicts = conflict_report.get("conflicts") if isinstance(conflict_report, dict) else []
    return [dict(item) for item in conflicts if isinstance(item, dict) and task_id in [str(task) for task in item.get("task_ids", [])]]


def _conflict_summary(conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    blocking = [item for item in conflicts if item.get("severity") == "blocking"]
    warnings = [item for item in conflicts if item.get("severity") == "warning"]
    return {
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "stale": any(item.get("kind") == "stale_task" for item in conflicts),
    }


def _conflict_public(conflict: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "conflict_id": conflict.get("conflict_id"),
            "severity": conflict.get("severity"),
            "kind": conflict.get("kind"),
            "message": conflict.get("message"),
        }
    )


def _order_bucket(action: ImplementationDocument) -> int:
    if action.get("action") == "inspect_conflict":
        return 0
    if action.get("action") in {"skip_stale", "skip_archived"}:
        return 3
    if action.get("action") == "no_action":
        return 4
    return 1


def _context_ref_count(preview: Any) -> int:
    if not isinstance(preview, dict):
        return 0
    return len(preview.get("asset_refs") or []) + len(preview.get("reference_refs") or [])


def _try_read_decision_report(task_store: ReviewTaskStore, task_id: str) -> ImplementationDocument:
    try:
        return task_store.read_decision_report(task_id)
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _song_request_for_task(project_document: Any | None, task: ReviewTask) -> ImplementationDocument:
    if project_document is not None:
        versions = getattr(project_document, "versions", [])
        for version in versions:
            if getattr(version, "version_id", None) == task.parent_version_id:
                request = getattr(version, "request", {})
                if isinstance(request, dict):
                    return sanitize_metadata(request)
    return {}


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
