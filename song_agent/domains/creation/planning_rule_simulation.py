# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

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
BASELINE_RULESET: ImplementationDocument = {
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

RULESET_TEMPLATES: dict[str, ImplementationDocument] = {
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
    weights: ImplementationDocument
    penalties: ImplementationDocument
    confidence: ImplementationDocument
    bounds: ImplementationDocument
    source: ImplementationDocument
    created_at: str
    updated_at: str
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "PlanningRuleSet":
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
    scope: ImplementationDocument
    source: ImplementationDocument
    summary: ImplementationDocument
    review_results: list[ImplementationDocument]
    rule_effects: list[ImplementationDocument]
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "PlanningRuleSimulationReport":
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


from song_agent.domains.creation import v142_prs_readiness as _v142_prs_readiness
from song_agent.domains.creation.v142_prs_readiness import PlanningRuleSimulationStore as PlanningRuleSimulationStore, ruleset_summary as ruleset_summary, planning_simulation_summary as planning_simulation_summary, latest_planning_simulation_summary as latest_planning_simulation_summary, write_planning_simulation_summary as write_planning_simulation_summary, _ruleset_from_payload as _ruleset_from_payload, _simulate_review as _simulate_review
from song_agent.domains.creation import v142_prs_evidence as _v142_prs_evidence
from song_agent.domains.creation.v142_prs_evidence import _simulate_item as _simulate_item, _rank_items as _rank_items, _rule_effects as _rule_effects, _simulation_summary as _simulation_summary, _alignment_score as _alignment_score, _high_score_unsupported_count as _high_score_unsupported_count, _low_score_supported_count as _low_score_supported_count, _review_recommendation as _review_recommendation, _simulation_recommendation as _simulation_recommendation, _review_source_core as _review_source_core, _ruleset_core as _ruleset_core, _source_core as _source_core, _simulation_options as _simulation_options, _target_summary as _target_summary, _scope as _scope, _review_matches_project as _review_matches_project, _simulation_matches_release as _simulation_matches_release, _simulation_matches_project as _simulation_matches_project, _numeric_map as _numeric_map, _bounds as _bounds, _safe_child as _safe_child, _validate_id as _validate_id, _append_event as _append_event, _lock_for_root as _lock_for_root, _safe_dict as _safe_dict, _bounded as _bounded, _int as _int, _mean as _mean, _effect_count as _effect_count

_v142_prs_readiness.bind_globals(globals())
_v142_prs_evidence.bind_globals(globals())
