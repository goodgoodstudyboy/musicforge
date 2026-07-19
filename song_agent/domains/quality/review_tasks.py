# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field, replace as replace
from pathlib import Path as Path
from typing import Any as Any

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


REVIEW_TASK_SCHEMA_VERSION = 1
REVIEW_CANDIDATE_SCHEMA_VERSION = 1
REVIEW_DECISION_REPORT_SCHEMA_VERSION = 1
TASK_ID_PATTERN = re.compile(r"^review-task-[0-9]{3,6}$")
CANDIDATE_ID_PATTERN = re.compile(r"^revcand-[0-9]{3,6}$")
TASK_STATUSES = {"open", "candidate_ready", "applied", "resolved", "needs_more_work", "archived", "stale"}
CANDIDATE_STATUSES = {"queued", "ready", "failed", "applied", "stale", "deleted"}
STRATEGIES = ("conservative", "balanced", "bold")
PROVIDER_STRATEGY = "provider"
TERMINAL_TASK_STATUSES = {"resolved", "archived", "stale", "needs_more_work"}
FIX_MARKERS = {"fix", "issue", "drop"}
PRESERVE_MARKERS = {"keep", "hook"}
_LOCKS_GUARD = threading.RLock()
_STORE_LOCKS: dict[str, threading.RLock] = {}


class ReviewTaskError(ValueError):
    pass


class ReviewTaskStateError(ReviewTaskError):
    pass


@dataclass(frozen=True)
class ReviewTask:
    schema_version: int
    task_id: str
    project_id: str
    parent_version_id: str
    preview_id: str
    audition_id: str
    status: str
    priority: int
    title: str
    summary: str
    source: ImplementationDocument = field(default_factory=dict)
    review_snapshot: ImplementationDocument = field(default_factory=dict)
    target: ImplementationDocument = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    selected_candidate_id: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None
    resolved_at: str | None = None
    resolution_note: str = ""
    follow_up_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ReviewTask":
        if not isinstance(data, dict):
            raise ReviewTaskError("review task must be an object.")
        status = str(data.get("status") or "open")
        if status not in TASK_STATUSES:
            raise ReviewTaskError(f"status must be one of: {', '.join(sorted(TASK_STATUSES))}.")
        candidate_id = data.get("selected_candidate_id")
        return cls(
            schema_version=int(data.get("schema_version", REVIEW_TASK_SCHEMA_VERSION) or REVIEW_TASK_SCHEMA_VERSION),
            task_id=validate_review_task_id(str(data.get("task_id") or "review-task-001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            preview_id=str(data.get("preview_id") or ""),
            audition_id=str(data.get("audition_id") or ""),
            status=status,
            priority=_clamp_int(data.get("priority"), 0, 100, 50),
            title=sanitize_sensitive_text(str(data.get("title") or ""))[:160],
            summary=sanitize_sensitive_text(str(data.get("summary") or ""))[:800],
            source=sanitize_metadata(dict(data.get("source") or {})),
            review_snapshot=sanitize_metadata(dict(data.get("review_snapshot") or {})),
            target=sanitize_metadata(dict(data.get("target") or {})),
            hashes={str(k): str(v) for k, v in dict(data.get("hashes") or {}).items()},
            counts={str(k): int(v) for k, v in dict(data.get("counts") or {}).items() if isinstance(v, (int, float, str))},
            selected_candidate_id=None if candidate_id in {None, ""} else validate_review_candidate_id(str(candidate_id)),
            applied_version_id=_optional_str(data.get("applied_version_id")),
            applied_job_id=_optional_str(data.get("applied_job_id")),
            resolved_at=_optional_str(data.get("resolved_at")),
            resolution_note=sanitize_sensitive_text(str(data.get("resolution_note") or ""))[:500],
            follow_up_task_id=None if not data.get("follow_up_task_id") else validate_review_task_id(str(data.get("follow_up_task_id"))),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class ReviewCandidate:
    schema_version: int
    candidate_id: str
    task_id: str
    project_id: str
    parent_version_id: str
    candidate_type: str
    strategy: str
    status: str
    rank: int = 0
    summary: str = ""
    source: ImplementationDocument = field(default_factory=dict)
    intents: list[ImplementationDocument] = field(default_factory=list)
    patch: ImplementationDocument | None = None
    validator: ImplementationDocument = field(default_factory=dict)
    scores: ImplementationDocument = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    midi_status: str = "not_started"
    midi_url: str | None = None
    midi_size_bytes: int = 0
    audio_status: str = "not_started"
    audio_url: str | None = None
    audio_size_bytes: int = 0
    audio_error: str | None = None
    hashes: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ReviewCandidate":
        if not isinstance(data, dict):
            raise ReviewTaskError("review candidate must be an object.")
        status = str(data.get("status") or "queued")
        if status not in CANDIDATE_STATUSES:
            raise ReviewTaskError(f"candidate status must be one of: {', '.join(sorted(CANDIDATE_STATUSES))}.")
        return cls(
            schema_version=int(data.get("schema_version", REVIEW_CANDIDATE_SCHEMA_VERSION) or REVIEW_CANDIDATE_SCHEMA_VERSION),
            candidate_id=validate_review_candidate_id(str(data.get("candidate_id") or "revcand-001")),
            task_id=validate_review_task_id(str(data.get("task_id") or "review-task-001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            candidate_type=_candidate_type(data.get("candidate_type")),
            strategy=_strategy(data.get("strategy")),
            status=status,
            rank=max(0, int(data.get("rank") or 0)),
            summary=sanitize_sensitive_text(str(data.get("summary") or ""))[:800],
            source=sanitize_metadata(dict(data.get("source") or {})),
            intents=[EditIntent.from_dict(dict(item)).to_dict() for item in data.get("intents", []) if isinstance(item, dict)],
            patch=sanitize_metadata(dict(data["patch"])) if isinstance(data.get("patch"), dict) else None,
            validator=sanitize_metadata(dict(data.get("validator") or {})),
            scores=sanitize_metadata(dict(data.get("scores") or {})),
            warnings=[sanitize_sensitive_text(str(item)) for item in data.get("warnings", [])],
            artifacts={str(k): str(v) for k, v in dict(data.get("artifacts") or {}).items()},
            midi_status=str(data.get("midi_status") or "not_started"),
            midi_url=_optional_str(data.get("midi_url")),
            midi_size_bytes=max(0, int(data.get("midi_size_bytes") or 0)),
            audio_status=str(data.get("audio_status") or "not_started"),
            audio_url=_optional_str(data.get("audio_url")),
            audio_size_bytes=max(0, int(data.get("audio_size_bytes") or 0)),
            audio_error=None if data.get("audio_error") in {None, ""} else sanitize_sensitive_text(str(data.get("audio_error"))),
            hashes={str(k): str(v) for k, v in dict(data.get("hashes") or {}).items()},
            error=None if data.get("error") in {None, ""} else sanitize_sensitive_text(str(data.get("error"))),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


from song_agent.domains.quality import v142_rt_readiness as _v142_rt_readiness
from song_agent.domains.quality.v142_rt_readiness import ReviewTaskStore
from song_agent.domains.quality import v142_rt_evidence as _v142_rt_evidence
from song_agent.domains.quality.v142_rt_evidence import (
    build_local_review_candidates,
    build_provider_review_candidates,
    provider_review_candidate_instruction,
    score_provider_review_candidate,
    build_review_decision_report,
    review_decision_summary,
    review_candidate_source_breakdown,
    _decision_rank_entry,
    _recommendation_reason,
    _decision_risk_flags,
)
from song_agent.domains.quality import v142_rt_lifecycle as _v142_rt_lifecycle
from song_agent.domains.quality.v142_rt_lifecycle import (
    _judge_summary_for_decision,
    _provider_patch_summary,
    candidate_intents_for_strategy,
    apply_candidate_intents,
    review_task_target,
    review_snapshot,
    review_task_summary,
    review_candidate_summary,
    task_list_summary,
    mark_task_resolved,
    mark_task_archived,
    candidate_apply_metadata,
    validate_review_task_id,
    validate_review_candidate_id,
    _ensure_task_open_for_generation,
    _ensure_task_open_for_apply,
    ensure_task_current,
    ensure_candidate_current,
    _ensure_candidate_current,
    _candidate_type,
    _strategy,
    _candidate_source,
    _provider_candidate_source,
    _provider_snapshot_for_candidate,
    _candidate_artifacts,
    _validator,
    _usage_int,
    score_review_candidate,
    candidate_summary,
    _candidate_warnings,
    _task_title,
    _task_summary,
    _priority,
    _primary_marker,
)
from song_agent.domains.quality import v142_rt_archive as _v142_rt_archive
from song_agent.domains.quality.v142_rt_archive import (
    _section_from_range_or_marker,
    _target_track,
    _review_text,
    _role_from_text,
    _track_by_role,
    _role_for_track,
    _track_id,
    _track_state,
    _find_section,
    _section_for_beat,
    _section_start,
    _section_end,
    _range_start,
    _intent,
    _has_any,
    _clamp_int,
    _clamp,
    _float_or_none,
    _optional_str,
    _lock_for_project,
    _append_event,
)

_v142_rt_readiness.bind_globals(globals())
_v142_rt_evidence.bind_globals(globals())
_v142_rt_lifecycle.bind_globals(globals())
_v142_rt_archive.bind_globals(globals())
