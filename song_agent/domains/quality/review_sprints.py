# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore, validate_review_task_id as validate_review_task_id


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
    task_refs: list[ImplementationDocument] = field(default_factory=list)
    settings: ImplementationDocument = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    selected_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    closed_at: str | None = None

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ReviewSprint":
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
            settings=_settings_from_dict(_as_document(data.get("settings"))),
            counts={str(key): _safe_int(value) for key, value in dict(data.get("counts") or {}).items()},
            selected_task_id=None if not data.get("selected_task_id") else validate_review_task_id(str(data.get("selected_task_id"))),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            closed_at=_optional_str(data.get("closed_at")),
        )

    def to_dict(self) -> DomainDocument:
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
        payload: DomainDocument | None = None,
        now: str | None = None,
    ) -> ReviewSprint:
        payload = _as_document(payload)
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
                    "settings": _as_document(payload.get("settings")),
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

    def update_sprint(self, sprint: ReviewSprint, *, event: str | None = None, payload: DomainDocument | None = None, now: str | None = None) -> ReviewSprint:
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
    ) -> DomainDocument:
        now = now or now_iso()
        tasks = _included_tasks(sprint, task_store, missing_ok=True)
        task_ids = {task.task_id for task in tasks}
        conflicts: list[ImplementationDocument] = []
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

    def read_summary(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.sprint_dir(sprint_id) / "summary.json"
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def read_conflict_report(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.sprint_dir(sprint_id) / "conflict-report.json"
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def recommendation_report_path(self, sprint_id: str) -> Path:
        return self.sprint_dir(sprint_id) / "recommendation-report.json"

    def read_recommendation_report(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.recommendation_report_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def write_recommendation_report(self, sprint: ReviewSprint, report: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        clean_report = sanitize_metadata({**(_as_document(report)), "schema_version": REVIEW_SPRINT_RECOMMENDATION_SCHEMA_VERSION})
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

    def read_judge_summary(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.judge_summary_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def write_judge_summary(self, sprint: ReviewSprint, summary: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        clean_summary = sanitize_metadata(_as_document(summary))
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

    def read_closeout_report(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.closeout_report_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def write_closeout_report(self, sprint: ReviewSprint, report: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        clean_report = sanitize_metadata(_as_document(report))
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

    def read_signoff(self, sprint_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.signoff_path(sprint_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(sprint_id)
        data = read_json(path)
        return sanitize_metadata(_as_document(data))

    def write_signoff(self, sprint: ReviewSprint, record: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        clean_record = sanitize_metadata(_as_document(record))
        with self.lock:
            write_json(self.signoff_path(sprint.sprint_id), clean_record)
            _append_event(
                self.sprint_dir(sprint.sprint_id),
                "review_sprint_signoff_written",
                {"forced": bool(clean_record.get("forced", False)), "closeout_status": clean_record.get("closeout_status"), "selected_version_id": clean_record.get("selected_version_id")},
                now,
            )
        return clean_record

    def read_events(self, sprint_id: str) -> list[DomainDocument]:
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

    def append_event(self, sprint_id: str, event: str, payload: DomainDocument | None = None, *, now: str | None = None) -> None:
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


from song_agent.domains.quality import v142_rs_readiness as _v142_rs_readiness
from song_agent.domains.quality.v142_rs_readiness import (
    review_sprint_export_summary,
    review_sprint_project_rollup,
    _recommendation_summary_for_export,
    _judge_summary_for_export,
    _settings_from_dict,
    _task_ref_from_dict,
    _task_ref,
    _renumber_ref,
    _task_ids,
    _read_project_tasks,
    _included_tasks,
    _summary_counts,
    _sprint_has_progress,
    _task_conflicts,
    _pair_conflicts,
    _conflict,
    _with_conflict_id,
    _ref_order,
    _ensure_sprint_mutable,
    _optional_str,
    _safe_int,
    _clamp_int,
    _float_or_none,
    _lock_for_project,
    _append_event,
)

_v142_rs_readiness.bind_globals(globals())
