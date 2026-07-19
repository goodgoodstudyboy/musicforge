# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import json as json
import math as math
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import PROGRAMS_BY_ROLE as PROGRAMS_BY_ROLE, _header_chunk as _header_chunk, _meta_track as _meta_track, _music_track as _music_track, _track_role as _track_role
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan
from song_agent.domains.studio.song_editor import EditorPreview as EditorPreview, build_editor_state as build_editor_state, song_plan_hash as song_plan_hash, validate_editor_preview_id as validate_editor_preview_id
from song_agent.domains.studio.editor_review import add_marker as add_marker, apply_review_patch as apply_review_patch, audition_review_row as audition_review_row, default_review as default_review, delete_marker as delete_marker, normalize_review as normalize_review, record_asset_created as record_asset_created, review_board as review_board, review_summary as audition_review_summary, update_marker as update_marker

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

EditorAuditionError = _make_deferred_global('EditorAuditionError')
EditorAuditionManifest = _make_deferred_global('EditorAuditionManifest')
EditorAuditionUnavailableError = _make_deferred_global('EditorAuditionUnavailableError')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
item = _make_deferred_global('item')
track = _make_deferred_global('track')
track_id = _make_deferred_global('track_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global EditorAuditionError, EditorAuditionManifest, EditorAuditionUnavailableError, _LOCKS_GUARD, item, track, track_id
    EditorAuditionError = namespace.get('EditorAuditionError', EditorAuditionError)
    EditorAuditionManifest = namespace.get('EditorAuditionManifest', EditorAuditionManifest)
    EditorAuditionUnavailableError = namespace.get('EditorAuditionUnavailableError', EditorAuditionUnavailableError)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    item = namespace.get('item', item)
    track = namespace.get('track', track)
    track_id = namespace.get('track_id', track_id)
    _bind_deferred_defaults(namespace)


EDITOR_AUDITION_SCHEMA_VERSION = 1
MAX_AUDITION_LABEL_LENGTH = 120
MAX_AUDITIONS_PER_PREVIEW = 500
AUDITION_SOURCES = {"preview", "parent"}
AUDITION_RANGE_MODES = {"full_song", "section", "changed_sections", "custom"}
AUDITION_TRACK_MODES = {"all", "solo", "mute"}
_STORE_LOCKS: dict[str, threading.RLock] = {}




def _resolve_range(state: DomainDocument, payload: DomainDocument, changed_sections: list[str]) -> tuple[float, float, DomainDocument]:
    mode = str(payload.get("mode") or "full_song").strip()
    if mode not in AUDITION_RANGE_MODES:
        raise EditorAuditionError("range.mode must be full_song, section, changed_sections, or custom.")
    total_beats = float(state["song"]["total_bars"]) * float(state["song"]["beats_per_bar"])
    if mode == "full_song":
        return 0.0, total_beats, {"mode": mode, "start_beat": 0.0, "end_beat": total_beats}
    if mode == "section":
        section_id = str(payload.get("section_id") or "").strip()
        section = next((item for item in state.get("sections", []) if item.get("section_id") == section_id), None)
        if section is None:
            raise EditorAuditionError("Unknown section_id.")
        start = float(section["start_beat"])
        end = float(section["end_beat"])
        return start, end, {"mode": mode, "section_id": section_id, "section_name": section.get("name"), "start_beat": start, "end_beat": end}
    if mode == "changed_sections":
        names = {str(item).strip() for item in changed_sections if str(item).strip()}
        sections = [item for item in state.get("sections", []) if str(item.get("name") or "") in names]
        if not sections:
            raise EditorAuditionUnavailableError("Preview has no changed sections for audition.")
        start = min(float(item["start_beat"]) for item in sections)
        end = max(float(item["end_beat"]) for item in sections)
        return start, end, {"mode": mode, "section_names": sorted(names), "start_beat": start, "end_beat": end}
    start = _float(payload.get("start_beat"), "range.start_beat")
    end = _float(payload.get("end_beat"), "range.end_beat")
    if start < 0:
        raise EditorAuditionError("range.start_beat must be >= 0.")
    if end <= start:
        raise EditorAuditionError("range.end_beat must be greater than start_beat.")
    if end - start < 0.25:
        raise EditorAuditionError("audition range must be at least 0.25 beat.")
    if end > total_beats + 0.001:
        raise EditorAuditionError("range.end_beat exceeds song length.")
    return start, end, {"mode": mode, "start_beat": start, "end_beat": end}

def _resolve_tracks(state: DomainDocument, track_mode: str, track_ids: list[str]) -> tuple[list[int], list[str]]:
    if track_mode not in AUDITION_TRACK_MODES:
        raise EditorAuditionError("track_mode must be all, solo, or mute.")
    tracks = list(state.get("tracks", []))
    ids = [str(track.get("track_id") or "") for track in tracks]
    if any(str(track_id).startswith("derived-") for track_id in track_ids):
        raise EditorAuditionError("derived track ids are not accepted for audition.")
    unknown = sorted(set(track_ids) - set(ids))
    if unknown:
        raise EditorAuditionError(f"Unknown track ids: {', '.join(unknown[:5])}.")
    if track_mode == "all":
        selected_ids = ids
    elif track_mode == "solo":
        if not track_ids:
            raise EditorAuditionError("track_ids are required for solo audition.")
        selected_ids = [track_id for track_id in ids if track_id in set(track_ids)]
    else:
        if not track_ids:
            raise EditorAuditionError("track_ids are required for mute audition.")
        muted = set(track_ids)
        selected_ids = [track_id for track_id in ids if track_id not in muted]
    indexes = [ids.index(track_id) for track_id in selected_ids]
    if not indexes:
        raise EditorAuditionUnavailableError("Audition produced no notes.")
    return indexes, selected_ids

def _clip_sections(plan: SongPlan, state: DomainDocument, start_beat: float, end_beat: float) -> list[SongSection]:
    beats_per_bar = int(state["song"]["beats_per_bar"])
    sections: list[SongSection] = []
    next_start_bar = 1
    for index, section_state in enumerate(state.get("sections", [])):
        section_start = float(section_state["start_beat"])
        section_end = float(section_state["end_beat"])
        overlap_start = max(start_beat, section_start)
        overlap_end = min(end_beat, section_end)
        if overlap_end <= overlap_start:
            continue
        bars = max(1, int(math.ceil((overlap_end - overlap_start) / beats_per_bar)))
        source = plan.sections[index]
        sections.append(SongSection(source.name, next_start_bar, bars, list(source.chords), source.lyrics))
        next_start_bar += bars
    if sections:
        return sections
    source = plan.sections[0]
    bars = max(1, int(math.ceil((end_beat - start_beat) / beats_per_bar)))
    return [SongSection(source.name or "audition", 1, bars, list(source.chords), source.lyrics)]

def _clip_notes(notes: list[NoteEvent], start_beat: float, end_beat: float) -> list[NoteEvent]:
    clipped: list[NoteEvent] = []
    for note in notes:
        note_start = float(note.start_beat)
        note_end = note_start + float(note.duration_beats)
        overlap_start = max(start_beat, note_start)
        overlap_end = min(end_beat, note_end)
        if overlap_end <= overlap_start:
            continue
        clipped.append(
            NoteEvent(
                pitch=note.pitch,
                start_beat=round(overlap_start - start_beat, 6),
                duration_beats=round(overlap_end - overlap_start, 6),
                velocity=note.velocity,
            )
        )
    return sorted(clipped, key=lambda item: (item.start_beat, item.pitch, item.duration_beats, item.velocity))

def _track_ids(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EditorAuditionError("track_ids must be a list.")
    ids = [str(item).strip() for item in value if str(item).strip()]
    if len(ids) != len(value):
        raise EditorAuditionError("track_ids must not contain empty ids.")
    if len(ids) > 32:
        raise EditorAuditionError("track_ids supports at most 32 ids.")
    if any(not re.match(r"^track-[0-9]{3}$", item) for item in ids):
        raise EditorAuditionError("track_ids must contain real track ids.")
    return ids

def _artifact_status(value: object, *, status_key: str) -> DomainDocument:
    data = _as_document(value)
    status = str(data.get("status") or status_key).strip()
    if status not in {"not_started", "running", "completed", "failed"}:
        status = status_key
    return sanitize_metadata(
        {
            "status": status,
            "exists": bool(data.get("exists", False)),
            "size_bytes": max(0, int(data.get("size_bytes") or 0)),
            "url": str(data.get("url") or ""),
            "error": sanitize_sensitive_text(str(data.get("error") or "")) if data.get("error") else None,
        }
    )

def _audition_status(value: object) -> str:
    status = str(value or "completed").strip()
    if status not in {"not_started", "running", "completed", "failed", "deleted"}:
        return "completed"
    return status

def _bounded_label(value: object) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    return text[:MAX_AUDITION_LABEL_LENGTH].rstrip()

def _float(value: object, name: str) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError) as exc:
        raise EditorAuditionError(f"{name} must be a number.") from exc

def _render_report(manifest: EditorAuditionManifest) -> DomainDocument:
    return {
        "status": manifest.status,
        "audition_id": manifest.audition_id,
        "source": manifest.source,
        "range": manifest.range,
        "track_mode": manifest.track_mode,
        "track_count": manifest.track_count,
        "note_count": manifest.note_count,
        "midi": manifest.midi,
        "audio": manifest.audio,
        "updated_at": manifest.updated_at,
    }

def _lock_for_project(project_dir: Path) -> threading.RLock:
    key = str(project_dir)
    with _LOCKS_GUARD:
        lock = _STORE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _STORE_LOCKS[key] = lock
        return lock

def _append_audition_event(audition_dir: Path, event_type: str, payload: DomainDocument, now: str | None = None) -> None:
    event = {"timestamp": now or now_iso(), "event": event_type, **sanitize_metadata(payload)}
    path = audition_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

def _review_event_payload(manifest: EditorAuditionManifest) -> DomainDocument:
    row = audition_review_row(manifest)
    review = _as_document(row.get("review"))
    return {
        "rating": review.get("rating", 0),
        "status": review.get("status", "unreviewed"),
        "favorite": bool(review.get("favorite", False)),
        "marker_count": len(review.get("markers") or []),
    }
