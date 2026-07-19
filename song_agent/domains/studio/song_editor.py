# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts.coercion import as_float as _as_float, as_int as _as_int


from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any, Mapping as Mapping

from song_agent.domains.creation.edits import SUPPORTED_HARMONY_CHORDS as SUPPORTED_HARMONY_CHORDS
from song_agent.domains.creation.music_quality import attach_quality as attach_quality, analyze_song_quality as analyze_song_quality
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan


EDITOR_PREVIEW_SCHEMA_VERSION = 1
EDITOR_PATCH_SCHEMA_VERSION = 1
MAX_EDITOR_TRACKS = 32
MAX_EDITOR_NOTES_PER_TRACK = 4096
MAX_EDITOR_PATCH_BYTES = 256 * 1024
MAX_EDITOR_OPERATIONS = 200
MAX_NOTE_IDS_PER_OPERATION = 512
MAX_ADDED_NOTES_PER_PATCH = 512
MAX_TOTAL_NOTES_AFTER_PATCH = 16000
MAX_TOTAL_BARS_AFTER_PATCH = 256
MAX_SECTION_BARS = 64
MAX_SECTION_NAME_LENGTH = 40
MAX_TRACK_NAME_LENGTH = 40
MAX_LYRICS_LENGTH = 2000
MAX_INSTRUMENT_LENGTH = 80
NOTE_PATCH_FIELDS = {"pitch", "start_beat", "duration_beats", "velocity"}
SUPPORTED_EDITOR_OPS = {
    "set_section_chords",
    "set_section_lyrics",
    "set_track_instrument",
    "add_section",
    "duplicate_section",
    "delete_section",
    "resize_section",
    "move_section",
    "add_track",
    "duplicate_track",
    "delete_track",
    "rename_track",
    "add_note",
    "update_note",
    "delete_notes",
    "move_notes",
    "transpose_notes",
    "quantize_notes",
    "scale_velocity",
}
QUANTIZE_GRIDS = {0.125, 0.25, 0.5, 1.0}
_SUPPORTED_CHORDS_BY_LOWER = {chord.lower(): chord for chord in SUPPORTED_HARMONY_CHORDS}
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NoteKey = tuple[int, float, float, int]


class EditorPatchError(ValueError):
    pass


class EditorPatchStaleError(EditorPatchError):
    pass


@dataclass(frozen=True)
class EditorPatch:
    schema_version: int
    base_plan_hash: str
    label: str = ""
    operations: list[ImplementationDocument] = field(default_factory=list)
    metadata: ImplementationDocument = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "EditorPatch":
        if not isinstance(data, dict):
            raise EditorPatchError("patch must be an object.")
        raw = json.dumps(data, ensure_ascii=False)
        if len(raw.encode("utf-8")) > MAX_EDITOR_PATCH_BYTES:
            raise EditorPatchError(f"editor patch must be {MAX_EDITOR_PATCH_BYTES} bytes or fewer.")
        schema_version = int(data.get("schema_version", EDITOR_PATCH_SCHEMA_VERSION) or EDITOR_PATCH_SCHEMA_VERSION)
        if schema_version != EDITOR_PATCH_SCHEMA_VERSION:
            raise EditorPatchError(f"editor patch schema_version must be {EDITOR_PATCH_SCHEMA_VERSION}.")
        operations = data.get("operations")
        if not isinstance(operations, list) or not operations:
            raise EditorPatchError("editor patch operations must be a non-empty list.")
        if len(operations) > MAX_EDITOR_OPERATIONS:
            raise EditorPatchError(f"editor patch supports at most {MAX_EDITOR_OPERATIONS} operations.")
        cleaned_ops = []
        for operation in operations:
            if not isinstance(operation, dict):
                raise EditorPatchError("editor patch operations must be objects.")
            op = str(operation.get("op") or "").strip()
            if op not in SUPPORTED_EDITOR_OPS:
                raise EditorPatchError(f"Unsupported editor operation: {op}.")
            cleaned_ops.append(sanitize_metadata(dict(operation)))
        return cls(
            schema_version=schema_version,
            base_plan_hash=str(data.get("base_plan_hash") or "").strip(),
            label=_bounded_text(data.get("label"), 160),
            operations=cleaned_ops,
            metadata=_patch_metadata(data.get("metadata")),
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class EditorPatchResult:
    plan: SongPlan
    patch: EditorPatch
    summary: ImplementationDocument
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EditorPreview:
    schema_version: int
    preview_id: str
    project_id: str
    parent_version_id: str
    parent_job_id: str
    base_plan_hash: str
    status: str
    label: str = ""
    created_at: str = ""
    updated_at: str = ""
    operation_count: int = 0
    changed_sections: list[str] = field(default_factory=list)
    changed_tracks: list[str] = field(default_factory=list)
    quality: ImplementationDocument = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    midi_url: str | None = None
    audio_url: str | None = None
    audio_status: str = "not_started"
    audio_error: str | None = None
    audio_size_bytes: int = 0
    audio_updated_at: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "EditorPreview":
        return cls(
            schema_version=int(data.get("schema_version", EDITOR_PREVIEW_SCHEMA_VERSION) or EDITOR_PREVIEW_SCHEMA_VERSION),
            preview_id=validate_editor_preview_id(str(data.get("preview_id") or "preview-001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            parent_job_id=str(data.get("parent_job_id") or ""),
            base_plan_hash=str(data.get("base_plan_hash") or ""),
            status=str(data.get("status") or "created"),
            label=sanitize_sensitive_text(str(data.get("label") or "")),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            operation_count=max(0, int(data.get("operation_count") or 0)),
            changed_sections=[str(item) for item in data.get("changed_sections", [])],
            changed_tracks=[str(item) for item in data.get("changed_tracks", [])],
            quality=sanitize_metadata(dict(data.get("quality") or {})),
            warnings=[sanitize_sensitive_text(str(item)) for item in data.get("warnings", [])],
            midi_url=_optional_str(data.get("midi_url")),
            audio_url=_optional_str(data.get("audio_url")),
            audio_status=_preview_audio_status(data.get("audio_status")),
            audio_error=_optional_str(sanitize_sensitive_text(str(data.get("audio_error") or ""))),
            audio_size_bytes=max(0, int(data.get("audio_size_bytes") or 0)),
            audio_updated_at=_optional_str(data.get("audio_updated_at")),
            applied_version_id=_optional_str(data.get("applied_version_id")),
            applied_job_id=_optional_str(data.get("applied_job_id")),
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


from song_agent.domains.studio import v142_se_readiness as _v142_se_readiness
from song_agent.domains.studio.v142_se_readiness import EditorPreviewStore, build_editor_state, _apply_editor_patch_part_01
from song_agent.domains.studio import v142_se_evidence as _v142_se_evidence
from song_agent.domains.studio.v142_se_evidence import (
    _apply_editor_patch_operations_01,
    _apply_editor_patch_operations_02,
    _apply_editor_patch_part_02,
    _apply_editor_patch_part_03,
    apply_editor_patch,
    summarize_editor_patch,
    describe_editor_operations,
    _operation_counts,
    _operation_name,
    _patch_metadata,
    _clip_inserts_from_metadata,
    _template_inserts_from_metadata,
    _structure_edit_summary,
)
from song_agent.domains.studio import v142_se_lifecycle as _v142_se_lifecycle
from song_agent.domains.studio.v142_se_lifecycle import (
    editor_edit_metadata,
    song_plan_hash,
    validate_editor_preview_id,
    _preview_audio_status,
    section_id_for_index,
    track_id_for_index,
    note_id_for,
    _section_index,
    _section_index_for_plan,
    _track_index,
    _track_index_for_plan,
    _chords,
    _clean_lyrics,
    _bounded_text,
    _note,
    _update_note,
    _note_ids,
    _base_note_keys_by_track_id,
    _note_key,
    _note_key_from_mapping,
    _note_index_by_key,
    _identity_by_id,
    _note_identity_by_track_id,
    normalize_sections,
    shift_notes_after_beat,
    delete_notes_in_range,
    copy_notes_in_range,
    remap_notes_by_section,
    trim_notes_to_total_beats,
    _note_selector,
    _map_selected_notes,
    _delete_selected_notes,
    _validate_selected_note_ids,
    _note_ids_by_key,
)
from song_agent.domains.studio import v142_se_archive as _v142_se_archive
from song_agent.domains.studio.v142_se_archive import (
    _pop_matching_note_id,
    _shift_note_keys_after_beat,
    _delete_note_keys_in_range,
    _trim_note_keys_to_total_beats,
    _remap_note_keys_by_section,
    _section_name_for_note_key,
    _beat_range,
    _section_from_operation,
    _unique_section_name,
    _unique_track_name,
    _optional_after_section_index,
    _section_start_beat,
    _section_span,
    _section_start_beat_at_index,
    _section_name_for_note,
    _assert_total_bars,
    _total_bars_from_sections,
    _choice,
    _missing_required_track_roles,
    _validate_note_limits,
    _ensure_note_bounds,
    _sorted_notes,
    _int_range,
    _float_min,
    _float_range,
    _parse_iso_datetime,
    _round_beat,
    _clamp,
    _total_bars,
    _beats_per_bar,
    _track_role,
    _quality_summary,
    _preview_validator_report,
    _append_preview_event,
    _optional_str,
)

_v142_se_readiness.bind_globals(globals())
_v142_se_evidence.bind_globals(globals())
_v142_se_lifecycle.bind_globals(globals())
_v142_se_archive.bind_globals(globals())
