from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, slugify, write_json
from song_agent.domains.creation.renderers.audio import RendererConfig, RendererError, render_audio
from song_agent.domains.creation.renderers.midi import CHANNELS_BY_ROLE, PROGRAMS_BY_ROLE, render_midi_stem
from song_agent.domains.creation.schemas.song import SongPlan, TrackPlan


STEM_STATUSES = {"not_started", "queued", "running", "completed", "failed", "skipped"}
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class StemRecord:
    stem_id: str
    track_name: str
    role: str
    instrument: str
    midi_path: str
    midi_exists: bool
    audio_path: str
    audio_exists: bool
    audio_status: str
    audio_error: str | None
    note_count: int
    duration_beats: float
    channel: int
    program: int | None
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StemRecord":
        status = str(data.get("audio_status") or "not_started")
        if status not in STEM_STATUSES:
            status = "not_started"
        return cls(
            stem_id=str(data["stem_id"]),
            track_name=str(data.get("track_name") or data["stem_id"]),
            role=str(data.get("role") or data["stem_id"]),
            instrument=str(data.get("instrument") or ""),
            midi_path=str(data.get("midi_path") or ""),
            midi_exists=bool(data.get("midi_exists", False)),
            audio_path=str(data.get("audio_path") or ""),
            audio_exists=bool(data.get("audio_exists", False)),
            audio_status=status,
            audio_error=None if data.get("audio_error") is None else str(data.get("audio_error")),
            note_count=int(data.get("note_count", 0) or 0),
            duration_beats=float(data.get("duration_beats", 0.0) or 0.0),
            channel=int(data.get("channel", 0) or 0),
            program=None if data.get("program") is None else int(data.get("program")),
            updated_at=str(data.get("updated_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StemManifest:
    version: int
    job_id: str
    source_song_plan: str
    source_hash: str
    created_at: str
    updated_at: str
    stems: list[StemRecord]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StemManifest":
        return cls(
            version=int(data.get("version", MANIFEST_VERSION) or MANIFEST_VERSION),
            job_id=str(data.get("job_id") or ""),
            source_song_plan=str(data.get("source_song_plan") or "data/song-plan.json"),
            source_hash=str(data.get("source_hash") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            stems=[StemRecord.from_dict(item) for item in data.get("stems", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "job_id": self.job_id,
            "source_song_plan": self.source_song_plan,
            "source_hash": self.source_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stems": [stem.to_dict() for stem in self.stems],
        }


def build_stem_manifest(plan: SongPlan, run_dir: Path, job_id: str, *, now: str) -> StemManifest:
    stems: list[StemRecord] = []
    used_ids: dict[str, int] = {}
    for track in plan.tracks:
        role = _track_role(track.name)
        stem_id = _unique_stem_id(role, track.name, used_ids)
        note_count = len(track.notes)
        midi_rel = _relative_stem_path("midi", f"{stem_id}.mid")
        audio_rel = _relative_stem_path("audio", f"{stem_id}.wav")
        midi_path = run_dir / midi_rel
        audio_path = run_dir / audio_rel
        stems.append(
            StemRecord(
                stem_id=stem_id,
                track_name=track.name,
                role=role,
                instrument=track.instrument,
                midi_path=midi_rel.as_posix(),
                midi_exists=midi_path.exists(),
                audio_path=audio_rel.as_posix(),
                audio_exists=audio_path.exists(),
                audio_status=_status_for_track(track, midi_path, audio_path),
                audio_error=None if note_count else "Track has no notes.",
                note_count=note_count,
                duration_beats=_track_duration(track),
                channel=CHANNELS_BY_ROLE.get(role, 0),
                program=PROGRAMS_BY_ROLE.get(role),
                updated_at=now,
            )
        )
    return StemManifest(
        version=MANIFEST_VERSION,
        job_id=job_id,
        source_song_plan="data/song-plan.json",
        source_hash=song_plan_hash(plan),
        created_at=now,
        updated_at=now,
        stems=stems,
    )


def render_stem_midis(plan: SongPlan, run_dir: Path, job_id: str, *, now: str, force: bool = False) -> StemManifest:
    manifest = build_stem_manifest(plan, run_dir, job_id, now=now)
    rendered_stems: list[StemRecord] = []
    for index, stem in enumerate(manifest.stems):
        midi_path = stem_midi_path(run_dir, manifest, stem.stem_id)
        if stem.note_count == 0:
            rendered_stems.append(_replace_stem(stem, midi_exists=False, audio_status="skipped", audio_error="Track has no notes.", updated_at=now))
            continue
        if force or not midi_path.exists():
            render_midi_stem(plan, index, midi_path)
        rendered_stems.append(
            _replace_stem(
                stem,
                midi_exists=midi_path.exists(),
                audio_exists=(run_dir / stem.audio_path).exists(),
                audio_status="completed" if (run_dir / stem.audio_path).exists() else "not_started",
                audio_error=None,
                updated_at=now,
            )
        )
    return write_stem_manifest(
        run_dir,
        StemManifest(
            version=manifest.version,
            job_id=manifest.job_id,
            source_song_plan=manifest.source_song_plan,
            source_hash=manifest.source_hash,
            created_at=manifest.created_at,
            updated_at=now,
            stems=rendered_stems,
        ),
    )


def read_stem_manifest(run_dir: Path) -> StemManifest | None:
    path = manifest_path(run_dir)
    if not path.exists():
        return None
    return StemManifest.from_dict(read_json(path))


def write_stem_manifest(run_dir: Path, manifest: StemManifest) -> StemManifest:
    write_json(manifest_path(run_dir), manifest.to_dict())
    return manifest


def load_or_preview_stem_manifest(plan: SongPlan, run_dir: Path, job_id: str, *, now: str) -> StemManifest:
    manifest = read_stem_manifest(run_dir)
    if manifest is not None:
        if stem_manifest_stale(manifest, plan):
            clear_stem_artifacts(run_dir)
            return build_stem_manifest(plan, run_dir, job_id, now=now)
        return refresh_stem_manifest(run_dir, manifest, now=now)
    return build_stem_manifest(plan, run_dir, job_id, now=now)


def refresh_stem_manifest(run_dir: Path, manifest: StemManifest, *, now: str) -> StemManifest:
    stems = []
    for stem in manifest.stems:
        midi_path = _ensure_stem_path_is_safe(run_dir, Path(stem.midi_path))
        audio_path = _ensure_stem_path_is_safe(run_dir, Path(stem.audio_path))
        status = stem.audio_status
        error = stem.audio_error
        if audio_path.exists():
            status = "completed"
            error = None
        elif status == "completed":
            status = "not_started"
        stems.append(
            _replace_stem(
                stem,
                midi_exists=midi_path.exists(),
                audio_exists=audio_path.exists(),
                audio_status=status,
                audio_error=error,
                updated_at=now,
            )
        )
    return StemManifest(
        version=manifest.version,
        job_id=manifest.job_id,
        source_song_plan=manifest.source_song_plan,
        source_hash=manifest.source_hash,
        created_at=manifest.created_at,
        updated_at=now,
        stems=stems,
    )


def render_stem_audio(
    run_dir: Path,
    config: RendererConfig,
    *,
    plan: SongPlan | None = None,
    stem_ids: list[str] | None = None,
    force: bool = False,
    now: str,
) -> StemManifest:
    manifest = read_stem_manifest(run_dir)
    if manifest is None:
        raise ValueError("Stem manifest is not available.")
    if plan is not None and stem_manifest_stale(manifest, plan):
        raise ValueError("Stem manifest is stale. Render stems again.")
    selected = set(stem_ids or [])
    if any(slugify(stem_id) != stem_id for stem_id in selected):
        raise FileNotFoundError("Stem not found.")
    unknown = selected - {stem.stem_id for stem in manifest.stems}
    if unknown:
        raise FileNotFoundError("Stem not found.")
    stems: list[StemRecord] = []
    for stem in manifest.stems:
        should_render = stem.stem_id in selected if selected else stem.audio_status != "completed"
        if not should_render:
            stems.append(stem)
            continue
        if stem.note_count == 0:
            stems.append(_replace_stem(stem, audio_status="skipped", audio_error="Track has no notes.", updated_at=now))
            continue
        midi_path = stem_midi_path(run_dir, manifest, stem.stem_id)
        audio_path = stem_audio_path(run_dir, manifest, stem.stem_id)
        if not midi_path.exists():
            stems.append(_replace_stem(stem, midi_exists=False, audio_status="failed", audio_error="Stem MIDI is not available.", updated_at=now))
            continue
        if audio_path.exists() and not force:
            stems.append(_replace_stem(stem, audio_exists=True, audio_status="completed", audio_error=None, updated_at=now))
            continue
        try:
            rendered = render_audio(midi_path, audio_path, config)
        except RendererError as exc:
            stems.append(_replace_stem(stem, audio_exists=False, audio_status="failed", audio_error=str(exc), updated_at=now))
            continue
        stems.append(
            _replace_stem(
                stem,
                midi_exists=midi_path.exists(),
                audio_exists=rendered.exists(),
                audio_status="completed",
                audio_error=None,
                updated_at=now,
            )
        )
    return write_stem_manifest(
        run_dir,
        StemManifest(
            version=manifest.version,
            job_id=manifest.job_id,
            source_song_plan=manifest.source_song_plan,
            source_hash=manifest.source_hash,
            created_at=manifest.created_at,
            updated_at=now,
            stems=stems,
        ),
    )


def manifest_path(run_dir: Path) -> Path:
    return run_dir / "stems" / "manifest.json"


def clear_stem_artifacts(run_dir: Path) -> None:
    stems_dir = run_dir / "stems"
    if not stems_dir.exists():
        return
    base = run_dir.resolve()
    target = stems_dir.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to delete stems outside the run directory.") from exc
    if target == base:
        raise ValueError("Refusing to delete run directory.")
    shutil.rmtree(target)


def stem_manifest_stale(manifest: StemManifest, plan: SongPlan) -> bool:
    return manifest.source_hash != song_plan_hash(plan)


def song_plan_hash(plan: SongPlan) -> str:
    payload = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stem_midi_path(run_dir: Path, manifest: StemManifest, stem_id: str) -> Path:
    stem = find_stem(manifest, stem_id)
    return _ensure_stem_path_is_safe(run_dir, Path(stem.midi_path))


def stem_audio_path(run_dir: Path, manifest: StemManifest, stem_id: str) -> Path:
    stem = find_stem(manifest, stem_id)
    return _ensure_stem_path_is_safe(run_dir, Path(stem.audio_path))


def find_stem(manifest: StemManifest, stem_id: str) -> StemRecord:
    if slugify(stem_id) != stem_id:
        raise FileNotFoundError("Stem not found.")
    for stem in manifest.stems:
        if stem.stem_id == stem_id:
            return stem
    raise FileNotFoundError("Stem not found.")


def _track_role(track_name: str) -> str:
    lower = track_name.lower()
    for role in CHANNELS_BY_ROLE:
        if role in lower:
            return role
    return slugify(track_name)


def _unique_stem_id(role: str, track_name: str, used_ids: dict[str, int]) -> str:
    base = slugify(role or track_name)
    if not base:
        base = "stem"
    count = used_ids.get(base, 0) + 1
    used_ids[base] = count
    return base if count == 1 else f"{base}-{count}"


def _track_duration(track: TrackPlan) -> float:
    if not track.notes:
        return 0.0
    return round(max(note.start_beat + note.duration_beats for note in track.notes), 3)


def _status_for_track(track: TrackPlan, midi_path: Path, audio_path: Path) -> str:
    if not track.notes:
        return "skipped"
    if audio_path.exists():
        return "completed"
    if midi_path.exists():
        return "not_started"
    return "not_started"


def _relative_stem_path(kind: str, filename: str) -> Path:
    return Path("stems") / kind / filename


def _ensure_stem_path_is_safe(run_dir: Path, path: Path) -> Path:
    base = (run_dir / "stems").resolve()
    target = (run_dir / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to access a path outside the job stems directory.") from exc
    return target


def _replace_stem(stem: StemRecord, **changes: Any) -> StemRecord:
    data = stem.to_dict()
    data.update(changes)
    return StemRecord.from_dict(data)
