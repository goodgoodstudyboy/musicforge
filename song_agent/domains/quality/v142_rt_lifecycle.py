# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field, replace as replace
from pathlib import Path as Path
from song_agent.domains.quality.candidate_scoring import score_provider_edit_candidate as score_provider_edit_candidate
from song_agent.domains.creation.edits import EditIntent as EditIntent, EditedSongPlanResult as EditedSongPlanResult, apply_edit_intent as apply_edit_intent, validate_edit_intent as validate_edit_intent
from song_agent.domains.studio.editor_audition import EditorAuditionManifest as EditorAuditionManifest
from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig
from song_agent.domains.creation.provider_edits import ProviderEditPatch as ProviderEditPatch, apply_provider_edit_patch as apply_provider_edit_patch, generate_provider_edit_candidates as generate_provider_edit_candidates, provider_patch_to_intents as provider_patch_to_intents
from song_agent.domains.studio.prompt_templates import PromptTemplate as PromptTemplate
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.quality.review_edits import build_review_edit as build_review_edit
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan
from song_agent.domains.studio.song_editor import song_plan_hash as song_plan_hash

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

CANDIDATE_ID_PATTERN = _make_deferred_global('CANDIDATE_ID_PATTERN')
ReviewCandidate = _make_deferred_global('ReviewCandidate')
ReviewTask = _make_deferred_global('ReviewTask')
ReviewTaskError = _make_deferred_global('ReviewTaskError')
ReviewTaskStateError = _make_deferred_global('ReviewTaskStateError')
TASK_ID_PATTERN = _make_deferred_global('TASK_ID_PATTERN')
_clamp = _make_deferred_global('_clamp')
_float_or_none = _make_deferred_global('_float_or_none')
_has_any = _make_deferred_global('_has_any')
_intent = _make_deferred_global('_intent')
_range_start = _make_deferred_global('_range_start')
_review_text = _make_deferred_global('_review_text')
_role_for_track = _make_deferred_global('_role_for_track')
_role_from_text = _make_deferred_global('_role_from_text')
_section_end = _make_deferred_global('_section_end')
_section_from_range_or_marker = _make_deferred_global('_section_from_range_or_marker')
_section_start = _make_deferred_global('_section_start')
_target_track = _make_deferred_global('_target_track')
_track_id = _make_deferred_global('_track_id')
item = _make_deferred_global('item')
operation = _make_deferred_global('operation')
review_decision_summary = _make_deferred_global('review_decision_summary')
tag = _make_deferred_global('tag')

def bind_globals(namespace: dict[str, object]) -> None:
    global CANDIDATE_ID_PATTERN, ReviewCandidate, ReviewTask, ReviewTaskError, ReviewTaskStateError, TASK_ID_PATTERN, _clamp, _float_or_none
    global _has_any, _intent, _range_start, _review_text, _role_for_track, _role_from_text, _section_end
    global _section_from_range_or_marker, _section_start, _target_track, _track_id, item, operation, review_decision_summary, tag
    CANDIDATE_ID_PATTERN = namespace.get('CANDIDATE_ID_PATTERN', CANDIDATE_ID_PATTERN)
    ReviewCandidate = namespace.get('ReviewCandidate', ReviewCandidate)
    ReviewTask = namespace.get('ReviewTask', ReviewTask)
    ReviewTaskError = namespace.get('ReviewTaskError', ReviewTaskError)
    ReviewTaskStateError = namespace.get('ReviewTaskStateError', ReviewTaskStateError)
    TASK_ID_PATTERN = namespace.get('TASK_ID_PATTERN', TASK_ID_PATTERN)
    _clamp = namespace.get('_clamp', _clamp)
    _float_or_none = namespace.get('_float_or_none', _float_or_none)
    _has_any = namespace.get('_has_any', _has_any)
    _intent = namespace.get('_intent', _intent)
    _range_start = namespace.get('_range_start', _range_start)
    _review_text = namespace.get('_review_text', _review_text)
    _role_for_track = namespace.get('_role_for_track', _role_for_track)
    _role_from_text = namespace.get('_role_from_text', _role_from_text)
    _section_end = namespace.get('_section_end', _section_end)
    _section_from_range_or_marker = namespace.get('_section_from_range_or_marker', _section_from_range_or_marker)
    _section_start = namespace.get('_section_start', _section_start)
    _target_track = namespace.get('_target_track', _target_track)
    _track_id = namespace.get('_track_id', _track_id)
    item = namespace.get('item', item)
    operation = namespace.get('operation', operation)
    review_decision_summary = namespace.get('review_decision_summary', review_decision_summary)
    tag = namespace.get('tag', tag)
    _bind_deferred_defaults(namespace)


REVIEW_TASK_SCHEMA_VERSION = 1
REVIEW_CANDIDATE_SCHEMA_VERSION = 1
REVIEW_DECISION_REPORT_SCHEMA_VERSION = 1
TASK_STATUSES = {"open", "candidate_ready", "applied", "resolved", "needs_more_work", "archived", "stale"}
CANDIDATE_STATUSES = {"queued", "ready", "failed", "applied", "stale", "deleted"}
STRATEGIES = ("conservative", "balanced", "bold")
PROVIDER_STRATEGY = "provider"
TERMINAL_TASK_STATUSES = {"resolved", "archived", "stale", "needs_more_work"}
FIX_MARKERS = {"fix", "issue", "drop"}
PRESERVE_MARKERS = {"keep", "hook"}
_STORE_LOCKS: dict[str, threading.RLock] = {}




def _judge_summary_for_decision(report: DomainDocument | None) -> DomainDocument:
    if not isinstance(report, dict) or not report:
        return {}
    scores = _as_list(report.get("candidate_scores"))
    recommended_id = report.get("recommended_candidate_id")
    top = next((score for score in scores if isinstance(score, dict) and score.get("candidate_id") == recommended_id), {})
    if not isinstance(top, dict):
        top = {}
    return sanitize_metadata(
        {
            "status": report.get("status") or "not_started",
            "stale": bool(report.get("stale", False)),
            "created_at": report.get("created_at"),
            "recommended_candidate_id": recommended_id,
            "top_overall": top.get("overall"),
            "top_confidence": top.get("confidence"),
            "top_risk": top.get("risk"),
            "manual_review_required": bool(report.get("manual_review_required", True)),
            "risk_flags": _as_list(report.get("risk_flags")),
        }
    )

def _provider_patch_summary(patch: DomainDocument) -> DomainDocument:
    operations = _as_list(patch.get("operations"))
    return sanitize_metadata(
        {
            "schema_version": patch.get("schema_version"),
            "summary": patch.get("summary"),
            "operation_count": len(operations),
            "operations": [
                {
                    "op": operation.get("op"),
                    "section_name": operation.get("section_name"),
                    "track_name": operation.get("track_name"),
                    "preserve": _as_list(operation.get("preserve")),
                }
                for operation in operations
                if isinstance(operation, dict)
            ],
            "warnings": _as_list(patch.get("warnings")),
            "confidence": patch.get("confidence"),
        }
    )

def candidate_intents_for_strategy(task: ReviewTask, strategy: str) -> list[EditIntent]:
    strategy = _strategy(strategy)
    if strategy not in STRATEGIES:
        raise ReviewTaskError("Invalid local review candidate strategy.")
    target = task.target
    section_name = str(target.get("section_name") or "")
    track_name = str(target.get("track_name") or "")
    role = str(target.get("role") or "")
    snapshot = task.review_snapshot
    text = " ".join([str(snapshot.get("notes_excerpt") or ""), " ".join(str(tag) for tag in snapshot.get("tags", [])), str(snapshot.get("status") or "")]).lower()
    markers = [item for item in snapshot.get("markers", []) if isinstance(item, dict)]
    marker_kinds = {str(marker.get("kind") or "") for marker in markers}
    intents: list[EditIntent] = []

    if track_name and (_has_any(text, ("busy", "dense", "reduce", "less", "太满", "太密", "减少")) or role in {"bass", "drums"} or marker_kinds & FIX_MARKERS):
        scale = {"conservative": 0.84, "balanced": 0.72, "bold": 0.62}[strategy]
        strength = {"conservative": 3, "balanced": 4, "bold": 5}[strategy]
        intents.append(_intent("track_density", section_name=section_name, track_name=track_name, strength=strength, instruction=f"{strategy} review task density adjustment.", preserve=["tempo", "key", "structure", "lyrics", "harmony"], payload={"density_scale": scale, "source": "review_task", "strategy": strategy}))

    wants_energy = _has_any(text, ("strong", "energy", "lift", "chorus", "更强", "能量", "高潮", "更炸")) or "drop" in marker_kinds
    if section_name and strategy in {"balanced", "bold"} and (wants_energy or strategy in {"balanced", "bold"}):
        strength = {"conservative": 6, "balanced": 7, "bold": 8}[strategy]
        intents.append(_intent("section_energy", section_name=section_name, strength=strength, instruction=f"{strategy} review task section lift.", preserve=["tempo", "key", "structure", "lyrics", "harmony"], payload={"source": "review_task", "strategy": strategy}))

    if strategy == "bold" and not (marker_kinds & PRESERVE_MARKERS):
        if _has_any(text, ("hook", "melody", "旋律", "副歌")):
            intents.append(_intent("melody_variation", section_name=section_name, strength=5, instruction="Bold review task melody variation.", preserve=["tempo", "key", "structure", "harmony"], payload={"source": "review_task", "strategy": strategy}))
        elif _has_any(text, ("arrangement", "transition", "过渡", "编曲")):
            intents.append(_intent("arrangement_variation", section_name=section_name, track_name=track_name or None, strength=6, instruction="Bold review task arrangement variation.", preserve=["tempo", "key", "structure"], payload={"source": "review_task", "strategy": strategy}))
        elif track_name:
            intents.append(_intent("arrangement_variation", section_name=section_name, track_name=track_name, strength=6, instruction="Bold review task arrangement color.", preserve=["tempo", "key", "structure"], payload={"source": "review_task", "strategy": strategy, "instrument": f"{track_name} alt"}))

    if marker_kinds & PRESERVE_MARKERS and strategy != "conservative":
        intents = [intent for intent in intents if intent.edit_type != "melody_variation"]
    if not intents and section_name:
        intents.append(_intent("section_energy", section_name=section_name, strength=6, instruction=f"{strategy} review task fallback section lift.", preserve=["tempo", "key", "structure", "lyrics", "harmony"], payload={"source": "review_task", "strategy": strategy}))
    return intents[:4]

def apply_candidate_intents(parent_plan: SongPlan, intents: list[EditIntent]) -> EditedSongPlanResult:
    current = parent_plan
    summaries = []
    warnings: list[str] = []
    for intent in intents:
        validate_edit_intent(current, intent)
        result = apply_edit_intent(current, intent)
        current = result.plan
        summaries.append(result.summary)
        warnings.extend(result.warnings)
    plan = attach_quality(current)
    plan.validate()
    return EditedSongPlanResult(
        plan=plan,
        summary={
            "edit_source": "review_task_candidate",
            "operation_count": len(intents),
            "changed_sections": sorted({section for summary in summaries for section in summary.get("changed_sections", [])}),
            "changed_tracks": sorted({track for summary in summaries for track in summary.get("changed_tracks", [])}),
            "operations": summaries,
        },
        warnings=warnings,
    )

def review_task_target(parent_plan: SongPlan, audition: EditorAuditionManifest, review: DomainDocument) -> DomainDocument:
    markers = [item for item in review.get("markers", []) if isinstance(item, dict)]
    marker = _primary_marker(markers)
    range_data = _as_document(audition.range)
    local_beat = _float_or_none(marker.get("beat") if marker else None)
    global_beat = None if local_beat is None else _range_start(range_data) + local_beat
    section = _section_from_range_or_marker(parent_plan, range_data, global_beat)
    text = _review_text(review, audition)
    track = _target_track(parent_plan, audition, text)
    return sanitize_metadata(
        {
            "range_mode": str(range_data.get("mode") or ""),
            "range_start_beat": _range_start(range_data),
            "local_marker_beat": local_beat,
            "global_marker_beat": global_beat,
            "section_name": section.name,
            "section_start_beat": _section_start(section),
            "section_end_beat": _section_end(section),
            "track_name": track.name if track else "",
            "track_id": _track_id(parent_plan, track) if track else "",
            "role": _role_for_track(track, text) if track else _role_from_text(text) or "",
            "marker_kind": str(marker.get("kind") or "") if marker else "",
        }
    )

def review_snapshot(review: DomainDocument) -> DomainDocument:
    markers = [
        {
            "marker_id": str(marker.get("marker_id") or ""),
            "beat": _float_or_none(marker.get("beat")),
            "kind": str(marker.get("kind") or ""),
            "severity": str(marker.get("severity") or "medium"),
            "label": sanitize_sensitive_text(str(marker.get("label") or ""))[:160],
        }
        for marker in review.get("markers", [])
        if isinstance(marker, dict)
    ]
    return sanitize_metadata(
        {
            "rating": int(review.get("rating") or 0),
            "status": str(review.get("status") or "unreviewed"),
            "favorite": bool(review.get("favorite", False)),
            "notes_excerpt": sanitize_sensitive_text(str(review.get("notes") or ""))[:500],
            "tags": [sanitize_sensitive_text(str(tag))[:40] for tag in review.get("tags", [])],
            "markers": markers,
            "marker_kinds": sorted({str(marker.get("kind") or "") for marker in markers if marker.get("kind")}),
            "asset_ids": [str(review.get("last_asset_id"))] if review.get("last_asset_id") else [],
        }
    )

def review_task_summary(task: ReviewTask, selected: ReviewCandidate | None = None) -> DomainDocument:
    return sanitize_metadata(
        {
            "task_id": task.task_id,
            "status": task.status,
            "source_type": task.source.get("source_type"),
            "preview_id": task.preview_id,
            "audition_id": task.audition_id,
            "parent_version_id": task.parent_version_id,
            "target": {
                "section_name": task.target.get("section_name"),
                "track_name": task.target.get("track_name"),
                "global_marker_beat": task.target.get("global_marker_beat"),
            },
            "selected_candidate_id": task.selected_candidate_id,
            "applied_version_id": task.applied_version_id,
            "follow_up_task_id": task.follow_up_task_id,
            "summary": task.summary,
            "selected_candidate": review_candidate_summary(selected) if selected else {},
        }
    )

def review_candidate_summary(candidate: ReviewCandidate | None) -> DomainDocument:
    if candidate is None:
        return {}
    return sanitize_metadata(
        {
            "candidate_id": candidate.candidate_id,
            "candidate_type": candidate.candidate_type,
            "strategy": candidate.strategy,
            "rank": candidate.rank,
            "score": candidate.scores.get("combined"),
            "summary": candidate.summary,
        }
    )

def task_list_summary(tasks: list[ReviewTask]) -> dict[str, int]:
    summary = {"total": len(tasks), "open": 0, "candidate_ready": 0, "applied": 0, "resolved": 0, "needs_more_work": 0, "archived": 0, "stale": 0}
    for task in tasks:
        summary[task.status] = summary.get(task.status, 0) + 1
    return summary

def mark_task_resolved(task: ReviewTask, note: str = "", *, now: str | None = None) -> ReviewTask:
    if task.status != "applied":
        raise ReviewTaskStateError("Only applied review tasks can be resolved.")
    return ReviewTask.from_dict({**task.to_dict(), "status": "resolved", "resolved_at": now or now_iso(), "resolution_note": sanitize_sensitive_text(str(note or ""))[:500]})

def mark_task_archived(task: ReviewTask) -> ReviewTask:
    if task.status == "stale":
        raise ReviewTaskStateError("Stale review task cannot be archived here.")
    return ReviewTask.from_dict({**task.to_dict(), "status": "archived"})

def candidate_apply_metadata(task: ReviewTask, candidate: ReviewCandidate, result: EditedSongPlanResult, *, decision_report: DomainDocument | None = None) -> DomainDocument:
    primary = EditIntent.from_dict(candidate.intents[0])
    metadata = {
        "schema_version": 1,
        "project_id": task.project_id,
        "parent_version_id": task.parent_version_id,
        "edit_source": "review_task_candidate",
        **primary.to_dict(),
        "operation_count": len(candidate.intents),
        "summary": result.summary,
        "warnings": result.warnings,
        "review_task": review_task_summary(task, candidate),
        "review_candidate": review_candidate_summary(candidate),
        "review_edit": {
            "review_edit_id": f"{task.task_id}-candidate",
            "intent_count": len(candidate.intents),
            "confidence": min(0.95, max(0.1, float(candidate.scores.get("combined") or 0) / 100.0)),
        },
        "review_candidate_intents": [dict(intent) for intent in candidate.intents],
    }
    if candidate.source:
        metadata["review_candidate_source"] = candidate.source
    if candidate.patch:
        metadata["review_provider_patch"] = _provider_patch_summary(candidate.patch)
    if isinstance(decision_report, dict):
        metadata["review_decision"] = review_decision_summary(decision_report)
    return sanitize_metadata(metadata)

def validate_review_task_id(task_id: str) -> str:
    if not TASK_ID_PATTERN.match(str(task_id or "")):
        raise ValueError("Invalid review task id.")
    return task_id

def validate_review_candidate_id(candidate_id: str) -> str:
    if not CANDIDATE_ID_PATTERN.match(str(candidate_id or "")):
        raise ValueError("Invalid review candidate id.")
    return candidate_id

def _ensure_task_open_for_generation(task: ReviewTask) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        raise ReviewTaskStateError(f"Cannot generate candidates for a {task.status} review task.")
    if task.status == "applied":
        raise ReviewTaskStateError("Review task has already applied a candidate.")

def _ensure_task_open_for_apply(task: ReviewTask) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        raise ReviewTaskStateError(f"Cannot apply candidate for a {task.status} review task.")
    if task.status == "applied" or task.selected_candidate_id:
        raise ReviewTaskStateError("Review task has already applied a candidate.")

def ensure_task_current(task: ReviewTask, parent_plan: SongPlan) -> None:
    if song_plan_hash(parent_plan) != task.hashes.get("parent_plan_hash"):
        raise ReviewTaskStateError("Review task is stale because the parent song-plan.json has changed.")

def ensure_candidate_current(task: ReviewTask, candidate: ReviewCandidate, parent_plan: SongPlan) -> None:
    ensure_task_current(task, parent_plan)
    _ensure_candidate_current(task, candidate)

def _ensure_candidate_current(task: ReviewTask, candidate: ReviewCandidate) -> None:
    if candidate.status in {"failed", "deleted", "stale"}:
        raise ReviewTaskStateError(f"Cannot use a {candidate.status} review candidate.")
    if candidate.hashes.get("parent_plan_hash") and candidate.hashes.get("parent_plan_hash") != task.hashes.get("parent_plan_hash"):
        raise ReviewTaskStateError("Review candidate is stale.")

def _candidate_type(value: object) -> str:
    candidate_type = str(value or "local_review_intents").strip()
    if candidate_type not in {"local_review_intents", "provider_review_patch", "manual_override"}:
        raise ReviewTaskError("Unsupported review candidate type.")
    return candidate_type

def _strategy(value: object) -> str:
    strategy = str(value or "balanced").strip()
    if strategy not in {*STRATEGIES, PROVIDER_STRATEGY}:
        raise ReviewTaskError("Invalid review candidate strategy.")
    return strategy

def _candidate_source(task: ReviewTask) -> DomainDocument:
    return {
        "review_task_id": task.task_id,
        "audition_id": task.audition_id,
        "preview_id": task.preview_id,
        "source_type": "audition_review",
    }

def _provider_candidate_source(task: ReviewTask, provider_snapshot: DomainDocument, template_id: str, candidate_index: int) -> DomainDocument:
    usage = _as_document(provider_snapshot.get("usage"))
    return sanitize_metadata(
        {
            "review_task_id": task.task_id,
            "audition_id": task.audition_id,
            "preview_id": task.preview_id,
            "source_type": "provider_review_candidate",
            "provider": True,
            "template_id": template_id,
            "wire_api": provider_snapshot.get("wire_api"),
            "model": provider_snapshot.get("model"),
            "request_id": provider_snapshot.get("request_id"),
            "usage": {
                "prompt_tokens": _usage_int(usage, "prompt_tokens"),
                "completion_tokens": _usage_int(usage, "completion_tokens"),
                "total_tokens": _usage_int(usage, "total_tokens"),
            },
            "candidate_index": candidate_index,
            "provider_run_id": provider_snapshot.get("provider_run_id"),
            "provider_snapshot": provider_snapshot,
        }
    )

def _provider_snapshot_for_candidate(snapshot: DomainDocument) -> DomainDocument:
    data = sanitize_metadata(dict(snapshot or {}))
    data.pop("api_key", None)
    data.pop("api_key_set", None)
    data.pop("api_key_masked", None)
    return data

def _candidate_artifacts(task_id: str, candidate_id: str) -> dict[str, str]:
    base = f"review-tasks/{task_id}/candidates/{candidate_id}"
    return {
        "candidate_song_plan_path": f"{base}/candidate-song-plan.json",
        "validator_report_path": f"{base}/validator-report.json",
        "summary_path": f"{base}/summary.json",
        "midi_path": f"{base}/renders/song.mid",
        "audio_path": f"{base}/renders/song.wav",
    }

def _validator(status: str, errors: list[str] | None = None, warnings: list[str] | None = None) -> DomainDocument:
    return {"status": status, "errors": errors or [], "warnings": warnings or [], "checked_at": now_iso()}

def _usage_int(usage: DomainDocument, field_name: str) -> int:
    try:
        return max(0, int((usage or {}).get(field_name) or 0))
    except (TypeError, ValueError):
        return 0

def score_review_candidate(task: ReviewTask, candidate_plan: SongPlan, intents: list[EditIntent], strategy: str, parent_plan: SongPlan) -> DomainDocument:
    edit_types = {intent.edit_type for intent in intents}
    target_section = str(task.target.get("section_name") or "")
    target_track = str(task.target.get("track_name") or "")
    changed_sections = {intent.target.section_name for intent in intents if intent.target.section_name}
    changed_tracks = {intent.target.track_name for intent in intents if intent.target.track_name}
    review_fit = 45
    if "track_density" in edit_types:
        review_fit += 25
    if "section_energy" in edit_types:
        review_fit += 20
    if "melody_variation" in edit_types:
        review_fit += 10
    target_precision = 40
    if target_section and target_section in changed_sections:
        target_precision += 35
    if target_track and target_track in changed_tracks:
        target_precision += 25
    if len(changed_sections) <= 1:
        target_precision += 10
    if len(changed_tracks) <= 1:
        target_precision += 5
    parent_quality = parent_plan.quality.scores.overall if parent_plan.quality and parent_plan.quality.scores else 0
    candidate_quality = candidate_plan.quality.scores.overall if candidate_plan.quality and candidate_plan.quality.scores else 0
    quality_delta = candidate_quality - parent_quality
    novelty = {"conservative": 40, "balanced": 62, "bold": 78}[strategy]
    safety = {"conservative": 100, "balanced": 90, "bold": 78}[strategy]
    combined = round(0.34 * _clamp(review_fit, 0, 100) + 0.28 * _clamp(target_precision, 0, 100) + 0.18 * _clamp(candidate_quality, 0, 100) + 0.1 * novelty + 0.1 * safety)
    return {
        "combined": _clamp(combined, 0, 100),
        "review_fit": _clamp(review_fit, 0, 100),
        "target_precision": _clamp(target_precision, 0, 100),
        "quality_delta": quality_delta,
        "quality_overall": candidate_quality,
        "novelty": novelty,
        "safety": safety,
    }

def candidate_summary(task: ReviewTask, strategy: str, intents: list[EditIntent]) -> str:
    edits = ", ".join(intent.edit_type for intent in intents)
    target = task.target
    return sanitize_sensitive_text(f"{strategy} candidate for {target.get('section_name') or 'song'} {target.get('track_name') or ''}: {edits}")[:800]

def _candidate_warnings(task: ReviewTask, strategy: str) -> list[str]:
    kinds = set(task.review_snapshot.get("marker_kinds") or [])
    if kinds & PRESERVE_MARKERS and strategy != "conservative":
        return ["Hook/keep markers were treated as preserve signals."]
    return []

def _task_title(snapshot: DomainDocument, target: DomainDocument) -> str:
    section = target.get("section_name") or "song"
    track = target.get("track_name") or "arrangement"
    return sanitize_sensitive_text(f"Review task: {section} {track}")[:160]

def _task_summary(snapshot: DomainDocument, target: DomainDocument) -> str:
    status = snapshot.get("status") or "review"
    notes = snapshot.get("notes_excerpt") or ""
    target_text = " ".join(str(item) for item in (target.get("section_name"), target.get("track_name")) if item)
    return sanitize_sensitive_text(f"{status}: {target_text}. {notes}")[:800]

def _priority(snapshot: DomainDocument) -> int:
    rating = int(snapshot.get("rating") or 0)
    status = str(snapshot.get("status") or "")
    score = 50 + (5 - rating) * 6 if rating else 58
    if status == "needs_fix":
        score += 16
    if status == "reject":
        score += 8
    if snapshot.get("favorite"):
        score -= 8
    return _clamp(score, 0, 100)

def _primary_marker(markers: list[DomainDocument]) -> DomainDocument | None:
    for kind in ("fix", "issue", "drop"):
        for marker in markers:
            if str(marker.get("kind") or "") == kind:
                return marker
    for kind in ("note", "maybe"):
        for marker in markers:
            if str(marker.get("kind") or "") == kind:
                return marker
    for marker in markers:
        if str(marker.get("kind") or "") in PRESERVE_MARKERS:
            return marker
    return markers[0] if markers else None
