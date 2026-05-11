from __future__ import annotations

import json
import math
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.music_quality import attach_quality
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.renderers.audio import RendererConfig, RendererError, render_audio
from song_agent.renderers.midi import PROGRAMS_BY_ROLE, _header_chunk, _meta_track, _music_track, _track_role
from song_agent.schemas.song import NoteEvent, SongPlan, SongSection, TrackPlan
from song_agent.song_editor import EditorPreview, build_editor_state, song_plan_hash, validate_editor_preview_id
from song_agent.editor_review import (
    add_marker,
    apply_review_patch,
    audition_review_row,
    default_review,
    delete_marker,
    normalize_review,
    record_asset_created,
    review_board,
    review_summary as audition_review_summary,
    update_marker,
)


EDITOR_AUDITION_SCHEMA_VERSION = 1
MAX_AUDITION_LABEL_LENGTH = 120
MAX_AUDITIONS_PER_PREVIEW = 500
AUDITION_SOURCES = {"preview", "parent"}
AUDITION_RANGE_MODES = {"full_song", "section", "changed_sections", "custom"}
AUDITION_TRACK_MODES = {"all", "solo", "mute"}
_LOCKS_GUARD = threading.RLock()
_STORE_LOCKS: dict[str, threading.RLock] = {}


class EditorAuditionError(ValueError):
    pass


class EditorAuditionUnavailableError(EditorAuditionError):
    pass


@dataclass(frozen=True)
class EditorAuditionManifest:
    schema_version: int
    audition_id: str
    project_id: str
    preview_id: str
    parent_version_id: str
    parent_job_id: str
    source: str
    source_plan_hash: str
    base_plan_hash: str
    label: str = ""
    status: str = "completed"
    created_at: str = ""
    updated_at: str = ""
    range: dict[str, Any] = field(default_factory=dict)
    track_mode: str = "all"
    track_ids: list[str] = field(default_factory=list)
    track_count: int = 0
    note_count: int = 0
    duration_beats: float = 0.0
    midi: dict[str, Any] = field(default_factory=dict)
    audio: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=default_review)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditorAuditionManifest":
        if not isinstance(data, dict):
            raise EditorAuditionError("audition manifest must be an object.")
        source = str(data.get("source") or "preview").strip()
        if source not in AUDITION_SOURCES:
            source = "preview"
        track_mode = str(data.get("track_mode") or "all").strip()
        if track_mode not in AUDITION_TRACK_MODES:
            track_mode = "all"
        return cls(
            schema_version=int(data.get("schema_version", EDITOR_AUDITION_SCHEMA_VERSION) or EDITOR_AUDITION_SCHEMA_VERSION),
            audition_id=validate_editor_audition_id(str(data.get("audition_id") or "audition-001")),
            project_id=str(data.get("project_id") or ""),
            preview_id=validate_editor_preview_id(str(data.get("preview_id") or "preview-001")),
            parent_version_id=str(data.get("parent_version_id") or ""),
            parent_job_id=str(data.get("parent_job_id") or ""),
            source=source,
            source_plan_hash=str(data.get("source_plan_hash") or ""),
            base_plan_hash=str(data.get("base_plan_hash") or ""),
            label=_bounded_label(data.get("label")),
            status=_audition_status(data.get("status")),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            range=sanitize_metadata(dict(data.get("range") or {})),
            track_mode=track_mode,
            track_ids=[str(item) for item in data.get("track_ids", []) if str(item).strip()],
            track_count=max(0, int(data.get("track_count") or 0)),
            note_count=max(0, int(data.get("note_count") or 0)),
            duration_beats=max(0.0, float(data.get("duration_beats") or 0.0)),
            midi=_artifact_status(data.get("midi"), status_key="completed"),
            audio=_artifact_status(data.get("audio"), status_key="not_started"),
            review=normalize_review(data.get("review"), duration_beats=max(0.0, float(data.get("duration_beats") or 0.0))),
            warnings=[sanitize_sensitive_text(str(item)) for item in data.get("warnings", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EditorAuditionStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.preview_root = self.project_dir / "editor-previews"
        self.lock = _lock_for_project(self.project_dir)

    def create_audition(
        self,
        *,
        project_id: str,
        preview: EditorPreview,
        source_plan: SongPlan,
        editor_state: dict[str, Any] | None = None,
        payload: dict[str, Any],
        now: str | None = None,
    ) -> EditorAuditionManifest:
        if not isinstance(payload, dict):
            raise EditorAuditionError("audition payload must be an object.")
        now = now or now_iso()
        source = str(payload.get("source") or "preview").strip()
        if source not in AUDITION_SOURCES:
            raise EditorAuditionError("source must be parent or preview.")
        label = _bounded_label(payload.get("label"))
        range_payload = payload.get("range") if isinstance(payload.get("range"), dict) else {"mode": "full_song"}
        track_mode = str(payload.get("track_mode") or "all").strip()
        if track_mode not in AUDITION_TRACK_MODES:
            raise EditorAuditionError("track_mode must be all, solo, or mute.")
        track_ids = _track_ids(payload.get("track_ids"))
        audition_plan, summary = build_audition_plan(
            source_plan,
            editor_state=editor_state,
            range_payload=range_payload,
            track_mode=track_mode,
            track_ids=track_ids,
            changed_sections=preview.changed_sections,
        )
        with self.lock:
            root = self.auditions_root(preview.preview_id)
            root.mkdir(parents=True, exist_ok=True)
            if len(list(root.glob("audition-*/audition.json"))) >= MAX_AUDITIONS_PER_PREVIEW:
                raise EditorAuditionError(f"Editor preview supports at most {MAX_AUDITIONS_PER_PREVIEW} auditions.")
            audition_id, audition_dir = self._reserve_audition_dir(preview.preview_id)
            midi_url = f"/api/projects/{project_id}/editor-previews/{preview.preview_id}/auditions/{audition_id}/midi"
            audio_url = f"/api/projects/{project_id}/editor-previews/{preview.preview_id}/auditions/{audition_id}/audio"
            manifest = EditorAuditionManifest(
                schema_version=EDITOR_AUDITION_SCHEMA_VERSION,
                audition_id=audition_id,
                project_id=project_id,
                preview_id=preview.preview_id,
                parent_version_id=preview.parent_version_id,
                parent_job_id=preview.parent_job_id,
                source=source,
                source_plan_hash=song_plan_hash(source_plan),
                base_plan_hash=preview.base_plan_hash,
                label=label,
                status="completed",
                created_at=now,
                updated_at=now,
                range=summary["range"],
                track_mode=track_mode,
                track_ids=list(summary["track_ids"]),
                track_count=int(summary["track_count"]),
                note_count=int(summary["note_count"]),
                duration_beats=float(summary["duration_beats"]),
                midi={"status": "completed", "exists": False, "size_bytes": 0, "url": midi_url},
                audio={"status": "not_started", "exists": False, "size_bytes": 0, "url": audio_url},
                review=default_review(),
                warnings=list(summary["warnings"]),
            )
            try:
                write_json(audition_dir / "song-plan.json", audition_plan.to_dict())
                render_audition_midi(audition_plan, self.midi_path(preview.preview_id, audition_id))
                midi_size = self.midi_path(preview.preview_id, audition_id).stat().st_size
                manifest = EditorAuditionManifest.from_dict(
                    {
                        **manifest.to_dict(),
                        "midi": {"status": "completed", "exists": True, "size_bytes": midi_size, "url": midi_url},
                    }
                )
                write_json(audition_dir / "render-report.json", _render_report(manifest))
                write_json(audition_dir / "audition.json", manifest.to_dict())
                _append_audition_event(audition_dir, "editor_audition_created", {"source": source, "note_count": manifest.note_count}, now)
            except Exception:
                if audition_dir.exists() and not (audition_dir / "audition.json").exists():
                    shutil.rmtree(audition_dir)
                raise
            return manifest

    def render_audition_audio(
        self,
        *,
        project_id: str,
        preview_id: str,
        audition_id: str,
        config: RendererConfig,
        now: str | None = None,
    ) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            audition_dir = self.audition_dir(preview_id, audition_id)
            midi_path = self.midi_path(preview_id, audition_id)
            if not midi_path.exists():
                plan = self.read_plan(preview_id, audition_id)
                render_audition_midi(plan, midi_path)
            try:
                wav_path = render_audio(midi_path, self.audio_path(preview_id, audition_id), config)
            except RendererError as exc:
                failed = EditorAuditionManifest.from_dict(
                    {
                        **manifest.to_dict(),
                        "status": "failed",
                        "audio": {
                            **manifest.audio,
                            "status": "failed",
                            "exists": False,
                            "size_bytes": 0,
                            "error": sanitize_sensitive_text(str(exc)),
                        },
                        "updated_at": now,
                    }
                )
                write_json(audition_dir / "audition.json", failed.to_dict())
                write_json(audition_dir / "render-report.json", _render_report(failed))
                _append_audition_event(audition_dir, "editor_audition_audio_failed", {"error": failed.audio.get("error")}, now)
                raise
            updated = EditorAuditionManifest.from_dict(
                {
                    **manifest.to_dict(),
                    "status": "completed",
                    "audio": {
                        **manifest.audio,
                        "status": "completed",
                        "exists": True,
                        "size_bytes": wav_path.stat().st_size,
                        "url": f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/audio",
                        "error": None,
                    },
                    "updated_at": now,
                }
            )
            write_json(audition_dir / "audition.json", updated.to_dict())
            write_json(audition_dir / "render-report.json", _render_report(updated))
            _append_audition_event(audition_dir, "editor_audition_audio_rendered", {"size_bytes": updated.audio.get("size_bytes")}, now)
            return updated

    def read_audition(self, preview_id: str, audition_id: str) -> EditorAuditionManifest:
        return EditorAuditionManifest.from_dict(read_json(self.audition_dir(preview_id, audition_id) / "audition.json"))

    def read_plan(self, preview_id: str, audition_id: str) -> SongPlan:
        return SongPlan.from_dict(read_json(self.audition_dir(preview_id, audition_id) / "song-plan.json"))

    def list_auditions(self, preview_id: str) -> list[EditorAuditionManifest]:
        validate_editor_preview_id(preview_id)
        with self.lock:
            root = self.auditions_root(preview_id)
            if not root.exists():
                return []
            auditions: list[EditorAuditionManifest] = []
            for manifest_path in root.glob("audition-*/audition.json"):
                try:
                    auditions.append(EditorAuditionManifest.from_dict(read_json(manifest_path)))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
            return sorted(auditions, key=lambda item: (item.updated_at or item.created_at, item.audition_id), reverse=True)

    def list_all_auditions(self) -> list[EditorAuditionManifest]:
        with self.lock:
            if not self.preview_root.exists():
                return []
            auditions: list[EditorAuditionManifest] = []
            for manifest_path in self.preview_root.glob("preview-*/auditions/audition-*/audition.json"):
                try:
                    auditions.append(EditorAuditionManifest.from_dict(read_json(manifest_path)))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
            return sorted(auditions, key=lambda item: (item.updated_at or item.created_at, item.audition_id), reverse=True)

    def review_board(self, preview_id: str | None = None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        auditions = self.list_auditions(preview_id) if preview_id else self.list_all_auditions()
        return review_board(auditions, filters=filters)

    def update_review(self, preview_id: str, audition_id: str, patch: dict[str, Any], now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = apply_review_patch(manifest.review, patch, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_review_updated", _review_event_payload(updated), now)
            return updated

    def add_marker(self, preview_id: str, audition_id: str, payload: dict[str, Any], now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = add_marker(manifest.review, payload, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            marker = (updated.review.get("markers") or [])[-1]
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_marker_added", {"marker_id": marker.get("marker_id"), "kind": marker.get("kind")}, now)
            return updated

    def update_marker(self, preview_id: str, audition_id: str, marker_id: str, patch: dict[str, Any], now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = update_marker(manifest.review, marker_id, patch, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_marker_updated", {"marker_id": marker_id}, now)
            return updated

    def delete_marker(self, preview_id: str, audition_id: str, marker_id: str, now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = delete_marker(manifest.review, marker_id, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_marker_deleted", {"marker_id": marker_id}, now)
            return updated

    def record_asset_created(self, preview_id: str, audition_id: str, asset_id: str, now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = record_asset_created(manifest.review, asset_id, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_asset_created", {"asset_id": asset_id}, now)
            return updated

    def delete_audition(self, preview_id: str, audition_id: str) -> None:
        with self.lock:
            raw_dir = self.auditions_root(preview_id) / validate_editor_audition_id(audition_id)
            if raw_dir.is_symlink():
                raise ValueError("Refusing to delete symlink editor audition.")
            audition_dir = self.audition_dir(preview_id, audition_id)
            if not audition_dir.exists():
                raise FileNotFoundError(audition_id)
            if audition_dir.resolve().is_symlink():
                raise ValueError("Refusing to delete symlink editor audition.")
            shutil.rmtree(audition_dir)

    def _write_manifest(self, manifest: EditorAuditionManifest) -> EditorAuditionManifest:
        write_json(self.audition_dir(manifest.preview_id, manifest.audition_id) / "audition.json", manifest.to_dict())
        return manifest

    def auditions_root(self, preview_id: str) -> Path:
        preview_id = validate_editor_preview_id(preview_id)
        preview_dir = self._preview_dir(preview_id)
        return preview_dir / "auditions"

    def audition_dir(self, preview_id: str, audition_id: str) -> Path:
        audition_id = validate_editor_audition_id(audition_id)
        base = self.auditions_root(preview_id).resolve()
        target = (base / audition_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside editor auditions.") from exc
        return target

    def midi_path(self, preview_id: str, audition_id: str) -> Path:
        return self.audition_dir(preview_id, audition_id) / "song.mid"

    def audio_path(self, preview_id: str, audition_id: str) -> Path:
        return self.audition_dir(preview_id, audition_id) / "song.wav"

    def _reserve_audition_dir(self, preview_id: str) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            audition_id = f"audition-{index:03d}"
            audition_dir = self.audition_dir(preview_id, audition_id)
            try:
                audition_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return audition_id, audition_dir
        raise RuntimeError("Could not allocate editor audition id.")

    def _preview_dir(self, preview_id: str) -> Path:
        preview_id = validate_editor_preview_id(preview_id)
        base = self.preview_root.resolve()
        target = (base / preview_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside editor previews.") from exc
        return target


def build_audition_plan(
    plan: SongPlan,
    *,
    editor_state: dict[str, Any] | None = None,
    range_payload: dict[str, Any] | None = None,
    track_mode: str = "all",
    track_ids: list[str] | None = None,
    changed_sections: list[str] | None = None,
) -> tuple[SongPlan, dict[str, Any]]:
    range_payload = range_payload if isinstance(range_payload, dict) else {"mode": "full_song"}
    track_ids = track_ids or []
    state = editor_state if isinstance(editor_state, dict) else build_editor_state(plan)
    start_beat, end_beat, range_summary = _resolve_range(state, range_payload, changed_sections or [])
    selected_track_indexes, selected_track_ids = _resolve_tracks(state, track_mode, track_ids)
    sections = _clip_sections(plan, state, start_beat, end_beat)
    tracks: list[TrackPlan] = []
    note_count = 0
    for track_index in selected_track_indexes:
        source_track = plan.tracks[track_index]
        notes = _clip_notes(source_track.notes, start_beat, end_beat)
        if notes:
            note_count += len(notes)
        tracks.append(TrackPlan(source_track.name, source_track.instrument, notes))
    if note_count <= 0:
        raise EditorAuditionUnavailableError("Audition produced no notes.")
    audition_plan = SongPlan(
        title=f"{plan.title} Audition",
        key=plan.key,
        tempo_bpm=plan.tempo_bpm,
        meter=plan.meter,
        sections=sections,
        tracks=tracks,
    )
    audition_plan = attach_quality(audition_plan)
    return audition_plan, {
        "range": range_summary,
        "track_mode": track_mode,
        "track_ids": selected_track_ids,
        "track_count": len(tracks),
        "note_count": note_count,
        "duration_beats": round(end_beat - start_beat, 6),
        "warnings": [],
    }


def validate_editor_audition_id(audition_id: str) -> str:
    if not re.match(r"^audition-[0-9]{3,6}$", audition_id):
        raise ValueError("Invalid editor audition id.")
    return audition_id


def render_audition_midi(plan: SongPlan, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    music_tracks = [track for track in plan.tracks if track.notes]
    if not music_tracks:
        raise EditorAuditionUnavailableError("Audition produced no notes.")
    tracks = [_meta_track(plan)]
    for track in music_tracks:
        role = _track_role(track.name)
        channel = 9 if role == "drums" else {"melody": 0, "chords": 1, "bass": 2}.get(role, 0)
        program = PROGRAMS_BY_ROLE.get(role)
        tracks.append(_music_track(track.notes, channel=channel, program=program))
    output_path.write_bytes(_header_chunk(len(tracks)) + b"".join(tracks))
    return output_path


def audition_summary_for_preview(project_dir: Path | str, preview_id: str) -> dict[str, Any]:
    store = EditorAuditionStore(project_dir)
    auditions = store.list_auditions(preview_id)
    return audition_summary(auditions)


def audition_summary(auditions: list[EditorAuditionManifest]) -> dict[str, Any]:
    sources = sorted({item.source for item in auditions})
    track_modes = sorted({item.track_mode for item in auditions})
    ranges = sorted({str(item.range.get("mode") or "") for item in auditions if isinstance(item.range, dict)})
    review = audition_review_summary(auditions)
    return sanitize_metadata(
        {
            "preview_audio_rendered": any(item.source == "preview" and item.audio.get("status") == "completed" for item in auditions),
            "audition_count": len(auditions),
            "sources": sources,
            "track_modes": track_modes,
            "ranges": ranges,
            "reviewed_count": review.get("reviewed_count", 0),
            "favorite_count": review.get("favorite_count", 0),
            "best_rating": review.get("best_rating", 0),
            "average_rating": review.get("average_rating", 0),
            "status_counts": review.get("status_counts", {}),
            "marker_count": review.get("marker_count", 0),
            "asset_count": review.get("asset_count", 0),
        }
    )


def _resolve_range(state: dict[str, Any], payload: dict[str, Any], changed_sections: list[str]) -> tuple[float, float, dict[str, Any]]:
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


def _resolve_tracks(state: dict[str, Any], track_mode: str, track_ids: list[str]) -> tuple[list[int], list[str]]:
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


def _clip_sections(plan: SongPlan, state: dict[str, Any], start_beat: float, end_beat: float) -> list[SongSection]:
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


def _track_ids(value: Any) -> list[str]:
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


def _artifact_status(value: Any, *, status_key: str) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
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


def _audition_status(value: Any) -> str:
    status = str(value or "completed").strip()
    if status not in {"not_started", "running", "completed", "failed", "deleted"}:
        return "completed"
    return status


def _bounded_label(value: Any) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    return text[:MAX_AUDITION_LABEL_LENGTH].rstrip()


def _float(value: Any, name: str) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError) as exc:
        raise EditorAuditionError(f"{name} must be a number.") from exc


def _render_report(manifest: EditorAuditionManifest) -> dict[str, Any]:
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


def _append_audition_event(audition_dir: Path, event_type: str, payload: dict[str, Any], now: str | None = None) -> None:
    event = {"timestamp": now or now_iso(), "event": event_type, **sanitize_metadata(payload)}
    path = audition_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def _review_event_payload(manifest: EditorAuditionManifest) -> dict[str, Any]:
    row = audition_review_row(manifest)
    review = row.get("review") if isinstance(row.get("review"), dict) else {}
    return {
        "rating": review.get("rating", 0),
        "status": review.get("status", "unreviewed"),
        "favorite": bool(review.get("favorite", False)),
        "marker_count": len(review.get("markers") or []),
    }
