from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.application.legacy_dependencies.music_acceptance import stable_hash
from song_agent.domains.creation.planning_rule_simulation import PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError, PlanningRuleSimulationStore, planning_simulation_summary, ruleset_summary
from song_agent.domains.studio.projectio import now_iso, read_json, write_json
from song_agent.domains.studio.projects import ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text


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
    promoted_from: dict[str, Any]
    approval: dict[str, Any]
    source_hash: str
    created_at: str
    updated_at: str
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "PlanningRuleVersion":
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
    scope: dict[str, Any]
    evidence: dict[str, Any]
    risk_assessment: dict[str, Any]
    approval: dict[str, Any] = field(default_factory=dict)
    note: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "PlanningRulePromotion":
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


class PlanningRuleGovernanceStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        simulation_store: PlanningRuleSimulationStore | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self.root = Path(root or PLANNING_RULE_GOVERNANCE_ROOT)
        self.project_store = project_store or getattr(simulation_store, "project_store", None) or ProjectStore()
        self.simulation_store = simulation_store or PlanningRuleSimulationStore(project_store=self.project_store)
        self.lock = _lock_for_root(self.root.resolve())

    def promotions_root(self) -> Path:
        return self.root / "promotions"

    def versions_root(self) -> Path:
        return self.root / "versions"

    def active_path(self) -> Path:
        return self.root / "active.json"

    def promotion_dir(self, promotion_id: str) -> Path:
        return _safe_child(self.promotions_root(), _validate_id(promotion_id, "prgprom"), "planning rule promotion")

    def version_dir(self, version_id: str) -> Path:
        return _safe_child(self.versions_root(), _validate_id(version_id, "prgv"), "planning rule version")

    def create_promotion(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRulePromotion:
        payload = payload or {}
        now = now or now_iso()
        ruleset = self.simulation_store.read_ruleset(str(payload.get("ruleset_id") or ""))
        simulation = self.simulation_store.read_simulation(str(payload.get("simulation_id") or ""))
        if simulation.ruleset_id != ruleset.ruleset_id:
            raise PlanningRuleGovernanceStateError("Planning Rule Promotion ruleset must match simulation ruleset.")
        if simulation.status not in READY_SIMULATION_STATUSES or self.simulation_store.simulation_is_stale(simulation):
            raise PlanningRuleGovernanceStateError("Planning Rule Promotion requires a non-stale ready simulation.")
        summary = planning_simulation_summary(simulation)
        recommendation = str(summary.get("recommendation") or "")
        if recommendation == "insufficient_data":
            raise PlanningRuleGovernanceStateError("Planning Rule Promotion requires sufficient simulation data.")
        ruleset_hash = stable_hash(ruleset.to_dict())
        evidence = {
            "simulation_id": simulation.simulation_id,
            "simulation_source_hash": simulation.source.get("source_hash"),
            "ruleset_id": ruleset.ruleset_id,
            "ruleset_hash": ruleset_hash,
            "recommendation": recommendation,
            "review_count": summary.get("review_count", 0),
            "item_count": summary.get("item_count", 0),
            "alignment_delta": summary.get("alignment_delta"),
            "synthetic_penalty_applied_count": summary.get("synthetic_penalty_applied_count", 0),
            "waiver_penalty_applied_count": summary.get("waiver_penalty_applied_count", 0),
            "stale": False,
        }
        risk = _risk_for_recommendation(recommendation, simulation)
        with self.lock:
            promotion_id, promotion_dir = self._reserve_promotion_dir()
            promotion = PlanningRulePromotion(
                promotion_id=promotion_id,
                ruleset_id=ruleset.ruleset_id,
                simulation_id=simulation.simulation_id,
                status="pending",
                scope=_scope(payload.get("scope") or simulation.scope),
                evidence=evidence,
                risk_assessment=risk,
                note=_bounded(payload.get("note"), 500),
                created_at=now,
                updated_at=now,
                created_by=_bounded(payload.get("created_by"), 120) or "developer",
            )
            write_json(promotion_dir / "promotion.json", promotion.to_dict())
            write_json(promotion_dir / "evidence.json", {"promotion_id": promotion_id, "evidence": evidence, "risk_assessment": risk})
            _append_event(promotion_dir / "events.jsonl", "planning_rule_promotion_created", {"promotion_id": promotion_id, "simulation_id": simulation.simulation_id}, now)
            _append_event(self.root / "events.jsonl", "planning_rule_promotion_created", {"promotion_id": promotion_id, "ruleset_id": ruleset.ruleset_id}, now)
            return promotion

    def read_promotion(self, promotion_id: str) -> PlanningRulePromotion:
        path = self.promotion_dir(promotion_id) / "promotion.json"
        if not path.exists():
            raise PlanningRuleGovernanceNotFoundError(promotion_id)
        return self._with_promotion_stale(PlanningRulePromotion.from_dict(read_json(path)))

    def list_promotions(self, *, include_archived: bool = False, status: str | None = None) -> list[PlanningRulePromotion]:
        rows: list[PlanningRulePromotion] = []
        if not self.promotions_root().exists():
            return rows
        for path in self.promotions_root().glob("prgprom-*/promotion.json"):
            try:
                promotion = self._with_promotion_stale(PlanningRulePromotion.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if promotion.status == "archived" and not include_archived:
                continue
            if status and promotion.status != status:
                continue
            rows.append(promotion)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def approve_promotion(self, promotion_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRulePromotion:
        payload = payload or {}
        now = now or now_iso()
        with self.lock:
            promotion = self.read_promotion(promotion_id)
            if self.promotion_is_stale(promotion):
                raise PlanningRuleGovernanceStateError("Planning Rule Promotion is stale. Refresh simulation evidence before approval.")
            if promotion.status != "pending":
                raise PlanningRuleGovernanceStateError("Only pending Planning Rule Promotions can be approved.")
            recommendation = str(promotion.evidence.get("recommendation") or "")
            note = _bounded(payload.get("approval_note") or payload.get("note"), 500)
            if recommendation == "candidate_mixed" and not note:
                raise PlanningRuleGovernanceStateError("approval_note is required for mixed Planning Rule Promotion.")
            if recommendation == "candidate_worse" and (not bool(payload.get("force", False)) or not str(payload.get("override_reason") or "").strip()):
                raise PlanningRuleGovernanceStateError("force=true and override_reason are required for worse Planning Rule Promotion.")
            approval = {
                "approved_by": _bounded(payload.get("approved_by"), 120) or "developer",
                "approved_at": now,
                "approval_note": note,
                "force": bool(payload.get("force", False)),
                "override_reason": _bounded(payload.get("override_reason"), 500),
            }
            updated = PlanningRulePromotion.from_dict({**promotion.to_dict(), "status": "approved", "approval": approval, "updated_at": now})
            self._write_promotion(updated)
            _append_event(self.promotion_dir(promotion_id) / "events.jsonl", "planning_rule_promotion_approved", {"promotion_id": promotion_id}, now)
            _append_event(self.root / "events.jsonl", "planning_rule_promotion_approved", {"promotion_id": promotion_id}, now)
            return updated

    def reject_promotion(self, promotion_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> PlanningRulePromotion:
        payload = payload or {}
        now = now or now_iso()
        reason = _bounded(payload.get("reason"), 500)
        if not reason:
            raise PlanningRuleGovernanceStateError("reason is required to reject a Planning Rule Promotion.")
        with self.lock:
            promotion = self.read_promotion(promotion_id)
            if promotion.status not in {"pending", "approved", "stale"}:
                raise PlanningRuleGovernanceStateError("Planning Rule Promotion cannot be rejected from its current status.")
            rejection = {"rejected_by": _bounded(payload.get("rejected_by"), 120) or "developer", "rejected_at": now, "reason": reason}
            updated = PlanningRulePromotion.from_dict({**promotion.to_dict(), "status": "rejected", "approval": rejection, "updated_at": now})
            self._write_promotion(updated)
            _append_event(self.promotion_dir(promotion_id) / "events.jsonl", "planning_rule_promotion_rejected", {"promotion_id": promotion_id}, now)
            _append_event(self.root / "events.jsonl", "planning_rule_promotion_rejected", {"promotion_id": promotion_id}, now)
            return updated

    def promote(self, promotion_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        now = now or now_iso()
        with self.lock:
            promotion = self.read_promotion(promotion_id)
            if promotion.status != "approved":
                raise PlanningRuleGovernanceStateError("Planning Rule Promotion must be approved before promote.")
            if self.promotion_is_stale(promotion):
                raise PlanningRuleGovernanceStateError("Planning Rule Promotion is stale. Refresh simulation evidence before promote.")
            ruleset = self.simulation_store.read_ruleset(promotion.ruleset_id)
            ruleset_payload = ruleset.to_dict()
            ruleset_hash = stable_hash(ruleset_payload)
            if ruleset_hash != str(promotion.evidence.get("ruleset_hash") or ""):
                raise PlanningRuleGovernanceStateError("Planning Rule Set changed after promotion evidence was created.")
            previous = self.active_version()
            version_id, version_dir = self._reserve_version_dir()
            promoted_from = {
                "promotion_id": promotion.promotion_id,
                "simulation_id": promotion.simulation_id,
                "simulation_source_hash": promotion.evidence.get("simulation_source_hash"),
                "recommendation": promotion.evidence.get("recommendation"),
                "alignment_delta": promotion.evidence.get("alignment_delta"),
                "review_count": promotion.evidence.get("review_count"),
                "item_count": promotion.evidence.get("item_count"),
            }
            approval = promotion.approval
            source_hash = stable_hash({"ruleset": ruleset_payload, "promotion": promoted_from, "approval": approval})
            version = PlanningRuleVersion(
                version_id=version_id,
                ruleset_id=ruleset.ruleset_id,
                ruleset_hash=ruleset_hash,
                ruleset_name=ruleset.name,
                status="active",
                previous_version_id=previous.version_id if previous else None,
                promoted_from=promoted_from,
                approval=approval,
                source_hash=source_hash,
                created_at=now,
                updated_at=now,
                created_by=_bounded(payload.get("promoted_by"), 120) or "developer",
            )
            if previous:
                self._write_version(PlanningRuleVersion.from_dict({**previous.to_dict(), "status": "superseded", "updated_at": now}))
            write_json(version_dir / "version.json", version.to_dict())
            write_json(version_dir / "ruleset-frozen.json", ruleset_payload)
            write_json(version_dir / "promotion-evidence.json", {"promotion": promotion.to_dict(), "evidence": promotion.evidence})
            active = self._active_pointer(version, activated_by=version.created_by, now=now)
            self._write_active(active)
            promoted_promotion = PlanningRulePromotion.from_dict({**promotion.to_dict(), "status": "promoted", "updated_at": now})
            self._write_promotion(promoted_promotion)
            _append_event(version_dir / "events.jsonl", "planning_rule_version_promoted", {"version_id": version_id, "promotion_id": promotion_id}, now)
            _append_event(self.root / "events.jsonl", "planning_rule_version_promoted", {"version_id": version_id, "previous_version_id": version.previous_version_id}, now)
            return {"version": version, "active": active, "promotion": promoted_promotion, "summary": governance_summary(version, active=active, evidence_stale=self.version_evidence_is_stale(version))}

    def rollback(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        now = now or now_iso()
        target_id = str(payload.get("target_version_id") or "").strip()
        reason = _bounded(payload.get("reason"), 500)
        if not reason:
            raise PlanningRuleGovernanceStateError("reason is required for Planning Rule Governance rollback.")
        with self.lock:
            target = self.read_version(target_id)
            if target.status == "archived":
                raise PlanningRuleGovernanceStateError("Archived Planning Rule Version cannot be activated.")
            current = self.active_version()
            if current and current.version_id != target.version_id:
                self._write_version(PlanningRuleVersion.from_dict({**current.to_dict(), "status": "rolled_back", "updated_at": now}))
            active_target = PlanningRuleVersion.from_dict({**target.to_dict(), "status": "active", "updated_at": now})
            self._write_version(active_target)
            active = self._active_pointer(active_target, activated_by=_bounded(payload.get("rolled_back_by"), 120) or "developer", now=now, event_type="rollback")
            self._write_active(active)
            _append_event(self.version_dir(active_target.version_id) / "events.jsonl", "planning_rule_version_rollback_target", {"version_id": active_target.version_id, "reason": reason}, now)
            _append_event(self.root / "events.jsonl", "planning_rule_version_rollback", {"target_version_id": active_target.version_id, "previous_version_id": current.version_id if current else None, "reason": reason}, now)
            return {"version": active_target, "active": active, "summary": governance_summary(active_target, active=active, evidence_stale=self.version_evidence_is_stale(active_target))}

    def read_version(self, version_id: str) -> PlanningRuleVersion:
        path = self.version_dir(version_id) / "version.json"
        if not path.exists():
            raise PlanningRuleGovernanceNotFoundError(version_id)
        return PlanningRuleVersion.from_dict(read_json(path))

    def list_versions(self, *, include_archived: bool = False, status: str | None = None) -> list[PlanningRuleVersion]:
        rows: list[PlanningRuleVersion] = []
        if not self.versions_root().exists():
            return rows
        for path in self.versions_root().glob("prgv-*/version.json"):
            try:
                version = PlanningRuleVersion.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if version.status == "archived" and not include_archived:
                continue
            if status and version.status != status:
                continue
            rows.append(version)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def active_version(self) -> PlanningRuleVersion | None:
        pointer = self.active_pointer()
        version_id = str(pointer.get("active_version_id") or "").strip()
        if not version_id:
            return None
        try:
            return self.read_version(version_id)
        except PlanningRuleGovernanceNotFoundError:
            return None

    def active_pointer(self) -> dict[str, Any]:
        if not self.active_path().exists():
            return {}
        try:
            return sanitize_metadata(read_json(self.active_path()))
        except Exception:
            return {}

    def active_summary(self) -> dict[str, Any]:
        version = self.active_version()
        if version is None:
            return {"status": "missing", "governance_status": "legacy_default", "active_version_id": None}
        return governance_summary(version, active=self.active_pointer(), evidence_stale=self.version_evidence_is_stale(version))

    def frozen_ruleset(self, version_id: str) -> dict[str, Any]:
        path = self.version_dir(version_id) / "ruleset-frozen.json"
        if not path.exists():
            raise PlanningRuleGovernanceNotFoundError(version_id)
        return sanitize_metadata(read_json(path))

    def promotion_is_stale(self, promotion: PlanningRulePromotion | dict[str, Any]) -> bool:
        data = promotion.to_dict() if isinstance(promotion, PlanningRulePromotion) else promotion if isinstance(promotion, dict) else {}
        if data.get("status") in {"rejected", "promoted", "archived"}:
            return False
        try:
            simulation = self.simulation_store.read_simulation(str(data.get("simulation_id") or ""))
            ruleset = self.simulation_store.read_ruleset(str(data.get("ruleset_id") or ""))
        except (PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError):
            return True
        evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
        return (
            self.simulation_store.simulation_is_stale(simulation)
            or simulation.status not in READY_SIMULATION_STATUSES
            or stable_hash(ruleset.to_dict()) != str(evidence.get("ruleset_hash") or "")
            or str(simulation.source.get("source_hash") or "") != str(evidence.get("simulation_source_hash") or "")
        )

    def version_evidence_is_stale(self, version: PlanningRuleVersion | dict[str, Any]) -> bool:
        data = version.to_dict() if isinstance(version, PlanningRuleVersion) else version if isinstance(version, dict) else {}
        promoted_from = data.get("promoted_from") if isinstance(data.get("promoted_from"), dict) else {}
        simulation_id = str(promoted_from.get("simulation_id") or "").strip()
        if not simulation_id:
            return True
        try:
            simulation = self.simulation_store.read_simulation(simulation_id)
        except PlanningRuleSimulationError:
            return True
        if str(simulation.source.get("source_hash") or "") != str(promoted_from.get("simulation_source_hash") or ""):
            return True
        for review_id in simulation.source.get("review_ids", []) if isinstance(simulation.source.get("review_ids"), list) else []:
            try:
                review = self.simulation_store.review_store.read_review(str(review_id))
            except Exception:
                return True
            expected = (simulation.source.get("review_hashes") if isinstance(simulation.source.get("review_hashes"), dict) else {}).get(str(review_id))
            if review.status == "archived" or self.simulation_store.review_store.review_is_stale(review) or stable_hash(_review_source_core(review)) != str(expected or ""):
                return True
        return False

    def frozen_ruleset_integrity_ok(self, version: PlanningRuleVersion | dict[str, Any]) -> bool:
        data = version.to_dict() if isinstance(version, PlanningRuleVersion) else version if isinstance(version, dict) else {}
        try:
            frozen = self.frozen_ruleset(str(data.get("version_id") or ""))
        except PlanningRuleGovernanceError:
            return False
        return stable_hash(frozen) == str(data.get("ruleset_hash") or "")

    def version_source_integrity_ok(self, version: PlanningRuleVersion | dict[str, Any]) -> bool:
        data = version.to_dict() if isinstance(version, PlanningRuleVersion) else version if isinstance(version, dict) else {}
        try:
            frozen = self.frozen_ruleset(str(data.get("version_id") or ""))
        except PlanningRuleGovernanceError:
            return False
        promoted_from = data.get("promoted_from") if isinstance(data.get("promoted_from"), dict) else {}
        approval = data.get("approval") if isinstance(data.get("approval"), dict) else {}
        expected = stable_hash({"ruleset": frozen, "promotion": promoted_from, "approval": approval})
        return expected == str(data.get("source_hash") or "")

    def version_integrity_ok(self, version: PlanningRuleVersion | dict[str, Any]) -> bool:
        return self.frozen_ruleset_integrity_ok(version) and self.version_source_integrity_ok(version)

    def events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        path = self.root / "events.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(sanitize_metadata(json.loads(line)))
            except json.JSONDecodeError:
                continue
        return rows[-max(1, min(500, limit)) :]

    def _with_promotion_stale(self, promotion: PlanningRulePromotion) -> PlanningRulePromotion:
        if promotion.status in {"rejected", "promoted", "archived"}:
            return promotion
        if not self.promotion_is_stale(promotion):
            return promotion
        return PlanningRulePromotion.from_dict({**promotion.to_dict(), "status": "stale", "evidence": {**promotion.evidence, "stale": True}, "updated_at": promotion.updated_at})

    def _write_promotion(self, promotion: PlanningRulePromotion) -> None:
        write_json(self.promotion_dir(promotion.promotion_id) / "promotion.json", promotion.to_dict())
        write_json(self.promotion_dir(promotion.promotion_id) / "evidence.json", {"promotion_id": promotion.promotion_id, "evidence": promotion.evidence, "risk_assessment": promotion.risk_assessment})

    def _write_version(self, version: PlanningRuleVersion) -> None:
        write_json(self.version_dir(version.version_id) / "version.json", version.to_dict())

    def _write_active(self, active: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.active_path(), active)

    def _active_pointer(self, version: PlanningRuleVersion, *, activated_by: str, now: str, event_type: str = "promote") -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": PLANNING_RULE_ACTIVE_POINTER_SCHEMA_VERSION,
                "active_version_id": version.version_id,
                "ruleset_id": version.ruleset_id,
                "ruleset_hash": version.ruleset_hash,
                "activated_at": now,
                "activated_by": activated_by,
                "activation_event_id": f"{event_type}:{version.version_id}:{now}",
            }
        )

    def _reserve_promotion_dir(self) -> tuple[str, Path]:
        self.promotions_root().mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            promotion_id = f"prgprom-{index:06d}"
            promotion_dir = self.promotion_dir(promotion_id)
            try:
                promotion_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return promotion_id, promotion_dir

    def _reserve_version_dir(self) -> tuple[str, Path]:
        self.versions_root().mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            version_id = f"prgv-{index:06d}"
            version_dir = self.version_dir(version_id)
            try:
                version_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return version_id, version_dir


def governance_summary(version: PlanningRuleVersion | dict[str, Any] | None, *, active: dict[str, Any] | None = None, evidence_stale: bool = False) -> dict[str, Any]:
    data = version.to_dict() if isinstance(version, PlanningRuleVersion) else version if isinstance(version, dict) else {}
    if not data:
        return {"status": "missing", "governance_status": "legacy_default", "active_version_id": None}
    promoted = data.get("promoted_from") if isinstance(data.get("promoted_from"), dict) else {}
    active = active if isinstance(active, dict) else {}
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


def promotion_summary(promotion: PlanningRulePromotion | dict[str, Any] | None) -> dict[str, Any]:
    data = promotion.to_dict() if isinstance(promotion, PlanningRulePromotion) else promotion if isinstance(promotion, dict) else {}
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    risk = data.get("risk_assessment") if isinstance(data.get("risk_assessment"), dict) else {}
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


def active_governance_summary(store: PlanningRuleGovernanceStore) -> dict[str, Any]:
    return store.active_summary()


def write_planning_rule_governance_summary(path: Path, store: PlanningRuleGovernanceStore) -> dict[str, Any]:
    summary = active_governance_summary(store)
    write_json(path, summary)
    return summary


def fix_plan_rule_governance_source(store: PlanningRuleGovernanceStore | None = None) -> dict[str, Any]:
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


def _risk_for_recommendation(recommendation: str, simulation: Any) -> dict[str, Any]:
    warnings = []
    summary = simulation.summary if isinstance(getattr(simulation, "summary", None), dict) else {}
    if int(summary.get("synthetic_penalty_applied_count") or 0) > 0:
        warnings.append("synthetic_only_reviews_present")
    if recommendation == "candidate_worse":
        return {"status": "blocked", "warnings": sorted(set(warnings + ["candidate_worse"])), "requires_force": True}
    if recommendation == "candidate_mixed":
        return {"status": "warning", "warnings": sorted(set(warnings + ["candidate_mixed"])), "requires_force": False}
    return {"status": "passed" if not warnings else "warning", "warnings": sorted(set(warnings)), "requires_force": False}


def _review_source_core(review: Any) -> dict[str, Any]:
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


def _scope(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    scope_type = str(raw.get("type") or ("release" if raw.get("release_id") else "project" if raw.get("project_id") else "global"))
    if scope_type not in {"global", "release", "project"}:
        scope_type = "global"
    return sanitize_metadata({"type": scope_type, "release_id": _bounded(raw.get("release_id"), 120), "project_id": _bounded(raw.get("project_id"), 120)})


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _bounded(value: Any, limit: int) -> str:
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


def _append_event(path: Path, event: str, payload: dict[str, Any], now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"event": event, "created_at": now or now_iso(), **payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
