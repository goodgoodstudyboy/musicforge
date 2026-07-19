# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.candidate_scoring import group_status_for_candidates as group_status_for_candidates, rank_candidate_summaries as rank_candidate_summaries
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan

GROUP_ID_PATTERN = re.compile(r"^cg-[0-9]{3,5}$")
CANDIDATE_ID_PATTERN = re.compile(r"^cand-[0-9]{3,5}$")
GROUP_STATUSES = {"creating", "ready", "partial_ready", "failed", "applied", "deleted"}
CANDIDATE_STATUSES = {"ready", "failed", "applied", "skipped"}
MAX_CANDIDATE_COUNT = 5
MIN_CANDIDATE_COUNT = 2


@dataclass(frozen=True)
class CandidateSummary:
    candidate_id: str
    group_id: str
    status: str
    rank: int | None = None
    summary: str = ""
    scores: ImplementationDocument = field(default_factory=dict)
    patch: ImplementationDocument = field(default_factory=dict)
    validator: ImplementationDocument = field(default_factory=dict)
    quality: ImplementationDocument | None = None
    provider_usage: ImplementationDocument = field(default_factory=dict)
    provider_request_id: str | None = None
    midi_status: str = "not_started"
    midi_error: str | None = None
    midi_size_bytes: int = 0
    midi_url: str | None = None
    audio_status: str = "not_started"
    audio_error: str | None = None
    audio_size_bytes: int = 0
    audio_url: str | None = None
    error: str | None = None
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "CandidateSummary":
        candidate_id = validate_candidate_id(str(data.get("candidate_id") or ""))
        group_id = validate_group_id(str(data.get("group_id") or ""))
        status = str(data.get("status") or "failed")
        if status not in CANDIDATE_STATUSES:
            status = "failed"
        return cls(
            candidate_id=candidate_id,
            group_id=group_id,
            status=status,
            rank=_optional_int(data.get("rank")),
            summary=str(data.get("summary") or ""),
            scores=dict(data.get("scores") or {}),
            patch=dict(data.get("patch") or {}),
            validator=dict(data.get("validator") or {}),
            quality=data.get("quality") if isinstance(data.get("quality"), dict) else None,
            provider_usage=dict(data.get("provider_usage") or {}),
            provider_request_id=None if data.get("provider_request_id") is None else str(data.get("provider_request_id")),
            midi_status=str(data.get("midi_status") or "not_started"),
            midi_error=None if data.get("midi_error") is None else str(data.get("midi_error")),
            midi_size_bytes=int(data.get("midi_size_bytes") or 0),
            midi_url=None if data.get("midi_url") is None else str(data.get("midi_url")),
            audio_status=str(data.get("audio_status") or "not_started"),
            audio_error=None if data.get("audio_error") is None else str(data.get("audio_error")),
            audio_size_bytes=int(data.get("audio_size_bytes") or 0),
            audio_url=None if data.get("audio_url") is None else str(data.get("audio_url")),
            error=None if data.get("error") is None else str(data.get("error")),
            created_at=str(data.get("created_at") or ""),
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class CandidateGroup:
    group_id: str
    project_id: str
    parent_version_id: str
    parent_job_id: str
    instruction: str
    template_id: str
    candidate_count: int
    status: str
    created_at: str
    updated_at: str
    source: ImplementationDocument
    candidates: list[CandidateSummary] = field(default_factory=list)
    ranking: list[ImplementationDocument] = field(default_factory=list)
    selected_candidate_id: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None
    provider_usage: ImplementationDocument = field(default_factory=dict)
    provider_request_id: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "CandidateGroup":
        group_id = validate_group_id(str(data.get("group_id") or ""))
        status = str(data.get("status") or "failed")
        if status not in GROUP_STATUSES:
            status = "failed"
        candidates = [CandidateSummary.from_dict(item) for item in data.get("candidates", []) if isinstance(item, dict)]
        return cls(
            group_id=group_id,
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            parent_job_id=str(data.get("parent_job_id") or ""),
            instruction=str(data.get("instruction") or ""),
            template_id=str(data.get("template_id") or "provider-edit-candidates"),
            candidate_count=_candidate_count(data.get("candidate_count")),
            status=status,
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            source=dict(data.get("source") or {}),
            candidates=candidates,
            ranking=[dict(item) for item in data.get("ranking", []) if isinstance(item, dict)],
            selected_candidate_id=_optional_candidate_id(data.get("selected_candidate_id")),
            applied_version_id=None if data.get("applied_version_id") is None else str(data.get("applied_version_id")),
            applied_job_id=None if data.get("applied_job_id") is None else str(data.get("applied_job_id")),
            provider_usage=dict(data.get("provider_usage") or {}),
            provider_request_id=None if data.get("provider_request_id") is None else str(data.get("provider_request_id")),
            error=None if data.get("error") is None else str(data.get("error")),
        )

    def to_dict(self) -> DomainDocument:
        return {
            "group_id": self.group_id,
            "project_id": self.project_id,
            "parent_version_id": self.parent_version_id,
            "parent_job_id": self.parent_job_id,
            "instruction": self.instruction,
            "template_id": self.template_id,
            "candidate_count": self.candidate_count,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": dict(self.source),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "ranking": [dict(item) for item in self.ranking],
            "selected_candidate_id": self.selected_candidate_id,
            "applied_version_id": self.applied_version_id,
            "applied_job_id": self.applied_job_id,
            "provider_usage": dict(self.provider_usage),
            "provider_request_id": self.provider_request_id,
            "error": self.error,
        }


from song_agent.domains.quality import v142_cg_readiness as _v142_cg_readiness
from song_agent.domains.quality.v142_cg_readiness import CandidateGroupStore as CandidateGroupStore, validate_group_id as validate_group_id, validate_candidate_id as validate_candidate_id, candidate_group_stale as candidate_group_stale, candidate_midi_path as candidate_midi_path, candidate_audio_path as candidate_audio_path, candidate_midi_url as candidate_midi_url, candidate_audio_url as candidate_audio_url, _candidate_count as _candidate_count
from song_agent.domains.quality import v142_cg_evidence as _v142_cg_evidence
from song_agent.domains.quality.v142_cg_evidence import _optional_candidate_id as _optional_candidate_id, _optional_int as _optional_int, _safe_artifact_path as _safe_artifact_path

_v142_cg_readiness.bind_globals(globals())
_v142_cg_evidence.bind_globals(globals())
