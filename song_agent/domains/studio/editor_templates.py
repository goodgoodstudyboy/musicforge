# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, document_or as _document_or

import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.editor_clips import ClipNote as ClipNote, EditorClipError as EditorClipError, EditorClipUnavailableError as EditorClipUnavailableError
from song_agent.domains.studio.editor_view import build_editor_view_from_result as build_editor_view_from_result
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.studio.song_editor import apply_editor_patch as apply_editor_patch, build_editor_state as build_editor_state, song_plan_hash as song_plan_hash


EDITOR_TEMPLATE_SCHEMA_VERSION = 1
EDITOR_TEMPLATE_ROOT = Path(".musicforge") / "editor-templates"
SECTION_TEMPLATE_PATTERN = re.compile(r"^section-template-[0-9]{3,6}$")
TRACK_TEMPLATE_PATTERN = re.compile(r"^track-template-[0-9]{3,6}$")
MAX_TEMPLATE_LANES = 8
MAX_TEMPLATE_LANE_NOTES = 128
MAX_TEMPLATE_TOTAL_NOTES = 180
MAX_TEMPLATE_DURATION_BEATS = 64.0
MAX_TEMPLATE_OPERATIONS = 200
MAX_TEMPLATE_JSON_BYTES = 512 * 1024
INSERT_MODES = {"overlay", "replace_range", "skip"}
ROLE_KEYWORDS = {
    "melody": ("melody", "lead", "vocal", "hook"),
    "chords": ("chord", "piano", "keys", "pad", "guitar", "synth"),
    "bass": ("bass", "sub"),
    "drums": ("drum", "beat", "perc", "kick", "snare", "hat"),
    "countermelody": ("counter", "countermelody"),
    "pad": ("pad", "strings", "atmos"),
    "fx": ("fx", "effect", "riser"),
}
SAFE_ROLES = set(ROLE_KEYWORDS) | {"unknown"}


class EditorTemplateError(ValueError):
    pass


class EditorTemplateUnavailableError(EditorTemplateError):
    pass


@dataclass(frozen=True)
class MultiTrackClipLane:
    lane_id: str
    role: str
    name: str
    instrument: str
    notes: list[ClipNote] = field(default_factory=list)
    chords: list[str] = field(default_factory=list)
    lyrics: str = ""
    metadata: ImplementationDocument = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "MultiTrackClipLane":
        if not isinstance(data, dict):
            raise EditorTemplateError("template lane must be an object.")
        lane_id = _safe_id(data.get("lane_id"), "lane_id")
        role = _role(data.get("role"))
        notes = [ClipNote.from_dict(dict(note)) for note in data.get("notes", []) if isinstance(note, dict)]
        if len(notes) > MAX_TEMPLATE_LANE_NOTES:
            raise EditorTemplateError(f"template lane supports at most {MAX_TEMPLATE_LANE_NOTES} notes.")
        return cls(
            lane_id=lane_id,
            role=role,
            name=_bounded(data.get("name"), 120) or lane_id,
            instrument=_bounded(data.get("instrument"), 120),
            notes=sorted(notes, key=lambda note: (note.start_beat, note.pitch, note.duration_beats, note.velocity)),
            chords=[_bounded(chord, 40) for chord in data.get("chords", []) if str(chord).strip()][:16] if isinstance(data.get("chords", []), list) else [],
            lyrics=_bounded(data.get("lyrics"), 2000),
            metadata=sanitize_metadata(dict(data.get("metadata") or {})),
        )

    def to_dict(self) -> DomainDocument:
        data = asdict(self)
        data["notes"] = [note.to_dict() for note in self.notes]
        return sanitize_metadata(data)


@dataclass(frozen=True)
class MultiTrackClip:
    schema_version: int
    clip_id: str
    source_type: str
    source_id: str
    title: str
    duration_beats: float
    key: str = ""
    tempo_bpm: int | None = None
    lanes: list[MultiTrackClipLane] = field(default_factory=list)
    metadata: ImplementationDocument = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "MultiTrackClip":
        if not isinstance(data, dict):
            raise EditorTemplateError("multitrack clip must be an object.")
        lanes = [MultiTrackClipLane.from_dict(dict(item)) for item in data.get("lanes", []) if isinstance(item, dict)]
        clip = cls(
            schema_version=int(data.get("schema_version", EDITOR_TEMPLATE_SCHEMA_VERSION) or EDITOR_TEMPLATE_SCHEMA_VERSION),
            clip_id=_safe_id(data.get("clip_id") or "clip-001", "clip_id"),
            source_type=_bounded(data.get("source_type"), 60) or "template",
            source_id=_bounded(data.get("source_id"), 160),
            title=_bounded(data.get("title"), 160) or "Untitled Template Clip",
            duration_beats=round(float(data.get("duration_beats") or 0), 6),
            key=_bounded(data.get("key"), 40),
            tempo_bpm=_optional_tempo(data.get("tempo_bpm")),
            lanes=lanes,
            metadata=sanitize_metadata(dict(data.get("metadata") or {})),
        )
        clip.validate()
        return clip

    def validate(self) -> None:
        if self.schema_version != EDITOR_TEMPLATE_SCHEMA_VERSION:
            raise EditorTemplateError(f"template schema_version must be {EDITOR_TEMPLATE_SCHEMA_VERSION}.")
        if not self.lanes:
            raise EditorTemplateUnavailableError("Template clip has no lanes.")
        if len(self.lanes) > MAX_TEMPLATE_LANES:
            raise EditorTemplateError(f"template clip supports at most {MAX_TEMPLATE_LANES} lanes.")
        if self.duration_beats <= 0 or self.duration_beats > MAX_TEMPLATE_DURATION_BEATS:
            raise EditorTemplateError(f"template duration must be > 0 and at most {MAX_TEMPLATE_DURATION_BEATS} beats.")
        total_notes = sum(len(lane.notes) for lane in self.lanes)
        if total_notes <= 0:
            raise EditorTemplateUnavailableError("Template clip has no notes.")
        if total_notes > MAX_TEMPLATE_TOTAL_NOTES:
            raise EditorTemplateError(f"template clip supports at most {MAX_TEMPLATE_TOTAL_NOTES} notes.")
        lane_ids = [lane.lane_id for lane in self.lanes]
        if len(set(lane_ids)) != len(lane_ids):
            raise EditorTemplateError("template lane_id values must be unique.")

    def to_dict(self) -> DomainDocument:
        data = asdict(self)
        data["lanes"] = [lane.to_dict() for lane in self.lanes]
        return sanitize_metadata(data)

    def summary(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "clip_id": self.clip_id,
                "source_type": self.source_type,
                "source_id": self.source_id,
                "title": self.title,
                "duration_beats": self.duration_beats,
                "key": self.key,
                "tempo_bpm": self.tempo_bpm,
                "lane_count": len(self.lanes),
                "note_count": sum(len(lane.notes) for lane in self.lanes),
                "lanes": [
                    {
                        "lane_id": lane.lane_id,
                        "role": lane.role,
                        "name": lane.name,
                        "instrument": lane.instrument,
                        "note_count": len(lane.notes),
                        "chord_count": len(lane.chords),
                    }
                    for lane in self.lanes
                ],
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True)
class SectionTemplate:
    schema_version: int
    template_id: str
    name: str
    section_name: str
    bars: int
    chords: list[str]
    lyrics_mode: str = "source_excerpt"
    clip: MultiTrackClip | None = None
    source_summary: ImplementationDocument = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    hidden: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "SectionTemplate":
        if not isinstance(data, dict):
            raise EditorTemplateError("section template must be an object.")
        clip_data = data.get("clip")
        clip = MultiTrackClip.from_dict(clip_data) if isinstance(clip_data, dict) else None
        template = cls(
            schema_version=int(data.get("schema_version", EDITOR_TEMPLATE_SCHEMA_VERSION) or EDITOR_TEMPLATE_SCHEMA_VERSION),
            template_id=validate_section_template_id(str(data.get("template_id") or "section-template-001")),
            name=_bounded(data.get("name"), 160) or "Untitled Section Template",
            section_name=_bounded(data.get("section_name"), 80) or "section",
            bars=_int_range(data.get("bars", 4), "bars", 1, 64),
            chords=[_bounded(item, 40) for item in data.get("chords", []) if str(item).strip()][:16] if isinstance(data.get("chords", []), list) else [],
            lyrics_mode=_choice(data.get("lyrics_mode") or "source_excerpt", "lyrics_mode", {"empty", "placeholder", "source_excerpt"}),
            clip=clip,
            source_summary=sanitize_metadata(dict(data.get("source_summary") or {})),
            tags=_tags(data.get("tags")),
            hidden=bool(data.get("hidden", False)),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )
        _validate_template_size(template.to_dict())
        return template

    def to_dict(self) -> DomainDocument:
        data = asdict(self)
        data["clip"] = self.clip.to_dict() if self.clip else None
        return sanitize_metadata(data)


@dataclass(frozen=True)
class TrackTemplate:
    schema_version: int
    template_id: str
    name: str
    role: str
    instrument: str
    default_notes: list[ClipNote] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_summary: ImplementationDocument = field(default_factory=dict)
    hidden: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "TrackTemplate":
        if not isinstance(data, dict):
            raise EditorTemplateError("track template must be an object.")
        notes = [ClipNote.from_dict(dict(note)) for note in data.get("default_notes", []) if isinstance(note, dict)]
        template = cls(
            schema_version=int(data.get("schema_version", EDITOR_TEMPLATE_SCHEMA_VERSION) or EDITOR_TEMPLATE_SCHEMA_VERSION),
            template_id=validate_track_template_id(str(data.get("template_id") or "track-template-001")),
            name=_bounded(data.get("name"), 160) or "Untitled Track Template",
            role=_role(data.get("role")),
            instrument=_bounded(data.get("instrument"), 120),
            default_notes=notes[:MAX_TEMPLATE_LANE_NOTES],
            tags=_tags(data.get("tags")),
            source_summary=sanitize_metadata(dict(data.get("source_summary") or {})),
            hidden=bool(data.get("hidden", False)),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )
        _validate_template_size(template.to_dict())
        return template

    def to_dict(self) -> DomainDocument:
        data = asdict(self)
        data["default_notes"] = [note.to_dict() for note in self.default_notes]
        return sanitize_metadata(data)


from song_agent.domains.studio import v142_et_readiness as _v142_et_readiness
from song_agent.domains.studio.v142_et_readiness import EditorTemplateStore as EditorTemplateStore, section_template_public_dict as section_template_public_dict, track_template_public_dict as track_template_public_dict, section_template_source_status as section_template_source_status, build_multitrack_clip_from_project_section as build_multitrack_clip_from_project_section, build_multitrack_clip_from_ref as build_multitrack_clip_from_ref, suggest_lane_mappings as suggest_lane_mappings
from song_agent.domains.studio import v142_et_evidence as _v142_et_evidence
from song_agent.domains.studio.v142_et_evidence import build_multitrack_clip_insert_patch as build_multitrack_clip_insert_patch, validate_section_template_id as validate_section_template_id, validate_track_template_id as validate_track_template_id, _project_version_plan as _project_version_plan, _track_by_id as _track_by_id, _section_by_id as _section_by_id, _target_section as _target_section, _target_start_beat as _target_start_beat, _clean_lane_mappings as _clean_lane_mappings, _note_ids_in_replace_range as _note_ids_in_replace_range, _lane_summary as _lane_summary, _template_insert_metadata as _template_insert_metadata, _template_group_id as _template_group_id, _mapping_score as _mapping_score, _ranges_overlap as _ranges_overlap, _range_from_payload as _range_from_payload, _safe_child as _safe_child, _validate_template_size as _validate_template_size, _safe_id as _safe_id, _role as _role, _tags as _tags, _bounded as _bounded, _choice as _choice, _int_range as _int_range, _float_min as _float_min, _float_range as _float_range, _optional_tempo as _optional_tempo, _quantize_grid as _quantize_grid, _round_beat as _round_beat

_v142_et_readiness.bind_globals(globals())
_v142_et_evidence.bind_globals(globals())
