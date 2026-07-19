# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.creation.planning_rule_simulation import PlanningRuleSimulationError as PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError as PlanningRuleSimulationNotFoundError, PlanningRuleSimulationStore as PlanningRuleSimulationStore, planning_simulation_summary as planning_simulation_summary, ruleset_summary as ruleset_summary
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text


PLANNING_RULE_GOVERNANCE_ROOT = Path(".musicforge") / "planning-rule-governance"
PLANNING_RULE_VERSION_SCHEMA_VERSION = "planning_rule_version.v1"
PLANNING_RULE_PROMOTION_SCHEMA_VERSION = "planning_rule_promotion.v1"
PLANNING_RULE_ACTIVE_POINTER_SCHEMA_VERSION = "planning_rule_active_pointer.v1"
PLANNING_RULE_GOVERNANCE_SCHEMA_VERSION = "planning_rule_governance.v1"
VERSION_STATUSES = {"active", "superseded", "rolled_back", "archived"}
PROMOTION_STATUSES = {"pending", "approved", "rejected", "promoted", "stale", "archived"}
READY_SIMULATION_STATUSES = {"ready", "warning"}


class PlanningRuleGovernanceError(ValueError):
    pass


class PlanningRuleGovernanceNotFoundError(PlanningRuleGovernanceError):
    pass


class PlanningRuleGovernanceStateError(PlanningRuleGovernanceError):
    pass


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


@dataclass
class PlanningRuleVersion:
    version_id: str
    ruleset_id: str
    ruleset_hash: str
    ruleset_name: str
    status: str
    previous_version_id: str | None
    promoted_from: ImplementationDocument
    approval: ImplementationDocument
    source_hash: str
    created_at: str
    updated_at: str
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": PLANNING_RULE_VERSION_SCHEMA_VERSION,
                "version_id": self.version_id,
                "ruleset_id": self.ruleset_id,
                "ruleset_hash": self.ruleset_hash,
                "ruleset_name": self.ruleset_name,
                "status": self.status,
                "previous_version_id": self.previous_version_id,
                "promoted_from": self.promoted_from,
                "approval": self.approval,
                "source_hash": self.source_hash,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "PlanningRuleVersion":
        now = now_iso()
        status = str(data.get("status") or "active")
        if status not in VERSION_STATUSES:
            status = "superseded"
        return cls(
            version_id=_validate_id(str(data.get("version_id") or "prgv-000001"), "prgv"),
            ruleset_id=_validate_id(str(data.get("ruleset_id") or "afprs-000001"), "afprs"),
            ruleset_hash=_bounded(data.get("ruleset_hash"), 160),
            ruleset_name=_bounded(data.get("ruleset_name"), 160) or "Planning Rule Version",
            status=status,
            previous_version_id=_bounded(data.get("previous_version_id"), 80) or None,
            promoted_from=_safe_dict(data.get("promoted_from")),
            approval=_safe_dict(data.get("approval")),
            source_hash=_bounded(data.get("source_hash"), 160),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


@dataclass
class PlanningRulePromotion:
    promotion_id: str
    ruleset_id: str
    simulation_id: str
    status: str
    scope: ImplementationDocument
    evidence: ImplementationDocument
    risk_assessment: ImplementationDocument
    approval: ImplementationDocument = field(default_factory=dict)
    note: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": PLANNING_RULE_PROMOTION_SCHEMA_VERSION,
                "promotion_id": self.promotion_id,
                "ruleset_id": self.ruleset_id,
                "simulation_id": self.simulation_id,
                "status": self.status,
                "scope": self.scope,
                "evidence": self.evidence,
                "risk_assessment": self.risk_assessment,
                "approval": self.approval,
                "note": sanitize_sensitive_text(self.note),
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "PlanningRulePromotion":
        now = now_iso()
        status = str(data.get("status") or "pending")
        if status not in PROMOTION_STATUSES:
            status = "pending"
        return cls(
            promotion_id=_validate_id(str(data.get("promotion_id") or "prgprom-000001"), "prgprom"),
            ruleset_id=_validate_id(str(data.get("ruleset_id") or "afprs-000001"), "afprs"),
            simulation_id=_validate_id(str(data.get("simulation_id") or "afpsim-000001"), "afpsim"),
            status=status,
            scope=_safe_dict(data.get("scope")),
            evidence=_safe_dict(data.get("evidence")),
            risk_assessment=_safe_dict(data.get("risk_assessment")),
            approval=_safe_dict(data.get("approval")),
            note=_bounded(data.get("note"), 500),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


from song_agent.domains.creation import v142_prg_readiness as _v142_prg_readiness
from song_agent.domains.creation.v142_prg_readiness import PlanningRuleGovernanceStore
from song_agent.domains.creation import v142_prg_evidence as _v142_prg_evidence
from song_agent.domains.creation.v142_prg_evidence import (
    governance_summary,
    promotion_summary,
    active_governance_summary,
    write_planning_rule_governance_summary,
    fix_plan_rule_governance_source,
    _risk_for_recommendation,
    _review_source_core,
    _scope,
    _safe_dict,
    _bounded,
    _validate_id,
    _safe_child,
    _lock_for_root,
    _append_event,
)

_v142_prg_readiness.bind_globals(globals())
_v142_prg_evidence.bind_globals(globals())
