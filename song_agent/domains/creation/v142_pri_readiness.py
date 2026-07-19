# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReview as AcceptanceFixPlanReview, AcceptanceFixPlanReviewStore as AcceptanceFixPlanReviewStore, fix_plan_review_summary as fix_plan_review_summary
from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlan as AcceptanceFixPlan, AcceptanceFixPlanningStore as AcceptanceFixPlanningStore, fix_plan_summary as fix_plan_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.creation.planning_rule_governance import PlanningRuleGovernanceStore as PlanningRuleGovernanceStore, governance_summary as governance_summary
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text

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

PlanningRuleImpactError = _make_deferred_global('PlanningRuleImpactError')
PlanningRuleImpactReport = _make_deferred_global('PlanningRuleImpactReport')
PlanningRuleImpactStore = _make_deferred_global('PlanningRuleImpactStore')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')

def bind_globals(namespace: dict[str, object]) -> None:
    global PlanningRuleImpactError, PlanningRuleImpactReport, PlanningRuleImpactStore, _LOCKS_GUARD
    PlanningRuleImpactError = namespace.get('PlanningRuleImpactError', PlanningRuleImpactError)
    PlanningRuleImpactReport = namespace.get('PlanningRuleImpactReport', PlanningRuleImpactReport)
    PlanningRuleImpactStore = namespace.get('PlanningRuleImpactStore', PlanningRuleImpactStore)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    _bind_deferred_defaults(namespace)


PLANNING_RULE_IMPACT_SCHEMA_VERSION = "planning_rule_impact_report.v1"
PLANNING_RULE_IMPACT_ENGINE_VERSION = "planning_rule_impact.v1"
IMPACT_REPORT_STATUSES = {"ready", "warning", "failed", "missing", "archived", "stale"}
ROLLBACK_RECOMMENDATIONS = {"rollback_watch", "rollback_recommended"}
IMPACT_REPORT_INTEGRITY_FIELDS = (
    "status",
    "scope",
    "active_version",
    "source",
    "summary",
    "adoption",
    "before_after",
    "risk_drift",
    "version_metrics",
    "plan_samples",
    "review_samples",
    "warnings",
)
_LOCKS: dict[str, threading.RLock] = {}




def planning_rule_impact_summary(report: PlanningRuleImpactReport | DomainDocument | None) -> DomainDocument:
    data = report.to_dict() if isinstance(report, PlanningRuleImpactReport) else _as_document(report)
    summary = _as_document(data.get("summary"))
    risk = _as_document(data.get("risk_drift"))
    integrity_hash = str(data.get("integrity_hash") or data.get("report_hash") or "")
    return sanitize_metadata(
        {
            "status": data.get("status") or summary.get("status") or "missing",
            "report_id": data.get("report_id") or summary.get("report_id"),
            "active_version_id": summary.get("active_version_id"),
            "observed_plan_count": summary.get("observed_plan_count", 0),
            "observed_review_count": summary.get("observed_review_count", 0),
            "manual_review_count": summary.get("manual_review_count", 0),
            "synthetic_review_count": summary.get("synthetic_review_count", 0),
            "adoption_status": summary.get("adoption_status"),
            "effectiveness_delta": summary.get("effectiveness_delta"),
            "ranking_alignment_delta": summary.get("ranking_alignment_delta"),
            "recommendation": summary.get("recommendation") or "missing",
            "rollback_recommended": bool(summary.get("rollback_recommended", False)),
            "readiness_status": summary.get("readiness_status"),
            "synthetic_only_rate": risk.get("synthetic_only_rate"),
            "waiver_rate": risk.get("waiver_rate"),
            "force_close_rate": risk.get("force_close_rate"),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
            "source_hash": (_as_document(data.get("source"))).get("source_hash"),
            "integrity_hash": integrity_hash,
            "integrity_ok": bool(integrity_hash and integrity_hash == planning_rule_impact_report_hash(data)),
        }
    )

def latest_planning_rule_impact_summary(store: PlanningRuleImpactStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    return store.latest_summary(release_id=release_id, project_id=project_id)

def write_planning_rule_impact_summary(path: Path, store: PlanningRuleImpactStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    summary = latest_planning_rule_impact_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary

def planning_rule_impact_report_hash(report: PlanningRuleImpactReport | DomainDocument | None) -> str:
    if isinstance(report, PlanningRuleImpactReport):
        data = {key: getattr(report, key) for key in IMPACT_REPORT_INTEGRITY_FIELDS}
    else:
        data = _as_document(report)
    payload = {key: data.get(key) for key in IMPACT_REPORT_INTEGRITY_FIELDS}
    return stable_hash(payload)

def _version_metrics(plan_samples: list[DomainDocument], review_samples: list[DomainDocument]) -> list[DomainDocument]:
    version_ids = sorted(set([str(item.get("version_id") or "legacy_default") for item in plan_samples] + [str(item.get("version_id") or "legacy_default") for item in review_samples]))
    rows = []
    for version_id in version_ids:
        plans = [item for item in plan_samples if str(item.get("version_id") or "legacy_default") == version_id]
        reviews = [item for item in review_samples if str(item.get("version_id") or "legacy_default") == version_id]
        planned_item_total = sum(_int(item.get("planned_item_count"), 0) for item in reviews)
        waived_total = sum(_int(item.get("waived_item_count"), 0) for item in reviews)
        synthetic_count = sum(1 for item in reviews if item.get("synthetic_only"))
        force_count = sum(1 for item in reviews if item.get("force_closed"))
        stale_count = sum(1 for item in plans if item.get("stale")) + sum(1 for item in reviews if item.get("stale"))
        rows.append(
            sanitize_metadata(
                {
                    "version_id": version_id,
                    "plan_count": len(plans),
                    "review_count": len(reviews),
                    "manual_review_count": sum(_int(item.get("manual_review_count"), 0) for item in reviews),
                    "synthetic_review_count": sum(_int(item.get("synthetic_review_count"), 0) for item in reviews),
                    "average_plan_effectiveness_score": _mean([item.get("plan_effectiveness_score") for item in reviews]),
                    "average_ranking_alignment_score": _mean([item.get("ranking_alignment_score") for item in reviews]),
                    "average_observed_effectiveness_score": _mean([item.get("observed_effectiveness_score") for item in reviews]),
                    "synthetic_only_rate": _rate(synthetic_count, len(reviews)),
                    "waiver_rate": _rate(waived_total, planned_item_total),
                    "force_close_rate": _rate(force_count, len(reviews)),
                    "stale_source_count": stale_count,
                    "warning_count": sum(_int(item.get("warning_count"), 0) for item in reviews),
                }
            )
        )
    return rows

def _adoption_metrics(plan_samples: list[DomainDocument], active_version_id: str | None) -> DomainDocument:
    total = len(plan_samples)
    active_count = sum(1 for item in plan_samples if active_version_id and item.get("version_id") == active_version_id)
    legacy_count = sum(1 for item in plan_samples if item.get("version_id") == "legacy_default")
    superseded_count = max(0, total - active_count - legacy_count)
    rate = _rate(active_count, total)
    if total == 0:
        status = "missing"
    elif rate < 25:
        status = "low"
    elif rate < 70:
        status = "partial"
    elif rate < 95:
        status = "healthy"
    else:
        status = "dominant"
    return {"active_plan_count": active_count, "legacy_plan_count": legacy_count, "superseded_plan_count": superseded_count, "total_plan_count": total, "active_adoption_rate": rate, "status": status}

def _before_after_metrics(version_metrics: list[DomainDocument], active_version_id: str | None) -> DomainDocument:
    active = next((item for item in version_metrics if item.get("version_id") == active_version_id), {})
    baseline = [item for item in version_metrics if item.get("version_id") != active_version_id]
    baseline_reviews = sum(_int(item.get("review_count"), 0) for item in baseline)
    active_reviews = _int(active.get("review_count"), 0)
    if not active or baseline_reviews == 0 or active_reviews == 0:
        return {"status": "insufficient_data", "baseline_group": "previous_or_legacy", "baseline_review_count": baseline_reviews, "active_review_count": active_reviews}
    baseline_effectiveness = _weighted_average(baseline, "average_plan_effectiveness_score", "review_count")
    baseline_ranking = _weighted_average(baseline, "average_ranking_alignment_score", "review_count")
    return {
        "status": "ready",
        "baseline_group": "previous_or_legacy",
        "baseline_review_count": baseline_reviews,
        "active_review_count": active_reviews,
        "effectiveness_delta": _int(active.get("average_plan_effectiveness_score"), 0) - baseline_effectiveness,
        "ranking_alignment_delta": _int(active.get("average_ranking_alignment_score"), 0) - baseline_ranking,
        "manual_only_delta": _int(active.get("manual_review_count"), 0) - sum(_int(item.get("manual_review_count"), 0) for item in baseline),
    }

def _risk_drift_metrics(version_metrics: list[DomainDocument], active_version_id: str | None, before_after: DomainDocument) -> DomainDocument:
    active = next((item for item in version_metrics if item.get("version_id") == active_version_id), {})
    baseline = [item for item in version_metrics if item.get("version_id") != active_version_id]
    synthetic_rate = _int(active.get("synthetic_only_rate"), 0)
    waiver_rate = _int(active.get("waiver_rate"), 0)
    force_rate = _int(active.get("force_close_rate"), 0)
    stale_count = _int(active.get("stale_source_count"), 0)
    baseline_synthetic = _weighted_average(baseline, "synthetic_only_rate", "review_count") if baseline else 0
    baseline_waiver = _weighted_average(baseline, "waiver_rate", "review_count") if baseline else 0
    baseline_force = _weighted_average(baseline, "force_close_rate", "review_count") if baseline else 0
    warnings = []
    if synthetic_rate >= 50:
        warnings.append("synthetic_only_sample_high")
    if waiver_rate - baseline_waiver >= 20:
        warnings.append("waiver_rate_increased")
    if force_rate - baseline_force > 0:
        warnings.append("force_close_rate_increased")
    if stale_count:
        warnings.append("stale_sources_present")
    return {
        "synthetic_only_rate": synthetic_rate,
        "waiver_rate": waiver_rate,
        "force_close_rate": force_rate,
        "stale_source_count": stale_count,
        "synthetic_only_rate_delta": synthetic_rate - baseline_synthetic,
        "waiver_rate_delta": waiver_rate - baseline_waiver,
        "force_close_rate_delta": force_rate - baseline_force,
        "warnings": warnings,
    }

def _impact_warnings(state: DomainDocument, adoption: DomainDocument, risk: DomainDocument) -> list[str]:
    warnings = list(_as_list(risk.get("warnings")))
    active = _as_document(state.get("active_version"))
    if active.get("status") == "missing":
        warnings.append("missing_active_rule_version")
    if active.get("evidence_stale") or active.get("integrity_ok") is False:
        warnings.append("active_rule_evidence_stale_or_invalid")
    if adoption.get("status") in {"missing", "low", "partial"}:
        warnings.append(f"adoption_{adoption.get('status')}")
    if state.get("source_stale"):
        warnings.append("source_stale")
    return sorted(set(warnings))

def _recommendation(adoption: DomainDocument, before_after: DomainDocument, risk: DomainDocument, warnings: list[str]) -> str:
    active_reviews = _int(before_after.get("active_review_count"), 0)
    active_plans = _int(adoption.get("active_plan_count"), 0)
    effectiveness_delta = _int(before_after.get("effectiveness_delta"), 0)
    ranking_delta = _int(before_after.get("ranking_alignment_delta"), 0)
    force_delta = _int(risk.get("force_close_rate_delta"), 0)
    waiver_delta = _int(risk.get("waiver_rate_delta"), 0)
    if active_reviews < 2 or active_plans < 2:
        if risk.get("synthetic_only_rate", 0) >= 50:
            return "increase_manual_review"
        return "insufficient_data"
    if _int(risk.get("force_close_rate"), 0) >= 20 and effectiveness_delta <= -10:
        return "rollback_recommended"
    if effectiveness_delta <= -10 and ranking_delta < 0:
        return "rollback_recommended"
    if effectiveness_delta <= -5 or waiver_delta >= 20 or force_delta > 0:
        return "rollback_watch"
    if risk.get("synthetic_only_rate", 0) >= 50:
        return "increase_manual_review"
    if effectiveness_delta >= 5 and ranking_delta >= 0 and force_delta <= 0 and "source_stale" not in warnings:
        return "candidate_improving"
    return "continue_monitoring"

def _report_status(state: DomainDocument, recommendation: str, warnings: list[str], active: DomainDocument) -> str:
    if active.get("status") == "missing":
        return "missing"
    if active.get("integrity_ok") is False:
        return "failed"
    if recommendation == "rollback_recommended":
        return "failed"
    if warnings or recommendation in {"insufficient_data", "increase_manual_review", "rollback_watch"} or state.get("source_stale"):
        return "warning"
    return "ready"

def _readiness_status(recommendation: str, warnings: list[str]) -> str:
    if recommendation == "rollback_recommended":
        return "rollback_recommended"
    if recommendation == "rollback_watch":
        return "rollback_watch"
    if recommendation == "increase_manual_review" or "synthetic_only_sample_high" in warnings:
        return "needs_more_manual_evidence"
    if recommendation == "insufficient_data":
        return "needs_more_samples"
    return "ready"

def _plan_matches_scope(plan: AcceptanceFixPlan, scope: DomainDocument) -> bool:
    scope_type = str(scope.get("type") or "global")
    if scope_type == "global":
        return True
    if scope_type == "release":
        release_id = str(scope.get("release_id") or "")
        return plan.scope.get("release_id") == release_id
    if scope_type == "project":
        project_id = str(scope.get("project_id") or "")
        if plan.scope.get("project_id") == project_id:
            return True
        return any(str((_as_document(item.get("target"))).get("project_id") or "") == project_id for item in plan.planned_items)
    return True

def _plan_project_ids(plan: AcceptanceFixPlan) -> list[str]:
    ids = set()
    if plan.scope.get("project_id"):
        ids.add(str(plan.scope["project_id"]))
    for item in plan.planned_items:
        target = _as_document(item.get("target"))
        if target.get("project_id"):
            ids.add(str(target["project_id"]))
    return sorted(ids)

def _report_project_ids(report: PlanningRuleImpactReport) -> set[str]:
    ids = set()
    for item in report.plan_samples:
        for project_id in item.get("project_ids", []) if isinstance(item.get("project_ids"), list) else []:
            if str(project_id).strip():
                ids.add(str(project_id))
    return ids

def _review_observed_effectiveness(review: AcceptanceFixPlanReview) -> int:
    values = []
    for item in review.item_outcomes:
        outcome = _as_document(item.get("outcome"))
        values.append(outcome.get("observed_effectiveness_score"))
    return _mean(values)

def _scope(value: object) -> DomainDocument:
    raw = _as_document(value)
    scope_type = str(raw.get("type") or ("release" if raw.get("release_id") else "project" if raw.get("project_id") else "global"))
    if scope_type not in {"global", "release", "project"}:
        scope_type = "global"
    return sanitize_metadata({"type": scope_type, "release_id": _bounded(raw.get("release_id"), 120), "project_id": _bounded(raw.get("project_id"), 120)})

def _scope_key(scope: DomainDocument) -> str:
    if scope.get("type") == "release" and scope.get("release_id"):
        return "release-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", str(scope["release_id"]))
    if scope.get("type") == "project" and scope.get("project_id"):
        return "project-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", str(scope["project_id"]))
    return "global"

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{6}}", text):
        raise PlanningRuleImpactError(f"Invalid {prefix} id.")
    return text

def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _mean(values: list[object]) -> int:
    numbers = []
    for value in values:
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numbers:
        return 0
    return int(round(sum(numbers) / len(numbers)))

def _rate(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((part / total) * 100))

def _weighted_average(rows: list[DomainDocument], value_key: str, weight_key: str) -> int:
    total_weight = sum(max(0, _int(item.get(weight_key), 0)) for item in rows)
    if total_weight <= 0:
        return 0
    total = sum(_int(item.get(value_key), 0) * max(0, _int(item.get(weight_key), 0)) for item in rows)
    return int(round(total / total_weight))

def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]

def _append_event(path: Path, event: str, payload: DomainDocument, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"timestamp": now or now_iso(), "event": event, **payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
