# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, score_song_plan as score_song_plan
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, now_iso as now_iso
from song_agent.domains.creation.provider_usage import build_provider_usage_report as build_provider_usage_report
from song_agent.domains.studio.prompt_templates import PromptTemplateStore as PromptTemplateStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_judge import REVIEW_JUDGE_TEMPLATE_ID as REVIEW_JUDGE_TEMPLATE_ID, judge_report_summary as judge_report_summary, mark_judge_report_stale as mark_judge_report_stale, read_judge_report_with_stale as read_judge_report_with_stale
from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore as ReviewSprintActionQueueStore, SprintActionQueue as SprintActionQueue
from song_agent.domains.quality.review_sprint_closeout import closeout_report_summary as closeout_report_summary, signoff_summary as signoff_summary
from song_agent.domains.quality.review_sprints import ReviewSprint as ReviewSprint, ReviewSprintStore as ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate as ReviewCandidate, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan


SPRINT_METRICS_SCHEMA_VERSION = 1
PROJECT_REVIEW_METRICS_SCHEMA_VERSION = 1
READINESS_VALUES = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}


class ReviewMetricsStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()

    def sprint_metrics_path(self, sprint_id: str) -> Path:
        return self.project_dir / "review-sprints" / sprint_id / "metrics-report.json"

    def read_sprint_metrics(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.sprint_metrics_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def write_sprint_metrics(self, sprint_id: str, report: DomainDocument) -> DomainDocument:
        path = self.sprint_metrics_path(sprint_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = sanitize_metadata(_as_document(report))
        write_json(path, clean)
        return clean

    def project_metrics_path(self) -> Path:
        return self.project_dir / "review-metrics.json"

    def read_project_metrics(self, default: DomainDocument | None = None) -> DomainDocument:
        path = self.project_metrics_path()
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(path)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def write_project_metrics(self, report: DomainDocument) -> DomainDocument:
        clean = sanitize_metadata(_as_document(report))
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
    provider_usage_records: list[DomainDocument] | None = None,
    now: str | None = None,
) -> DomainDocument:
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
    provider_usage_records: list[DomainDocument] | None = None,
    now: str | None = None,
) -> DomainDocument:
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
    project_state: Any = getattr(project_document, "state", {})
    report = {
        "schema_version": PROJECT_REVIEW_METRICS_SCHEMA_VERSION,
        "project_id": project_id,
        "created_at": now,
        "source_hash": _source_hash(
            {
                "project": project_state.to_dict() if hasattr(project_state, "to_dict") else {},
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


def sprint_metrics_summary(report: DomainDocument | None) -> DomainDocument:
    if not isinstance(report, dict) or not report:
        return {}
    overview = _as_document(report.get("overview"))
    candidate = _as_document(report.get("candidate_funnel"))
    queue = _as_document(report.get("action_queue_execution"))
    provider = _as_document(report.get("provider_usage"))
    quality = _as_document(report.get("quality_delta"))
    readiness = _as_document(report.get("risk_readiness"))
    warnings = _as_list(report.get("warnings"))
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
            "judge_metrics": _as_document(report.get("judge_metrics")),
            "closeout": _as_document(report.get("closeout")),
        }
    )


def project_review_metrics_summary(report: DomainDocument | None) -> DomainDocument:
    if not isinstance(report, dict) or not report:
        return {}
    quality_trend = _as_document(report.get("quality_trend"))
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
            "judge_summary": _as_document(report.get("judge_summary")),
            "closeout_summary": _as_document(report.get("closeout_summary")),
        }
    )


def _sprint_sources(
    *,
    sprint: ReviewSprint,
    sprint_store: ReviewSprintStore,
    task_store: ReviewTaskStore,
    queue_store: ReviewSprintActionQueueStore,
    project_document: Any,
) -> ImplementationDocument:
    tasks: list[ReviewTask] = []
    missing: list[str] = []
    candidates_by_task: dict[str, list[ReviewCandidate]] = {}
    decision_reports: dict[str, ImplementationDocument] = {}
    judge_reports: dict[str, ImplementationDocument] = {}
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


def _overview_metrics(sprint: ReviewSprint, tasks: list[ReviewTask], missing_task_ids: list[str]) -> ImplementationDocument:
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


def _task_throughput_metrics(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]], missing_task_ids: list[str]) -> ImplementationDocument:
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


def _candidate_funnel_metrics(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]]) -> ImplementationDocument:
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


def _recommendation_adoption_metrics(recommendation_report: ImplementationDocument, queues: list[SprintActionQueue]) -> ImplementationDocument:
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


def _action_queue_metrics(queues: list[SprintActionQueue]) -> ImplementationDocument:
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


from song_agent.domains.quality import v142_rsm_readiness as _v142_rsm_readiness
from song_agent.domains.quality.v142_rsm_readiness import (
    _provider_usage_metrics,
    _quality_delta_metrics,
    _manual_decision_metrics,
    _judge_metrics,
    _project_judge_summary,
    _sprint_closeout_metrics,
    _project_closeout_summary,
    _risk_readiness_metrics,
    _dashboard_messages,
    _task_status_counts,
    _item_status_counts,
    _candidate_source,
    _rate,
    _context_ref_count,
    _included_task_ids,
    _reason_counts,
    _baseline_version_id,
    _latest_applied_version_id,
    _version_by_id,
    _version_song_plan,
    _version_quality,
    _project_quality_trend,
    _source_hash,
)
from song_agent.domains.quality import v142_rsm_evidence as _v142_rsm_evidence
from song_agent.domains.quality.v142_rsm_evidence import _task_source_summary, _queue_source_summary, _version_source_summary, _provider_usage_public, _provider_records_for_tasks

_v142_rsm_readiness.bind_globals(globals())
_v142_rsm_evidence.bind_globals(globals())
