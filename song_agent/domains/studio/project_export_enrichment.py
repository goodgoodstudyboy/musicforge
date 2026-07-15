from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.studio.project_planning_read_models import collect_planning_rule_governance_summary, collect_planning_rule_impact_summary, collect_planning_rule_simulation_summary
from song_agent.domains.studio.project_repository import BLOCKED_ASSET_METADATA_KEYS, ProjectDocument
from song_agent.domains.studio.projectio import read_json


def build_project_summary(project_dir: Path, document: ProjectDocument) -> dict[str, Any]:
    project_id = document.state.project_id
    return {
        "review_tasks": _collect_project_review_tasks(project_dir),
        "review_sprints": _collect_project_review_sprints(project_dir),
        "review_metrics_summary": _collect_project_review_metrics_summary(project_dir),
        "acceptance_fix_sprint_summary": _collect_project_acceptance_fix_sprint_summary(project_id),
        "acceptance_fix_plan_summary": _collect_project_acceptance_fix_plan_summary(project_id),
        "acceptance_fix_plan_review_summary": _collect_project_acceptance_fix_plan_review_summary(project_id),
        "acceptance_kb_summary": _collect_project_acceptance_kb_summary(project_id),
        "planning_rule_simulation_summary": _collect_project_planning_rule_simulation_summary(project_id),
        "planning_rule_governance_summary": _collect_project_planning_rule_governance_summary(project_id),
        "planning_rule_impact_summary": _collect_project_planning_rule_impact_summary(project_id),
        "delivery_qa_summary": _collect_project_delivery_qa_summary(project_dir),
        "delivery_signoff_summary": _collect_project_delivery_signoff_summary(project_dir),
    }


def _collect_project_review_tasks(project_dir: Path) -> list[dict[str, Any]]:
    from song_agent.domains.studio.prompt_templates import PromptTemplateStore
    from song_agent.domains.quality.review_judge import REVIEW_JUDGE_TEMPLATE_ID, judge_report_summary, mark_judge_report_stale, read_judge_report_with_stale
    from song_agent.domains.quality.review_tasks import ReviewTaskStore, review_candidate_source_breakdown, review_decision_summary, review_task_summary

    store = ReviewTaskStore(project_dir)
    template_store = PromptTemplateStore(project_dir.parent.parent / "prompt-templates.json")
    tasks = store.list_tasks(include_archived=True)
    summaries: list[dict[str, Any]] = []
    for task in tasks:
        selected = None
        if task.selected_candidate_id:
            try:
                selected = store.read_candidate(task.task_id, task.selected_candidate_id)
            except (OSError, ValueError, TypeError, FileNotFoundError):
                selected = None
        summary = review_task_summary(task, selected)
        candidates = store.list_candidates(task.task_id)
        try:
            decision_report = store.read_decision_report(task.task_id)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            decision_report = {}
        try:
            template_id = str((store.read_judge_report(task.task_id, default={}) or {}).get("template_id") or REVIEW_JUDGE_TEMPLATE_ID)
            template = template_store.get_template(template_id)
            parent_plan = _project_version_song_plan(project_dir, task.parent_version_id)
            judge_report = read_judge_report_with_stale(store, task, candidates=candidates, parent_plan=parent_plan, template=template)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            try:
                raw_report = store.read_judge_report(task.task_id, default={})
            except (OSError, ValueError, TypeError, FileNotFoundError):
                raw_report = {}
            judge_report = mark_judge_report_stale(raw_report, stale=True) if raw_report else {}
        summary["candidate_count"] = int(task.counts.get("candidate_count") or 0)
        summary["ready_candidate_count"] = int(task.counts.get("ready_candidate_count") or 0)
        summary["provider_summary"] = review_candidate_source_breakdown(candidates)
        summary["decision_report"] = review_decision_summary(decision_report)
        summary["judge_summary"] = judge_report_summary(judge_report)
        summary["priority"] = task.priority
        summaries.append(_sanitize_asset_metadata(summary))
    return sorted(summaries, key=lambda item: str(item.get("task_id") or ""))


def _project_version_song_plan(project_dir: Path, version_id: str) -> Any:
    from song_agent.domains.creation.schemas.song import SongPlan

    versions_path = project_dir / "versions.json"
    data = read_json(versions_path)
    for version in data.get("versions", []) if isinstance(data, dict) else []:
        if isinstance(version, dict) and version.get("version_id") == version_id:
            return SongPlan.from_dict(read_json(Path(str(version.get("output_dir") or "")) / "data" / "song-plan.json"))
    raise FileNotFoundError(version_id)


def _collect_project_review_sprints(project_dir: Path) -> list[dict[str, Any]]:
    from song_agent.domains.quality.review_sprints import ReviewSprintStore, review_sprint_export_summary
    from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore, action_queue_collection_summary
    from song_agent.domains.quality.review_sprint_metrics import ReviewMetricsStore, sprint_metrics_summary
    from song_agent.domains.quality.review_sprint_closeout import closeout_report_summary, signoff_summary

    store = ReviewSprintStore(project_dir)
    metrics_store = ReviewMetricsStore(project_dir)
    sprints = store.list_sprints(include_archived=True)
    summaries = []
    for sprint in sprints:
        summary = store.read_summary(sprint.sprint_id, default={})
        conflict_report = store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = store.read_recommendation_report(sprint.sprint_id, default={})
        judge_summary = store.read_judge_summary(sprint.sprint_id, default={})
        queue_store = ReviewSprintActionQueueStore(store.sprint_dir(sprint.sprint_id))
        queue_summary = action_queue_collection_summary(queue_store.list_queues(include_archived=True))
        closeout_summary = closeout_report_summary(store.read_closeout_report(sprint.sprint_id, default={}))
        signoff = signoff_summary(store.read_signoff(sprint.sprint_id, default={}))
        payload = review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, queue_summary, judge_summary, closeout_summary, signoff)
        metrics_summary = sprint_metrics_summary(metrics_store.read_sprint_metrics(sprint.sprint_id, default={}))
        if metrics_summary:
            payload["metrics_summary"] = metrics_summary
        summaries.append(payload)
    return sorted((_sanitize_asset_metadata(item) for item in summaries), key=lambda item: str(item.get("sprint_id") or ""))


def _collect_project_review_metrics_summary(project_dir: Path) -> dict[str, Any]:
    from song_agent.domains.quality.review_sprint_metrics import ReviewMetricsStore, project_review_metrics_summary

    try:
        store = ReviewMetricsStore(project_dir)
        return _sanitize_asset_metadata(project_review_metrics_summary(store.read_project_metrics(default={})))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _collect_project_acceptance_fix_sprint_summary(project_id: str) -> dict[str, Any]:
    from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixSprintStore, latest_fix_sprint_summary

    try:
        return _sanitize_asset_metadata(latest_fix_sprint_summary(AcceptanceFixSprintStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_acceptance_fix_plan_summary(project_id: str) -> dict[str, Any]:
    from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlanningStore, latest_fix_plan_summary

    try:
        return _sanitize_asset_metadata(latest_fix_plan_summary(AcceptanceFixPlanningStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_acceptance_fix_plan_review_summary(project_id: str) -> dict[str, Any]:
    from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStore, latest_fix_plan_review_summary

    try:
        return _sanitize_asset_metadata(latest_fix_plan_review_summary(AcceptanceFixPlanReviewStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_acceptance_kb_summary(project_id: str) -> dict[str, Any]:
    from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseStore

    try:
        return _sanitize_asset_metadata(AcceptanceKnowledgeBaseStore().summary(project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_planning_rule_simulation_summary(project_id: str) -> dict[str, Any]:
    try:
        return _sanitize_asset_metadata(collect_planning_rule_simulation_summary(project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_planning_rule_governance_summary(project_id: str) -> dict[str, Any]:
    try:
        return _sanitize_asset_metadata(collect_planning_rule_governance_summary(project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_planning_rule_impact_summary(project_id: str) -> dict[str, Any]:
    try:
        return _sanitize_asset_metadata(collect_planning_rule_impact_summary(project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_delivery_qa_summary(project_dir: Path) -> dict[str, Any]:
    from song_agent.domains.delivery.delivery_qa import delivery_qa_summary

    try:
        return _sanitize_asset_metadata(delivery_qa_summary(read_json(project_dir / "delivery-qa.json")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _collect_project_delivery_signoff_summary(project_dir: Path) -> dict[str, Any]:
    from song_agent.domains.delivery.delivery_qa import delivery_signoff_summary

    try:
        return _sanitize_asset_metadata(delivery_signoff_summary(read_json(project_dir / "delivery-signoff.json")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "not_signed"}


def _sanitize_asset_metadata(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=BLOCKED_ASSET_METADATA_KEYS)
