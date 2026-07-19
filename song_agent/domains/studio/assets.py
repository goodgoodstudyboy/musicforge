# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_list as _as_list

import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan


ASSET_ROOT = Path(".musicforge") / "assets"
ASSET_ID_PATTERN = re.compile(r"^asset-[0-9]{3,6}$")
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


@dataclass(frozen=True)
class CreativeAsset:
    schema_version: int
    asset_id: str
    asset_type: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    style: str = ""
    mood: str = ""
    key: str = "C"
    tempo_bpm: int = 92
    meter: str = "4/4"
    duration_beats: float = 4.0
    quality_score: int | None = None
    favorite: bool = False
    hidden: bool = False
    usage_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    source: ImplementationDocument = field(default_factory=dict)
    content: ImplementationDocument = field(default_factory=dict)
    preview: ImplementationDocument = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "CreativeAsset":
        asset_id = validate_asset_id(str(data.get("asset_id") or "asset-001"))
        asset_type = str(data.get("asset_type") or "").strip()
        if asset_type not in ASSET_TYPES:
            raise ValueError(f"Unsupported asset_type: {asset_type}.")
        tags = _clean_tags(data.get("tags", []))
        tempo = int(data.get("tempo_bpm") or 92)
        if tempo < 40 or tempo > 240:
            raise ValueError("tempo_bpm must be between 40 and 240.")
        duration = float(data.get("duration_beats") or 4.0)
        if duration <= 0 or duration > 256:
            raise ValueError("duration_beats must be greater than 0 and at most 256.")
        quality_score = _optional_score(data.get("quality_score"))
        content = dict(data.get("content") or {})
        _validate_content(content)
        preview = _preview_dict(data.get("preview"))
        asset = cls(
            schema_version=int(data.get("schema_version", ASSET_SCHEMA_VERSION) or ASSET_SCHEMA_VERSION),
            asset_id=asset_id,
            asset_type=asset_type,
            name=_bounded_text(data.get("name"), "name", 120) or asset_id,
            description=_bounded_text(data.get("description"), "description", 1000),
            tags=tags,
            style=_bounded_text(data.get("style"), "style", 120),
            mood=_bounded_text(data.get("mood"), "mood", 120),
            key=_bounded_text(data.get("key"), "key", 40) or "C",
            tempo_bpm=tempo,
            meter=_bounded_text(data.get("meter"), "meter", 16) or "4/4",
            duration_beats=duration,
            quality_score=quality_score,
            favorite=bool(data.get("favorite", False)),
            hidden=bool(data.get("hidden", False)),
            usage_count=max(0, int(data.get("usage_count") or 0)),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            source=sanitize_asset_metadata(dict(data.get("source") or {})),
            content=content,
            preview=preview,
        )
        _validate_asset_size(asset)
        return asset

    def to_dict(self) -> DomainDocument:
        return asdict(self)


class AssetStore:
    def __init__(self, root: Path | str = ASSET_ROOT):
        self.root = Path(root)
        self.lock = threading.RLock()

    def list_assets(self, include_hidden: bool = False, filters: DomainDocument | None = None) -> list[CreativeAsset]:
        filters = filters or {}
        assets: list[CreativeAsset] = []
        if not self.root.exists():
            return []
        for path in self.root.glob("*/asset.json"):
            try:
                asset = CreativeAsset.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if asset.hidden and not include_hidden:
                continue
            if _asset_matches(asset, filters):
                assets.append(asset)
        return sorted(assets, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_asset(self, asset_id: str) -> CreativeAsset:
        asset_dir = self.asset_dir(asset_id)
        path = asset_dir / "asset.json"
        if not path.exists():
            raise FileNotFoundError(asset_id)
        return CreativeAsset.from_dict(read_json(path))

    def create_asset(self, payload: DomainDocument, now: str | None = None) -> CreativeAsset:
        now = now or now_iso()
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            asset_id = self._next_asset_id()
            data = {
                **payload,
                "schema_version": ASSET_SCHEMA_VERSION,
                "asset_id": asset_id,
                "created_at": now,
                "updated_at": now,
                "usage_count": 0,
                "preview": _preview_dict(payload.get("preview")),
            }
            asset = CreativeAsset.from_dict(data)
            asset_dir = self.asset_dir(asset.asset_id)
            try:
                asset_dir.mkdir(parents=True, exist_ok=False)
                write_json(asset_dir / "asset.json", asset.to_dict())
                if isinstance(payload.get("source_fragment"), dict):
                    write_json(asset_dir / "source-fragment.json", sanitize_asset_metadata(payload["source_fragment"]))
                _append_asset_event(asset_dir, "asset_created", {"asset_type": asset.asset_type}, now)
            except Exception:
                if asset_dir.exists() and not (asset_dir / "asset.json").exists():
                    shutil.rmtree(asset_dir)
                raise
            return asset

    def update_asset(self, asset_id: str, patch: DomainDocument) -> CreativeAsset:
        allowed = {"name", "description", "tags", "style", "mood", "favorite"}
        if any(key not in allowed for key in patch):
            raise ValueError("Only asset metadata fields can be updated.")
        asset = self.read_asset(asset_id)
        data = {**asset.to_dict(), **{key: patch[key] for key in patch if key in allowed}, "updated_at": now_iso()}
        updated = CreativeAsset.from_dict(data)
        self._write_asset(updated)
        _append_asset_event(self.asset_dir(asset_id), "asset_updated", {"fields": sorted(patch)}, updated.updated_at)
        return updated

    def hide_asset(self, asset_id: str, hidden: bool = True) -> CreativeAsset:
        asset = self.read_asset(asset_id)
        updated = CreativeAsset.from_dict({**asset.to_dict(), "hidden": hidden, "updated_at": now_iso()})
        self._write_asset(updated)
        _append_asset_event(self.asset_dir(asset_id), "asset_hidden" if hidden else "asset_unhidden", {}, updated.updated_at)
        return updated

    def favorite_asset(self, asset_id: str, favorite: bool = True) -> CreativeAsset:
        asset = self.read_asset(asset_id)
        updated = CreativeAsset.from_dict({**asset.to_dict(), "favorite": favorite, "updated_at": now_iso()})
        self._write_asset(updated)
        _append_asset_event(self.asset_dir(asset_id), "asset_favorited" if favorite else "asset_unfavorited", {}, updated.updated_at)
        return updated

    def delete_asset(self, asset_id: str) -> None:
        asset_dir = self.asset_dir(asset_id)
        if not asset_dir.exists():
            raise FileNotFoundError(asset_id)
        resolved = asset_dir.resolve()
        base = self.root.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to delete outside assets.") from exc
        if resolved.is_symlink():
            raise ValueError("Refusing to delete symlink asset.")
        shutil.rmtree(resolved)

    def render_asset_midi(self, asset_id: str) -> CreativeAsset:
        asset = self.read_asset(asset_id)
        if asset.asset_type not in RENDERABLE_TYPES:
            raise ValueError(f"{asset.asset_type} assets do not have MIDI preview.")
        plan = asset_preview_song_plan(asset)
        midi_path = asset_midi_path(self.asset_dir(asset_id))
        try:
            render_midi(plan, midi_path)
        except Exception as exc:
            updated = _with_preview(asset, midi_status="failed", midi_error=str(exc), midi_size_bytes=0, midi_url=None)
            self._write_asset(updated)
            write_json(self.asset_dir(asset_id) / "render-report.json", {"status": "failed", "error": str(exc), "rendered_at": now_iso()})
            return updated
        updated = _with_preview(
            asset,
            midi_status="completed",
            midi_error=None,
            midi_size_bytes=midi_path.stat().st_size,
            midi_url=asset_midi_url(asset_id),
        )
        self._write_asset(updated)
        write_json(self.asset_dir(asset_id) / "render-report.json", {"status": "completed", "midi_size_bytes": midi_path.stat().st_size, "rendered_at": now_iso()})
        return updated

    def render_asset_audio(self, asset_id: str, config: RendererConfig) -> CreativeAsset:
        asset_dir = self.asset_dir(asset_id)
        midi_path = asset_midi_path(asset_dir)
        if not midi_path.exists():
            self.render_asset_midi(asset_id)
        wav_path = asset_audio_path(asset_dir)
        asset = self.read_asset(asset_id)
        try:
            render_audio(midi_path, wav_path, config)
        except RendererError as exc:
            updated = _with_preview(asset, audio_status="failed", audio_error=str(exc), audio_size_bytes=0, audio_url=None)
            self._write_asset(updated)
            write_json(asset_dir / "audio-render-report.json", {"status": "failed", "error": str(exc), "rendered_at": now_iso()})
            return updated
        updated = _with_preview(
            asset,
            audio_status="completed",
            audio_error=None,
            audio_size_bytes=wav_path.stat().st_size,
            audio_url=asset_audio_url(asset_id),
        )
        self._write_asset(updated)
        write_json(asset_dir / "audio-render-report.json", {"status": "completed", "audio_size_bytes": wav_path.stat().st_size, "rendered_at": now_iso()})
        return updated

    def mark_used(self, asset_refs: list[DomainDocument], context: DomainDocument | None = None) -> list[DomainDocument]:
        refs = resolve_asset_refs(self, asset_refs)
        now = now_iso()
        for ref in refs:
            asset = self.read_asset(ref["asset_id"])
            updated = CreativeAsset.from_dict({**asset.to_dict(), "usage_count": asset.usage_count + 1, "updated_at": now})
            self._write_asset(updated)
            _append_asset_event(self.asset_dir(asset.asset_id), "asset_used", {**(context or {}), "role": ref.get("role"), "strength": ref.get("strength")}, now)
        return refs

    def asset_dir(self, asset_id: str) -> Path:
        asset_id = validate_asset_id(asset_id)
        base = self.root.resolve()
        raw_target = base / asset_id
        if raw_target.is_symlink():
            raise ValueError("Refusing to operate on symlink asset.")
        target = raw_target.resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside assets.") from exc
        return target

    def _write_asset(self, asset: CreativeAsset) -> CreativeAsset:
        write_json(self.asset_dir(asset.asset_id) / "asset.json", asset.to_dict())
        return asset

    def _next_asset_id(self) -> str:
        for index in range(1, 1_000_000):
            asset_id = f"asset-{index:03d}"
            if not (self.root / asset_id).exists():
                return asset_id
        raise RuntimeError("Could not allocate asset id.")


def extract_assets_from_song_plan(plan: SongPlan, source: DomainDocument, request: DomainDocument) -> list[DomainDocument]:
    asset_types = [str(item) for item in request.get("asset_types", ["motif", "chord_progression"]) if str(item).strip()]
    if not asset_types:
        raise ValueError("asset_types must not be empty.")
    section_name = str(request.get("section_name") or "").strip()
    track_name = str(request.get("track_name") or "").strip()
    tags = _clean_tags(request.get("tags", []))
    name_prefix = _bounded_text(request.get("name_prefix"), "name_prefix", 80)
    favorite = bool(request.get("favorite", False))
    source_hash = song_plan_hash(plan)
    common_source = {**sanitize_asset_metadata(source), "song_plan_sha256": source_hash}
    payloads = []
    for asset_type in asset_types:
        if asset_type not in ASSET_TYPES:
            raise ValueError(f"Unsupported asset_type: {asset_type}.")
        payload = _extract_asset_payload(plan, asset_type, section_name=section_name, track_name=track_name, source=common_source, tags=tags, name_prefix=name_prefix)
        payload["favorite"] = favorite
        payloads.append(payload)
    return payloads


def resolve_asset_refs(store: AssetStore, raw_refs: Any) -> list[DomainDocument]:
    if raw_refs is None:
        return []
    if not isinstance(raw_refs, list):
        raise ValueError("asset_refs must be a list.")
    if len(raw_refs) > MAX_ASSET_REFS:
        raise ValueError(f"asset_refs supports at most {MAX_ASSET_REFS} assets.")
    refs = []
    seen = set()
    for item in raw_refs:
        if not isinstance(item, dict):
            raise ValueError("asset_refs items must be objects.")
        asset_id = validate_asset_id(str(item.get("asset_id") or ""))
        if asset_id in seen:
            continue
        seen.add(asset_id)
        asset = store.read_asset(asset_id)
        if asset.hidden:
            raise ValueError("Hidden assets cannot be used.")
        strength = _strength(item.get("strength"))
        refs.append(
            {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "name": asset.name,
                "role": _bounded_text(item.get("role"), "role", 80) or _default_asset_role(asset.asset_type),
                "strength": strength,
                "source": _asset_source_summary(asset.source),
                "content_summary": asset_content_summary(asset),
            }
        )
    return refs


def asset_refs_snapshot(store: AssetStore, raw_refs: Any, *, captured_at: str | None = None) -> DomainDocument:
    refs = resolve_asset_refs(store, raw_refs)
    return {"schema_version": 1, "asset_refs": refs, "captured_at": captured_at or now_iso()}


def asset_prompt_summaries(store: AssetStore, raw_refs: Any) -> list[DomainDocument]:
    summaries = []
    for ref in resolve_asset_refs(store, raw_refs):
        asset = store.read_asset(ref["asset_id"])
        content = sanitize_asset_metadata(dict(asset.content))
        if "notes" in content:
            content["notes"] = content["notes"][:16]
            content["note_count"] = len(asset.content.get("notes") or [])
        summaries.append(
            {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "name": asset.name,
                "tags": list(asset.tags),
                "role": ref["role"],
                "strength": ref["strength"],
                "content": content,
            }
        )
    return summaries


def apply_asset_refs_to_plan(plan: SongPlan, store: AssetStore, raw_refs: Any) -> SongPlan:
    refs = resolve_asset_refs(store, raw_refs)
    if not refs:
        return plan
    sections = list(plan.sections)
    tracks = list(plan.tracks)
    for ref in refs:
        asset = store.read_asset(ref["asset_id"])
        if asset.asset_type == "chord_progression":
            sections = _apply_chord_asset(sections, asset)
        elif asset.asset_type == "motif":
            tracks = _apply_motif_asset(tracks, sections, asset)
    return SongPlan(title=plan.title, key=plan.key, tempo_bpm=plan.tempo_bpm, meter=plan.meter, sections=sections, tracks=tracks, quality=plan.quality)


def write_asset_refs_snapshot(run_dir: Path, snapshot: DomainDocument) -> Path:
    return write_json(run_dir / "data" / "asset-refs.json", snapshot)


def asset_content_summary(asset: CreativeAsset) -> DomainDocument:
    content = asset.content
    notes = _as_list(content.get("notes"))
    chords = _as_list(content.get("chords"))
    return {
        "duration_beats": asset.duration_beats,
        "note_count": len(notes),
        "chord_count": len(chords),
        "section_name": content.get("section_name"),
        "track_name": content.get("track_name"),
    }


def asset_public_dict(asset: CreativeAsset) -> DomainDocument:
    data = asset.to_dict()
    data["source"] = sanitize_asset_metadata(dict(data.get("source") or {}))
    data["content"] = sanitize_asset_metadata(dict(data.get("content") or {}))
    return data


def asset_midi_path(asset_dir: Path) -> Path:
    return _safe_asset_file(asset_dir, "preview.mid")


def asset_audio_path(asset_dir: Path) -> Path:
    return _safe_asset_file(asset_dir, "preview.wav")


def asset_midi_url(asset_id: str) -> str:
    return f"/api/assets/{asset_id}/midi"


def asset_audio_url(asset_id: str) -> str:
    return f"/api/assets/{asset_id}/audio"


def validate_asset_id(asset_id: str) -> str:
    if not ASSET_ID_PATTERN.match(asset_id):
        raise ValueError("Invalid asset id.")
    return asset_id


def song_plan_hash(plan: SongPlan) -> str:
    payload = json.dumps(plan.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_asset_metadata(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=BLOCKED_CONTENT_KEYS)


def asset_preview_song_plan(asset: CreativeAsset) -> SongPlan:
    notes = _asset_notes(asset)
    track_name = {
        "motif": "melody",
        "chord_progression": "chords",
        "drum_pattern": "drums",
        "bass_pattern": "bass",
        "section_template": "chords",
    }.get(asset.asset_type, "melody")
    max_note_end = max((note.start_beat + note.duration_beats for note in notes), default=asset.duration_beats)
    bars = max(1, int(round(max(asset.duration_beats, max_note_end) / 4 + 0.499)))
    section = SongSection(name="asset", start_bar=1, bars=bars, chords=_asset_chords(asset))
    filler = [NoteEvent(60, 0.0, 1.0, 1)]
    track_notes = {
        "melody": filler,
        "chords": [NoteEvent(60, 0.0, 3.75, 1), NoteEvent(64, 0.0, 3.75, 1), NoteEvent(67, 0.0, 3.75, 1)],
        "bass": [NoteEvent(36, 0.0, 1.0, 1)],
        "drums": [NoteEvent(42, 0.0, 0.25, 1)],
    }
    track_notes[track_name] = notes
    tracks = [
        TrackPlan(name="melody", instrument="lead", notes=track_notes["melody"]),
        TrackPlan(name="chords", instrument="electric piano", notes=track_notes["chords"]),
        TrackPlan(name="bass", instrument="electric bass", notes=track_notes["bass"]),
        TrackPlan(name="drums", instrument="gm drums", notes=track_notes["drums"]),
    ]
    return SongPlan(
        title=asset.name,
        key=asset.key,
        tempo_bpm=asset.tempo_bpm,
        meter=asset.meter,
        sections=[section],
        tracks=tracks,
    )


from song_agent.domains.studio import v142_a_readiness as _v142_a_readiness
from song_agent.domains.studio.v142_a_readiness import _extract_asset_payload as _extract_asset_payload, _motif_content as _motif_content, _select_section as _select_section, _select_track as _select_track, _notes_in_section as _notes_in_section, _relative_note as _relative_note, _asset_notes as _asset_notes, _asset_chords as _asset_chords, _apply_chord_asset as _apply_chord_asset, _apply_motif_asset as _apply_motif_asset, _chord_pitches as _chord_pitches, _with_preview as _with_preview, _preview_dict as _preview_dict, _safe_asset_file as _safe_asset_file, _validate_content as _validate_content, _scan_blocked_content as _scan_blocked_content, _validate_asset_size as _validate_asset_size, _bounded_text as _bounded_text, _clean_tags as _clean_tags, _optional_score as _optional_score, _asset_matches as _asset_matches, _strength as _strength, _default_asset_role as _default_asset_role, _asset_source_summary as _asset_source_summary, _append_asset_event as _append_asset_event, _root_motion as _root_motion

_v142_a_readiness.bind_globals(globals())
