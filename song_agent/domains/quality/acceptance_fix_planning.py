# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.acceptance_analytics import AcceptanceAnalyticsError as AcceptanceAnalyticsError, AcceptanceAnalyticsNotFoundError as AcceptanceAnalyticsNotFoundError, AcceptanceAnalyticsStore as AcceptanceAnalyticsStore
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixItem as AcceptanceFixItem, AcceptanceFixSprint as AcceptanceFixSprint, AcceptanceFixSprintStore as AcceptanceFixSprintStore
from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseError as AcceptanceKnowledgeBaseError, AcceptanceKnowledgeBaseStore as AcceptanceKnowledgeBaseStore, KnowledgeEntry as KnowledgeEntry, knowledge_entry_summary as knowledge_entry_summary
from song_agent.domains.creation.planning_rule_governance_source import current_fix_plan_governance_source as current_fix_plan_governance_source, fix_plan_governance_projection as fix_plan_governance_projection
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text


ACCEPTANCE_FIX_PLAN_ROOT = Path(".musicforge") / "fix-plans"
ACCEPTANCE_FIX_PLAN_SCHEMA_VERSION = "acceptance_fix_plan.v1"
PLANNING_RULES_VERSION = "acceptance_fix_planning.v1"
PLAN_STATUSES = {"ready", "warning", "used", "archived", "stale"}


class AcceptanceFixPlanError(ValueError):
    pass


class AcceptanceFixPlanNotFoundError(AcceptanceFixPlanError):
    pass


class AcceptanceFixPlanStateError(AcceptanceFixPlanError):
    pass


@dataclass
class PlannedFixItem:
    planned_item_id: str
    recommendation_id: str
    planning_score: int
    priority: int
    severity: str
    target: ImplementationDocument
    analytics: ImplementationDocument
    knowledge: ImplementationDocument
    planning_reason: str
    suggested_actions: list[str]
    source: ImplementationDocument = field(default_factory=dict)

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "planned_item_id": self.planned_item_id,
                "recommendation_id": self.recommendation_id,
                "planning_score": self.planning_score,
                "priority": self.priority,
                "severity": self.severity,
                "target": self.target,
                "analytics": self.analytics,
                "knowledge": self.knowledge,
                "planning_reason": self.planning_reason,
                "suggested_actions": self.suggested_actions,
                "source": self.source,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "PlannedFixItem":
        return cls(
            planned_item_id=_validate_id(str(data.get("planned_item_id") or "afpi-000001"), "afpi"),
            recommendation_id=_bounded(data.get("recommendation_id"), 80),
            planning_score=max(0, min(100, _int(data.get("planning_score"), 0))),
            priority=max(1, min(100, _int(data.get("priority"), 50))),
            severity=_bounded(data.get("severity"), 40) or "medium",
            target=_safe_dict(data.get("target")),
            analytics=_safe_dict(data.get("analytics")),
            knowledge=_safe_dict(data.get("knowledge")),
            planning_reason=_bounded(data.get("planning_reason"), 500),
            suggested_actions=[_bounded(item, 160) for item in data.get("suggested_actions", []) if str(item).strip()] if isinstance(data.get("suggested_actions"), list) else [],
            source=_safe_dict(data.get("source")),
        )


@dataclass
class AcceptanceFixPlan:
    plan_id: str
    status: str
    scope: ImplementationDocument
    source: ImplementationDocument
    summary: ImplementationDocument
    planned_items: list[ImplementationDocument]
    strategy: ImplementationDocument
    warnings: list[str]
    execution: ImplementationDocument = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": ACCEPTANCE_FIX_PLAN_SCHEMA_VERSION,
                "plan_id": self.plan_id,
                "status": self.status,
                "scope": self.scope,
                "source": self.source,
                "summary": self.summary,
                "planned_items": self.planned_items,
                "strategy": self.strategy,
                "warnings": self.warnings,
                "execution": self.execution,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "AcceptanceFixPlan":
        now = now_iso()
        status = str(data.get("status") or "ready")
        if status not in PLAN_STATUSES:
            status = "ready"
        return cls(
            plan_id=_validate_id(str(data.get("plan_id") or "afp-000001"), "afp"),
            status=status,
            scope=_safe_dict(data.get("scope")),
            source=_safe_dict(data.get("source")),
            summary=_safe_dict(data.get("summary")),
            planned_items=[PlannedFixItem.from_dict(item).to_dict() for item in data.get("planned_items", []) if isinstance(item, dict)] if isinstance(data.get("planned_items"), list) else [],
            strategy=_safe_dict(data.get("strategy")),
            warnings=[_bounded(item, 180) for item in data.get("warnings", []) if str(item).strip()] if isinstance(data.get("warnings"), list) else [],
            execution=_safe_dict(data.get("execution")),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


class AcceptanceFixPlanningStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        analytics_store: AcceptanceAnalyticsStore | None = None,
        kb_store: AcceptanceKnowledgeBaseStore | None = None,
        fix_sprint_store: AcceptanceFixSprintStore | None = None,
        project_store: ProjectStore | None = None,
    ):
        self.root = Path(root or ACCEPTANCE_FIX_PLAN_ROOT)
        self.project_store = project_store or getattr(analytics_store, "project_store", None) or getattr(fix_sprint_store, "project_store", None) or ProjectStore()
        self.analytics_store = analytics_store or AcceptanceAnalyticsStore(project_store=self.project_store)
        self.fix_sprint_store = fix_sprint_store or AcceptanceFixSprintStore(analytics_store=self.analytics_store, project_store=self.project_store)
        self.kb_store = kb_store or AcceptanceKnowledgeBaseStore(fix_sprint_store=self.fix_sprint_store, project_store=self.project_store)
        self.lock = _lock_for_root(self.root.resolve())
        self.planning_rule_governance_store: Any | None = None

    def plan_dir(self, plan_id: str) -> Path:
        base = self.root.resolve()
        target = (base / _validate_id(plan_id, "afp")).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise AcceptanceFixPlanError("Refusing to operate outside acceptance fix plan store.") from exc
        return target

    def list_plans(self, *, include_archived: bool = False, status: str | None = None) -> list[AcceptanceFixPlan]:
        rows: list[AcceptanceFixPlan] = []
        if not self.root.exists():
            return rows
        for path in self.root.glob("afp-*/fix-plan.json"):
            try:
                plan = self._with_stale(AcceptanceFixPlan.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if plan.status == "archived" and not include_archived:
                continue
            if status and plan.status != status:
                continue
            rows.append(plan)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_plan(self, plan_id: str) -> AcceptanceFixPlan:
        path = self.plan_dir(plan_id) / "fix-plan.json"
        if not path.exists():
            raise AcceptanceFixPlanNotFoundError(plan_id)
        return self._with_stale(AcceptanceFixPlan.from_dict(read_json(path)))

    def create(self, payload: DomainDocument | None = None, *, now: str | None = None) -> AcceptanceFixPlan:
        payload = payload or {}
        now = now or now_iso()
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            plan_id, plan_dir = self._reserve_plan_dir()
            plan = self._build_plan(plan_id, payload, now=now)
            write_json(plan_dir / "fix-plan.json", plan.to_dict())
            write_json(plan_dir / "source-summary.json", {"source": plan.source, "summary": plan.summary})
            _append_event(plan_dir / "events.jsonl", "acceptance_fix_plan_created", {"plan_id": plan_id, "planned_item_count": len(plan.planned_items)}, now)
            return plan

    def preview(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        plan = self._build_plan("afp-000000", payload or {}, now=now or now_iso(), preview=True)
        return plan.to_dict()

    def refresh_plan(self, plan_id: str, *, now: str | None = None) -> AcceptanceFixPlan:
        existing = self.read_plan(plan_id)
        payload = {
            "analytics_report_id": existing.source.get("analytics_report_id"),
            "kb_report_id": existing.source.get("kb_report_id"),
            "scope": existing.scope,
            "max_items": existing.summary.get("max_items", len(existing.planned_items) or 20),
            "include_hidden_kb": bool(existing.source.get("include_hidden_kb", False)),
            "created_by": existing.created_by,
        }
        plan = self._build_plan(existing.plan_id, payload, now=now or now_iso())
        plan.created_at = existing.created_at
        plan.execution = existing.execution
        if existing.execution.get("created_fix_sprint_id") and plan.status in {"ready", "warning"}:
            plan.status = "used"
        self._write_plan(plan)
        _append_event(self.plan_dir(plan_id) / "events.jsonl", "acceptance_fix_plan_refreshed", {"plan_id": plan.plan_id, "status": plan.status}, now)
        return plan

    def archive_plan(self, plan_id: str, *, now: str | None = None) -> AcceptanceFixPlan:
        plan = self.read_plan(plan_id)
        updated = AcceptanceFixPlan.from_dict({**plan.to_dict(), "status": "archived", "updated_at": now or now_iso()})
        self._write_plan(updated)
        _append_event(self.plan_dir(plan_id) / "events.jsonl", "acceptance_fix_plan_archived", {"plan_id": plan_id}, now)
        return updated

    def create_fix_sprint(self, plan_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        plan = self.read_plan(plan_id)
        if plan.status == "used" or plan.execution.get("created_fix_sprint_id"):
            raise AcceptanceFixPlanStateError("Acceptance Fix Plan has already created a Fix Sprint. Refresh or create a new plan.")
        if plan.status in {"archived", "stale"} or self.plan_is_stale(plan):
            raise AcceptanceFixPlanStateError("Acceptance Fix Plan is stale. Refresh the plan before creating a Fix Sprint.")
        selected = _selected_planned_items(plan, payload.get("planned_item_ids"))
        if not selected:
            raise AcceptanceFixPlanStateError("Fix Plan has no selected planned items.")
        with self.fix_sprint_store.lock:
            self.fix_sprint_store.root.mkdir(parents=True, exist_ok=True)
            sprint_id, sprint_dir = self.fix_sprint_store._reserve_sprint_dir()
            items = [_fix_item_from_planned(index, item, plan=plan, now=now) for index, item in enumerate(selected, start=1)]
            sprint = AcceptanceFixSprint(
                fix_sprint_id=sprint_id,
                name=_bounded(payload.get("name"), 160) or "Knowledge-assisted Fix Sprint",
                status="planned",
                scope=plan.scope,
                source={
                    "source_type": "acceptance_fix_plan",
                    "fix_plan_id": plan.plan_id,
                    "fix_plan_source_hash": plan.source.get("source_hash"),
                    "analytics_report_id": plan.source.get("analytics_report_id"),
                    "analytics_source_hash": plan.source.get("analytics_source_hash"),
                    "kb_report_id": plan.source.get("kb_report_id"),
                    "kb_source_hash": plan.source.get("kb_source_hash"),
                    "planned_item_ids": [item.get("planned_item_id") for item in selected],
                    "planned_item_hashes": {str(item.get("planned_item_id")): stable_hash(item) for item in selected},
                },
                settings={
                    "profile_id": _bounded(payload.get("profile_id"), 80) or str(plan.strategy.get("recommended_recheck_profile") or "developer_manual"),
                    "require_manual_recheck": bool(payload.get("require_manual_recheck", True)),
                    "allow_synthetic_recheck": bool(payload.get("allow_synthetic_recheck", False)),
                    "max_items": len(selected),
                },
                counts=_fix_item_counts(items),
                recheck={"suite_id": None, "analytics_report_id": None, "status": "not_started"},
                created_at=now,
                updated_at=now,
                created_by=_bounded(payload.get("created_by"), 120) or "developer",
            )
            write_json(sprint_dir / "fix-sprint.json", sprint.to_dict())
            self.fix_sprint_store._write_items(sprint.fix_sprint_id, items)
            _append_event(sprint_dir / "events.jsonl", "acceptance_fix_sprint_created_from_plan", {"plan_id": plan.plan_id, "item_count": len(items)}, now)
        updated_plan = AcceptanceFixPlan.from_dict(
            {
                **plan.to_dict(),
                "status": "used",
                "execution": {"created_fix_sprint_id": sprint.fix_sprint_id, "created_at": now, "planned_item_ids": [item.get("planned_item_id") for item in selected]},
                "updated_at": now,
            }
        )
        self._write_plan(updated_plan)
        _append_event(self.plan_dir(plan_id) / "events.jsonl", "acceptance_fix_sprint_created_from_plan", {"fix_sprint_id": sprint.fix_sprint_id}, now)
        return {
            "status": "created",
            "fix_sprint": sprint.to_dict(),
            "items": [item.to_dict() for item in items],
            "plan": updated_plan.to_dict(),
            "summary": {"fix_sprint_id": sprint.fix_sprint_id, "item_count": len(items), "plan_id": plan.plan_id},
        }

    def plan_is_stale(self, plan: AcceptanceFixPlan | DomainDocument) -> bool:
        data = plan.to_dict() if isinstance(plan, AcceptanceFixPlan) else _as_document(plan)
        state = self._source_state(data)
        return bool(state.get("analytics_changed") or state.get("kb_entries_changed"))

    def _build_plan(self, plan_id: str, payload: ImplementationDocument, *, now: str, preview: bool = False) -> AcceptanceFixPlan:
        report_id = str(payload.get("analytics_report_id") or "").strip()
        if not report_id:
            raise AcceptanceFixPlanStateError("analytics_report_id is required.")
        analytics = self.analytics_store.get_report(report_id)
        if analytics.get("stale") is True:
            raise AcceptanceFixPlanStateError("Acceptance analytics report is stale. Refresh analytics before creating a Fix Plan.")
        max_items = max(1, min(50, _int(payload.get("max_items"), 20)))
        recommendations = _selected_recommendations(analytics, payload.get("recommendation_ids"), max_items=max_items)
        if not recommendations:
            raise AcceptanceFixPlanStateError("Acceptance analytics report has no recommendations to plan.")
        scope = _scope(payload.get("scope")) or _scope(analytics.get("scope"))
        include_hidden = bool(payload.get("include_hidden_kb", False))
        kb_report, kb_warning = self._kb_report(payload.get("kb_report_id"))
        kb_entries = self._kb_entries(scope, include_hidden=include_hidden)
        planned_items = _planned_items_from_sources(analytics, recommendations, kb_entries, max_items=max_items)
        warnings = []
        if kb_warning:
            warnings.append(kb_warning)
        if kb_report.get("stale"):
            warnings.append("stale_kb_report")
        if include_hidden:
            warnings.append("hidden_entries_included")
        if not kb_entries:
            warnings.append("no_kb_history")
        planning_rule_governance = self._planning_rule_governance_source()
        source_payload = {
            "planning_rules_version": PLANNING_RULES_VERSION,
            "planning_rule_governance": planning_rule_governance,
            "analytics_report_id": report_id,
            "analytics_source_hash": analytics.get("source_hash"),
            "recommendation_hashes": {str(item.get("recommendation_id") or ""): stable_hash(item) for item in recommendations},
            "kb_entry_hashes": _kb_entry_hashes_for_plan(planned_items, self.kb_store),
            "include_hidden_kb": include_hidden,
            "max_items": max_items,
        }
        source_hash = stable_hash(source_payload)
        kb_match_count = sum(int(item.get("knowledge", {}).get("match_count") or 0) for item in planned_items)
        risk_warning_count = sum(len(item.get("knowledge", {}).get("warnings") or []) for item in planned_items)
        status = "warning" if warnings or risk_warning_count else "ready"
        summary = {
            "planned_item_count": len(planned_items),
            "high_priority_count": sum(1 for item in planned_items if int(item.get("planning_score") or 0) >= 75 or item.get("severity") == "high"),
            "kb_match_count": kb_match_count,
            "risk_warning_count": risk_warning_count + len(warnings),
            "recommended_recheck_profile": "developer_manual",
            "manual_recheck_required": True,
            "max_items": max_items,
            "planning_rule_version_id": planning_rule_governance.get("planning_rule_version_id"),
            "governance_status": planning_rule_governance.get("governance_status"),
            "generated_with_active_rules": bool(planning_rule_governance.get("generated_with_active_rules", False)),
        }
        return AcceptanceFixPlan(
            plan_id=plan_id,
            status=status,
            scope=scope,
            source={
                **source_payload,
                "source_hash": source_hash,
                "kb_report_id": kb_report.get("report_id"),
                "kb_source_hash": kb_report.get("source_hash"),
                "kb_report_stale": bool(kb_report.get("stale", False)),
            },
            summary=summary,
            planned_items=planned_items,
            strategy={
                "planning_rules_version": PLANNING_RULES_VERSION,
                "planning_rule_governance": planning_rule_governance,
                "recommended_recheck_profile": "developer_manual",
                "manual_recheck_required": True,
                "suggested_order": [item.get("planned_item_id") for item in planned_items],
                "manual_required": True,
            },
            warnings=sorted(set(warnings)),
            execution={},
            created_at=now,
            updated_at=now,
            created_by=_bounded(payload.get("created_by"), 120) or ("preview" if preview else "developer"),
        )

    def _planning_rule_governance_source(self) -> ImplementationDocument:
        try:
            store = self.planning_rule_governance_store
            if store is not None:
                return fix_plan_governance_projection(store.active_summary())
            return current_fix_plan_governance_source()
        except Exception:
            return {"status": "legacy_default", "governance_status": "legacy_default", "generated_with_active_rules": False, "planning_rule_version_id": None}

    def _kb_report(self, report_id: Any) -> tuple[ImplementationDocument, str]:
        wanted = str(report_id or "").strip()
        if wanted:
            try:
                return self.kb_store.get_report(wanted), ""
            except AcceptanceKnowledgeBaseError:
                return {}, "kb_report_missing"
        try:
            return self.kb_store.latest_report(), ""
        except AcceptanceKnowledgeBaseError:
            return {}, "kb_report_missing"

    def _kb_entries(self, scope: ImplementationDocument, *, include_hidden: bool) -> list[KnowledgeEntry]:
        query = {key: scope.get(key) for key in ("project_id", "release_id", "song_id", "style", "issue_type") if scope.get(key)}
        entries = self.kb_store.search_entries(query, include_hidden=include_hidden)
        return [entry for entry in entries if entry.status == "active" or (include_hidden and entry.status == "hidden")]

    def _source_state(self, plan_data: ImplementationDocument) -> ImplementationDocument:
        source = _as_document(plan_data.get("source"))
        state = {"analytics_changed": False, "kb_entries_changed": False, "source_hash": source.get("source_hash")}
        try:
            report = self.analytics_store.get_report(str(source.get("analytics_report_id") or ""))
        except Exception:
            state["analytics_changed"] = True
            return state
        if report.get("stale") is True or str(report.get("source_hash") or "") != str(source.get("analytics_source_hash") or ""):
            state["analytics_changed"] = True
        expected_recommendations = _as_document(source.get("recommendation_hashes"))
        current = {str(item.get("recommendation_id") or ""): item for item in report.get("recommendations", []) if isinstance(item, dict)}
        for recommendation_id, expected_hash in expected_recommendations.items():
            if recommendation_id not in current or stable_hash(current[recommendation_id]) != expected_hash:
                state["analytics_changed"] = True
        current_entry_hashes = _current_entry_hashes(source.get("kb_entry_hashes"), self.kb_store)
        if current_entry_hashes != (_as_document(source.get("kb_entry_hashes"))):
            state["kb_entries_changed"] = True
        return state

    def _with_stale(self, plan: AcceptanceFixPlan) -> AcceptanceFixPlan:
        if plan.status == "archived":
            return plan
        state = self._source_state(plan.to_dict())
        if state.get("analytics_changed") or state.get("kb_entries_changed"):
            return AcceptanceFixPlan.from_dict({**plan.to_dict(), "status": "stale", "summary": {**plan.summary, "stale": True}, "warnings": sorted(set(plan.warnings + ["source_changed"]))})
        if plan.status == "ready":
            try:
                kb_report_id = str(plan.source.get("kb_report_id") or "")
                if kb_report_id and self.kb_store.get_report(kb_report_id).get("stale") is True:
                    return AcceptanceFixPlan.from_dict({**plan.to_dict(), "status": "warning", "warnings": sorted(set(plan.warnings + ["stale_kb_report"]))})
            except Exception:
                return AcceptanceFixPlan.from_dict({**plan.to_dict(), "status": "warning", "warnings": sorted(set(plan.warnings + ["kb_report_missing"]))})
        return plan

    def _write_plan(self, plan: AcceptanceFixPlan) -> None:
        write_json(self.plan_dir(plan.plan_id) / "fix-plan.json", plan.to_dict())
        write_json(self.plan_dir(plan.plan_id) / "source-summary.json", {"source": plan.source, "summary": plan.summary})

    def _reserve_plan_dir(self) -> tuple[str, Path]:
        index = 1
        while True:
            plan_id = f"afp-{index:06d}"
            plan_dir = self.plan_dir(plan_id)
            try:
                plan_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return plan_id, plan_dir


def fix_plan_summary(plan: AcceptanceFixPlan | DomainDocument | None) -> DomainDocument:
    data = plan.to_dict() if isinstance(plan, AcceptanceFixPlan) else _as_document(plan)
    summary = _as_document(data.get("summary"))
    source = _as_document(data.get("source"))
    execution = _as_document(data.get("execution"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "plan_id": data.get("plan_id"),
            "scope": _as_document(data.get("scope")),
            "planned_item_count": summary.get("planned_item_count", 0),
            "high_priority_count": summary.get("high_priority_count", 0),
            "kb_match_count": summary.get("kb_match_count", 0),
            "risk_warning_count": summary.get("risk_warning_count", 0),
            "created_fix_sprint_id": execution.get("created_fix_sprint_id"),
            "analytics_report_id": source.get("analytics_report_id"),
            "analytics_source_hash": source.get("analytics_source_hash"),
            "kb_report_id": source.get("kb_report_id"),
            "kb_source_hash": source.get("kb_source_hash"),
            "planning_rule_governance": _as_document(source.get("planning_rule_governance")),
            "planning_rule_version_id": (_as_document(source.get("planning_rule_governance"))).get("planning_rule_version_id"),
            "governance_status": (_as_document(source.get("planning_rule_governance"))).get("governance_status", "legacy_default"),
            "source_hash": source.get("source_hash"),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
        }
    )


from song_agent.domains.quality import v142_afp_readiness as _v142_afp_readiness
from song_agent.domains.quality.v142_afp_readiness import (
    latest_fix_plan_summary,
    write_acceptance_fix_plan_summary,
    _planned_items_from_sources,
    _planning_score,
    _knowledge_for_matches,
    _matching_kb_entries,
    _fix_item_from_planned,
    _fix_item_counts,
    _kb_entry_hashes_for_plan,
    _current_entry_hashes,
    _entry_plan_summary,
    _selected_recommendations,
    _selected_planned_items,
    _planning_reason,
    _suggested_actions,
    _recommendation_source,
    _scope,
    _safe_dict,
    _bounded,
    _normalize_text,
    _int,
    _validate_id,
    _lock_for_root,
    _append_event,
)













































_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()

_v142_afp_readiness.bind_globals(globals())
