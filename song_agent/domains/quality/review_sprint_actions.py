from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
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
from song_agent.domains.quality.review_sprints import ReviewSprint
from song_agent.domains.quality.review_tasks import validate_review_task_id


ACTION_QUEUE_SCHEMA_VERSION = 1
ACTION_QUEUE_ID_PATTERN = re.compile(r"^queue-[0-9]{3,6}$")
ACTION_ITEM_ID_PATTERN = re.compile(r"^item-[0-9]{3,6}$")
ACTION_QUEUE_STATUSES = {"pending", "running", "completed", "completed_with_warnings", "failed", "blocked", "archived"}
ACTION_ITEM_STATUSES = {"pending", "running", "completed", "failed", "skipped", "blocked", "manual_required", "interrupted"}
ACTION_SAFETY = {"auto_safe", "provider_safe", "manual_required", "blocked", "informational"}
ACTION_TYPES = {
    "refresh_recommendations",
    "refresh_conflicts",
    "save_recommended_context_pack",
    "generate_local_candidates",
    "generate_provider_candidates",
    "refresh_judge_report",
    "refresh_decision_report",
    "inspect_conflict",
    "manual_apply_candidate",
    "manual_resolve_task",
    "manual_add_follow_up",
    "skip_stale_task",
    "skip_archived_task",
    "no_action",
}
RECOMMENDATION_ACTION_MAP = {
    "inspect_conflict": "inspect_conflict",
    "generate_local": "generate_local_candidates",
    "generate_provider": "generate_provider_candidates",
    "refresh_decision_report": "refresh_decision_report",
    "apply_ready_candidate": "manual_apply_candidate",
    "resolve": "manual_resolve_task",
    "add_follow_up": "manual_add_follow_up",
    "skip_stale": "skip_stale_task",
    "skip_archived": "skip_archived_task",
    "no_action": "no_action",
}
_LOCKS_GUARD = threading.RLock()
_QUEUE_STORE_LOCKS: dict[str, threading.RLock] = {}


class SprintActionQueueError(ValueError):
    pass


@dataclass(frozen=True)
class SprintActionItem:
    item_id: str
    task_id: str | None
    action: str
    status: str
    safety: str
    rank: int
    priority: int
    reason: str = ""
    recommendation: dict[str, Any] = field(default_factory=dict)
    input: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    attempt: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SprintActionItem":
        if not isinstance(data, dict):
            raise SprintActionQueueError("action item must be an object.")
        item_id = str(data.get("item_id") or "")
        if item_id:
            validate_action_item_id(item_id)
        task_id = _optional_task_id(data.get("task_id"))
        action = str(data.get("action") or "")
        if action not in ACTION_TYPES:
            raise SprintActionQueueError(f"action must be one of: {', '.join(sorted(ACTION_TYPES))}.")
        status = str(data.get("status") or "pending")
        if status not in ACTION_ITEM_STATUSES:
            raise SprintActionQueueError(f"item status must be one of: {', '.join(sorted(ACTION_ITEM_STATUSES))}.")
        safety = str(data.get("safety") or action_safety(action))
        if safety not in ACTION_SAFETY:
            raise SprintActionQueueError(f"safety must be one of: {', '.join(sorted(ACTION_SAFETY))}.")
        return cls(
            item_id=item_id,
            task_id=task_id,
            action=action,
            status=status,
            safety=safety,
            rank=max(0, int(data.get("rank") or 0)),
            priority=_clamp_int(data.get("priority"), 0, 100, 0),
            reason=sanitize_sensitive_text(str(data.get("reason") or ""))[:1000],
            recommendation=sanitize_metadata(dict(data.get("recommendation") or {})) if isinstance(data.get("recommendation"), dict) else {},
            input=sanitize_metadata(dict(data.get("input") or {})) if isinstance(data.get("input"), dict) else {},
            result=sanitize_metadata(dict(data.get("result") or {})) if isinstance(data.get("result"), dict) else {},
            error=None if data.get("error") is None else sanitize_sensitive_text(str(data.get("error") or ""))[:1000],
            started_at=_optional_str(data.get("started_at")),
            completed_at=_optional_str(data.get("completed_at")),
            attempt=max(0, int(data.get("attempt") or 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SprintActionQueue:
    schema_version: int
    queue_id: str
    project_id: str
    sprint_id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    created_from: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    items: list[SprintActionItem] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    archived_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SprintActionQueue":
        if not isinstance(data, dict):
            raise SprintActionQueueError("action queue must be an object.")
        queue_id = str(data.get("queue_id") or "")
        if queue_id:
            validate_action_queue_id(queue_id)
        status = str(data.get("status") or "pending")
        if status not in ACTION_QUEUE_STATUSES:
            raise SprintActionQueueError(f"queue status must be one of: {', '.join(sorted(ACTION_QUEUE_STATUSES))}.")
        items = [SprintActionItem.from_dict(item) for item in data.get("items", []) if isinstance(item, dict)]
        return cls(
            schema_version=int(data.get("schema_version", ACTION_QUEUE_SCHEMA_VERSION) or ACTION_QUEUE_SCHEMA_VERSION),
            queue_id=queue_id,
            project_id=str(data.get("project_id") or ""),
            sprint_id=str(data.get("sprint_id") or ""),
            name=sanitize_sensitive_text(str(data.get("name") or "Action Queue"))[:160],
            status=status,
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            created_from=sanitize_metadata(dict(data.get("created_from") or {})) if isinstance(data.get("created_from"), dict) else {},
            settings=_queue_settings(data.get("settings") if isinstance(data.get("settings"), dict) else {}),
            items=items,
            summary=_queue_summary(items),
            archived_at=_optional_str(data.get("archived_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        data["summary"] = _queue_summary(self.items)
        return data


class ReviewSprintActionQueueStore:
    def __init__(self, sprint_dir: Path | str):
        self.sprint_dir = Path(sprint_dir).resolve()
        self.root = self.sprint_dir / "action-queues"
        self.lock = _lock_for_root(self.root)

    def create_queue(self, queue: SprintActionQueue, *, now: str | None = None) -> SprintActionQueue:
        now = now or now_iso()
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            queue_id, queue_dir = self._reserve_queue_dir()
            items = [_with_item_id(item, f"item-{index:03d}") for index, item in enumerate(queue.items, start=1)]
            created = SprintActionQueue.from_dict(
                {
                    **queue.to_dict(),
                    "schema_version": ACTION_QUEUE_SCHEMA_VERSION,
                    "queue_id": queue_id,
                    "created_at": now,
                    "updated_at": now,
                    "items": [item.to_dict() for item in items],
                    "status": _queue_status(items, requested=queue.status),
                }
            )
            try:
                write_json(queue_dir / "queue.json", created.to_dict())
                self.append_event(queue_id, "queue_created", {"item_count": len(items)}, now=now)
            except Exception:
                if queue_dir.exists() and not (queue_dir / "queue.json").exists():
                    shutil.rmtree(queue_dir)
                raise
            return created

    def read_queue(self, queue_id: str) -> SprintActionQueue:
        path = self.queue_dir(queue_id) / "queue.json"
        if not path.exists():
            raise FileNotFoundError(queue_id)
        return SprintActionQueue.from_dict(read_json(path))

    def list_queues(self, *, include_archived: bool = False) -> list[SprintActionQueue]:
        if not self.root.exists():
            return []
        queues = []
        for path in self.root.glob("queue-*/queue.json"):
            try:
                queue = SprintActionQueue.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if queue.status == "archived" and not include_archived:
                continue
            queues.append(queue)
        return sorted(queues, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def update_queue(self, queue: SprintActionQueue, *, event: str | None = None, payload: dict[str, Any] | None = None, now: str | None = None) -> SprintActionQueue:
        now = now or now_iso()
        updated = SprintActionQueue.from_dict({**queue.to_dict(), "updated_at": now, "status": _queue_status(queue.items, requested=queue.status)})
        with self.lock:
            write_json(self.queue_dir(updated.queue_id) / "queue.json", updated.to_dict())
            if event:
                self.append_event(updated.queue_id, event, payload or {}, now=now)
        return updated

    def archive_queue(self, queue_id: str, *, now: str | None = None) -> SprintActionQueue:
        now = now or now_iso()
        queue = self.read_queue(queue_id)
        archived = SprintActionQueue.from_dict({**queue.to_dict(), "status": "archived", "updated_at": now, "archived_at": now})
        with self.lock:
            write_json(self.queue_dir(archived.queue_id) / "queue.json", archived.to_dict())
            self.append_event(archived.queue_id, "queue_archived", {}, now=now)
        return archived

    def append_event(self, queue_id: str, event: str, payload: dict[str, Any], *, now: str | None = None) -> None:
        queue_id = validate_action_queue_id(queue_id)
        event_data = {
            "timestamp": now or now_iso(),
            "event": sanitize_sensitive_text(str(event or ""))[:120],
            "payload": sanitize_metadata(payload if isinstance(payload, dict) else {}),
        }
        queue_dir = self.queue_dir(queue_id)
        queue_dir.mkdir(parents=True, exist_ok=True)
        with (queue_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event_data, ensure_ascii=False) + "\n")

    def read_events(self, queue_id: str) -> list[dict[str, Any]]:
        path = self.queue_dir(queue_id) / "events.jsonl"
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(sanitize_metadata(json.loads(line)))
            except json.JSONDecodeError:
                continue
        return events

    def queue_dir(self, queue_id: str) -> Path:
        queue_id = validate_action_queue_id(queue_id)
        base = self.root.resolve()
        target = (base / queue_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside review sprint action queues.") from exc
        return target

    def _reserve_queue_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            queue_id = f"queue-{index:03d}"
            queue_dir = self.queue_dir(queue_id)
            try:
                queue_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return queue_id, queue_dir
        raise RuntimeError("Could not allocate action queue id.")


def build_action_queue_from_recommendation_report(
    *,
    project_id: str,
    sprint: ReviewSprint,
    recommendation_report: dict[str, Any],
    name: str | None = None,
    settings: dict[str, Any] | None = None,
    now: str | None = None,
) -> SprintActionQueue:
    now = now or now_iso()
    clean_settings = _queue_settings(settings or {})
    report_hash = recommendation_report_hash(recommendation_report)
    report_created_at = _optional_str(recommendation_report.get("created_at"))
    recommended_order = [str(item) for item in recommendation_report.get("recommended_order", []) if str(item).strip()] if isinstance(recommendation_report.get("recommended_order"), list) else []
    items: list[SprintActionItem] = []
    for action in _recommendation_actions(recommendation_report):
        queue_action = RECOMMENDATION_ACTION_MAP.get(str(action.get("action") or ""), "no_action")
        items.append(_queue_item_from_recommendation(action, queue_action, report_hash, report_created_at, sprint))
        if clean_settings.get("include_judge_actions", True) and queue_action in {"manual_apply_candidate", "refresh_decision_report"}:
            candidate_summary = action.get("candidate_summary") if isinstance(action.get("candidate_summary"), dict) else {}
            if int(candidate_summary.get("ready_candidate_count") or 0) > 0:
                items.append(_queue_item_from_recommendation(action, "refresh_judge_report", report_hash, report_created_at, sprint))
        preview = action.get("context_pack_preview") if isinstance(action.get("context_pack_preview"), dict) else {}
        if clean_settings.get("run_context_pack_actions", True) and _context_ref_count(preview) > 0:
            items.append(_context_pack_queue_item(action, report_hash, report_created_at, preview))
    queue = SprintActionQueue.from_dict(
        {
            "schema_version": ACTION_QUEUE_SCHEMA_VERSION,
            "queue_id": "",
            "project_id": project_id,
            "sprint_id": sprint.sprint_id,
            "name": name or f"Recommendation Queue {now[:10]}",
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "created_from": {
                "source_type": "review_sprint_recommendation",
                "recommendation_report_created_at": recommendation_report.get("created_at"),
                "recommendation_report_hash": report_hash,
                "recommended_order": recommended_order,
            },
            "settings": clean_settings,
            "items": [item.to_dict() for item in sorted(items, key=_item_sort_key)],
        }
    )
    return SprintActionQueue.from_dict({**queue.to_dict(), "status": _queue_status(queue.items, requested="pending")})


def recommendation_report_hash(report: dict[str, Any]) -> str:
    clean = sanitize_metadata(report if isinstance(report, dict) else {})
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def action_queue_summary(queue: SprintActionQueue | dict[str, Any] | None) -> dict[str, Any]:
    if queue is None:
        return {}
    if isinstance(queue, dict):
        queue = SprintActionQueue.from_dict(queue)
    return sanitize_metadata(
        {
            "queue_id": queue.queue_id,
            "status": queue.status,
            "created_at": queue.created_at,
            "updated_at": queue.updated_at,
            "summary": queue.summary,
            "completed_action_count": int(queue.summary.get("completed") or 0),
            "failed_action_count": int(queue.summary.get("failed") or 0),
            "manual_required_count": int(queue.summary.get("manual_required") or 0),
            "blocked_action_count": int(queue.summary.get("blocked") or 0),
        }
    )


def action_queue_export_summary(queues: list[SprintActionQueue | dict[str, Any]]) -> dict[str, Any]:
    if not queues:
        return {}
    clean_queues = [queue if isinstance(queue, SprintActionQueue) else SprintActionQueue.from_dict(queue) for queue in queues]
    latest = sorted(clean_queues, key=lambda item: item.updated_at or item.created_at, reverse=True)[0]
    return sanitize_metadata(
        {
            "latest_queue_id": latest.queue_id,
            "queue_count": len(clean_queues),
            "completed_action_count": sum(int(queue.summary.get("completed") or 0) for queue in clean_queues),
            "failed_action_count": sum(int(queue.summary.get("failed") or 0) for queue in clean_queues),
            "manual_required_count": sum(int(queue.summary.get("manual_required") or 0) for queue in clean_queues),
            "blocked_action_count": sum(int(queue.summary.get("blocked") or 0) for queue in clean_queues),
            "latest_status": latest.status,
        }
    )


def action_queue_collection_summary(queues: list[SprintActionQueue | dict[str, Any]]) -> dict[str, Any]:
    return action_queue_export_summary(queues)


def queue_report_is_stale(queue: SprintActionQueue | dict[str, Any], recommendation_report: dict[str, Any]) -> bool:
    if isinstance(queue, dict):
        queue = SprintActionQueue.from_dict(queue)
    expected = str((queue.created_from or {}).get("recommendation_report_hash") or "")
    return bool(expected and expected != recommendation_report_hash(recommendation_report))


def validate_action_queue_id(queue_id: str) -> str:
    if not ACTION_QUEUE_ID_PATTERN.match(str(queue_id or "")):
        raise ValueError("Invalid action queue id.")
    return str(queue_id)


def validate_action_item_id(item_id: str) -> str:
    if not ACTION_ITEM_ID_PATTERN.match(str(item_id or "")):
        raise ValueError("Invalid action item id.")
    return str(item_id)


def action_safety(action: str) -> str:
    if action in {"generate_provider_candidates", "refresh_judge_report"}:
        return "provider_safe"
    if action in {"manual_apply_candidate", "manual_resolve_task", "manual_add_follow_up"}:
        return "manual_required"
    if action in {"skip_stale_task", "skip_archived_task"}:
        return "blocked"
    if action in {"inspect_conflict", "no_action"}:
        return "informational"
    return "auto_safe"


def default_item_status(action: str, safety: str) -> str:
    if safety == "manual_required" or safety == "informational":
        return "manual_required" if action != "no_action" else "skipped"
    if safety == "blocked":
        return "blocked"
    return "pending"


def _queue_item_from_recommendation(action: ImplementationDocument, queue_action: str, report_hash: str, report_created_at: str | None, sprint: ReviewSprint) -> SprintActionItem:
    safety = action_safety(queue_action)
    recommendation = _recommendation_snapshot(action, report_hash, report_created_at)
    return SprintActionItem.from_dict(
        {
            "item_id": "",
            "task_id": action.get("task_id"),
            "action": queue_action,
            "status": default_item_status(queue_action, safety),
            "safety": safety,
            "rank": action.get("rank") or 0,
            "priority": action.get("priority") or 0,
            "reason": action.get("reason") or "",
            "recommendation": recommendation,
            "input": _input_for_action(queue_action, action, sprint),
            "result": _manual_result(queue_action, action) if safety in {"manual_required", "informational", "blocked"} else {},
        }
    )


def _context_pack_queue_item(action: ImplementationDocument, report_hash: str, report_created_at: str | None, preview: ImplementationDocument) -> SprintActionItem:
    recommendation = _recommendation_snapshot(action, report_hash, report_created_at)
    return SprintActionItem.from_dict(
        {
            "item_id": "",
            "task_id": action.get("task_id"),
            "action": "save_recommended_context_pack",
            "status": "pending",
            "safety": "auto_safe",
            "rank": action.get("rank") or 0,
            "priority": action.get("priority") or 0,
            "reason": "Save the recommended Context Pack preview for this ReviewTask.",
            "recommendation": recommendation,
            "input": {
                "name": f"Recommendation Context {action.get('task_id') or ''}".strip(),
                "context_pack_preview": {
                    "query": preview.get("query") if isinstance(preview.get("query"), dict) else {},
                    "asset_refs": preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else [],
                    "reference_refs": preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else [],
                },
            },
        }
    )


def _recommendation_snapshot(action: ImplementationDocument, report_hash: str, report_created_at: str | None) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "report_created_at": report_created_at,
            "report_hash": report_hash,
            "action": action.get("action"),
            "score": action.get("score"),
            "score_breakdown": action.get("score_breakdown") if isinstance(action.get("score_breakdown"), dict) else {},
            "recommended_candidate_id": (action.get("candidate_summary") or {}).get("recommended_candidate_id") if isinstance(action.get("candidate_summary"), dict) else None,
        }
    )


def _input_for_action(queue_action: str, action: ImplementationDocument, sprint: ReviewSprint | None = None) -> ImplementationDocument:
    if queue_action == "generate_local_candidates":
        strategies = (sprint.settings or {}).get("local_candidate_strategies") if sprint is not None else None
        if not isinstance(strategies, list) or not strategies:
            strategies = ["balanced"]
        return {"strategies": [str(item) for item in strategies], "render_midi": True, "skip_existing_ready": True}
    if queue_action == "generate_provider_candidates":
        count = int((sprint.settings or {}).get("provider_candidate_count") or 2) if sprint is not None else 2
        template_id = str((sprint.settings or {}).get("provider_template_id") or "provider-review-candidates") if sprint is not None else "provider-review-candidates"
        return {"candidate_count": max(1, min(5, count)), "template_id": template_id, "render_midi": True, "skip_existing_provider": True, "include_local_context": True}
    if queue_action == "refresh_judge_report":
        template_id = str((sprint.settings or {}).get("judge_template_id") or "provider-review-judge") if sprint is not None else "provider-review-judge"
        return {"template_id": template_id, "note": "review sprint action queue"}
    if queue_action == "refresh_decision_report":
        return {"note": "review sprint action queue"}
    if queue_action == "manual_apply_candidate":
        return {"candidate_id": (action.get("candidate_summary") or {}).get("recommended_candidate_id") if isinstance(action.get("candidate_summary"), dict) else None}
    return {}


def _manual_result(queue_action: str, action: ImplementationDocument) -> ImplementationDocument:
    if queue_action == "manual_apply_candidate":
        return {"message": "Apply must be performed from the ReviewTask candidate apply endpoint.", "candidate_id": _input_for_action(queue_action, action).get("candidate_id")}
    if queue_action == "manual_resolve_task":
        return {"message": "Resolve must be confirmed manually from the ReviewTask endpoint."}
    if queue_action == "manual_add_follow_up":
        return {"message": "Follow-up task creation or sprint addition requires manual confirmation."}
    if queue_action == "inspect_conflict":
        return {"message": "Inspect the sprint conflict report before running candidate actions.", "conflict_count": len(action.get("conflicts") or []) if isinstance(action.get("conflicts"), list) else 0}
    if queue_action in {"skip_stale_task", "skip_archived_task"}:
        return {"message": "Task cannot be executed from this queue in its current state."}
    return {}


def _recommendation_actions(report: ImplementationDocument) -> list[ImplementationDocument]:
    actions = [item for item in report.get("recommended_actions", []) if isinstance(item, dict)] if isinstance(report, dict) else []
    return sorted(actions, key=lambda item: (int(item.get("rank") or 9999), int(item.get("sprint_order") or 9999), str(item.get("task_id") or "")))


def _queue_settings(data: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "stop_on_failure": bool(data.get("stop_on_failure", False)),
            "run_provider_actions": bool(data.get("run_provider_actions", False)),
            "run_context_pack_actions": bool(data.get("run_context_pack_actions", True)),
            "run_local_actions": bool(data.get("run_local_actions", True)),
            "include_judge_actions": bool(data.get("include_judge_actions", True)),
            "max_provider_actions": _clamp_int(data.get("max_provider_actions"), 0, 20, 3),
            "max_concurrency": 1,
        }
    )


def _queue_summary(items: list[SprintActionItem]) -> dict[str, int]:
    summary = {status: 0 for status in ACTION_ITEM_STATUSES}
    for item in items:
        summary[item.status] = summary.get(item.status, 0) + 1
    summary["total"] = len(items)
    return {key: int(value) for key, value in summary.items()}


def _queue_status(items: list[SprintActionItem], *, requested: str = "pending") -> str:
    if requested == "archived":
        return "archived"
    if any(item.status == "running" for item in items):
        return "running"
    if any(item.status == "failed" for item in items):
        return "failed"
    executable = [item for item in items if item.safety in {"auto_safe", "provider_safe"}]
    if executable and all(item.status in {"completed", "skipped", "blocked"} for item in executable):
        return "completed_with_warnings" if any(item.status in {"blocked", "manual_required"} for item in items) else "completed"
    if all(item.status in {"blocked", "manual_required", "skipped"} for item in items):
        return "blocked" if any(item.status == "blocked" for item in items) else "completed_with_warnings"
    return requested if requested in ACTION_QUEUE_STATUSES else "pending"


def _with_item_id(item: SprintActionItem, item_id: str) -> SprintActionItem:
    return SprintActionItem.from_dict({**item.to_dict(), "item_id": item_id})


def _item_sort_key(item: SprintActionItem) -> tuple[int, int, int, str]:
    action_order = {
        "refresh_conflicts": 0,
        "refresh_recommendations": 1,
        "save_recommended_context_pack": 2,
        "generate_local_candidates": 3,
        "generate_provider_candidates": 4,
        "refresh_judge_report": 5,
        "refresh_decision_report": 6,
    }.get(item.action, 9)
    return (action_order, item.rank or 9999, -int(item.priority or 0), item.task_id or item.action)


def _context_ref_count(preview: Any) -> int:
    if not isinstance(preview, dict):
        return 0
    return len(preview.get("asset_refs") or []) + len(preview.get("reference_refs") or [])


def _optional_task_id(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return validate_review_task_id(str(value))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(high, parsed))


def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        lock = _QUEUE_STORE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _QUEUE_STORE_LOCKS[key] = lock
        return lock
