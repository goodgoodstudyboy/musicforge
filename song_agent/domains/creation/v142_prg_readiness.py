# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.creation.planning_rule_simulation import PlanningRuleSimulationError as PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError as PlanningRuleSimulationNotFoundError, PlanningRuleSimulationStore as PlanningRuleSimulationStore, planning_simulation_summary as planning_simulation_summary, ruleset_summary as ruleset_summary
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

PLANNING_RULE_GOVERNANCE_ROOT = _make_deferred_global('PLANNING_RULE_GOVERNANCE_ROOT')
PlanningRuleGovernanceError = _make_deferred_global('PlanningRuleGovernanceError')
PlanningRuleGovernanceNotFoundError = _make_deferred_global('PlanningRuleGovernanceNotFoundError')
PlanningRuleGovernanceStateError = _make_deferred_global('PlanningRuleGovernanceStateError')
PlanningRulePromotion = _make_deferred_global('PlanningRulePromotion')
PlanningRuleVersion = _make_deferred_global('PlanningRuleVersion')
_append_event = _make_deferred_global('_append_event')
_bounded = _make_deferred_global('_bounded')
_lock_for_root = _make_deferred_global('_lock_for_root')
_review_source_core = _make_deferred_global('_review_source_core')
_risk_for_recommendation = _make_deferred_global('_risk_for_recommendation')
_safe_child = _make_deferred_global('_safe_child')
_scope = _make_deferred_global('_scope')
_validate_id = _make_deferred_global('_validate_id')
governance_summary = _make_deferred_global('governance_summary')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global PLANNING_RULE_GOVERNANCE_ROOT, PlanningRuleGovernanceError, PlanningRuleGovernanceNotFoundError, PlanningRuleGovernanceStateError, PlanningRulePromotion, PlanningRuleVersion, _append_event, _bounded
    global _lock_for_root, _review_source_core, _risk_for_recommendation, _safe_child, _scope, _validate_id, governance_summary
    global item
    PLANNING_RULE_GOVERNANCE_ROOT = namespace.get('PLANNING_RULE_GOVERNANCE_ROOT', PLANNING_RULE_GOVERNANCE_ROOT)
    PlanningRuleGovernanceError = namespace.get('PlanningRuleGovernanceError', PlanningRuleGovernanceError)
    PlanningRuleGovernanceNotFoundError = namespace.get('PlanningRuleGovernanceNotFoundError', PlanningRuleGovernanceNotFoundError)
    PlanningRuleGovernanceStateError = namespace.get('PlanningRuleGovernanceStateError', PlanningRuleGovernanceStateError)
    PlanningRulePromotion = namespace.get('PlanningRulePromotion', PlanningRulePromotion)
    PlanningRuleVersion = namespace.get('PlanningRuleVersion', PlanningRuleVersion)
    _append_event = namespace.get('_append_event', _append_event)
    _bounded = namespace.get('_bounded', _bounded)
    _lock_for_root = namespace.get('_lock_for_root', _lock_for_root)
    _review_source_core = namespace.get('_review_source_core', _review_source_core)
    _risk_for_recommendation = namespace.get('_risk_for_recommendation', _risk_for_recommendation)
    _safe_child = namespace.get('_safe_child', _safe_child)
    _scope = namespace.get('_scope', _scope)
    _validate_id = namespace.get('_validate_id', _validate_id)
    governance_summary = namespace.get('governance_summary', governance_summary)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


PLANNING_RULE_VERSION_SCHEMA_VERSION = "planning_rule_version.v1"
PLANNING_RULE_PROMOTION_SCHEMA_VERSION = "planning_rule_promotion.v1"
PLANNING_RULE_ACTIVE_POINTER_SCHEMA_VERSION = "planning_rule_active_pointer.v1"
PLANNING_RULE_GOVERNANCE_SCHEMA_VERSION = "planning_rule_governance.v1"
VERSION_STATUSES = {"active", "superseded", "rolled_back", "archived"}
PROMOTION_STATUSES = {"pending", "approved", "rejected", "promoted", "stale", "archived"}
READY_SIMULATION_STATUSES = {"ready", "warning"}
_LOCKS: dict[str, threading.RLock] = {}




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

    def create_promotion(self, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRulePromotion:
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

    def approve_promotion(self, promotion_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRulePromotion:
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

    def reject_promotion(self, promotion_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> PlanningRulePromotion:
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

    def promote(self, promotion_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def rollback(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def active_pointer(self) -> DomainDocument:
        if not self.active_path().exists():
            return {}
        try:
            return sanitize_metadata(read_json(self.active_path()))
        except Exception:
            return {}

    def active_summary(self) -> DomainDocument:
        version = self.active_version()
        if version is None:
            return {"status": "missing", "governance_status": "legacy_default", "active_version_id": None}
        return governance_summary(version, active=self.active_pointer(), evidence_stale=self.version_evidence_is_stale(version))

    def frozen_ruleset(self, version_id: str) -> DomainDocument:
        path = self.version_dir(version_id) / "ruleset-frozen.json"
        if not path.exists():
            raise PlanningRuleGovernanceNotFoundError(version_id)
        return sanitize_metadata(read_json(path))

    def promotion_is_stale(self, promotion: PlanningRulePromotion | DomainDocument) -> bool:
        data = promotion.to_dict() if isinstance(promotion, PlanningRulePromotion) else _as_document(promotion)
        if data.get("status") in {"rejected", "promoted", "archived"}:
            return False
        try:
            simulation = self.simulation_store.read_simulation(str(data.get("simulation_id") or ""))
            ruleset = self.simulation_store.read_ruleset(str(data.get("ruleset_id") or ""))
        except (PlanningRuleSimulationError, PlanningRuleSimulationNotFoundError):
            return True
        evidence = _as_document(data.get("evidence"))
        return (
            self.simulation_store.simulation_is_stale(simulation)
            or simulation.status not in READY_SIMULATION_STATUSES
            or stable_hash(ruleset.to_dict()) != str(evidence.get("ruleset_hash") or "")
            or str(simulation.source.get("source_hash") or "") != str(evidence.get("simulation_source_hash") or "")
        )

    def version_evidence_is_stale(self, version: PlanningRuleVersion | DomainDocument) -> bool:
        data = version.to_dict() if isinstance(version, PlanningRuleVersion) else _as_document(version)
        promoted_from = _as_document(data.get("promoted_from"))
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
            expected = (_as_document(simulation.source.get("review_hashes"))).get(str(review_id))
            if review.status == "archived" or self.simulation_store.review_store.review_is_stale(review) or stable_hash(_review_source_core(review)) != str(expected or ""):
                return True
        return False

    def frozen_ruleset_integrity_ok(self, version: PlanningRuleVersion | DomainDocument) -> bool:
        data = version.to_dict() if isinstance(version, PlanningRuleVersion) else _as_document(version)
        try:
            frozen = self.frozen_ruleset(str(data.get("version_id") or ""))
        except PlanningRuleGovernanceError:
            return False
        return stable_hash(frozen) == str(data.get("ruleset_hash") or "")

    def version_source_integrity_ok(self, version: PlanningRuleVersion | DomainDocument) -> bool:
        data = version.to_dict() if isinstance(version, PlanningRuleVersion) else _as_document(version)
        try:
            frozen = self.frozen_ruleset(str(data.get("version_id") or ""))
        except PlanningRuleGovernanceError:
            return False
        promoted_from = _as_document(data.get("promoted_from"))
        approval = _as_document(data.get("approval"))
        expected = stable_hash({"ruleset": frozen, "promotion": promoted_from, "approval": approval})
        return expected == str(data.get("source_hash") or "")

    def version_integrity_ok(self, version: PlanningRuleVersion | DomainDocument) -> bool:
        return self.frozen_ruleset_integrity_ok(version) and self.version_source_integrity_ok(version)

    def events(self, *, limit: int = 50) -> list[DomainDocument]:
        path = self.root / "events.jsonl"
        if not path.exists():
            return []
        rows: list[DomainDocument] = []
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

    def _write_active(self, active: DomainDocument) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.active_path(), active)

    def _active_pointer(self, version: PlanningRuleVersion, *, activated_by: str, now: str, event_type: str = "promote") -> DomainDocument:
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
