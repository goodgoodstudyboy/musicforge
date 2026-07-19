# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, document_or as _document_or

import json as json
import math as math
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import PROGRAMS_BY_ROLE as PROGRAMS_BY_ROLE, _header_chunk as _header_chunk, _meta_track as _meta_track, _music_track as _music_track, _track_role as _track_role
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan
from song_agent.domains.studio.song_editor import EditorPreview as EditorPreview, build_editor_state as build_editor_state, song_plan_hash as song_plan_hash, validate_editor_preview_id as validate_editor_preview_id
from song_agent.domains.studio.editor_review import add_marker as add_marker, apply_review_patch as apply_review_patch, audition_review_row as audition_review_row, default_review as default_review, delete_marker as delete_marker, normalize_review as normalize_review, record_asset_created as record_asset_created, review_board as review_board, review_summary as audition_review_summary, update_marker as update_marker


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
    range: ImplementationDocument = field(default_factory=dict)
    track_mode: str = "all"
    track_ids: list[str] = field(default_factory=list)
    track_count: int = 0
    note_count: int = 0
    duration_beats: float = 0.0
    midi: ImplementationDocument = field(default_factory=dict)
    audio: ImplementationDocument = field(default_factory=dict)
    review: ImplementationDocument = field(default_factory=default_review)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "EditorAuditionManifest":
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

    def to_dict(self) -> DomainDocument:
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
        editor_state: DomainDocument | None = None,
        payload: DomainDocument,
        now: str | None = None,
    ) -> EditorAuditionManifest:
        if not isinstance(payload, dict):
            raise EditorAuditionError("audition payload must be an object.")
        now = now or now_iso()
        source = str(payload.get("source") or "preview").strip()
        if source not in AUDITION_SOURCES:
            raise EditorAuditionError("source must be parent or preview.")
        label = _bounded_label(payload.get("label"))
        range_payload = _document_or(payload.get("range"), {"mode": "full_song"})
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

    def review_board(self, preview_id: str | None = None, filters: DomainDocument | None = None) -> DomainDocument:
        auditions = self.list_auditions(preview_id) if preview_id else self.list_all_auditions()
        return review_board(auditions, filters=filters)

    def update_review(self, preview_id: str, audition_id: str, patch: DomainDocument, now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = apply_review_patch(manifest.review, patch, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_review_updated", _review_event_payload(updated), now)
            return updated

    def add_marker(self, preview_id: str, audition_id: str, payload: DomainDocument, now: str | None = None) -> EditorAuditionManifest:
        now = now or now_iso()
        with self.lock:
            manifest = self.read_audition(preview_id, audition_id)
            review = add_marker(manifest.review, payload, duration_beats=manifest.duration_beats, now=now)
            updated = self._write_manifest(EditorAuditionManifest.from_dict({**manifest.to_dict(), "review": review, "updated_at": now}))
            marker = (updated.review.get("markers") or [])[-1]
            _append_audition_event(self.audition_dir(preview_id, audition_id), "editor_audition_marker_added", {"marker_id": marker.get("marker_id"), "kind": marker.get("kind")}, now)
            return updated

    def update_marker(self, preview_id: str, audition_id: str, marker_id: str, patch: DomainDocument, now: str | None = None) -> EditorAuditionManifest:
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
    editor_state: DomainDocument | None = None,
    range_payload: DomainDocument | None = None,
    track_mode: str = "all",
    track_ids: list[str] | None = None,
    changed_sections: list[str] | None = None,
) -> tuple[SongPlan, DomainDocument]:
    range_payload = _document_or(range_payload, {"mode": "full_song"})
    track_ids = track_ids or []
    state = _document_or(editor_state, build_editor_state(plan))
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


def audition_summary_for_preview(project_dir: Path | str, preview_id: str) -> DomainDocument:
    store = EditorAuditionStore(project_dir)
    auditions = store.list_auditions(preview_id)
    return audition_summary(auditions)


def audition_summary(auditions: list[EditorAuditionManifest]) -> DomainDocument:
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


from song_agent.domains.studio import v142_ea_readiness as _v142_ea_readiness
from song_agent.domains.studio.v142_ea_readiness import _resolve_range as _resolve_range, _resolve_tracks as _resolve_tracks, _clip_sections as _clip_sections, _clip_notes as _clip_notes, _track_ids as _track_ids, _artifact_status as _artifact_status, _audition_status as _audition_status, _bounded_label as _bounded_label, _float as _float, _render_report as _render_report, _lock_for_project as _lock_for_project, _append_audition_event as _append_audition_event, _review_event_payload as _review_event_payload

_v142_ea_readiness.bind_globals(globals())
