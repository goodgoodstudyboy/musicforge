# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_analytics import AcceptanceAnalyticsError as AcceptanceAnalyticsError, AcceptanceAnalyticsNotFoundError as AcceptanceAnalyticsNotFoundError, AcceptanceAnalyticsStore as AcceptanceAnalyticsStore
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixItem as AcceptanceFixItem, AcceptanceFixSprint as AcceptanceFixSprint, AcceptanceFixSprintStore as AcceptanceFixSprintStore
from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseError as AcceptanceKnowledgeBaseError, AcceptanceKnowledgeBaseStore as AcceptanceKnowledgeBaseStore, KnowledgeEntry as KnowledgeEntry, knowledge_entry_summary as knowledge_entry_summary
from song_agent.domains.creation.planning_rule_governance_source import current_fix_plan_governance_source as current_fix_plan_governance_source, fix_plan_governance_projection as fix_plan_governance_projection
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
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

AcceptanceFixPlan = _make_deferred_global('AcceptanceFixPlan')
AcceptanceFixPlanError = _make_deferred_global('AcceptanceFixPlanError')
AcceptanceFixPlanningStore = _make_deferred_global('AcceptanceFixPlanningStore')
PlannedFixItem = _make_deferred_global('PlannedFixItem')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
fix_plan_summary = _make_deferred_global('fix_plan_summary')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceFixPlan, AcceptanceFixPlanError, AcceptanceFixPlanningStore, PlannedFixItem, _LOCKS_GUARD, fix_plan_summary
    AcceptanceFixPlan = namespace.get('AcceptanceFixPlan', AcceptanceFixPlan)
    AcceptanceFixPlanError = namespace.get('AcceptanceFixPlanError', AcceptanceFixPlanError)
    AcceptanceFixPlanningStore = namespace.get('AcceptanceFixPlanningStore', AcceptanceFixPlanningStore)
    PlannedFixItem = namespace.get('PlannedFixItem', PlannedFixItem)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    fix_plan_summary = namespace.get('fix_plan_summary', fix_plan_summary)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_FIX_PLAN_SCHEMA_VERSION = "acceptance_fix_plan.v1"
PLANNING_RULES_VERSION = "acceptance_fix_planning.v1"
PLAN_STATUSES = {"ready", "warning", "used", "archived", "stale"}
_LOCKS: dict[str, threading.RLock] = {}




def latest_fix_plan_summary(store: AcceptanceFixPlanningStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    for plan in store.list_plans(include_archived=False):
        scope = _as_document(plan.scope)
        if release_id and scope.get("release_id") != release_id:
            continue
        if project_id and scope.get("project_id") != project_id and not any(str((_as_document(item.get("target"))).get("project_id") or "") == project_id for item in plan.planned_items):
            continue
        return fix_plan_summary(plan)
    return {"status": "missing"}

def write_acceptance_fix_plan_summary(path: Path, store: AcceptanceFixPlanningStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    summary = latest_fix_plan_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary

def _planned_items_from_sources(analytics: DomainDocument, recommendations: list[DomainDocument], kb_entries: list[KnowledgeEntry], *, max_items: int) -> list[DomainDocument]:
    heatmap = {str(item.get("song_id") or ""): item for item in analytics.get("songbook_heatmap", []) if isinstance(item, dict)}
    rows = []
    for index, recommendation in enumerate(recommendations[:max_items], start=1):
        target = _safe_dict(recommendation.get("target"))
        evidence = _safe_dict(recommendation.get("evidence"))
        issue_types = [str(item).strip().lower() for item in evidence.get("issue_types", []) if str(item).strip()] if isinstance(evidence.get("issue_types"), list) else []
        if issue_types:
            target["issue_types"] = issue_types
        song_id = str(target.get("song_id") or "")
        heat = heatmap.get(song_id, {})
        weakness = _int(heat.get("weakness_score"), _int(recommendation.get("weakness_score"), 0))
        latest_status = str(heat.get("latest_status") or "")
        matches = _matching_kb_entries(target, issue_types, kb_entries)
        knowledge = _knowledge_for_matches(matches)
        score = _planning_score(weakness=weakness, severity=str(recommendation.get("severity") or "medium"), latest_status=latest_status, issue_count=_int(heat.get("issue_count"), 0), knowledge=knowledge, open_task_count=_int(heat.get("open_review_task_count"), 0))
        reason = _planning_reason(recommendation, weakness=weakness, knowledge=knowledge)
        item = PlannedFixItem(
            planned_item_id=f"afpi-{index:06d}",
            recommendation_id=str(recommendation.get("recommendation_id") or f"rec-{index:03d}"),
            planning_score=score,
            priority=max(score, 90 if recommendation.get("severity") == "high" else 72),
            severity=str(recommendation.get("severity") or "medium"),
            target=target,
            analytics={
                "weakness_score": weakness,
                "latest_status": latest_status,
                "issue_count": heat.get("issue_count", 0),
                "recommendation_type": recommendation.get("type"),
                "recommendation_hash": stable_hash(recommendation),
            },
            knowledge=knowledge,
            planning_reason=reason,
            suggested_actions=_suggested_actions(knowledge),
            source={"recommendation": _recommendation_source(recommendation), "kb_entry_ids": knowledge.get("top_entry_ids", [])},
        )
        rows.append(item.to_dict())
    return sorted(rows, key=lambda item: (-int(item.get("planning_score") or 0), str(item.get("planned_item_id") or "")))

def _planning_score(*, weakness: int, severity: str, latest_status: str, issue_count: int, knowledge: DomainDocument, open_task_count: int) -> int:
    score = int(weakness * 0.55)
    if severity == "high":
        score += 15
    if latest_status == "rejected":
        score += 10
    elif latest_status == "needs_fix":
        score += 8
    if knowledge.get("risk") in {"high", "medium"}:
        score += 10 if knowledge.get("risk") == "high" else 6
    if issue_count > 1:
        score += 8
    if int(knowledge.get("average_effectiveness_score") or 0) >= 80:
        score -= 8
    if open_task_count:
        score -= 10
    return max(0, min(100, score))

def _knowledge_for_matches(matches: list[KnowledgeEntry]) -> DomainDocument:
    scores = [int(entry.outcome.get("effectiveness_score") or 0) for entry in matches]
    effective = [entry for entry in matches if entry.outcome.get("outcome_status") == "effective"]
    warnings: set[str] = set()
    if not matches:
        warnings.add("no_kb_history")
    if any(entry.outcome.get("outcome_status") == "ineffective" for entry in matches):
        warnings.add("history_ineffective")
    if any(entry.outcome.get("outcome_status") == "mixed" for entry in matches):
        warnings.add("history_mixed_effectiveness")
    if any(int(entry.fix.get("waived_count") or 0) > 0 for entry in matches):
        warnings.add("waiver_heavy_history")
    if any("force_closed" in entry.warnings for entry in matches):
        warnings.add("force_closed_history")
    if any(entry.status == "hidden" for entry in matches):
        warnings.add("hidden_entries_included")
    risk = "low"
    if {"history_ineffective", "waiver_heavy_history", "force_closed_history"}.intersection(warnings):
        risk = "high"
    elif {"history_mixed_effectiveness", "no_kb_history", "hidden_entries_included"}.intersection(warnings):
        risk = "medium"
    return sanitize_metadata(
        {
            "match_count": len(matches),
            "effective_match_count": len(effective),
            "average_effectiveness_score": round(sum(scores) / len(scores), 2) if scores else None,
            "top_entry_ids": [entry.entry_id for entry in matches[:5]],
            "risk": risk,
            "warnings": sorted(warnings),
        }
    )

def _matching_kb_entries(target: DomainDocument, issue_types: list[str], entries: list[KnowledgeEntry]) -> list[KnowledgeEntry]:
    song_id = str(target.get("song_id") or "")
    style = _normalize_text(target.get("style"))
    issues = set(issue_types or [str(item).lower() for item in target.get("issue_types", []) if str(item).strip()] if isinstance(target.get("issue_types"), list) else [])
    scored: list[tuple[int, KnowledgeEntry]] = []
    for entry in entries:
        score = 0
        entry_issues = {str(item).lower() for item in entry.target.get("issue_types", []) if str(item).strip()} if isinstance(entry.target.get("issue_types"), list) else set()
        if song_id and str(entry.target.get("song_id") or "") == song_id:
            score += 4
        if issues and issues.intersection(entry_issues):
            score += 3
        entry_style = _normalize_text(entry.target.get("style"))
        if style and entry_style and (style in entry_style or entry_style in style):
            score += 2
        if score:
            scored.append((score, entry))
    return [entry for _score, entry in sorted(scored, key=lambda item: (-item[0], -int(item[1].outcome.get("effectiveness_score") or 0), item[1].entry_id))[:8]]

def _fix_item_from_planned(index: int, planned_item: DomainDocument, *, plan: AcceptanceFixPlan, now: str) -> AcceptanceFixItem:
    target = _safe_dict(planned_item.get("target"))
    issue_types = _as_list(target.get("issue_types"))
    return AcceptanceFixItem(
        item_id=f"afi-{index:06d}",
        status="open",
        priority=max(1, min(100, _int(planned_item.get("priority"), _int(planned_item.get("planning_score"), 72)))),
        severity=str(planned_item.get("severity") or "medium"),
        source={
            "source_type": "planned_item",
            "fix_plan_id": plan.plan_id,
            "planned_item_id": planned_item.get("planned_item_id"),
            "recommendation_id": planned_item.get("recommendation_id"),
            "planning_score": planned_item.get("planning_score"),
            "kb_entry_ids": (_as_document(planned_item.get("knowledge"))).get("top_entry_ids", []),
        },
        target=target,
        title=_bounded(planned_item.get("planning_reason"), 180) or "Knowledge-assisted acceptance fix",
        summary=_bounded(planned_item.get("planning_reason"), 800),
        evidence={
            "planning": {
                "plan_id": plan.plan_id,
                "planned_item_id": planned_item.get("planned_item_id"),
                "planning_score": planned_item.get("planning_score"),
                "knowledge": _as_document(planned_item.get("knowledge")),
                "suggested_actions": planned_item.get("suggested_actions", []),
            },
            "issue_types": issue_types,
        },
        created_at=now,
        updated_at=now,
    )

def _fix_item_counts(items: list[AcceptanceFixItem]) -> DomainDocument:
    return {
        "item_count": len(items),
        "open_item_count": len(items),
        "linked_review_task_count": 0,
        "completed_review_task_count": 0,
        "waived_item_count": 0,
        "fixed_item_count": 0,
    }

def _kb_entry_hashes_for_plan(planned_items: list[DomainDocument], kb_store: AcceptanceKnowledgeBaseStore) -> dict[str, str]:
    entry_ids = sorted({str(entry_id) for item in planned_items for entry_id in ((_as_document(item.get("knowledge"))).get("top_entry_ids") or []) if str(entry_id).strip()})
    return _current_entry_hashes({entry_id: "" for entry_id in entry_ids}, kb_store)

def _current_entry_hashes(expected: object, kb_store: AcceptanceKnowledgeBaseStore) -> dict[str, str]:
    ids = sorted(str(entry_id) for entry_id in (expected.keys() if isinstance(expected, dict) else []) if str(entry_id).strip())
    hashes: dict[str, str] = {}
    for entry_id in ids:
        try:
            entry = kb_store.read_entry(entry_id)
        except Exception:
            continue
        hashes[entry_id] = stable_hash(_entry_plan_summary(entry))
    return hashes

def _entry_plan_summary(entry: KnowledgeEntry) -> DomainDocument:
    return knowledge_entry_summary(entry) | {"source_fingerprint": entry.source.get("source_fingerprint")}

def _selected_recommendations(report: DomainDocument, recommendation_ids: object, *, max_items: int) -> list[DomainDocument]:
    rows = [item for item in report.get("recommendations", []) if isinstance(item, dict)]
    selected_ids = [str(item) for item in recommendation_ids if str(item).strip()] if isinstance(recommendation_ids, list) else []
    if selected_ids:
        wanted = set(selected_ids)
        rows = [item for item in rows if str(item.get("recommendation_id") or "") in wanted]
    else:
        rows = [item for item in rows if item.get("type") == "create_review_task"] or rows
    deduped = []
    seen = set()
    for row in rows:
        key = str(row.get("recommendation_id") or stable_hash(row))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:max_items]

def _selected_planned_items(plan: AcceptanceFixPlan, planned_item_ids: object) -> list[DomainDocument]:
    rows = [item for item in plan.planned_items if isinstance(item, dict)]
    selected_ids = [str(item) for item in planned_item_ids if str(item).strip()] if isinstance(planned_item_ids, list) else []
    if not selected_ids:
        return rows
    wanted = set(selected_ids)
    return [item for item in rows if str(item.get("planned_item_id") or "") in wanted]

def _planning_reason(recommendation: DomainDocument, *, weakness: int, knowledge: DomainDocument) -> str:
    issues = ", ".join((_as_document(recommendation.get("evidence"))).get("issue_types", []) or ["acceptance"])
    return _bounded(f"{recommendation.get('title') or 'Acceptance weakness'} has weakness score {weakness}. Historical {issues} fixes show {knowledge.get('risk')} risk with {knowledge.get('match_count')} KB match(es).", 500)

def _suggested_actions(knowledge: DomainDocument) -> list[str]:
    actions = ["Create ReviewTask after human review", "Require manual recheck", "Refresh delta before closeout"]
    warnings = set(_as_list(knowledge.get("warnings")))
    if "waiver_heavy_history" in warnings or "force_closed_history" in warnings:
        actions.append("Avoid waiver-only closeout")
    if "history_ineffective" in warnings:
        actions.append("Prefer smaller targeted fixes")
    return actions[:6]

def _recommendation_source(recommendation: DomainDocument) -> DomainDocument:
    return {"recommendation_id": recommendation.get("recommendation_id"), "type": recommendation.get("type"), "severity": recommendation.get("severity"), "hash": stable_hash(recommendation)}

def _scope(value: object) -> DomainDocument:
    data = _as_document(value)
    scope_type = str(data.get("type") or data.get("scope") or "global")
    return {"type": scope_type, "project_id": data.get("project_id"), "release_id": data.get("release_id"), "suite_id": data.get("suite_id"), "song_id": data.get("song_id"), "style": data.get("style"), "issue_type": data.get("issue_type")}

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _bounded(value: object, limit: int = 300) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9_ -]+", "", str(value or "").lower()).strip()

def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if prefix == "afp" and text == "afp-000000":
        return text
    if not re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{6}}", text):
        raise AcceptanceFixPlanError(f"Invalid {prefix} id.")
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
