# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReview as AcceptanceFixPlanReview, AcceptanceFixPlanReviewError as AcceptanceFixPlanReviewError, AcceptanceFixPlanReviewNotFoundError as AcceptanceFixPlanReviewNotFoundError, AcceptanceFixPlanReviewStore as AcceptanceFixPlanReviewStore, fix_plan_review_summary as fix_plan_review_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
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

PlanningRuleSet = _make_deferred_global('PlanningRuleSet')
PlanningRuleSimulationError = _make_deferred_global('PlanningRuleSimulationError')
PlanningRuleSimulationReport = _make_deferred_global('PlanningRuleSimulationReport')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
index = _make_deferred_global('index')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global PlanningRuleSet, PlanningRuleSimulationError, PlanningRuleSimulationReport, _LOCKS_GUARD, index, row
    PlanningRuleSet = namespace.get('PlanningRuleSet', PlanningRuleSet)
    PlanningRuleSimulationError = namespace.get('PlanningRuleSimulationError', PlanningRuleSimulationError)
    PlanningRuleSimulationReport = namespace.get('PlanningRuleSimulationReport', PlanningRuleSimulationReport)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    index = namespace.get('index', index)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


PLANNING_RULESET_SCHEMA_VERSION = "planning_ruleset.v1"
PLANNING_RULE_SIMULATION_SCHEMA_VERSION = "planning_rule_simulation.v1"
PLANNING_RULE_SIMULATION_ENGINE_VERSION = "planning_rule_simulation_engine.v1"
RULESET_STATUSES = {"draft", "active_candidate", "archived"}
SIMULATION_STATUSES = {"ready", "warning", "blocked", "stale", "archived"}
_LOCKS: dict[str, threading.RLock] = {}
DEFAULT_BOUNDS = {"min_score": 0, "max_score": 100, "high_score_threshold": 75}
BASELINE_RULESET: DomainDocument = {
    "weights": {
        "weakness": 0.55,
        "severity_high_bonus": 15,
        "latest_rejected_bonus": 10,
        "latest_needs_fix_bonus": 8,
        "risk_high_bonus": 10,
        "risk_medium_bonus": 6,
        "issue_count_bonus": 8,
        "effective_history_discount": -8,
        "open_task_discount": -10,
    },
    "penalties": {
        "no_kb_history": 0,
        "history_ineffective": 8,
        "history_mixed_effectiveness": 4,
        "waiver_heavy_history": 4,
        "force_closed_history": 6,
        "synthetic_only_recheck": 0,
    },
    "confidence": {"manual_recheck_bonus": 0, "synthetic_only_penalty": 0, "kb_match_cap": 8},
}
RULESET_TEMPLATES: dict[str, DomainDocument] = {
    "baseline": {
        "name": "Baseline Planning Rules",
        "description": "Approximate the current production planning score shape.",
        **BASELINE_RULESET,
    },
    "manual_conservative": {
        "name": "Manual Conservative",
        "description": "Reward manual recheck evidence and keep synthetic-only history visible as risk.",
        "weights": {**BASELINE_RULESET["weights"]},
        "penalties": {**BASELINE_RULESET["penalties"], "synthetic_only_recheck": 10, "waiver_heavy_history": 8},
        "confidence": {"manual_recheck_bonus": 16, "synthetic_only_penalty": 10, "kb_match_cap": 8},
    },
    "kb_trust_light": {
        "name": "KB Trust Light",
        "description": "Reduce the influence of historical KB matches when planning risk is uncertain.",
        "weights": {**BASELINE_RULESET["weights"], "risk_high_bonus": 7, "risk_medium_bonus": 3, "effective_history_discount": -4},
        "penalties": {**BASELINE_RULESET["penalties"], "no_kb_history": 2, "history_mixed_effectiveness": 8},
        "confidence": {"manual_recheck_bonus": 4, "synthetic_only_penalty": 8, "kb_match_cap": 4},
    },
    "waiver_strict": {
        "name": "Waiver Strict",
        "description": "Penalize waiver-heavy and force-closed histories more strongly.",
        "weights": {**BASELINE_RULESET["weights"]},
        "penalties": {**BASELINE_RULESET["penalties"], "waiver_heavy_history": 14, "force_closed_history": 16, "history_mixed_effectiveness": 8},
        "confidence": {"manual_recheck_bonus": 4, "synthetic_only_penalty": 8, "kb_match_cap": 8},
    },
    "synthetic_strict": {
        "name": "Synthetic Strict",
        "description": "Treat synthetic-only recheck evidence as weak and risky during planning simulation.",
        "weights": {**BASELINE_RULESET["weights"]},
        "penalties": {**BASELINE_RULESET["penalties"], "synthetic_only_recheck": 18, "waiver_heavy_history": 8, "force_closed_history": 10},
        "confidence": {"manual_recheck_bonus": 4, "synthetic_only_penalty": 18, "kb_match_cap": 8},
    },
}




def _simulate_item(item: DomainDocument, ruleset: PlanningRuleSet, review_summary: DomainDocument) -> DomainDocument:
    baseline = max(0, min(100, _int(item.get("planning_score"), 0)))
    score = baseline
    effects: list[str] = []
    knowledge = _as_document(item.get("planned_knowledge"))
    execution = _as_document(item.get("execution"))
    warnings = [str(value) for value in knowledge.get("warnings", []) if str(value).strip()] if isinstance(knowledge.get("warnings"), list) else []
    if review_summary.get("manual_recheck_confirmed"):
        score += _int(ruleset.confidence.get("manual_recheck_bonus"), 0)
        if _int(ruleset.confidence.get("manual_recheck_bonus"), 0):
            effects.append("manual_bonus")
    if review_summary.get("synthetic_only"):
        penalty = _int(ruleset.confidence.get("synthetic_only_penalty"), _int(ruleset.penalties.get("synthetic_only_recheck"), 0))
        score -= penalty
        if penalty:
            effects.append("synthetic_penalty")
    if execution.get("waived") or "waived_item" in item.get("warnings", []):
        penalty = _int(ruleset.penalties.get("waiver_heavy_history"), 0)
        score -= penalty
        if penalty:
            effects.append("waiver_penalty")
    if execution.get("force_closed") or "force_closed" in item.get("warnings", []):
        penalty = _int(ruleset.penalties.get("force_closed_history"), 0)
        score -= penalty
        if penalty:
            effects.append("force_close_penalty")
    if _int(knowledge.get("match_count"), 0) == 0 or "no_kb_history" in warnings:
        penalty = _int(ruleset.penalties.get("no_kb_history"), 0)
        score -= penalty
        if penalty:
            effects.append("no_kb_penalty")
    if "history_ineffective" in warnings:
        penalty = _int(ruleset.penalties.get("history_ineffective"), 0)
        score -= penalty
        if penalty:
            effects.append("ineffective_history_penalty")
    if "history_mixed_effectiveness" in warnings:
        penalty = _int(ruleset.penalties.get("history_mixed_effectiveness"), 0)
        score -= penalty
        if penalty:
            effects.append("mixed_history_penalty")
    if knowledge.get("risk") == "high":
        score += _int(ruleset.weights.get("risk_high_bonus"), 0)
        effects.append("risk_high_adjustment")
    elif knowledge.get("risk") == "medium":
        score += _int(ruleset.weights.get("risk_medium_bonus"), 0)
        effects.append("risk_medium_adjustment")
    if _int(knowledge.get("effective_match_count"), 0) > 0:
        score += _int(ruleset.weights.get("effective_history_discount"), 0)
        if _int(ruleset.weights.get("effective_history_discount"), 0):
            effects.append("effective_history_adjustment")
    min_score = _int(ruleset.bounds.get("min_score"), 0)
    max_score = _int(ruleset.bounds.get("max_score"), 100)
    simulated = max(min_score, min(max_score, score))
    outcome = _as_document(item.get("outcome"))
    target = _as_document(item.get("target"))
    return sanitize_metadata(
        {
            "planned_item_id": item.get("planned_item_id"),
            "baseline_planning_score": baseline,
            "simulated_planning_score": simulated,
            "score_delta": simulated - baseline,
            "outcome_status": outcome.get("observed_outcome_status"),
            "evidence_status": outcome.get("evidence_status"),
            "observed_effectiveness_score": outcome.get("observed_effectiveness_score"),
            "target": _target_summary(target),
            "applied_effects": sorted(set(effects)),
            "rank_before": item.get("original_rank"),
            "rank_after": None,
        }
    )

def _rank_items(items: list[DomainDocument]) -> list[DomainDocument]:
    ranked_ids = {str(item.get("planned_item_id") or ""): index for index, item in enumerate(sorted(items, key=lambda row: (-_int(row.get("simulated_planning_score"), 0), str(row.get("planned_item_id") or ""))), start=1)}
    return [{**item, "rank_after": ranked_ids.get(str(item.get("planned_item_id") or ""), item.get("rank_after"))} for item in items]

def _rule_effects(review_results: list[DomainDocument]) -> list[DomainDocument]:
    buckets: dict[str, DomainDocument] = {}
    for review in review_results:
        for item in review.get("item_results", []):
            if not isinstance(item, dict):
                continue
            for effect in item.get("applied_effects", []) if isinstance(item.get("applied_effects"), list) else []:
                bucket = buckets.setdefault(str(effect), {"effect_id": str(effect), "count": 0, "score_deltas": [], "affected_review_ids": set(), "affected_issue_types": set()})
                bucket["count"] += 1
                bucket["score_deltas"].append(_int(item.get("score_delta"), 0))
                bucket["affected_review_ids"].add(str(review.get("review_id") or ""))
                target = _as_document(item.get("target"))
                for issue in target.get("issue_types", []) if isinstance(target.get("issue_types"), list) else []:
                    bucket["affected_issue_types"].add(str(issue))
    rows = []
    for effect_id, bucket in buckets.items():
        rows.append(
            sanitize_metadata(
                {
                    "effect_id": effect_id,
                    "count": bucket["count"],
                    "average_score_delta": round(sum(bucket["score_deltas"]) / len(bucket["score_deltas"]), 2) if bucket["score_deltas"] else 0,
                    "affected_review_ids": sorted(bucket["affected_review_ids"])[:20],
                    "affected_issue_types": sorted(bucket["affected_issue_types"])[:20],
                }
            )
        )
    return sorted(rows, key=lambda item: (-int(item.get("count") or 0), str(item.get("effect_id") or "")))

def _simulation_summary(review_results: list[DomainDocument], effects: list[DomainDocument]) -> DomainDocument:
    item_results = [item for review in review_results for item in review.get("item_results", []) if isinstance(item, dict)]
    baseline_alignment = _mean([(review.get("baseline") or {}).get("ranking_alignment_score") for review in review_results])
    if baseline_alignment is None:
        baseline_alignment = _mean([_alignment_score(review.get("item_results", []), key="baseline_planning_score") for review in review_results])
    simulated_alignment = _mean([(review.get("simulated") or {}).get("alignment_score") for review in review_results])
    baseline_high = sum(_int((review.get("baseline") or {}).get("high_score_unsupported_count"), 0) for review in review_results)
    simulated_high = sum(_int((review.get("simulated") or {}).get("high_score_unsupported_count"), 0) for review in review_results)
    alignment_delta = round(float(simulated_alignment or 0) - float(baseline_alignment or 0), 2) if baseline_alignment is not None and simulated_alignment is not None else 0
    synthetic_penalty = _effect_count(effects, "synthetic_penalty")
    waiver_penalty = _effect_count(effects, "waiver_penalty")
    recommendation = _simulation_recommendation(len(review_results), len(item_results), alignment_delta, baseline_high, simulated_high)
    return sanitize_metadata(
        {
            "review_count": len(review_results),
            "item_count": len(item_results),
            "baseline_alignment_score": baseline_alignment,
            "simulated_alignment_score": simulated_alignment,
            "alignment_delta": alignment_delta,
            "baseline_high_score_unsupported_count": baseline_high,
            "simulated_high_score_unsupported_count": simulated_high,
            "low_score_supported_count": _low_score_supported_count(item_results),
            "synthetic_penalty_applied_count": synthetic_penalty,
            "waiver_penalty_applied_count": waiver_penalty,
            "no_kb_penalty_applied_count": _effect_count(effects, "no_kb_penalty"),
            "mixed_history_penalty_applied_count": _effect_count(effects, "mixed_history_penalty"),
            "ineffective_history_penalty_applied_count": _effect_count(effects, "ineffective_history_penalty"),
            "manual_bonus_applied_count": _effect_count(effects, "manual_bonus"),
            "recommendation": recommendation,
            "stale": False,
        }
    )

def _alignment_score(items: list[DomainDocument], *, key: str) -> int | None:
    if not items:
        return None
    ranked = sorted(items, key=lambda item: (-_int(item.get(key), 0), str(item.get("planned_item_id") or "")))
    ideal = sorted(items, key=lambda item: (-_int(item.get("observed_effectiveness_score"), 0), str(item.get("planned_item_id") or "")))
    ideal_rank = {str(item.get("planned_item_id") or ""): index for index, item in enumerate(ideal, start=1)}
    distance = sum(abs(index - ideal_rank.get(str(item.get("planned_item_id") or ""), index)) for index, item in enumerate(ranked, start=1))
    max_distance = max(1, len(items) * (len(items) - 1))
    return max(0, min(100, round(100 - (distance / max_distance * 100))))

def _high_score_unsupported_count(items: list[DomainDocument], *, key: str, threshold: int) -> int:
    return sum(1 for item in items if _int(item.get(key), 0) >= threshold and str(item.get("evidence_status") or "") in {"unsupported", "unknown", "not_executed"})

def _low_score_supported_count(items: list[DomainDocument]) -> int:
    return sum(1 for item in items if _int(item.get("simulated_planning_score"), 0) < 50 and str(item.get("evidence_status") or "") == "supported")

def _review_recommendation(baseline_alignment: int | None, simulated_alignment: int | None, baseline_high: int, simulated_high: int, item_count: int) -> str:
    if item_count < 1:
        return "insufficient_data"
    delta = int(simulated_alignment or 0) - int(baseline_alignment or 0)
    if delta >= 5 and simulated_high <= baseline_high:
        return "candidate_better"
    if delta <= -5 or simulated_high > baseline_high:
        return "candidate_worse"
    return "candidate_mixed"

def _simulation_recommendation(review_count: int, item_count: int, alignment_delta: float, baseline_high: int, simulated_high: int) -> str:
    if review_count < 1 or item_count < 1:
        return "insufficient_data"
    if (review_count >= 2 or item_count >= 4) and alignment_delta >= 5 and simulated_high <= baseline_high:
        return "candidate_better"
    if alignment_delta <= -5 or simulated_high > baseline_high:
        return "candidate_worse"
    return "candidate_mixed"

def _review_source_core(review: AcceptanceFixPlanReview) -> DomainDocument:
    return sanitize_metadata(
        {
            "review_id": review.review_id,
            "status": review.status,
            "readiness": review.readiness,
            "source": review.source,
            "summary": review.summary,
            "item_outcomes": review.item_outcomes,
            "scope": review.scope,
        }
    )

def _ruleset_core(ruleset: PlanningRuleSet) -> DomainDocument:
    return sanitize_metadata(
        {
            "schema_version": ruleset.to_dict().get("schema_version"),
            "ruleset_id": ruleset.ruleset_id,
            "status": ruleset.status,
            "base_rules_version": ruleset.base_rules_version,
            "weights": ruleset.weights,
            "penalties": ruleset.penalties,
            "confidence": ruleset.confidence,
            "bounds": ruleset.bounds,
        }
    )

def _source_core(source: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "engine_version": source.get("engine_version"),
            "ruleset_id": source.get("ruleset_id"),
            "ruleset_hash": source.get("ruleset_hash"),
            "review_ids": _as_list(source.get("review_ids")),
            "review_hashes": _as_document(source.get("review_hashes")),
            "scope": _as_document(source.get("scope")),
            "options": _as_document(source.get("options")),
        }
    )

def _simulation_options(payload: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "include_warning_reviews": bool(payload.get("include_warning_reviews", True)),
            "exclude_synthetic_only": bool(payload.get("exclude_synthetic_only", False)),
        }
    )

def _target_summary(target: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "song_id": _bounded(target.get("song_id"), 120),
            "style": _bounded(target.get("style"), 120),
            "issue_types": [_bounded(item, 80) for item in target.get("issue_types", []) if str(item).strip()] if isinstance(target.get("issue_types"), list) else [],
            "project_id": _bounded(target.get("project_id"), 120),
            "version_id": _bounded(target.get("version_id"), 120),
        }
    )

def _scope(value: object, payload: DomainDocument | None = None) -> DomainDocument:
    payload = payload or {}
    source = _as_document(value)
    scope_type = str(source.get("type") or payload.get("scope_type") or ("release" if source.get("release_id") or payload.get("release_id") else "project" if source.get("project_id") or payload.get("project_id") else "global"))
    if scope_type not in {"global", "release", "project"}:
        scope_type = "global"
    return sanitize_metadata(
        {
            "type": scope_type,
            "release_id": _bounded(source.get("release_id") or payload.get("release_id"), 120),
            "project_id": _bounded(source.get("project_id") or payload.get("project_id"), 120),
        }
    )

def _review_matches_project(review: AcceptanceFixPlanReview, project_id: str) -> bool:
    if review.scope.get("project_id") == project_id:
        return True
    for item in review.item_outcomes:
        target = _as_document(item.get("target"))
        if target.get("project_id") == project_id:
            return True
    return False

def _simulation_matches_release(report: PlanningRuleSimulationReport, release_id: str) -> bool:
    if report.scope.get("release_id") == release_id:
        return True
    for review in report.review_results:
        scope = review.get("scope") if isinstance(review, dict) and isinstance(review.get("scope"), dict) else {}
        if _as_document(scope).get("release_id") == release_id:
            return True
    return False

def _simulation_matches_project(report: PlanningRuleSimulationReport, project_id: str) -> bool:
    if report.scope.get("project_id") == project_id:
        return True
    for review in report.review_results:
        for item in review.get("item_results", []):
            target = item.get("target") if isinstance(item, dict) and isinstance(item.get("target"), dict) else {}
            if _as_document(target).get("project_id") == project_id:
                return True
    return False

def _numeric_map(value: object, low: int, high: int) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PlanningRuleSimulationError("Rule set numeric sections must be objects.")
    result: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(raw, (int, float)):
            raise PlanningRuleSimulationError(f"Rule set value for {key} must be numeric.")
        result[_bounded(key, 80)] = max(low, min(high, int(raw)))
    return result

def _bounds(value: object) -> dict[str, int]:
    raw = _as_document(value)
    min_score = max(0, min(100, _int(raw.get("min_score"), 0)))
    max_score = max(min_score, min(100, _int(raw.get("max_score"), 100)))
    threshold = max(50, min(95, _int(raw.get("high_score_threshold"), 75)))
    return {"min_score": min_score, "max_score": max_score, "high_score_threshold": threshold}

def _safe_child(base: Path, child: str, label: str) -> Path:
    root = base.resolve()
    target = (root / child).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PlanningRuleSimulationError(f"Refusing to operate outside {label} store.") from exc
    return target

def _validate_id(value: str, prefix: str) -> str:
    if not value.startswith(f"{prefix}-") or not value.replace(f"{prefix}-", "", 1).isdigit():
        raise PlanningRuleSimulationError(f"Invalid {prefix} id.")
    return value

def _append_event(path: Path, event: str, payload: DomainDocument, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, "timestamp": now or now_iso(), "payload": sanitize_metadata(payload)}, ensure_ascii=False) + "\n")

def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _mean(values: list[object]) -> float | None:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)

def _effect_count(effects: list[DomainDocument], effect_id: str) -> int:
    for effect in effects:
        if effect.get("effect_id") == effect_id:
            return _int(effect.get("count"), 0)
    return 0
