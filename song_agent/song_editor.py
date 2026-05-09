from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from song_agent.edits import SUPPORTED_HARMONY_CHORDS
from song_agent.music_quality import attach_quality, analyze_song_quality
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.schemas.song import NoteEvent, SongPlan, SongSection, TrackPlan


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
    operations: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditorPatch":
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
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EditorPatchResult:
    plan: SongPlan
    patch: EditorPatch
    summary: dict[str, Any]
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
    quality: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    midi_url: str | None = None
    audio_url: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditorPreview":
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
            applied_version_id=_optional_str(data.get("applied_version_id")),
            applied_job_id=_optional_str(data.get("applied_job_id")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        from song_agent.renderers.midi import render_midi as render_song_midi

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

    def read_patch_summary(self, preview_id: str, *, include_operations: bool = False) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        days = _int_range(delete_unapplied_older_than_days, "delete_unapplied_older_than_days", 0, 3650)
        keep = _int_range(keep_latest, "keep_latest", 5, 200)
        cutoff = _parse_iso_datetime(now or now_iso()) - timedelta(days=days)
        deleted: list[str] = []
        kept: list[str] = []
        with self.lock:
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
                if preview_dir.resolve().is_symlink():
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
        target = (base / preview_id).resolve()
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


def build_editor_state(plan: SongPlan) -> dict[str, Any]:
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


def apply_editor_patch(parent_plan: SongPlan, patch_data: dict[str, Any] | EditorPatch) -> EditorPatchResult:
    patch = patch_data if isinstance(patch_data, EditorPatch) else EditorPatch.from_dict(patch_data)
    current_hash = song_plan_hash(parent_plan)
    if patch.base_plan_hash != current_hash:
        raise EditorPatchStaleError("Editor patch is stale because the base song-plan hash changed.")
    state = build_editor_state(parent_plan)
    base_section_names_by_id: dict[str, str | None] = {section["section_id"]: str(section["name"]) for section in state["sections"]}
    base_track_names_by_id: dict[str, str | None] = {track["track_id"]: str(track["name"]) for track in state["tracks"]}
    base_note_keys_by_track_id = _base_note_keys_by_track_id(state)
    sections = list(parent_plan.sections)
    tracks = list(parent_plan.tracks)
    summary_counts: dict[str, int] = {}
    changed_sections: set[str] = set()
    changed_tracks: set[str] = set()
    warnings: list[str] = []
    added_notes = 0
    total_beats = _total_bars(parent_plan) * _beats_per_bar(parent_plan)
    for operation in patch.operations:
        op = str(operation.get("op") or "")
        summary_counts[op] = summary_counts.get(op, 0) + 1
        if op == "set_section_chords":
            section_index = _section_index_for_plan(operation, sections, base_section_names_by_id)
            chords = _chords(operation.get("chords"))
            section = sections[section_index]
            sections[section_index] = SongSection(section.name, section.start_bar, section.bars, chords, section.lyrics)
            changed_sections.add(section.name)
        elif op == "set_section_lyrics":
            section_index = _section_index_for_plan(operation, sections, base_section_names_by_id)
            lyrics = _clean_lyrics(operation.get("lyrics"))
            section = sections[section_index]
            sections[section_index] = SongSection(section.name, section.start_bar, section.bars, section.chords, lyrics)
            changed_sections.add(section.name)
        elif op == "set_track_instrument":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            instrument = _bounded_text(operation.get("instrument"), MAX_INSTRUMENT_LENGTH)
            if not instrument:
                raise EditorPatchError("instrument must not be empty.")
            track = tracks[track_index]
            tracks[track_index] = TrackPlan(track.name, instrument, track.notes)
            changed_tracks.add(track.name)
        elif op == "add_section":
            beats_per_bar = _beats_per_bar(parent_plan)
            section = _section_from_operation(operation, sections)
            after_index = _optional_after_section_index(operation, sections, base_section_names_by_id)
            insert_index = len(sections) if after_index is None else after_index + 1
            insert_start = _section_start_beat_at_index(sections, insert_index, beats_per_bar)
            delta = section.bars * beats_per_bar
            sections.insert(insert_index, section)
            _assert_total_bars(sections)
            sections = normalize_sections(sections)
            tracks = shift_notes_after_beat(tracks, insert_start, delta)
            _shift_note_keys_after_beat(base_note_keys_by_track_id, insert_start, delta)
            total_beats = _total_bars_from_sections(sections) * beats_per_bar
            changed_sections.add(section.name)
            warnings.append(f"Section {section.name} was added without notes.")
        elif op == "duplicate_section":
            beats_per_bar = _beats_per_bar(parent_plan)
            source_index = _section_index_for_plan(operation, sections, base_section_names_by_id)
            source = sections[source_index]
            new_name = _unique_section_name(operation.get("name"), sections)
            after_index = _optional_after_section_index(operation, sections, base_section_names_by_id)
            insert_index = len(sections) if after_index is None else after_index + 1
            source_start = _section_start_beat(source, beats_per_bar)
            source_end = source_start + source.bars * beats_per_bar
            insert_start = _section_start_beat_at_index(sections, insert_index, beats_per_bar)
            delta = source.bars * beats_per_bar
            new_section = SongSection(new_name, 1, source.bars, list(source.chords), source.lyrics)
            tracks = shift_notes_after_beat(tracks, insert_start, delta)
            _shift_note_keys_after_beat(base_note_keys_by_track_id, insert_start, delta)
            if bool(operation.get("copy_notes", True)):
                shifted_source_start = source_start + (delta if insert_start <= source_start else 0)
                shifted_source_end = source_end + (delta if insert_start <= source_start else 0)
                tracks = copy_notes_in_range(tracks, shifted_source_start, shifted_source_end, insert_start)
            sections.insert(insert_index, new_section)
            _assert_total_bars(sections)
            sections = normalize_sections(sections)
            total_beats = _total_bars_from_sections(sections) * beats_per_bar
            changed_sections.update({source.name, new_name})
            for track in tracks:
                if any(insert_start <= note.start_beat < insert_start + delta for note in track.notes):
                    changed_tracks.add(track.name)
        elif op == "delete_section":
            beats_per_bar = _beats_per_bar(parent_plan)
            if len(sections) <= 1:
                raise EditorPatchError("Cannot delete the last section.")
            section_index = _section_index_for_plan(operation, sections, base_section_names_by_id)
            section = sections[section_index]
            policy = _choice(operation.get("note_policy") or "delete", "note_policy", {"delete", "shift_left", "keep_absolute"})
            start = _section_start_beat(section, beats_per_bar)
            end = start + section.bars * beats_per_bar
            delta = -(section.bars * beats_per_bar)
            if policy in {"delete", "shift_left"}:
                tracks = delete_notes_in_range(tracks, start, end)
                _delete_note_keys_in_range(base_note_keys_by_track_id, start, end)
                tracks = shift_notes_after_beat(tracks, end, delta)
                _shift_note_keys_after_beat(base_note_keys_by_track_id, end, delta)
            sections.pop(section_index)
            base_section_names_by_id[str(operation.get("section_id") or "")] = None
            sections = normalize_sections(sections)
            total_beats = _total_bars_from_sections(sections) * beats_per_bar
            if policy == "keep_absolute":
                tracks = trim_notes_to_total_beats(tracks, total_beats, warnings)
                _trim_note_keys_to_total_beats(base_note_keys_by_track_id, total_beats)
            changed_sections.add(section.name)
            changed_tracks.update(track.name for track in tracks)
        elif op == "resize_section":
            beats_per_bar = _beats_per_bar(parent_plan)
            section_index = _section_index_for_plan(operation, sections, base_section_names_by_id)
            section = sections[section_index]
            new_bars = _int_range(operation.get("bars"), "bars", 1, MAX_SECTION_BARS)
            policy = _choice(operation.get("note_policy") or "shift_tail", "note_policy", {"shift_tail", "crop"})
            old_bars = section.bars
            if new_bars == old_bars:
                changed_sections.add(section.name)
            else:
                old_end = _section_start_beat(section, beats_per_bar) + old_bars * beats_per_bar
                new_end = _section_start_beat(section, beats_per_bar) + new_bars * beats_per_bar
                delta = (new_bars - old_bars) * beats_per_bar
                if delta < 0 and policy == "crop":
                    tracks = delete_notes_in_range(tracks, new_end, old_end)
                    _delete_note_keys_in_range(base_note_keys_by_track_id, new_end, old_end)
                tracks = shift_notes_after_beat(tracks, old_end, delta)
                _shift_note_keys_after_beat(base_note_keys_by_track_id, old_end, delta)
                sections[section_index] = SongSection(section.name, section.start_bar, new_bars, list(section.chords), section.lyrics)
                _assert_total_bars(sections)
                sections = normalize_sections(sections)
                total_beats = _total_bars_from_sections(sections) * beats_per_bar
                tracks = trim_notes_to_total_beats(tracks, total_beats, warnings)
                _trim_note_keys_to_total_beats(base_note_keys_by_track_id, total_beats)
                changed_sections.add(section.name)
                changed_tracks.update(track.name for track in tracks)
        elif op == "move_section":
            beats_per_bar = _beats_per_bar(parent_plan)
            section_index = _section_index_for_plan(operation, sections, base_section_names_by_id)
            after_index = _optional_after_section_index(operation, sections, base_section_names_by_id, allow_self=False)
            section = sections[section_index]
            before_names = [item.name for item in sections]
            old_spans_by_name = {item.name: _section_span(item, beats_per_bar) for item in sections}
            moved = sections.pop(section_index)
            if after_index is None:
                insert_index = 0
            else:
                insert_index = after_index + 1
                if after_index > section_index:
                    insert_index -= 1
            sections.insert(insert_index, moved)
            if [item.name for item in sections] == before_names:
                changed_sections.add(section.name)
            else:
                sections = normalize_sections(sections)
                new_spans_by_name = {item.name: _section_span(item, beats_per_bar) for item in sections}
                move_names = set(before_names) if bool(operation.get("move_notes", True)) else (set(before_names) - {section.name})
                tracks = remap_notes_by_section(tracks, old_spans_by_name, new_spans_by_name, move_names=move_names)
                _remap_note_keys_by_section(base_note_keys_by_track_id, old_spans_by_name, new_spans_by_name, move_names=move_names)
                total_beats = _total_bars_from_sections(sections) * beats_per_bar
                changed_sections.add(section.name)
                changed_tracks.update(track.name for track in tracks)
        elif op == "add_track":
            if len(tracks) >= MAX_EDITOR_TRACKS:
                raise EditorPatchError(f"editor supports at most {MAX_EDITOR_TRACKS} tracks.")
            name = _unique_track_name(operation.get("name"), tracks)
            instrument = _bounded_text(operation.get("instrument"), MAX_INSTRUMENT_LENGTH)
            if not instrument:
                raise EditorPatchError("instrument must not be empty.")
            tracks.append(TrackPlan(name, instrument, []))
            changed_tracks.add(name)
            warnings.append(f"Track {name} was added without notes.")
        elif op == "duplicate_track":
            if len(tracks) >= MAX_EDITOR_TRACKS:
                raise EditorPatchError(f"editor supports at most {MAX_EDITOR_TRACKS} tracks.")
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            source = tracks[track_index]
            name = _unique_track_name(operation.get("name"), tracks)
            instrument = _bounded_text(operation.get("instrument") or source.instrument, MAX_INSTRUMENT_LENGTH)
            transpose = _int_range(operation.get("transpose", 0), "transpose", -24, 24)
            notes = [
                NoteEvent(_clamp(note.pitch + transpose, 0, 127), note.start_beat, note.duration_beats, note.velocity)
                for note in source.notes
            ]
            tracks.append(TrackPlan(name, instrument, _sorted_notes(notes)))
            changed_tracks.update({source.name, name})
        elif op == "delete_track":
            if len(tracks) <= 1:
                raise EditorPatchError("Cannot delete the last track.")
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            track = tracks[track_index]
            remaining = [item for index, item in enumerate(tracks) if index != track_index]
            if track.notes and not any(item.notes for item in remaining) and not bool(operation.get("allow_empty_song")):
                raise EditorPatchError("Cannot delete the last track with notes unless allow_empty_song is true.")
            if track.notes and not any(item.notes for item in remaining):
                warnings.append("All notes were removed by deleting the last non-empty track.")
            if _missing_required_track_roles(remaining) and not bool(operation.get("allow_empty_song")):
                raise EditorPatchError("Cannot delete required track roles unless allow_empty_song is true.")
            tracks = remaining
            base_track_names_by_id[str(operation.get("track_id") or "")] = None
            changed_tracks.add(track.name)
        elif op == "rename_track":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            track = tracks[track_index]
            name = _unique_track_name(operation.get("name"), [item for index, item in enumerate(tracks) if index != track_index])
            tracks[track_index] = TrackPlan(name, track.instrument, track.notes)
            base_track_names_by_id[str(operation.get("track_id") or "")] = name
            changed_tracks.update({track.name, name})
        elif op == "add_note":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            if added_notes >= MAX_ADDED_NOTES_PER_PATCH:
                raise EditorPatchError(f"editor patch can add at most {MAX_ADDED_NOTES_PER_PATCH} notes.")
            note = _note(operation.get("note"), total_beats)
            track = tracks[track_index]
            tracks[track_index] = TrackPlan(track.name, track.instrument, _sorted_notes([*track.notes, note]))
            changed_tracks.add(track.name)
            added_notes += 1
        elif op == "update_note":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            track = tracks[track_index]
            note_keys_by_id = base_note_keys_by_track_id.get(str(operation.get("track_id") or ""), {})
            notes, updated_note = _update_note(track, note_keys_by_id, operation, total_beats)
            note_keys_by_id[str(operation.get("note_id") or "")] = _note_key(updated_note)
            tracks[track_index] = TrackPlan(track.name, track.instrument, notes)
            changed_tracks.add(track.name)
        elif op == "delete_notes":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            track = tracks[track_index]
            selected = set(_note_ids(operation.get("note_ids")))
            note_keys_by_id = base_note_keys_by_track_id.get(str(operation.get("track_id") or ""), {})
            notes, deleted_note_ids = _delete_selected_notes(track, note_keys_by_id, selected)
            for note_id in deleted_note_ids:
                note_keys_by_id[note_id] = None
            if not notes:
                warnings.append(f"Track {track.name} has no notes after editor patch.")
            tracks[track_index] = TrackPlan(track.name, track.instrument, notes)
            changed_tracks.add(track.name)
        elif op == "move_notes":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            delta = _float_range(operation.get("delta_beats"), "delta_beats", -64.0, 64.0)
            track = tracks[track_index]
            ids = set(_note_ids(operation.get("note_ids")))
            note_keys_by_id = base_note_keys_by_track_id.get(str(operation.get("track_id") or ""), {})
            notes, updated_keys = _map_selected_notes(track, note_keys_by_id=note_keys_by_id, ids=ids, total_beats=total_beats, mapper=lambda note: NoteEvent(note.pitch, _round_beat(note.start_beat + delta), note.duration_beats, note.velocity))
            note_keys_by_id.update(updated_keys)
            tracks[track_index] = TrackPlan(track.name, track.instrument, notes)
            changed_tracks.add(track.name)
        elif op == "transpose_notes":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            semitones = _int_range(operation.get("semitones"), "semitones", -24, 24)
            track = tracks[track_index]
            selector = _note_selector(operation, track)
            note_keys_by_id = base_note_keys_by_track_id.get(str(operation.get("track_id") or ""), {})
            notes, updated_keys = _map_selected_notes(track, note_keys_by_id=note_keys_by_id, ids=selector.get("ids"), beat_range=selector.get("range"), total_beats=total_beats, mapper=lambda note: NoteEvent(_clamp(note.pitch + semitones, 0, 127), note.start_beat, note.duration_beats, note.velocity))
            note_keys_by_id.update(updated_keys)
            tracks[track_index] = TrackPlan(track.name, track.instrument, notes)
            changed_tracks.add(track.name)
        elif op == "quantize_notes":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            grid = float(operation.get("grid"))
            if grid not in QUANTIZE_GRIDS:
                raise EditorPatchError("grid must be one of 0.125, 0.25, 0.5, 1.0.")
            track = tracks[track_index]
            selector = _note_selector(operation, track)
            note_keys_by_id = base_note_keys_by_track_id.get(str(operation.get("track_id") or ""), {})
            notes, updated_keys = _map_selected_notes(track, note_keys_by_id=note_keys_by_id, ids=selector.get("ids"), beat_range=selector.get("range"), total_beats=total_beats, mapper=lambda note: NoteEvent(note.pitch, _round_beat(round(note.start_beat / grid) * grid), note.duration_beats, note.velocity))
            note_keys_by_id.update(updated_keys)
            tracks[track_index] = TrackPlan(track.name, track.instrument, notes)
            changed_tracks.add(track.name)
        elif op == "scale_velocity":
            track_index = _track_index_for_plan(operation, tracks, base_track_names_by_id)
            factor = _float_range(operation.get("factor"), "factor", 0.25, 2.0)
            track = tracks[track_index]
            selector = _note_selector(operation, track)
            note_keys_by_id = base_note_keys_by_track_id.get(str(operation.get("track_id") or ""), {})
            notes, updated_keys = _map_selected_notes(track, note_keys_by_id=note_keys_by_id, ids=selector.get("ids"), beat_range=selector.get("range"), total_beats=total_beats, mapper=lambda note: NoteEvent(note.pitch, note.start_beat, note.duration_beats, _clamp(round(note.velocity * factor), 1, 127)))
            note_keys_by_id.update(updated_keys)
            tracks[track_index] = TrackPlan(track.name, track.instrument, notes)
            changed_tracks.add(track.name)
    _validate_note_limits(tracks)
    edited = SongPlan(
        title=parent_plan.title,
        key=parent_plan.key,
        tempo_bpm=parent_plan.tempo_bpm,
        meter=parent_plan.meter,
        sections=sections,
        tracks=[TrackPlan(track.name, track.instrument, _sorted_notes(track.notes)) for track in tracks],
        quality=parent_plan.quality,
    )
    edited = attach_quality(edited)
    edited.validate()
    summary = {
        "operation_counts": summary_counts,
        "changed_sections": sorted(changed_sections),
        "changed_tracks": sorted(changed_tracks),
    }
    return EditorPatchResult(plan=edited, patch=patch, summary=summary, warnings=warnings)


def summarize_editor_patch(result: EditorPatchResult) -> dict[str, Any]:
    return {
        "operation_count": len(result.patch.operations),
        "changed_sections": list(result.summary.get("changed_sections") or []),
        "changed_tracks": list(result.summary.get("changed_tracks") or []),
        "operation_counts": dict(result.summary.get("operation_counts") or {}),
        "warnings": list(result.warnings),
    }


def describe_editor_operations(operations: list[dict[str, Any]]) -> list[str]:
    descriptions = []
    for operation in operations:
        op = str(operation.get("op") or "")
        if op == "add_section":
            descriptions.append(f"add_section: {_operation_name(operation, 'name', 'section')} after {operation.get('after_section_id') or 'end'}")
        elif op == "duplicate_section":
            descriptions.append(f"duplicate_section: {operation.get('section_id') or '?'} -> {_operation_name(operation, 'name', 'copy')}")
        elif op == "delete_section":
            descriptions.append(f"delete_section: {operation.get('section_id') or '?'}")
        elif op == "resize_section":
            descriptions.append(f"resize_section: {operation.get('section_id') or '?'} -> {operation.get('bars')} bars")
        elif op == "move_section":
            descriptions.append(f"move_section: {operation.get('section_id') or '?'} after {operation.get('after_section_id') or 'start'}")
        elif op == "add_track":
            descriptions.append(f"add_track: {_operation_name(operation, 'name', 'track')}")
        elif op == "duplicate_track":
            descriptions.append(f"duplicate_track: {operation.get('track_id') or '?'} -> {_operation_name(operation, 'name', 'copy')}")
        elif op == "delete_track":
            descriptions.append(f"delete_track: {operation.get('track_id') or '?'}")
        elif op == "rename_track":
            descriptions.append(f"rename_track: {operation.get('track_id') or '?'} -> {_operation_name(operation, 'name', 'track')}")
        elif op == "set_section_chords":
            descriptions.append(f"set_section_chords: {operation.get('section_id') or '?'}")
        elif op == "set_section_lyrics":
            descriptions.append(f"set_section_lyrics: {operation.get('section_id') or '?'}")
        elif op == "set_track_instrument":
            descriptions.append(f"set_track_instrument: {operation.get('track_id') or '?'}")
        elif op in {"add_note", "update_note", "delete_notes", "move_notes", "transpose_notes", "quantize_notes", "scale_velocity"}:
            descriptions.append(f"{op}: {operation.get('track_id') or '?'}")
        else:
            descriptions.append(op or "unknown_operation")
    return descriptions


def _operation_counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for operation in operations:
        op = str(operation.get("op") or "unknown_operation")
        counts[op] = counts.get(op, 0) + 1
    return counts


def _operation_name(operation: dict[str, Any], field_name: str, fallback: str) -> str:
    value = sanitize_sensitive_text(str(operation.get(field_name) or "")).strip()
    return value[:80] if value else fallback


def _structure_edit_summary(operations: list[dict[str, Any]]) -> dict[str, Any]:
    section_ops = {"add_section", "duplicate_section", "delete_section", "resize_section", "move_section"}
    track_ops = {"add_track", "duplicate_track", "delete_track", "rename_track"}
    counts = _operation_counts([operation for operation in operations if str(operation.get("op") or "") in section_ops | track_ops])
    if not counts:
        return {}
    return {
        "section_operations": {key: value for key, value in counts.items() if key in section_ops},
        "track_operations": {key: value for key, value in counts.items() if key in track_ops},
        "operation_text": [
            text
            for operation, text in zip(operations, describe_editor_operations(operations))
            if str(operation.get("op") or "") in section_ops | track_ops
        ],
    }


def editor_edit_metadata(
    *,
    project_id: str,
    parent_version_id: str,
    parent_job_id: str,
    preview_id: str,
    patch: EditorPatch,
    result: EditorPatchResult,
    created_at: str | None = None,
) -> dict[str, Any]:
    summary = summarize_editor_patch(result)
    structure = _structure_edit_summary(patch.operations)
    return sanitize_metadata(
        {
            "schema_version": 2,
            "edit_source": "visual_editor",
            "edit_type": "manual_editor_edit",
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
            "summary": {
                **summary["operation_counts"],
                "changed_sections": summary["changed_sections"],
                "changed_tracks": summary["changed_tracks"],
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


def section_id_for_index(index: int) -> str:
    return f"section-{index + 1:03d}"


def track_id_for_index(index: int) -> str:
    return f"track-{index + 1:03d}"


def note_id_for(track_id: str, note_index: int, note: NoteEvent) -> str:
    raw = f"{track_id}:{note_index}:{note.pitch}:{note.start_beat:.6f}:{note.duration_beats:.6f}:{note.velocity}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"note-{track_id}-{note_index + 1:04d}-{digest}"


def _section_index(operation: dict[str, Any]) -> int:
    section_id = str(operation.get("section_id") or "").strip()
    if not re.match(r"^section-[0-9]{3}$", section_id):
        raise EditorPatchError("section_id is required.")
    index = int(section_id.split("-")[1]) - 1
    if index < 0:
        raise EditorPatchError("section_id is out of range.")
    return index


def _section_index_for_plan(operation: dict[str, Any], sections: list[SongSection], base_names_by_id: dict[str, str | None] | None = None) -> int:
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


def _track_index(operation: dict[str, Any]) -> int:
    track_id = str(operation.get("track_id") or "").strip()
    if not re.match(r"^track-[0-9]{3}$", track_id):
        raise EditorPatchError("track_id is required.")
    index = int(track_id.split("-")[1]) - 1
    if index < 0:
        raise EditorPatchError("track_id is out of range.")
    return index


def _track_index_for_plan(operation: dict[str, Any], tracks: list[TrackPlan], base_names_by_id: dict[str, str | None] | None = None) -> int:
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


def _chords(value: Any) -> list[str]:
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


def _clean_lyrics(value: Any) -> str:
    lyrics = sanitize_sensitive_text(str(value or ""))
    if _CONTROL_CHARS.search(lyrics):
        raise EditorPatchError("lyrics must not contain control characters.")
    if len(lyrics) > MAX_LYRICS_LENGTH:
        raise EditorPatchError(f"lyrics must be {MAX_LYRICS_LENGTH} characters or fewer.")
    return lyrics


def _bounded_text(value: Any, max_length: int) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    if _CONTROL_CHARS.search(text):
        raise EditorPatchError("text fields must not contain control characters.")
    return text[:max_length].rstrip()


def _note(value: Any, total_beats: float) -> NoteEvent:
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
    operation: dict[str, Any],
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


def _note_ids(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise EditorPatchError("note_ids must be a non-empty list.")
    if len(value) > MAX_NOTE_IDS_PER_OPERATION:
        raise EditorPatchError(f"note_ids supports at most {MAX_NOTE_IDS_PER_OPERATION} notes.")
    result = [str(item).strip() for item in value if str(item).strip()]
    if len(result) != len(value):
        raise EditorPatchError("note_ids must not contain empty ids.")
    return result


def _base_note_keys_by_track_id(state: dict[str, Any]) -> dict[str, dict[str, NoteKey | None]]:
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


def _note_key_from_mapping(note: dict[str, Any]) -> NoteKey:
    return (
        int(note.get("pitch")),
        _round_beat(float(note.get("start_beat"))),
        _round_beat(float(note.get("duration_beats"))),
        int(note.get("velocity", 90)),
    )


def _note_index_by_key(notes: list[NoteEvent], target_key: NoteKey, note_id: str) -> int:
    for index, note in enumerate(notes):
        if _note_key(note) == target_key:
            return index
    raise EditorPatchError(f"Note {note_id} is no longer available in this patch.")


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


def _note_selector(operation: dict[str, Any], track: TrackPlan) -> dict[str, Any]:
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
    mapper: Any,
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


def _beat_range(value: dict[str, Any]) -> tuple[float, float]:
    start = _float_min(value.get("start_beat"), "range.start_beat", 0.0)
    end = _float_min(value.get("end_beat"), "range.end_beat", 0.0)
    if end <= start:
        raise EditorPatchError("range.end_beat must be greater than range.start_beat.")
    return start, end


def _section_from_operation(operation: dict[str, Any], sections: list[SongSection]) -> SongSection:
    name = _unique_section_name(operation.get("name"), sections)
    bars = _int_range(operation.get("bars"), "bars", 1, MAX_SECTION_BARS)
    chords = _chords(operation.get("chords") or sections[-1].chords if sections else operation.get("chords"))
    lyrics = _clean_lyrics(operation.get("lyrics", ""))
    return SongSection(name, 1, bars, chords, lyrics)


def _unique_section_name(value: Any, sections: list[SongSection]) -> str:
    name = _bounded_text(value, MAX_SECTION_NAME_LENGTH)
    if not name:
        raise EditorPatchError("section name must not be empty.")
    existing = {section.name.strip().lower() for section in sections}
    if name.strip().lower() in existing:
        raise EditorPatchError(f"Duplicate section name: {name}.")
    return name


def _unique_track_name(value: Any, tracks: list[TrackPlan]) -> str:
    name = _bounded_text(value, MAX_TRACK_NAME_LENGTH)
    if not name:
        raise EditorPatchError("track name must not be empty.")
    existing = {track.name.strip().lower() for track in tracks}
    if name.strip().lower() in existing:
        raise EditorPatchError(f"Duplicate track name: {name}.")
    return name


def _optional_after_section_index(
    operation: dict[str, Any],
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


def _choice(value: Any, name: str, choices: set[str]) -> str:
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


def _int_range(value: Any, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EditorPatchError(f"{name} must be an integer.") from exc
    if number < low or number > high:
        raise EditorPatchError(f"{name} must be between {low} and {high}.")
    return number


def _float_min(value: Any, name: str, minimum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorPatchError(f"{name} must be a number.") from exc
    if number < minimum:
        raise EditorPatchError(f"{name} must be >= {minimum}.")
    return _round_beat(number)


def _float_range(value: Any, name: str, low: float, high: float) -> float:
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


def _quality_summary(plan: SongPlan) -> dict[str, Any]:
    quality = plan.quality or analyze_song_quality(plan)
    scores = quality.scores.to_dict() if quality.scores else {}
    return {"overall": scores.get("overall"), "dimension_scores": scores, "warnings": list(quality.warnings)}


def _preview_validator_report(plan: SongPlan, render_midi: bool) -> dict[str, Any]:
    return {
        "status": "passed",
        "checks": ["song_plan_schema", "song_plan_validation", *(("midi_render",) if render_midi else ())],
        "title": plan.title,
        "midi_exists": False,
        "midi_size": 0,
        "checked_at": now_iso(),
    }


def _append_preview_event(preview_dir: Path, event_type: str, payload: dict[str, Any], now: str | None = None) -> None:
    event = {"timestamp": now or now_iso(), "type": event_type, "payload": sanitize_metadata(payload)}
    with (preview_dir / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)
