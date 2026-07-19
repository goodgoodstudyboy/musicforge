# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_list as _as_list
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
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

CreativeAsset = _make_deferred_global('CreativeAsset')

def bind_globals(namespace: dict[str, object]) -> None:
    global CreativeAsset
    CreativeAsset = namespace.get('CreativeAsset', CreativeAsset)
    _bind_deferred_defaults(namespace)


ASSET_SCHEMA_VERSION = 1
MAX_ASSET_JSON_BYTES = 128_000
MAX_ASSET_NOTES = 1024
MAX_ASSET_REFS = 5
ASSET_TYPES = {
    "motif",
    "chord_progression",
    "drum_pattern",
    "bass_pattern",
    "section_template",
    "arrangement_template",
    "lyric_hook",
}
BLOCKED_CONTENT_KEYS = {
    "absolute_path",
    "api_key",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "secret",
    "token",
}
RENDERABLE_TYPES = {"motif", "chord_progression", "drum_pattern", "bass_pattern", "section_template"}




def _extract_asset_payload(
    plan: SongPlan,
    asset_type: str,
    *,
    section_name: str,
    track_name: str,
    source: DomainDocument,
    tags: list[str],
    name_prefix: str,
) -> DomainDocument:
    section = _select_section(plan, section_name)
    quality_score = plan.quality.scores.overall if plan.quality and plan.quality.scores else None
    if asset_type == "motif":
        track = _select_track(plan, track_name, "melody")
        notes = _notes_in_section(track, section)[:16]
        if not notes:
            raise ValueError("No melody notes found for motif asset.")
        content = _motif_content(plan, section, track, notes)
        name = f"{name_prefix or plan.title} motif"
    elif asset_type == "chord_progression":
        content = {"kind": "chord_progression", "section_name": section.name, "chords": list(section.chords), "bars": section.bars, "harmonic_rhythm": 4.0, "key": plan.key}
        name = f"{name_prefix or plan.title} chords"
    elif asset_type == "drum_pattern":
        track = _select_track(plan, track_name, "drums")
        notes = _notes_in_section(track, section)[:MAX_ASSET_NOTES]
        content = {"kind": "drum_pattern", "section_name": section.name, "track_name": track.name, "notes": [_relative_note(note, section) for note in notes], "meter": plan.meter}
        name = f"{name_prefix or plan.title} drums"
    elif asset_type == "bass_pattern":
        track = _select_track(plan, track_name, "bass")
        notes = _notes_in_section(track, section)[:MAX_ASSET_NOTES]
        content = {"kind": "bass_pattern", "section_name": section.name, "track_name": track.name, "notes": [_relative_note(note, section) for note in notes], "root_motion": _root_motion(notes)}
        name = f"{name_prefix or plan.title} bass"
    elif asset_type == "section_template":
        content = {"kind": "section_template", "section_name": section.name, "bars": section.bars, "chords": list(section.chords)}
        name = f"{name_prefix or plan.title} section"
    elif asset_type == "arrangement_template":
        content = {"kind": "arrangement_template", "sections": [item.to_dict() for item in plan.sections], "tracks": [{"name": track.name, "instrument": track.instrument} for track in plan.tracks]}
        name = f"{name_prefix or plan.title} arrangement"
    elif asset_type == "lyric_hook":
        content = {"kind": "lyric_hook", "section_name": section.name, "text": (section.lyrics or "")[:1000], "language": ""}
        name = f"{name_prefix or plan.title} lyric hook"
    else:
        raise ValueError(f"Unsupported asset_type: {asset_type}.")
    return {
        "asset_type": asset_type,
        "name": name,
        "description": f"Extracted {asset_type} from {plan.title}.",
        "tags": tags,
        "style": str(source.get("style") or ""),
        "key": plan.key,
        "tempo_bpm": plan.tempo_bpm,
        "meter": plan.meter,
        "duration_beats": max(1.0, float(section.bars * 4)),
        "quality_score": quality_score,
        "source": {**source, "section_name": section.name, "track_name": content.get("track_name")},
        "content": content,
        "source_fragment": {"schema_version": 1, "section": section.to_dict(), "content": content, "extracted_at": now_iso()},
    }

def _motif_content(plan: SongPlan, section: SongSection, track: TrackPlan, notes: list[NoteEvent]) -> DomainDocument:
    if plan.quality and plan.quality.primary_motif and plan.quality.primary_motif.pitch_intervals:
        motif = plan.quality.primary_motif
        return {
            "kind": "motif",
            "section_name": section.name,
            "track_name": track.name,
            "rhythm_pattern": list(motif.rhythm_pattern),
            "pitch_intervals": list(motif.pitch_intervals),
            "anchor_pitch": notes[0].pitch,
            "notes": [_relative_note(note, section) for note in notes],
        }
    anchor = notes[0].pitch
    starts = [note.start_beat for note in notes]
    rhythm = [round(note.duration_beats, 3) for note in notes[:8]]
    intervals = [note.pitch - anchor for note in notes[:8]]
    return {
        "kind": "motif",
        "section_name": section.name,
        "track_name": track.name,
        "rhythm_pattern": rhythm,
        "pitch_intervals": intervals,
        "anchor_pitch": anchor,
        "start_pattern": [round(start - starts[0], 3) for start in starts[:8]],
        "notes": [_relative_note(note, section) for note in notes],
    }

def _select_section(plan: SongPlan, section_name: str) -> SongSection:
    if section_name:
        for section in plan.sections:
            if section.name == section_name:
                return section
        raise ValueError(f"Section not found: {section_name}.")
    if plan.quality:
        for hook in plan.quality.hook_sections:
            for section in plan.sections:
                if section.name == hook:
                    return section
    for section in plan.sections:
        if "chorus" in section.name.lower():
            return section
    return max(plan.sections, key=lambda section: section.bars)

def _select_track(plan: SongPlan, track_name: str, role: str) -> TrackPlan:
    if track_name:
        for track in plan.tracks:
            if track.name == track_name:
                return track
        raise ValueError(f"Track not found: {track_name}.")
    for track in plan.tracks:
        text = f"{track.name} {track.instrument}".lower()
        if role in text or (role == "drums" and "drum" in text):
            return track
    raise ValueError(f"{role} track not found.")

def _notes_in_section(track: TrackPlan, section: SongSection) -> list[NoteEvent]:
    start = (section.start_bar - 1) * 4
    end = start + section.bars * 4
    return [note for note in track.notes if note.start_beat >= start and note.start_beat < end]

def _relative_note(note: NoteEvent, section: SongSection) -> DomainDocument:
    section_start = (section.start_bar - 1) * 4
    return {
        "pitch": note.pitch,
        "start_beat": round(note.start_beat - section_start, 3),
        "duration_beats": round(note.duration_beats, 3),
        "velocity": note.velocity,
    }

def _asset_notes(asset: CreativeAsset) -> list[NoteEvent]:
    content = asset.content
    raw_notes = content.get("notes")
    if isinstance(raw_notes, list) and raw_notes:
        return [NoteEvent.from_dict(dict(note)) for note in raw_notes[:MAX_ASSET_NOTES] if isinstance(note, dict)]
    if asset.asset_type == "motif":
        anchor = int(content.get("anchor_pitch") or 64)
        intervals = [int(item) for item in content.get("pitch_intervals", [0, 3, 5, 7])][:16]
        rhythm = [float(item) for item in content.get("rhythm_pattern", [1.0] * len(intervals))]
        notes = []
        cursor = 0.0
        for index, interval in enumerate(intervals):
            duration = rhythm[index % len(rhythm)] if rhythm else 1.0
            notes.append(NoteEvent(anchor + interval, cursor, max(0.25, duration), 92))
            cursor += max(0.25, duration)
        return notes
    if asset.asset_type in {"chord_progression", "section_template"}:
        notes = []
        for index, chord in enumerate(_asset_chords(asset)):
            for pitch in _chord_pitches(chord):
                notes.append(NoteEvent(pitch, float(index * 4), 3.75, 72))
        return notes
    return [NoteEvent(64, 0.0, 1.0, 90)]

def _asset_chords(asset: CreativeAsset) -> list[str]:
    chords = asset.content.get("chords")
    if isinstance(chords, list) and chords:
        return [str(chord) for chord in chords]
    return ["Cmaj7"]

def _apply_chord_asset(sections: list[SongSection], asset: CreativeAsset) -> list[SongSection]:
    chords = _asset_chords(asset)
    target_index = 0
    for index, section in enumerate(sections):
        if "chorus" in section.name.lower():
            target_index = index
            break
    updated = []
    for index, section in enumerate(sections):
        updated.append(SongSection(section.name, section.start_bar, section.bars, chords if index == target_index else section.chords, section.lyrics))
    return updated

def _apply_motif_asset(tracks: list[TrackPlan], sections: list[SongSection], asset: CreativeAsset) -> list[TrackPlan]:
    target = next((section for section in sections if "chorus" in section.name.lower()), sections[0])
    section_start = (target.start_bar - 1) * 4
    asset_notes = _asset_notes(asset)
    updated_tracks = []
    for track in tracks:
        if "melody" not in track.name.lower():
            updated_tracks.append(track)
            continue
        outside = [note for note in track.notes if not (note.start_beat >= section_start and note.start_beat < section_start + target.bars * 4)]
        injected = [NoteEvent(note.pitch, section_start + note.start_beat, note.duration_beats, note.velocity) for note in asset_notes if note.start_beat < target.bars * 4]
        updated_tracks.append(TrackPlan(track.name, track.instrument, sorted([*outside, *injected], key=lambda note: note.start_beat)))
    return updated_tracks

def _chord_pitches(chord_name: str) -> list[int]:
    chord_map = {
        "Cmaj7": [60, 64, 67, 71],
        "Am7": [57, 60, 64, 67],
        "Dm7": [62, 65, 69, 72],
        "Fmaj7": [53, 57, 60, 64],
        "G7": [55, 59, 62, 65],
        "E7": [52, 56, 59, 62],
    }
    return chord_map.get(chord_name, [60, 64, 67])

def _with_preview(asset: CreativeAsset, **values: object) -> CreativeAsset:
    preview = _preview_dict(asset.preview)
    preview.update(values)
    return CreativeAsset.from_dict({**asset.to_dict(), "preview": preview, "updated_at": now_iso()})

def _preview_dict(value: object) -> DomainDocument:
    data = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "midi_status": str(data.get("midi_status") or "not_started"),
        "midi_size_bytes": int(data.get("midi_size_bytes") or 0),
        "midi_url": None if data.get("midi_url") is None else str(data.get("midi_url")),
        "midi_error": None if data.get("midi_error") is None else str(data.get("midi_error")),
        "audio_status": str(data.get("audio_status") or "not_started"),
        "audio_size_bytes": int(data.get("audio_size_bytes") or 0),
        "audio_url": None if data.get("audio_url") is None else str(data.get("audio_url")),
        "audio_error": None if data.get("audio_error") is None else str(data.get("audio_error")),
    }

def _safe_asset_file(asset_dir: Path, filename: str) -> Path:
    base = asset_dir.resolve()
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside asset directory.") from exc
    return target

def _validate_content(value: object) -> None:
    size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    if size > MAX_ASSET_JSON_BYTES:
        raise ValueError(f"asset content must be {MAX_ASSET_JSON_BYTES} bytes or fewer.")
    _scan_blocked_content(value)
    notes = value.get("notes") if isinstance(value, dict) else None
    if isinstance(notes, list) and len(notes) > MAX_ASSET_NOTES:
        raise ValueError(f"asset notes supports at most {MAX_ASSET_NOTES} notes.")

def _scan_blocked_content(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in BLOCKED_CONTENT_KEYS:
                raise ValueError(f"asset content contains blocked field: {key}.")
            _scan_blocked_content(item)
    elif isinstance(value, list):
        for item in value:
            _scan_blocked_content(item)

def _validate_asset_size(asset: CreativeAsset) -> None:
    size = len(json.dumps(asset.to_dict(), ensure_ascii=False).encode("utf-8"))
    if size > MAX_ASSET_JSON_BYTES:
        raise ValueError(f"asset JSON must be {MAX_ASSET_JSON_BYTES} bytes or fewer.")

def _bounded_text(value: object, field_name: str, max_length: int) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return text

def _clean_tags(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list.")
    tags = []
    for item in value:
        tag = str(item).strip()
        if not tag:
            continue
        if len(tag) > 48:
            raise ValueError("asset tags must be 48 characters or fewer.")
        if tag not in tags:
            tags.append(tag)
    if len(tags) > 32:
        raise ValueError("asset tags supports at most 32 items.")
    return tags

def _optional_score(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    score = int(value)
    if score < 0 or score > 100:
        raise ValueError("quality_score must be between 0 and 100.")
    return score

def _asset_matches(asset: CreativeAsset, filters: DomainDocument) -> bool:
    q = str(filters.get("q") or "").strip().lower()
    if q and q not in f"{asset.name} {asset.description} {' '.join(asset.tags)}".lower():
        return False
    type_filter = str(filters.get("type") or filters.get("asset_type") or "").strip()
    if type_filter and asset.asset_type != type_filter:
        return False
    tag = str(filters.get("tag") or "").strip()
    if tag and tag not in asset.tags:
        return False
    style = str(filters.get("style") or "").strip().lower()
    if style and style not in asset.style.lower():
        return False
    mood = str(filters.get("mood") or "").strip().lower()
    if mood and mood not in asset.mood.lower():
        return False
    if filters.get("favorite") in {True, "1", "true", "yes"} and not asset.favorite:
        return False
    min_quality = filters.get("min_quality")
    if min_quality not in {None, ""} and (asset.quality_score is None or asset.quality_score < int(min_quality)):
        return False
    return True

def _strength(value: object) -> float:
    strength = 0.7 if value is None or str(value).strip() == "" else float(value)
    if strength < 0 or strength > 1:
        raise ValueError("asset ref strength must be between 0 and 1.")
    return round(strength, 3)

def _default_asset_role(asset_type: str) -> str:
    return {
        "motif": "motif_reference",
        "chord_progression": "chord_reference",
        "drum_pattern": "drum_reference",
        "bass_pattern": "bass_reference",
    }.get(asset_type, "reference")

def _asset_source_summary(source: DomainDocument) -> DomainDocument:
    return {
        key: str(source.get(key) or "")
        for key in ("source_type", "project_id", "version_id", "job_id", "candidate_group_id", "candidate_id", "section_name", "track_name")
        if source.get(key) is not None
    }

def _append_asset_event(asset_dir: Path, event_type: str, payload: DomainDocument, timestamp: str | None = None) -> None:
    event = {"timestamp": timestamp or now_iso(), "type": event_type, "payload": payload}
    asset_dir.mkdir(parents=True, exist_ok=True)
    with (asset_dir / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

def _root_motion(notes: list[NoteEvent]) -> list[int]:
    return [note.pitch % 12 for note in notes[:16]]
