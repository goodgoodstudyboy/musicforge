# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.coercion import as_float as _as_float, as_int as _as_int
from song_agent.platform.contracts.documents import DomainDocument
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path
from typing import Mapping as Mapping
from song_agent.domains.creation.edits import SUPPORTED_HARMONY_CHORDS as SUPPORTED_HARMONY_CHORDS
from song_agent.domains.creation.music_quality import attach_quality as attach_quality, analyze_song_quality as analyze_song_quality
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan

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

EditorPatch = _make_deferred_global('EditorPatch')
EditorPatchError = _make_deferred_global('EditorPatchError')
EditorPatchResult = _make_deferred_global('EditorPatchResult')
NoteKey = _make_deferred_global('NoteKey')
_CONTROL_CHARS = _make_deferred_global('_CONTROL_CHARS')
_SUPPORTED_CHORDS_BY_LOWER = _make_deferred_global('_SUPPORTED_CHORDS_BY_LOWER')
_assert_total_bars = _make_deferred_global('_assert_total_bars')
_beat_range = _make_deferred_global('_beat_range')
_clip_inserts_from_metadata = _make_deferred_global('_clip_inserts_from_metadata')
_ensure_note_bounds = _make_deferred_global('_ensure_note_bounds')
_float_min = _make_deferred_global('_float_min')
_int_range = _make_deferred_global('_int_range')
_pop_matching_note_id = _make_deferred_global('_pop_matching_note_id')
_round_beat = _make_deferred_global('_round_beat')
_section_name_for_note = _make_deferred_global('_section_name_for_note')
_sorted_notes = _make_deferred_global('_sorted_notes')
_structure_edit_summary = _make_deferred_global('_structure_edit_summary')
_template_inserts_from_metadata = _make_deferred_global('_template_inserts_from_metadata')
summarize_editor_patch = _make_deferred_global('summarize_editor_patch')

def bind_globals(namespace: dict[str, object]) -> None:
    global EditorPatch, EditorPatchError, EditorPatchResult, NoteKey, _CONTROL_CHARS, _SUPPORTED_CHORDS_BY_LOWER, _assert_total_bars, _beat_range
    global _clip_inserts_from_metadata, _ensure_note_bounds, _float_min, _int_range, _pop_matching_note_id, _round_beat, _section_name_for_note
    global _sorted_notes, _structure_edit_summary, _template_inserts_from_metadata, summarize_editor_patch
    EditorPatch = namespace.get('EditorPatch', EditorPatch)
    EditorPatchError = namespace.get('EditorPatchError', EditorPatchError)
    EditorPatchResult = namespace.get('EditorPatchResult', EditorPatchResult)
    NoteKey = namespace.get('NoteKey', NoteKey)
    _CONTROL_CHARS = namespace.get('_CONTROL_CHARS', _CONTROL_CHARS)
    _SUPPORTED_CHORDS_BY_LOWER = namespace.get('_SUPPORTED_CHORDS_BY_LOWER', _SUPPORTED_CHORDS_BY_LOWER)
    _assert_total_bars = namespace.get('_assert_total_bars', _assert_total_bars)
    _beat_range = namespace.get('_beat_range', _beat_range)
    _clip_inserts_from_metadata = namespace.get('_clip_inserts_from_metadata', _clip_inserts_from_metadata)
    _ensure_note_bounds = namespace.get('_ensure_note_bounds', _ensure_note_bounds)
    _float_min = namespace.get('_float_min', _float_min)
    _int_range = namespace.get('_int_range', _int_range)
    _pop_matching_note_id = namespace.get('_pop_matching_note_id', _pop_matching_note_id)
    _round_beat = namespace.get('_round_beat', _round_beat)
    _section_name_for_note = namespace.get('_section_name_for_note', _section_name_for_note)
    _sorted_notes = namespace.get('_sorted_notes', _sorted_notes)
    _structure_edit_summary = namespace.get('_structure_edit_summary', _structure_edit_summary)
    _template_inserts_from_metadata = namespace.get('_template_inserts_from_metadata', _template_inserts_from_metadata)
    summarize_editor_patch = namespace.get('summarize_editor_patch', summarize_editor_patch)
    _bind_deferred_defaults(namespace)


EDITOR_PREVIEW_SCHEMA_VERSION = 1
EDITOR_PATCH_SCHEMA_VERSION = 1
MAX_EDITOR_TRACKS = 32
MAX_EDITOR_NOTES_PER_TRACK = 4096
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




def editor_edit_metadata(
    *,
    project_id: str,
    parent_version_id: str,
    parent_job_id: str,
    preview_id: str,
    patch: EditorPatch,
    result: EditorPatchResult,
    created_at: str | None = None,
) -> DomainDocument:
    summary = summarize_editor_patch(result)
    structure = _structure_edit_summary(patch.operations)
    clip_inserts = _clip_inserts_from_metadata(patch.metadata)
    template_inserts = _template_inserts_from_metadata(patch.metadata)
    edit_type = "visual_editor_template_insert" if template_inserts else "visual_editor_clip_insert" if clip_inserts else "manual_editor_edit"
    return sanitize_metadata(
        {
            "schema_version": 2,
            "edit_source": "visual_editor",
            "edit_type": edit_type,
            "provider_mode": "local",
            "project_id": project_id,
            "parent_version_id": parent_version_id,
            "parent_job_id": parent_job_id,
            "preview_id": preview_id,
            "base_plan_hash": patch.base_plan_hash,
            "label": patch.label,
            "operation_count": summary["operation_count"],
            "changed_sections": summary["changed_sections"],
            "changed_tracks": summary["changed_tracks"],
            "clip_inserts": clip_inserts,
            "template_inserts": template_inserts,
            "summary": {
                **summary["operation_counts"],
                "changed_sections": summary["changed_sections"],
                "changed_tracks": summary["changed_tracks"],
                "clip_insert_count": len(clip_inserts),
                "template_insert_count": len(template_inserts),
            },
            "structure": structure,
            "warnings": summary["warnings"],
            "created_at": created_at or now_iso(),
        }
    )

def song_plan_hash(plan: SongPlan) -> str:
    payload = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def validate_editor_preview_id(preview_id: str) -> str:
    if not re.match(r"^preview-[0-9]{3,6}$", preview_id):
        raise ValueError("Invalid editor preview id.")
    return preview_id

def _preview_audio_status(value: object) -> str:
    status = str(value or "not_started").strip()
    if status not in {"not_started", "running", "completed", "failed"}:
        return "not_started"
    return status

def section_id_for_index(index: int) -> str:
    return f"section-{index + 1:03d}"

def track_id_for_index(index: int) -> str:
    return f"track-{index + 1:03d}"

def note_id_for(track_id: str, note_index: int, note: NoteEvent) -> str:
    raw = f"{track_id}:{note_index}:{note.pitch}:{note.start_beat:.6f}:{note.duration_beats:.6f}:{note.velocity}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"note-{track_id}-{note_index + 1:04d}-{digest}"

def _section_index(operation: DomainDocument) -> int:
    section_id = str(operation.get("section_id") or "").strip()
    if not re.match(r"^section-[0-9]{3}$", section_id):
        raise EditorPatchError("section_id is required.")
    index = int(section_id.split("-")[1]) - 1
    if index < 0:
        raise EditorPatchError("section_id is out of range.")
    return index

def _section_index_for_plan(operation: DomainDocument, sections: list[SongSection], base_names_by_id: Mapping[str, str | None] | None = None) -> int:
    section_id = str(operation.get("section_id") or "").strip()
    if base_names_by_id is not None:
        name = base_names_by_id.get(section_id)
        if section_id not in base_names_by_id:
            raise EditorPatchError("section_id is out of range.")
        if name is None:
            raise EditorPatchError("section_id is no longer available in this patch.")
        for index, section in enumerate(sections):
            if section.name == name:
                return index
        raise EditorPatchError(f"Section {name} is no longer available in this patch.")
    index = _section_index(operation)
    if index >= len(sections):
        raise EditorPatchError("section_id is out of range.")
    return index

def _track_index(operation: DomainDocument) -> int:
    track_id = str(operation.get("track_id") or "").strip()
    if not re.match(r"^track-[0-9]{3}$", track_id):
        raise EditorPatchError("track_id is required.")
    index = int(track_id.split("-")[1]) - 1
    if index < 0:
        raise EditorPatchError("track_id is out of range.")
    return index

def _track_index_for_plan(operation: DomainDocument, tracks: list[TrackPlan], base_names_by_id: dict[str, str | None] | None = None) -> int:
    track_id = str(operation.get("track_id") or "").strip()
    if base_names_by_id is not None:
        name = base_names_by_id.get(track_id)
        if track_id not in base_names_by_id:
            raise EditorPatchError("track_id is out of range.")
        if name is None:
            raise EditorPatchError("track_id is no longer available in this patch.")
        for index, track in enumerate(tracks):
            if track.name == name:
                return index
        raise EditorPatchError(f"Track {name} is no longer available in this patch.")
    index = _track_index(operation)
    if index >= len(tracks):
        raise EditorPatchError("track_id is out of range.")
    return index

def _chords(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise EditorPatchError("chords must be a non-empty list.")
    if len(value) > 16:
        raise EditorPatchError("chords supports at most 16 chords.")
    chords = []
    invalid = []
    for item in value:
        chord = _SUPPORTED_CHORDS_BY_LOWER.get(str(item).strip().lower())
        if chord is None:
            invalid.append(str(item))
        else:
            chords.append(chord)
    if invalid:
        raise EditorPatchError(f"Unsupported chord names: {', '.join(invalid)}.")
    return chords

def _clean_lyrics(value: object) -> str:
    lyrics = sanitize_sensitive_text(str(value or ""))
    if _CONTROL_CHARS.search(lyrics):
        raise EditorPatchError("lyrics must not contain control characters.")
    if len(lyrics) > MAX_LYRICS_LENGTH:
        raise EditorPatchError(f"lyrics must be {MAX_LYRICS_LENGTH} characters or fewer.")
    return lyrics

def _bounded_text(value: object, max_length: int) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    if _CONTROL_CHARS.search(text):
        raise EditorPatchError("text fields must not contain control characters.")
    return text[:max_length].rstrip()

def _note(value: object, total_beats: float) -> NoteEvent:
    if not isinstance(value, dict):
        raise EditorPatchError("note must be an object.")
    note = NoteEvent(
        pitch=_int_range(value.get("pitch"), "pitch", 0, 127),
        start_beat=_float_min(value.get("start_beat"), "start_beat", 0.0),
        duration_beats=_float_min(value.get("duration_beats"), "duration_beats", 0.0001),
        velocity=_int_range(value.get("velocity", 90), "velocity", 1, 127),
    )
    _ensure_note_bounds(note, total_beats)
    return note

def _update_note(
    track: TrackPlan,
    note_keys_by_id: dict[str, NoteKey | None],
    operation: DomainDocument,
    total_beats: float,
) -> tuple[list[NoteEvent], NoteEvent]:
    note_id = str(operation.get("note_id") or "").strip()
    patch = operation.get("patch")
    if not isinstance(patch, dict) or not patch:
        raise EditorPatchError("update_note patch must be a non-empty object.")
    unknown = sorted(set(patch) - NOTE_PATCH_FIELDS)
    if unknown:
        raise EditorPatchError(f"update_note patch contains unsupported fields: {', '.join(unknown)}.")
    target_key = note_keys_by_id.get(note_id)
    if target_key is None:
        if note_id in note_keys_by_id:
            raise EditorPatchError(f"Note {note_id} is no longer available in this patch.")
        raise EditorPatchError(f"Unknown note id: {note_id}.")
    notes = list(track.notes)
    target_index = _note_index_by_key(notes, target_key, note_id)
    current = notes[target_index]
    updated = NoteEvent(
        pitch=_int_range(patch.get("pitch", current.pitch), "pitch", 0, 127),
        start_beat=_float_min(patch.get("start_beat", current.start_beat), "start_beat", 0.0),
        duration_beats=_float_min(patch.get("duration_beats", current.duration_beats), "duration_beats", 0.0001),
        velocity=_int_range(patch.get("velocity", current.velocity), "velocity", 1, 127),
    )
    _ensure_note_bounds(updated, total_beats)
    notes[target_index] = updated
    return _sorted_notes(notes), updated

def _note_ids(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise EditorPatchError("note_ids must be a non-empty list.")
    if len(value) > MAX_NOTE_IDS_PER_OPERATION:
        raise EditorPatchError(f"note_ids supports at most {MAX_NOTE_IDS_PER_OPERATION} notes.")
    result = [str(item).strip() for item in value if str(item).strip()]
    if len(result) != len(value):
        raise EditorPatchError("note_ids must not contain empty ids.")
    return result

def _base_note_keys_by_track_id(state: DomainDocument) -> dict[str, dict[str, NoteKey | None]]:
    result: dict[str, dict[str, NoteKey | None]] = {}
    for track in state.get("tracks", []):
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("track_id") or "")
        note_keys: dict[str, NoteKey | None] = {}
        for note in track.get("notes", []):
            if isinstance(note, dict) and note.get("note_id"):
                note_keys[str(note["note_id"])] = _note_key_from_mapping(note)
        result[track_id] = note_keys
    return result

def _note_key(note: NoteEvent) -> NoteKey:
    return (int(note.pitch), _round_beat(note.start_beat), _round_beat(note.duration_beats), int(note.velocity))

def _note_key_from_mapping(note: DomainDocument) -> NoteKey:
    return (
        _as_int(note.get("pitch")),
        _round_beat(_as_float(note.get("start_beat"))),
        _round_beat(_as_float(note.get("duration_beats"))),
        int(note.get("velocity", 90)),
    )

def _note_index_by_key(notes: list[NoteEvent], target_key: NoteKey, note_id: str) -> int:
    for index, note in enumerate(notes):
        if _note_key(note) == target_key:
            return index
    raise EditorPatchError(f"Note {note_id} is no longer available in this patch.")

def _identity_by_id(names_by_id: dict[str, str | None]) -> dict[str, str | None]:
    return dict(names_by_id)

def _note_identity_by_track_id(note_keys_by_track_id: dict[str, dict[str, NoteKey | None]]) -> dict[str, dict[str, dict[str, float | int]]]:
    identity: dict[str, dict[str, dict[str, float | int]]] = {}
    for track_id, note_keys_by_id in note_keys_by_track_id.items():
        notes = {}
        for note_id, note_key in note_keys_by_id.items():
            if note_key is not None:
                notes[note_id] = {
                    "pitch": note_key[0],
                    "start_beat": note_key[1],
                    "duration_beats": note_key[2],
                    "velocity": note_key[3],
                }
        identity[track_id] = notes
    return identity

def normalize_sections(sections: list[SongSection]) -> list[SongSection]:
    normalized = []
    next_start = 1
    seen: set[str] = set()
    for section in sections:
        if section.bars < 1:
            raise EditorPatchError("section bars must be >= 1.")
        if section.name.strip().lower() in seen:
            raise EditorPatchError(f"Duplicate section name: {section.name}.")
        seen.add(section.name.strip().lower())
        normalized.append(SongSection(section.name, next_start, section.bars, list(section.chords), section.lyrics))
        next_start += section.bars
    _assert_total_bars(normalized)
    return normalized

def shift_notes_after_beat(tracks: list[TrackPlan], beat: float, delta: float) -> list[TrackPlan]:
    if abs(delta) < 0.000001:
        return tracks
    shifted = []
    for track in tracks:
        notes = [
            NoteEvent(note.pitch, _round_beat(note.start_beat + delta), note.duration_beats, note.velocity)
            if note.start_beat >= beat
            else note
            for note in track.notes
        ]
        shifted.append(TrackPlan(track.name, track.instrument, _sorted_notes(notes)))
    return shifted

def delete_notes_in_range(tracks: list[TrackPlan], start_beat: float, end_beat: float) -> list[TrackPlan]:
    return [
        TrackPlan(track.name, track.instrument, [note for note in track.notes if not (start_beat <= note.start_beat < end_beat)])
        for track in tracks
    ]

def copy_notes_in_range(tracks: list[TrackPlan], start_beat: float, end_beat: float, target_start_beat: float) -> list[TrackPlan]:
    copied_tracks = []
    for track in tracks:
        copies = [
            NoteEvent(note.pitch, _round_beat(target_start_beat + (note.start_beat - start_beat)), note.duration_beats, note.velocity)
            for note in track.notes
            if start_beat <= note.start_beat < end_beat
        ]
        copied_tracks.append(TrackPlan(track.name, track.instrument, _sorted_notes([*track.notes, *copies])))
    return copied_tracks

def remap_notes_by_section(
    tracks: list[TrackPlan],
    old_spans_by_name: dict[str, tuple[float, float]],
    new_spans_by_name: dict[str, tuple[float, float]],
    *,
    move_names: set[str],
) -> list[TrackPlan]:
    remapped = []
    for track in tracks:
        notes = []
        for note in track.notes:
            section_name = _section_name_for_note(note, old_spans_by_name)
            if section_name and section_name in move_names:
                old_start = old_spans_by_name[section_name][0]
                new_start = new_spans_by_name[section_name][0]
                notes.append(NoteEvent(note.pitch, _round_beat(new_start + (note.start_beat - old_start)), note.duration_beats, note.velocity))
            else:
                notes.append(note)
        remapped.append(TrackPlan(track.name, track.instrument, _sorted_notes(notes)))
    return remapped

def trim_notes_to_total_beats(tracks: list[TrackPlan], total_beats: float, warnings: list[str]) -> list[TrackPlan]:
    trimmed = []
    removed = 0
    for track in tracks:
        notes = []
        for note in track.notes:
            if note.start_beat + note.duration_beats <= total_beats + 0.001:
                notes.append(note)
            else:
                removed += 1
        trimmed.append(TrackPlan(track.name, track.instrument, notes))
    if removed:
        warnings.append(f"Removed {removed} notes beyond the edited song length.")
    return trimmed

def _note_selector(operation: DomainDocument, track: TrackPlan) -> DomainDocument:
    if isinstance(operation.get("note_ids"), list):
        return {"ids": set(_note_ids(operation.get("note_ids")))}
    if isinstance(operation.get("range"), dict):
        beat_range = _beat_range(operation["range"])
        if not any(beat_range[0] <= note.start_beat < beat_range[1] for note in track.notes):
            raise EditorPatchError("range did not select any notes.")
        return {"range": beat_range}
    raise EditorPatchError("operation requires note_ids or range.")

def _map_selected_notes(
    track: TrackPlan,
    *,
    total_beats: float,
    mapper: object,
    note_keys_by_id: dict[str, NoteKey | None] | None = None,
    ids: set[str] | None = None,
    beat_range: tuple[float, float] | None = None,
) -> tuple[list[NoteEvent], dict[str, NoteKey]]:
    if ids is not None:
        _validate_selected_note_ids(note_keys_by_id or {}, ids)
    selected = 0
    mapped = []
    updated_keys: dict[str, NoteKey] = {}
    matched_ids: set[str] = set()
    ids_by_key = _note_ids_by_key(note_keys_by_id or {})
    for note in track.notes:
        note_key = _note_key(note)
        note_id = _pop_matching_note_id(ids_by_key, note_key, ids) if ids is not None else None
        range_match = beat_range is not None and beat_range[0] <= note.start_beat < beat_range[1]
        if note_id is None and ids is None and range_match:
            note_id = _pop_matching_note_id(ids_by_key, note_key, None)
        match = note_id is not None or range_match
        if match:
            updated = mapper(note)
            _ensure_note_bounds(updated, total_beats)
            mapped.append(updated)
            if note_id:
                matched_ids.add(note_id)
                updated_keys[note_id] = _note_key(updated)
            selected += 1
        else:
            mapped.append(note)
    if ids is not None:
        unavailable = ids - matched_ids
        if unavailable:
            raise EditorPatchError(f"Note ids are no longer available in this patch: {', '.join(sorted(unavailable)[:5])}.")
    if selected == 0:
        raise EditorPatchError("operation did not select any notes.")
    return _sorted_notes(mapped), updated_keys

def _delete_selected_notes(
    track: TrackPlan,
    note_keys_by_id: dict[str, NoteKey | None],
    selected: set[str],
) -> tuple[list[NoteEvent], set[str]]:
    _validate_selected_note_ids(note_keys_by_id, selected)
    ids_by_key = _note_ids_by_key(note_keys_by_id)
    notes: list[NoteEvent] = []
    deleted: set[str] = set()
    for note in track.notes:
        note_id = _pop_matching_note_id(ids_by_key, _note_key(note), selected)
        if note_id:
            deleted.add(note_id)
        else:
            notes.append(note)
    unavailable = selected - deleted
    if unavailable:
        raise EditorPatchError(f"Note ids are no longer available in this patch: {', '.join(sorted(unavailable)[:5])}.")
    return notes, deleted

def _validate_selected_note_ids(note_keys_by_id: dict[str, NoteKey | None], selected: set[str]) -> None:
    missing = selected - set(note_keys_by_id)
    if missing:
        raise EditorPatchError(f"Unknown note ids: {', '.join(sorted(missing)[:5])}.")
    unavailable = {note_id for note_id in selected if note_keys_by_id.get(note_id) is None}
    if unavailable:
        raise EditorPatchError(f"Note ids are no longer available in this patch: {', '.join(sorted(unavailable)[:5])}.")

def _note_ids_by_key(note_keys_by_id: dict[str, NoteKey | None]) -> dict[NoteKey, list[str]]:
    ids_by_key: dict[NoteKey, list[str]] = {}
    for note_id, note_key in note_keys_by_id.items():
        if note_key is not None:
            ids_by_key.setdefault(note_key, []).append(note_id)
    return ids_by_key
