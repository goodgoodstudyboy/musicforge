from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, document_or as _document_or

import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.editor_clips import ClipNote as ClipNote, EditorClipError as EditorClipError, EditorClipUnavailableError as EditorClipUnavailableError
from song_agent.domains.studio.editor_view import build_editor_view_from_result as build_editor_view_from_result
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.studio.song_editor import apply_editor_patch as apply_editor_patch, build_editor_state as build_editor_state, song_plan_hash as song_plan_hash


EDITOR_TEMPLATE_SCHEMA_VERSION = 1
EDITOR_TEMPLATE_ROOT = Path(".musicforge") / "editor-templates"
SECTION_TEMPLATE_PATTERN = re.compile(r"^section-template-[0-9]{3,6}$")
TRACK_TEMPLATE_PATTERN = re.compile(r"^track-template-[0-9]{3,6}$")
MAX_TEMPLATE_LANES = 8
MAX_TEMPLATE_LANE_NOTES = 128
MAX_TEMPLATE_TOTAL_NOTES = 180
MAX_TEMPLATE_DURATION_BEATS = 64.0
MAX_TEMPLATE_OPERATIONS = 200
MAX_TEMPLATE_JSON_BYTES = 512 * 1024
INSERT_MODES = {"overlay", "replace_range", "skip"}
ROLE_KEYWORDS = {
    "melody": ("melody", "lead", "vocal", "hook"),
    "chords": ("chord", "piano", "keys", "pad", "guitar", "synth"),
    "bass": ("bass", "sub"),
    "drums": ("drum", "beat", "perc", "kick", "snare", "hat"),
    "countermelody": ("counter", "countermelody"),
    "pad": ("pad", "strings", "atmos"),
    "fx": ("fx", "effect", "riser"),
}
SAFE_ROLES = set(ROLE_KEYWORDS) | {"unknown"}


class EditorTemplateError(ValueError):
    pass


class EditorTemplateUnavailableError(EditorTemplateError):
    pass


@dataclass(frozen=True)
class MultiTrackClipLane:
    lane_id: str
    role: str
    name: str
    instrument: str
    notes: list[ClipNote] = field(default_factory=list)
    chords: list[str] = field(default_factory=list)
    lyrics: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MultiTrackClipLane":
        if not isinstance(data, dict):
            raise EditorTemplateError("template lane must be an object.")
        lane_id = _safe_id(data.get("lane_id"), "lane_id")
        role = _role(data.get("role"))
        notes = [ClipNote.from_dict(dict(note)) for note in data.get("notes", []) if isinstance(note, dict)]
        if len(notes) > MAX_TEMPLATE_LANE_NOTES:
            raise EditorTemplateError(f"template lane supports at most {MAX_TEMPLATE_LANE_NOTES} notes.")
        return cls(
            lane_id=lane_id,
            role=role,
            name=_bounded(data.get("name"), 120) or lane_id,
            instrument=_bounded(data.get("instrument"), 120),
            notes=sorted(notes, key=lambda note: (note.start_beat, note.pitch, note.duration_beats, note.velocity)),
            chords=[_bounded(chord, 40) for chord in data.get("chords", []) if str(chord).strip()][:16] if isinstance(data.get("chords", []), list) else [],
            lyrics=_bounded(data.get("lyrics"), 2000),
            metadata=sanitize_metadata(dict(data.get("metadata") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["notes"] = [note.to_dict() for note in self.notes]
        return sanitize_metadata(data)


@dataclass(frozen=True)
class MultiTrackClip:
    schema_version: int
    clip_id: str
    source_type: str
    source_id: str
    title: str
    duration_beats: float
    key: str = ""
    tempo_bpm: int | None = None
    lanes: list[MultiTrackClipLane] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MultiTrackClip":
        if not isinstance(data, dict):
            raise EditorTemplateError("multitrack clip must be an object.")
        lanes = [MultiTrackClipLane.from_dict(dict(item)) for item in data.get("lanes", []) if isinstance(item, dict)]
        clip = cls(
            schema_version=int(data.get("schema_version", EDITOR_TEMPLATE_SCHEMA_VERSION) or EDITOR_TEMPLATE_SCHEMA_VERSION),
            clip_id=_safe_id(data.get("clip_id") or "clip-001", "clip_id"),
            source_type=_bounded(data.get("source_type"), 60) or "template",
            source_id=_bounded(data.get("source_id"), 160),
            title=_bounded(data.get("title"), 160) or "Untitled Template Clip",
            duration_beats=round(float(data.get("duration_beats") or 0), 6),
            key=_bounded(data.get("key"), 40),
            tempo_bpm=_optional_tempo(data.get("tempo_bpm")),
            lanes=lanes,
            metadata=sanitize_metadata(dict(data.get("metadata") or {})),
        )
        clip.validate()
        return clip

    def validate(self) -> None:
        if self.schema_version != EDITOR_TEMPLATE_SCHEMA_VERSION:
            raise EditorTemplateError(f"template schema_version must be {EDITOR_TEMPLATE_SCHEMA_VERSION}.")
        if not self.lanes:
            raise EditorTemplateUnavailableError("Template clip has no lanes.")
        if len(self.lanes) > MAX_TEMPLATE_LANES:
            raise EditorTemplateError(f"template clip supports at most {MAX_TEMPLATE_LANES} lanes.")
        if self.duration_beats <= 0 or self.duration_beats > MAX_TEMPLATE_DURATION_BEATS:
            raise EditorTemplateError(f"template duration must be > 0 and at most {MAX_TEMPLATE_DURATION_BEATS} beats.")
        total_notes = sum(len(lane.notes) for lane in self.lanes)
        if total_notes <= 0:
            raise EditorTemplateUnavailableError("Template clip has no notes.")
        if total_notes > MAX_TEMPLATE_TOTAL_NOTES:
            raise EditorTemplateError(f"template clip supports at most {MAX_TEMPLATE_TOTAL_NOTES} notes.")
        lane_ids = [lane.lane_id for lane in self.lanes]
        if len(set(lane_ids)) != len(lane_ids):
            raise EditorTemplateError("template lane_id values must be unique.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lanes"] = [lane.to_dict() for lane in self.lanes]
        return sanitize_metadata(data)

    def summary(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "clip_id": self.clip_id,
                "source_type": self.source_type,
                "source_id": self.source_id,
                "title": self.title,
                "duration_beats": self.duration_beats,
                "key": self.key,
                "tempo_bpm": self.tempo_bpm,
                "lane_count": len(self.lanes),
                "note_count": sum(len(lane.notes) for lane in self.lanes),
                "lanes": [
                    {
                        "lane_id": lane.lane_id,
                        "role": lane.role,
                        "name": lane.name,
                        "instrument": lane.instrument,
                        "note_count": len(lane.notes),
                        "chord_count": len(lane.chords),
                    }
                    for lane in self.lanes
                ],
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True)
class SectionTemplate:
    schema_version: int
    template_id: str
    name: str
    section_name: str
    bars: int
    chords: list[str]
    lyrics_mode: str = "source_excerpt"
    clip: MultiTrackClip | None = None
    source_summary: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    hidden: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionTemplate":
        if not isinstance(data, dict):
            raise EditorTemplateError("section template must be an object.")
        clip_data = data.get("clip")
        clip = MultiTrackClip.from_dict(clip_data) if isinstance(clip_data, dict) else None
        template = cls(
            schema_version=int(data.get("schema_version", EDITOR_TEMPLATE_SCHEMA_VERSION) or EDITOR_TEMPLATE_SCHEMA_VERSION),
            template_id=validate_section_template_id(str(data.get("template_id") or "section-template-001")),
            name=_bounded(data.get("name"), 160) or "Untitled Section Template",
            section_name=_bounded(data.get("section_name"), 80) or "section",
            bars=_int_range(data.get("bars", 4), "bars", 1, 64),
            chords=[_bounded(item, 40) for item in data.get("chords", []) if str(item).strip()][:16] if isinstance(data.get("chords", []), list) else [],
            lyrics_mode=_choice(data.get("lyrics_mode") or "source_excerpt", "lyrics_mode", {"empty", "placeholder", "source_excerpt"}),
            clip=clip,
            source_summary=sanitize_metadata(dict(data.get("source_summary") or {})),
            tags=_tags(data.get("tags")),
            hidden=bool(data.get("hidden", False)),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )
        _validate_template_size(template.to_dict())
        return template

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["clip"] = self.clip.to_dict() if self.clip else None
        return sanitize_metadata(data)


@dataclass(frozen=True)
class TrackTemplate:
    schema_version: int
    template_id: str
    name: str
    role: str
    instrument: str
    default_notes: list[ClipNote] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_summary: dict[str, Any] = field(default_factory=dict)
    hidden: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackTemplate":
        if not isinstance(data, dict):
            raise EditorTemplateError("track template must be an object.")
        notes = [ClipNote.from_dict(dict(note)) for note in data.get("default_notes", []) if isinstance(note, dict)]
        template = cls(
            schema_version=int(data.get("schema_version", EDITOR_TEMPLATE_SCHEMA_VERSION) or EDITOR_TEMPLATE_SCHEMA_VERSION),
            template_id=validate_track_template_id(str(data.get("template_id") or "track-template-001")),
            name=_bounded(data.get("name"), 160) or "Untitled Track Template",
            role=_role(data.get("role")),
            instrument=_bounded(data.get("instrument"), 120),
            default_notes=notes[:MAX_TEMPLATE_LANE_NOTES],
            tags=_tags(data.get("tags")),
            source_summary=sanitize_metadata(dict(data.get("source_summary") or {})),
            hidden=bool(data.get("hidden", False)),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )
        _validate_template_size(template.to_dict())
        return template

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["default_notes"] = [note.to_dict() for note in self.default_notes]
        return sanitize_metadata(data)


class EditorTemplateStore:
    def __init__(self, root: Path | str = EDITOR_TEMPLATE_ROOT):
        self.root = Path(root)
        self.section_root = self.root / "section-templates"
        self.track_root = self.root / "track-templates"
        self.lock = threading.RLock()

    def list_section_templates(self, include_hidden: bool = False) -> list[SectionTemplate]:
        templates: list[SectionTemplate] = []
        if not self.section_root.exists():
            return templates
        for path in self.section_root.glob("*/template.json"):
            try:
                template = SectionTemplate.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if template.hidden and not include_hidden:
                continue
            templates.append(template)
        return sorted(templates, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def list_track_templates(self, include_hidden: bool = False) -> list[TrackTemplate]:
        templates: list[TrackTemplate] = []
        if not self.track_root.exists():
            return templates
        for path in self.track_root.glob("*/template.json"):
            try:
                template = TrackTemplate.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if template.hidden and not include_hidden:
                continue
            templates.append(template)
        return sorted(templates, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def to_response(self, *, include_hidden: bool = False, project_store: ProjectStore | None = None) -> dict[str, Any]:
        sections = [section_template_public_dict(template, project_store=project_store) for template in self.list_section_templates(include_hidden=include_hidden)]
        tracks = [track_template_public_dict(template) for template in self.list_track_templates(include_hidden=include_hidden)]
        return {
            "ok": True,
            "schema_version": EDITOR_TEMPLATE_SCHEMA_VERSION,
            "section_templates": sections,
            "track_templates": tracks,
            "limits": {
                "max_lanes": MAX_TEMPLATE_LANES,
                "max_lane_notes": MAX_TEMPLATE_LANE_NOTES,
                "max_total_notes": MAX_TEMPLATE_TOTAL_NOTES,
                "max_duration_beats": MAX_TEMPLATE_DURATION_BEATS,
            },
        }

    def read_section_template(self, template_id: str) -> SectionTemplate:
        path = self.section_template_dir(template_id) / "template.json"
        if not path.exists():
            raise FileNotFoundError(template_id)
        return SectionTemplate.from_dict(read_json(path))

    def read_track_template(self, template_id: str) -> TrackTemplate:
        path = self.track_template_dir(template_id) / "template.json"
        if not path.exists():
            raise FileNotFoundError(template_id)
        return TrackTemplate.from_dict(read_json(path))

    def create_section_template_from_project_version(
        self,
        *,
        project_store: ProjectStore,
        project_id: str,
        version_id: str,
        section_id: str,
        payload: dict[str, Any],
        now: str | None = None,
    ) -> SectionTemplate:
        now = now or now_iso()
        clip = build_multitrack_clip_from_project_section(project_store=project_store, project_id=project_id, version_id=version_id, section_id=section_id, include_roles=payload.get("include_roles"))
        state_section = clip.metadata.get("section", {}) if isinstance(clip.metadata.get("section"), dict) else {}
        with self.lock:
            self.section_root.mkdir(parents=True, exist_ok=True)
            template_id, template_dir = self._reserve_section_template_dir()
            try:
                template = SectionTemplate.from_dict(
                    {
                        "schema_version": EDITOR_TEMPLATE_SCHEMA_VERSION,
                        "template_id": template_id,
                        "name": payload.get("name") or clip.title,
                        "section_name": state_section.get("name") or clip.title,
                        "bars": int(state_section.get("bars") or max(1, round(clip.duration_beats / 4))),
                        "chords": state_section.get("chords") or [],
                        "lyrics_mode": payload.get("lyrics_mode") or "source_excerpt",
                        "clip": {**clip.to_dict(), "source_type": "section_template", "source_id": template_id},
                        "source_summary": {
                            "source_type": "project_version_section",
                            "source_project_id": project_id,
                            "source_version_id": version_id,
                            "source_section_id": section_id,
                            "source_plan_hash": clip.metadata.get("source_plan_hash"),
                            "section": state_section,
                        },
                        "tags": payload.get("tags") or [],
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                write_json(template_dir / "template.json", template.to_dict())
                self.append_event("section", template.template_id, "section_template_created", {"source_project_id": project_id, "source_version_id": version_id}, now=now)
            except Exception:
                if template_dir.exists() and not (template_dir / "template.json").exists():
                    shutil.rmtree(template_dir)
                raise
            return template

    def create_track_template_from_project_version(
        self,
        *,
        project_store: ProjectStore,
        project_id: str,
        version_id: str,
        track_id: str,
        payload: dict[str, Any],
        now: str | None = None,
    ) -> TrackTemplate:
        now = now or now_iso()
        plan = _project_version_plan(project_store, project_id, version_id)
        state = build_editor_state(plan)
        track = _track_by_id(state, track_id)
        start, end = _range_from_payload(payload, default_start=0.0, default_end=float(state["song"]["total_bars"]) * float(state["song"]["beats_per_bar"]))
        notes = [
            ClipNote.from_dict({**note, "start_beat": round(float(note["start_beat"]) - start, 6), "role": track.get("role")})
            for note in track.get("notes", [])
            if start <= float(note["start_beat"]) < end
        ][:MAX_TEMPLATE_LANE_NOTES]
        with self.lock:
            self.track_root.mkdir(parents=True, exist_ok=True)
            template_id, template_dir = self._reserve_track_template_dir()
            try:
                template = TrackTemplate.from_dict(
                    {
                        "schema_version": EDITOR_TEMPLATE_SCHEMA_VERSION,
                        "template_id": template_id,
                        "name": payload.get("name") or track.get("name") or template_id,
                        "role": track.get("role") or "unknown",
                        "instrument": payload.get("instrument") or track.get("instrument") or "",
                        "default_notes": [note.to_dict() for note in notes],
                        "tags": payload.get("tags") or [],
                        "source_summary": {
                            "source_type": "project_version_track",
                            "source_project_id": project_id,
                            "source_version_id": version_id,
                            "source_track_id": track_id,
                            "source_plan_hash": state["base_plan_hash"],
                            "range": {"start_beat": start, "end_beat": end},
                        },
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                write_json(template_dir / "template.json", template.to_dict())
                self.append_event("track", template.template_id, "track_template_created", {"source_project_id": project_id, "source_version_id": version_id}, now=now)
            except Exception:
                if template_dir.exists() and not (template_dir / "template.json").exists():
                    shutil.rmtree(template_dir)
                raise
            return template

    def hide_template(self, template_type: str, template_id: str, hidden: bool = True) -> dict[str, Any]:
        with self.lock:
            if template_type == "section":
                section_template = self.read_section_template(template_id)
                section_updated = SectionTemplate.from_dict({**section_template.to_dict(), "hidden": hidden, "updated_at": now_iso()})
                write_json(self.section_template_dir(template_id) / "template.json", section_updated.to_dict())
                self.append_event("section", template_id, "section_template_hidden" if hidden else "section_template_unhidden", {}, now=section_updated.updated_at)
                return section_template_public_dict(section_updated)
            if template_type == "track":
                track_template = self.read_track_template(template_id)
                track_updated = TrackTemplate.from_dict({**track_template.to_dict(), "hidden": hidden, "updated_at": now_iso()})
                write_json(self.track_template_dir(template_id) / "template.json", track_updated.to_dict())
                self.append_event("track", template_id, "track_template_hidden" if hidden else "track_template_unhidden", {}, now=track_updated.updated_at)
                return track_template_public_dict(track_updated)
            raise ValueError("template_type must be section or track.")

    def delete_template(self, template_type: str, template_id: str) -> None:
        with self.lock:
            template_dir = self.section_template_dir(template_id) if template_type == "section" else self.track_template_dir(template_id)
            if not template_dir.exists():
                raise FileNotFoundError(template_id)
            resolved = template_dir.resolve()
            base = (self.section_root if template_type == "section" else self.track_root).resolve()
            try:
                resolved.relative_to(base)
            except ValueError as exc:
                raise ValueError("Refusing to delete outside editor templates.") from exc
            if resolved.is_symlink():
                raise ValueError("Refusing to delete symlink editor template.")
            shutil.rmtree(resolved)

    def section_template_dir(self, template_id: str) -> Path:
        template_id = validate_section_template_id(template_id)
        return _safe_child(self.section_root, template_id)

    def track_template_dir(self, template_id: str) -> Path:
        template_id = validate_track_template_id(template_id)
        return _safe_child(self.track_root, template_id)

    def append_event(self, template_type: str, template_id: str, event_type: str, payload: dict[str, Any], *, now: str | None = None) -> None:
        template_dir = self.section_template_dir(template_id) if template_type == "section" else self.track_template_dir(template_id)
        template_dir.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": now or now_iso(), "type": event_type, "payload": sanitize_metadata(payload)}
        with (template_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _reserve_section_template_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            template_id = f"section-template-{index:03d}"
            template_dir = self.section_template_dir(template_id)
            try:
                template_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return template_id, template_dir
        raise RuntimeError("Could not allocate section template id.")

    def _reserve_track_template_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            template_id = f"track-template-{index:03d}"
            template_dir = self.track_template_dir(template_id)
            try:
                template_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return template_id, template_dir
        raise RuntimeError("Could not allocate track template id.")


def section_template_public_dict(template: SectionTemplate, *, project_store: ProjectStore | None = None) -> dict[str, Any]:
    data = template.to_dict()
    clip = template.clip
    data["clip"] = clip.summary() if clip else None
    data["source_status"] = section_template_source_status(template, project_store) if project_store is not None else {"status": "unknown"}
    return sanitize_metadata(data)


def track_template_public_dict(template: TrackTemplate) -> dict[str, Any]:
    data = template.to_dict()
    data["default_note_count"] = len(template.default_notes)
    data.pop("default_notes", None)
    return sanitize_metadata(data)


def section_template_source_status(template: SectionTemplate, project_store: ProjectStore | None) -> dict[str, Any]:
    source = template.source_summary or {}
    project_id = str(source.get("source_project_id") or "")
    version_id = str(source.get("source_version_id") or "")
    expected = str(source.get("source_plan_hash") or "")
    if not project_store or not project_id or not version_id or not expected:
        return {"status": "snapshot"}
    try:
        plan = _project_version_plan(project_store, project_id, version_id)
    except FileNotFoundError:
        return {"status": "source_missing"}
    actual = song_plan_hash(plan)
    return {"status": "fresh" if actual == expected else "source_changed", "source_plan_hash": expected}


def build_multitrack_clip_from_project_section(
    *,
    project_store: ProjectStore,
    project_id: str,
    version_id: str,
    section_id: str,
    include_roles: Any = None,
) -> MultiTrackClip:
    plan = _project_version_plan(project_store, project_id, version_id)
    state = build_editor_state(plan)
    section = _section_by_id(state, section_id)
    include = {_role(role) for role in include_roles} if isinstance(include_roles, list) and include_roles else None
    start = float(section["start_beat"])
    end = float(section["end_beat"])
    lanes: list[MultiTrackClipLane] = []
    for track in state.get("tracks", []):
        role = _role(track.get("role"))
        if include is not None and role not in include:
            continue
        raw_notes = [
            {**note, "start_beat": round(float(note["start_beat"]) - start, 6), "role": role}
            for note in track.get("notes", [])
            if start <= float(note["start_beat"]) < end
        ]
        if not raw_notes:
            continue
        notes = [ClipNote.from_dict(note) for note in raw_notes][:MAX_TEMPLATE_LANE_NOTES]
        lanes.append(
            MultiTrackClipLane(
                lane_id=f"lane-{len(lanes) + 1:03d}",
                role=role,
                name=str(track.get("name") or role),
                instrument=str(track.get("instrument") or ""),
                notes=notes,
                chords=list(section.get("chords") or []) if role == "chords" else [],
                lyrics=str(section.get("lyrics") or "") if role == "melody" else "",
                metadata={"source_track_id": track.get("track_id")},
            )
        )
        if len(lanes) >= MAX_TEMPLATE_LANES:
            break
    if not lanes:
        raise EditorTemplateUnavailableError("Selected section has no reusable notes.")
    clip = MultiTrackClip(
        schema_version=EDITOR_TEMPLATE_SCHEMA_VERSION,
        clip_id=f"project-section-{section_id}",
        source_type="project_section",
        source_id=project_id,
        title=f"{version_id} {section['name']}",
        duration_beats=round(end - start, 6),
        key=plan.key,
        tempo_bpm=plan.tempo_bpm,
        lanes=lanes,
        metadata={
            "project_id": project_id,
            "source_version_id": version_id,
            "section_id": section_id,
            "source_plan_hash": state["base_plan_hash"],
            "section": {
                "name": section.get("name"),
                "bars": section.get("bars"),
                "start_beat": section.get("start_beat"),
                "end_beat": section.get("end_beat"),
                "chords": section.get("chords") or [],
            },
        },
    )
    return clip


def build_multitrack_clip_from_ref(source_ref: dict[str, Any], *, template_store: EditorTemplateStore, project_store: ProjectStore, default_project_id: str) -> MultiTrackClip:
    if not isinstance(source_ref, dict):
        raise EditorTemplateError("source_ref must be an object.")
    source_type = str(source_ref.get("source_type") or "").strip()
    if source_type == "section_template":
        template_id = validate_section_template_id(str(source_ref.get("template_id") or source_ref.get("source_id") or ""))
        template = template_store.read_section_template(template_id)
        if template.hidden:
            raise EditorTemplateUnavailableError("Hidden section templates cannot be inserted.")
        if template.clip is None:
            raise EditorTemplateUnavailableError("Section template has no clip.")
        return MultiTrackClip.from_dict({**template.clip.to_dict(), "source_type": "section_template", "source_id": template.template_id, "title": template.name})
    if source_type == "project_section":
        return build_multitrack_clip_from_project_section(
            project_store=project_store,
            project_id=str(source_ref.get("project_id") or default_project_id),
            version_id=str(source_ref.get("version_id") or source_ref.get("source_version_id") or ""),
            section_id=str(source_ref.get("section_id") or ""),
            include_roles=source_ref.get("include_roles"),
        )
    raise EditorTemplateError(f"Unsupported template source_type: {source_type}.")


def suggest_lane_mappings(clip: MultiTrackClip, editor_state: dict[str, Any]) -> list[dict[str, Any]]:
    suggestions = []
    used_tracks: set[str] = set()
    tracks = [dict(track) for track in editor_state.get("tracks", []) if not str(track.get("track_id") or "").startswith("derived-track-")]
    for lane in clip.lanes:
        best: tuple[float, str, str] | None = None
        for track in tracks:
            track_id = str(track.get("track_id") or "")
            if track_id in used_tracks:
                continue
            score, reason = _mapping_score(lane, track)
            if best is None or score > best[0]:
                best = (score, track_id, reason)
        if best and best[0] > 0:
            used_tracks.add(best[1])
            suggestions.append(
                {
                    "lane_id": lane.lane_id,
                    "lane_role": lane.role,
                    "lane_name": lane.name,
                    "note_count": len(lane.notes),
                    "suggested_track_id": best[1],
                    "confidence": round(best[0], 2),
                    "reason": best[2],
                }
            )
        else:
            suggestions.append(
                {
                    "lane_id": lane.lane_id,
                    "lane_role": lane.role,
                    "lane_name": lane.name,
                    "note_count": len(lane.notes),
                    "suggested_track_id": None,
                    "confidence": 0.0,
                    "reason": "unmapped",
                }
            )
    return sanitize_metadata(suggestions)


def build_multitrack_clip_insert_patch(
    parent_plan: SongPlan,
    clip: MultiTrackClip,
    payload: dict[str, Any],
    *,
    draft_plan: SongPlan | None = None,
    draft_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_TEMPLATE_JSON_BYTES:
        raise EditorTemplateError(f"template insert request must be {MAX_TEMPLATE_JSON_BYTES} bytes or fewer.")
    target = payload.get("target")
    options = payload.get("options") or {}
    mappings = payload.get("lane_mappings") or []
    if not isinstance(target, dict):
        raise EditorTemplateError("target must be an object.")
    if not isinstance(options, dict):
        raise EditorTemplateError("options must be an object.")
    if not isinstance(mappings, list):
        raise EditorTemplateError("lane_mappings must be a list.")
    base_state = build_editor_state(parent_plan)
    state = _document_or(draft_state, build_editor_state(draft_plan or parent_plan))
    section = _target_section(target, state)
    start_beat = _target_start_beat(target, section)
    transpose = _int_range(options.get("transpose", 0), "transpose", -24, 24)
    velocity_scale = _float_range(options.get("velocity_scale", 1.0), "velocity_scale", 0.25, 2.0)
    quantize_grid = _quantize_grid(options.get("quantize_grid"))
    trim_to_section = bool(options.get("trim_to_section", section is not None or options.get("fit") == "trim"))
    total_beats = float(state["song"]["total_bars"]) * float(state["song"]["beats_per_bar"])
    section_end = float(section["end_beat"]) if section and trim_to_section else None
    mapping_by_lane = _clean_lane_mappings(mappings, valid_lane_ids={lane.lane_id for lane in clip.lanes})
    operations: list[dict[str, Any]] = []
    warnings: list[str] = []
    lane_summaries: list[dict[str, Any]] = []
    replace_ranges: list[tuple[str, float, float]] = []
    for lane in clip.lanes:
        mapping = mapping_by_lane.get(lane.lane_id)
        if not mapping or mapping["mode"] == "skip":
            lane_summaries.append(_lane_summary(lane, target_track_id=None, mode="skip", inserted=0, replaced=0))
            continue
        track_id = mapping["target_track_id"]
        _track_by_id(state, track_id)
        if str(track_id).startswith("derived-track-"):
            raise EditorTemplateError("Cannot map template lanes to derived tracks.")
        mode = mapping["mode"]
        if mode == "replace_range":
            lane_range = (track_id, start_beat, start_beat + clip.duration_beats)
            if any(_ranges_overlap(lane_range, existing) for existing in replace_ranges):
                raise EditorTemplateError("Multiple replace_range lanes cannot target the same overlapping track range.")
            replace_ranges.append(lane_range)
            note_ids = _note_ids_in_replace_range(state, track_id, start_beat, start_beat + clip.duration_beats)
            if note_ids:
                operations.append({"op": "delete_notes", "track_id": track_id, "note_ids": note_ids})
            replaced = len(note_ids)
        else:
            replaced = 0
        inserted = 0
        for note in lane.notes:
            absolute_start = _round_beat(start_beat + note.start_beat)
            if quantize_grid:
                absolute_start = _round_beat(round(absolute_start / quantize_grid) * quantize_grid)
            duration = note.duration_beats
            if section_end is not None and absolute_start + duration > section_end:
                duration = _round_beat(section_end - absolute_start)
            if absolute_start < 0 or absolute_start >= total_beats or duration <= 0:
                warnings.append("Skipped template note outside target range.")
                continue
            if absolute_start + duration > total_beats:
                duration = _round_beat(total_beats - absolute_start)
            pitch = note.pitch + transpose
            if pitch < 0 or pitch > 127:
                warnings.append("Skipped template note outside MIDI pitch range after transpose.")
                continue
            velocity = max(1, min(127, int(round(note.velocity * velocity_scale))))
            operations.append(
                {
                    "op": "add_note",
                    "track_id": track_id,
                    "note": {
                        "pitch": pitch,
                        "start_beat": absolute_start,
                        "duration_beats": _round_beat(duration),
                        "velocity": velocity,
                    },
                }
            )
            inserted += 1
        lane_summaries.append(_lane_summary(lane, target_track_id=track_id, mode=mode, inserted=inserted, replaced=replaced))
    if not any(summary["inserted_note_count"] for summary in lane_summaries):
        raise EditorTemplateUnavailableError("Template insert produced no notes.")
    if len(operations) > MAX_TEMPLATE_OPERATIONS:
        raise EditorTemplateError(f"template insert can create at most {MAX_TEMPLATE_OPERATIONS} editor operations.")
    template_group_id = _template_group_id(clip, start_beat=start_beat, operations=operations, lane_summaries=lane_summaries)
    for operation in operations:
        operation["template_group_id"] = template_group_id
    metadata = _template_insert_metadata(
        clip,
        template_group_id=template_group_id,
        target={"section_id": section.get("section_id") if section else None, "start_beat": start_beat},
        options={"transpose": transpose, "velocity_scale": velocity_scale, "quantize_grid": quantize_grid, "trim_to_section": trim_to_section},
        lane_mappings=lane_summaries,
    )
    patch = {
        "schema_version": 1,
        "base_plan_hash": str(base_state["base_plan_hash"]),
        "label": f"Insert template: {clip.title}"[:160],
        "operations": operations,
        "metadata": {"template_inserts": [metadata]},
    }
    return sanitize_metadata(patch), clip.summary(), [sanitize_sensitive_text(item) for item in warnings]


def validate_section_template_id(template_id: str) -> str:
    if not SECTION_TEMPLATE_PATTERN.match(str(template_id or "")):
        raise ValueError("Invalid section_template_id.")
    return str(template_id)


def validate_track_template_id(template_id: str) -> str:
    if not TRACK_TEMPLATE_PATTERN.match(str(template_id or "")):
        raise ValueError("Invalid track_template_id.")
    return str(template_id)


def _project_version_plan(project_store: ProjectStore, project_id: str, version_id: str) -> SongPlan:
    document = project_store.get_project(project_id)
    version = next((item for item in document.versions if item.version_id == version_id), None)
    if version is None:
        raise FileNotFoundError(version_id)
    path = Path(version.output_dir) / "data" / "song-plan.json"
    if not path.exists():
        raise EditorTemplateUnavailableError("Project version song-plan.json is not available.")
    return SongPlan.from_dict(read_json(path))


def _track_by_id(state: ImplementationDocument, track_id: str) -> ImplementationDocument:
    track = next((item for item in state.get("tracks", []) if item.get("track_id") == track_id), None)
    if track is None:
        raise EditorTemplateError("Unknown track_id.")
    return dict(track)


def _section_by_id(state: ImplementationDocument, section_id: str) -> ImplementationDocument:
    section = next((item for item in state.get("sections", []) if item.get("section_id") == section_id), None)
    if section is None:
        raise EditorTemplateError("Unknown section_id.")
    return dict(section)


def _target_section(target: ImplementationDocument, state: ImplementationDocument) -> ImplementationDocument | None:
    section_id = str(target.get("section_id") or "").strip()
    if not section_id:
        return None
    return _section_by_id(state, section_id)


def _target_start_beat(target: ImplementationDocument, section: ImplementationDocument | None) -> float:
    if "start_beat" in target:
        return _float_min(target.get("start_beat"), "target.start_beat", 0.0)
    if section is not None:
        return round(float(section["start_beat"]), 6)
    raise EditorTemplateError("target.start_beat is required when section_id is not provided.")


def _clean_lane_mappings(value: list[Any], *, valid_lane_ids: set[str] | None = None) -> dict[str, dict[str, str]]:
    mappings: dict[str, dict[str, str]] = {}
    valid_lane_ids = valid_lane_ids or set()
    for item in value:
        if not isinstance(item, dict):
            raise EditorTemplateError("lane_mappings items must be objects.")
        lane_id = _safe_id(item.get("lane_id"), "lane_id")
        if valid_lane_ids and lane_id not in valid_lane_ids:
            raise EditorTemplateError(f"Unknown template lane_id: {lane_id}.")
        mode = _choice(item.get("mode") or "overlay", "mode", INSERT_MODES)
        track_id = str(item.get("target_track_id") or "").strip()
        if mode != "skip" and not re.match(r"^track-[0-9]{3}$", track_id):
            raise EditorTemplateError("target_track_id is required for mapped lanes.")
        if lane_id in mappings:
            raise EditorTemplateError("Each lane can only be mapped once.")
        mappings[lane_id] = {"lane_id": lane_id, "target_track_id": track_id, "mode": mode}
    return mappings


def _note_ids_in_replace_range(state: ImplementationDocument, track_id: str, start: float, end: float) -> list[str]:
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


def _lane_summary(lane: MultiTrackClipLane, *, target_track_id: str | None, mode: str, inserted: int, replaced: int) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "lane_id": lane.lane_id,
            "source_role": lane.role,
            "lane_name": lane.name,
            "target_track_id": target_track_id,
            "mode": mode,
            "inserted_note_count": inserted,
            "replaced_note_count": replaced,
        }
    )


def _template_insert_metadata(
    clip: MultiTrackClip,
    *,
    template_group_id: str,
    target: ImplementationDocument,
    options: ImplementationDocument,
    lane_mappings: list[ImplementationDocument],
) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "schema_version": EDITOR_TEMPLATE_SCHEMA_VERSION,
            "template_group_id": template_group_id,
            "source_type": clip.source_type,
            "source_id": clip.source_id,
            "title": clip.title,
            "duration_beats": clip.duration_beats,
            "lane_count": len(clip.lanes),
            "note_count": sum(len(lane.notes) for lane in clip.lanes),
            "target": target,
            "options": options,
            "lane_mappings": lane_mappings,
            "source": clip.metadata,
        }
    )


def _template_group_id(clip: MultiTrackClip, *, start_beat: float, operations: list[ImplementationDocument], lane_summaries: list[ImplementationDocument]) -> str:
    operation_fingerprint = [
        {key: value for key, value in operation.items() if key not in {"template_group_id", "clip_group_id"}}
        for operation in operations
    ]
    payload = json.dumps(
        {
            "source_type": clip.source_type,
            "source_id": clip.source_id,
            "title": clip.title,
            "start_beat": start_beat,
            "lanes": lane_summaries,
            "operations": operation_fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"template-{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"


def _mapping_score(lane: MultiTrackClipLane, track: ImplementationDocument) -> tuple[float, str]:
    lane_role = lane.role
    track_role = _role(track.get("role"))
    name = str(track.get("name") or "").lower()
    instrument = str(track.get("instrument") or "").lower()
    if lane_role != "unknown" and lane_role == track_role:
        return 0.95, f"role match: {lane_role}"
    for keyword in ROLE_KEYWORDS.get(lane_role, ()):
        if keyword in name:
            return 0.82, f"track name contains {keyword}"
        if keyword in instrument:
            return 0.74, f"instrument contains {keyword}"
    if lane.instrument and any(word for word in lane.instrument.lower().split() if word and word in instrument):
        return 0.5, "instrument similarity"
    return 0.0, "unmapped"


def _ranges_overlap(left: tuple[str, float, float], right: tuple[str, float, float]) -> bool:
    return left[0] == right[0] and left[2] > right[1] and left[1] < right[2]


def _range_from_payload(payload: ImplementationDocument, *, default_start: float, default_end: float) -> tuple[float, float]:
    raw_range = _as_document(payload.get("range"))
    start = _float_min(raw_range.get("start_beat", default_start), "range.start_beat", 0.0)
    end = _float_min(raw_range.get("end_beat", default_end), "range.end_beat", 0.0)
    if end <= start:
        raise EditorTemplateError("range.end_beat must be greater than range.start_beat.")
    if end - start > MAX_TEMPLATE_DURATION_BEATS:
        raise EditorTemplateError("track template range is too long.")
    return start, end


def _safe_child(root: Path, child: str) -> Path:
    base = root.resolve()
    target = (base / child).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside editor templates.") from exc
    return target


def _validate_template_size(data: ImplementationDocument) -> None:
    raw = json.dumps(data, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_TEMPLATE_JSON_BYTES:
        raise EditorTemplateError(f"editor template must be {MAX_TEMPLATE_JSON_BYTES} bytes or fewer.")


def _safe_id(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,120}$", text):
        raise EditorTemplateError(f"{name} is required.")
    return text


def _role(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in SAFE_ROLES:
        return raw
    haystack = raw
    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return role
    return "unknown"


def _tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags = []
    for item in value[:20]:
        tag = _bounded(item, 40)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]


def _choice(value: Any, name: str, choices: set[str]) -> str:
    text = str(value or "").strip()
    if text not in choices:
        raise EditorTemplateError(f"{name} must be one of: {', '.join(sorted(choices))}.")
    return text


def _int_range(value: Any, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EditorTemplateError(f"{name} must be an integer.") from exc
    if number < low or number > high:
        raise EditorTemplateError(f"{name} must be between {low} and {high}.")
    return number


def _float_min(value: Any, name: str, minimum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorTemplateError(f"{name} must be a number.") from exc
    if number < minimum:
        raise EditorTemplateError(f"{name} must be >= {minimum}.")
    return round(number, 6)


def _float_range(value: Any, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorTemplateError(f"{name} must be a number.") from exc
    if number < low or number > high:
        raise EditorTemplateError(f"{name} must be between {low} and {high}.")
    return number


def _optional_tempo(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _int_range(value, "tempo_bpm", 40, 240)


def _quantize_grid(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, str):
        lookup = {"1/32": 0.125, "1/16": 0.25, "1/8": 0.5, "1/4": 1.0}
        if value.strip() in lookup:
            return lookup[value.strip()]
    grid = _float_range(value, "quantize_grid", 0.125, 4.0)
    if grid not in {0.125, 0.25, 0.5, 1.0, 2.0, 4.0}:
        raise EditorTemplateError("quantize_grid must be one of 0.125, 0.25, 0.5, 1.0, 2.0, 4.0.")
    return grid


def _round_beat(value: float) -> float:
    return round(float(value), 6)
