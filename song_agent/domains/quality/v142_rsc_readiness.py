# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore as ReviewSprintActionQueueStore, SprintActionQueue as SprintActionQueue
from song_agent.domains.quality.review_sprints import ReviewSprint as ReviewSprint, ReviewSprintStore as ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate as ReviewCandidate, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore

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

candidate = _make_deferred_global('candidate')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
version = _make_deferred_global('version')

def bind_globals(namespace: dict[str, object]) -> None:
    global candidate, item, key, version
    candidate = namespace.get('candidate', candidate)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    version = namespace.get('version', version)
    _bind_deferred_defaults(namespace)


CLOSEOUT_SCHEMA_VERSION = 1
SIGNOFF_SCHEMA_VERSION = 1
CLOSEOUT_STATUSES = {"passed", "warning", "failed", "stale", "not_ready"}
CLOSEOUT_READINESS_VALUES = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}
OPEN_TASK_STATUSES = {"open", "candidate_ready", "needs_more_work"}
EXECUTABLE_ACTION_SAFETY = {"auto_safe", "provider_safe"}
PROVIDER_TOKEN_WARNING_THRESHOLD = 100_000




def _task_source_summary(task: ReviewTask, candidates: list[ReviewCandidate]) -> DomainDocument:
    return {
        "task_id": task.task_id,
        "status": task.status,
        "parent_version_id": task.parent_version_id,
        "selected_candidate_id": task.selected_candidate_id,
        "applied_version_id": task.applied_version_id,
        "follow_up_task_id": task.follow_up_task_id,
        "counts": task.counts,
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "candidate_type": candidate.candidate_type,
                "status": candidate.status,
                "rank": candidate.rank,
                "midi_status": candidate.midi_status,
                "audio_status": candidate.audio_status,
                "score": candidate.scores.get("combined"),
            }
            for candidate in candidates
        ],
    }

def _queue_source_summary(queue: SprintActionQueue) -> DomainDocument:
    return {
        "queue_id": queue.queue_id,
        "status": queue.status,
        "updated_at": queue.updated_at,
        "summary": queue.summary,
        "items": [
            {
                "item_id": item.item_id,
                "task_id": item.task_id,
                "action": item.action,
                "status": item.status,
                "safety": item.safety,
            }
            for item in queue.items
        ],
    }

def _conflict_source_summary(report: DomainDocument) -> DomainDocument:
    return {
        "schema_version": report.get("schema_version"),
        "sprint_id": report.get("sprint_id"),
        "conflicts": [
            {
                "severity": item.get("severity"),
                "kind": item.get("kind"),
                "task_ids": _as_list(item.get("task_ids")),
            }
            for item in report.get("conflicts", [])
            if isinstance(item, dict)
        ]
        if isinstance(report, dict)
        else [],
    }

def _recommendation_source_summary(report: DomainDocument) -> DomainDocument:
    if not isinstance(report, dict):
        return {}
    return {
        "schema_version": report.get("schema_version"),
        "sprint_id": report.get("sprint_id"),
        "created_at": report.get("created_at"),
        "stale": report.get("stale"),
        "status": report.get("status"),
        "recommended_order": _as_list(report.get("recommended_order")),
        "source_summary": _as_document(report.get("source_summary")),
    }

def _metrics_source_summary(report: DomainDocument) -> DomainDocument:
    if not isinstance(report, dict):
        return {}
    return {
        "schema_version": report.get("schema_version"),
        "sprint_id": report.get("sprint_id"),
        "source_hash": report.get("source_hash"),
        "risk_readiness": _as_document(report.get("risk_readiness")),
        "overview": _as_document(report.get("overview")),
        "candidate_funnel": _as_document(report.get("candidate_funnel")),
        "action_queue_execution": _as_document(report.get("action_queue_execution")),
        "quality_delta": _as_document(report.get("quality_delta")),
        "judge_metrics": _as_document(report.get("judge_metrics")),
        "provider_usage": _as_document(report.get("provider_usage")),
    }

def _judge_source_summary(summary: DomainDocument) -> DomainDocument:
    if not isinstance(summary, dict):
        return {}
    return {
        "schema_version": summary.get("schema_version"),
        "sprint_id": summary.get("sprint_id"),
        "source_hash": summary.get("source_hash"),
        "created_at": summary.get("created_at"),
        "judged_task_count": summary.get("judged_task_count"),
        "stale_judge_count": summary.get("stale_judge_count"),
        "recommended_candidate_count": summary.get("recommended_candidate_count"),
        "high_risk_candidate_count": summary.get("high_risk_candidate_count"),
        "judge_provider_tokens": summary.get("judge_provider_tokens"),
    }

def _project_source_summary(project_document: object) -> DomainDocument:
    state = getattr(project_document, "state", None)
    return {
        "selected_version_id": getattr(state, "selected_version_id", None),
        "final_version_id": getattr(state, "final_version_id", None),
        "latest_version_id": getattr(state, "latest_version_id", None),
        "versions": [
            {
                "version_id": getattr(version, "version_id", None),
                "status": getattr(version, "status", None),
                "quality_score": getattr(version, "quality_score", None),
                "updated_at": getattr(version, "updated_at", None),
            }
            for version in getattr(project_document, "versions", [])
        ],
    }

def _source_hash(source: DomainDocument) -> str:
    source_summary = {
        **{key: value for key, value in source.items() if key not in {"tasks", "candidates_by_task", "queues"}},
        "tasks": [_task_source_summary(task, source.get("candidates_by_task", {}).get(task.task_id, [])) for task in source.get("tasks", [])],
        "missing_task_ids": source.get("missing_task_ids", []),
        "queues": [_queue_source_summary(queue) for queue in source.get("queues", [])],
    }
    return _stable_hash(source_summary)

def _stable_hash(value: object) -> str:
    clean = sanitize_metadata(value)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _blocking_conflict_count(report: DomainDocument) -> int:
    conflicts = report.get("conflicts") if isinstance(report, dict) else []
    return len([item for item in _as_list(conflicts) if isinstance(item, dict) and item.get("severity") == "blocking"])

def _report_stale(report: DomainDocument) -> bool:
    return bool(isinstance(report, dict) and (report.get("stale") or report.get("status") == "stale"))

def _quality_not_improved(metrics_summary: DomainDocument) -> bool:
    if metrics_summary.get("quality_delta") is None:
        return False
    try:
        return int(metrics_summary.get("quality_delta") or 0) <= 0
    except (TypeError, ValueError):
        return False

def _has_applied_or_selected_version(task_summary: DomainDocument, project_document: object, recommended_final_version: DomainDocument) -> bool:
    if task_summary.get("applied_version_ids"):
        return True
    if recommended_final_version.get("version_id"):
        return True
    state = getattr(project_document, "state", None)
    return bool(getattr(state, "selected_version_id", None) or getattr(state, "final_version_id", None))

def _optional_str(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    return sanitize_sensitive_text(str(value).strip())[:160]
