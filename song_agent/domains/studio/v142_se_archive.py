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

EditorPatchError = _make_deferred_global('EditorPatchError')
NoteKey = _make_deferred_global('NoteKey')
_bounded_text = _make_deferred_global('_bounded_text')
_chords = _make_deferred_global('_chords')
_clean_lyrics = _make_deferred_global('_clean_lyrics')
_section_index_for_plan = _make_deferred_global('_section_index_for_plan')

def bind_globals(namespace: dict[str, object]) -> None:
    global EditorPatchError, NoteKey, _bounded_text, _chords, _clean_lyrics, _section_index_for_plan
    EditorPatchError = namespace.get('EditorPatchError', EditorPatchError)
    NoteKey = namespace.get('NoteKey', NoteKey)
    _bounded_text = namespace.get('_bounded_text', _bounded_text)
    _chords = namespace.get('_chords', _chords)
    _clean_lyrics = namespace.get('_clean_lyrics', _clean_lyrics)
    _section_index_for_plan = namespace.get('_section_index_for_plan', _section_index_for_plan)
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




def _pop_matching_note_id(ids_by_key: dict[NoteKey, list[str]], note_key: NoteKey, selected: set[str] | None) -> str | None:
    candidates = ids_by_key.get(note_key)
    if not candidates:
        return None
    for index, note_id in enumerate(candidates):
        if selected is None or note_id in selected:
            return candidates.pop(index)
    return None

def _shift_note_keys_after_beat(note_keys_by_track_id: dict[str, dict[str, NoteKey | None]], beat: float, delta: float) -> None:
    if abs(delta) < 0.000001:
        return
    for note_keys_by_id in note_keys_by_track_id.values():
        for note_id, note_key in list(note_keys_by_id.items()):
            if note_key is not None and note_key[1] >= beat:
                note_keys_by_id[note_id] = (note_key[0], _round_beat(note_key[1] + delta), note_key[2], note_key[3])

def _delete_note_keys_in_range(note_keys_by_track_id: dict[str, dict[str, NoteKey | None]], start_beat: float, end_beat: float) -> None:
    for note_keys_by_id in note_keys_by_track_id.values():
        for note_id, note_key in list(note_keys_by_id.items()):
            if note_key is not None and start_beat <= note_key[1] < end_beat:
                note_keys_by_id[note_id] = None

def _trim_note_keys_to_total_beats(note_keys_by_track_id: dict[str, dict[str, NoteKey | None]], total_beats: float) -> None:
    for note_keys_by_id in note_keys_by_track_id.values():
        for note_id, note_key in list(note_keys_by_id.items()):
            if note_key is not None and note_key[1] + note_key[2] > total_beats + 0.001:
                note_keys_by_id[note_id] = None

def _remap_note_keys_by_section(
    note_keys_by_track_id: dict[str, dict[str, NoteKey | None]],
    old_spans_by_name: dict[str, tuple[float, float]],
    new_spans_by_name: dict[str, tuple[float, float]],
    *,
    move_names: set[str],
) -> None:
    for note_keys_by_id in note_keys_by_track_id.values():
        for note_id, note_key in list(note_keys_by_id.items()):
            if note_key is None:
                continue
            section_name = _section_name_for_note_key(note_key, old_spans_by_name)
            if section_name and section_name in move_names:
                old_start = old_spans_by_name[section_name][0]
                new_start = new_spans_by_name[section_name][0]
                note_keys_by_id[note_id] = (note_key[0], _round_beat(new_start + (note_key[1] - old_start)), note_key[2], note_key[3])

def _section_name_for_note_key(note_key: NoteKey, spans: dict[str, tuple[float, float]]) -> str | None:
    start_beat = note_key[1]
    for name, (start, end) in spans.items():
        if start <= start_beat < end:
            return name
    return None

def _beat_range(value: DomainDocument) -> tuple[float, float]:
    start = _float_min(value.get("start_beat"), "range.start_beat", 0.0)
    end = _float_min(value.get("end_beat"), "range.end_beat", 0.0)
    if end <= start:
        raise EditorPatchError("range.end_beat must be greater than range.start_beat.")
    return start, end

def _section_from_operation(operation: DomainDocument, sections: list[SongSection]) -> SongSection:
    name = _unique_section_name(operation.get("name"), sections)
    bars = _int_range(operation.get("bars"), "bars", 1, MAX_SECTION_BARS)
    chords = _chords(operation.get("chords") or sections[-1].chords if sections else operation.get("chords"))
    lyrics = _clean_lyrics(operation.get("lyrics", ""))
    return SongSection(name, 1, bars, chords, lyrics)

def _unique_section_name(value: object, sections: list[SongSection]) -> str:
    name = _bounded_text(value, MAX_SECTION_NAME_LENGTH)
    if not name:
        raise EditorPatchError("section name must not be empty.")
    existing = {section.name.strip().lower() for section in sections}
    if name.strip().lower() in existing:
        raise EditorPatchError(f"Duplicate section name: {name}.")
    return name

def _unique_track_name(value: object, tracks: list[TrackPlan]) -> str:
    name = _bounded_text(value, MAX_TRACK_NAME_LENGTH)
    if not name:
        raise EditorPatchError("track name must not be empty.")
    existing = {track.name.strip().lower() for track in tracks}
    if name.strip().lower() in existing:
        raise EditorPatchError(f"Duplicate track name: {name}.")
    return name

def _optional_after_section_index(
    operation: DomainDocument,
    sections: list[SongSection],
    base_names_by_id: dict[str, str] | None = None,
    *,
    allow_self: bool = True,
) -> int | None:
    value = operation.get("after_section_id")
    if value is None or str(value).strip() == "":
        return None
    candidate = {"section_id": value}
    index = _section_index_for_plan(candidate, sections, base_names_by_id)
    if not allow_self and operation.get("section_id") and str(operation.get("section_id")) == str(value):
        raise EditorPatchError("after_section_id must not equal section_id.")
    return index

def _section_start_beat(section: SongSection, beats_per_bar: int) -> float:
    return (section.start_bar - 1) * beats_per_bar

def _section_span(section: SongSection, beats_per_bar: int) -> tuple[float, float]:
    start = _section_start_beat(section, beats_per_bar)
    return start, start + section.bars * beats_per_bar

def _section_start_beat_at_index(sections: list[SongSection], index: int, beats_per_bar: int) -> float:
    if index < 0 or index > len(sections):
        raise EditorPatchError("section insert index is out of range.")
    return sum(section.bars for section in sections[:index]) * beats_per_bar

def _section_name_for_note(note: NoteEvent, spans: dict[str, tuple[float, float]]) -> str | None:
    for name, (start, end) in spans.items():
        if start <= note.start_beat < end:
            return name
    return None

def _assert_total_bars(sections: list[SongSection]) -> None:
    total = _total_bars_from_sections(sections)
    if total < 1 or total > MAX_TOTAL_BARS_AFTER_PATCH:
        raise EditorPatchError(f"edited song total bars must be between 1 and {MAX_TOTAL_BARS_AFTER_PATCH}.")

def _total_bars_from_sections(sections: list[SongSection]) -> int:
    return sum(section.bars for section in sections)

def _choice(value: object, name: str, choices: set[str]) -> str:
    selected = str(value or "").strip()
    if selected not in choices:
        raise EditorPatchError(f"{name} must be one of: {', '.join(sorted(choices))}.")
    return selected

def _missing_required_track_roles(tracks: list[TrackPlan]) -> list[str]:
    required = {"melody", "chords", "bass", "drums"}
    roles = {_track_role(track.name) for track in tracks}
    return sorted(required - roles)

def _validate_note_limits(tracks: list[TrackPlan]) -> None:
    total = sum(len(track.notes) for track in tracks)
    if total > MAX_TOTAL_NOTES_AFTER_PATCH:
        raise EditorPatchError(f"editor patch result supports at most {MAX_TOTAL_NOTES_AFTER_PATCH} total notes.")
    for track in tracks:
        if len(track.notes) > MAX_EDITOR_NOTES_PER_TRACK:
            raise EditorPatchError(f"Track {track.name} has too many notes after editor patch.")

def _ensure_note_bounds(note: NoteEvent, total_beats: float) -> None:
    if note.start_beat < 0:
        raise EditorPatchError("note start_beat must be >= 0.")
    if note.duration_beats <= 0:
        raise EditorPatchError("note duration_beats must be > 0.")
    if note.start_beat + note.duration_beats > total_beats + 0.001:
        raise EditorPatchError("note end exceeds song length.")

def _sorted_notes(notes: list[NoteEvent]) -> list[NoteEvent]:
    return sorted(notes, key=lambda note: (note.start_beat, note.pitch, note.duration_beats, note.velocity))

def _int_range(value: object, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EditorPatchError(f"{name} must be an integer.") from exc
    if number < low or number > high:
        raise EditorPatchError(f"{name} must be between {low} and {high}.")
    return number

def _float_min(value: object, name: str, minimum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorPatchError(f"{name} must be a number.") from exc
    if number < minimum:
        raise EditorPatchError(f"{name} must be >= {minimum}.")
    return _round_beat(number)

def _float_range(value: object, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorPatchError(f"{name} must be a number.") from exc
    if number < low or number > high:
        raise EditorPatchError(f"{name} must be between {low} and {high}.")
    return number

def _parse_iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _round_beat(value: float) -> float:
    return round(float(value), 6)

def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))

def _total_bars(plan: SongPlan) -> int:
    if not plan.sections:
        return 0
    return max(section.start_bar - 1 + section.bars for section in plan.sections)

def _beats_per_bar(plan: SongPlan) -> int:
    return 4 if plan.meter == "4/4" else 4

def _track_role(name: str) -> str:
    lower_name = name.lower()
    for role in ("melody", "chords", "bass", "drums"):
        if role in lower_name:
            return role
    return lower_name.strip()

def _quality_summary(plan: SongPlan) -> DomainDocument:
    quality = plan.quality or analyze_song_quality(plan)
    scores = quality.scores.to_dict() if quality.scores else {}
    return {"overall": scores.get("overall"), "dimension_scores": scores, "warnings": list(quality.warnings)}

def _preview_validator_report(plan: SongPlan, render_midi: bool) -> DomainDocument:
    return {
        "status": "passed",
        "checks": ["song_plan_schema", "song_plan_validation", *(("midi_render",) if render_midi else ())],
        "title": plan.title,
        "midi_exists": False,
        "midi_size": 0,
        "checked_at": now_iso(),
    }

def _append_preview_event(preview_dir: Path, event_type: str, payload: DomainDocument, now: str | None = None) -> None:
    event = {"timestamp": now or now_iso(), "type": event_type, "payload": sanitize_metadata(payload)}
    with (preview_dir / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

def _optional_str(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)
