# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_int as _as_int, document_or as _document_or, list_or as _list_or
import hashlib as hashlib
import json as json
import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.assets import AssetStore as AssetStore, CreativeAsset as CreativeAsset, asset_content_summary as asset_content_summary, sanitize_asset_metadata as sanitize_asset_metadata
from song_agent.domains.creation.midi_analysis import notes_for_slice as notes_for_slice, parse_midi as parse_midi
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.reference_analysis import reference_context as reference_context, require_fresh_slices as require_fresh_slices
from song_agent.domains.studio.references import ReferenceStore as ReferenceStore
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan
from song_agent.domains.studio.song_editor import build_editor_state as build_editor_state, song_plan_hash as song_plan_hash

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

ClipNote = _make_deferred_global('ClipNote')
EditorClip = _make_deferred_global('EditorClip')
EditorClipError = _make_deferred_global('EditorClipError')
EditorClipUnavailableError = _make_deferred_global('EditorClipUnavailableError')
_SAFE_ID = _make_deferred_global('_SAFE_ID')
operation = _make_deferred_global('operation')

def bind_globals(namespace: dict[str, object]) -> None:
    global ClipNote, EditorClip, EditorClipError, EditorClipUnavailableError, _SAFE_ID, operation
    ClipNote = namespace.get('ClipNote', ClipNote)
    EditorClip = namespace.get('EditorClip', EditorClip)
    EditorClipError = namespace.get('EditorClipError', EditorClipError)
    EditorClipUnavailableError = namespace.get('EditorClipUnavailableError', EditorClipUnavailableError)
    _SAFE_ID = namespace.get('_SAFE_ID', _SAFE_ID)
    operation = namespace.get('operation', operation)
    _bind_deferred_defaults(namespace)


EDITOR_CLIP_SCHEMA_VERSION = 1
MAX_EDITOR_CLIP_NOTES = 128
MAX_EDITOR_CLIP_DURATION_BEATS = 64.0
MAX_EDITOR_CLIP_OPERATIONS = 160
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




def _clip_from_reference_slice(clip_ref: DomainDocument, store: ReferenceStore) -> EditorClip:
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

def _clip_from_project_section(clip_ref: DomainDocument, *, default_project_id: str, project_store: ProjectStore) -> EditorClip:
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

def _clip_from_project_track_range(clip_ref: DomainDocument, *, default_project_id: str, project_store: ProjectStore) -> EditorClip:
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

def _raw_asset_notes(asset: CreativeAsset) -> list[DomainDocument]:
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
        chords = _list_or(asset.content.get("chords"), ["Cmaj7"])
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

def _normalize_notes(raw_notes: list[DomainDocument]) -> list[ClipNote]:
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

def _target_track_id(target: DomainDocument, state: DomainDocument) -> str:
    track_id = _clean_id(target.get("track_id"), "track_id")
    _track_by_id(state, track_id)
    return track_id

def _target_section(target: DomainDocument, state: DomainDocument) -> DomainDocument | None:
    section_id = str(target.get("section_id") or "").strip()
    if not section_id:
        return None
    return _section_by_id(state, section_id)

def _target_start_beat(target: DomainDocument, section: DomainDocument | None) -> float:
    if "start_beat" in target:
        return _float_min(target.get("start_beat"), "target.start_beat", 0.0)
    if section is not None:
        return round(float(section["start_beat"]), 6)
    raise EditorClipError("target.start_beat is required when section_id is not provided.")

def _note_ids_in_replace_range(state: DomainDocument, track_id: str, start: float, end: float) -> list[str]:
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
    target: DomainDocument,
    options: DomainDocument,
    inserted_note_count: int,
    replaced_note_count: int,
) -> DomainDocument:
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

def _clip_group_id(clip: EditorClip, *, track_id: str, start_beat: float, operations: list[DomainDocument]) -> str:
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
) -> DomainDocument:
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

def _find_slice(manifest: DomainDocument, slice_id: str) -> DomainDocument:
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

def _check_project_source_hash(clip_ref: DomainDocument, actual_hash: str) -> None:
    expected_hash = str(clip_ref.get("source_hash") or "").strip()
    if expected_hash and expected_hash != actual_hash:
        raise EditorClipUnavailableError("Project version clip is stale.")

def _section_by_id(state: DomainDocument, section_id: str) -> DomainDocument:
    section = next((item for item in state.get("sections", []) if item.get("section_id") == section_id), None)
    if section is None:
        raise EditorClipError("Unknown section_id.")
    return dict(section)

def _track_by_id(state: DomainDocument, track_id: str) -> DomainDocument:
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

def _clean_id(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_ID.match(text):
        raise EditorClipError(f"{name} is required.")
    return text

def _int_range(value: object, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EditorClipError(f"{name} must be an integer.") from exc
    if number < low or number > high:
        raise EditorClipError(f"{name} must be between {low} and {high}.")
    return number

def _float_min(value: object, name: str, minimum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorClipError(f"{name} must be a number.") from exc
    if number < minimum:
        raise EditorClipError(f"{name} must be >= {minimum}.")
    return round(number, 6)

def _float_range(value: object, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorClipError(f"{name} must be a number.") from exc
    if number < low or number > high:
        raise EditorClipError(f"{name} must be between {low} and {high}.")
    return float(number)

def _quantize_grid(value: object) -> float | None:
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
