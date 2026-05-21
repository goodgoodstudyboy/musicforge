from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.acceptance_fix_planning import AcceptanceFixPlan, AcceptanceFixPlanningStore, fix_plan_summary
from song_agent.acceptance_fix_sprints import AcceptanceFixItem, AcceptanceFixSprint, AcceptanceFixSprintStore, acceptance_fix_closeout_summary, fix_sprint_summary
from song_agent.acceptance_kb import AcceptanceKnowledgeBaseStore, knowledge_entry_summary
from song_agent.music_acceptance import stable_hash
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.review_tasks import ReviewTaskStore


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
    scope: dict[str, Any]
    source: dict[str, Any]
    summary: dict[str, Any]
    item_outcomes: list[dict[str, Any]]
    calibration_hints: list[dict[str, Any]]
    warnings: list[str]
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "AcceptanceFixPlanReview":
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

    def latest_summary(self, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
        rows = self.list_reviews(include_archived=False, release_id=release_id, project_id=project_id)
        if not rows:
            return {"status": "missing"}
        return fix_plan_review_summary(rows[0])

    def get_or_missing_for_plan(self, plan_id: str) -> dict[str, Any]:
        review = self.latest_for_plan(plan_id)
        if review is None:
            return {"status": "missing", "plan_id": plan_id, "stale": False}
        return review.to_dict()

    def refresh_for_plan(self, plan_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> AcceptanceFixPlanReview:
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

    def refresh_review(self, review_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> AcceptanceFixPlanReview:
        review = self.read_review(review_id)
        return self.refresh_for_plan(review.plan_id, payload or {}, now=now)

    def archive_review(self, review_id: str, *, now: str | None = None) -> AcceptanceFixPlanReview:
        with self.lock:
            review = self.read_review(review_id)
            updated = AcceptanceFixPlanReview.from_dict({**review.to_dict(), "status": "archived", "readiness": "archived", "updated_at": now or now_iso()})
            write_json(self.review_dir(review_id) / "outcome-review.json", updated.to_dict())
            _append_event(self.review_dir(review_id) / "events.jsonl", "acceptance_fix_plan_outcome_review_archived", {"review_id": review_id}, now)
            return updated

    def review_is_stale(self, review: AcceptanceFixPlanReview | dict[str, Any]) -> bool:
        data = review.to_dict() if isinstance(review, AcceptanceFixPlanReview) else review if isinstance(review, dict) else {}
        try:
            current = self._source_state(str(data.get("plan_id") or ""))
        except AcceptanceFixPlanReviewError:
            return True
        stored = data.get("source") if isinstance(data.get("source"), dict) else {}
        keys = ("plan_hash", "plan_source_hash", "fix_sprint_hash", "fix_items_hash", "delta_hash", "closeout_hash", "source_hash")
        return any(str(current.get(key) or "") != str(stored.get(key) or "") for key in keys) or current.get("kb_entry_hashes") != stored.get("kb_entry_hashes")

    def _build_review(self, review_id: str, plan_id: str, payload: dict[str, Any], *, created_at: str, now: str) -> AcceptanceFixPlanReview:
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

    def _source_state(self, plan_id: str, *, plan: AcceptanceFixPlan | None = None) -> dict[str, Any]:
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

    def _kb_summaries(self, plan: AcceptanceFixPlan, items: list[AcceptanceFixItem]) -> dict[str, dict[str, Any]]:
        ids: set[str] = set()
        for item in plan.planned_items:
            knowledge = item.get("knowledge") if isinstance(item.get("knowledge"), dict) else {}
            ids.update(str(value) for value in knowledge.get("top_entry_ids", []) if str(value).strip())
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            ids.update(str(value) for value in source.get("kb_entry_ids", []) if str(value).strip())
        for item in items:
            source = item.source if isinstance(item.source, dict) else {}
            ids.update(str(value) for value in source.get("kb_entry_ids", []) if str(value).strip())
            planning = item.evidence.get("planning") if isinstance(item.evidence, dict) and isinstance(item.evidence.get("planning"), dict) else {}
            knowledge = planning.get("knowledge") if isinstance(planning.get("knowledge"), dict) else {}
            ids.update(str(value) for value in knowledge.get("top_entry_ids", []) if str(value).strip())
        summaries: dict[str, dict[str, Any]] = {}
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


def fix_plan_review_summary(review: AcceptanceFixPlanReview | dict[str, Any] | None) -> dict[str, Any]:
    data = review.to_dict() if isinstance(review, AcceptanceFixPlanReview) else review if isinstance(review, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness") or data.get("status") or "missing",
            "review_id": data.get("review_id"),
            "plan_id": data.get("plan_id"),
            "fix_sprint_id": data.get("fix_sprint_id"),
            "scope": data.get("scope") if isinstance(data.get("scope"), dict) else {},
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


def latest_fix_plan_review_summary(store: AcceptanceFixPlanReviewStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    return store.latest_summary(release_id=release_id, project_id=project_id)


def write_acceptance_fix_plan_review_summary(path: Path, store: AcceptanceFixPlanReviewStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    summary = latest_fix_plan_review_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary


def _item_outcomes(plan: AcceptanceFixPlan, sprint: AcceptanceFixSprint, items: list[AcceptanceFixItem], delta: dict[str, Any], closeout: dict[str, Any], kb_summaries: dict[str, dict[str, Any]], *, project_store: ProjectStore) -> list[dict[str, Any]]:
    planned_by_id = {str(item.get("planned_item_id") or ""): item for item in plan.planned_items}
    items_by_planned = {str(item.source.get("planned_item_id") or ""): item for item in items}
    delta_summary = delta.get("summary") if isinstance(delta.get("summary"), dict) else {}
    closeout_forced = bool(closeout.get("forced", False))
    rows = []
    for index, planned in enumerate(plan.planned_items, start=1):
        planned_id = str(planned.get("planned_item_id") or "")
        item = items_by_planned.get(planned_id)
        task_statuses = _task_statuses(item, project_store) if item else []
        kb_ids = [str(value) for value in (planned.get("knowledge") if isinstance(planned.get("knowledge"), dict) else {}).get("top_entry_ids", []) if str(value).strip()]
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
                        "match_count": (planned.get("knowledge") if isinstance(planned.get("knowledge"), dict) else {}).get("match_count", len(kb_ids)),
                        "top_entry_ids": kb_ids,
                        "risk": (planned.get("knowledge") if isinstance(planned.get("knowledge"), dict) else {}).get("risk"),
                        "warnings": (planned.get("knowledge") if isinstance(planned.get("knowledge"), dict) else {}).get("warnings", []),
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


def _review_summary(plan: AcceptanceFixPlan, sprint: AcceptanceFixSprint, items: list[AcceptanceFixItem], delta: dict[str, Any], closeout: dict[str, Any], item_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    delta_summary = delta.get("summary") if isinstance(delta.get("summary"), dict) else {}
    statuses = [str(item.get("outcome", {}).get("evidence_status") or "") for item in item_outcomes if isinstance(item.get("outcome"), dict)]
    warnings = []
    open_items = [item for item in items if item.status not in {"fixed", "closed", "waived"}]
    waived_items = [item for item in items if item.status == "waived"]
    fixed_items = [item for item in items if item.status in {"fixed", "closed"}]
    score = _plan_effectiveness_score(delta_summary, items, closeout, item_outcomes)
    if closeout.get("forced"):
        warnings.append("force_closed")
    if waived_items:
        warnings.append("waived_items_present")
    if open_items:
        warnings.append("open_items_present")
    manual_accepted_count = _int(delta_summary.get("manual_accepted_count"), 0)
    synthetic_accepted_count = _int(delta_summary.get("synthetic_accepted_count"), 0)
    manual_review_count = _int(delta_summary.get("manual_review_count"), 0)
    synthetic_review_count = _int(delta_summary.get("synthetic_review_count"), 0)
    manual_recheck_confirmed = manual_accepted_count > 0 or manual_review_count > 0
    synthetic_only = synthetic_accepted_count > 0 and manual_accepted_count == 0 and manual_review_count == 0
    if synthetic_only:
        warnings.append("synthetic_only_recheck")
    ranking = _ranking_alignment_score(plan.planned_items, item_outcomes)
    helpfulness = _overall_kb_helpfulness(item_outcomes)
    return sanitize_metadata(
        {
            "planned_item_count": len(plan.planned_items),
            "executed_item_count": len([item for item in items if item.source.get("source_type") == "planned_item"]),
            "resolved_item_count": len(fixed_items),
            "waived_item_count": len(waived_items),
            "open_item_count": len(open_items),
            "plan_effectiveness_score": score,
            "ranking_alignment_score": ranking,
            "kb_evidence_helpfulness": helpfulness,
            "supported_item_count": statuses.count("supported"),
            "unsupported_item_count": statuses.count("unsupported"),
            "unknown_item_count": statuses.count("unknown") + statuses.count("not_executed"),
            "warning_count": len(warnings) + sum(1 for item in item_outcomes if item.get("warnings")),
            "manual_recheck_confirmed": manual_recheck_confirmed,
            "synthetic_only": synthetic_only,
            "manual_accepted_count": manual_accepted_count,
            "synthetic_accepted_count": synthetic_accepted_count,
            "manual_review_count": manual_review_count,
            "synthetic_review_count": synthetic_review_count,
            "delta_status": delta_summary.get("status"),
            "closeout_status": closeout.get("status"),
            "warnings": warnings,
        }
    )


def _calibration_hints(plan: AcceptanceFixPlan, item_outcomes: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, Any]]:
    hints = []
    for item in item_outcomes:
        outcome = item.get("outcome") if isinstance(item.get("outcome"), dict) else {}
        planning_score = _int(item.get("planning_score"), 0)
        if planning_score >= 80 and outcome.get("evidence_status") in {"unsupported", "unknown", "not_executed"}:
            hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "deprioritize_pattern", "severity": "warning", "planned_item_id": item.get("planned_item_id"), "reason": "High-score planned item did not produce supported evidence.", "suggestion": "Review issue weighting and KB match quality before using similar high-score items again."})
        if item.get("warnings"):
            hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "require_stronger_evidence", "severity": "note", "planned_item_id": item.get("planned_item_id"), "reason": "Planned item required waiver, force close, or incomplete evidence.", "suggestion": "Prefer manual recheck evidence before treating this pattern as reliable."})
    if summary.get("ranking_alignment_score", 100) < 60:
        hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "ranking_alignment_low", "severity": "warning", "reason": "Observed outcomes do not align with planning score order.", "suggestion": "Compare low-score supported items against high-score unknown items before the next plan."})
    if summary.get("kb_evidence_helpfulness") in {"negative", "missing"} and int(summary.get("planned_item_count") or 0):
        hints.append({"hint_id": f"hint-{len(hints)+1:03d}", "type": "kb_helpfulness_low", "severity": "warning", "reason": "KB evidence did not clearly support the plan outcome.", "suggestion": "Refresh KB only from non-stale closed sprints and avoid over-weighting weak matches."})
    return [sanitize_metadata({**hint, "suggestion": _bounded(hint.get("suggestion"), 400), "reason": _bounded(hint.get("reason"), 300)}) for hint in hints[:12]]


def _plan_effectiveness_score(delta_summary: dict[str, Any], items: list[AcceptanceFixItem], closeout: dict[str, Any], item_outcomes: list[dict[str, Any]]) -> int:
    score = 50
    if delta_summary.get("status") == "improved":
        score += 20
    if str(delta_summary.get("after_readiness") or "") in {"ready", "watch"}:
        score += 10
    if items and all(item.status in {"fixed", "closed", "waived"} for item in items):
        score += 10
    rating_delta = _float(delta_summary.get("rating_delta"))
    if rating_delta is not None:
        if rating_delta >= 2:
            score += 8
        elif rating_delta >= 1:
            score += 5
        elif rating_delta < 0:
            score -= 8
    issue_delta = _int_or_none(delta_summary.get("issue_count_delta"))
    if issue_delta is not None:
        if issue_delta <= -2:
            score += 8
        elif issue_delta == -1:
            score += 5
        elif issue_delta > 0:
            score -= 8
    if _int(delta_summary.get("accepted_delta"), 0) > 0:
        score += 5
    if delta_summary.get("status") == "regressed":
        score -= 15
    if any(item.status not in {"fixed", "closed", "waived"} for item in items):
        score -= 12
    if any(item.status == "waived" for item in items):
        score -= 8
    if closeout.get("forced"):
        score -= 10
    supported = sum(1 for item in item_outcomes if isinstance(item.get("outcome"), dict) and item["outcome"].get("evidence_status") == "supported")
    unsupported = sum(1 for item in item_outcomes if isinstance(item.get("outcome"), dict) and item["outcome"].get("evidence_status") == "unsupported")
    score += min(10, supported * 3)
    score -= min(10, unsupported * 5)
    return max(0, min(100, score))


def _ranking_alignment_score(planned_items: list[dict[str, Any]], item_outcomes: list[dict[str, Any]]) -> int:
    if len(planned_items) <= 1:
        return 100
    outcome_by_id = {str(item.get("planned_item_id") or ""): item for item in item_outcomes}
    pairs = []
    for planned in planned_items:
        planned_id = str(planned.get("planned_item_id") or "")
        outcome = outcome_by_id.get(planned_id, {})
        outcome_data = outcome.get("outcome") if isinstance(outcome.get("outcome"), dict) else {}
        pairs.append((_int(planned.get("planning_score"), 0), _int(outcome_data.get("observed_effectiveness_score"), 0)))
    inversions = 0
    total = 0
    for left in range(len(pairs)):
        for right in range(left + 1, len(pairs)):
            total += 1
            if pairs[left][0] > pairs[right][0] and pairs[left][1] < pairs[right][1]:
                inversions += 1
            elif pairs[left][0] < pairs[right][0] and pairs[left][1] > pairs[right][1]:
                inversions += 1
    if not total:
        return 100
    return max(0, min(100, int(round(100 - (inversions / total) * 100))))


def _evidence_status(item: AcceptanceFixItem | None, delta_summary: dict[str, Any], kb_ids: list[str], kb_summaries: dict[str, dict[str, Any]], task_statuses: list[str], forced: bool) -> str:
    if item is None:
        return "not_executed"
    if item.status not in {"fixed", "closed", "waived"}:
        return "not_executed"
    if delta_summary.get("status") == "regressed":
        return "unsupported"
    if item.status == "waived" or forced:
        return "mixed"
    kb_effective = any(kb_summaries.get(entry_id, {}).get("outcome_status") == "effective" for entry_id in kb_ids)
    kb_mixed = any(kb_summaries.get(entry_id, {}).get("outcome_status") == "mixed" for entry_id in kb_ids)
    tasks_closed = not task_statuses or all(status in {"resolved", "archived"} for status in task_statuses)
    if delta_summary.get("status") == "improved" and tasks_closed and (kb_effective or not kb_ids):
        return "supported"
    if delta_summary.get("status") == "improved" and (kb_mixed or kb_ids):
        return "mixed"
    if delta_summary.get("status") in {"unchanged", "incomplete"}:
        return "unknown"
    return "unknown"


def _item_effectiveness_score(item: AcceptanceFixItem | None, delta_summary: dict[str, Any], evidence_status: str, task_statuses: list[str], forced: bool) -> int:
    score = 0
    if evidence_status == "supported":
        score = 72
    elif evidence_status == "mixed":
        score = 48
    elif evidence_status == "unknown":
        score = 30
    elif evidence_status == "unsupported":
        score = 10
    elif evidence_status == "not_executed":
        score = 0
    rating_delta = _float(delta_summary.get("rating_delta"))
    if rating_delta is not None and rating_delta >= 2:
        score += 10
    elif rating_delta is not None and rating_delta >= 1:
        score += 5
    if _int(delta_summary.get("accepted_delta"), 0) > 0:
        score += 6
    issue_delta = _int_or_none(delta_summary.get("issue_count_delta"))
    if issue_delta is not None and issue_delta < 0:
        score += 6
    if item and item.status == "waived":
        score -= 10
    if forced:
        score -= 8
    if task_statuses and not all(status in {"resolved", "archived"} for status in task_statuses):
        score -= 10
    return max(0, min(100, score))


def _observed_status(evidence_status: str, score: int) -> str:
    if evidence_status == "supported" and score >= 65:
        return "effective"
    if evidence_status in {"mixed", "supported"}:
        return "mixed"
    if evidence_status == "unsupported":
        return "ineffective"
    return "unknown"


def _kb_helpfulness(evidence_status: str, kb_ids: list[str]) -> str:
    if not kb_ids:
        return "missing"
    return {"supported": "helpful", "mixed": "mixed", "unsupported": "misleading", "unknown": "neutral", "not_executed": "unknown"}.get(evidence_status, "unknown")


def _overall_kb_helpfulness(item_outcomes: list[dict[str, Any]]) -> str:
    values = [str((item.get("outcome") if isinstance(item.get("outcome"), dict) else {}).get("kb_evidence_helpfulness") or "missing") for item in item_outcomes]
    if not values or all(value == "missing" for value in values):
        return "missing"
    helpful = values.count("helpful")
    mixed = values.count("mixed")
    misleading = values.count("misleading")
    if helpful and not misleading:
        return "positive" if not mixed else "mixed_positive"
    if misleading and misleading >= helpful:
        return "negative"
    return "neutral"


def _task_statuses(item: AcceptanceFixItem | None, project_store: ProjectStore) -> list[str]:
    if not item or not item.review_task_id or not item.target.get("project_id"):
        return []
    try:
        task = ReviewTaskStore(project_store.project_dir(str(item.target.get("project_id")))).read_task(str(item.review_task_id))
    except Exception:
        return ["missing"]
    return [str(task.status or "missing")]


def _song_delta_status(delta: dict[str, Any], planned_or_item: dict[str, Any]) -> str:
    target = planned_or_item.get("target") if isinstance(planned_or_item.get("target"), dict) else {}
    song_id = str(target.get("song_id") or "")
    for row in delta.get("song_deltas", []) if isinstance(delta.get("song_deltas"), list) else []:
        if str(row.get("song_id") or "") != song_id:
            continue
        issue_delta = _int(row.get("issue_delta"), 0)
        before_rating = _float(row.get("before_rating"))
        after_rating = _float(row.get("after_rating"))
        if after_rating is not None and before_rating is not None and after_rating > before_rating:
            return "improved"
        if issue_delta < 0:
            return "improved"
        if after_rating is not None and before_rating is not None and after_rating < before_rating:
            return "regressed"
        if issue_delta > 0:
            return "regressed"
        return "unchanged"
    summary = delta.get("summary") if isinstance(delta.get("summary"), dict) else {}
    return str(summary.get("status") or "unknown")


def _plan_source(plan: AcceptanceFixPlan) -> dict[str, Any]:
    return sanitize_metadata({"plan_id": plan.plan_id, "status": plan.status, "scope": plan.scope, "source": plan.source, "summary": plan.summary, "planned_items": plan.planned_items, "strategy": plan.strategy, "warnings": plan.warnings, "execution": plan.execution})


def _sprint_source(sprint: AcceptanceFixSprint) -> dict[str, Any]:
    return sanitize_metadata({"fix_sprint_id": sprint.fix_sprint_id, "status": sprint.status, "scope": sprint.scope, "source": sprint.source, "settings": sprint.settings, "counts": sprint.counts, "recheck": sprint.recheck, "delta_summary": sprint.delta_summary, "closeout_summary": sprint.closeout_summary})


def _item_source(item: AcceptanceFixItem) -> dict[str, Any]:
    return sanitize_metadata({"item_id": item.item_id, "status": item.status, "priority": item.priority, "severity": item.severity, "source": item.source, "target": item.target, "evidence": item.evidence, "review_task_id": item.review_task_id, "resolution": item.resolution})


def _delta_source(delta: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata({"source": delta.get("source") if isinstance(delta.get("source"), dict) else {}, "recheck": delta.get("recheck") if isinstance(delta.get("recheck"), dict) else {}, "summary": delta.get("summary") if isinstance(delta.get("summary"), dict) else {}, "song_deltas": delta.get("song_deltas") if isinstance(delta.get("song_deltas"), list) else [], "issue_deltas": delta.get("issue_deltas") if isinstance(delta.get("issue_deltas"), list) else []})


def _closeout_source(closeout: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata({"status": closeout.get("status"), "forced": bool(closeout.get("forced", False)), "summary": closeout.get("summary") if isinstance(closeout.get("summary"), dict) else {}, "checks": closeout.get("checks") if isinstance(closeout.get("checks"), list) else []})


def _review_matches_project(review: AcceptanceFixPlanReview, project_id: str) -> bool:
    if review.scope.get("project_id") == project_id:
        return True
    for item in review.item_outcomes:
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        if target.get("project_id") == project_id:
            return True
    return False


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _bounded(value: Any, limit: int = 300) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{6}}", text):
        raise AcceptanceFixPlanReviewError(f"Invalid {prefix} id.")
    return text


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]


def _append_event(path: Path, event: str, payload: dict[str, Any] | None = None, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"timestamp": now or now_iso(), "event": event, **(payload or {})})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
