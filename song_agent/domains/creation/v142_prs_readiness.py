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

PLANNING_RULE_SIMULATION_ROOT = _make_deferred_global('PLANNING_RULE_SIMULATION_ROOT')
PlanningRuleSet = _make_deferred_global('PlanningRuleSet')
PlanningRuleSimulationError = _make_deferred_global('PlanningRuleSimulationError')
PlanningRuleSimulationNotFoundError = _make_deferred_global('PlanningRuleSimulationNotFoundError')
PlanningRuleSimulationReport = _make_deferred_global('PlanningRuleSimulationReport')
PlanningRuleSimulationStateError = _make_deferred_global('PlanningRuleSimulationStateError')
_alignment_score = _make_deferred_global('_alignment_score')
_append_event = _make_deferred_global('_append_event')
_bounded = _make_deferred_global('_bounded')
_high_score_unsupported_count = _make_deferred_global('_high_score_unsupported_count')
_int = _make_deferred_global('_int')
_lock_for_root = _make_deferred_global('_lock_for_root')
_mean = _make_deferred_global('_mean')
_rank_items = _make_deferred_global('_rank_items')
_review_matches_project = _make_deferred_global('_review_matches_project')
_review_recommendation = _make_deferred_global('_review_recommendation')
_review_source_core = _make_deferred_global('_review_source_core')
_rule_effects = _make_deferred_global('_rule_effects')
_ruleset_core = _make_deferred_global('_ruleset_core')
_safe_child = _make_deferred_global('_safe_child')
_safe_dict = _make_deferred_global('_safe_dict')
_scope = _make_deferred_global('_scope')
_simulate_item = _make_deferred_global('_simulate_item')
_simulation_matches_project = _make_deferred_global('_simulation_matches_project')
_simulation_matches_release = _make_deferred_global('_simulation_matches_release')
_simulation_options = _make_deferred_global('_simulation_options')
_simulation_summary = _make_deferred_global('_simulation_summary')
_source_core = _make_deferred_global('_source_core')
_validate_id = _make_deferred_global('_validate_id')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
result = _make_deferred_global('result')
value = _make_deferred_global('value')
warning = _make_deferred_global('warning')

def bind_globals(namespace: dict[str, object]) -> None:
    global PLANNING_RULE_SIMULATION_ROOT, PlanningRuleSet, PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError, PlanningRuleSimulationReport, PlanningRuleSimulationStateError, _alignment_score, _append_event
    global _bounded, _high_score_unsupported_count, _int, _lock_for_root, _mean, _rank_items, _review_matches_project
    global _review_recommendation, _review_source_core, _rule_effects, _ruleset_core, _safe_child, _safe_dict, _scope, _simulate_item
    global _simulation_matches_project, _simulation_matches_release, _simulation_options, _simulation_summary, _source_core, _validate_id, item, key
    global result, value, warning
    PLANNING_RULE_SIMULATION_ROOT = namespace.get('PLANNING_RULE_SIMULATION_ROOT', PLANNING_RULE_SIMULATION_ROOT)
    PlanningRuleSet = namespace.get('PlanningRuleSet', PlanningRuleSet)
    PlanningRuleSimulationError = namespace.get('PlanningRuleSimulationError', PlanningRuleSimulationError)
    PlanningRuleSimulationNotFoundError = namespace.get('PlanningRuleSimulationNotFoundError', PlanningRuleSimulationNotFoundError)
    PlanningRuleSimulationReport = namespace.get('PlanningRuleSimulationReport', PlanningRuleSimulationReport)
    PlanningRuleSimulationStateError = namespace.get('PlanningRuleSimulationStateError', PlanningRuleSimulationStateError)
    _alignment_score = namespace.get('_alignment_score', _alignment_score)
    _append_event = namespace.get('_append_event', _append_event)
    _bounded = namespace.get('_bounded', _bounded)
    _high_score_unsupported_count = namespace.get('_high_score_unsupported_count', _high_score_unsupported_count)
    _int = namespace.get('_int', _int)
    _lock_for_root = namespace.get('_lock_for_root', _lock_for_root)
    _mean = namespace.get('_mean', _mean)
    _rank_items = namespace.get('_rank_items', _rank_items)
    _review_matches_project = namespace.get('_review_matches_project', _review_matches_project)
    _review_recommendation = namespace.get('_review_recommendation', _review_recommendation)
    _review_source_core = namespace.get('_review_source_core', _review_source_core)
    _rule_effects = namespace.get('_rule_effects', _rule_effects)
    _ruleset_core = namespace.get('_ruleset_core', _ruleset_core)
    _safe_child = namespace.get('_safe_child', _safe_child)
    _safe_dict = namespace.get('_safe_dict', _safe_dict)
    _scope = namespace.get('_scope', _scope)
    _simulate_item = namespace.get('_simulate_item', _simulate_item)
    _simulation_matches_project = namespace.get('_simulation_matches_project', _simulation_matches_project)
    _simulation_matches_release = namespace.get('_simulation_matches_release', _simulation_matches_release)
    _simulation_options = namespace.get('_simulation_options', _simulation_options)
    _simulation_summary = namespace.get('_simulation_summary', _simulation_summary)
    _source_core = namespace.get('_source_core', _source_core)
    _validate_id = namespace.get('_validate_id', _validate_id)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    result = namespace.get('result', result)
    value = namespace.get('value', value)
    warning = namespace.get('warning', warning)
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

    def create_ruleset(self, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRuleSet:
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

    def clone_ruleset(self, ruleset_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRuleSet:
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

    def validate_ruleset(self, ruleset_id: str) -> DomainDocument:
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

    def create_simulation(self, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRuleSimulationReport:
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

    def refresh_simulation(self, simulation_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRuleSimulationReport:
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

    def simulation_is_stale(self, report: PlanningRuleSimulationReport | DomainDocument) -> bool:
        data = report.to_dict() if isinstance(report, PlanningRuleSimulationReport) else _as_document(report)
        if data.get("status") == "archived":
            return False
        try:
            current = self._source_state(data)
        except PlanningRuleSimulationError:
            return True
        stored = _as_document(data.get("source"))
        return stable_hash(current) != stable_hash(_source_core(stored))

    def latest_summary(self, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
        rows = self.list_simulations(include_archived=False, release_id=release_id, project_id=project_id)
        if not rows:
            return {"status": "missing"}
        return planning_simulation_summary(rows[0])

    def _select_reviews(self, payload: DomainDocument) -> list[AcceptanceFixPlanReview]:
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

    def _build_simulation(self, simulation_id: str, ruleset: PlanningRuleSet, reviews: list[AcceptanceFixPlanReview], payload: DomainDocument, *, created_at: str, now: str) -> PlanningRuleSimulationReport:
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

    def _source_state(self, report_data: DomainDocument) -> DomainDocument:
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

def ruleset_summary(ruleset: PlanningRuleSet | DomainDocument | None) -> DomainDocument:
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

def planning_simulation_summary(report: PlanningRuleSimulationReport | DomainDocument | None) -> DomainDocument:
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

def latest_planning_simulation_summary(store: PlanningRuleSimulationStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    return store.latest_summary(release_id=release_id, project_id=project_id)

def write_planning_simulation_summary(path: Path, store: PlanningRuleSimulationStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    summary = latest_planning_simulation_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary

def _ruleset_from_payload(ruleset_id: str, payload: DomainDocument, *, now: str) -> PlanningRuleSet:
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

def _simulate_review(review: AcceptanceFixPlanReview, ruleset: PlanningRuleSet) -> DomainDocument:
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
