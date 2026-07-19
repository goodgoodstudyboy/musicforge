# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_int as _as_int, document_or as _document_or, list_or as _list_or

import hashlib as hashlib
import json as json
import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.assets import AssetStore as AssetStore, CreativeAsset as CreativeAsset, asset_content_summary as asset_content_summary, sanitize_asset_metadata as sanitize_asset_metadata
from song_agent.domains.creation.midi_analysis import notes_for_slice as notes_for_slice, parse_midi as parse_midi
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.reference_analysis import reference_context as reference_context, require_fresh_slices as require_fresh_slices
from song_agent.domains.studio.references import ReferenceStore as ReferenceStore
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan
from song_agent.domains.studio.song_editor import build_editor_state as build_editor_state, song_plan_hash as song_plan_hash


EDITOR_CLIP_SCHEMA_VERSION = 1
MAX_EDITOR_CLIP_NOTES = 128
MAX_EDITOR_CLIP_DURATION_BEATS = 64.0
MAX_EDITOR_CLIP_OPERATIONS = 160
MAX_EDITOR_CLIP_BODY_BYTES = 256 * 1024
MAX_REPLACE_NOTE_IDS = 512
CLIP_SOURCE_TYPES = {
    "asset",
    "reference_slice",
    "project_version_section",
    "project_version_track_range",
}
INSERT_MODES = {"overlay", "replace_range"}
QUANTIZE_GRIDS = {
    "1/4": 1.0,
    "1/8": 0.5,
    "1/16": 0.25,
    "1/32": 0.125,
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,120}$")


class EditorClipError(ValueError):
    pass


class EditorClipUnavailableError(EditorClipError):
    pass


@dataclass(frozen=True)
class ClipNote:
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int = 90
    channel: int | None = None
    role: str = ""

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ClipNote":
        if not isinstance(data, dict):
            raise EditorClipError("clip note must be an object.")
        try:
            pitch = _as_int(data.get("pitch"))
            start = round(float(data.get("start_beat") or 0), 6)
            duration = round(float(data.get("duration_beats") or 0), 6)
            velocity = int(data.get("velocity", 90) or 90)
        except (TypeError, ValueError) as exc:
            raise EditorClipError("clip note has invalid numeric fields.") from exc
        if pitch < 0 or pitch > 127:
            raise EditorClipError("clip note pitch must be between 0 and 127.")
        if start < 0:
            raise EditorClipError("clip note start_beat must be >= 0.")
        if duration <= 0:
            raise EditorClipError("clip note duration_beats must be > 0.")
        if velocity < 1 or velocity > 127:
            raise EditorClipError("clip note velocity must be between 1 and 127.")
        channel = data.get("channel")
        if channel is not None:
            channel = int(channel)
            if channel < 0 or channel > 15:
                channel = None
        return cls(
            pitch=pitch,
            start_beat=start,
            duration_beats=duration,
            velocity=velocity,
            channel=channel,
            role=sanitize_sensitive_text(str(data.get("role") or ""))[:40],
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class EditorClip:
    schema_version: int
    source_type: str
    source_id: str
    title: str
    kind: str
    duration_beats: float
    notes: list[ClipNote]
    source_version_id: str | None = None
    suggested_track_role: str = ""
    suggested_key: str = ""
    suggested_tempo: int | None = None
    lyrics: list[str] = field(default_factory=list)
    metadata: ImplementationDocument = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_type not in CLIP_SOURCE_TYPES:
            raise EditorClipError(f"Unsupported clip source_type: {self.source_type}.")
        if not self.notes:
            raise EditorClipUnavailableError("Clip has no notes.")
        if len(self.notes) > MAX_EDITOR_CLIP_NOTES:
            raise EditorClipError(f"editor clips support at most {MAX_EDITOR_CLIP_NOTES} notes.")
        if self.duration_beats <= 0 or self.duration_beats > MAX_EDITOR_CLIP_DURATION_BEATS:
            raise EditorClipError(f"editor clip duration must be > 0 and at most {MAX_EDITOR_CLIP_DURATION_BEATS} beats.")

    def to_dict(self) -> DomainDocument:
        data = asdict(self)
        data["notes"] = [note.to_dict() for note in self.notes]
        return sanitize_metadata(data)

    def summary(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "source_type": self.source_type,
                "source_id": self.source_id,
                "source_version_id": self.source_version_id,
                "title": self.title,
                "kind": self.kind,
                "duration_beats": self.duration_beats,
                "note_count": len(self.notes),
                "suggested_track_role": self.suggested_track_role,
                "suggested_key": self.suggested_key,
                "suggested_tempo": self.suggested_tempo,
                "metadata": self.metadata,
            }
        )


def list_editor_clips(
    *,
    project_id: str,
    version_id: str,
    asset_store: AssetStore,
    reference_store: ReferenceStore,
    project_store: ProjectStore,
) -> DomainDocument:
    assets = [_asset_clip_summary(asset) for asset in asset_store.list_assets() if _asset_has_notes(asset)]
    reference_slices = _reference_slice_summaries(reference_store)
    project_versions = _project_version_clip_summaries(project_store, project_id)
    clips = [
        *assets,
        *reference_slices,
        *[clip for version in project_versions for clip in version.get("clips", [])],
    ]
    return sanitize_metadata(
        {
            "ok": True,
            "schema_version": EDITOR_CLIP_SCHEMA_VERSION,
            "project_id": project_id,
            "version_id": version_id,
            "limits": {
                "max_notes": MAX_EDITOR_CLIP_NOTES,
                "max_duration_beats": MAX_EDITOR_CLIP_DURATION_BEATS,
                "max_operations": MAX_EDITOR_CLIP_OPERATIONS,
            },
            "clips": clips,
            "assets": assets,
            "reference_slices": reference_slices,
            "project_versions": project_versions,
        }
    )


def build_editor_clip_from_ref(
    clip_ref: DomainDocument,
    *,
    default_project_id: str,
    asset_store: AssetStore,
    reference_store: ReferenceStore,
    project_store: ProjectStore,
) -> EditorClip:
    if not isinstance(clip_ref, dict):
        raise EditorClipError("clip_ref must be an object.")
    source_type = str(clip_ref.get("source_type") or "").strip()
    if source_type == "asset":
        return _clip_from_asset(clip_ref, asset_store)
    if source_type == "reference_slice":
        return _clip_from_reference_slice(clip_ref, reference_store)
    if source_type == "project_version_section":
        return _clip_from_project_section(clip_ref, default_project_id=default_project_id, project_store=project_store)
    if source_type == "project_version_track_range":
        return _clip_from_project_track_range(clip_ref, default_project_id=default_project_id, project_store=project_store)
    raise EditorClipError(f"Unsupported clip source_type: {source_type}.")


def build_clip_insert_patch(
    parent_plan: SongPlan,
    clip: EditorClip,
    payload: DomainDocument,
    *,
    draft_plan: SongPlan | None = None,
    draft_state: DomainDocument | None = None,
) -> tuple[DomainDocument, DomainDocument, list[str]]:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_EDITOR_CLIP_BODY_BYTES:
        raise EditorClipError(f"clip insert request must be {MAX_EDITOR_CLIP_BODY_BYTES} bytes or fewer.")
    target = payload.get("target")
    options = payload.get("options") or {}
    if not isinstance(target, dict):
        raise EditorClipError("target must be an object.")
    if not isinstance(options, dict):
        raise EditorClipError("options must be an object.")
    base_state = build_editor_state(parent_plan)
    state = _document_or(draft_state, build_editor_state(draft_plan or parent_plan))
    track_id = _target_track_id(target, state)
    section = _target_section(target, state)
    start_beat = _target_start_beat(target, section)
    mode = str(options.get("mode") or target.get("mode") or "overlay").strip()
    if mode not in INSERT_MODES:
        raise EditorClipError(f"clip insert mode must be one of: {', '.join(sorted(INSERT_MODES))}.")
    transpose = _int_range(options.get("transpose", 0), "transpose", -24, 24)
    velocity_scale = _float_range(options.get("velocity_scale", 1.0), "velocity_scale", 0.25, 2.0)
    quantize_grid = _quantize_grid(options.get("quantize_grid"))
    trim_to_section = bool(options.get("trim_to_section", section is not None or options.get("fit") == "trim"))
    total_beats = float(state["song"]["total_bars"]) * float(state["song"]["beats_per_bar"])
    section_end = float(section["end_beat"]) if section and trim_to_section else None
    operations: list[ImplementationDocument] = []
    warnings: list[str] = []
    if mode == "replace_range":
        note_ids = _note_ids_in_replace_range(state, track_id, start_beat, start_beat + clip.duration_beats)
        if len(note_ids) > MAX_REPLACE_NOTE_IDS:
            raise EditorClipError(f"replace_range can remove at most {MAX_REPLACE_NOTE_IDS} notes.")
        if note_ids:
            operations.append({"op": "delete_notes", "track_id": track_id, "note_ids": note_ids})
    inserted = 0
    for note in clip.notes:
        absolute_start = _round_beat(start_beat + note.start_beat)
        if quantize_grid:
            absolute_start = _round_beat(round(absolute_start / quantize_grid) * quantize_grid)
        duration = note.duration_beats
        if section_end is not None and absolute_start + duration > section_end:
            duration = _round_beat(section_end - absolute_start)
        if absolute_start < 0 or absolute_start >= total_beats or duration <= 0:
            warnings.append("Skipped clip note outside target range.")
            continue
        if absolute_start + duration > total_beats:
            duration = _round_beat(total_beats - absolute_start)
        pitch = note.pitch + transpose
        if pitch < 0 or pitch > 127:
            warnings.append("Skipped clip note outside MIDI pitch range after transpose.")
            continue
        velocity = max(1, min(127, int(round(note.velocity * velocity_scale))))
        operations.append(
            {
                "op": "add_note",
                "track_id": track_id,
                "note": {
                    "pitch": pitch,
                    "start_beat": absolute_start,
                    "duration_beats": _round_beat(duration),
                    "velocity": velocity,
                },
            }
        )
        inserted += 1
    if inserted == 0:
        raise EditorClipUnavailableError("Clip insert produced no notes.")
    if len(operations) > MAX_EDITOR_CLIP_OPERATIONS:
        raise EditorClipError(f"clip insert can create at most {MAX_EDITOR_CLIP_OPERATIONS} editor operations.")
    group_id = _clip_group_id(clip, track_id=track_id, start_beat=start_beat, operations=operations)
    for operation in operations:
        operation["clip_group_id"] = group_id
    metadata = _clip_insert_metadata(
        clip,
        group_id=group_id,
        target={
            "track_id": track_id,
            "section_id": section.get("section_id") if section else None,
            "start_beat": start_beat,
            "mode": mode,
        },
        options={
            "transpose": transpose,
            "velocity_scale": velocity_scale,
            "quantize_grid": quantize_grid,
            "trim_to_section": trim_to_section,
        },
        inserted_note_count=inserted,
        replaced_note_count=max(0, len(operations) - inserted) and len(operations[0].get("note_ids", [])) if mode == "replace_range" and operations else 0,
    )
    patch = {
        "schema_version": 1,
        "base_plan_hash": str(base_state["base_plan_hash"]),
        "label": f"Insert clip: {clip.title}"[:160],
        "operations": operations,
        "metadata": {"clip_inserts": [metadata]},
    }
    return sanitize_metadata(patch), clip.summary(), [sanitize_sensitive_text(item) for item in warnings]


def _asset_clip_summary(asset: CreativeAsset) -> ImplementationDocument:
    summary = _base_summary(
        source_type="asset",
        source_id=asset.asset_id,
        title=asset.name,
        kind=_kind_for_asset(asset),
        duration_beats=float(asset.duration_beats),
        note_count=len(_raw_asset_notes(asset)),
        suggested_track_role=_role_for_asset(asset),
        suggested_key=asset.key,
        suggested_tempo=asset.tempo_bpm,
        source_hash=_asset_hash(asset),
    )
    summary["clip_ref"] = {
        "source_type": "asset",
        "asset_id": asset.asset_id,
        "source_hash": summary["source_hash"],
    }
    summary["content_summary"] = asset_content_summary(asset)
    return sanitize_metadata(summary)


def _reference_slice_summaries(reference_store: ReferenceStore) -> list[ImplementationDocument]:
    summaries: list[ImplementationDocument] = []
    for reference in reference_store.list_references():
        if reference.reference_type != "midi":
            continue
        try:
            manifest = require_fresh_slices(reference_store, reference.reference_id)
        except Exception:
            continue
        for slice_item in manifest.get("slices", []) if isinstance(manifest.get("slices"), list) else []:
            note_count = int(slice_item.get("note_count") or 0)
            if note_count <= 0:
                continue
            slice_id = str(slice_item.get("slice_id") or "")
            summary = _base_summary(
                source_type="reference_slice",
                source_id=reference.reference_id,
                title=f"{reference.title} {slice_id}",
                kind=str(slice_item.get("slice_type") or "motif"),
                duration_beats=float(slice_item.get("duration_beats") or 0),
                note_count=note_count,
                suggested_track_role=str(slice_item.get("slice_type") or ""),
                suggested_key=reference.key,
                suggested_tempo=reference.tempo_bpm,
                source_hash=str(manifest.get("source_sha256") or reference.sha256),
            )
            summary["slice_id"] = slice_id
            summary["clip_ref"] = {
                "source_type": "reference_slice",
                "reference_id": reference.reference_id,
                "slice_id": slice_id,
                "source_hash": summary["source_hash"],
            }
            summaries.append(sanitize_metadata(summary))
    return summaries


def _project_version_clip_summaries(project_store: ProjectStore, project_id: str) -> list[ImplementationDocument]:
    try:
        document = project_store.get_project(project_id)
    except FileNotFoundError:
        return []
    versions = []
    for version in document.versions:
        plan = _version_plan(version.output_dir)
        if plan is None:
            continue
        state = build_editor_state(plan)
        source_hash = state["base_plan_hash"]
        clips = []
        for section in state["sections"]:
            for track in state["tracks"]:
                notes = [
                    note
                    for note in track.get("notes", [])
                    if float(section["start_beat"]) <= float(note["start_beat"]) < float(section["end_beat"])
                ]
                if not notes:
                    continue
                summary = _base_summary(
                    source_type="project_version_section",
                    source_id=project_id,
                    title=f"{version.name} / {section['name']} / {track['name']}",
                    kind=str(track.get("role") or "track"),
                    duration_beats=float(section["end_beat"]) - float(section["start_beat"]),
                    note_count=len(notes),
                    suggested_track_role=str(track.get("role") or ""),
                    suggested_key=plan.key,
                    suggested_tempo=plan.tempo_bpm,
                    source_hash=source_hash,
                )
                summary["source_version_id"] = version.version_id
                summary["section_id"] = section["section_id"]
                summary["track_id"] = track["track_id"]
                summary["clip_ref"] = {
                    "source_type": "project_version_section",
                    "project_id": project_id,
                    "source_version_id": version.version_id,
                    "section_id": section["section_id"],
                    "track_id": track["track_id"],
                    "source_hash": source_hash,
                }
                clips.append(sanitize_metadata(summary))
        if clips:
            versions.append(
                sanitize_metadata(
                    {
                        "version_id": version.version_id,
                        "name": version.name,
                        "source_hash": source_hash,
                        "clip_count": len(clips),
                        "clips": clips,
                    }
                )
            )
    return versions


def _clip_from_asset(clip_ref: ImplementationDocument, store: AssetStore) -> EditorClip:
    asset_id = _clean_id(clip_ref.get("asset_id") or clip_ref.get("source_id"), "asset_id")
    asset = store.read_asset(asset_id)
    if asset.hidden:
        raise EditorClipUnavailableError("Hidden assets cannot be inserted.")
    expected_hash = str(clip_ref.get("source_hash") or "").strip()
    actual_hash = _asset_hash(asset)
    if expected_hash and expected_hash != actual_hash:
        raise EditorClipUnavailableError("Asset clip is stale.")
    notes = _normalize_notes(_raw_asset_notes(asset))
    return EditorClip(
        schema_version=EDITOR_CLIP_SCHEMA_VERSION,
        source_type="asset",
        source_id=asset.asset_id,
        source_version_id=None,
        title=asset.name,
        kind=_kind_for_asset(asset),
        duration_beats=_clip_duration(notes, asset.duration_beats),
        suggested_track_role=_role_for_asset(asset),
        suggested_key=asset.key,
        suggested_tempo=asset.tempo_bpm,
        notes=notes,
        metadata={
            "asset_type": asset.asset_type,
            "source_hash": actual_hash,
            "content_summary": asset_content_summary(asset),
        },
    )


from song_agent.domains.studio import v142_ec_readiness as _v142_ec_readiness
from song_agent.domains.studio.v142_ec_readiness import (
    _clip_from_reference_slice,
    _clip_from_project_section,
    _clip_from_project_track_range,
    _raw_asset_notes,
    _fallback_asset_notes,
    _asset_has_notes,
    _normalize_notes,
    _clip_duration,
    _target_track_id,
    _target_section,
    _target_start_beat,
    _note_ids_in_replace_range,
    _clip_insert_metadata,
    _clip_group_id,
    _base_summary,
    _find_slice,
    _project_version_plan,
    _version_plan,
    _check_project_source_hash,
    _section_by_id,
    _track_by_id,
    _kind_for_asset,
    _role_for_asset,
    _asset_hash,
    _clean_id,
    _int_range,
    _float_min,
    _float_range,
    _quantize_grid,
    _round_beat,
)

_v142_ec_readiness.bind_globals(globals())
