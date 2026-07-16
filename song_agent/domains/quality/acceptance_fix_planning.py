from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

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
    target: dict[str, Any]
    analytics: dict[str, Any]
    knowledge: dict[str, Any]
    planning_reason: str
    suggested_actions: list[str]
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "PlannedFixItem":
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
    scope: dict[str, Any]
    source: dict[str, Any]
    summary: dict[str, Any]
    planned_items: list[dict[str, Any]]
    strategy: dict[str, Any]
    warnings: list[str]
    execution: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "AcceptanceFixPlan":
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
        self.planning_rule_governance_store = None

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

    def create(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> AcceptanceFixPlan:
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

    def preview(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def create_fix_sprint(self, plan_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def plan_is_stale(self, plan: AcceptanceFixPlan | dict[str, Any]) -> bool:
        data = plan.to_dict() if isinstance(plan, AcceptanceFixPlan) else plan if isinstance(plan, dict) else {}
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
        source = plan_data.get("source") if isinstance(plan_data.get("source"), dict) else {}
        state = {"analytics_changed": False, "kb_entries_changed": False, "source_hash": source.get("source_hash")}
        try:
            report = self.analytics_store.get_report(str(source.get("analytics_report_id") or ""))
        except Exception:
            state["analytics_changed"] = True
            return state
        if report.get("stale") is True or str(report.get("source_hash") or "") != str(source.get("analytics_source_hash") or ""):
            state["analytics_changed"] = True
        expected_recommendations = source.get("recommendation_hashes") if isinstance(source.get("recommendation_hashes"), dict) else {}
        current = {str(item.get("recommendation_id") or ""): item for item in report.get("recommendations", []) if isinstance(item, dict)}
        for recommendation_id, expected_hash in expected_recommendations.items():
            if recommendation_id not in current or stable_hash(current[recommendation_id]) != expected_hash:
                state["analytics_changed"] = True
        current_entry_hashes = _current_entry_hashes(source.get("kb_entry_hashes"), self.kb_store)
        if current_entry_hashes != (source.get("kb_entry_hashes") if isinstance(source.get("kb_entry_hashes"), dict) else {}):
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


def fix_plan_summary(plan: AcceptanceFixPlan | dict[str, Any] | None) -> dict[str, Any]:
    data = plan.to_dict() if isinstance(plan, AcceptanceFixPlan) else plan if isinstance(plan, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "plan_id": data.get("plan_id"),
            "scope": data.get("scope") if isinstance(data.get("scope"), dict) else {},
            "planned_item_count": summary.get("planned_item_count", 0),
            "high_priority_count": summary.get("high_priority_count", 0),
            "kb_match_count": summary.get("kb_match_count", 0),
            "risk_warning_count": summary.get("risk_warning_count", 0),
            "created_fix_sprint_id": execution.get("created_fix_sprint_id"),
            "analytics_report_id": source.get("analytics_report_id"),
            "analytics_source_hash": source.get("analytics_source_hash"),
            "kb_report_id": source.get("kb_report_id"),
            "kb_source_hash": source.get("kb_source_hash"),
            "planning_rule_governance": source.get("planning_rule_governance") if isinstance(source.get("planning_rule_governance"), dict) else {},
            "planning_rule_version_id": (source.get("planning_rule_governance") if isinstance(source.get("planning_rule_governance"), dict) else {}).get("planning_rule_version_id"),
            "governance_status": (source.get("planning_rule_governance") if isinstance(source.get("planning_rule_governance"), dict) else {}).get("governance_status", "legacy_default"),
            "source_hash": source.get("source_hash"),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
        }
    )


def latest_fix_plan_summary(store: AcceptanceFixPlanningStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    for plan in store.list_plans(include_archived=False):
        scope = plan.scope if isinstance(plan.scope, dict) else {}
        if release_id and scope.get("release_id") != release_id:
            continue
        if project_id and scope.get("project_id") != project_id and not any(str((item.get("target") if isinstance(item.get("target"), dict) else {}).get("project_id") or "") == project_id for item in plan.planned_items):
            continue
        return fix_plan_summary(plan)
    return {"status": "missing"}


def write_acceptance_fix_plan_summary(path: Path, store: AcceptanceFixPlanningStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    summary = latest_fix_plan_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary


def _planned_items_from_sources(analytics: ImplementationDocument, recommendations: list[ImplementationDocument], kb_entries: list[KnowledgeEntry], *, max_items: int) -> list[ImplementationDocument]:
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


def _planning_score(*, weakness: int, severity: str, latest_status: str, issue_count: int, knowledge: ImplementationDocument, open_task_count: int) -> int:
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


def _knowledge_for_matches(matches: list[KnowledgeEntry]) -> ImplementationDocument:
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


def _matching_kb_entries(target: ImplementationDocument, issue_types: list[str], entries: list[KnowledgeEntry]) -> list[KnowledgeEntry]:
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


def _fix_item_from_planned(index: int, planned_item: ImplementationDocument, *, plan: AcceptanceFixPlan, now: str) -> AcceptanceFixItem:
    target = _safe_dict(planned_item.get("target"))
    issue_types = target.get("issue_types") if isinstance(target.get("issue_types"), list) else []
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
            "kb_entry_ids": (planned_item.get("knowledge") if isinstance(planned_item.get("knowledge"), dict) else {}).get("top_entry_ids", []),
        },
        target=target,
        title=_bounded(planned_item.get("planning_reason"), 180) or "Knowledge-assisted acceptance fix",
        summary=_bounded(planned_item.get("planning_reason"), 800),
        evidence={
            "planning": {
                "plan_id": plan.plan_id,
                "planned_item_id": planned_item.get("planned_item_id"),
                "planning_score": planned_item.get("planning_score"),
                "knowledge": planned_item.get("knowledge") if isinstance(planned_item.get("knowledge"), dict) else {},
                "suggested_actions": planned_item.get("suggested_actions", []),
            },
            "issue_types": issue_types,
        },
        created_at=now,
        updated_at=now,
    )


def _fix_item_counts(items: list[AcceptanceFixItem]) -> ImplementationDocument:
    return {
        "item_count": len(items),
        "open_item_count": len(items),
        "linked_review_task_count": 0,
        "completed_review_task_count": 0,
        "waived_item_count": 0,
        "fixed_item_count": 0,
    }


def _kb_entry_hashes_for_plan(planned_items: list[ImplementationDocument], kb_store: AcceptanceKnowledgeBaseStore) -> dict[str, str]:
    entry_ids = sorted({str(entry_id) for item in planned_items for entry_id in ((item.get("knowledge") if isinstance(item.get("knowledge"), dict) else {}).get("top_entry_ids") or []) if str(entry_id).strip()})
    return _current_entry_hashes({entry_id: "" for entry_id in entry_ids}, kb_store)


def _current_entry_hashes(expected: Any, kb_store: AcceptanceKnowledgeBaseStore) -> dict[str, str]:
    ids = sorted(str(entry_id) for entry_id in (expected.keys() if isinstance(expected, dict) else []) if str(entry_id).strip())
    hashes: dict[str, str] = {}
    for entry_id in ids:
        try:
            entry = kb_store.read_entry(entry_id)
        except Exception:
            continue
        hashes[entry_id] = stable_hash(_entry_plan_summary(entry))
    return hashes


def _entry_plan_summary(entry: KnowledgeEntry) -> ImplementationDocument:
    return knowledge_entry_summary(entry) | {"source_fingerprint": entry.source.get("source_fingerprint")}


def _selected_recommendations(report: ImplementationDocument, recommendation_ids: Any, *, max_items: int) -> list[ImplementationDocument]:
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


def _selected_planned_items(plan: AcceptanceFixPlan, planned_item_ids: Any) -> list[ImplementationDocument]:
    rows = [item for item in plan.planned_items if isinstance(item, dict)]
    selected_ids = [str(item) for item in planned_item_ids if str(item).strip()] if isinstance(planned_item_ids, list) else []
    if not selected_ids:
        return rows
    wanted = set(selected_ids)
    return [item for item in rows if str(item.get("planned_item_id") or "") in wanted]


def _planning_reason(recommendation: ImplementationDocument, *, weakness: int, knowledge: ImplementationDocument) -> str:
    issues = ", ".join((recommendation.get("evidence") if isinstance(recommendation.get("evidence"), dict) else {}).get("issue_types", []) or ["acceptance"])
    return _bounded(f"{recommendation.get('title') or 'Acceptance weakness'} has weakness score {weakness}. Historical {issues} fixes show {knowledge.get('risk')} risk with {knowledge.get('match_count')} KB match(es).", 500)


def _suggested_actions(knowledge: ImplementationDocument) -> list[str]:
    actions = ["Create ReviewTask after human review", "Require manual recheck", "Refresh delta before closeout"]
    warnings = set(knowledge.get("warnings") if isinstance(knowledge.get("warnings"), list) else [])
    if "waiver_heavy_history" in warnings or "force_closed_history" in warnings:
        actions.append("Avoid waiver-only closeout")
    if "history_ineffective" in warnings:
        actions.append("Prefer smaller targeted fixes")
    return actions[:6]


def _recommendation_source(recommendation: ImplementationDocument) -> ImplementationDocument:
    return {"recommendation_id": recommendation.get("recommendation_id"), "type": recommendation.get("type"), "severity": recommendation.get("severity"), "hash": stable_hash(recommendation)}


def _scope(value: Any) -> ImplementationDocument:
    data = value if isinstance(value, dict) else {}
    scope_type = str(data.get("type") or data.get("scope") or "global")
    return {"type": scope_type, "project_id": data.get("project_id"), "release_id": data.get("release_id"), "suite_id": data.get("suite_id"), "song_id": data.get("song_id"), "style": data.get("style"), "issue_type": data.get("issue_type")}


def _safe_dict(value: Any) -> ImplementationDocument:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _bounded(value: Any, limit: int = 300) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9_ -]+", "", str(value or "").lower()).strip()


def _int(value: Any, default: int) -> int:
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


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]


def _append_event(path: Path, event: str, payload: ImplementationDocument | None = None, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"timestamp": now or now_iso(), "event": event, **(payload or {})})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
