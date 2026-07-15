from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.domains.studio.assets import AssetStore, CreativeAsset, asset_content_summary, sanitize_asset_metadata
from song_agent.domains.creation.midi_analysis import notes_for_slice, parse_midi
from song_agent.domains.studio.projectio import read_json
from song_agent.domains.studio.project_repository import ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.studio.reference_analysis import reference_context, require_fresh_slices
from song_agent.domains.studio.references import ReferenceStore
from song_agent.domains.creation.schemas.song import NoteEvent, SongPlan
from song_agent.domains.studio.song_editor import build_editor_state, song_plan_hash


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
    def from_dict(cls, data: dict[str, Any]) -> "ClipNote":
        if not isinstance(data, dict):
            raise EditorClipError("clip note must be an object.")
        try:
            pitch = int(data.get("pitch"))
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

    def to_dict(self) -> dict[str, Any]:
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
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_type not in CLIP_SOURCE_TYPES:
            raise EditorClipError(f"Unsupported clip source_type: {self.source_type}.")
        if not self.notes:
            raise EditorClipUnavailableError("Clip has no notes.")
        if len(self.notes) > MAX_EDITOR_CLIP_NOTES:
            raise EditorClipError(f"editor clips support at most {MAX_EDITOR_CLIP_NOTES} notes.")
        if self.duration_beats <= 0 or self.duration_beats > MAX_EDITOR_CLIP_DURATION_BEATS:
            raise EditorClipError(f"editor clip duration must be > 0 and at most {MAX_EDITOR_CLIP_DURATION_BEATS} beats.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["notes"] = [note.to_dict() for note in self.notes]
        return sanitize_metadata(data)

    def summary(self) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
    clip_ref: dict[str, Any],
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
    payload: dict[str, Any],
    *,
    draft_plan: SongPlan | None = None,
    draft_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
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
    state = draft_state if isinstance(draft_state, dict) else build_editor_state(draft_plan or parent_plan)
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
    operations: list[dict[str, Any]] = []
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


def _asset_clip_summary(asset: CreativeAsset) -> dict[str, Any]:
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


def _reference_slice_summaries(reference_store: ReferenceStore) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
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


def _project_version_clip_summaries(project_store: ProjectStore, project_id: str) -> list[dict[str, Any]]:
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


def _clip_from_asset(clip_ref: dict[str, Any], store: AssetStore) -> EditorClip:
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


def _clip_from_reference_slice(clip_ref: dict[str, Any], store: ReferenceStore) -> EditorClip:
    reference_id = _clean_id(clip_ref.get("reference_id") or clip_ref.get("source_id"), "reference_id")
    slice_id = _clean_id(clip_ref.get("slice_id"), "slice_id")
    context = reference_context(store, reference_id)
    if context.reference.hidden:
        raise EditorClipUnavailableError("Hidden references cannot be inserted.")
    if context.reference.reference_type != "midi":
        raise EditorClipError("Only MIDI references can provide editor clips.")
    manifest = require_fresh_slices(store, reference_id)
    expected_hash = str(clip_ref.get("source_hash") or "").strip()
    actual_hash = str(manifest.get("source_sha256") or context.reference.sha256)
    if expected_hash and expected_hash != actual_hash:
        raise EditorClipUnavailableError("Reference clip is stale.")
    slice_item = _find_slice(manifest, slice_id)
    midi = parse_midi(context.source_path.read_bytes())
    notes = _normalize_notes(notes_for_slice(midi, slice_item))
    return EditorClip(
        schema_version=EDITOR_CLIP_SCHEMA_VERSION,
        source_type="reference_slice",
        source_id=context.reference.reference_id,
        source_version_id=None,
        title=f"{context.reference.title} {slice_id}",
        kind=str(slice_item.get("slice_type") or "motif"),
        duration_beats=_clip_duration(notes, float(slice_item.get("duration_beats") or 0)),
        suggested_track_role=str(slice_item.get("slice_type") or ""),
        suggested_key=context.reference.key,
        suggested_tempo=context.reference.tempo_bpm,
        notes=notes,
        metadata={
            "reference_id": context.reference.reference_id,
            "slice_id": slice_id,
            "source_hash": actual_hash,
            "track_index": slice_item.get("track_index"),
            "channel": slice_item.get("channel"),
        },
    )


def _clip_from_project_section(clip_ref: dict[str, Any], *, default_project_id: str, project_store: ProjectStore) -> EditorClip:
    project_id = _clean_id(clip_ref.get("project_id") or default_project_id, "project_id")
    version_id = _clean_id(clip_ref.get("source_version_id") or clip_ref.get("version_id"), "source_version_id")
    section_id = _clean_id(clip_ref.get("section_id"), "section_id")
    track_id = _clean_id(clip_ref.get("track_id"), "track_id")
    plan = _project_version_plan(project_store, project_id, version_id)
    state = build_editor_state(plan)
    _check_project_source_hash(clip_ref, state["base_plan_hash"])
    section = _section_by_id(state, section_id)
    track = _track_by_id(state, track_id)
    section_start = float(section["start_beat"])
    section_end = float(section["end_beat"])
    raw_notes = [
        {**note, "start_beat": float(note["start_beat"]) - section_start, "role": track.get("role")}
        for note in track.get("notes", [])
        if section_start <= float(note["start_beat"]) < section_end
    ]
    notes = _normalize_notes(raw_notes)
    return EditorClip(
        schema_version=EDITOR_CLIP_SCHEMA_VERSION,
        source_type="project_version_section",
        source_id=project_id,
        source_version_id=version_id,
        title=f"{version_id} {section['name']} {track['name']}",
        kind=str(track.get("role") or "track"),
        duration_beats=_clip_duration(notes, float(section["end_beat"]) - float(section["start_beat"])),
        suggested_track_role=str(track.get("role") or ""),
        suggested_key=plan.key,
        suggested_tempo=plan.tempo_bpm,
        notes=notes,
        metadata={
            "project_id": project_id,
            "source_version_id": version_id,
            "section_id": section_id,
            "track_id": track_id,
            "source_hash": state["base_plan_hash"],
        },
    )


def _clip_from_project_track_range(clip_ref: dict[str, Any], *, default_project_id: str, project_store: ProjectStore) -> EditorClip:
    project_id = _clean_id(clip_ref.get("project_id") or default_project_id, "project_id")
    version_id = _clean_id(clip_ref.get("source_version_id") or clip_ref.get("version_id"), "source_version_id")
    track_id = _clean_id(clip_ref.get("track_id"), "track_id")
    start = _float_min(clip_ref.get("start_beat"), "start_beat", 0.0)
    end = _float_min(clip_ref.get("end_beat"), "end_beat", start + 0.0001)
    if end <= start:
        raise EditorClipError("end_beat must be greater than start_beat.")
    if end - start > MAX_EDITOR_CLIP_DURATION_BEATS:
        raise EditorClipError("track range clip is too long.")
    plan = _project_version_plan(project_store, project_id, version_id)
    state = build_editor_state(plan)
    _check_project_source_hash(clip_ref, state["base_plan_hash"])
    track = _track_by_id(state, track_id)
    raw_notes = [
        {**note, "start_beat": float(note["start_beat"]) - start, "role": track.get("role")}
        for note in track.get("notes", [])
        if start <= float(note["start_beat"]) < end
    ]
    notes = _normalize_notes(raw_notes)
    return EditorClip(
        schema_version=EDITOR_CLIP_SCHEMA_VERSION,
        source_type="project_version_track_range",
        source_id=project_id,
        source_version_id=version_id,
        title=f"{version_id} {track['name']} {start:g}-{end:g}",
        kind=str(track.get("role") or "track"),
        duration_beats=_clip_duration(notes, end - start),
        suggested_track_role=str(track.get("role") or ""),
        suggested_key=plan.key,
        suggested_tempo=plan.tempo_bpm,
        notes=notes,
        metadata={
            "project_id": project_id,
            "source_version_id": version_id,
            "track_id": track_id,
            "start_beat": start,
            "end_beat": end,
            "source_hash": state["base_plan_hash"],
        },
    )


def _raw_asset_notes(asset: CreativeAsset) -> list[dict[str, Any]]:
    notes = asset.content.get("notes")
    if isinstance(notes, list) and notes:
        return [dict(note) for note in notes if isinstance(note, dict)]
    return [note.to_dict() for note in _fallback_asset_notes(asset)]


def _fallback_asset_notes(asset: CreativeAsset) -> list[NoteEvent]:
    if asset.asset_type == "motif":
        anchor = int(asset.content.get("anchor_pitch") or 64)
        intervals = [int(item) for item in asset.content.get("pitch_intervals", [0, 3, 5, 7])][:16]
        rhythm = [float(item) for item in asset.content.get("rhythm_pattern", [1.0] * len(intervals))]
        cursor = 0.0
        notes = []
        for index, interval in enumerate(intervals):
            duration = max(0.25, rhythm[index % len(rhythm)] if rhythm else 1.0)
            notes.append(NoteEvent(anchor + interval, cursor, duration, 92))
            cursor += duration
        return notes
    if asset.asset_type in {"chord_progression", "section_template"}:
        chords = asset.content.get("chords") if isinstance(asset.content.get("chords"), list) else ["Cmaj7"]
        notes = []
        for index, _chord in enumerate(chords[:16]):
            for pitch in (60, 64, 67):
                notes.append(NoteEvent(pitch, float(index * 4), 3.75, 72))
        return notes
    return []


def _asset_has_notes(asset: CreativeAsset) -> bool:
    if asset.hidden:
        return False
    try:
        return bool(_raw_asset_notes(asset))
    except Exception:
        return False


def _normalize_notes(raw_notes: list[dict[str, Any]]) -> list[ClipNote]:
    notes = [ClipNote.from_dict(dict(note)) for note in raw_notes if isinstance(note, dict)]
    if not notes:
        raise EditorClipUnavailableError("Clip has no notes.")
    if len(notes) > MAX_EDITOR_CLIP_NOTES:
        raise EditorClipError(f"editor clips support at most {MAX_EDITOR_CLIP_NOTES} notes.")
    min_start = min(note.start_beat for note in notes)
    normalized = [
        ClipNote(
            pitch=note.pitch,
            start_beat=round(note.start_beat - min_start, 6),
            duration_beats=note.duration_beats,
            velocity=note.velocity,
            channel=note.channel,
            role=note.role,
        )
        for note in sorted(notes, key=lambda item: (item.start_beat, item.pitch, item.duration_beats, item.velocity))
    ]
    duration = max(note.start_beat + note.duration_beats for note in normalized)
    if duration > MAX_EDITOR_CLIP_DURATION_BEATS:
        raise EditorClipError(f"editor clip duration must be at most {MAX_EDITOR_CLIP_DURATION_BEATS} beats.")
    return normalized


def _clip_duration(notes: list[ClipNote], fallback: float) -> float:
    duration = max((note.start_beat + note.duration_beats for note in notes), default=float(fallback or 0))
    return round(max(0.25, min(MAX_EDITOR_CLIP_DURATION_BEATS, duration or float(fallback or 0.25))), 6)


def _target_track_id(target: dict[str, Any], state: dict[str, Any]) -> str:
    track_id = _clean_id(target.get("track_id"), "track_id")
    _track_by_id(state, track_id)
    return track_id


def _target_section(target: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    section_id = str(target.get("section_id") or "").strip()
    if not section_id:
        return None
    return _section_by_id(state, section_id)


def _target_start_beat(target: dict[str, Any], section: dict[str, Any] | None) -> float:
    if "start_beat" in target:
        return _float_min(target.get("start_beat"), "target.start_beat", 0.0)
    if section is not None:
        return round(float(section["start_beat"]), 6)
    raise EditorClipError("target.start_beat is required when section_id is not provided.")


def _note_ids_in_replace_range(state: dict[str, Any], track_id: str, start: float, end: float) -> list[str]:
    track = _track_by_id(state, track_id)
    lane = next((item for item in state.get("lanes", []) if item.get("track_id") == track_id), None)
    raw_notes = lane.get("notes", []) if isinstance(lane, dict) else track.get("notes", [])
    ids = []
    for note in raw_notes:
        if bool(note.get("derived", False)) or str(note.get("note_id") or "").startswith("derived-note-"):
            continue
        note_start = float(note["start_beat"])
        note_end = note_start + float(note["duration_beats"])
        if note_end > start and note_start < end:
            ids.append(str(note["note_id"]))
    return ids


def _clip_insert_metadata(
    clip: EditorClip,
    *,
    group_id: str,
    target: dict[str, Any],
    options: dict[str, Any],
    inserted_note_count: int,
    replaced_note_count: int,
) -> dict[str, Any]:
    metadata = {
        "schema_version": EDITOR_CLIP_SCHEMA_VERSION,
        "clip_group_id": group_id,
        "source_type": clip.source_type,
        "source_id": clip.source_id,
        "source_version_id": clip.source_version_id,
        "title": clip.title,
        "kind": clip.kind,
        "duration_beats": clip.duration_beats,
        "note_count": len(clip.notes),
        "inserted_note_count": inserted_note_count,
        "replaced_note_count": replaced_note_count,
        "target": target,
        "options": options,
        "source": clip.metadata,
    }
    for key in ("asset_type", "reference_id", "slice_id", "project_id", "section_id", "track_id", "source_hash"):
        if key in clip.metadata:
            metadata[key] = clip.metadata[key]
    return sanitize_metadata(metadata)


def _clip_group_id(clip: EditorClip, *, track_id: str, start_beat: float, operations: list[dict[str, Any]]) -> str:
    operation_fingerprint = [
        {
            key: value
            for key, value in operation.items()
            if key not in {"clip_group_id", "clipInsert"}
        }
        for operation in operations
    ]
    payload = json.dumps(
        {
            "source_type": clip.source_type,
            "source_id": clip.source_id,
            "source_version_id": clip.source_version_id,
            "title": clip.title,
            "track_id": track_id,
            "start_beat": start_beat,
            "operation_count": len(operations),
            "notes": [note.to_dict() for note in clip.notes[:MAX_EDITOR_CLIP_NOTES]],
            "operations": operation_fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"clip-{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"


def _base_summary(
    *,
    source_type: str,
    source_id: str,
    title: str,
    kind: str,
    duration_beats: float,
    note_count: int,
    suggested_track_role: str,
    suggested_key: str,
    suggested_tempo: int | None,
    source_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": EDITOR_CLIP_SCHEMA_VERSION,
        "source_type": source_type,
        "source_id": source_id,
        "title": sanitize_sensitive_text(str(title or source_id))[:160],
        "kind": sanitize_sensitive_text(str(kind or "clip"))[:80],
        "duration_beats": round(float(duration_beats or 0), 6),
        "note_count": max(0, int(note_count or 0)),
        "suggested_track_role": sanitize_sensitive_text(str(suggested_track_role or ""))[:80],
        "suggested_key": sanitize_sensitive_text(str(suggested_key or ""))[:40],
        "suggested_tempo": suggested_tempo,
        "source_hash": source_hash,
    }


def _find_slice(manifest: dict[str, Any], slice_id: str) -> dict[str, Any]:
    for item in manifest.get("slices", []) if isinstance(manifest.get("slices"), list) else []:
        if str(item.get("slice_id") or "") == slice_id:
            return dict(item)
    raise FileNotFoundError(slice_id)


def _project_version_plan(project_store: ProjectStore, project_id: str, version_id: str) -> SongPlan:
    document = project_store.get_project(project_id)
    version = next((item for item in document.versions if item.version_id == version_id), None)
    if version is None:
        raise FileNotFoundError(version_id)
    plan = _version_plan(version.output_dir)
    if plan is None:
        raise EditorClipUnavailableError("Project version song-plan.json is not available.")
    return plan


def _version_plan(output_dir: str | Path) -> SongPlan | None:
    path = Path(output_dir) / "data" / "song-plan.json"
    if not path.exists():
        return None
    try:
        return SongPlan.from_dict(read_json(path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _check_project_source_hash(clip_ref: dict[str, Any], actual_hash: str) -> None:
    expected_hash = str(clip_ref.get("source_hash") or "").strip()
    if expected_hash and expected_hash != actual_hash:
        raise EditorClipUnavailableError("Project version clip is stale.")


def _section_by_id(state: dict[str, Any], section_id: str) -> dict[str, Any]:
    section = next((item for item in state.get("sections", []) if item.get("section_id") == section_id), None)
    if section is None:
        raise EditorClipError("Unknown section_id.")
    return dict(section)


def _track_by_id(state: dict[str, Any], track_id: str) -> dict[str, Any]:
    track = next((item for item in state.get("tracks", []) if item.get("track_id") == track_id), None)
    if track is None:
        raise EditorClipError("Unknown track_id.")
    return dict(track)


def _kind_for_asset(asset: CreativeAsset) -> str:
    return str(asset.content.get("kind") or asset.asset_type)


def _role_for_asset(asset: CreativeAsset) -> str:
    return {
        "motif": "melody",
        "chord_progression": "chords",
        "drum_pattern": "drums",
        "bass_pattern": "bass",
        "section_template": "chords",
    }.get(asset.asset_type, "melody")


def _asset_hash(asset: CreativeAsset) -> str:
    payload = json.dumps(
        {
            "asset_id": asset.asset_id,
            "updated_at": asset.updated_at,
            "content": sanitize_asset_metadata(asset.content),
            "source": sanitize_asset_metadata(asset.source),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean_id(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_ID.match(text):
        raise EditorClipError(f"{name} is required.")
    return text


def _int_range(value: Any, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EditorClipError(f"{name} must be an integer.") from exc
    if number < low or number > high:
        raise EditorClipError(f"{name} must be between {low} and {high}.")
    return number


def _float_min(value: Any, name: str, minimum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorClipError(f"{name} must be a number.") from exc
    if number < minimum:
        raise EditorClipError(f"{name} must be >= {minimum}.")
    return round(number, 6)


def _float_range(value: Any, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorClipError(f"{name} must be a number.") from exc
    if number < low or number > high:
        raise EditorClipError(f"{name} must be between {low} and {high}.")
    return float(number)


def _quantize_grid(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, str) and value.strip() in QUANTIZE_GRIDS:
        return QUANTIZE_GRIDS[value.strip()]
    grid = _float_range(value, "quantize_grid", 0.125, 4.0)
    if grid not in {0.125, 0.25, 0.5, 1.0, 2.0, 4.0}:
        raise EditorClipError("quantize_grid must be one of 0.125, 0.25, 0.5, 1.0, 2.0, 4.0.")
    return grid


def _round_beat(value: float) -> float:
    return round(float(value), 6)
