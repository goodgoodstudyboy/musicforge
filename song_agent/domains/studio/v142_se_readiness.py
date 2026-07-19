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
EditorPatchStaleError = _make_deferred_global('EditorPatchStaleError')
EditorPreview = _make_deferred_global('EditorPreview')
_append_preview_event = _make_deferred_global('_append_preview_event')
_base_note_keys_by_track_id = _make_deferred_global('_base_note_keys_by_track_id')
_beats_per_bar = _make_deferred_global('_beats_per_bar')
_clip_inserts_from_metadata = _make_deferred_global('_clip_inserts_from_metadata')
_int_range = _make_deferred_global('_int_range')
_operation_counts = _make_deferred_global('_operation_counts')
_parse_iso_datetime = _make_deferred_global('_parse_iso_datetime')
_preview_audio_status = _make_deferred_global('_preview_audio_status')
_preview_validator_report = _make_deferred_global('_preview_validator_report')
_quality_summary = _make_deferred_global('_quality_summary')
_template_inserts_from_metadata = _make_deferred_global('_template_inserts_from_metadata')
_total_bars = _make_deferred_global('_total_bars')
_track_role = _make_deferred_global('_track_role')
describe_editor_operations = _make_deferred_global('describe_editor_operations')
item = _make_deferred_global('item')
note = _make_deferred_global('note')
note_id_for = _make_deferred_global('note_id_for')
note_index = _make_deferred_global('note_index')
operation = _make_deferred_global('operation')
path = _make_deferred_global('path')
section_id_for_index = _make_deferred_global('section_id_for_index')
song_plan_hash = _make_deferred_global('song_plan_hash')
track_id_for_index = _make_deferred_global('track_id_for_index')
validate_editor_preview_id = _make_deferred_global('validate_editor_preview_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global EditorPatch, EditorPatchError, EditorPatchResult, EditorPatchStaleError, EditorPreview, _append_preview_event, _base_note_keys_by_track_id, _beats_per_bar
    global _clip_inserts_from_metadata, _int_range, _operation_counts, _parse_iso_datetime, _preview_audio_status, _preview_validator_report, _quality_summary
    global _template_inserts_from_metadata, _total_bars, _track_role, describe_editor_operations, item, note, note_id_for, note_index
    global operation, path, section_id_for_index, song_plan_hash, track_id_for_index, validate_editor_preview_id
    EditorPatch = namespace.get('EditorPatch', EditorPatch)
    EditorPatchError = namespace.get('EditorPatchError', EditorPatchError)
    EditorPatchResult = namespace.get('EditorPatchResult', EditorPatchResult)
    EditorPatchStaleError = namespace.get('EditorPatchStaleError', EditorPatchStaleError)
    EditorPreview = namespace.get('EditorPreview', EditorPreview)
    _append_preview_event = namespace.get('_append_preview_event', _append_preview_event)
    _base_note_keys_by_track_id = namespace.get('_base_note_keys_by_track_id', _base_note_keys_by_track_id)
    _beats_per_bar = namespace.get('_beats_per_bar', _beats_per_bar)
    _clip_inserts_from_metadata = namespace.get('_clip_inserts_from_metadata', _clip_inserts_from_metadata)
    _int_range = namespace.get('_int_range', _int_range)
    _operation_counts = namespace.get('_operation_counts', _operation_counts)
    _parse_iso_datetime = namespace.get('_parse_iso_datetime', _parse_iso_datetime)
    _preview_audio_status = namespace.get('_preview_audio_status', _preview_audio_status)
    _preview_validator_report = namespace.get('_preview_validator_report', _preview_validator_report)
    _quality_summary = namespace.get('_quality_summary', _quality_summary)
    _template_inserts_from_metadata = namespace.get('_template_inserts_from_metadata', _template_inserts_from_metadata)
    _total_bars = namespace.get('_total_bars', _total_bars)
    _track_role = namespace.get('_track_role', _track_role)
    describe_editor_operations = namespace.get('describe_editor_operations', describe_editor_operations)
    item = namespace.get('item', item)
    note = namespace.get('note', note)
    note_id_for = namespace.get('note_id_for', note_id_for)
    note_index = namespace.get('note_index', note_index)
    operation = namespace.get('operation', operation)
    path = namespace.get('path', path)
    section_id_for_index = namespace.get('section_id_for_index', section_id_for_index)
    song_plan_hash = namespace.get('song_plan_hash', song_plan_hash)
    track_id_for_index = namespace.get('track_id_for_index', track_id_for_index)
    validate_editor_preview_id = namespace.get('validate_editor_preview_id', validate_editor_preview_id)
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




class EditorPreviewStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.root = self.project_dir / "editor-previews"
        self.lock = threading.RLock()

    def create_preview(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        parent_job_id: str,
        parent_plan: SongPlan,
        patch: EditorPatch,
        result: EditorPatchResult,
        render_midi: bool = True,
        now: str | None = None,
    ) -> tuple[EditorPreview, Path]:
        from song_agent.domains.creation.renderers.midi import render_midi as render_song_midi

        now = now or now_iso()
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            preview_id, preview_dir = self._reserve_preview_dir()
            midi_url = f"/api/projects/{project_id}/editor-previews/{preview_id}/midi" if render_midi else None
            preview = EditorPreview(
                schema_version=EDITOR_PREVIEW_SCHEMA_VERSION,
                preview_id=preview_id,
                project_id=project_id,
                parent_version_id=parent_version_id,
                parent_job_id=parent_job_id,
                base_plan_hash=song_plan_hash(parent_plan),
                status="completed",
                label=patch.label,
                created_at=now,
                updated_at=now,
                operation_count=len(patch.operations),
                changed_sections=list(result.summary.get("changed_sections") or []),
                changed_tracks=list(result.summary.get("changed_tracks") or []),
                quality=_quality_summary(result.plan),
                warnings=list(result.warnings),
                midi_url=midi_url,
            )
            try:
                write_json(preview_dir / "patch.json", patch.to_dict())
                write_json(preview_dir / "song-plan.json", result.plan.to_dict())
                write_json(preview_dir / "validator-report.json", _preview_validator_report(result.plan, render_midi))
                write_json(preview_dir / "quality.json", {"quality": result.plan.quality.to_dict() if result.plan.quality else {}})
                if render_midi:
                    render_song_midi(result.plan, preview_dir / "song.mid")
                    report = read_json(preview_dir / "validator-report.json")
                    report["midi_exists"] = True
                    report["midi_size"] = (preview_dir / "song.mid").stat().st_size
                    write_json(preview_dir / "validator-report.json", report)
                write_json(preview_dir / "preview.json", preview.to_dict())
                _append_preview_event(preview_dir, "editor_preview_created", {"operation_count": preview.operation_count}, now)
            except Exception:
                if preview_dir.exists() and not (preview_dir / "preview.json").exists():
                    shutil.rmtree(preview_dir)
                raise
            return preview, preview_dir

    def read_preview(self, preview_id: str) -> EditorPreview:
        return EditorPreview.from_dict(read_json(self.preview_dir(preview_id) / "preview.json"))

    def read_patch(self, preview_id: str) -> EditorPatch:
        return EditorPatch.from_dict(read_json(self.preview_dir(preview_id) / "patch.json"))

    def read_plan(self, preview_id: str) -> SongPlan:
        return SongPlan.from_dict(read_json(self.preview_dir(preview_id) / "song-plan.json"))

    def list_previews(self) -> list[EditorPreview]:
        with self.lock:
            if not self.root.exists():
                return []
            previews: list[EditorPreview] = []
            for preview_json in self.root.glob("preview-*/preview.json"):
                try:
                    previews.append(EditorPreview.from_dict(read_json(preview_json)))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
            return sorted(previews, key=lambda item: (item.updated_at or item.created_at, item.preview_id), reverse=True)

    def read_patch_summary(self, preview_id: str, *, include_operations: bool = False) -> DomainDocument:
        preview = self.read_preview(preview_id)
        patch = self.read_patch(preview_id)
        summary = {
            "preview_id": preview.preview_id,
            "parent_version_id": preview.parent_version_id,
            "status": preview.status,
            "label": preview.label,
            "operation_count": preview.operation_count,
            "changed_sections": list(preview.changed_sections),
            "changed_tracks": list(preview.changed_tracks),
            "operation_counts": _operation_counts(patch.operations),
            "operations_text": describe_editor_operations(patch.operations),
            "clip_inserts": _clip_inserts_from_metadata(patch.metadata),
            "template_inserts": _template_inserts_from_metadata(patch.metadata),
            "warnings": list(preview.warnings),
            "applied_version_id": preview.applied_version_id,
            "updated_at": preview.updated_at,
        }
        if include_operations:
            summary["operations"] = sanitize_metadata([dict(operation) for operation in patch.operations])
        return sanitize_metadata(summary)

    def cleanup_previews(
        self,
        *,
        delete_unapplied_older_than_days: int = 7,
        keep_latest: int = 20,
        now: str | None = None,
    ) -> DomainDocument:
        days = _int_range(delete_unapplied_older_than_days, "delete_unapplied_older_than_days", 0, 3650)
        keep = _int_range(keep_latest, "keep_latest", 5, 200)
        cutoff = _parse_iso_datetime(now or now_iso()) - timedelta(days=days)
        deleted: list[str] = []
        kept: list[str] = []
        with self.lock:
            if self.root.exists() and any(path.is_symlink() for path in self.root.iterdir()):
                raise ValueError("Refusing to delete symlink editor preview.")
            previews = self.list_previews()
            protected = {preview.preview_id for preview in previews[:keep]}
            for preview in previews:
                if preview.applied_version_id:
                    kept.append(preview.preview_id)
                    continue
                if preview.preview_id in protected:
                    kept.append(preview.preview_id)
                    continue
                updated = _parse_iso_datetime(preview.updated_at or preview.created_at)
                if updated > cutoff:
                    kept.append(preview.preview_id)
                    continue
                preview_dir = self.preview_dir(preview.preview_id)
                if preview_dir.is_symlink():
                    raise ValueError("Refusing to delete symlink editor preview.")
                shutil.rmtree(preview_dir)
                deleted.append(preview.preview_id)
        return {"deleted": deleted, "deleted_count": len(deleted), "kept_count": len(kept)}

    def mark_applied(self, preview_id: str, *, version_id: str, job_id: str, now: str | None = None) -> EditorPreview:
        with self.lock:
            preview = self.read_preview(preview_id)
            if preview.applied_version_id:
                raise EditorPatchStaleError("Editor preview has already been applied.")
            updated = EditorPreview.from_dict({**preview.to_dict(), "status": "applied", "applied_version_id": version_id, "applied_job_id": job_id, "updated_at": now or now_iso()})
            write_json(self.preview_dir(preview_id) / "preview.json", updated.to_dict())
            _append_preview_event(self.preview_dir(preview_id), "editor_preview_applied", {"version_id": version_id, "job_id": job_id}, updated.updated_at)
            return updated

    def update_preview_audio(
        self,
        preview_id: str,
        *,
        status: str,
        audio_url: str | None = None,
        audio_error: str | None = None,
        audio_size_bytes: int = 0,
        now: str | None = None,
    ) -> EditorPreview:
        with self.lock:
            preview = self.read_preview(preview_id)
            updated_at = now or now_iso()
            updated = EditorPreview.from_dict(
                {
                    **preview.to_dict(),
                    "audio_status": _preview_audio_status(status),
                    "audio_url": audio_url if audio_url is not None else preview.audio_url,
                    "audio_error": sanitize_sensitive_text(str(audio_error or "")) if audio_error else None,
                    "audio_size_bytes": max(0, int(audio_size_bytes or 0)),
                    "audio_updated_at": updated_at,
                    "updated_at": updated_at,
                }
            )
            write_json(self.preview_dir(preview_id) / "preview.json", updated.to_dict())
            _append_preview_event(
                self.preview_dir(preview_id),
                "editor_preview_audio_updated",
                {"status": updated.audio_status, "size_bytes": updated.audio_size_bytes},
                updated_at,
            )
            return updated

    def delete_preview(self, preview_id: str) -> None:
        with self.lock:
            preview_dir = self.preview_dir(preview_id)
            if not preview_dir.exists():
                raise FileNotFoundError(preview_id)
            if preview_dir.resolve().is_symlink():
                raise ValueError("Refusing to delete symlink editor preview.")
            shutil.rmtree(preview_dir)

    def preview_dir(self, preview_id: str) -> Path:
        preview_id = validate_editor_preview_id(preview_id)
        base = self.root.resolve()
        raw_target = base / preview_id
        if raw_target.is_symlink():
            raise ValueError("Refusing to operate on symlink editor preview.")
        target = raw_target.resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside editor previews.") from exc
        return target

    def _reserve_preview_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            preview_id = f"preview-{index:03d}"
            preview_dir = self.preview_dir(preview_id)
            try:
                preview_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return preview_id, preview_dir
        raise RuntimeError("Could not allocate editor preview id.")

def build_editor_state(plan: SongPlan) -> DomainDocument:
    if len(plan.tracks) > MAX_EDITOR_TRACKS:
        raise EditorPatchError("SongPlan has too many tracks for visual editor.")
    if any(len(track.notes) > MAX_EDITOR_NOTES_PER_TRACK for track in plan.tracks):
        raise EditorPatchError("SongPlan has too many notes for visual editor.")
    beats_per_bar = _beats_per_bar(plan)
    total_bars = _total_bars(plan)
    sections = []
    for index, section in enumerate(plan.sections):
        section_id = section_id_for_index(index)
        start_beat = (section.start_bar - 1) * beats_per_bar
        end_beat = start_beat + section.bars * beats_per_bar
        sections.append(
            {
                "section_id": section_id,
                "name": section.name,
                "start_bar": section.start_bar,
                "bars": section.bars,
                "start_beat": start_beat,
                "end_beat": end_beat,
                "chords": list(section.chords),
                "lyrics": section.lyrics or "",
            }
        )
    tracks = []
    for track_index, track in enumerate(plan.tracks):
        track_id = track_id_for_index(track_index)
        pitches = [note.pitch for note in track.notes]
        notes = [
            {
                "note_id": note_id_for(track_id, note_index, note),
                "pitch": note.pitch,
                "start_beat": note.start_beat,
                "duration_beats": note.duration_beats,
                "velocity": note.velocity,
            }
            for note_index, note in enumerate(track.notes)
        ]
        tracks.append(
            {
                "track_id": track_id,
                "name": track.name,
                "instrument": track.instrument,
                "role": _track_role(track.name),
                "note_count": len(track.notes),
                "pitch_min": min(pitches) if pitches else None,
                "pitch_max": max(pitches) if pitches else None,
                "notes": notes,
            }
        )
    quality = plan.quality.to_dict() if plan.quality else analyze_song_quality(plan).to_dict()
    return {
        "ok": True,
        "base_plan_hash": song_plan_hash(plan),
        "song": {
            "title": plan.title,
            "key": plan.key,
            "tempo_bpm": plan.tempo_bpm,
            "meter": plan.meter,
            "total_bars": total_bars,
            "beats_per_bar": beats_per_bar,
        },
        "sections": sections,
        "tracks": tracks,
        "quality": quality,
        "warnings": [],
    }

def _apply_editor_patch_part_01(parent_plan: SongPlan, patch_data: DomainDocument | EditorPatch, _split_state):
    _split_state['patch'] = patch_data if isinstance(patch_data, EditorPatch) else EditorPatch.from_dict(patch_data)
    current_hash = song_plan_hash(parent_plan)
    if _split_state['patch'].base_plan_hash != current_hash:
        raise EditorPatchStaleError('Editor patch is stale because the base song-plan hash changed.')
    state = build_editor_state(parent_plan)
    _split_state['base_section_names_by_id'] = {_split_state['section']['section_id']: str(_split_state['section']['name']) for _split_state['section'] in state['sections']}
    _split_state['base_track_names_by_id'] = {_split_state['track']['track_id']: str(_split_state['track']['name']) for _split_state['track'] in state['tracks']}
    _split_state['base_note_keys_by_track_id'] = _base_note_keys_by_track_id(state)
    _split_state['sections'] = list(parent_plan.sections)
    _split_state['tracks'] = list(parent_plan.tracks)
    _split_state['summary_counts'] = {}
    _split_state['changed_sections'] = set()
    _split_state['changed_tracks'] = set()
    _split_state['warnings'] = []
    _split_state['added_notes'] = 0
    _split_state['total_beats'] = _total_bars(parent_plan) * _beats_per_bar(parent_plan)
    return (False, None)
