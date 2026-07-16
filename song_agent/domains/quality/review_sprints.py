from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import ReviewTask, ReviewTaskStore, validate_review_task_id


REVIEW_SPRINT_SCHEMA_VERSION = 1
REVIEW_SPRINT_SUMMARY_SCHEMA_VERSION = 1
REVIEW_SPRINT_CONFLICT_SCHEMA_VERSION = 1
REVIEW_SPRINT_RECOMMENDATION_SCHEMA_VERSION = 1
SPRINT_ID_PATTERN = re.compile(r"^sprint-[0-9]{3,6}$")
SPRINT_STATUSES = {"open", "in_progress", "blocked", "closed", "archived"}
MUTABLE_SPRINT_STATUSES = {"open", "in_progress", "blocked"}
LOCAL_STRATEGIES = {"conservative", "balanced", "bold"}
_LOCKS_GUARD = threading.RLock()
_STORE_LOCKS: dict[str, threading.RLock] = {}


class ReviewSprintError(ValueError):
    pass


class ReviewSprintStateError(ReviewSprintError):
    pass


@dataclass(frozen=True)
class ReviewSprint:
    schema_version: int
    sprint_id: str
    project_id: str
    name: str
    description: str
    status: str
    parent_version_id: str | None = None
    task_refs: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    selected_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    closed_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewSprint":
        if not isinstance(data, dict):
            raise ReviewSprintError("review sprint must be an object.")
        status = str(data.get("status") or "open")
        if status not in SPRINT_STATUSES:
            raise ReviewSprintError(f"sprint status must be one of: {', '.join(sorted(SPRINT_STATUSES))}.")
        return cls(
            schema_version=int(data.get("schema_version", REVIEW_SPRINT_SCHEMA_VERSION) or REVIEW_SPRINT_SCHEMA_VERSION),
            sprint_id=validate_review_sprint_id(str(data.get("sprint_id") or "sprint-001")),
            project_id=str(data.get("project_id") or ""),
            name=sanitize_sensitive_text(str(data.get("name") or ""))[:160],
            description=sanitize_sensitive_text(str(data.get("description") or ""))[:1000],
            status=status,
            parent_version_id=_optional_str(data.get("parent_version_id")),
            task_refs=[_task_ref_from_dict(item) for item in data.get("task_refs", []) if isinstance(item, dict)],
            settings=_settings_from_dict(data.get("settings") if isinstance(data.get("settings"), dict) else {}),
            counts={str(key): _safe_int(value) for key, value in dict(data.get("counts") or {}).items()},
            selected_task_id=None if not data.get("selected_task_id") else validate_review_task_id(str(data.get("selected_task_id"))),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            closed_at=_optional_str(data.get("closed_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReviewSprintStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.root = self.project_dir / "review-sprints"
        self.lock = _lock_for_project(self.project_dir)

    def create_sprint(
        self,
        *,
        project_id: str,
        task_store: ReviewTaskStore,
        payload: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> ReviewSprint:
        payload = payload if isinstance(payload, dict) else {}
        now = now or now_iso()
        task_ids = _task_ids(payload.get("task_ids"))
        tasks = _read_project_tasks(task_store, project_id, task_ids)
        parent_version_id = _optional_str(payload.get("parent_version_id")) or (tasks[0].parent_version_id if tasks else None)
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            sprint_id, sprint_dir = self._reserve_sprint_dir()
            sprint = ReviewSprint.from_dict(
                {
                    "schema_version": REVIEW_SPRINT_SCHEMA_VERSION,
                    "sprint_id": sprint_id,
                    "project_id": project_id,
                    "name": payload.get("name") or f"Review Sprint {sprint_id[-3:]}",
                    "description": payload.get("description") or "",
                    "status": "open",
                    "parent_version_id": parent_version_id,
                    "task_refs": [_task_ref(task, index + 1, lane=str(payload.get("lane") or ""), notes=str(payload.get("notes") or ""), now=now) for index, task in enumerate(tasks)],
                    "settings": payload.get("settings") if isinstance(payload.get("settings"), dict) else {},
                    "counts": {},
                    "selected_task_id": tasks[0].task_id if tasks else None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            try:
                write_json(sprint_dir / "sprint.json", sprint.to_dict())
                _append_event(sprint_dir, "review_sprint_created", {"task_ids": task_ids}, now)
            except Exception:
                if sprint_dir.exists() and not (sprint_dir / "sprint.json").exists():
                    shutil.rmtree(sprint_dir)
                raise
        self.detect_conflicts(sprint, task_store=task_store, now=now)
        return self.refresh_summary(sprint, task_store=task_store, now=now)

    def list_sprints(self, *, include_archived: bool = False, status: str | None = None) -> list[ReviewSprint]:
        if not self.root.exists():
            return []
        sprints = []
        for path in self.root.glob("sprint-*/sprint.json"):
            try:
                sprint = ReviewSprint.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if sprint.status == "archived" and not include_archived:
                continue
            if status and sprint.status != status:
                continue
            sprints.append(sprint)
        return sorted(sprints, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_sprint(self, sprint_id: str) -> ReviewSprint:
        path = self.sprint_dir(sprint_id) / "sprint.json"
        if not path.exists():
            raise FileNotFoundError(sprint_id)
        return ReviewSprint.from_dict(read_json(path))

    def update_sprint(self, sprint: ReviewSprint, *, event: str | None = None, payload: dict[str, Any] | None = None, now: str | None = None) -> ReviewSprint:
        now = now or now_iso()
        updated = ReviewSprint.from_dict({**sprint.to_dict(), "updated_at": now})
        with self.lock:
            sprint_dir = self.sprint_dir(updated.sprint_id)
            write_json(sprint_dir / "sprint.json", updated.to_dict())
            if event:
                _append_event(sprint_dir, event, payload or {}, now)
        return updated

    def add_tasks(
        self,
        sprint: ReviewSprint,
        *,
        task_store: ReviewTaskStore,
        task_ids: list[str],
        lane: str = "",
        notes: str = "",
        now: str | None = None,
    ) -> ReviewSprint:
        _ensure_sprint_mutable(sprint)
        now = now or now_iso()
        clean_ids = _task_ids(task_ids)
        existing = {str(ref.get("task_id") or "") for ref in sprint.task_refs}
        duplicates = sorted(existing & set(clean_ids))
        if duplicates:
            raise ReviewSprintError(f"Review sprint already contains task: {duplicates[0]}.")
        tasks = _read_project_tasks(task_store, sprint.project_id, clean_ids)
        start_order = max([int(ref.get("order") or 0) for ref in sprint.task_refs] or [0]) + 1
        refs = list(sprint.task_refs)
        refs.extend(_task_ref(task, start_order + index, lane=lane, notes=notes, now=now) for index, task in enumerate(tasks))
        updated = self.update_sprint(
            ReviewSprint.from_dict({**sprint.to_dict(), "task_refs": refs, "selected_task_id": sprint.selected_task_id or (tasks[0].task_id if tasks else None)}),
            event="review_sprint_tasks_added",
            payload={"task_ids": clean_ids},
            now=now,
        )
        self.detect_conflicts(updated, task_store=task_store, now=now)
        return self.refresh_summary(updated, task_store=task_store, now=now)

    def remove_task(self, sprint: ReviewSprint, task_id: str, *, task_store: ReviewTaskStore | None = None, now: str | None = None) -> ReviewSprint:
        _ensure_sprint_mutable(sprint)
        now = now or now_iso()
        task_id = validate_review_task_id(task_id)
        refs = [ref for ref in sprint.task_refs if ref.get("task_id") != task_id]
        if len(refs) == len(sprint.task_refs):
            raise ReviewSprintError("Review sprint task ref not found.")
        refs = [_renumber_ref(ref, index + 1) for index, ref in enumerate(refs)]
        selected = sprint.selected_task_id
        if selected == task_id:
            selected = str(refs[0].get("task_id")) if refs else None
        updated = self.update_sprint(
            ReviewSprint.from_dict({**sprint.to_dict(), "task_refs": refs, "selected_task_id": selected}),
            event="review_sprint_task_removed",
            payload={"task_id": task_id},
            now=now,
        )
        if task_store is not None:
            self.detect_conflicts(updated, task_store=task_store, now=now)
            return self.refresh_summary(updated, task_store=task_store, now=now)
        return updated

    def reorder_tasks(self, sprint: ReviewSprint, task_ids: list[str], *, task_store: ReviewTaskStore | None = None, now: str | None = None) -> ReviewSprint:
        _ensure_sprint_mutable(sprint)
        now = now or now_iso()
        clean_ids = _task_ids(task_ids)
        refs_by_id = {str(ref.get("task_id")): ref for ref in sprint.task_refs}
        if set(clean_ids) != set(refs_by_id):
            raise ReviewSprintError("Reorder task_ids must match sprint task refs.")
        refs = [_renumber_ref(refs_by_id[task_id], index + 1) for index, task_id in enumerate(clean_ids)]
        updated = self.update_sprint(
            ReviewSprint.from_dict({**sprint.to_dict(), "task_refs": refs, "selected_task_id": clean_ids[0] if clean_ids else None}),
            event="review_sprint_tasks_reordered",
            payload={"task_ids": clean_ids},
            now=now,
        )
        if task_store is not None:
            self.detect_conflicts(updated, task_store=task_store, now=now)
            return self.refresh_summary(updated, task_store=task_store, now=now)
        return updated

    def refresh_summary(self, sprint: ReviewSprint, *, task_store: ReviewTaskStore, now: str | None = None) -> ReviewSprint:
        now = now or now_iso()
        tasks = _included_tasks(sprint, task_store)
        conflict_report = self.read_conflict_report(sprint.sprint_id, default={})
        counts = _summary_counts(tasks, task_store)
        counts["conflict_count"] = len(conflict_report.get("conflicts", [])) if isinstance(conflict_report, dict) else 0
        counts["blocking_conflict_count"] = len([item for item in conflict_report.get("conflicts", []) if isinstance(item, dict) and item.get("severity") == "blocking"]) if isinstance(conflict_report, dict) else 0
        recommended_order = [task.task_id for task in sorted(tasks, key=lambda task: (-int(task.priority or 0), _ref_order(sprint, task.task_id), task.task_id))]
        summary = {
            "schema_version": REVIEW_SPRINT_SUMMARY_SCHEMA_VERSION,
            "sprint_id": sprint.sprint_id,
            "project_id": sprint.project_id,
            "status": sprint.status,
            "task_count": len(tasks),
            "counts": counts,
            "recommended_order": recommended_order,
            "updated_at": now,
        }
        status = sprint.status
        if status in MUTABLE_SPRINT_STATUSES:
            status = "blocked" if counts["blocking_conflict_count"] else ("in_progress" if _sprint_has_progress(tasks, task_store) else "open")
            summary["status"] = status
        with self.lock:
            write_json(self.sprint_dir(sprint.sprint_id) / "summary.json", sanitize_metadata(summary))
        return self.update_sprint(ReviewSprint.from_dict({**sprint.to_dict(), "status": status, "counts": counts}), event="review_sprint_summary_refreshed", payload={"task_count": len(tasks), "conflict_count": counts["conflict_count"]}, now=now)

    def detect_conflicts(
        self,
        sprint: ReviewSprint,
        *,
        task_store: ReviewTaskStore,
        parent_plan_hashes: dict[str, str] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        now = now or now_iso()
        tasks = _included_tasks(sprint, task_store, missing_ok=True)
        task_ids = {task.task_id for task in tasks}
        conflicts: list[dict[str, Any]] = []
        missing_ids = [str(ref.get("task_id")) for ref in sprint.task_refs if ref.get("included", True) and str(ref.get("task_id")) not in task_ids]
        for task_id in missing_ids:
            conflicts.append(_conflict("blocking", "missing_task", [task_id], "Sprint references a missing ReviewTask."))
        for task in tasks:
            conflicts.extend(_task_conflicts(sprint, task, task_ids, task_store, parent_plan_hashes or {}))
        for left_index, left in enumerate(tasks):
            for right in tasks[left_index + 1 :]:
                conflicts.extend(_pair_conflicts(left, right))
        conflicts = [_with_conflict_id(conflict, index + 1) for index, conflict in enumerate(conflicts)]
        report = sanitize_metadata(
            {
                "schema_version": REVIEW_SPRINT_CONFLICT_SCHEMA_VERSION,
                "sprint_id": sprint.sprint_id,
                "created_at": now,
                "conflicts": conflicts,
                "stale_task_ids": sorted({task_id for conflict in conflicts if conflict.get("kind") == "stale_task" for task_id in conflict.get("task_ids", [])}),
                "blocked_task_ids": sorted({task_id for conflict in conflicts if conflict.get("severity") == "blocking" for task_id in conflict.get("task_ids", [])}),
            }
        )
        with self.lock:
            write_json(self.sprint_dir(sprint.sprint_id) / "conflict-report.json", report)
            _append_event(self.sprint_dir(sprint.sprint_id), "review_sprint_conflicts_refreshed", {"conflict_count": len(conflicts)}, now)
        return report

    def read_summary(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.sprint_dir(sprint_id) / "summary.json"
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def read_conflict_report(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.sprint_dir(sprint_id) / "conflict-report.json"
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def recommendation_report_path(self, sprint_id: str) -> Path:
        return self.sprint_dir(sprint_id) / "recommendation-report.json"

    def read_recommendation_report(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.recommendation_report_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def write_recommendation_report(self, sprint: ReviewSprint, report: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        clean_report = sanitize_metadata({**(report if isinstance(report, dict) else {}), "schema_version": REVIEW_SPRINT_RECOMMENDATION_SCHEMA_VERSION})
        with self.lock:
            write_json(self.recommendation_report_path(sprint.sprint_id), clean_report)
            _append_event(
                self.sprint_dir(sprint.sprint_id),
                "review_sprint_recommendations_refreshed",
                {
                    "recommended_count": len(clean_report.get("recommended_order", [])) if isinstance(clean_report.get("recommended_order"), list) else 0,
                    "context_recommendation_count": int((clean_report.get("source_summary") or {}).get("context_recommendation_count") or 0) if isinstance(clean_report.get("source_summary"), dict) else 0,
                },
                now,
            )
        return clean_report

    def judge_summary_path(self, sprint_id: str) -> Path:
        return self.sprint_dir(sprint_id) / "judge-summary.json"

    def read_judge_summary(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.judge_summary_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def write_judge_summary(self, sprint: ReviewSprint, summary: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        clean_summary = sanitize_metadata(summary if isinstance(summary, dict) else {})
        with self.lock:
            write_json(self.judge_summary_path(sprint.sprint_id), clean_summary)
            _append_event(
                self.sprint_dir(sprint.sprint_id),
                "review_sprint_judge_summary_refreshed",
                {"judged_task_count": clean_summary.get("judged_task_count"), "stale_judge_count": clean_summary.get("stale_judge_count")},
                now,
            )
        return clean_summary

    def closeout_report_path(self, sprint_id: str) -> Path:
        return self.sprint_dir(sprint_id) / "closeout-report.json"

    def read_closeout_report(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.closeout_report_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def write_closeout_report(self, sprint: ReviewSprint, report: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        clean_report = sanitize_metadata(report if isinstance(report, dict) else {})
        with self.lock:
            write_json(self.closeout_report_path(sprint.sprint_id), clean_report)
            _append_event(
                self.sprint_dir(sprint.sprint_id),
                "review_sprint_closeout_refreshed",
                {"status": clean_report.get("status"), "readiness": clean_report.get("readiness"), "close_allowed": bool(clean_report.get("close_allowed", False))},
                now,
            )
        return clean_report

    def signoff_path(self, sprint_id: str) -> Path:
        return self.sprint_dir(sprint_id) / "signoff.json"

    def read_signoff(self, sprint_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.signoff_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {})

    def write_signoff(self, sprint: ReviewSprint, record: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        clean_record = sanitize_metadata(record if isinstance(record, dict) else {})
        with self.lock:
            write_json(self.signoff_path(sprint.sprint_id), clean_record)
            _append_event(
                self.sprint_dir(sprint.sprint_id),
                "review_sprint_signoff_written",
                {"forced": bool(clean_record.get("forced", False)), "closeout_status": clean_record.get("closeout_status"), "selected_version_id": clean_record.get("selected_version_id")},
                now,
            )
        return clean_record

    def read_events(self, sprint_id: str) -> list[dict[str, Any]]:
        path = self.sprint_dir(sprint_id) / "events.jsonl"
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def append_event(self, sprint_id: str, event: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> None:
        now = now or now_iso()
        with self.lock:
            _append_event(self.sprint_dir(sprint_id), event, payload or {}, now)

    def close_sprint(self, sprint: ReviewSprint, *, now: str | None = None) -> ReviewSprint:
        if sprint.status == "archived":
            raise ReviewSprintStateError("Archived sprint cannot be closed.")
        if sprint.status == "closed":
            return sprint
        now = now or now_iso()
        return self.update_sprint(ReviewSprint.from_dict({**sprint.to_dict(), "status": "closed", "closed_at": now}), event="review_sprint_closed", payload={}, now=now)

    def archive_sprint(self, sprint: ReviewSprint, *, now: str | None = None) -> ReviewSprint:
        now = now or now_iso()
        return self.update_sprint(ReviewSprint.from_dict({**sprint.to_dict(), "status": "archived"}), event="review_sprint_archived", payload={}, now=now)

    def sprint_dir(self, sprint_id: str) -> Path:
        sprint_id = validate_review_sprint_id(sprint_id)
        base = self.root.resolve()
        target = (base / sprint_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside review sprints.") from exc
        return target

    def _reserve_sprint_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            sprint_id = f"sprint-{index:03d}"
            sprint_dir = self.sprint_dir(sprint_id)
            try:
                sprint_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return sprint_id, sprint_dir
        raise RuntimeError("Could not allocate review sprint id.")


def validate_review_sprint_id(sprint_id: str) -> str:
    if not SPRINT_ID_PATTERN.match(str(sprint_id or "")):
        raise ValueError("Invalid review sprint id.")
    return sprint_id


def review_sprint_export_summary(
    sprint: ReviewSprint,
    summary: dict[str, Any] | None = None,
    conflict_report: dict[str, Any] | None = None,
    recommendation_report: dict[str, Any] | None = None,
    action_queue_summary: dict[str, Any] | None = None,
    judge_summary: dict[str, Any] | None = None,
    closeout_summary: dict[str, Any] | None = None,
    signoff_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = summary if isinstance(summary, dict) else {}
    conflict_report = conflict_report if isinstance(conflict_report, dict) else {}
    action_queue_summary = action_queue_summary if isinstance(action_queue_summary, dict) else {}
    judge_summary = judge_summary if isinstance(judge_summary, dict) else {}
    closeout_summary = closeout_summary if isinstance(closeout_summary, dict) else {}
    signoff_summary = signoff_summary if isinstance(signoff_summary, dict) else {}
    recommendation_summary = _recommendation_summary_for_export(recommendation_report)
    counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else sprint.counts
    return sanitize_metadata(
        {
            "sprint_id": sprint.sprint_id,
            "name": sprint.name,
            "status": sprint.status,
            "parent_version_id": sprint.parent_version_id,
            "task_count": len([ref for ref in sprint.task_refs if ref.get("included", True)]),
            "summary": summary,
            "conflict_count": len(conflict_report.get("conflicts", [])) if isinstance(conflict_report.get("conflicts"), list) else int(counts.get("conflict_count") or 0),
            "recommendation_summary": recommendation_summary,
            "action_queue_summary": action_queue_summary,
            "judge_summary": _judge_summary_for_export(judge_summary),
            "closeout_summary": closeout_summary,
            "signoff_summary": signoff_summary,
            "task_ids": [str(ref.get("task_id")) for ref in sorted(sprint.task_refs, key=lambda ref: int(ref.get("order") or 0)) if ref.get("included", True)],
        }
    )


def review_sprint_project_rollup(sprints: list[dict[str, Any]]) -> dict[str, Any]:
    latest = sprints[0] if sprints else {}
    closed = [sprint for sprint in sprints if sprint.get("status") == "closed"]
    counts = [sprint.get("summary", {}).get("counts", {}) for sprint in sprints if isinstance(sprint.get("summary"), dict)]
    recommendation_summaries = [sprint.get("recommendation_summary", {}) for sprint in sprints if isinstance(sprint.get("recommendation_summary"), dict)]
    action_queue_summaries = [sprint.get("action_queue_summary", {}) for sprint in sprints if isinstance(sprint.get("action_queue_summary"), dict)]
    judge_summaries = [sprint.get("judge_summary", {}) for sprint in sprints if isinstance(sprint.get("judge_summary"), dict)]
    closeout_summaries = [sprint.get("closeout_summary", {}) for sprint in sprints if isinstance(sprint.get("closeout_summary"), dict)]
    signoff_summaries = [sprint.get("signoff_summary", {}) for sprint in sprints if isinstance(sprint.get("signoff_summary"), dict)]
    return sanitize_metadata(
        {
            "latest_sprint_id": latest.get("sprint_id"),
            "closed_sprint_count": len(closed),
            "resolved_task_count": sum(int(count.get("resolved") or 0) for count in counts),
            "open_task_count": sum(int(count.get("open") or 0) for count in counts),
            "conflict_count": sum(int(count.get("conflict_count") or 0) for count in counts),
            "recommendation_count": sum(int(item.get("open_recommendation_count") or 0) for item in recommendation_summaries),
            "context_recommendation_count": sum(int(item.get("context_recommendation_count") or 0) for item in recommendation_summaries),
            "next_action": (recommendation_summaries[0].get("next_action") if recommendation_summaries else None),
            "action_queue_count": sum(int(item.get("queue_count") or 0) for item in action_queue_summaries),
            "completed_action_count": sum(int(item.get("completed_action_count") or 0) for item in action_queue_summaries),
            "failed_action_count": sum(int(item.get("failed_action_count") or 0) for item in action_queue_summaries),
            "manual_required_action_count": sum(int(item.get("manual_required_count") or 0) for item in action_queue_summaries),
            "judged_task_count": sum(int(item.get("judged_task_count") or 0) for item in judge_summaries),
            "stale_judge_count": sum(int(item.get("stale_judge_count") or 0) for item in judge_summaries),
            "judge_provider_tokens": sum(int(item.get("judge_provider_tokens") or 0) for item in judge_summaries),
            "closeout_report_count": len([item for item in closeout_summaries if item]),
            "signed_sprint_count": len([item for item in signoff_summaries if item.get("status") == "signed"]),
            "forced_close_count": len([item for item in closeout_summaries if item.get("forced")]) + len([item for item in signoff_summaries if item.get("forced")]),
            "open_blocker_count": sum(int(item.get("blocker_count") or 0) for item in closeout_summaries if item.get("status") not in {"passed", "warning"}),
            "latest_closeout_status": (closeout_summaries[0].get("status") if closeout_summaries else None),
            "latest_closeout_readiness": (closeout_summaries[0].get("readiness") if closeout_summaries else None),
        }
    )


def _recommendation_summary_for_export(report: ImplementationDocument | None) -> ImplementationDocument:
    if not isinstance(report, dict) or not report:
        return {}
    actions = [item for item in report.get("recommended_actions", []) if isinstance(item, dict)]
    sprint_level = report.get("sprint_level_recommendation") if isinstance(report.get("sprint_level_recommendation"), dict) else {}
    top = actions[0] if actions else {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "created_at": report.get("created_at"),
            "recommended_order": [str(item) for item in report.get("recommended_order", []) if str(item).strip()][:20] if isinstance(report.get("recommended_order"), list) else [],
            "next_action": sprint_level.get("next_action"),
            "ready_to_close": bool(sprint_level.get("ready_to_close", False)),
            "open_recommendation_count": len([item for item in actions if item.get("action") not in {"no_action", "skip_archived"}]),
            "context_recommendation_count": int((report.get("source_summary") or {}).get("context_recommendation_count") or 0) if isinstance(report.get("source_summary"), dict) else 0,
            "top_recommendation": {
                "task_id": top.get("task_id"),
                "rank": top.get("rank"),
                "action": top.get("action"),
                "score": top.get("score"),
            },
        }
    )


def _judge_summary_for_export(summary: ImplementationDocument | None) -> ImplementationDocument:
    if not isinstance(summary, dict) or not summary:
        return {}
    return sanitize_metadata(
        {
            "schema_version": summary.get("schema_version"),
            "sprint_id": summary.get("sprint_id"),
            "created_at": summary.get("created_at"),
            "judged_task_count": summary.get("judged_task_count", 0),
            "stale_judge_count": summary.get("stale_judge_count", 0),
            "recommended_candidate_count": summary.get("recommended_candidate_count", 0),
            "judge_provider_tokens": summary.get("judge_provider_tokens", 0),
            "high_risk_candidate_count": summary.get("high_risk_candidate_count", 0),
            "risk_flags": summary.get("risk_flags") if isinstance(summary.get("risk_flags"), list) else [],
        }
    )


def _settings_from_dict(data: ImplementationDocument) -> ImplementationDocument:
    strategies = data.get("local_candidate_strategies")
    if isinstance(strategies, list):
        clean_strategies = [str(item).strip() for item in strategies if str(item).strip() in LOCAL_STRATEGIES]
    else:
        clean_strategies = ["balanced"]
    count = _clamp_int(data.get("provider_candidate_count"), 2, 5, 2)
    return sanitize_metadata(
        {
            "local_candidate_strategies": clean_strategies or ["balanced"],
            "provider_candidate_count": count,
            "provider_template_id": str(data.get("provider_template_id") or "provider-review-candidates")[:120],
            "generate_provider": bool(data.get("generate_provider", False)),
            "render_midi": bool(data.get("render_midi", True)),
            "stop_on_conflict": bool(data.get("stop_on_conflict", False)),
            "require_same_parent": bool(data.get("require_same_parent", True)),
        }
    )


def _task_ref_from_dict(data: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "task_id": validate_review_task_id(str(data.get("task_id") or "")),
            "order": max(1, int(data.get("order") or 1)),
            "priority": _clamp_int(data.get("priority"), 0, 100, 50),
            "lane": sanitize_sensitive_text(str(data.get("lane") or ""))[:80],
            "included": bool(data.get("included", True)),
            "notes": sanitize_sensitive_text(str(data.get("notes") or ""))[:500],
            "added_at": str(data.get("added_at") or ""),
        }
    )


def _task_ref(task: ReviewTask, order: int, *, lane: str, notes: str, now: str) -> ImplementationDocument:
    return _task_ref_from_dict({"task_id": task.task_id, "order": order, "priority": task.priority, "lane": lane, "included": True, "notes": notes, "added_at": now})


def _renumber_ref(ref: ImplementationDocument, order: int) -> ImplementationDocument:
    return _task_ref_from_dict({**ref, "order": order})


def _task_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        task_id = validate_review_task_id(str(item))
        if task_id in result:
            raise ReviewSprintError(f"Duplicate task id: {task_id}.")
        result.append(task_id)
    return result


def _read_project_tasks(task_store: ReviewTaskStore, project_id: str, task_ids: list[str]) -> list[ReviewTask]:
    tasks = []
    for task_id in task_ids:
        task = task_store.read_task(task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(task_id)
        tasks.append(task)
    return tasks


def _included_tasks(sprint: ReviewSprint, task_store: ReviewTaskStore, *, missing_ok: bool = False) -> list[ReviewTask]:
    tasks = []
    for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
        if not ref.get("included", True):
            continue
        try:
            task = task_store.read_task(str(ref.get("task_id") or ""))
        except FileNotFoundError:
            if missing_ok:
                continue
            raise
        if task.project_id == sprint.project_id:
            tasks.append(task)
    return tasks


def _summary_counts(tasks: list[ReviewTask], task_store: ReviewTaskStore) -> dict[str, int]:
    counts = {status: 0 for status in ("open", "candidate_ready", "applied", "resolved", "needs_more_work", "stale", "archived")}
    counts.update({"ready_candidate_count": 0, "local_candidate_count": 0, "provider_candidate_count": 0, "failed_candidate_count": 0, "conflict_count": 0, "blocking_conflict_count": 0})
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
        try:
            candidates = task_store.list_candidates(task.task_id)
        except FileNotFoundError:
            candidates = []
        counts["ready_candidate_count"] += len([candidate for candidate in candidates if candidate.status in {"ready", "applied"}])
        counts["local_candidate_count"] += len([candidate for candidate in candidates if candidate.candidate_type == "local_review_intents"])
        counts["provider_candidate_count"] += len([candidate for candidate in candidates if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")])
        counts["failed_candidate_count"] += len([candidate for candidate in candidates if candidate.status == "failed"])
    return counts


def _sprint_has_progress(tasks: list[ReviewTask], task_store: ReviewTaskStore) -> bool:
    return any(task.status != "open" or task_store.list_candidates(task.task_id) for task in tasks)


def _task_conflicts(sprint: ReviewSprint, task: ReviewTask, task_ids: set[str], task_store: ReviewTaskStore, parent_plan_hashes: dict[str, str]) -> list[ImplementationDocument]:
    conflicts: list[dict[str, Any]] = []
    if sprint.settings.get("require_same_parent", True) and sprint.parent_version_id and task.parent_version_id != sprint.parent_version_id:
        conflicts.append(_conflict("blocking", "parent_mismatch", [task.task_id], f"Task parent {task.parent_version_id} differs from sprint parent {sprint.parent_version_id}."))
    current_hash = parent_plan_hashes.get(task.parent_version_id)
    if task.status == "stale" or (current_hash and task.hashes.get("parent_plan_hash") and task.hashes.get("parent_plan_hash") != current_hash):
        conflicts.append(_conflict("blocking", "stale_task", [task.task_id], "ReviewTask is stale and must be refreshed outside the sprint."))
    if task.status == "archived":
        conflicts.append(_conflict("blocking", "archived_task", [task.task_id], "Archived ReviewTask cannot participate in sprint generation."))
    if task.status in {"applied", "resolved"}:
        conflicts.append(_conflict("info", f"task_{task.status}", [task.task_id], f"ReviewTask is already {task.status}."))
    if task.status == "needs_more_work" and task.follow_up_task_id and task.follow_up_task_id not in task_ids:
        conflicts.append(_conflict("warning", "missing_follow_up", [task.task_id], "Task needs more work but its follow-up task is not in this sprint."))
    candidates = task_store.list_candidates(task.task_id)
    if task.status == "candidate_ready":
        try:
            task_store.read_decision_report(task.task_id)
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            conflicts.append(_conflict("info", "missing_decision_report", [task.task_id], "Task has ready candidates but no Decision Report."))
    if candidates and not any(candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider") for candidate in candidates):
        conflicts.append(_conflict("info", "no_provider_candidates", [task.task_id], "Task only has local candidates."))
    return conflicts


def _pair_conflicts(left: ReviewTask, right: ReviewTask) -> list[ImplementationDocument]:
    if left.status not in {"open", "candidate_ready"} or right.status not in {"open", "candidate_ready"}:
        return []
    conflicts: list[dict[str, Any]] = []
    left_section = str(left.target.get("section_name") or "")
    right_section = str(right.target.get("section_name") or "")
    left_track = str(left.target.get("track_name") or "")
    right_track = str(right.target.get("track_name") or "")
    left_role = str(left.target.get("role") or "")
    right_role = str(right.target.get("role") or "")
    if left_section and left_section == right_section and left_track and left_track == right_track:
        conflicts.append(_conflict("warning", "same_section_track", [left.task_id, right.task_id], f"Two tasks target {left_section} / {left_track}. Apply one and refresh the other before continuing.", section_name=left_section, track_name=left_track))
    elif left_section and left_section == right_section:
        conflicts.append(_conflict("warning", "same_section", [left.task_id, right.task_id], f"Two tasks target section {left_section}.", section_name=left_section))
    if left_track and left_track == right_track and not (left_section and left_section == right_section):
        conflicts.append(_conflict("warning", "same_track", [left.task_id, right.task_id], f"Two tasks target track {left_track}.", track_name=left_track))
    if left_section and left_section == right_section and left_role and left_role == right_role:
        conflicts.append(_conflict("warning", "same_section_role", [left.task_id, right.task_id], f"Two tasks target {left_section} with role {left_role}.", section_name=left_section, role=left_role))
    left_beat = _float_or_none(left.target.get("global_marker_beat"))
    right_beat = _float_or_none(right.target.get("global_marker_beat"))
    if left_beat is not None and right_beat is not None and abs(left_beat - right_beat) < 4:
        conflicts.append(_conflict("warning", "nearby_markers", [left.task_id, right.task_id], "Two task markers are less than 4 beats apart.", marker_distance_beats=round(abs(left_beat - right_beat), 3)))
    return conflicts


def _conflict(severity: str, kind: str, task_ids: list[str], message: str, **extra: Any) -> ImplementationDocument:
    return sanitize_metadata({"severity": severity, "kind": kind, "task_ids": task_ids, "message": message, **extra})


def _with_conflict_id(conflict: ImplementationDocument, index: int) -> ImplementationDocument:
    return {"conflict_id": f"conflict-{index:03d}", **conflict}


def _ref_order(sprint: ReviewSprint, task_id: str) -> int:
    for ref in sprint.task_refs:
        if ref.get("task_id") == task_id:
            return int(ref.get("order") or 9999)
    return 9999


def _ensure_sprint_mutable(sprint: ReviewSprint) -> None:
    if sprint.status not in MUTABLE_SPRINT_STATUSES:
        raise ReviewSprintStateError(f"Cannot modify a {sprint.status} review sprint.")


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return sanitize_sensitive_text(str(value))[:160]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lock_for_project(project_dir: Path) -> threading.RLock:
    key = str(project_dir.resolve())
    with _LOCKS_GUARD:
        if key not in _STORE_LOCKS:
            _STORE_LOCKS[key] = threading.RLock()
        return _STORE_LOCKS[key]


def _append_event(root: Path, event_type: str, payload: ImplementationDocument, now: str) -> None:
    event_path = root / "events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"timestamp": now, "event": event_type, **sanitize_metadata(payload)}, ensure_ascii=False) + "\n")
