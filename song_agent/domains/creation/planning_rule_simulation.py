from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list

import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReview as AcceptanceFixPlanReview, AcceptanceFixPlanReviewError as AcceptanceFixPlanReviewError, AcceptanceFixPlanReviewNotFoundError as AcceptanceFixPlanReviewNotFoundError, AcceptanceFixPlanReviewStore as AcceptanceFixPlanReviewStore, fix_plan_review_summary as fix_plan_review_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text


PLANNING_RULE_SIMULATION_ROOT = Path(".musicforge") / "planning-rule-simulations"
PLANNING_RULESET_SCHEMA_VERSION = "planning_ruleset.v1"
PLANNING_RULE_SIMULATION_SCHEMA_VERSION = "planning_rule_simulation.v1"
PLANNING_RULE_SIMULATION_ENGINE_VERSION = "planning_rule_simulation_engine.v1"
RULESET_STATUSES = {"draft", "active_candidate", "archived"}
SIMULATION_STATUSES = {"ready", "warning", "blocked", "stale", "archived"}


class PlanningRuleSimulationError(ValueError):
    pass


class PlanningRuleSimulationNotFoundError(PlanningRuleSimulationError):
    pass


class PlanningRuleSimulationStateError(PlanningRuleSimulationError):
    pass


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


DEFAULT_BOUNDS = {"min_score": 0, "max_score": 100, "high_score_threshold": 75}
BASELINE_RULESET: dict[str, Any] = {
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

RULESET_TEMPLATES: dict[str, dict[str, Any]] = {
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


@dataclass
class PlanningRuleSet:
    ruleset_id: str
    name: str
    description: str
    status: str
    base_rules_version: str
    weights: dict[str, Any]
    penalties: dict[str, Any]
    confidence: dict[str, Any]
    bounds: dict[str, Any]
    source: dict[str, Any]
    created_at: str
    updated_at: str
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": PLANNING_RULESET_SCHEMA_VERSION,
                "ruleset_id": self.ruleset_id,
                "name": self.name,
                "description": self.description,
                "status": self.status,
                "base_rules_version": self.base_rules_version,
                "weights": self.weights,
                "penalties": self.penalties,
                "confidence": self.confidence,
                "bounds": self.bounds,
                "source": self.source,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningRuleSet":
        now = now_iso()
        status = str(data.get("status") or "draft")
        if status not in RULESET_STATUSES:
            status = "draft"
        return cls(
            ruleset_id=_validate_id(str(data.get("ruleset_id") or "afprs-000001"), "afprs"),
            name=_bounded(data.get("name"), 120) or "Planning Rule Set",
            description=_bounded(data.get("description"), 500),
            status=status,
            base_rules_version=_bounded(data.get("base_rules_version"), 80) or "acceptance_fix_planning.v1",
            weights=_numeric_map(data.get("weights"), -50, 100),
            penalties=_numeric_map(data.get("penalties"), 0, 100),
            confidence=_numeric_map(data.get("confidence"), -50, 100),
            bounds=_bounds(data.get("bounds")),
            source=_safe_dict(data.get("source")),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


@dataclass
class PlanningRuleSimulationReport:
    simulation_id: str
    ruleset_id: str
    status: str
    scope: dict[str, Any]
    source: dict[str, Any]
    summary: dict[str, Any]
    review_results: list[dict[str, Any]]
    rule_effects: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": PLANNING_RULE_SIMULATION_SCHEMA_VERSION,
                "simulation_id": self.simulation_id,
                "ruleset_id": self.ruleset_id,
                "status": self.status,
                "scope": self.scope,
                "source": self.source,
                "summary": self.summary,
                "review_results": self.review_results,
                "rule_effects": self.rule_effects,
                "warnings": self.warnings,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningRuleSimulationReport":
        now = now_iso()
        status = str(data.get("status") or "ready")
        if status not in SIMULATION_STATUSES:
            status = "ready"
        return cls(
            simulation_id=_validate_id(str(data.get("simulation_id") or "afpsim-000001"), "afpsim"),
            ruleset_id=_validate_id(str(data.get("ruleset_id") or "afprs-000001"), "afprs"),
            status=status,
            scope=_safe_dict(data.get("scope")),
            source=_safe_dict(data.get("source")),
            summary=_safe_dict(data.get("summary")),
            review_results=[_safe_dict(item) for item in data.get("review_results", []) if isinstance(item, dict)] if isinstance(data.get("review_results"), list) else [],
            rule_effects=[_safe_dict(item) for item in data.get("rule_effects", []) if isinstance(item, dict)] if isinstance(data.get("rule_effects"), list) else [],
            warnings=[_bounded(item, 180) for item in data.get("warnings", []) if str(item).strip()] if isinstance(data.get("warnings"), list) else [],
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


class PlanningRuleSimulationStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        review_store: AcceptanceFixPlanReviewStore | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self.root = Path(root or PLANNING_RULE_SIMULATION_ROOT)
        self.project_store = project_store or getattr(review_store, "project_store", None) or ProjectStore()
        self.review_store = review_store or AcceptanceFixPlanReviewStore(project_store=self.project_store)
        self.lock = _lock_for_root(self.root.resolve())

    def rulesets_root(self) -> Path:
        return self.root / "rulesets"

    def simulations_root(self) -> Path:
        return self.root / "simulations"

    def ruleset_dir(self, ruleset_id: str) -> Path:
        return _safe_child(self.rulesets_root(), _validate_id(ruleset_id, "afprs"), "planning ruleset")

    def simulation_dir(self, simulation_id: str) -> Path:
        return _safe_child(self.simulations_root(), _validate_id(simulation_id, "afpsim"), "planning simulation")

    def list_rulesets(self, *, include_archived: bool = False) -> list[PlanningRuleSet]:
        rows: list[PlanningRuleSet] = []
        if not self.rulesets_root().exists():
            return rows
        for path in self.rulesets_root().glob("afprs-*/ruleset.json"):
            try:
                ruleset = PlanningRuleSet.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if ruleset.status == "archived" and not include_archived:
                continue
            rows.append(ruleset)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def create_ruleset(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRuleSet:
        payload = payload or {}
        now = now or now_iso()
        with self.lock:
            ruleset_id, ruleset_dir = self._reserve_ruleset_dir()
            ruleset = _ruleset_from_payload(ruleset_id, payload, now=now)
            write_json(ruleset_dir / "ruleset.json", ruleset.to_dict())
            _append_event(ruleset_dir / "events.jsonl", "planning_ruleset_created", {"ruleset_id": ruleset.ruleset_id, "template": ruleset.source.get("template")}, now)
            return ruleset

    def read_ruleset(self, ruleset_id: str) -> PlanningRuleSet:
        path = self.ruleset_dir(ruleset_id) / "ruleset.json"
        if not path.exists():
            raise PlanningRuleSimulationNotFoundError(ruleset_id)
        return PlanningRuleSet.from_dict(read_json(path))

    def clone_ruleset(self, ruleset_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRuleSet:
        base = self.read_ruleset(ruleset_id)
        payload = payload or {}
        template = str(base.source.get("template") or "baseline")
        clone_payload = {
            **base.to_dict(),
            **payload,
            "name": payload.get("name") or f"{base.name} Copy",
            "status": payload.get("status") or "draft",
            "template": payload.get("template") or template,
            "source": {"created_from": "clone", "source_ruleset_id": base.ruleset_id, "template": payload.get("template") or template},
        }
        clone_payload.pop("ruleset_id", None)
        return self.create_ruleset(clone_payload, now=now)

    def archive_ruleset(self, ruleset_id: str, *, now: str | None = None) -> PlanningRuleSet:
        with self.lock:
            ruleset = self.read_ruleset(ruleset_id)
            updated = PlanningRuleSet.from_dict({**ruleset.to_dict(), "status": "archived", "updated_at": now or now_iso()})
            write_json(self.ruleset_dir(ruleset_id) / "ruleset.json", updated.to_dict())
            _append_event(self.ruleset_dir(ruleset_id) / "events.jsonl", "planning_ruleset_archived", {"ruleset_id": ruleset_id}, now)
            return updated

    def validate_ruleset(self, ruleset_id: str) -> dict[str, Any]:
        ruleset = self.read_ruleset(ruleset_id)
        return {"status": "passed", "ruleset_id": ruleset.ruleset_id, "summary": ruleset_summary(ruleset), "warnings": []}

    def list_simulations(self, *, include_archived: bool = False, status: str | None = None, release_id: str | None = None, project_id: str | None = None) -> list[PlanningRuleSimulationReport]:
        rows: list[PlanningRuleSimulationReport] = []
        if not self.simulations_root().exists():
            return rows
        for path in self.simulations_root().glob("afpsim-*/simulation-report.json"):
            try:
                report = self._with_stale(PlanningRuleSimulationReport.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if report.status == "archived" and not include_archived:
                continue
            if status and report.status != status:
                continue
            if release_id and not _simulation_matches_release(report, release_id):
                continue
            if project_id and not _simulation_matches_project(report, project_id):
                continue
            rows.append(report)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def create_simulation(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRuleSimulationReport:
        payload = payload or {}
        now = now or now_iso()
        ruleset = self.read_ruleset(str(payload.get("ruleset_id") or ""))
        if ruleset.status == "archived":
            raise PlanningRuleSimulationStateError("Archived Planning Rule Set cannot be simulated.")
        reviews = self._select_reviews(payload)
        with self.lock:
            simulation_id, simulation_dir = self._reserve_simulation_dir()
            report = self._build_simulation(simulation_id, ruleset, reviews, payload, created_at=now, now=now)
            write_json(simulation_dir / "simulation-report.json", report.to_dict())
            write_json(simulation_dir / "source-summary.json", {"source": report.source, "summary": report.summary})
            write_json(simulation_dir / "review-results.json", {"simulation_id": report.simulation_id, "review_results": report.review_results})
            _append_event(simulation_dir / "events.jsonl", "planning_rule_simulation_created", {"simulation_id": simulation_id, "ruleset_id": ruleset.ruleset_id, "review_count": len(reviews)}, now)
            return report

    def read_simulation(self, simulation_id: str) -> PlanningRuleSimulationReport:
        path = self.simulation_dir(simulation_id) / "simulation-report.json"
        if not path.exists():
            raise PlanningRuleSimulationNotFoundError(simulation_id)
        return self._with_stale(PlanningRuleSimulationReport.from_dict(read_json(path)))

    def refresh_simulation(self, simulation_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRuleSimulationReport:
        payload = payload or {}
        now = now or now_iso()
        existing = self.read_simulation(simulation_id)
        if existing.status == "archived":
            raise PlanningRuleSimulationStateError("Archived Planning Rule Simulation cannot be refreshed.")
        ruleset = self.read_ruleset(existing.ruleset_id)
        review_ids = _as_list(existing.source.get("review_ids"))
        reviews = [self.review_store.read_review(str(review_id)) for review_id in review_ids]
        for review in reviews:
            if review.status == "archived" or self.review_store.review_is_stale(review):
                raise PlanningRuleSimulationStateError("Planning Rule Simulation source Outcome Review is stale or archived. Refresh the Outcome Review before refreshing the simulation.")
            if review.status not in {"ready", "warning"}:
                raise PlanningRuleSimulationStateError("Planning Rule Simulation source Outcome Review is not ready.")
        refreshed = self._build_simulation(existing.simulation_id, ruleset, reviews, {**existing.source.get("options", {}), **payload, "scope": existing.scope, "review_ids": review_ids}, created_at=existing.created_at, now=now)
        write_json(self.simulation_dir(simulation_id) / "simulation-report.json", refreshed.to_dict())
        write_json(self.simulation_dir(simulation_id) / "source-summary.json", {"source": refreshed.source, "summary": refreshed.summary})
        write_json(self.simulation_dir(simulation_id) / "review-results.json", {"simulation_id": refreshed.simulation_id, "review_results": refreshed.review_results})
        _append_event(self.simulation_dir(simulation_id) / "events.jsonl", "planning_rule_simulation_refreshed", {"simulation_id": simulation_id, "status": refreshed.status}, now)
        return refreshed

    def archive_simulation(self, simulation_id: str, *, now: str | None = None) -> PlanningRuleSimulationReport:
        with self.lock:
            report = self.read_simulation(simulation_id)
            updated = PlanningRuleSimulationReport.from_dict({**report.to_dict(), "status": "archived", "updated_at": now or now_iso()})
            write_json(self.simulation_dir(simulation_id) / "simulation-report.json", updated.to_dict())
            _append_event(self.simulation_dir(simulation_id) / "events.jsonl", "planning_rule_simulation_archived", {"simulation_id": simulation_id}, now)
            return updated

    def simulation_is_stale(self, report: PlanningRuleSimulationReport | dict[str, Any]) -> bool:
        data = report.to_dict() if isinstance(report, PlanningRuleSimulationReport) else _as_document(report)
        if data.get("status") == "archived":
            return False
        try:
            current = self._source_state(data)
        except PlanningRuleSimulationError:
            return True
        stored = _as_document(data.get("source"))
        return stable_hash(current) != stable_hash(_source_core(stored))

    def latest_summary(self, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
        rows = self.list_simulations(include_archived=False, release_id=release_id, project_id=project_id)
        if not rows:
            return {"status": "missing"}
        return planning_simulation_summary(rows[0])

    def _select_reviews(self, payload: ImplementationDocument) -> list[AcceptanceFixPlanReview]:
        scope = _scope(payload.get("scope"), payload)
        review_ids = [str(item) for item in payload.get("review_ids", []) if str(item).strip()] if isinstance(payload.get("review_ids"), list) else []
        if payload.get("review_id"):
            review_ids.append(str(payload.get("review_id")))
        include_warnings = bool(payload.get("include_warning_reviews", True))
        exclude_synthetic = bool(payload.get("exclude_synthetic_only", False))
        explicit = bool(review_ids)
        if explicit:
            rows = [self.review_store.read_review(review_id) for review_id in sorted(set(review_ids))]
        else:
            rows = self.review_store.list_reviews(include_archived=False, release_id=scope.get("release_id"), project_id=scope.get("project_id"))
        selected = []
        for review in rows:
            if review.status == "archived":
                if explicit:
                    raise PlanningRuleSimulationStateError("Explicit Outcome Review is archived.")
                continue
            if self.review_store.review_is_stale(review):
                if explicit:
                    raise PlanningRuleSimulationStateError("Explicit Outcome Review is stale.")
                continue
            if review.status not in {"ready", "warning"}:
                if explicit:
                    raise PlanningRuleSimulationStateError("Explicit Outcome Review is not ready for simulation.")
                continue
            if review.status == "warning" and not include_warnings:
                if explicit:
                    raise PlanningRuleSimulationStateError("Explicit warning Outcome Review requires include_warning_reviews=true.")
                continue
            if exclude_synthetic and bool(review.summary.get("synthetic_only")):
                continue
            if scope.get("release_id") and review.scope.get("release_id") != scope.get("release_id"):
                continue
            if scope.get("project_id") and not _review_matches_project(review, str(scope.get("project_id"))):
                continue
            selected.append(review)
        if not selected:
            raise PlanningRuleSimulationStateError("Planning Rule Simulation requires at least one non-stale Outcome Review.")
        return selected

    def _build_simulation(self, simulation_id: str, ruleset: PlanningRuleSet, reviews: list[AcceptanceFixPlanReview], payload: ImplementationDocument, *, created_at: str, now: str) -> PlanningRuleSimulationReport:
        scope = _scope(payload.get("scope"), payload)
        review_results = [_simulate_review(review, ruleset) for review in reviews]
        effects = _rule_effects(review_results)
        summary = _simulation_summary(review_results, effects)
        warnings = sorted({warning for result in review_results for warning in result.get("warnings", []) if str(warning).strip()})
        if summary.get("recommendation") in {"candidate_mixed", "insufficient_data", "candidate_worse"}:
            warnings.append(str(summary.get("recommendation")))
        status = "blocked" if summary.get("recommendation") == "insufficient_data" else "warning" if warnings or summary.get("recommendation") in {"candidate_mixed", "candidate_worse"} else "ready"
        source = {
            "engine_version": PLANNING_RULE_SIMULATION_ENGINE_VERSION,
            "ruleset_id": ruleset.ruleset_id,
            "ruleset_hash": stable_hash(_ruleset_core(ruleset)),
            "review_ids": [review.review_id for review in reviews],
            "review_hashes": {review.review_id: stable_hash(_review_source_core(review)) for review in reviews},
            "scope": scope,
            "options": _simulation_options(payload),
        }
        source["source_hash"] = stable_hash(_source_core(source))
        return PlanningRuleSimulationReport(
            simulation_id=simulation_id,
            ruleset_id=ruleset.ruleset_id,
            status=status,
            scope=scope,
            source=source,
            summary=summary,
            review_results=review_results,
            rule_effects=effects,
            warnings=sorted(set(warnings)),
            created_at=created_at,
            updated_at=now,
            created_by=_bounded(payload.get("created_by"), 120) or "developer",
        )

    def _with_stale(self, report: PlanningRuleSimulationReport) -> PlanningRuleSimulationReport:
        if report.status == "archived":
            return report
        if not self.simulation_is_stale(report):
            return report
        warnings = sorted(set(report.warnings + ["source_changed"]))
        return PlanningRuleSimulationReport.from_dict({**report.to_dict(), "status": "stale", "summary": {**report.summary, "stale": True}, "warnings": warnings})

    def _source_state(self, report_data: ImplementationDocument) -> ImplementationDocument:
        source = _as_document(report_data.get("source"))
        ruleset = self.read_ruleset(str(report_data.get("ruleset_id") or source.get("ruleset_id") or ""))
        if ruleset.status == "archived":
            raise PlanningRuleSimulationStateError("Planning Rule Set is archived.")
        reviews = []
        for review_id in source.get("review_ids", []) if isinstance(source.get("review_ids"), list) else []:
            review = self.review_store.read_review(str(review_id))
            if review.status == "archived" or self.review_store.review_is_stale(review):
                raise PlanningRuleSimulationStateError("Planning Rule Simulation source Outcome Review is stale or archived.")
            reviews.append(review)
        return _source_core(
            {
                "engine_version": PLANNING_RULE_SIMULATION_ENGINE_VERSION,
                "ruleset_id": ruleset.ruleset_id,
                "ruleset_hash": stable_hash(_ruleset_core(ruleset)),
                "review_ids": [review.review_id for review in reviews],
                "review_hashes": {review.review_id: stable_hash(_review_source_core(review)) for review in reviews},
                "scope": _safe_dict(source.get("scope")),
                "options": _safe_dict(source.get("options")),
            }
        )

    def _reserve_ruleset_dir(self) -> tuple[str, Path]:
        self.rulesets_root().mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            ruleset_id = f"afprs-{index:06d}"
            ruleset_dir = self.ruleset_dir(ruleset_id)
            try:
                ruleset_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return ruleset_id, ruleset_dir

    def _reserve_simulation_dir(self) -> tuple[str, Path]:
        self.simulations_root().mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            simulation_id = f"afpsim-{index:06d}"
            simulation_dir = self.simulation_dir(simulation_id)
            try:
                simulation_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return simulation_id, simulation_dir


def ruleset_summary(ruleset: PlanningRuleSet | dict[str, Any] | None) -> dict[str, Any]:
    data = ruleset.to_dict() if isinstance(ruleset, PlanningRuleSet) else _as_document(ruleset)
    return sanitize_metadata(
        {
            "ruleset_id": data.get("ruleset_id"),
            "name": data.get("name"),
            "status": data.get("status") or "missing",
            "template": (_as_document(data.get("source"))).get("template"),
            "base_rules_version": data.get("base_rules_version"),
            "synthetic_only_penalty": (_as_document(data.get("confidence"))).get("synthetic_only_penalty", 0),
            "waiver_penalty": (_as_document(data.get("penalties"))).get("waiver_heavy_history", 0),
        }
    )


def planning_simulation_summary(report: PlanningRuleSimulationReport | dict[str, Any] | None) -> dict[str, Any]:
    data = report.to_dict() if isinstance(report, PlanningRuleSimulationReport) else _as_document(report)
    summary = _as_document(data.get("summary"))
    source = _as_document(data.get("source"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "simulation_id": data.get("simulation_id"),
            "ruleset_id": data.get("ruleset_id"),
            "scope": _as_document(data.get("scope")),
            "review_count": summary.get("review_count", 0),
            "item_count": summary.get("item_count", 0),
            "baseline_alignment_score": summary.get("baseline_alignment_score"),
            "simulated_alignment_score": summary.get("simulated_alignment_score"),
            "alignment_delta": summary.get("alignment_delta"),
            "recommendation": summary.get("recommendation") or "missing",
            "synthetic_penalty_applied_count": summary.get("synthetic_penalty_applied_count", 0),
            "waiver_penalty_applied_count": summary.get("waiver_penalty_applied_count", 0),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "source_hash": source.get("source_hash"),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
        }
    )


def latest_planning_simulation_summary(store: PlanningRuleSimulationStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    return store.latest_summary(release_id=release_id, project_id=project_id)


def write_planning_simulation_summary(path: Path, store: PlanningRuleSimulationStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    summary = latest_planning_simulation_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary


def _ruleset_from_payload(ruleset_id: str, payload: ImplementationDocument, *, now: str) -> PlanningRuleSet:
    source = _as_document(payload.get("source"))
    template_name = str(payload.get("template") or source.get("template") or "baseline")
    template = RULESET_TEMPLATES.get(template_name)
    if template is None:
        raise PlanningRuleSimulationError(f"Unknown planning ruleset template: {template_name}")
    base = {
        "ruleset_id": ruleset_id,
        "name": template.get("name"),
        "description": template.get("description"),
        "status": "draft",
        "base_rules_version": "acceptance_fix_planning.v1",
        "weights": template.get("weights", {}),
        "penalties": template.get("penalties", {}),
        "confidence": template.get("confidence", {}),
        "bounds": DEFAULT_BOUNDS,
        "source": {"created_from": "builtin", "template": template_name},
        "created_at": now,
        "updated_at": now,
        "created_by": "developer",
    }
    merged = {
        **base,
        **{key: value for key, value in payload.items() if key not in {"ruleset_id", "schema_version"}},
        "weights": {**base["weights"], **_safe_dict(payload.get("weights"))},
        "penalties": {**base["penalties"], **_safe_dict(payload.get("penalties"))},
        "confidence": {**base["confidence"], **_safe_dict(payload.get("confidence"))},
        "bounds": {**base["bounds"], **_safe_dict(payload.get("bounds"))},
        "source": {**base["source"], **_safe_dict(payload.get("source"))},
        "created_at": now,
        "updated_at": now,
    }
    return PlanningRuleSet.from_dict(merged)


def _simulate_review(review: AcceptanceFixPlanReview, ruleset: PlanningRuleSet) -> ImplementationDocument:
    summary = _as_document(review.summary)
    item_results = [_simulate_item(item, ruleset, summary) for item in review.item_outcomes if isinstance(item, dict)]
    baseline_alignment = _alignment_score(item_results, key="baseline_planning_score")
    simulated_alignment = _alignment_score(item_results, key="simulated_planning_score")
    baseline_high = _high_score_unsupported_count(item_results, key="baseline_planning_score", threshold=_int(ruleset.bounds.get("high_score_threshold"), 75))
    simulated_high = _high_score_unsupported_count(item_results, key="simulated_planning_score", threshold=_int(ruleset.bounds.get("high_score_threshold"), 75))
    recommendation = _review_recommendation(baseline_alignment, simulated_alignment, baseline_high, simulated_high, len(item_results))
    warnings = []
    if summary.get("synthetic_only"):
        warnings.append("synthetic_only_recheck")
    if review.status == "warning":
        warnings.append("warning_review")
    return sanitize_metadata(
        {
            "review_id": review.review_id,
            "plan_id": review.plan_id,
            "fix_sprint_id": review.fix_sprint_id,
            "scope": review.scope,
            "baseline": {
                "plan_effectiveness_score": summary.get("plan_effectiveness_score"),
                "ranking_alignment_score": summary.get("ranking_alignment_score"),
                "high_score_unsupported_count": baseline_high,
                "kb_helpfulness": summary.get("kb_evidence_helpfulness"),
            },
            "simulated": {
                "alignment_score": simulated_alignment,
                "score_mean": _mean([item.get("simulated_planning_score") for item in item_results]),
                "high_score_unsupported_count": simulated_high,
                "synthetic_penalty_count": sum(1 for item in item_results if "synthetic_penalty" in item.get("applied_effects", [])),
                "waiver_penalty_count": sum(1 for item in item_results if "waiver_penalty" in item.get("applied_effects", [])),
            },
            "item_results": _rank_items(item_results),
            "recommendation": recommendation,
            "warnings": sorted(set(warnings)),
        }
    )


def _simulate_item(item: ImplementationDocument, ruleset: PlanningRuleSet, review_summary: ImplementationDocument) -> ImplementationDocument:
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


def _rank_items(items: list[ImplementationDocument]) -> list[ImplementationDocument]:
    ranked_ids = {str(item.get("planned_item_id") or ""): index for index, item in enumerate(sorted(items, key=lambda row: (-_int(row.get("simulated_planning_score"), 0), str(row.get("planned_item_id") or ""))), start=1)}
    return [{**item, "rank_after": ranked_ids.get(str(item.get("planned_item_id") or ""), item.get("rank_after"))} for item in items]


def _rule_effects(review_results: list[ImplementationDocument]) -> list[ImplementationDocument]:
    buckets: dict[str, dict[str, Any]] = {}
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


def _simulation_summary(review_results: list[ImplementationDocument], effects: list[ImplementationDocument]) -> ImplementationDocument:
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


def _alignment_score(items: list[ImplementationDocument], *, key: str) -> int | None:
    if not items:
        return None
    ranked = sorted(items, key=lambda item: (-_int(item.get(key), 0), str(item.get("planned_item_id") or "")))
    ideal = sorted(items, key=lambda item: (-_int(item.get("observed_effectiveness_score"), 0), str(item.get("planned_item_id") or "")))
    ideal_rank = {str(item.get("planned_item_id") or ""): index for index, item in enumerate(ideal, start=1)}
    distance = sum(abs(index - ideal_rank.get(str(item.get("planned_item_id") or ""), index)) for index, item in enumerate(ranked, start=1))
    max_distance = max(1, len(items) * (len(items) - 1))
    return max(0, min(100, round(100 - (distance / max_distance * 100))))


def _high_score_unsupported_count(items: list[ImplementationDocument], *, key: str, threshold: int) -> int:
    return sum(1 for item in items if _int(item.get(key), 0) >= threshold and str(item.get("evidence_status") or "") in {"unsupported", "unknown", "not_executed"})


def _low_score_supported_count(items: list[ImplementationDocument]) -> int:
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


def _review_source_core(review: AcceptanceFixPlanReview) -> ImplementationDocument:
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


def _ruleset_core(ruleset: PlanningRuleSet) -> ImplementationDocument:
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


def _source_core(source: ImplementationDocument) -> ImplementationDocument:
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


def _simulation_options(payload: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "include_warning_reviews": bool(payload.get("include_warning_reviews", True)),
            "exclude_synthetic_only": bool(payload.get("exclude_synthetic_only", False)),
        }
    )


def _target_summary(target: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "song_id": _bounded(target.get("song_id"), 120),
            "style": _bounded(target.get("style"), 120),
            "issue_types": [_bounded(item, 80) for item in target.get("issue_types", []) if str(item).strip()] if isinstance(target.get("issue_types"), list) else [],
            "project_id": _bounded(target.get("project_id"), 120),
            "version_id": _bounded(target.get("version_id"), 120),
        }
    )


def _scope(value: Any, payload: ImplementationDocument | None = None) -> ImplementationDocument:
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


def _numeric_map(value: Any, low: int, high: int) -> dict[str, int]:
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


def _bounds(value: Any) -> dict[str, int]:
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


def _append_event(path: Path, event: str, payload: ImplementationDocument, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, "timestamp": now or now_iso(), "payload": sanitize_metadata(payload)}, ensure_ascii=False) + "\n")


def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]


def _safe_dict(value: Any) -> ImplementationDocument:
    return sanitize_metadata(_as_document(value))


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[Any]) -> float | None:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)


def _effect_count(effects: list[ImplementationDocument], effect_id: str) -> int:
    for effect in effects:
        if effect.get("effect_id") == effect_id:
            return _int(effect.get("count"), 0)
    return 0
