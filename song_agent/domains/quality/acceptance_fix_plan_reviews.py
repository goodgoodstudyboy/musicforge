# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlan as AcceptanceFixPlan, AcceptanceFixPlanningStore as AcceptanceFixPlanningStore, fix_plan_summary as fix_plan_summary
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixItem as AcceptanceFixItem, AcceptanceFixSprint as AcceptanceFixSprint, AcceptanceFixSprintStore as AcceptanceFixSprintStore, acceptance_fix_closeout_summary as acceptance_fix_closeout_summary, fix_sprint_summary as fix_sprint_summary
from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseStore as AcceptanceKnowledgeBaseStore, knowledge_entry_summary as knowledge_entry_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import ReviewTaskStore as ReviewTaskStore


ACCEPTANCE_FIX_PLAN_REVIEW_ROOT = Path(".musicforge") / "fix-plan-reviews"
ACCEPTANCE_FIX_PLAN_REVIEW_SCHEMA_VERSION = "acceptance_fix_plan_review.v1"
ACCEPTANCE_FIX_PLAN_REVIEW_RULES_VERSION = "acceptance_fix_plan_review_rules.v1"
REVIEW_STATUSES = {"ready", "warning", "blocked", "stale", "archived"}
REVIEW_READY_STATUSES = {"ready", "warning"}
REVIEW_BLOCKED_MESSAGE = "Acceptance Fix Plan Outcome Review requires a used plan with a closed Fix Sprint, delta report, and closeout report."


class AcceptanceFixPlanReviewError(ValueError):
    pass


class AcceptanceFixPlanReviewNotFoundError(AcceptanceFixPlanReviewError):
    pass


class AcceptanceFixPlanReviewStateError(AcceptanceFixPlanReviewError):
    pass


@dataclass
class AcceptanceFixPlanReview:
    review_id: str
    plan_id: str
    fix_sprint_id: str
    status: str
    readiness: str
    scope: ImplementationDocument
    source: ImplementationDocument
    summary: ImplementationDocument
    item_outcomes: list[ImplementationDocument]
    calibration_hints: list[ImplementationDocument]
    warnings: list[str]
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": ACCEPTANCE_FIX_PLAN_REVIEW_SCHEMA_VERSION,
                "review_id": self.review_id,
                "plan_id": self.plan_id,
                "fix_sprint_id": self.fix_sprint_id,
                "status": self.status,
                "readiness": self.readiness,
                "scope": self.scope,
                "source": self.source,
                "summary": self.summary,
                "item_outcomes": self.item_outcomes,
                "calibration_hints": self.calibration_hints,
                "warnings": self.warnings,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "AcceptanceFixPlanReview":
        now = now_iso()
        status = str(data.get("status") or "ready")
        if status not in REVIEW_STATUSES:
            status = "ready"
        readiness = str(data.get("readiness") or status)
        if readiness not in REVIEW_STATUSES:
            readiness = status
        return cls(
            review_id=_validate_id(str(data.get("review_id") or "afpr-000001"), "afpr"),
            plan_id=_validate_id(str(data.get("plan_id") or "afp-000001"), "afp"),
            fix_sprint_id=_validate_id(str(data.get("fix_sprint_id") or "afs-000001"), "afs"),
            status=status,
            readiness=readiness,
            scope=_safe_dict(data.get("scope")),
            source=_safe_dict(data.get("source")),
            summary=_safe_dict(data.get("summary")),
            item_outcomes=[_safe_dict(item) for item in data.get("item_outcomes", []) if isinstance(item, dict)] if isinstance(data.get("item_outcomes"), list) else [],
            calibration_hints=[_safe_dict(item) for item in data.get("calibration_hints", []) if isinstance(item, dict)] if isinstance(data.get("calibration_hints"), list) else [],
            warnings=[_bounded(item, 180) for item in data.get("warnings", []) if str(item).strip()] if isinstance(data.get("warnings"), list) else [],
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


class AcceptanceFixPlanReviewStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        plan_store: AcceptanceFixPlanningStore | None = None,
        fix_sprint_store: AcceptanceFixSprintStore | None = None,
        kb_store: AcceptanceKnowledgeBaseStore | None = None,
        project_store: ProjectStore | None = None,
    ):
        self.root = Path(root or ACCEPTANCE_FIX_PLAN_REVIEW_ROOT)
        self.project_store = project_store or getattr(plan_store, "project_store", None) or getattr(fix_sprint_store, "project_store", None) or ProjectStore()
        self.fix_sprint_store = fix_sprint_store or getattr(plan_store, "fix_sprint_store", None) or AcceptanceFixSprintStore(project_store=self.project_store)
        self.kb_store = kb_store or getattr(plan_store, "kb_store", None) or AcceptanceKnowledgeBaseStore(fix_sprint_store=self.fix_sprint_store, project_store=self.project_store)
        self.plan_store = plan_store or AcceptanceFixPlanningStore(kb_store=self.kb_store, fix_sprint_store=self.fix_sprint_store, project_store=self.project_store)
        self.lock = _lock_for_root(self.root.resolve())

    def review_dir(self, review_id: str) -> Path:
        base = self.root.resolve()
        target = (base / _validate_id(review_id, "afpr")).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise AcceptanceFixPlanReviewError("Refusing to operate outside acceptance fix plan review store.") from exc
        return target

    def latest_path(self) -> Path:
        return self.root / "latest.json"

    def list_reviews(self, *, include_archived: bool = False, status: str | None = None, release_id: str | None = None, project_id: str | None = None) -> list[AcceptanceFixPlanReview]:
        rows: list[AcceptanceFixPlanReview] = []
        if not self.root.exists():
            return rows
        for path in self.root.glob("afpr-*/outcome-review.json"):
            try:
                review = self._with_stale(AcceptanceFixPlanReview.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if review.status == "archived" and not include_archived:
                continue
            if status and review.status != status:
                continue
            if release_id and review.scope.get("release_id") != release_id:
                continue
            if project_id and not _review_matches_project(review, project_id):
                continue
            rows.append(review)
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_review(self, review_id: str) -> AcceptanceFixPlanReview:
        path = self.review_dir(review_id) / "outcome-review.json"
        if not path.exists():
            raise AcceptanceFixPlanReviewNotFoundError(review_id)
        return self._with_stale(AcceptanceFixPlanReview.from_dict(read_json(path)))

    def latest_for_plan(self, plan_id: str) -> AcceptanceFixPlanReview | None:
        for review in self.list_reviews(include_archived=False):
            if review.plan_id == plan_id:
                return review
        return None

    def latest_summary(self, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
        rows = self.list_reviews(include_archived=False, release_id=release_id, project_id=project_id)
        if not rows:
            return {"status": "missing"}
        return fix_plan_review_summary(rows[0])

    def get_or_missing_for_plan(self, plan_id: str) -> DomainDocument:
        review = self.latest_for_plan(plan_id)
        if review is None:
            return {"status": "missing", "plan_id": plan_id, "stale": False}
        return review.to_dict()

    def refresh_for_plan(self, plan_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> AcceptanceFixPlanReview:
        payload = payload or {}
        now = now or now_iso()
        with self.lock:
            latest = self.latest_for_plan(plan_id)
            if latest and latest.status != "archived":
                review_id = latest.review_id
                review_dir = self.review_dir(review_id)
                created_at = latest.created_at
            else:
                review_id, review_dir = self._reserve_review_dir()
                created_at = now
            review = self._build_review(review_id, plan_id, payload, created_at=created_at, now=now)
            write_json(review_dir / "outcome-review.json", review.to_dict())
            write_json(review_dir / "item-outcomes.json", {"review_id": review.review_id, "items": review.item_outcomes})
            write_json(review_dir / "source-summary.json", {"source": review.source, "summary": review.summary})
            _append_event(review_dir / "events.jsonl", "acceptance_fix_plan_outcome_review_refreshed", {"review_id": review.review_id, "plan_id": plan_id, "status": review.status}, now)
            self.latest_path().parent.mkdir(parents=True, exist_ok=True)
            write_json(self.latest_path(), review.to_dict())
            return review

    def refresh_review(self, review_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> AcceptanceFixPlanReview:
        review = self.read_review(review_id)
        return self.refresh_for_plan(review.plan_id, payload or {}, now=now)

    def archive_review(self, review_id: str, *, now: str | None = None) -> AcceptanceFixPlanReview:
        with self.lock:
            review = self.read_review(review_id)
            updated = AcceptanceFixPlanReview.from_dict({**review.to_dict(), "status": "archived", "readiness": "archived", "updated_at": now or now_iso()})
            write_json(self.review_dir(review_id) / "outcome-review.json", updated.to_dict())
            _append_event(self.review_dir(review_id) / "events.jsonl", "acceptance_fix_plan_outcome_review_archived", {"review_id": review_id}, now)
            return updated

    def review_is_stale(self, review: AcceptanceFixPlanReview | DomainDocument) -> bool:
        data = review.to_dict() if isinstance(review, AcceptanceFixPlanReview) else _as_document(review)
        try:
            current = self._source_state(str(data.get("plan_id") or ""))
        except AcceptanceFixPlanReviewError:
            return True
        stored = _as_document(data.get("source"))
        keys = ("plan_hash", "plan_source_hash", "fix_sprint_hash", "fix_items_hash", "delta_hash", "closeout_hash", "source_hash")
        return any(str(current.get(key) or "") != str(stored.get(key) or "") for key in keys) or current.get("kb_entry_hashes") != stored.get("kb_entry_hashes")

    def _build_review(self, review_id: str, plan_id: str, payload: ImplementationDocument, *, created_at: str, now: str) -> AcceptanceFixPlanReview:
        plan = self.plan_store.read_plan(plan_id)
        state = self._source_state(plan.plan_id, plan=plan)
        sprint = state["sprint"]
        items = state["items"]
        delta = state["delta"]
        closeout = state["closeout"]
        if plan.status != "used" or not plan.execution.get("created_fix_sprint_id") or sprint.status != "closed" or not delta or not closeout:
            raise AcceptanceFixPlanReviewStateError(REVIEW_BLOCKED_MESSAGE)
        item_outcomes = _item_outcomes(plan, sprint, items, delta, closeout, state["kb_summaries"], project_store=self.project_store)
        summary = _review_summary(plan, sprint, items, delta, closeout, item_outcomes)
        warnings = list(summary.pop("warnings", []))
        calibration_hints = _calibration_hints(plan, item_outcomes, summary)
        status = "warning" if warnings or any(item.get("warnings") for item in item_outcomes) or closeout.get("forced") else "ready"
        if summary.get("plan_effectiveness_score", 0) <= 20:
            status = "blocked"
        return AcceptanceFixPlanReview(
            review_id=review_id,
            plan_id=plan.plan_id,
            fix_sprint_id=sprint.fix_sprint_id,
            status=status,
            readiness=status,
            scope=plan.scope,
            source={
                "rules_version": ACCEPTANCE_FIX_PLAN_REVIEW_RULES_VERSION,
                "plan_id": plan.plan_id,
                "plan_hash": state["plan_hash"],
                "plan_source_hash": state["plan_source_hash"],
                "fix_sprint_id": sprint.fix_sprint_id,
                "fix_sprint_hash": state["fix_sprint_hash"],
                "fix_items_hash": state["fix_items_hash"],
                "delta_hash": state["delta_hash"],
                "closeout_hash": state["closeout_hash"],
                "kb_entry_hashes": state["kb_entry_hashes"],
                "source_hash": state["source_hash"],
            },
            summary=summary,
            item_outcomes=item_outcomes,
            calibration_hints=calibration_hints,
            warnings=warnings,
            created_at=created_at,
            updated_at=now,
            created_by=_bounded(payload.get("created_by"), 120) or "developer",
        )

    def _source_state(self, plan_id: str, *, plan: AcceptanceFixPlan | None = None) -> ImplementationDocument:
        plan = plan or self.plan_store.read_plan(plan_id)
        if self.plan_store.plan_is_stale(plan):
            raise AcceptanceFixPlanReviewStateError("Acceptance Fix Plan is stale. Refresh the plan before reviewing outcomes.")
        fix_sprint_id = str(plan.execution.get("created_fix_sprint_id") or "")
        if not fix_sprint_id:
            raise AcceptanceFixPlanReviewStateError(REVIEW_BLOCKED_MESSAGE)
        sprint = self.fix_sprint_store.read_sprint(fix_sprint_id)
        if sprint.source.get("source_type") != "acceptance_fix_plan" or str(sprint.source.get("fix_plan_id") or "") != plan.plan_id:
            raise AcceptanceFixPlanReviewStateError("Acceptance Fix Sprint is not linked to this Fix Plan.")
        if str(sprint.source.get("fix_plan_source_hash") or "") != str(plan.source.get("source_hash") or ""):
            raise AcceptanceFixPlanReviewStateError("Acceptance Fix Sprint source no longer matches this Fix Plan.")
        items = self.fix_sprint_store.read_items(fix_sprint_id)
        delta = self.fix_sprint_store.read_delta(fix_sprint_id, default={})
        closeout = self.fix_sprint_store.read_closeout(fix_sprint_id, default={})
        kb_summaries = self._kb_summaries(plan, items)
        source_payload = {
            "rules_version": ACCEPTANCE_FIX_PLAN_REVIEW_RULES_VERSION,
            "plan": _plan_source(plan),
            "fix_sprint": _sprint_source(sprint),
            "items": [_item_source(item) for item in items],
            "delta": _delta_source(delta),
            "closeout": _closeout_source(closeout),
            "kb_entry_hashes": {entry_id: stable_hash(summary) for entry_id, summary in kb_summaries.items()},
        }
        return {
            "plan": plan,
            "sprint": sprint,
            "items": items,
            "delta": delta,
            "closeout": closeout,
            "kb_summaries": kb_summaries,
            "plan_hash": stable_hash(_plan_source(plan)),
            "plan_source_hash": plan.source.get("source_hash"),
            "fix_sprint_hash": stable_hash(_sprint_source(sprint)),
            "fix_items_hash": stable_hash([_item_source(item) for item in items]),
            "delta_hash": stable_hash(_delta_source(delta)),
            "closeout_hash": stable_hash(_closeout_source(closeout)),
            "kb_entry_hashes": source_payload["kb_entry_hashes"],
            "source_hash": stable_hash(source_payload),
        }

    def _kb_summaries(self, plan: AcceptanceFixPlan, items: list[AcceptanceFixItem]) -> dict[str, ImplementationDocument]:
        ids: set[str] = set()
        for planned_item in plan.planned_items:
            knowledge = _as_document(planned_item.get("knowledge"))
            ids.update(str(value) for value in knowledge.get("top_entry_ids", []) if str(value).strip())
            source = _as_document(planned_item.get("source"))
            ids.update(str(value) for value in source.get("kb_entry_ids", []) if str(value).strip())
        for fix_item in items:
            source = _as_document(fix_item.source)
            ids.update(str(value) for value in source.get("kb_entry_ids", []) if str(value).strip())
            planning = fix_item.evidence.get("planning") if isinstance(fix_item.evidence, dict) and isinstance(fix_item.evidence.get("planning"), dict) else {}
            knowledge = _as_document(_as_document(planning).get("knowledge"))
            ids.update(str(value) for value in knowledge.get("top_entry_ids", []) if str(value).strip())
        summaries: dict[str, ImplementationDocument] = {}
        for entry_id in sorted(ids):
            try:
                summaries[entry_id] = knowledge_entry_summary(self.kb_store.read_entry(entry_id))
            except Exception:
                summaries[entry_id] = {"entry_id": entry_id, "status": "missing"}
        return summaries

    def _with_stale(self, review: AcceptanceFixPlanReview) -> AcceptanceFixPlanReview:
        if review.status == "archived":
            return review
        if not self.review_is_stale(review):
            return review
        return AcceptanceFixPlanReview.from_dict({**review.to_dict(), "status": "stale", "readiness": "stale", "summary": {**review.summary, "stale": True}, "warnings": sorted(set(review.warnings + ["source_changed"]))})

    def _reserve_review_dir(self) -> tuple[str, Path]:
        index = 1
        while True:
            review_id = f"afpr-{index:06d}"
            review_dir = self.review_dir(review_id)
            try:
                review_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                index += 1
                continue
            return review_id, review_dir


def fix_plan_review_summary(review: AcceptanceFixPlanReview | DomainDocument | None) -> DomainDocument:
    data = review.to_dict() if isinstance(review, AcceptanceFixPlanReview) else _as_document(review)
    summary = _as_document(data.get("summary"))
    source = _as_document(data.get("source"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness") or data.get("status") or "missing",
            "review_id": data.get("review_id"),
            "plan_id": data.get("plan_id"),
            "fix_sprint_id": data.get("fix_sprint_id"),
            "scope": _as_document(data.get("scope")),
            "planned_item_count": summary.get("planned_item_count", 0),
            "executed_item_count": summary.get("executed_item_count", 0),
            "resolved_item_count": summary.get("resolved_item_count", 0),
            "waived_item_count": summary.get("waived_item_count", 0),
            "open_item_count": summary.get("open_item_count", 0),
            "plan_effectiveness_score": summary.get("plan_effectiveness_score"),
            "ranking_alignment_score": summary.get("ranking_alignment_score"),
            "kb_evidence_helpfulness": summary.get("kb_evidence_helpfulness"),
            "supported_item_count": summary.get("supported_item_count", 0),
            "unsupported_item_count": summary.get("unsupported_item_count", 0),
            "unknown_item_count": summary.get("unknown_item_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "manual_recheck_confirmed": summary.get("manual_recheck_confirmed", False),
            "synthetic_only": summary.get("synthetic_only", False),
            "manual_accepted_count": summary.get("manual_accepted_count", 0),
            "synthetic_accepted_count": summary.get("synthetic_accepted_count", 0),
            "manual_review_count": summary.get("manual_review_count", 0),
            "synthetic_review_count": summary.get("synthetic_review_count", 0),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "source_hash": source.get("source_hash"),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
        }
    )


def latest_fix_plan_review_summary(store: AcceptanceFixPlanReviewStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    return store.latest_summary(release_id=release_id, project_id=project_id)


def write_acceptance_fix_plan_review_summary(path: Path, store: AcceptanceFixPlanReviewStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    summary = latest_fix_plan_review_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary


def _item_outcomes(plan: AcceptanceFixPlan, sprint: AcceptanceFixSprint, items: list[AcceptanceFixItem], delta: ImplementationDocument, closeout: ImplementationDocument, kb_summaries: dict[str, ImplementationDocument], *, project_store: ProjectStore) -> list[ImplementationDocument]:
    planned_by_id = {str(item.get("planned_item_id") or ""): item for item in plan.planned_items}
    items_by_planned = {str(item.source.get("planned_item_id") or ""): item for item in items}
    delta_summary = _as_document(delta.get("summary"))
    closeout_forced = bool(closeout.get("forced", False))
    rows = []
    for index, planned in enumerate(plan.planned_items, start=1):
        planned_id = str(planned.get("planned_item_id") or "")
        item = items_by_planned.get(planned_id)
        task_statuses = _task_statuses(item, project_store) if item else []
        kb_ids = [str(value) for value in (_as_document(planned.get("knowledge"))).get("top_entry_ids", []) if str(value).strip()]
        warnings = []
        if item is None:
            warnings.append("planned_item_not_executed")
        if item and item.status == "waived":
            warnings.append("waived_item")
        if closeout_forced:
            warnings.append("force_closed")
        evidence_status = _evidence_status(item, delta_summary, kb_ids, kb_summaries, task_statuses, closeout_forced)
        score = _item_effectiveness_score(item, delta_summary, evidence_status, task_statuses, closeout_forced)
        rows.append(
            sanitize_metadata(
                {
                    "planned_item_id": planned_id,
                    "recommendation_id": planned.get("recommendation_id"),
                    "fix_item_id": item.item_id if item else None,
                    "planning_score": planned.get("planning_score"),
                    "original_rank": index,
                    "severity": planned.get("severity"),
                    "target": _safe_dict(planned.get("target")),
                    "planned_knowledge": {
                        "match_count": (_as_document(planned.get("knowledge"))).get("match_count", len(kb_ids)),
                        "top_entry_ids": kb_ids,
                        "risk": (_as_document(planned.get("knowledge"))).get("risk"),
                        "warnings": (_as_document(planned.get("knowledge"))).get("warnings", []),
                    },
                    "execution": {
                        "fix_item_status": item.status if item else "missing",
                        "linked_review_task_ids": [item.review_task_id] if item and item.review_task_id else [],
                        "task_statuses": task_statuses,
                        "waived": bool(item and item.status == "waived"),
                        "force_closed": closeout_forced,
                    },
                    "delta": {
                        "sprint_delta_status": delta_summary.get("status"),
                        "song_delta_status": _song_delta_status(delta, planned),
                        "issue_count_delta": delta_summary.get("issue_count_delta"),
                        "rating_delta": delta_summary.get("rating_delta"),
                        "accepted_delta": delta_summary.get("accepted_delta"),
                    },
                    "outcome": {
                        "evidence_status": evidence_status,
                        "observed_outcome_status": _observed_status(evidence_status, score),
                        "observed_effectiveness_score": score,
                        "kb_evidence_helpfulness": _kb_helpfulness(evidence_status, kb_ids),
                    },
                    "warnings": warnings,
                }
            )
        )
    for item in items:
        planned_id = str(item.source.get("planned_item_id") or "")
        if planned_id in planned_by_id:
            continue
        rows.append(
            sanitize_metadata(
                {
                    "planned_item_id": planned_id or None,
                    "recommendation_id": item.source.get("recommendation_id"),
                    "fix_item_id": item.item_id,
                    "planning_score": item.source.get("planning_score"),
                    "original_rank": None,
                    "severity": item.severity,
                    "target": item.target,
                    "planned_knowledge": {"match_count": 0, "top_entry_ids": [], "risk": None, "warnings": ["manual_or_unplanned_item"]},
                    "execution": {"fix_item_status": item.status, "linked_review_task_ids": [item.review_task_id] if item.review_task_id else [], "task_statuses": _task_statuses(item, project_store), "waived": item.status == "waived", "force_closed": closeout_forced},
                    "delta": {"sprint_delta_status": delta_summary.get("status"), "song_delta_status": _song_delta_status(delta, {"target": item.target}), "issue_count_delta": delta_summary.get("issue_count_delta"), "rating_delta": delta_summary.get("rating_delta"), "accepted_delta": delta_summary.get("accepted_delta")},
                    "outcome": {"evidence_status": "unknown", "observed_outcome_status": "unknown", "observed_effectiveness_score": 0, "kb_evidence_helpfulness": "missing"},
                    "warnings": ["unplanned_fix_item"],
                }
            )
        )
    return rows


from song_agent.domains.quality import v142_afpr_readiness as _v142_afpr_readiness
from song_agent.domains.quality.v142_afpr_readiness import _review_summary as _review_summary, _calibration_hints as _calibration_hints, _plan_effectiveness_score as _plan_effectiveness_score, _ranking_alignment_score as _ranking_alignment_score, _evidence_status as _evidence_status, _item_effectiveness_score as _item_effectiveness_score, _observed_status as _observed_status, _kb_helpfulness as _kb_helpfulness, _overall_kb_helpfulness as _overall_kb_helpfulness, _task_statuses as _task_statuses, _song_delta_status as _song_delta_status, _plan_source as _plan_source, _sprint_source as _sprint_source, _item_source as _item_source, _delta_source as _delta_source, _closeout_source as _closeout_source, _review_matches_project as _review_matches_project, _safe_dict as _safe_dict, _bounded as _bounded, _int as _int, _int_or_none as _int_or_none, _float as _float, _validate_id as _validate_id, _lock_for_root as _lock_for_root, _append_event as _append_event















































_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()

_v142_afpr_readiness.bind_globals(globals())
