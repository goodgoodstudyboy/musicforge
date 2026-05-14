from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from song_agent.music_quality import analyze_song_quality
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectDocument, now_iso
from song_agent.provider_usage import build_provider_usage_report
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.review_judge import REVIEW_JUDGE_TEMPLATE_ID, judge_report_summary, mark_judge_report_stale, read_judge_report_with_stale
from song_agent.review_sprint_actions import ReviewSprintActionQueueStore, SprintActionQueue
from song_agent.review_sprint_closeout import closeout_report_summary, signoff_summary
from song_agent.review_sprints import ReviewSprint, ReviewSprintStore
from song_agent.review_tasks import ReviewCandidate, ReviewTask, ReviewTaskStore
from song_agent.schemas.song import SongPlan


SPRINT_METRICS_SCHEMA_VERSION = 1
PROJECT_REVIEW_METRICS_SCHEMA_VERSION = 1
READINESS_VALUES = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}


class ReviewMetricsStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()

    def sprint_metrics_path(self, sprint_id: str) -> Path:
        return self.project_dir / "review-sprints" / sprint_id / "metrics-report.json"

    def read_sprint_metrics(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.sprint_metrics_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def write_sprint_metrics(self, sprint_id: str, report: dict[str, Any]) -> dict[str, Any]:
        path = self.sprint_metrics_path(sprint_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = sanitize_metadata(report if isinstance(report, dict) else {})
        write_json(path, clean)
        return clean

    def project_metrics_path(self) -> Path:
        return self.project_dir / "review-metrics.json"

    def read_project_metrics(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.project_metrics_path()
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(path)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def write_project_metrics(self, report: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(report if isinstance(report, dict) else {})
        write_json(self.project_metrics_path(), clean)
        return clean


def build_sprint_metrics_report(
    *,
    project_id: str,
    sprint: ReviewSprint,
    project_document: ProjectDocument | Any,
    task_store: ReviewTaskStore,
    sprint_store: ReviewSprintStore,
    queue_store: ReviewSprintActionQueueStore | None = None,
    provider_usage_records: list[dict[str, Any]] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    queue_store = queue_store or ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
    source = _sprint_sources(sprint=sprint, sprint_store=sprint_store, task_store=task_store, queue_store=queue_store, project_document=project_document)
    tasks = source["tasks"]
    candidates_by_task = source["candidates_by_task"]
    queues = source["queues"]
    recommendation_report = source["recommendation_report"]
    conflict_report = source["conflict_report"]
    decision_reports = source["decision_reports"]
    judge_reports = source["judge_reports"]
    sprint_provider_records = _provider_records_for_tasks(provider_usage_records or [], [task.task_id for task in tasks])
    provider_report = build_provider_usage_report(scope="project", project_id=project_id, records=sprint_provider_records)
    provider_usage = _provider_usage_metrics(provider_report, tasks, candidates_by_task)
    overview = _overview_metrics(sprint, tasks, source["missing_task_ids"])
    task_throughput = _task_throughput_metrics(tasks, candidates_by_task, source["missing_task_ids"])
    candidate_funnel = _candidate_funnel_metrics(tasks, candidates_by_task)
    action_queue_execution = _action_queue_metrics(queues)
    recommendation_adoption = _recommendation_adoption_metrics(recommendation_report, queues)
    manual_decisions = _manual_decision_metrics(tasks, candidates_by_task, decision_reports)
    judge_metrics = _judge_metrics(judge_reports, tasks, decision_reports, provider_report)
    quality_delta = _quality_delta_metrics(sprint=sprint, tasks=tasks, project_document=project_document)
    risk_readiness = _risk_readiness_metrics(
        overview=overview,
        task_throughput=task_throughput,
        action_queue_execution=action_queue_execution,
        conflict_report=conflict_report,
        tasks=tasks,
        queues=queues,
        missing_task_ids=source["missing_task_ids"],
    )
    highlights, warnings = _dashboard_messages(overview, candidate_funnel, action_queue_execution, provider_usage, quality_delta, risk_readiness)
    source_summary = {
        "task_count": len(tasks),
        "missing_task_count": len(source["missing_task_ids"]),
        "candidate_count": candidate_funnel["candidate_count"],
        "queue_count": len(queues),
        "has_recommendation_report": bool(recommendation_report),
        "has_action_queue": bool(queues),
    }
    report = {
        "schema_version": SPRINT_METRICS_SCHEMA_VERSION,
        "project_id": project_id,
        "sprint_id": sprint.sprint_id,
        "created_at": now,
        "source_hash": _source_hash(
            {
                "sprint": sprint.to_dict(),
                "summary": source["summary"],
                "conflict_report": conflict_report,
                "recommendation_report": recommendation_report,
                "tasks": [_task_source_summary(task, candidates_by_task.get(task.task_id, []), decision_reports.get(task.task_id, {})) for task in tasks],
                "judge_reports": {task_id: judge_report_summary(report) for task_id, report in judge_reports.items()},
                "queues": [_queue_source_summary(queue) for queue in queues],
                "versions": [_version_source_summary(version) for version in getattr(project_document, "versions", [])],
                "provider_usage": provider_usage,
            }
        ),
        "overview": overview,
        "task_throughput": task_throughput,
        "candidate_funnel": candidate_funnel,
        "recommendation_adoption": recommendation_adoption,
        "action_queue_execution": action_queue_execution,
        "provider_usage": provider_usage,
        "quality_delta": quality_delta,
        "manual_decisions": manual_decisions,
        "judge_metrics": judge_metrics,
        "risk_readiness": risk_readiness,
        "highlights": highlights,
        "warnings": warnings,
        "closeout": _sprint_closeout_metrics(sprint_store, sprint),
        "source_summary": source_summary,
    }
    return sanitize_metadata(report)


def build_project_review_metrics(
    *,
    project_id: str,
    project_document: ProjectDocument | Any,
    sprint_store: ReviewSprintStore,
    task_store: ReviewTaskStore,
    provider_usage_records: list[dict[str, Any]] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    sprints = sprint_store.list_sprints(include_archived=True)
    sprint_reports = []
    for sprint in sprints:
        queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
        sprint_reports.append(
            build_sprint_metrics_report(
                project_id=project_id,
                sprint=sprint,
                project_document=project_document,
                task_store=task_store,
                sprint_store=sprint_store,
                queue_store=queue_store,
                provider_usage_records=provider_usage_records or [],
                now=now,
            )
        )
    provider_report = build_provider_usage_report(scope="project", project_id=project_id, records=provider_usage_records or [])
    latest_report = sprint_reports[0] if sprint_reports else {}
    quality_trend = _project_quality_trend(getattr(project_document, "versions", []))
    summaries = [sprint_metrics_summary(report) for report in sprint_reports]
    closeout_summary = _project_closeout_summary(sprint_store, sprints)
    report = {
        "schema_version": PROJECT_REVIEW_METRICS_SCHEMA_VERSION,
        "project_id": project_id,
        "created_at": now,
        "source_hash": _source_hash(
            {
                "project": getattr(project_document, "state", {}).to_dict() if hasattr(getattr(project_document, "state", {}), "to_dict") else {},
                "versions": [_version_source_summary(version) for version in getattr(project_document, "versions", [])],
                "sprint_summaries": summaries,
                "provider_usage": _provider_usage_public(provider_report),
            }
        ),
        "sprint_count": len(sprints),
        "active_sprint_count": len([sprint for sprint in sprints if sprint.status not in {"closed", "archived"}]),
        "closed_sprint_count": len([sprint for sprint in sprints if sprint.status == "closed"]),
        "total_task_count": sum(int(summary.get("task_count") or 0) for summary in summaries),
        "total_candidate_count": sum(int(summary.get("candidate_count") or 0) for summary in summaries),
        "total_provider_tokens": int(provider_report.get("total_tokens") or 0),
        "total_applied_candidate_count": sum(int(summary.get("applied_candidate_count") or 0) for summary in summaries),
        "judge_summary": _project_judge_summary(summaries),
        "closeout_summary": closeout_summary,
        "latest_sprint_id": latest_report.get("sprint_id"),
        "latest_readiness": (latest_report.get("risk_readiness") or {}).get("readiness") if isinstance(latest_report.get("risk_readiness"), dict) else "no_data",
        "quality_trend": quality_trend,
        "sprint_summaries": summaries,
    }
    return sanitize_metadata(report)


def sprint_metrics_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {}
    overview = report.get("overview") if isinstance(report.get("overview"), dict) else {}
    candidate = report.get("candidate_funnel") if isinstance(report.get("candidate_funnel"), dict) else {}
    queue = report.get("action_queue_execution") if isinstance(report.get("action_queue_execution"), dict) else {}
    provider = report.get("provider_usage") if isinstance(report.get("provider_usage"), dict) else {}
    quality = report.get("quality_delta") if isinstance(report.get("quality_delta"), dict) else {}
    readiness = report.get("risk_readiness") if isinstance(report.get("risk_readiness"), dict) else {}
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "project_id": report.get("project_id"),
            "sprint_id": report.get("sprint_id"),
            "created_at": report.get("created_at"),
            "source_hash": report.get("source_hash"),
            "readiness": readiness.get("readiness") or "no_data",
            "ready_to_close": bool(readiness.get("ready_to_close", False)),
            "completion_rate": overview.get("completion_rate"),
            "task_count": overview.get("task_count", 0),
            "open_task_count": overview.get("open_task_count", 0),
            "resolved_task_count": overview.get("resolved_task_count", 0),
            "candidate_count": candidate.get("candidate_count", 0),
            "provider_candidate_count": candidate.get("provider_candidate_count", 0),
            "applied_candidate_count": candidate.get("applied_candidate_count", 0),
            "queue_count": queue.get("queue_count", 0),
            "completed_action_count": queue.get("completed_action_count", 0),
            "failed_action_count": queue.get("failed_action_count", 0),
            "provider_tokens": provider.get("total_tokens", 0),
            "quality_delta": quality.get("overall_delta"),
            "quality_status": quality.get("status"),
            "warning_count": len(warnings),
            "warnings": [sanitize_sensitive_text(str(item))[:200] for item in warnings[:8]],
            "judge_metrics": report.get("judge_metrics") if isinstance(report.get("judge_metrics"), dict) else {},
            "closeout": report.get("closeout") if isinstance(report.get("closeout"), dict) else {},
        }
    )


def project_review_metrics_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {}
    quality_trend = report.get("quality_trend") if isinstance(report.get("quality_trend"), dict) else {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "project_id": report.get("project_id"),
            "created_at": report.get("created_at"),
            "source_hash": report.get("source_hash"),
            "sprint_count": report.get("sprint_count", 0),
            "active_sprint_count": report.get("active_sprint_count", 0),
            "closed_sprint_count": report.get("closed_sprint_count", 0),
            "total_task_count": report.get("total_task_count", 0),
            "total_candidate_count": report.get("total_candidate_count", 0),
            "total_provider_tokens": report.get("total_provider_tokens", 0),
            "total_applied_candidate_count": report.get("total_applied_candidate_count", 0),
            "latest_sprint_id": report.get("latest_sprint_id"),
            "latest_readiness": report.get("latest_readiness") or "no_data",
            "quality_trend": quality_trend,
            "judge_summary": report.get("judge_summary") if isinstance(report.get("judge_summary"), dict) else {},
            "closeout_summary": report.get("closeout_summary") if isinstance(report.get("closeout_summary"), dict) else {},
        }
    )


def _sprint_sources(
    *,
    sprint: ReviewSprint,
    sprint_store: ReviewSprintStore,
    task_store: ReviewTaskStore,
    queue_store: ReviewSprintActionQueueStore,
    project_document: Any,
) -> dict[str, Any]:
    tasks: list[ReviewTask] = []
    missing: list[str] = []
    candidates_by_task: dict[str, list[ReviewCandidate]] = {}
    decision_reports: dict[str, dict[str, Any]] = {}
    judge_reports: dict[str, dict[str, Any]] = {}
    template_store = PromptTemplateStore(task_store.project_dir.parent.parent / "prompt-templates.json")
    for task_id in _included_task_ids(sprint):
        try:
            task = task_store.read_task(task_id)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            missing.append(task_id)
            continue
        tasks.append(task)
        candidates_by_task[task.task_id] = task_store.list_candidates(task.task_id)
        try:
            decision_reports[task.task_id] = task_store.read_decision_report(task.task_id)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            decision_reports[task.task_id] = {}
        try:
            raw_report = task_store.read_judge_report(task.task_id, default={})
            if raw_report:
                template_id = str(raw_report.get("template_id") or REVIEW_JUDGE_TEMPLATE_ID)
                template = template_store.get_template(template_id)
                parent_plan = _version_song_plan(project_document, task.parent_version_id)
                judge_reports[task.task_id] = read_judge_report_with_stale(task_store, task, candidates=candidates_by_task[task.task_id], parent_plan=parent_plan, template=template)
            else:
                judge_reports[task.task_id] = {}
        except (OSError, ValueError, TypeError, FileNotFoundError):
            try:
                raw_report = task_store.read_judge_report(task.task_id, default={})
            except (OSError, ValueError, TypeError, FileNotFoundError):
                raw_report = {}
            judge_reports[task.task_id] = mark_judge_report_stale(raw_report, stale=True) if raw_report else {}
    try:
        queues = queue_store.list_queues(include_archived=True)
    except (OSError, ValueError, TypeError, FileNotFoundError):
        queues = []
    return {
        "summary": sprint_store.read_summary(sprint.sprint_id, default={}),
        "conflict_report": sprint_store.read_conflict_report(sprint.sprint_id, default={}),
        "recommendation_report": sprint_store.read_recommendation_report(sprint.sprint_id, default={}),
        "tasks": tasks,
        "missing_task_ids": sorted(missing),
        "candidates_by_task": candidates_by_task,
        "decision_reports": decision_reports,
        "judge_reports": judge_reports,
        "queues": queues,
        "project_version_ids": [getattr(version, "version_id", "") for version in getattr(project_document, "versions", [])],
    }


def _overview_metrics(sprint: ReviewSprint, tasks: list[ReviewTask], missing_task_ids: list[str]) -> dict[str, Any]:
    status_counts = _task_status_counts(tasks)
    active = [task for task in tasks if task.status != "archived"]
    resolved = status_counts.get("resolved", 0)
    active_count = len(active)
    completion_rate = _rate(resolved, active_count)
    ready_candidate_tasks = len([task for task in tasks if int(task.counts.get("ready_candidate_count") or 0) > 0 or task.status == "candidate_ready"])
    return sanitize_metadata(
        {
            "sprint_id": sprint.sprint_id,
            "sprint_name": sprint.name,
            "status": sprint.status,
            "task_count": len(tasks),
            "missing_task_count": len(missing_task_ids),
            "open_task_count": status_counts.get("open", 0) + status_counts.get("candidate_ready", 0),
            "resolved_task_count": resolved,
            "applied_task_count": status_counts.get("applied", 0),
            "blocked_task_count": 0,
            "stale_task_count": status_counts.get("stale", 0),
            "archived_task_count": status_counts.get("archived", 0),
            "ready_candidate_task_count": ready_candidate_tasks,
            "needs_more_work_count": status_counts.get("needs_more_work", 0),
            "completion_rate": completion_rate,
        }
    )


def _task_throughput_metrics(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]], missing_task_ids: list[str]) -> dict[str, Any]:
    candidate_counts = [len(candidates_by_task.get(task.task_id, [])) for task in tasks]
    follow_up_count = len([task for task in tasks if task.follow_up_task_id])
    return sanitize_metadata(
        {
            "created_task_count": len(tasks),
            "candidate_ready_task_count": len([task for task in tasks if task.status == "candidate_ready" or int(task.counts.get("ready_candidate_count") or 0) > 0]),
            "applied_task_count": len([task for task in tasks if task.status == "applied"]),
            "resolved_task_count": len([task for task in tasks if task.status == "resolved"]),
            "follow_up_task_count": follow_up_count,
            "missing_task_count": len(missing_task_ids),
            "average_candidate_count_per_task": round(sum(candidate_counts) / len(tasks), 3) if tasks else None,
            "task_status_counts": _task_status_counts(tasks),
        }
    )


def _candidate_funnel_metrics(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]]) -> dict[str, Any]:
    candidates = [candidate for task in tasks for candidate in candidates_by_task.get(task.task_id, [])]
    ready = [candidate for candidate in candidates if candidate.status in {"ready", "applied"}]
    applied = [candidate for candidate in candidates if candidate.status == "applied" or any(task.selected_candidate_id == candidate.candidate_id for task in tasks)]
    failed = [candidate for candidate in candidates if candidate.status == "failed"]
    local_ready = [candidate for candidate in ready if _candidate_source(candidate) == "local"]
    provider_ready = [candidate for candidate in ready if _candidate_source(candidate) == "provider"]
    local_applied = [candidate for candidate in applied if _candidate_source(candidate) == "local"]
    provider_applied = [candidate for candidate in applied if _candidate_source(candidate) == "provider"]
    source_counts: dict[str, int] = {}
    for candidate in candidates:
        source_counts[candidate.candidate_type] = source_counts.get(candidate.candidate_type, 0) + 1
    return sanitize_metadata(
        {
            "candidate_count": len(candidates),
            "ready_candidate_count": len(ready),
            "local_candidate_count": len([candidate for candidate in candidates if _candidate_source(candidate) == "local"]),
            "provider_candidate_count": len([candidate for candidate in candidates if _candidate_source(candidate) == "provider"]),
            "unknown_candidate_count": len([candidate for candidate in candidates if _candidate_source(candidate) == "unknown"]),
            "applied_candidate_count": len(applied),
            "failed_candidate_count": len(failed),
            "candidate_source_counts": source_counts,
            "adoption_rate": _rate(len(applied), len(ready)),
            "provider_adoption_rate": _rate(len(provider_applied), len(provider_ready)),
            "local_adoption_rate": _rate(len(local_applied), len(local_ready)),
            "applied_candidate_ids": [candidate.candidate_id for candidate in applied],
        }
    )


def _recommendation_adoption_metrics(recommendation_report: dict[str, Any], queues: list[SprintActionQueue]) -> dict[str, Any]:
    actions = [item for item in recommendation_report.get("recommended_actions", []) if isinstance(item, dict)] if isinstance(recommendation_report, dict) else []
    queue_items = [item for queue in queues for item in queue.items if item.recommendation.get("report_hash")]
    executable = [item for item in queue_items if item.safety in {"auto_safe", "provider_safe"}]
    completed = [item for item in executable if item.status == "completed"]
    context_items = [item for item in queue_items if item.action == "save_recommended_context_pack"]
    manual_items = [item for item in queue_items if item.action == "manual_apply_candidate"]
    return sanitize_metadata(
        {
            "recommendation_report_count": 1 if recommendation_report else 0,
            "recommended_task_count": len(actions),
            "top_recommendation_action": actions[0].get("action") if actions else None,
            "recommended_context_pack_count": len([item for item in actions if _context_ref_count(item.get("context_pack_preview")) > 0]),
            "saved_recommended_context_pack_count": len([item for item in context_items if item.status == "completed"]),
            "manual_apply_recommended_count": len(manual_items),
            "recommendation_to_queue_item_count": len(queue_items),
            "completed_recommendation_queue_item_count": len(completed),
            "executable_recommendation_queue_item_count": len(executable),
            "recommendation_adoption_rate": _rate(len(completed), len(executable)),
        }
    )


def _action_queue_metrics(queues: list[SprintActionQueue]) -> dict[str, Any]:
    items = [item for queue in queues for item in queue.items]
    latest = sorted(queues, key=lambda queue: queue.updated_at or queue.created_at, reverse=True)[0] if queues else None
    counts = _item_status_counts(items)
    denominator = counts.get("completed", 0) + counts.get("failed", 0) + counts.get("blocked", 0)
    provider_safe_actions = {"generate_provider_candidates", "refresh_judge_report"}
    provider_skipped = len([item for item in items if item.action in provider_safe_actions and item.status == "skipped"])
    blocked_reasons = _reason_counts([item.error or item.result.get("reason") for item in items if item.status in {"blocked", "failed"}])
    return sanitize_metadata(
        {
            "queue_count": len(queues),
            "latest_queue_id": latest.queue_id if latest else None,
            "latest_status": latest.status if latest else None,
            "action_item_count": len(items),
            "completed_action_count": counts.get("completed", 0),
            "failed_action_count": counts.get("failed", 0),
            "blocked_action_count": counts.get("blocked", 0),
            "manual_required_count": counts.get("manual_required", 0),
            "pending_action_count": counts.get("pending", 0),
            "running_action_count": counts.get("running", 0),
            "provider_skipped_count": provider_skipped,
            "pending_provider_action_count": len([item for item in items if item.action in provider_safe_actions and item.status == "pending"]),
            "execution_success_rate": _rate(counts.get("completed", 0), denominator),
            "blocked_reasons": blocked_reasons,
        }
    )


def _provider_usage_metrics(provider_report: dict[str, Any], tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]]) -> dict[str, Any]:
    applied_count = len([task for task in tasks if task.selected_candidate_id])
    ready_count = len([candidate for task in tasks for candidate in candidates_by_task.get(task.task_id, []) if candidate.status in {"ready", "applied"}])
    operations = {}
    for row in provider_report.get("by_operation", []) if isinstance(provider_report.get("by_operation"), list) else []:
        if isinstance(row, dict):
            operations[str(row.get("operation") or "unknown")] = {
                "call_count": int(row.get("total_calls") or 0),
                "total_tokens": int(row.get("total_tokens") or 0),
            }
    total_tokens = int(provider_report.get("total_tokens") or 0)
    cost = provider_report.get("estimated_cost")
    return sanitize_metadata(
        {
            "provider_call_count": int(provider_report.get("total_calls") or 0),
            "total_tokens": total_tokens,
            "prompt_tokens": int(provider_report.get("prompt_tokens") or 0),
            "completion_tokens": int(provider_report.get("completion_tokens") or 0),
            "estimated_cost": cost if cost is not None else None,
            "currency": provider_report.get("currency"),
            "operations": operations,
            "cost_per_applied_candidate": round(float(cost) / applied_count, 8) if cost is not None and applied_count else None,
            "tokens_per_ready_candidate": round(total_tokens / ready_count, 3) if ready_count else None,
        }
    )


def _quality_delta_metrics(*, sprint: ReviewSprint, tasks: list[ReviewTask], project_document: Any) -> dict[str, Any]:
    baseline_id = _baseline_version_id(sprint, tasks, project_document)
    latest_id = _latest_applied_version_id(tasks, project_document)
    if not latest_id:
        return {"status": "not_available", "reason": "No applied sprint candidate version found.", "baseline_version_id": baseline_id}
    baseline = _version_by_id(project_document, baseline_id) if baseline_id else None
    latest = _version_by_id(project_document, latest_id)
    baseline_quality = _version_quality(baseline)
    latest_quality = _version_quality(latest)
    if not baseline_quality or not latest_quality:
        return {"status": "not_available", "reason": "Quality metadata is missing.", "baseline_version_id": baseline_id, "latest_applied_version_id": latest_id}
    dimensions = sorted(set(baseline_quality.get("dimensions", {})) | set(latest_quality.get("dimensions", {})))
    deltas = {dimension: int(latest_quality.get("dimensions", {}).get(dimension) or 0) - int(baseline_quality.get("dimensions", {}).get(dimension) or 0) for dimension in dimensions}
    overall_delta = int(latest_quality.get("overall") or 0) - int(baseline_quality.get("overall") or 0)
    warning_delta = int(latest_quality.get("warning_count") or 0) - int(baseline_quality.get("warning_count") or 0)
    return sanitize_metadata(
        {
            "baseline_version_id": baseline_id,
            "latest_applied_version_id": latest_id,
            "baseline_quality_overall": baseline_quality.get("overall"),
            "latest_quality_overall": latest_quality.get("overall"),
            "overall_delta": overall_delta,
            "dimension_deltas": deltas,
            "validator_warning_delta": warning_delta,
            "status": "improved" if overall_delta > 0 else ("regressed" if overall_delta < 0 else "unchanged"),
        }
    )


def _manual_decision_metrics(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]], decision_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manual_apply_count = len([task for task in tasks if task.selected_candidate_id])
    followed = 0
    top_ranked = 0
    provider = 0
    local = 0
    overrides = 0
    unknown = 0
    for task in tasks:
        if not task.selected_candidate_id:
            continue
        candidates = candidates_by_task.get(task.task_id, [])
        selected = next((candidate for candidate in candidates if candidate.candidate_id == task.selected_candidate_id), None)
        report = decision_reports.get(task.task_id, {})
        recommended_id = report.get("recommended_candidate_id") if isinstance(report, dict) else None
        if recommended_id:
            if task.selected_candidate_id == recommended_id:
                followed += 1
            else:
                overrides += 1
        else:
            unknown += 1
        if selected and int(selected.rank or 0) == 1:
            top_ranked += 1
        source = _candidate_source(selected) if selected else "unknown"
        if source == "provider":
            provider += 1
        elif source == "local":
            local += 1
    return sanitize_metadata(
        {
            "manual_apply_count": manual_apply_count,
            "applied_from_decision_recommendation_count": followed,
            "applied_from_top_ranked_candidate_count": top_ranked,
            "applied_from_provider_count": provider,
            "applied_from_local_count": local,
            "manual_override_count": overrides,
            "unknown_decision_count": unknown,
        }
    )


def _judge_metrics(
    judge_reports: dict[str, dict[str, Any]],
    tasks: list[ReviewTask],
    decision_reports: dict[str, dict[str, Any]],
    provider_report: dict[str, Any],
) -> dict[str, Any]:
    reports = {task_id: report for task_id, report in judge_reports.items() if isinstance(report, dict) and report}
    completed = {task_id: report for task_id, report in reports.items() if report.get("status") == "completed"}
    stale = {task_id: report for task_id, report in reports.items() if report.get("status") == "stale" or report.get("stale")}
    matched_apply = 0
    apply_with_judge = 0
    disagreements = 0
    high_risk = 0
    for task in tasks:
        report = reports.get(task.task_id, {})
        decision = decision_reports.get(task.task_id, {})
        judge_id = report.get("recommended_candidate_id")
        local_id = decision.get("local_recommended_candidate_id") or decision.get("recommended_candidate_id")
        if judge_id and local_id and judge_id != local_id:
            disagreements += 1
        if task.selected_candidate_id and judge_id:
            apply_with_judge += 1
            if task.selected_candidate_id == judge_id:
                matched_apply += 1
        for score in report.get("candidate_scores", []) if isinstance(report.get("candidate_scores"), list) else []:
            if isinstance(score, dict) and int(score.get("risk") or 0) >= 70:
                high_risk += 1
    judge_tokens = 0
    judge_calls = 0
    for row in provider_report.get("by_operation", []) if isinstance(provider_report.get("by_operation"), list) else []:
        if isinstance(row, dict) and str(row.get("operation") or "") == "provider_review_judge":
            judge_calls += int(row.get("total_calls") or 0)
            judge_tokens += int(row.get("total_tokens") or 0)
    if judge_tokens <= 0:
        judge_tokens = sum(int((report.get("provider_usage") or {}).get("total_tokens") or 0) for report in reports.values() if isinstance(report.get("provider_usage"), dict))
    return sanitize_metadata(
        {
            "judged_task_count": len(completed),
            "stale_judge_count": len(stale),
            "judge_provider_call_count": judge_calls,
            "judge_provider_tokens": judge_tokens,
            "judge_recommendation_match_apply_count": matched_apply,
            "judge_apply_match_rate": _rate(matched_apply, apply_with_judge),
            "judge_local_disagreement_count": disagreements,
            "high_risk_candidate_count": high_risk,
            "task_summaries": [judge_report_summary(report) for report in reports.values()],
        }
    )


def _project_judge_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    judged = 0
    stale = 0
    tokens = 0
    matched = 0
    applied_with_judge = 0
    disagreements = 0
    high_risk = 0
    judged_sprint_count = 0
    for summary in summaries:
        metrics = summary.get("judge_metrics") if isinstance(summary.get("judge_metrics"), dict) else {}
        if not metrics:
            continue
        if int(metrics.get("judged_task_count") or 0) > 0:
            judged_sprint_count += 1
        judged += int(metrics.get("judged_task_count") or 0)
        stale += int(metrics.get("stale_judge_count") or 0)
        tokens += int(metrics.get("judge_provider_tokens") or 0)
        matched += int(metrics.get("judge_recommendation_match_apply_count") or 0)
        disagreements += int(metrics.get("judge_local_disagreement_count") or 0)
        high_risk += int(metrics.get("high_risk_candidate_count") or 0)
        rate = metrics.get("judge_apply_match_rate")
        if rate is not None:
            try:
                denominator = round(int(metrics.get("judge_recommendation_match_apply_count") or 0) / float(rate))
            except (TypeError, ValueError, ZeroDivisionError):
                denominator = 0
            applied_with_judge += max(denominator, int(metrics.get("judge_recommendation_match_apply_count") or 0))
    return sanitize_metadata(
        {
            "judged_sprint_count": judged_sprint_count,
            "judged_task_count": judged,
            "stale_judge_count": stale,
            "judge_provider_tokens": tokens,
            "judge_apply_match_rate": _rate(matched, applied_with_judge),
            "judge_local_disagreement_count": disagreements,
            "high_risk_candidate_count": high_risk,
        }
    )


def _sprint_closeout_metrics(sprint_store: ReviewSprintStore, sprint: ReviewSprint) -> dict[str, Any]:
    closeout = closeout_report_summary(sprint_store.read_closeout_report(sprint.sprint_id, default={}))
    signoff = signoff_summary(sprint_store.read_signoff(sprint.sprint_id, default={}))
    return sanitize_metadata(
        {
            "status": closeout.get("status"),
            "readiness": closeout.get("readiness"),
            "close_allowed": bool(closeout.get("close_allowed", False)),
            "blocker_count": int(closeout.get("blocker_count") or 0),
            "warning_count": int(closeout.get("warning_count") or 0),
            "forced": bool(closeout.get("forced", False) or signoff.get("forced", False)),
            "signed": signoff.get("status") == "signed",
            "signed_at": signoff.get("signed_at"),
            "selected_version_id": signoff.get("selected_version_id") or closeout.get("recommended_final_version_id"),
        }
    )


def _project_closeout_summary(sprint_store: ReviewSprintStore, sprints: list[ReviewSprint]) -> dict[str, Any]:
    closeouts = []
    signoffs = []
    for sprint in sprints:
        closeouts.append(closeout_report_summary(sprint_store.read_closeout_report(sprint.sprint_id, default={})))
        signoffs.append(signoff_summary(sprint_store.read_signoff(sprint.sprint_id, default={})))
    closeouts = [item for item in closeouts if item]
    signed = [item for item in signoffs if item.get("status") == "signed"]
    latest = closeouts[0] if closeouts else {}
    return sanitize_metadata(
        {
            "closeout_report_count": len(closeouts),
            "signed_sprint_count": len(signed),
            "forced_close_count": len([item for item in closeouts if item.get("forced")]) + len([item for item in signed if item.get("forced")]),
            "latest_closeout_status": latest.get("status"),
            "latest_closeout_readiness": latest.get("readiness"),
            "open_blocker_count": sum(int(item.get("blocker_count") or 0) for item in closeouts if item.get("status") not in {"passed", "warning"}),
        }
    )


def _risk_readiness_metrics(
    *,
    overview: dict[str, Any],
    task_throughput: dict[str, Any],
    action_queue_execution: dict[str, Any],
    conflict_report: dict[str, Any],
    tasks: list[ReviewTask],
    queues: list[SprintActionQueue],
    missing_task_ids: list[str],
) -> dict[str, Any]:
    conflict_count = len([item for item in conflict_report.get("conflicts", []) if isinstance(item, dict) and item.get("severity") == "blocking"]) if isinstance(conflict_report, dict) else 0
    open_high_priority = len([task for task in tasks if task.status in {"open", "candidate_ready", "needs_more_work"} and int(task.priority or 0) >= 70])
    stale_count = int(overview.get("stale_task_count") or 0)
    failed_count = int(action_queue_execution.get("failed_action_count") or 0)
    pending_provider = int(action_queue_execution.get("pending_provider_action_count") or 0)
    manual_required = int(action_queue_execution.get("manual_required_count") or 0)
    open_count = int(overview.get("open_task_count") or 0)
    ready_candidates = int(overview.get("ready_candidate_task_count") or 0)
    completion_rate = overview.get("completion_rate")
    warnings: list[str] = []
    if missing_task_ids:
        warnings.append(f"{len(missing_task_ids)} sprint task reference is missing.")
    if conflict_count:
        warnings.append(f"{conflict_count} blocking conflict is present.")
    if open_high_priority:
        warnings.append(f"{open_high_priority} high-priority task is still open.")
    if failed_count:
        warnings.append(f"{failed_count} action queue item failed.")
    if pending_provider:
        warnings.append(f"{pending_provider} provider-safe action is pending.")
    if manual_required:
        warnings.append(f"{manual_required} manual action requires review.")
    if not tasks:
        readiness = "no_data"
    elif stale_count:
        readiness = "stale"
    elif conflict_count or failed_count or missing_task_ids:
        readiness = "blocked"
    elif open_high_priority or manual_required:
        readiness = "needs_review"
    elif ready_candidates == 0 and open_count > 0:
        readiness = "needs_candidates"
    elif open_count == 0 or (completion_rate is not None and float(completion_rate) >= 0.8):
        readiness = "ready_to_close"
    else:
        readiness = "needs_review"
    return sanitize_metadata(
        {
            "readiness": readiness if readiness in READINESS_VALUES else "needs_review",
            "ready_to_close": readiness == "ready_to_close",
            "blocking_conflict_count": conflict_count,
            "open_high_priority_task_count": open_high_priority,
            "stale_task_count": stale_count,
            "failed_action_count": failed_count,
            "pending_provider_action_count": pending_provider,
            "manual_required_apply_count": manual_required,
            "warnings": warnings,
        }
    )


def _dashboard_messages(
    overview: dict[str, Any],
    candidate_funnel: dict[str, Any],
    action_queue_execution: dict[str, Any],
    provider_usage: dict[str, Any],
    quality_delta: dict[str, Any],
    risk_readiness: dict[str, Any],
) -> tuple[list[str], list[str]]:
    highlights = []
    warnings = list(risk_readiness.get("warnings") or [])
    if overview.get("completion_rate") is not None:
        highlights.append(f"Sprint completion is {round(float(overview['completion_rate']) * 100)}%.")
    if candidate_funnel.get("candidate_count"):
        highlights.append(f"{candidate_funnel['candidate_count']} review candidates are available.")
    if action_queue_execution.get("completed_action_count"):
        highlights.append(f"{action_queue_execution['completed_action_count']} action queue item completed.")
    if provider_usage.get("total_tokens"):
        highlights.append(f"Provider usage totals {provider_usage['total_tokens']} tokens.")
    if quality_delta.get("status") == "not_available":
        warnings.append(str(quality_delta.get("reason") or "Quality delta is not available."))
    elif quality_delta.get("overall_delta") is not None:
        delta = int(quality_delta.get("overall_delta") or 0)
        highlights.append(f"Quality overall delta is {delta}.")
    return [sanitize_sensitive_text(item)[:240] for item in highlights[:8]], [sanitize_sensitive_text(item)[:240] for item in warnings[:12]]


def _task_status_counts(tasks: list[ReviewTask]) -> dict[str, int]:
    counts = {"open": 0, "candidate_ready": 0, "applied": 0, "resolved": 0, "needs_more_work": 0, "archived": 0, "stale": 0}
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    return counts


def _item_status_counts(items: list[Any]) -> dict[str, int]:
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "skipped": 0, "blocked": 0, "manual_required": 0, "interrupted": 0}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def _candidate_source(candidate: ReviewCandidate | None) -> str:
    if candidate is None:
        return "unknown"
    if candidate.candidate_type == "provider_review_patch" or bool(candidate.source.get("provider")):
        return "provider"
    if candidate.candidate_type == "local_review_intents":
        return "local"
    return "unknown"


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _context_ref_count(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return len(value.get("asset_refs") or []) + len(value.get("reference_refs") or [])


def _included_task_ids(sprint: ReviewSprint) -> list[str]:
    refs = sorted(sprint.task_refs, key=lambda ref: int(ref.get("order") or 0))
    return [str(ref.get("task_id")) for ref in refs if ref.get("included", True) and str(ref.get("task_id") or "").strip()]


def _reason_counts(values: list[Any]) -> list[dict[str, Any]]:
    buckets: dict[str, int] = {}
    for value in values:
        text = sanitize_sensitive_text(str(value or "").strip())[:240]
        if not text:
            continue
        buckets[text] = buckets.get(text, 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(buckets.items(), key=lambda item: (-item[1], item[0]))[:8]]


def _baseline_version_id(sprint: ReviewSprint, tasks: list[ReviewTask], project_document: Any) -> str | None:
    if sprint.parent_version_id:
        return sprint.parent_version_id
    counts: dict[str, int] = {}
    for task in tasks:
        if task.parent_version_id:
            counts[task.parent_version_id] = counts.get(task.parent_version_id, 0) + 1
    if counts:
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    state = getattr(project_document, "state", None)
    return getattr(state, "selected_version_id", None) or getattr(state, "final_version_id", None) or (getattr(project_document, "versions", [])[:1][0].version_id if getattr(project_document, "versions", []) else None)


def _latest_applied_version_id(tasks: list[ReviewTask], project_document: Any) -> str | None:
    ids = {task.applied_version_id for task in tasks if task.applied_version_id}
    latest = None
    for version in getattr(project_document, "versions", []):
        if version.version_id in ids:
            latest = version.version_id
    return latest


def _version_by_id(project_document: Any, version_id: str | None) -> Any | None:
    if not version_id:
        return None
    for version in getattr(project_document, "versions", []):
        if version.version_id == version_id:
            return version
    return None


def _version_song_plan(project_document: Any, version_id: str | None) -> SongPlan:
    version = _version_by_id(project_document, version_id)
    if version is None:
        raise FileNotFoundError(version_id or "")
    return SongPlan.from_dict(read_json(Path(getattr(version, "output_dir", "") or "") / "data" / "song-plan.json"))


def _version_quality(version: Any | None) -> dict[str, Any] | None:
    if version is None:
        return None
    run_dir = Path(getattr(version, "output_dir", "") or "")
    plan_path = run_dir / "data" / "song-plan.json"
    if not plan_path.exists():
        return None
    try:
        plan = SongPlan.from_dict(read_json(plan_path))
        quality = plan.quality or analyze_song_quality(plan)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    scores = quality.scores
    return {
        "overall": scores.overall,
        "dimensions": {
            "structure": scores.structure,
            "melody": scores.melody,
            "harmony": scores.harmony,
            "arrangement": scores.arrangement,
            "lyric_fit": scores.lyric_fit,
        },
        "warning_count": len(quality.warnings or []),
    }


def _project_quality_trend(versions: list[Any]) -> dict[str, Any]:
    scored = [version for version in versions if getattr(version, "quality_score", None) is not None]
    if not scored:
        return {"status": "not_available", "reason": "No project version quality scores found."}
    first = scored[0]
    latest = scored[-1]
    first_score = int(first.quality_score or 0)
    latest_score = int(latest.quality_score or 0)
    return {
        "first_version_id": first.version_id,
        "latest_version_id": latest.version_id,
        "first_quality_overall": first_score,
        "latest_quality_overall": latest_score,
        "overall_delta": latest_score - first_score,
        "status": "improved" if latest_score > first_score else ("regressed" if latest_score < first_score else "unchanged"),
    }


def _source_hash(value: dict[str, Any]) -> str:
    clean = sanitize_metadata(value)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _task_source_summary(task: ReviewTask, candidates: list[ReviewCandidate], decision_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "status": task.status,
        "priority": task.priority,
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
                "score": candidate.scores.get("combined"),
            }
            for candidate in candidates
        ],
        "decision": {"recommended_candidate_id": decision_report.get("recommended_candidate_id")} if isinstance(decision_report, dict) else {},
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
                "report_hash": item.recommendation.get("report_hash"),
            }
            for item in queue.items
        ],
    }


def _version_source_summary(version: Any) -> dict[str, Any]:
    return {
        "version_id": getattr(version, "version_id", None),
        "parent_version_id": getattr(version, "parent_version_id", None),
        "status": getattr(version, "status", None),
        "quality_score": getattr(version, "quality_score", None),
        "updated_at": getattr(version, "updated_at", None),
    }


def _provider_usage_public(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_calls": report.get("total_calls", 0),
        "prompt_tokens": report.get("prompt_tokens", 0),
        "completion_tokens": report.get("completion_tokens", 0),
        "total_tokens": report.get("total_tokens", 0),
        "estimated_cost": report.get("estimated_cost"),
        "by_operation": [
            {
                "operation": row.get("operation"),
                "total_calls": row.get("total_calls"),
                "total_tokens": row.get("total_tokens"),
            }
            for row in report.get("by_operation", [])
            if isinstance(row, dict)
        ],
    }


def _provider_records_for_tasks(records: list[dict[str, Any]], task_ids: list[str]) -> list[dict[str, Any]]:
    task_id_set = set(task_ids)
    if not task_id_set:
        return []
    filtered = []
    for record in records:
        source_id = str(record.get("source_id") or "")
        group_id = str(record.get("group_id") or "")
        if source_id in task_id_set or group_id in task_id_set:
            filtered.append(record)
    return filtered
