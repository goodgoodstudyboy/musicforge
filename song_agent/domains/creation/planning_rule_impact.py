from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.application.legacy_dependencies.acceptance_fix_plan_reviews import AcceptanceFixPlanReview, AcceptanceFixPlanReviewStore, fix_plan_review_summary
from song_agent.application.legacy_dependencies.acceptance_fix_planning import AcceptanceFixPlan, AcceptanceFixPlanningStore, fix_plan_summary
from song_agent.application.legacy_dependencies.music_acceptance import stable_hash
from song_agent.domains.creation.planning_rule_governance import PlanningRuleGovernanceStore, governance_summary
from song_agent.domains.studio.projectio import now_iso, read_json, write_json
from song_agent.domains.studio.projects import ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text


PLANNING_RULE_IMPACT_ROOT = Path(".musicforge") / "planning-rule-impact"
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


class PlanningRuleImpactError(ValueError):
    pass


class PlanningRuleImpactNotFoundError(PlanningRuleImpactError):
    pass


class PlanningRuleImpactStateError(PlanningRuleImpactError):
    pass


@dataclass
class PlanningRuleImpactReport:
    report_id: str
    status: str
    scope: dict[str, Any]
    active_version: dict[str, Any]
    source: dict[str, Any]
    summary: dict[str, Any]
    adoption: dict[str, Any]
    before_after: dict[str, Any]
    risk_drift: dict[str, Any]
    version_metrics: list[dict[str, Any]]
    plan_samples: list[dict[str, Any]]
    review_samples: list[dict[str, Any]]
    warnings: list[str]
    integrity_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": PLANNING_RULE_IMPACT_SCHEMA_VERSION,
                "report_id": self.report_id,
                "status": self.status,
                "scope": self.scope,
                "active_version": self.active_version,
                "source": self.source,
                "summary": self.summary,
                "adoption": self.adoption,
                "before_after": self.before_after,
                "risk_drift": self.risk_drift,
                "version_metrics": self.version_metrics,
                "plan_samples": self.plan_samples,
                "review_samples": self.review_samples,
                "warnings": self.warnings,
                "integrity_hash": self.integrity_hash,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningRuleImpactReport":
        now = now_iso()
        status = str(data.get("status") or "warning")
        if status not in IMPACT_REPORT_STATUSES:
            status = "warning"
        return cls(
            report_id=_validate_id(str(data.get("report_id") or "prgir-000001"), "prgir"),
            status=status,
            scope=_scope(data.get("scope")),
            active_version=_safe_dict(data.get("active_version")),
            source=_safe_dict(data.get("source")),
            summary=_safe_dict(data.get("summary")),
            adoption=_safe_dict(data.get("adoption")),
            before_after=_safe_dict(data.get("before_after")),
            risk_drift=_safe_dict(data.get("risk_drift")),
            version_metrics=[_safe_dict(item) for item in data.get("version_metrics", []) if isinstance(item, dict)] if isinstance(data.get("version_metrics"), list) else [],
            plan_samples=[_safe_dict(item) for item in data.get("plan_samples", []) if isinstance(item, dict)] if isinstance(data.get("plan_samples"), list) else [],
            review_samples=[_safe_dict(item) for item in data.get("review_samples", []) if isinstance(item, dict)] if isinstance(data.get("review_samples"), list) else [],
            warnings=[_bounded(item, 180) for item in data.get("warnings", []) if str(item).strip()] if isinstance(data.get("warnings"), list) else [],
            integrity_hash=str(data.get("integrity_hash") or data.get("report_hash") or ""),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


class PlanningRuleImpactStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        governance_store: PlanningRuleGovernanceStore | None = None,
        plan_store: AcceptanceFixPlanningStore | None = None,
        review_store: AcceptanceFixPlanReviewStore | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self.root = Path(root or PLANNING_RULE_IMPACT_ROOT)
        self.project_store = project_store or getattr(governance_store, "project_store", None) or getattr(plan_store, "project_store", None) or ProjectStore()
        self.plan_store = plan_store or AcceptanceFixPlanningStore(project_store=self.project_store)
        self.review_store = review_store or AcceptanceFixPlanReviewStore(plan_store=self.plan_store, fix_sprint_store=self.plan_store.fix_sprint_store, kb_store=self.plan_store.kb_store, project_store=self.project_store)
        self.governance_store = governance_store or PlanningRuleGovernanceStore(project_store=self.project_store)
        self.lock = _lock_for_root(self.root.resolve())

    def reports_root(self) -> Path:
        return self.root / "reports"

    def report_dir(self, report_id: str) -> Path:
        base = self.reports_root().resolve()
        target = (base / _validate_id(report_id, "prgir")).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise PlanningRuleImpactError("Refusing to operate outside planning rule impact reports.") from exc
        return target

    def latest_path(self, scope: dict[str, Any] | None = None) -> Path:
        return self.root / f"latest-{_scope_key(_scope(scope))}.json"

    def refresh(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRuleImpactReport:
        payload = payload or {}
        now = now or now_iso()
        with self.lock:
            report_id, report_dir = self._reserve_report_dir()
            report = self._build_report(report_id, payload, created_at=now, now=now)
            write_json(report_dir / "report.json", report.to_dict())
            write_json(report_dir / "source-summary.json", {"source": report.source, "summary": report.summary})
            _append_event(report_dir / "events.jsonl", "planning_rule_impact_report_refreshed", {"report_id": report_id, "status": report.status}, now)
            self.latest_path(report.scope).parent.mkdir(parents=True, exist_ok=True)
            write_json(self.latest_path(report.scope), report.to_dict())
            return report

    def refresh_report(self, report_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRuleImpactReport:
        existing = self.get_report(report_id)
        payload = {**(payload or {}), "scope": existing.scope, "include_legacy": existing.source.get("include_legacy", True), "include_superseded": existing.source.get("include_superseded", True)}
        report = self._build_report(existing.report_id, payload, created_at=existing.created_at, now=now or now_iso())
        self._write_report(report)
        _append_event(self.report_dir(report_id) / "events.jsonl", "planning_rule_impact_report_refreshed", {"report_id": report_id, "status": report.status}, now)
        return report

    def archive_report(self, report_id: str, *, now: str | None = None) -> PlanningRuleImpactReport:
        report = self.get_report(report_id)
        archived = PlanningRuleImpactReport.from_dict({**report.to_dict(), "status": "archived", "updated_at": now or now_iso()})
        archived.integrity_hash = planning_rule_impact_report_hash(archived)
        self._write_report(archived)
        _append_event(self.report_dir(report_id) / "events.jsonl", "planning_rule_impact_report_archived", {"report_id": report_id}, now)
        return archived

    def get_report(self, report_id: str) -> PlanningRuleImpactReport:
        path = self.report_dir(report_id) / "report.json"
        if not path.exists():
            raise PlanningRuleImpactNotFoundError(report_id)
        return self._with_stale(PlanningRuleImpactReport.from_dict(read_json(path)))

    def list_reports(self, *, include_archived: bool = False, release_id: str | None = None, project_id: str | None = None) -> list[PlanningRuleImpactReport]:
        rows: list[PlanningRuleImpactReport] = []
        if not self.reports_root().exists():
            return rows
        for path in self.reports_root().glob("prgir-*/report.json"):
            try:
                report = self._with_stale(PlanningRuleImpactReport.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if report.status == "archived" and not include_archived:
                continue
            if release_id and report.scope.get("release_id") != release_id:
                continue
            if project_id and report.scope.get("project_id") != project_id and project_id not in _report_project_ids(report):
                continue
            rows.append(report)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def latest_summary(self, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
        scope = _scope({"type": "release" if release_id else "project" if project_id else "global", "release_id": release_id, "project_id": project_id})
        path = self.latest_path(scope)
        if path.exists():
            try:
                report = self._with_stale(PlanningRuleImpactReport.from_dict(read_json(path)))
                return planning_rule_impact_summary(report)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        reports = self.list_reports(release_id=release_id, project_id=project_id)
        if not reports:
            return {"status": "missing"}
        return planning_rule_impact_summary(reports[0])

    def report_is_stale(self, report: PlanningRuleImpactReport | dict[str, Any]) -> bool:
        data = report.to_dict() if isinstance(report, PlanningRuleImpactReport) else report if isinstance(report, dict) else {}
        if data.get("status") == "archived":
            return False
        if data.get("status") == "stale":
            return True
        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        scope = _scope(data.get("scope"))
        current = self._source_state(
            {
                "scope": scope,
                "include_legacy": source.get("include_legacy", True),
                "include_superseded": source.get("include_superseded", True),
            }
        )
        keys = ("source_hash", "governance_active_hash", "active_version_source_hash")
        return any(str(current.get(key) or "") != str(source.get(key) or "") for key in keys) or current.get("plan_hashes") != source.get("plan_hashes") or current.get("review_hashes") != source.get("review_hashes") or current.get("version_hashes") != source.get("version_hashes") or bool(current.get("source_stale", False))

    def report_integrity_ok(self, report: PlanningRuleImpactReport | dict[str, Any]) -> bool:
        data = report.to_dict() if isinstance(report, PlanningRuleImpactReport) else report if isinstance(report, dict) else {}
        expected = str(data.get("integrity_hash") or data.get("report_hash") or "")
        return bool(expected and expected == planning_rule_impact_report_hash(data))

    def _build_report(self, report_id: str, payload: dict[str, Any], *, created_at: str, now: str) -> PlanningRuleImpactReport:
        state = self._source_state(payload)
        active = state.get("active_version") if isinstance(state.get("active_version"), dict) else {}
        plan_samples = state["plan_samples"]
        review_samples = state["review_samples"]
        version_metrics = _version_metrics(plan_samples, review_samples)
        adoption = _adoption_metrics(plan_samples, active.get("version_id"))
        before_after = _before_after_metrics(version_metrics, active.get("version_id"))
        risk_drift = _risk_drift_metrics(version_metrics, active.get("version_id"), before_after)
        warnings = _impact_warnings(state, adoption, risk_drift)
        recommendation = _recommendation(adoption, before_after, risk_drift, warnings)
        active_metric = next((item for item in version_metrics if item.get("version_id") == active.get("version_id")), {})
        status = _report_status(state, recommendation, warnings, active)
        summary = {
            "status": status,
            "report_id": report_id,
            "active_version_id": active.get("version_id"),
            "observed_plan_count": len(plan_samples),
            "observed_review_count": len(review_samples),
            "manual_review_count": _int(active_metric.get("manual_review_count"), 0),
            "synthetic_review_count": _int(active_metric.get("synthetic_review_count"), 0),
            "adoption_status": adoption.get("status"),
            "effectiveness_delta": before_after.get("effectiveness_delta"),
            "ranking_alignment_delta": before_after.get("ranking_alignment_delta"),
            "waiver_rate_delta": risk_drift.get("waiver_rate_delta"),
            "force_close_rate_delta": risk_drift.get("force_close_rate_delta"),
            "synthetic_only_rate_delta": risk_drift.get("synthetic_only_rate_delta"),
            "recommendation": recommendation,
            "rollback_recommended": recommendation == "rollback_recommended",
            "readiness_status": _readiness_status(recommendation, warnings),
            "stale": bool(state.get("source_stale", False)),
        }
        report = PlanningRuleImpactReport(
            report_id=report_id,
            status=status,
            scope=state["scope"],
            active_version=active,
            source={
                "source_hash": state["source_hash"],
                "engine_version": PLANNING_RULE_IMPACT_ENGINE_VERSION,
                "scope": state["scope"],
                "include_legacy": state.get("include_legacy", True),
                "include_superseded": state.get("include_superseded", True),
                "governance_active_hash": state.get("governance_active_hash"),
                "active_version_source_hash": active.get("source_hash"),
                "fix_plan_ids": [item.get("plan_id") for item in plan_samples],
                "outcome_review_ids": [item.get("review_id") for item in review_samples],
                "version_ids": [item.get("version_id") for item in state.get("version_samples", [])],
                "plan_hashes": state.get("plan_hashes", {}),
                "review_hashes": state.get("review_hashes", {}),
                "version_hashes": state.get("version_hashes", {}),
                "source_stale": bool(state.get("source_stale", False)),
            },
            summary=summary,
            adoption=adoption,
            before_after=before_after,
            risk_drift=risk_drift,
            version_metrics=version_metrics,
            plan_samples=plan_samples,
            review_samples=review_samples,
            warnings=sorted(set(warnings)),
            created_at=created_at,
            updated_at=now,
            created_by=_bounded(payload.get("created_by"), 120) or "developer",
        )
        report.integrity_hash = planning_rule_impact_report_hash(report)
        return report

    def _source_state(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        scope = _scope(payload.get("scope"))
        include_legacy = bool(payload.get("include_legacy", True))
        include_superseded = bool(payload.get("include_superseded", True))
        active_version = self.governance_store.active_version()
        active_summary = self.governance_store.active_summary()
        active_payload: dict[str, Any] = {}
        source_stale = False
        if active_version is None:
            active_payload = {"status": "missing", "version_id": None, "integrity_ok": False, "evidence_stale": True}
            source_stale = True
        else:
            evidence_stale = self.governance_store.version_evidence_is_stale(active_version)
            frozen_integrity_ok = self.governance_store.frozen_ruleset_integrity_ok(active_version)
            version_source_integrity_ok = self.governance_store.version_source_integrity_ok(active_version)
            active_payload = {
                **governance_summary(active_version, active=self.governance_store.active_pointer(), evidence_stale=evidence_stale),
                "version_id": active_version.version_id,
                "status": active_version.status,
                "integrity_ok": frozen_integrity_ok and version_source_integrity_ok,
                "frozen_ruleset_integrity_ok": frozen_integrity_ok,
                "version_source_integrity_ok": version_source_integrity_ok,
                "evidence_stale": evidence_stale,
            }
            if evidence_stale or not frozen_integrity_ok or not version_source_integrity_ok:
                source_stale = True
        plans = self._plan_samples(scope=scope, include_legacy=include_legacy, include_superseded=include_superseded, active_version_id=active_payload.get("version_id"))
        reviews = self._review_samples(plans)
        versions = [governance_summary(version, active=self.governance_store.active_pointer(), evidence_stale=self.governance_store.version_evidence_is_stale(version)) for version in self.governance_store.list_versions(include_archived=True)]
        source_stale = source_stale or any(item.get("stale") for item in plans) or any(item.get("stale") for item in reviews)
        plan_hashes = {str(item.get("plan_id")): item.get("plan_hash") for item in plans}
        review_hashes = {str(item.get("review_id")): item.get("review_hash") for item in reviews}
        version_hashes = {str(item.get("version_id")): stable_hash(item) for item in versions if item.get("version_id")}
        source_payload = {
            "engine_version": PLANNING_RULE_IMPACT_ENGINE_VERSION,
            "scope": scope,
            "include_legacy": include_legacy,
            "include_superseded": include_superseded,
            "active": active_payload,
            "active_summary": active_summary,
            "plans": plan_hashes,
            "reviews": review_hashes,
            "versions": version_hashes,
        }
        return {
            "scope": scope,
            "include_legacy": include_legacy,
            "include_superseded": include_superseded,
            "active_version": active_payload,
            "governance_active_hash": stable_hash({"active": active_payload, "summary": active_summary}),
            "active_version_source_hash": active_payload.get("source_hash"),
            "plan_samples": plans,
            "review_samples": reviews,
            "version_samples": versions,
            "plan_hashes": plan_hashes,
            "review_hashes": review_hashes,
            "version_hashes": version_hashes,
            "source_hash": stable_hash(source_payload),
            "source_stale": source_stale,
        }

    def _plan_samples(self, *, scope: dict[str, Any], include_legacy: bool, include_superseded: bool, active_version_id: str | None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for plan in self.plan_store.list_plans(include_archived=False):
            if not _plan_matches_scope(plan, scope):
                continue
            summary = fix_plan_summary(plan)
            governance = plan.source.get("planning_rule_governance") if isinstance(plan.source.get("planning_rule_governance"), dict) else {}
            version_id = str(governance.get("planning_rule_version_id") or governance.get("version_id") or "legacy_default")
            if version_id == "legacy_default" and not include_legacy:
                continue
            if active_version_id and version_id not in {active_version_id, "legacy_default"} and not include_superseded:
                continue
            row = {
                "plan_id": plan.plan_id,
                "status": plan.status,
                "scope": plan.scope,
                "project_ids": _plan_project_ids(plan),
                "version_id": version_id,
                "governance_status": governance.get("governance_status", "legacy_default"),
                "generated_with_active_rules": bool(governance.get("generated_with_active_rules", False)),
                "created_fix_sprint_id": plan.execution.get("created_fix_sprint_id"),
                "planned_item_count": summary.get("planned_item_count", 0),
                "risk_warning_count": summary.get("risk_warning_count", 0),
                "warnings": plan.warnings,
                "stale": self.plan_store.plan_is_stale(plan) or plan.status == "stale",
                "source_hash": plan.source.get("source_hash"),
            }
            row["plan_hash"] = stable_hash(row)
            rows.append(sanitize_metadata(row))
        return sorted(rows, key=lambda item: str(item.get("plan_id") or ""))

    def _review_samples(self, plan_samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        plan_versions = {str(item.get("plan_id") or ""): str(item.get("version_id") or "legacy_default") for item in plan_samples}
        rows: list[dict[str, Any]] = []
        for review in self.review_store.list_reviews(include_archived=False):
            if review.plan_id not in plan_versions:
                continue
            summary = fix_plan_review_summary(review)
            row = {
                "review_id": review.review_id,
                "plan_id": review.plan_id,
                "fix_sprint_id": review.fix_sprint_id,
                "status": review.status,
                "version_id": plan_versions.get(review.plan_id, "legacy_default"),
                "plan_effectiveness_score": summary.get("plan_effectiveness_score"),
                "ranking_alignment_score": summary.get("ranking_alignment_score"),
                "manual_recheck_confirmed": bool(summary.get("manual_recheck_confirmed", False)),
                "synthetic_only": bool(summary.get("synthetic_only", False)),
                "manual_review_count": summary.get("manual_review_count", 0),
                "synthetic_review_count": summary.get("synthetic_review_count", 0),
                "manual_accepted_count": summary.get("manual_accepted_count", 0),
                "synthetic_accepted_count": summary.get("synthetic_accepted_count", 0),
                "waived_item_count": summary.get("waived_item_count", 0),
                "planned_item_count": summary.get("planned_item_count", 0),
                "warning_count": summary.get("warning_count", 0),
                "force_closed": "force_closed" in (summary.get("warnings") or review.warnings),
                "stale": self.review_store.review_is_stale(review) or review.status == "stale",
                "source_hash": review.source.get("source_hash"),
                "warnings": review.warnings,
            }
            row["observed_effectiveness_score"] = _review_observed_effectiveness(review)
            row["review_hash"] = stable_hash(row)
            rows.append(sanitize_metadata(row))
        return sorted(rows, key=lambda item: str(item.get("review_id") or ""))

    def _with_stale(self, report: PlanningRuleImpactReport) -> PlanningRuleImpactReport:
        if report.status == "archived":
            return report
        if not self.report_is_stale(report):
            return report
        stale = PlanningRuleImpactReport.from_dict({**report.to_dict(), "status": "stale", "summary": {**report.summary, "status": "stale", "stale": True}, "warnings": sorted(set(report.warnings + ["source_changed"]))})
        stale.integrity_hash = planning_rule_impact_report_hash(stale)
        return stale

    def _write_report(self, report: PlanningRuleImpactReport) -> None:
        report_dir = self.report_dir(report.report_id)
        report.integrity_hash = planning_rule_impact_report_hash(report)
        write_json(report_dir / "report.json", report.to_dict())
        write_json(report_dir / "source-summary.json", {"source": report.source, "summary": report.summary})
        write_json(self.latest_path(report.scope), report.to_dict())

    def _reserve_report_dir(self) -> tuple[str, Path]:
        self.reports_root().mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            report_id = f"prgir-{index:06d}"
            report_dir = self.report_dir(report_id)
            try:
                report_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return report_id, report_dir


def planning_rule_impact_summary(report: PlanningRuleImpactReport | dict[str, Any] | None) -> dict[str, Any]:
    data = report.to_dict() if isinstance(report, PlanningRuleImpactReport) else report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    risk = data.get("risk_drift") if isinstance(data.get("risk_drift"), dict) else {}
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
            "source_hash": (data.get("source") if isinstance(data.get("source"), dict) else {}).get("source_hash"),
            "integrity_hash": integrity_hash,
            "integrity_ok": bool(integrity_hash and integrity_hash == planning_rule_impact_report_hash(data)),
        }
    )


def latest_planning_rule_impact_summary(store: PlanningRuleImpactStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    return store.latest_summary(release_id=release_id, project_id=project_id)


def write_planning_rule_impact_summary(path: Path, store: PlanningRuleImpactStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    summary = latest_planning_rule_impact_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary


def planning_rule_impact_report_hash(report: PlanningRuleImpactReport | dict[str, Any] | None) -> str:
    if isinstance(report, PlanningRuleImpactReport):
        data = {key: getattr(report, key) for key in IMPACT_REPORT_INTEGRITY_FIELDS}
    else:
        data = report if isinstance(report, dict) else {}
    payload = {key: data.get(key) for key in IMPACT_REPORT_INTEGRITY_FIELDS}
    return stable_hash(payload)


def _version_metrics(plan_samples: list[dict[str, Any]], review_samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _adoption_metrics(plan_samples: list[dict[str, Any]], active_version_id: str | None) -> dict[str, Any]:
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


def _before_after_metrics(version_metrics: list[dict[str, Any]], active_version_id: str | None) -> dict[str, Any]:
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


def _risk_drift_metrics(version_metrics: list[dict[str, Any]], active_version_id: str | None, before_after: dict[str, Any]) -> dict[str, Any]:
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


def _impact_warnings(state: dict[str, Any], adoption: dict[str, Any], risk: dict[str, Any]) -> list[str]:
    warnings = list(risk.get("warnings") if isinstance(risk.get("warnings"), list) else [])
    active = state.get("active_version") if isinstance(state.get("active_version"), dict) else {}
    if active.get("status") == "missing":
        warnings.append("missing_active_rule_version")
    if active.get("evidence_stale") or active.get("integrity_ok") is False:
        warnings.append("active_rule_evidence_stale_or_invalid")
    if adoption.get("status") in {"missing", "low", "partial"}:
        warnings.append(f"adoption_{adoption.get('status')}")
    if state.get("source_stale"):
        warnings.append("source_stale")
    return sorted(set(warnings))


def _recommendation(adoption: dict[str, Any], before_after: dict[str, Any], risk: dict[str, Any], warnings: list[str]) -> str:
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


def _report_status(state: dict[str, Any], recommendation: str, warnings: list[str], active: dict[str, Any]) -> str:
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


def _plan_matches_scope(plan: AcceptanceFixPlan, scope: dict[str, Any]) -> bool:
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
        return any(str((item.get("target") if isinstance(item.get("target"), dict) else {}).get("project_id") or "") == project_id for item in plan.planned_items)
    return True


def _plan_project_ids(plan: AcceptanceFixPlan) -> list[str]:
    ids = set()
    if plan.scope.get("project_id"):
        ids.add(str(plan.scope["project_id"]))
    for item in plan.planned_items:
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
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
        outcome = item.get("outcome") if isinstance(item.get("outcome"), dict) else {}
        values.append(outcome.get("observed_effectiveness_score"))
    return _mean(values)


def _scope(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    scope_type = str(raw.get("type") or ("release" if raw.get("release_id") else "project" if raw.get("project_id") else "global"))
    if scope_type not in {"global", "release", "project"}:
        scope_type = "global"
    return sanitize_metadata({"type": scope_type, "release_id": _bounded(raw.get("release_id"), 120), "project_id": _bounded(raw.get("project_id"), 120)})


def _scope_key(scope: dict[str, Any]) -> str:
    if scope.get("type") == "release" and scope.get("release_id"):
        return "release-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", str(scope["release_id"]))
    if scope.get("type") == "project" and scope.get("project_id"):
        return "project-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", str(scope["project_id"]))
    return "global"


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{6}}", text):
        raise PlanningRuleImpactError(f"Invalid {prefix} id.")
    return text


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[Any]) -> int:
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


def _weighted_average(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> int:
    total_weight = sum(max(0, _int(item.get(weight_key), 0)) for item in rows)
    if total_weight <= 0:
        return 0
    total = sum(_int(item.get(value_key), 0) * max(0, _int(item.get(weight_key), 0)) for item in rows)
    return int(round(total / total_weight))


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]


def _append_event(path: Path, event: str, payload: dict[str, Any], now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"timestamp": now or now_iso(), "event": event, **payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
