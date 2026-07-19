# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
from pathlib import Path as Path
from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, score_song_plan as score_song_plan
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, now_iso as now_iso
from song_agent.domains.creation.provider_usage import build_provider_usage_report as build_provider_usage_report
from song_agent.domains.studio.prompt_templates import PromptTemplateStore as PromptTemplateStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_judge import REVIEW_JUDGE_TEMPLATE_ID as REVIEW_JUDGE_TEMPLATE_ID, judge_report_summary as judge_report_summary, mark_judge_report_stale as mark_judge_report_stale, read_judge_report_with_stale as read_judge_report_with_stale
from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore as ReviewSprintActionQueueStore, SprintActionQueue as SprintActionQueue
from song_agent.domains.quality.review_sprint_closeout import closeout_report_summary as closeout_report_summary, signoff_summary as signoff_summary
from song_agent.domains.quality.review_sprints import ReviewSprint as ReviewSprint, ReviewSprintStore as ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate as ReviewCandidate, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan

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
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global candidate, item, row
    candidate = namespace.get('candidate', candidate)
    item = namespace.get('item', item)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


SPRINT_METRICS_SCHEMA_VERSION = 1
PROJECT_REVIEW_METRICS_SCHEMA_VERSION = 1
READINESS_VALUES = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}




def _task_source_summary(task: ReviewTask, candidates: list[ReviewCandidate], decision_report: DomainDocument) -> DomainDocument:
    return {
        "task_id": task.task_id,
        "status": task.status,
        "priority": task.priority,
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
                "score": candidate.scores.get("combined"),
            }
            for candidate in candidates
        ],
        "decision": {"recommended_candidate_id": decision_report.get("recommended_candidate_id")} if isinstance(decision_report, dict) else {},
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
                "report_hash": item.recommendation.get("report_hash"),
            }
            for item in queue.items
        ],
    }

def _version_source_summary(version: object) -> DomainDocument:
    return {
        "version_id": getattr(version, "version_id", None),
        "parent_version_id": getattr(version, "parent_version_id", None),
        "status": getattr(version, "status", None),
        "quality_score": getattr(version, "quality_score", None),
        "updated_at": getattr(version, "updated_at", None),
    }

def _provider_usage_public(report: DomainDocument) -> DomainDocument:
    return {
        "total_calls": report.get("total_calls", 0),
        "prompt_tokens": report.get("prompt_tokens", 0),
        "completion_tokens": report.get("completion_tokens", 0),
        "total_tokens": report.get("total_tokens", 0),
        "estimated_cost": report.get("estimated_cost"),
        "by_operation": [
            {
                "operation": row.get("operation"),
                "total_calls": row.get("total_calls"),
                "total_tokens": row.get("total_tokens"),
            }
            for row in report.get("by_operation", [])
            if isinstance(row, dict)
        ],
    }

def _provider_records_for_tasks(records: list[DomainDocument], task_ids: list[str]) -> list[DomainDocument]:
    task_id_set = set(task_ids)
    if not task_id_set:
        return []
    filtered = []
    for record in records:
        source_id = str(record.get("source_id") or "")
        group_id = str(record.get("group_id") or "")
        if source_id in task_id_set or group_id in task_id_set:
            filtered.append(record)
    return filtered
