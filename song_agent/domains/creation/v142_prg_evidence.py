# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.creation.planning_rule_simulation import PlanningRuleSimulationError as PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError as PlanningRuleSimulationNotFoundError, PlanningRuleSimulationStore as PlanningRuleSimulationStore, planning_simulation_summary as planning_simulation_summary, ruleset_summary as ruleset_summary
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

PlanningRuleGovernanceError = _make_deferred_global('PlanningRuleGovernanceError')
PlanningRuleGovernanceStore = _make_deferred_global('PlanningRuleGovernanceStore')
PlanningRulePromotion = _make_deferred_global('PlanningRulePromotion')
PlanningRuleVersion = _make_deferred_global('PlanningRuleVersion')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
char = _make_deferred_global('char')

def bind_globals(namespace: dict[str, object]) -> None:
    global PlanningRuleGovernanceError, PlanningRuleGovernanceStore, PlanningRulePromotion, PlanningRuleVersion, _LOCKS_GUARD, char
    PlanningRuleGovernanceError = namespace.get('PlanningRuleGovernanceError', PlanningRuleGovernanceError)
    PlanningRuleGovernanceStore = namespace.get('PlanningRuleGovernanceStore', PlanningRuleGovernanceStore)
    PlanningRulePromotion = namespace.get('PlanningRulePromotion', PlanningRulePromotion)
    PlanningRuleVersion = namespace.get('PlanningRuleVersion', PlanningRuleVersion)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    char = namespace.get('char', char)
    _bind_deferred_defaults(namespace)


PLANNING_RULE_VERSION_SCHEMA_VERSION = "planning_rule_version.v1"
PLANNING_RULE_PROMOTION_SCHEMA_VERSION = "planning_rule_promotion.v1"
PLANNING_RULE_ACTIVE_POINTER_SCHEMA_VERSION = "planning_rule_active_pointer.v1"
PLANNING_RULE_GOVERNANCE_SCHEMA_VERSION = "planning_rule_governance.v1"
VERSION_STATUSES = {"active", "superseded", "rolled_back", "archived"}
PROMOTION_STATUSES = {"pending", "approved", "rejected", "promoted", "stale", "archived"}
READY_SIMULATION_STATUSES = {"ready", "warning"}
_LOCKS: dict[str, threading.RLock] = {}




def governance_summary(version: PlanningRuleVersion | DomainDocument | None, *, active: DomainDocument | None = None, evidence_stale: bool = False) -> DomainDocument:
    data = version.to_dict() if isinstance(version, PlanningRuleVersion) else _as_document(version)
    if not data:
        return {"status": "missing", "governance_status": "legacy_default", "active_version_id": None}
    promoted = _as_document(data.get("promoted_from"))
    active = _as_document(active)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "governance_status": data.get("status") or "missing",
            "active_version_id": data.get("version_id") if data.get("status") == "active" else active.get("active_version_id") or data.get("version_id"),
            "version_id": data.get("version_id"),
            "ruleset_id": data.get("ruleset_id"),
            "ruleset_hash": data.get("ruleset_hash"),
            "ruleset_name": data.get("ruleset_name"),
            "promotion_id": promoted.get("promotion_id"),
            "promoted_from_simulation_id": promoted.get("simulation_id"),
            "simulation_id": promoted.get("simulation_id"),
            "recommendation": promoted.get("recommendation"),
            "alignment_delta": promoted.get("alignment_delta"),
            "review_count": promoted.get("review_count", 0),
            "item_count": promoted.get("item_count", 0),
            "activated_at": active.get("activated_at") or data.get("created_at"),
            "activated_by": active.get("activated_by") or data.get("created_by"),
            "evidence_stale": bool(evidence_stale),
            "stale": bool(evidence_stale),
            "source_hash": data.get("source_hash"),
        }
    )

def promotion_summary(promotion: PlanningRulePromotion | DomainDocument | None) -> DomainDocument:
    data = promotion.to_dict() if isinstance(promotion, PlanningRulePromotion) else _as_document(promotion)
    evidence = _as_document(data.get("evidence"))
    risk = _as_document(data.get("risk_assessment"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "promotion_id": data.get("promotion_id"),
            "ruleset_id": data.get("ruleset_id"),
            "simulation_id": data.get("simulation_id"),
            "recommendation": evidence.get("recommendation"),
            "alignment_delta": evidence.get("alignment_delta"),
            "review_count": evidence.get("review_count", 0),
            "item_count": evidence.get("item_count", 0),
            "risk_status": risk.get("status") or "unknown",
            "requires_force": bool(risk.get("requires_force", False)),
            "stale": data.get("status") == "stale" or bool(evidence.get("stale", False)),
        }
    )

def active_governance_summary(store: PlanningRuleGovernanceStore) -> DomainDocument:
    return store.active_summary()

def write_planning_rule_governance_summary(path: Path, store: PlanningRuleGovernanceStore) -> DomainDocument:
    summary = active_governance_summary(store)
    write_json(path, summary)
    return summary

def fix_plan_rule_governance_source(store: PlanningRuleGovernanceStore | None = None) -> DomainDocument:
    store = store or PlanningRuleGovernanceStore()
    summary = store.active_summary()
    if summary.get("status") == "missing":
        return {"status": "legacy_default", "governance_status": "legacy_default", "generated_with_active_rules": False, "planning_rule_version_id": None}
    return sanitize_metadata(
        {
            "status": "active",
            "governance_status": "active",
            "generated_with_active_rules": True,
            "planning_rule_version_id": summary.get("active_version_id") or summary.get("version_id"),
            "version_id": summary.get("active_version_id") or summary.get("version_id"),
            "ruleset_id": summary.get("ruleset_id"),
            "ruleset_hash": summary.get("ruleset_hash"),
            "active_at": summary.get("activated_at"),
            "source": "planning_rule_governance",
        }
    )

def _risk_for_recommendation(recommendation: str, simulation: object) -> DomainDocument:
    warnings = []
    summary = simulation.summary if isinstance(getattr(simulation, "summary", None), dict) else {}
    if int(summary.get("synthetic_penalty_applied_count") or 0) > 0:
        warnings.append("synthetic_only_reviews_present")
    if recommendation == "candidate_worse":
        return {"status": "blocked", "warnings": sorted(set(warnings + ["candidate_worse"])), "requires_force": True}
    if recommendation == "candidate_mixed":
        return {"status": "warning", "warnings": sorted(set(warnings + ["candidate_mixed"])), "requires_force": False}
    return {"status": "passed" if not warnings else "warning", "warnings": sorted(set(warnings)), "requires_force": False}

def _review_source_core(review: object) -> DomainDocument:
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

def _scope(value: object) -> DomainDocument:
    raw = _as_document(value)
    scope_type = str(raw.get("type") or ("release" if raw.get("release_id") else "project" if raw.get("project_id") else "global"))
    if scope_type not in {"global", "release", "project"}:
        scope_type = "global"
    return sanitize_metadata({"type": scope_type, "release_id": _bounded(raw.get("release_id"), 120), "project_id": _bounded(raw.get("project_id"), 120)})

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _bounded(value: object, limit: int) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())
    return text[:limit]

def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not text.startswith(prefix + "-") or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for char in text):
        raise PlanningRuleGovernanceError(f"Invalid {prefix} id.")
    return text

def _safe_child(base: Path, child: str, label: str) -> Path:
    base_resolved = base.resolve()
    target = (base_resolved / child).resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError as exc:
        raise PlanningRuleGovernanceError(f"Refusing to operate outside {label} store.") from exc
    return target

def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]

def _append_event(path: Path, event: str, payload: DomainDocument, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"event": event, "created_at": now or now_iso(), **payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
