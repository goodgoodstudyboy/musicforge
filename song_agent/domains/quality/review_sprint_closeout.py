from __future__ import annotations

import hashlib
import json
from typing import Any

from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore, SprintActionQueue
from song_agent.domains.quality.review_sprints import ReviewSprint, ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate, ReviewTask, ReviewTaskStore


CLOSEOUT_SCHEMA_VERSION = 1
SIGNOFF_SCHEMA_VERSION = 1
CLOSEOUT_STATUSES = {"passed", "warning", "failed", "stale", "not_ready"}
CLOSEOUT_READINESS_VALUES = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}
OPEN_TASK_STATUSES = {"open", "candidate_ready", "needs_more_work"}
EXECUTABLE_ACTION_SAFETY = {"auto_safe", "provider_safe"}
PROVIDER_TOKEN_WARNING_THRESHOLD = 100_000


def build_closeout_report(
    *,
    project_id: str,
    sprint: ReviewSprint,
    project_document: Any,
    task_store: ReviewTaskStore,
    sprint_store: ReviewSprintStore,
    queue_store: ReviewSprintActionQueueStore,
    metrics_report: dict[str, Any] | None = None,
    judge_summary: dict[str, Any] | None = None,
    recommendation_report: dict[str, Any] | None = None,
    conflict_report: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    source = _closeout_sources(
        sprint=sprint,
        project_document=project_document,
        task_store=task_store,
        sprint_store=sprint_store,
        queue_store=queue_store,
        metrics_report=metrics_report or {},
        judge_summary=judge_summary or {},
        recommendation_report=recommendation_report or {},
        conflict_report=conflict_report or {},
    )
    task_summary = _task_summary(source["tasks"], source["missing_task_ids"])
    candidate_summary = _candidate_summary(source["tasks"], source["candidates_by_task"])
    queue_summary = _queue_summary(source["queues"])
    metrics_summary = _metrics_summary(source["metrics_report"])
    judge_report_summary = _judge_summary(source["judge_summary"], source["metrics_report"])
    recommended_final_version = _recommended_final_version(source["tasks"], project_document)
    checks = _build_checks(
        task_summary=task_summary,
        candidate_summary=candidate_summary,
        queue_summary=queue_summary,
        judge_summary=judge_report_summary,
        metrics_summary=metrics_summary,
        conflict_report=source["conflict_report"],
        recommendation_report=source["recommendation_report"],
        recommended_final_version=recommended_final_version,
        project_document=project_document,
    )
    blockers = [check for check in checks if check.get("severity") == "blocking" and check.get("status") == "failed"]
    warnings = [check for check in checks if check.get("severity") == "warning" and check.get("status") == "warning"]
    status = _closeout_status(task_summary, blockers, warnings)
    readiness = _closeout_readiness(status, task_summary, checks, metrics_summary)
    report = {
        "schema_version": CLOSEOUT_SCHEMA_VERSION,
        "project_id": project_id,
        "sprint_id": sprint.sprint_id,
        "created_at": now,
        "source_hash": _source_hash(source),
        "status": status,
        "readiness": readiness,
        "close_allowed": status in {"passed", "warning"},
        "forced": False,
        "stale": False,
        "blockers": [_check_message(check) for check in blockers],
        "warnings": [_check_message(check) for check in warnings],
        "checks": checks,
        "task_summary": task_summary,
        "candidate_summary": candidate_summary,
        "queue_summary": queue_summary,
        "judge_summary": judge_report_summary,
        "metrics_summary": metrics_summary,
        "recommended_final_version": recommended_final_version,
    }
    return sanitize_metadata(report)


def closeout_source_hash(
    *,
    sprint: ReviewSprint,
    project_document: Any,
    task_store: ReviewTaskStore,
    sprint_store: ReviewSprintStore,
    queue_store: ReviewSprintActionQueueStore,
    metrics_report: dict[str, Any] | None = None,
    judge_summary: dict[str, Any] | None = None,
    recommendation_report: dict[str, Any] | None = None,
    conflict_report: dict[str, Any] | None = None,
) -> str:
    return _source_hash(
        _closeout_sources(
            sprint=sprint,
            project_document=project_document,
            task_store=task_store,
            sprint_store=sprint_store,
            queue_store=queue_store,
            metrics_report=metrics_report or {},
            judge_summary=judge_summary or {},
            recommendation_report=recommendation_report or {},
            conflict_report=conflict_report or {},
        )
    )


def closeout_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {}
    recommended = report.get("recommended_final_version") if isinstance(report.get("recommended_final_version"), dict) else {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "project_id": report.get("project_id"),
            "sprint_id": report.get("sprint_id"),
            "created_at": report.get("created_at"),
            "source_hash": report.get("source_hash"),
            "status": report.get("status"),
            "readiness": report.get("readiness"),
            "close_allowed": bool(report.get("close_allowed", False)),
            "forced": bool(report.get("forced", False)),
            "stale": bool(report.get("stale", False)),
            "blocker_count": len(report.get("blockers") or []),
            "warning_count": len(report.get("warnings") or []),
            "recommended_final_version_id": recommended.get("version_id"),
        }
    )


def mark_closeout_report_stale(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> dict[str, Any]:
    data = dict(report or {})
    checks = [check for check in data.get("checks", []) if isinstance(check, dict)]
    stale_check = _check("closeout_stale", True, "blocking", "Closeout Report is stale. Refresh closeout before closing.", 1)
    if not any(check.get("check_id") == "closeout_stale" for check in checks):
        checks.insert(0, stale_check)
    data.update(
        {
            "status": "stale",
            "readiness": "stale",
            "close_allowed": False,
            "stale": True,
            "current_source_hash": current_source_hash,
            "checks": checks,
            "blockers": [_check_message(check) for check in checks if check.get("severity") == "blocking" and check.get("status") == "failed"],
        }
    )
    return sanitize_metadata(data)


def mark_closeout_report_forced(report: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(report or {})
    data["forced"] = True
    return sanitize_metadata(data)


def build_signoff_record(
    *,
    project_id: str,
    sprint: ReviewSprint,
    closeout_report: dict[str, Any],
    payload: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    now = now or now_iso()
    forced = bool(payload.get("force", False))
    override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "")).strip()[:1000]
    if forced and not override_reason:
        raise ValueError("override_reason is required when force=true.")
    recommended = closeout_report.get("recommended_final_version") if isinstance(closeout_report.get("recommended_final_version"), dict) else {}
    selected_version_id = _optional_str(payload.get("selected_version_id")) or _optional_str(recommended.get("version_id"))
    blockers = [sanitize_sensitive_text(str(item))[:240] for item in closeout_report.get("blockers", []) if str(item).strip()]
    warnings = [sanitize_sensitive_text(str(item))[:240] for item in closeout_report.get("warnings", []) if str(item).strip()]
    record = {
        "schema_version": SIGNOFF_SCHEMA_VERSION,
        "project_id": project_id,
        "sprint_id": sprint.sprint_id,
        "signed_at": now,
        "signed_by": sanitize_sensitive_text(str(payload.get("signed_by") or "local-user"))[:120],
        "decision": "closed",
        "forced": forced,
        "override_reason": override_reason,
        "closeout_report_hash": _stable_hash(closeout_report),
        "closeout_status": closeout_report.get("status"),
        "selected_version_id": selected_version_id,
        "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:1000],
        "acknowledged_blockers": blockers[:20],
        "acknowledged_warnings": warnings[:20],
    }
    return sanitize_metadata(record)


def signoff_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict) or not record:
        return {"status": "not_signed"}
    return sanitize_metadata(
        {
            "status": "signed",
            "schema_version": record.get("schema_version"),
            "project_id": record.get("project_id"),
            "sprint_id": record.get("sprint_id"),
            "signed_at": record.get("signed_at"),
            "signed_by": record.get("signed_by"),
            "decision": record.get("decision"),
            "forced": bool(record.get("forced", False)),
            "closeout_status": record.get("closeout_status"),
            "selected_version_id": record.get("selected_version_id"),
            "acknowledged_blocker_count": len(record.get("acknowledged_blockers") or []),
            "acknowledged_warning_count": len(record.get("acknowledged_warnings") or []),
        }
    )


def closeout_allows_close(report: dict[str, Any] | None) -> bool:
    return bool(isinstance(report, dict) and report.get("close_allowed") and report.get("status") in {"passed", "warning"} and not report.get("stale"))


def _closeout_sources(
    *,
    sprint: ReviewSprint,
    project_document: Any,
    task_store: ReviewTaskStore,
    sprint_store: ReviewSprintStore,
    queue_store: ReviewSprintActionQueueStore,
    metrics_report: dict[str, Any],
    judge_summary: dict[str, Any],
    recommendation_report: dict[str, Any],
    conflict_report: dict[str, Any],
) -> dict[str, Any]:
    tasks: list[ReviewTask] = []
    missing_task_ids: list[str] = []
    candidates_by_task: dict[str, list[ReviewCandidate]] = {}
    for task_id in _included_task_ids(sprint):
        try:
            task = task_store.read_task(task_id)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            missing_task_ids.append(task_id)
            continue
        tasks.append(task)
        try:
            candidates_by_task[task.task_id] = task_store.list_candidates(task.task_id)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            candidates_by_task[task.task_id] = []
    try:
        queues = queue_store.list_queues(include_archived=True)
    except (OSError, ValueError, TypeError, FileNotFoundError):
        queues = []
    summary = sprint_store.read_summary(sprint.sprint_id, default={})
    return {
        "sprint": _sprint_source_summary(sprint),
        "summary": summary,
        "conflict_report": _conflict_source_summary(conflict_report),
        "recommendation_report": _recommendation_source_summary(recommendation_report),
        "metrics_report": _metrics_source_summary(metrics_report),
        "judge_summary": _judge_source_summary(judge_summary),
        "tasks": tasks,
        "missing_task_ids": sorted(missing_task_ids),
        "candidates_by_task": candidates_by_task,
        "queues": queues,
        "project": _project_source_summary(project_document),
    }


def _build_checks(
    *,
    task_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    queue_summary: dict[str, Any],
    judge_summary: dict[str, Any],
    metrics_summary: dict[str, Any],
    conflict_report: dict[str, Any],
    recommendation_report: dict[str, Any],
    recommended_final_version: dict[str, Any],
    project_document: Any,
) -> list[dict[str, Any]]:
    checks = [
        _check("task_data", int(task_summary.get("task_count") or 0) <= 0, "blocking", "Sprint has no included ReviewTasks.", int(task_summary.get("task_count") or 0)),
        _check("open_tasks", int(task_summary.get("open_task_count") or 0) > 0, "blocking", "ReviewTasks are still open, candidate-ready, or need more work.", int(task_summary.get("open_task_count") or 0)),
        _check("stale_tasks", int(task_summary.get("stale_task_count") or 0) > 0, "blocking", "Stale ReviewTasks must be refreshed before close.", int(task_summary.get("stale_task_count") or 0)),
        _check("blocking_conflicts", _blocking_conflict_count(conflict_report) > 0, "blocking", "Blocking Sprint conflicts remain.", _blocking_conflict_count(conflict_report)),
        _check("pending_queue_items", int(queue_summary.get("pending_executable_item_count") or 0) > 0, "blocking", "Executable Action Queue items are still pending or running.", int(queue_summary.get("pending_executable_item_count") or 0)),
        _check("failed_queue_items", int(queue_summary.get("failed_item_count") or 0) > 0, "blocking", "Action Queue items failed.", int(queue_summary.get("failed_item_count") or 0)),
        _check("stale_recommendations", _report_stale(recommendation_report), "blocking", "Recommendation Report is stale.", 1 if _report_stale(recommendation_report) else 0),
        _check("stale_judge_reports", int(judge_summary.get("stale_judge_count") or 0) > 0, "blocking", "Provider Judge reports are stale.", int(judge_summary.get("stale_judge_count") or 0)),
        _check("metrics_not_ready", (metrics_summary.get("readiness") or "no_data") != "ready_to_close", "blocking", "Sprint metrics are not ready to close.", 0 if (metrics_summary.get("readiness") or "no_data") == "ready_to_close" else 1),
        _check("missing_applied_version", not _has_applied_or_selected_version(task_summary, project_document, recommended_final_version), "blocking", "Sprint has no applied candidate version or selected version.", 1 if not _has_applied_or_selected_version(task_summary, project_document, recommended_final_version) else 0),
        _check("unresolved_manual_required", int(queue_summary.get("manual_required_count") or 0) > 0, "warning", "Manual-required Action Queue items remain for audit.", int(queue_summary.get("manual_required_count") or 0)),
        _check("judge_local_disagreement", int(judge_summary.get("judge_local_disagreement_count") or 0) > 0, "warning", "Provider Judge disagrees with local ranking.", int(judge_summary.get("judge_local_disagreement_count") or 0)),
        _check("high_risk_judge_candidate", int(judge_summary.get("high_risk_candidate_count") or 0) > 0, "warning", "Provider Judge flagged high-risk candidates.", int(judge_summary.get("high_risk_candidate_count") or 0)),
        _check("provider_tokens_high", int(metrics_summary.get("provider_tokens") or 0) > PROVIDER_TOKEN_WARNING_THRESHOLD, "warning", "Provider token usage is high for this Sprint.", int(metrics_summary.get("provider_tokens") or 0)),
        _check("quality_not_improved", _quality_not_improved(metrics_summary), "warning", "Quality delta is not improved.", int(metrics_summary.get("quality_delta") or 0) if metrics_summary.get("quality_delta") is not None else 0),
        _check("failed_candidates_present", int(candidate_summary.get("failed_candidate_count") or 0) > 0, "warning", "Failed candidates are present.", int(candidate_summary.get("failed_candidate_count") or 0)),
        _check("unrendered_audio", int(candidate_summary.get("selected_unrendered_audio_count") or 0) > 0, "warning", "Selected or applied candidates have no rendered WAV.", int(candidate_summary.get("selected_unrendered_audio_count") or 0)),
    ]
    return checks


def _check(check_id: str, failed: bool, severity: str, message: str, count: int | float | None = 0) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "check_id": check_id,
            "status": "failed" if failed and severity == "blocking" else ("warning" if failed else "passed"),
            "severity": severity,
            "message": message,
            "count": count,
        }
    )


def _check_message(check: dict[str, Any]) -> str:
    count = check.get("count")
    suffix = f" ({count})" if count not in {None, "", 0} else ""
    return sanitize_sensitive_text(f"{check.get('check_id')}: {check.get('message')}{suffix}")[:240]


def _closeout_status(task_summary: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    if int(task_summary.get("task_count") or 0) <= 0:
        return "not_ready"
    if blockers:
        return "failed"
    if warnings:
        return "warning"
    return "passed"


def _closeout_readiness(status: str, task_summary: dict[str, Any], checks: list[dict[str, Any]], metrics_summary: dict[str, Any]) -> str:
    if status == "not_ready":
        return "no_data"
    if any(check.get("check_id") in {"stale_tasks", "stale_recommendations", "stale_judge_reports"} and check.get("status") == "failed" for check in checks):
        return "stale"
    if status == "failed":
        if int(task_summary.get("open_task_count") or 0) > 0 and int(task_summary.get("ready_candidate_task_count") or 0) <= 0:
            return "needs_candidates"
        if int(task_summary.get("open_task_count") or 0) > 0:
            return "needs_review"
        return "blocked"
    if status == "warning":
        return str(metrics_summary.get("readiness") or "needs_review")
    return "ready_to_close"


def _task_summary(tasks: list[ReviewTask], missing_task_ids: list[str]) -> dict[str, Any]:
    counts = {status: 0 for status in ("open", "candidate_ready", "applied", "resolved", "needs_more_work", "stale", "archived")}
    applied_versions = []
    ready_candidate_tasks = 0
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
        if task.applied_version_id:
            applied_versions.append(task.applied_version_id)
        if int(task.counts.get("ready_candidate_count") or 0) > 0:
            ready_candidate_tasks += 1
    open_count = sum(int(counts.get(status) or 0) for status in OPEN_TASK_STATUSES)
    return sanitize_metadata(
        {
            "task_count": len(tasks),
            "missing_task_count": len(missing_task_ids),
            "open_task_count": open_count + len(missing_task_ids),
            "resolved_task_count": counts.get("resolved", 0),
            "applied_task_count": counts.get("applied", 0),
            "needs_more_work_count": counts.get("needs_more_work", 0),
            "stale_task_count": counts.get("stale", 0),
            "archived_task_count": counts.get("archived", 0),
            "ready_candidate_task_count": ready_candidate_tasks,
            "status_counts": counts,
            "applied_version_ids": sorted({item for item in applied_versions if item}),
            "missing_task_ids": missing_task_ids,
        }
    )


def _candidate_summary(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]]) -> dict[str, Any]:
    candidates = [candidate for task in tasks for candidate in candidates_by_task.get(task.task_id, [])]
    selected_ids = {task.selected_candidate_id for task in tasks if task.selected_candidate_id}
    selected_or_applied = [candidate for candidate in candidates if candidate.status == "applied" or candidate.candidate_id in selected_ids]
    unrendered_audio = [candidate for candidate in selected_or_applied if candidate.audio_status != "completed"]
    return sanitize_metadata(
        {
            "candidate_count": len(candidates),
            "ready_candidate_count": len([candidate for candidate in candidates if candidate.status == "ready"]),
            "applied_candidate_count": len([candidate for candidate in candidates if candidate.status == "applied"]),
            "failed_candidate_count": len([candidate for candidate in candidates if candidate.status == "failed"]),
            "selected_candidate_count": len(selected_or_applied),
            "selected_unrendered_audio_count": len(unrendered_audio),
        }
    )


def _queue_summary(queues: list[SprintActionQueue]) -> dict[str, Any]:
    active_queues = [queue for queue in queues if queue.status != "archived"]
    items = [item for queue in active_queues for item in queue.items]
    pending_executable = [item for item in items if item.safety in EXECUTABLE_ACTION_SAFETY and item.status in {"pending", "running"}]
    pending_provider = [item for item in items if item.safety == "provider_safe" and item.status in {"pending", "running"}]
    return sanitize_metadata(
        {
            "queue_count": len(active_queues),
            "pending_item_count": len([item for item in items if item.status == "pending"]),
            "running_item_count": len([item for item in items if item.status == "running"]),
            "pending_executable_item_count": len(pending_executable),
            "failed_item_count": len([item for item in items if item.status == "failed"]),
            "manual_required_count": len([item for item in items if item.status == "manual_required"]),
            "pending_provider_action_count": len(pending_provider),
        }
    )


def _metrics_summary(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {"readiness": "no_data", "completion_rate": None, "quality_delta": None, "provider_tokens": 0}
    risk = report.get("risk_readiness") if isinstance(report.get("risk_readiness"), dict) else {}
    overview = report.get("overview") if isinstance(report.get("overview"), dict) else {}
    quality = report.get("quality_delta") if isinstance(report.get("quality_delta"), dict) else {}
    provider = report.get("provider_usage") if isinstance(report.get("provider_usage"), dict) else {}
    quality_delta = quality.get("overall_delta") if quality else report.get("quality_delta")
    if isinstance(quality_delta, dict):
        quality_delta = None
    return sanitize_metadata(
        {
            "readiness": risk.get("readiness") or report.get("readiness") or "no_data",
            "completion_rate": overview.get("completion_rate", report.get("completion_rate")),
            "quality_delta": quality_delta,
            "provider_tokens": provider.get("total_tokens", report.get("provider_tokens", 0)),
            "warnings": report.get("warnings") if isinstance(report.get("warnings"), list) else [],
        }
    )


def _judge_summary(summary: dict[str, Any], metrics_report: dict[str, Any]) -> dict[str, Any]:
    metrics = metrics_report.get("judge_metrics") if isinstance(metrics_report.get("judge_metrics"), dict) else {}
    return sanitize_metadata(
        {
            "judged_task_count": max(int(summary.get("judged_task_count") or 0), int(metrics.get("judged_task_count") or 0)),
            "stale_judge_count": max(int(summary.get("stale_judge_count") or 0), int(metrics.get("stale_judge_count") or 0)),
            "judge_local_disagreement_count": int(metrics.get("judge_local_disagreement_count") or summary.get("judge_local_disagreement_count") or 0),
            "judge_apply_match_rate": metrics.get("judge_apply_match_rate", summary.get("judge_apply_match_rate")),
            "high_risk_candidate_count": max(int(summary.get("high_risk_candidate_count") or 0), int(metrics.get("high_risk_candidate_count") or 0)),
            "judge_provider_tokens": int(summary.get("judge_provider_tokens") or metrics.get("judge_provider_tokens") or 0),
        }
    )


def _recommended_final_version(tasks: list[ReviewTask], project_document: Any) -> dict[str, Any]:
    applied_ids = {task.applied_version_id for task in tasks if task.applied_version_id}
    version_ids = [getattr(version, "version_id", "") for version in getattr(project_document, "versions", [])]
    latest_applied = None
    for version_id in version_ids:
        if version_id in applied_ids:
            latest_applied = version_id
    state = getattr(project_document, "state", None)
    selected = latest_applied or getattr(state, "final_version_id", None) or getattr(state, "selected_version_id", None)
    if not selected:
        return {}
    version = _version_by_id(project_document, selected)
    return sanitize_metadata(
        {
            "version_id": selected,
            "source": "latest_applied_sprint_candidate" if latest_applied else ("final_version" if getattr(state, "final_version_id", None) == selected else "selected_version"),
            "quality_score": getattr(version, "quality_score", None),
        }
    )


def _version_by_id(project_document: Any, version_id: str | None) -> Any | None:
    if not version_id:
        return None
    for version in getattr(project_document, "versions", []):
        if getattr(version, "version_id", None) == version_id:
            return version
    return None


def _included_task_ids(sprint: ReviewSprint) -> list[str]:
    refs = sorted(sprint.task_refs, key=lambda ref: int(ref.get("order") or 0))
    return [str(ref.get("task_id")) for ref in refs if ref.get("included", True) and str(ref.get("task_id") or "").strip()]


def _sprint_source_summary(sprint: ReviewSprint) -> dict[str, Any]:
    return {
        "sprint_id": sprint.sprint_id,
        "project_id": sprint.project_id,
        "status": sprint.status,
        "parent_version_id": sprint.parent_version_id,
        "task_refs": sprint.task_refs,
        "selected_task_id": sprint.selected_task_id,
        "counts": sprint.counts,
        "closed_at": sprint.closed_at,
    }


def _task_source_summary(task: ReviewTask, candidates: list[ReviewCandidate]) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "status": task.status,
        "parent_version_id": task.parent_version_id,
        "selected_candidate_id": task.selected_candidate_id,
        "applied_version_id": task.applied_version_id,
        "follow_up_task_id": task.follow_up_task_id,
        "counts": task.counts,
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "candidate_type": candidate.candidate_type,
                "status": candidate.status,
                "rank": candidate.rank,
                "midi_status": candidate.midi_status,
                "audio_status": candidate.audio_status,
                "score": candidate.scores.get("combined"),
            }
            for candidate in candidates
        ],
    }


def _queue_source_summary(queue: SprintActionQueue) -> dict[str, Any]:
    return {
        "queue_id": queue.queue_id,
        "status": queue.status,
        "updated_at": queue.updated_at,
        "summary": queue.summary,
        "items": [
            {
                "item_id": item.item_id,
                "task_id": item.task_id,
                "action": item.action,
                "status": item.status,
                "safety": item.safety,
            }
            for item in queue.items
        ],
    }


def _conflict_source_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "sprint_id": report.get("sprint_id"),
        "conflicts": [
            {
                "severity": item.get("severity"),
                "kind": item.get("kind"),
                "task_ids": item.get("task_ids") if isinstance(item.get("task_ids"), list) else [],
            }
            for item in report.get("conflicts", [])
            if isinstance(item, dict)
        ]
        if isinstance(report, dict)
        else [],
    }


def _recommendation_source_summary(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    return {
        "schema_version": report.get("schema_version"),
        "sprint_id": report.get("sprint_id"),
        "created_at": report.get("created_at"),
        "stale": report.get("stale"),
        "status": report.get("status"),
        "recommended_order": report.get("recommended_order") if isinstance(report.get("recommended_order"), list) else [],
        "source_summary": report.get("source_summary") if isinstance(report.get("source_summary"), dict) else {},
    }


def _metrics_source_summary(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    return {
        "schema_version": report.get("schema_version"),
        "sprint_id": report.get("sprint_id"),
        "source_hash": report.get("source_hash"),
        "risk_readiness": report.get("risk_readiness") if isinstance(report.get("risk_readiness"), dict) else {},
        "overview": report.get("overview") if isinstance(report.get("overview"), dict) else {},
        "candidate_funnel": report.get("candidate_funnel") if isinstance(report.get("candidate_funnel"), dict) else {},
        "action_queue_execution": report.get("action_queue_execution") if isinstance(report.get("action_queue_execution"), dict) else {},
        "quality_delta": report.get("quality_delta") if isinstance(report.get("quality_delta"), dict) else {},
        "judge_metrics": report.get("judge_metrics") if isinstance(report.get("judge_metrics"), dict) else {},
        "provider_usage": report.get("provider_usage") if isinstance(report.get("provider_usage"), dict) else {},
    }


def _judge_source_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    return {
        "schema_version": summary.get("schema_version"),
        "sprint_id": summary.get("sprint_id"),
        "source_hash": summary.get("source_hash"),
        "created_at": summary.get("created_at"),
        "judged_task_count": summary.get("judged_task_count"),
        "stale_judge_count": summary.get("stale_judge_count"),
        "recommended_candidate_count": summary.get("recommended_candidate_count"),
        "high_risk_candidate_count": summary.get("high_risk_candidate_count"),
        "judge_provider_tokens": summary.get("judge_provider_tokens"),
    }


def _project_source_summary(project_document: Any) -> dict[str, Any]:
    state = getattr(project_document, "state", None)
    return {
        "selected_version_id": getattr(state, "selected_version_id", None),
        "final_version_id": getattr(state, "final_version_id", None),
        "latest_version_id": getattr(state, "latest_version_id", None),
        "versions": [
            {
                "version_id": getattr(version, "version_id", None),
                "status": getattr(version, "status", None),
                "quality_score": getattr(version, "quality_score", None),
                "updated_at": getattr(version, "updated_at", None),
            }
            for version in getattr(project_document, "versions", [])
        ],
    }


def _source_hash(source: dict[str, Any]) -> str:
    source_summary = {
        **{key: value for key, value in source.items() if key not in {"tasks", "candidates_by_task", "queues"}},
        "tasks": [_task_source_summary(task, source.get("candidates_by_task", {}).get(task.task_id, [])) for task in source.get("tasks", [])],
        "missing_task_ids": source.get("missing_task_ids", []),
        "queues": [_queue_source_summary(queue) for queue in source.get("queues", [])],
    }
    return _stable_hash(source_summary)


def _stable_hash(value: Any) -> str:
    clean = sanitize_metadata(value)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _blocking_conflict_count(report: dict[str, Any]) -> int:
    conflicts = report.get("conflicts") if isinstance(report, dict) else []
    return len([item for item in conflicts if isinstance(item, dict) and item.get("severity") == "blocking"])


def _report_stale(report: dict[str, Any]) -> bool:
    return bool(isinstance(report, dict) and (report.get("stale") or report.get("status") == "stale"))


def _quality_not_improved(metrics_summary: dict[str, Any]) -> bool:
    if metrics_summary.get("quality_delta") is None:
        return False
    try:
        return int(metrics_summary.get("quality_delta") or 0) <= 0
    except (TypeError, ValueError):
        return False


def _has_applied_or_selected_version(task_summary: dict[str, Any], project_document: Any, recommended_final_version: dict[str, Any]) -> bool:
    if task_summary.get("applied_version_ids"):
        return True
    if recommended_final_version.get("version_id"):
        return True
    state = getattr(project_document, "state", None)
    return bool(getattr(state, "selected_version_id", None) or getattr(state, "final_version_id", None))


def _optional_str(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return sanitize_sensitive_text(str(value).strip())[:160]
