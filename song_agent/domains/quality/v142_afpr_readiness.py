# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlan as AcceptanceFixPlan, AcceptanceFixPlanningStore as AcceptanceFixPlanningStore, fix_plan_summary as fix_plan_summary
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixItem as AcceptanceFixItem, AcceptanceFixSprint as AcceptanceFixSprint, AcceptanceFixSprintStore as AcceptanceFixSprintStore, acceptance_fix_closeout_summary as acceptance_fix_closeout_summary, fix_sprint_summary as fix_sprint_summary
from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseStore as AcceptanceKnowledgeBaseStore, knowledge_entry_summary as knowledge_entry_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import ReviewTaskStore as ReviewTaskStore

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

AcceptanceFixPlanReview = _make_deferred_global('AcceptanceFixPlanReview')
AcceptanceFixPlanReviewError = _make_deferred_global('AcceptanceFixPlanReviewError')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
entry_id = _make_deferred_global('entry_id')
hint = _make_deferred_global('hint')
status = _make_deferred_global('status')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceFixPlanReview, AcceptanceFixPlanReviewError, _LOCKS_GUARD, entry_id, hint, status
    AcceptanceFixPlanReview = namespace.get('AcceptanceFixPlanReview', AcceptanceFixPlanReview)
    AcceptanceFixPlanReviewError = namespace.get('AcceptanceFixPlanReviewError', AcceptanceFixPlanReviewError)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    entry_id = namespace.get('entry_id', entry_id)
    hint = namespace.get('hint', hint)
    status = namespace.get('status', status)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_FIX_PLAN_REVIEW_SCHEMA_VERSION = "acceptance_fix_plan_review.v1"
ACCEPTANCE_FIX_PLAN_REVIEW_RULES_VERSION = "acceptance_fix_plan_review_rules.v1"
REVIEW_STATUSES = {"ready", "warning", "blocked", "stale", "archived"}
REVIEW_READY_STATUSES = {"ready", "warning"}
REVIEW_BLOCKED_MESSAGE = "Acceptance Fix Plan Outcome Review requires a used plan with a closed Fix Sprint, delta report, and closeout report."
_LOCKS: dict[str, threading.RLock] = {}




def _review_summary(plan: AcceptanceFixPlan, sprint: AcceptanceFixSprint, items: list[AcceptanceFixItem], delta: DomainDocument, closeout: DomainDocument, item_outcomes: list[DomainDocument]) -> DomainDocument:
    delta_summary = _as_document(delta.get("summary"))
    statuses = [str(item.get("outcome", {}).get("evidence_status") or "") for item in item_outcomes if isinstance(item.get("outcome"), dict)]
    warnings = []
    open_items = [item for item in items if item.status not in {"fixed", "closed", "waived"}]
    waived_items = [item for item in items if item.status == "waived"]
    fixed_items = [item for item in items if item.status in {"fixed", "closed"}]
    score = _plan_effectiveness_score(delta_summary, items, closeout, item_outcomes)
    if closeout.get("forced"):
        warnings.append("force_closed")
    if waived_items:
        warnings.append("waived_items_present")
    if open_items:
        warnings.append("open_items_present")
    manual_accepted_count = _int(delta_summary.get("manual_accepted_count"), 0)
    synthetic_accepted_count = _int(delta_summary.get("synthetic_accepted_count"), 0)
    manual_review_count = _int(delta_summary.get("manual_review_count"), 0)
    synthetic_review_count = _int(delta_summary.get("synthetic_review_count"), 0)
    manual_recheck_confirmed = manual_accepted_count > 0 or manual_review_count > 0
    synthetic_only = synthetic_accepted_count > 0 and manual_accepted_count == 0 and manual_review_count == 0
    if synthetic_only:
        warnings.append("synthetic_only_recheck")
    ranking = _ranking_alignment_score(plan.planned_items, item_outcomes)
    helpfulness = _overall_kb_helpfulness(item_outcomes)
    return sanitize_metadata(
        {
            "planned_item_count": len(plan.planned_items),
            "executed_item_count": len([item for item in items if item.source.get("source_type") == "planned_item"]),
            "resolved_item_count": len(fixed_items),
            "waived_item_count": len(waived_items),
            "open_item_count": len(open_items),
            "plan_effectiveness_score": score,
            "ranking_alignment_score": ranking,
            "kb_evidence_helpfulness": helpfulness,
            "supported_item_count": statuses.count("supported"),
            "unsupported_item_count": statuses.count("unsupported"),
            "unknown_item_count": statuses.count("unknown") + statuses.count("not_executed"),
            "warning_count": len(warnings) + sum(1 for item in item_outcomes if item.get("warnings")),
            "manual_recheck_confirmed": manual_recheck_confirmed,
            "synthetic_only": synthetic_only,
            "manual_accepted_count": manual_accepted_count,
            "synthetic_accepted_count": synthetic_accepted_count,
            "manual_review_count": manual_review_count,
            "synthetic_review_count": synthetic_review_count,
            "delta_status": delta_summary.get("status"),
            "closeout_status": closeout.get("status"),
            "warnings": warnings,
        }
    )

def _calibration_hints(plan: AcceptanceFixPlan, item_outcomes: list[DomainDocument], summary: DomainDocument) -> list[DomainDocument]:
    hints: list[object] = []
    for item in item_outcomes:
        outcome = _as_document(item.get("outcome"))
        planning_score = _int(item.get("planning_score"), 0)
        if planning_score >= 80 and outcome.get("evidence_status") in {"unsupported", "unknown", "not_executed"}:
            hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "deprioritize_pattern", "severity": "warning", "planned_item_id": item.get("planned_item_id"), "reason": "High-score planned item did not produce supported evidence.", "suggestion": "Review issue weighting and KB match quality before using similar high-score items again."})
        if item.get("warnings"):
            hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "require_stronger_evidence", "severity": "note", "planned_item_id": item.get("planned_item_id"), "reason": "Planned item required waiver, force close, or incomplete evidence.", "suggestion": "Prefer manual recheck evidence before treating this pattern as reliable."})
    if summary.get("ranking_alignment_score", 100) < 60:
        hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "ranking_alignment_low", "severity": "warning", "reason": "Observed outcomes do not align with planning score order.", "suggestion": "Compare low-score supported items against high-score unknown items before the next plan."})
    if summary.get("kb_evidence_helpfulness") in {"negative", "missing"} and int(summary.get("planned_item_count") or 0):
        hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "kb_helpfulness_low", "severity": "warning", "reason": "KB evidence did not clearly support the plan outcome.", "suggestion": "Refresh KB only from non-stale closed sprints and avoid over-weighting weak matches."})
    return [sanitize_metadata({**hint, "suggestion": _bounded(hint.get("suggestion"), 400), "reason": _bounded(hint.get("reason"), 300)}) for hint in hints[:12]]

def _plan_effectiveness_score(delta_summary: DomainDocument, items: list[AcceptanceFixItem], closeout: DomainDocument, item_outcomes: list[DomainDocument]) -> int:
    score = 50
    if delta_summary.get("status") == "improved":
        score += 20
    if str(delta_summary.get("after_readiness") or "") in {"ready", "watch"}:
        score += 10
    if items and all(item.status in {"fixed", "closed", "waived"} for item in items):
        score += 10
    rating_delta = _float(delta_summary.get("rating_delta"))
    if rating_delta is not None:
        if rating_delta >= 2:
            score += 8
        elif rating_delta >= 1:
            score += 5
        elif rating_delta < 0:
            score -= 8
    issue_delta = _int_or_none(delta_summary.get("issue_count_delta"))
    if issue_delta is not None:
        if issue_delta <= -2:
            score += 8
        elif issue_delta == -1:
            score += 5
        elif issue_delta > 0:
            score -= 8
    if _int(delta_summary.get("accepted_delta"), 0) > 0:
        score += 5
    if delta_summary.get("status") == "regressed":
        score -= 15
    if any(item.status not in {"fixed", "closed", "waived"} for item in items):
        score -= 12
    if any(item.status == "waived" for item in items):
        score -= 8
    if closeout.get("forced"):
        score -= 10
    supported = sum(1 for item in item_outcomes if isinstance(item.get("outcome"), dict) and item["outcome"].get("evidence_status") == "supported")
    unsupported = sum(1 for item in item_outcomes if isinstance(item.get("outcome"), dict) and item["outcome"].get("evidence_status") == "unsupported")
    score += min(10, supported * 3)
    score -= min(10, unsupported * 5)
    return max(0, min(100, score))

def _ranking_alignment_score(planned_items: list[DomainDocument], item_outcomes: list[DomainDocument]) -> int:
    if len(planned_items) <= 1:
        return 100
    outcome_by_id = {str(item.get("planned_item_id") or ""): item for item in item_outcomes}
    pairs = []
    for planned in planned_items:
        planned_id = str(planned.get("planned_item_id") or "")
        outcome = outcome_by_id.get(planned_id, {})
        outcome_data = _as_document(outcome.get("outcome"))
        pairs.append((_int(planned.get("planning_score"), 0), _int(outcome_data.get("observed_effectiveness_score"), 0)))
    inversions = 0
    total = 0
    for left in range(len(pairs)):
        for right in range(left + 1, len(pairs)):
            total += 1
            if pairs[left][0] > pairs[right][0] and pairs[left][1] < pairs[right][1]:
                inversions += 1
            elif pairs[left][0] < pairs[right][0] and pairs[left][1] > pairs[right][1]:
                inversions += 1
    if not total:
        return 100
    return max(0, min(100, int(round(100 - (inversions / total) * 100))))

def _evidence_status(item: AcceptanceFixItem | None, delta_summary: DomainDocument, kb_ids: list[str], kb_summaries: dict[str, DomainDocument], task_statuses: list[str], forced: bool) -> str:
    if item is None:
        return "not_executed"
    if item.status not in {"fixed", "closed", "waived"}:
        return "not_executed"
    if delta_summary.get("status") == "regressed":
        return "unsupported"
    if item.status == "waived" or forced:
        return "mixed"
    kb_effective = any(kb_summaries.get(entry_id, {}).get("outcome_status") == "effective" for entry_id in kb_ids)
    kb_mixed = any(kb_summaries.get(entry_id, {}).get("outcome_status") == "mixed" for entry_id in kb_ids)
    tasks_closed = not task_statuses or all(status in {"resolved", "archived"} for status in task_statuses)
    if delta_summary.get("status") == "improved" and tasks_closed and (kb_effective or not kb_ids):
        return "supported"
    if delta_summary.get("status") == "improved" and (kb_mixed or kb_ids):
        return "mixed"
    if delta_summary.get("status") in {"unchanged", "incomplete"}:
        return "unknown"
    return "unknown"

def _item_effectiveness_score(item: AcceptanceFixItem | None, delta_summary: DomainDocument, evidence_status: str, task_statuses: list[str], forced: bool) -> int:
    score = 0
    if evidence_status == "supported":
        score = 72
    elif evidence_status == "mixed":
        score = 48
    elif evidence_status == "unknown":
        score = 30
    elif evidence_status == "unsupported":
        score = 10
    elif evidence_status == "not_executed":
        score = 0
    rating_delta = _float(delta_summary.get("rating_delta"))
    if rating_delta is not None and rating_delta >= 2:
        score += 10
    elif rating_delta is not None and rating_delta >= 1:
        score += 5
    if _int(delta_summary.get("accepted_delta"), 0) > 0:
        score += 6
    issue_delta = _int_or_none(delta_summary.get("issue_count_delta"))
    if issue_delta is not None and issue_delta < 0:
        score += 6
    if item and item.status == "waived":
        score -= 10
    if forced:
        score -= 8
    if task_statuses and not all(status in {"resolved", "archived"} for status in task_statuses):
        score -= 10
    return max(0, min(100, score))

def _observed_status(evidence_status: str, score: int) -> str:
    if evidence_status == "supported" and score >= 65:
        return "effective"
    if evidence_status in {"mixed", "supported"}:
        return "mixed"
    if evidence_status == "unsupported":
        return "ineffective"
    return "unknown"

def _kb_helpfulness(evidence_status: str, kb_ids: list[str]) -> str:
    if not kb_ids:
        return "missing"
    return {"supported": "helpful", "mixed": "mixed", "unsupported": "misleading", "unknown": "neutral", "not_executed": "unknown"}.get(evidence_status, "unknown")

def _overall_kb_helpfulness(item_outcomes: list[DomainDocument]) -> str:
    values = [str((_as_document(item.get("outcome"))).get("kb_evidence_helpfulness") or "missing") for item in item_outcomes]
    if not values or all(value == "missing" for value in values):
        return "missing"
    helpful = values.count("helpful")
    mixed = values.count("mixed")
    misleading = values.count("misleading")
    if helpful and not misleading:
        return "positive" if not mixed else "mixed_positive"
    if misleading and misleading >= helpful:
        return "negative"
    return "neutral"

def _task_statuses(item: AcceptanceFixItem | None, project_store: ProjectStore) -> list[str]:
    if not item or not item.review_task_id or not item.target.get("project_id"):
        return []
    try:
        task = ReviewTaskStore(project_store.project_dir(str(item.target.get("project_id")))).read_task(str(item.review_task_id))
    except Exception:
        return ["missing"]
    return [str(task.status or "missing")]

def _song_delta_status(delta: DomainDocument, planned_or_item: DomainDocument) -> str:
    target = _as_document(planned_or_item.get("target"))
    song_id = str(target.get("song_id") or "")
    for row in delta.get("song_deltas", []) if isinstance(delta.get("song_deltas"), list) else []:
        if str(row.get("song_id") or "") != song_id:
            continue
        issue_delta = _int(row.get("issue_delta"), 0)
        before_rating = _float(row.get("before_rating"))
        after_rating = _float(row.get("after_rating"))
        if after_rating is not None and before_rating is not None and after_rating > before_rating:
            return "improved"
        if issue_delta < 0:
            return "improved"
        if after_rating is not None and before_rating is not None and after_rating < before_rating:
            return "regressed"
        if issue_delta > 0:
            return "regressed"
        return "unchanged"
    summary = _as_document(delta.get("summary"))
    return str(summary.get("status") or "unknown")

def _plan_source(plan: AcceptanceFixPlan) -> DomainDocument:
    return sanitize_metadata({"plan_id": plan.plan_id, "status": plan.status, "scope": plan.scope, "source": plan.source, "summary": plan.summary, "planned_items": plan.planned_items, "strategy": plan.strategy, "warnings": plan.warnings, "execution": plan.execution})

def _sprint_source(sprint: AcceptanceFixSprint) -> DomainDocument:
    return sanitize_metadata({"fix_sprint_id": sprint.fix_sprint_id, "status": sprint.status, "scope": sprint.scope, "source": sprint.source, "settings": sprint.settings, "counts": sprint.counts, "recheck": sprint.recheck, "delta_summary": sprint.delta_summary, "closeout_summary": sprint.closeout_summary})

def _item_source(item: AcceptanceFixItem) -> DomainDocument:
    return sanitize_metadata({"item_id": item.item_id, "status": item.status, "priority": item.priority, "severity": item.severity, "source": item.source, "target": item.target, "evidence": item.evidence, "review_task_id": item.review_task_id, "resolution": item.resolution})

def _delta_source(delta: DomainDocument) -> DomainDocument:
    return sanitize_metadata({"source": _as_document(delta.get("source")), "recheck": _as_document(delta.get("recheck")), "summary": _as_document(delta.get("summary")), "song_deltas": _as_list(delta.get("song_deltas")), "issue_deltas": _as_list(delta.get("issue_deltas"))})

def _closeout_source(closeout: DomainDocument) -> DomainDocument:
    return sanitize_metadata({"status": closeout.get("status"), "forced": bool(closeout.get("forced", False)), "summary": _as_document(closeout.get("summary")), "checks": _as_list(closeout.get("checks"))})

def _review_matches_project(review: AcceptanceFixPlanReview, project_id: str) -> bool:
    if review.scope.get("project_id") == project_id:
        return True
    for item in review.item_outcomes:
        target = _as_document(item.get("target"))
        if target.get("project_id") == project_id:
            return True
    return False

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _bounded(value: object, limit: int = 300) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{6}}", text):
        raise AcceptanceFixPlanReviewError(f"Invalid {prefix} id.")
    return text

def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]

def _append_event(path: Path, event: str, payload: DomainDocument | None = None, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"timestamp": now or now_iso(), "event": event, **(payload or {})})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
