# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReview as AcceptanceFixPlanReview, AcceptanceFixPlanReviewStore as AcceptanceFixPlanReviewStore, fix_plan_review_summary as fix_plan_review_summary
from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlan as AcceptanceFixPlan, AcceptanceFixPlanningStore as AcceptanceFixPlanningStore, fix_plan_summary as fix_plan_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.creation.planning_rule_governance import PlanningRuleGovernanceStore as PlanningRuleGovernanceStore, governance_summary as governance_summary
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text


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
    scope: ImplementationDocument
    active_version: ImplementationDocument
    source: ImplementationDocument
    summary: ImplementationDocument
    adoption: ImplementationDocument
    before_after: ImplementationDocument
    risk_drift: ImplementationDocument
    version_metrics: list[ImplementationDocument]
    plan_samples: list[ImplementationDocument]
    review_samples: list[ImplementationDocument]
    warnings: list[str]
    integrity_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "PlanningRuleImpactReport":
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

    def latest_path(self, scope: DomainDocument | None = None) -> Path:
        return self.root / f"latest-{_scope_key(_scope(scope))}.json"

    def refresh(self, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRuleImpactReport:
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

    def refresh_report(self, report_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRuleImpactReport:
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

    def latest_summary(self, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
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

    def report_is_stale(self, report: PlanningRuleImpactReport | DomainDocument) -> bool:
        data = report.to_dict() if isinstance(report, PlanningRuleImpactReport) else _as_document(report)
        if data.get("status") == "archived":
            return False
        if data.get("status") == "stale":
            return True
        source = _as_document(data.get("source"))
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

    def report_integrity_ok(self, report: PlanningRuleImpactReport | DomainDocument) -> bool:
        data = report.to_dict() if isinstance(report, PlanningRuleImpactReport) else _as_document(report)
        expected = str(data.get("integrity_hash") or data.get("report_hash") or "")
        return bool(expected and expected == planning_rule_impact_report_hash(data))

    def _build_report(self, report_id: str, payload: ImplementationDocument, *, created_at: str, now: str) -> PlanningRuleImpactReport:
        state = self._source_state(payload)
        active = _as_document(state.get("active_version"))
        plan_samples = state["plan_samples"]
        review_samples = state["review_samples"]
        version_metrics = _version_metrics(plan_samples, review_samples)
        adoption = _adoption_metrics(plan_samples, active.get("version_id"))
        before_after = _before_after_metrics(version_metrics, active.get("version_id"))
        risk_drift = _risk_drift_metrics(version_metrics, active.get("version_id"), before_after)
        warnings = _impact_warnings(state, adoption, risk_drift)
        recommendation = _recommendation(adoption, before_after, risk_drift, warnings)
        active_metric: DomainDocument = next(
            (item for item in version_metrics if item.get("version_id") == active.get("version_id")),
            {},
        )
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

    def _source_state(self, payload: ImplementationDocument | None = None) -> ImplementationDocument:
        payload = payload or {}
        scope = _scope(payload.get("scope"))
        include_legacy = bool(payload.get("include_legacy", True))
        include_superseded = bool(payload.get("include_superseded", True))
        active_version = self.governance_store.active_version()
        active_summary = self.governance_store.active_summary()
        active_payload: ImplementationDocument = {}
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

    def _plan_samples(self, *, scope: ImplementationDocument, include_legacy: bool, include_superseded: bool, active_version_id: str | None) -> list[ImplementationDocument]:
        rows: list[ImplementationDocument] = []
        for plan in self.plan_store.list_plans(include_archived=False):
            if not _plan_matches_scope(plan, scope):
                continue
            summary = fix_plan_summary(plan)
            governance = _as_document(plan.source.get("planning_rule_governance"))
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

    def _review_samples(self, plan_samples: list[ImplementationDocument]) -> list[ImplementationDocument]:
        plan_versions = {str(item.get("plan_id") or ""): str(item.get("version_id") or "legacy_default") for item in plan_samples}
        rows: list[ImplementationDocument] = []
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


from song_agent.domains.creation import v142_pri_readiness as _v142_pri_readiness
from song_agent.domains.creation.v142_pri_readiness import planning_rule_impact_summary as planning_rule_impact_summary, latest_planning_rule_impact_summary as latest_planning_rule_impact_summary, write_planning_rule_impact_summary as write_planning_rule_impact_summary, planning_rule_impact_report_hash as planning_rule_impact_report_hash, _version_metrics as _version_metrics, _adoption_metrics as _adoption_metrics, _before_after_metrics as _before_after_metrics, _risk_drift_metrics as _risk_drift_metrics, _impact_warnings as _impact_warnings, _recommendation as _recommendation, _report_status as _report_status, _readiness_status as _readiness_status, _plan_matches_scope as _plan_matches_scope, _plan_project_ids as _plan_project_ids, _report_project_ids as _report_project_ids, _review_observed_effectiveness as _review_observed_effectiveness, _scope as _scope, _scope_key as _scope_key, _safe_dict as _safe_dict, _bounded as _bounded, _validate_id as _validate_id, _int as _int, _mean as _mean, _rate as _rate, _weighted_average as _weighted_average, _lock_for_root as _lock_for_root, _append_event as _append_event



















































_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()

_v142_pri_readiness.bind_globals(globals())
