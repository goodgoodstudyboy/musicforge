# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from collections.abc import Sequence as Sequence
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
from pathlib import Path as Path
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

count = _make_deferred_global('count')
dimension = _make_deferred_global('dimension')
reason = _make_deferred_global('reason')
ref = _make_deferred_global('ref')
task_id = _make_deferred_global('task_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global count, dimension, reason, ref, task_id
    count = namespace.get('count', count)
    dimension = namespace.get('dimension', dimension)
    reason = namespace.get('reason', reason)
    ref = namespace.get('ref', ref)
    task_id = namespace.get('task_id', task_id)
    _bind_deferred_defaults(namespace)


SPRINT_METRICS_SCHEMA_VERSION = 1
PROJECT_REVIEW_METRICS_SCHEMA_VERSION = 1
READINESS_VALUES = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}




def _provider_usage_metrics(provider_report: DomainDocument, tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]]) -> DomainDocument:
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

def _quality_delta_metrics(*, sprint: ReviewSprint, tasks: list[ReviewTask], project_document: object) -> DomainDocument:
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

def _manual_decision_metrics(tasks: list[ReviewTask], candidates_by_task: dict[str, list[ReviewCandidate]], decision_reports: dict[str, DomainDocument]) -> DomainDocument:
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
    judge_reports: dict[str, DomainDocument],
    tasks: list[ReviewTask],
    decision_reports: dict[str, DomainDocument],
    provider_report: DomainDocument,
) -> DomainDocument:
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

def _project_judge_summary(summaries: list[DomainDocument]) -> DomainDocument:
    judged = 0
    stale = 0
    tokens = 0
    matched = 0
    applied_with_judge = 0
    disagreements = 0
    high_risk = 0
    judged_sprint_count = 0
    for summary in summaries:
        metrics = _as_document(summary.get("judge_metrics"))
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

def _sprint_closeout_metrics(sprint_store: ReviewSprintStore, sprint: ReviewSprint) -> DomainDocument:
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

def _project_closeout_summary(sprint_store: ReviewSprintStore, sprints: list[ReviewSprint]) -> DomainDocument:
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
    overview: DomainDocument,
    task_throughput: DomainDocument,
    action_queue_execution: DomainDocument,
    conflict_report: DomainDocument,
    tasks: list[ReviewTask],
    queues: list[SprintActionQueue],
    missing_task_ids: list[str],
) -> DomainDocument:
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
    overview: DomainDocument,
    candidate_funnel: DomainDocument,
    action_queue_execution: DomainDocument,
    provider_usage: DomainDocument,
    quality_delta: DomainDocument,
    risk_readiness: DomainDocument,
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

def _item_status_counts(items: Sequence[object]) -> dict[str, int]:
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

def _context_ref_count(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    return len(value.get("asset_refs") or []) + len(value.get("reference_refs") or [])

def _included_task_ids(sprint: ReviewSprint) -> list[str]:
    refs = sorted(sprint.task_refs, key=lambda ref: int(ref.get("order") or 0))
    return [str(ref.get("task_id")) for ref in refs if ref.get("included", True) and str(ref.get("task_id") or "").strip()]

def _reason_counts(values: list[object]) -> list[DomainDocument]:
    buckets: dict[str, int] = {}
    for value in values:
        text = sanitize_sensitive_text(str(value or "").strip())[:240]
        if not text:
            continue
        buckets[text] = buckets.get(text, 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(buckets.items(), key=lambda item: (-item[1], item[0]))[:8]]

def _baseline_version_id(sprint: ReviewSprint, tasks: list[ReviewTask], project_document: object) -> str | None:
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

def _latest_applied_version_id(tasks: list[ReviewTask], project_document: object) -> str | None:
    ids = {task.applied_version_id for task in tasks if task.applied_version_id}
    latest = None
    for version in getattr(project_document, "versions", []):
        if version.version_id in ids:
            latest = version.version_id
    return latest

def _version_by_id(project_document: object, version_id: str | None) -> object | None:
    if not version_id:
        return None
    for version in getattr(project_document, "versions", []):
        if version.version_id == version_id:
            return version
    return None

def _version_song_plan(project_document: object, version_id: str | None) -> SongPlan:
    version = _version_by_id(project_document, version_id)
    if version is None:
        raise FileNotFoundError(version_id or "")
    return SongPlan.from_dict(read_json(Path(getattr(version, "output_dir", "") or "") / "data" / "song-plan.json"))

def _version_quality(version: object | None) -> DomainDocument | None:
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
    scores = quality.scores or score_song_plan(plan)
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

def _project_quality_trend(versions: list[object]) -> DomainDocument:
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

def _source_hash(value: DomainDocument) -> str:
    clean = sanitize_metadata(value)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
