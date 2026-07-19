# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.editor_clips import ClipNote as ClipNote, EditorClipError as EditorClipError, EditorClipUnavailableError as EditorClipUnavailableError
from song_agent.domains.studio.editor_view import build_editor_view_from_result as build_editor_view_from_result
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.studio.song_editor import apply_editor_patch as apply_editor_patch, build_editor_state as build_editor_state, song_plan_hash as song_plan_hash

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

EDITOR_TEMPLATE_ROOT = _make_deferred_global('EDITOR_TEMPLATE_ROOT')
EditorTemplateError = _make_deferred_global('EditorTemplateError')
EditorTemplateUnavailableError = _make_deferred_global('EditorTemplateUnavailableError')
MultiTrackClip = _make_deferred_global('MultiTrackClip')
MultiTrackClipLane = _make_deferred_global('MultiTrackClipLane')
SectionTemplate = _make_deferred_global('SectionTemplate')
TrackTemplate = _make_deferred_global('TrackTemplate')
_mapping_score = _make_deferred_global('_mapping_score')
_project_version_plan = _make_deferred_global('_project_version_plan')
_range_from_payload = _make_deferred_global('_range_from_payload')
_role = _make_deferred_global('_role')
_safe_child = _make_deferred_global('_safe_child')
_section_by_id = _make_deferred_global('_section_by_id')
_track_by_id = _make_deferred_global('_track_by_id')
item = _make_deferred_global('item')
note = _make_deferred_global('note')
validate_section_template_id = _make_deferred_global('validate_section_template_id')
validate_track_template_id = _make_deferred_global('validate_track_template_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global EDITOR_TEMPLATE_ROOT, EditorTemplateError, EditorTemplateUnavailableError, MultiTrackClip, MultiTrackClipLane, SectionTemplate, TrackTemplate
    global _mapping_score, _project_version_plan, _range_from_payload, _role, _safe_child, _section_by_id, _track_by_id, item
    global note, validate_section_template_id, validate_track_template_id
    EDITOR_TEMPLATE_ROOT = namespace.get('EDITOR_TEMPLATE_ROOT', EDITOR_TEMPLATE_ROOT)
    EditorTemplateError = namespace.get('EditorTemplateError', EditorTemplateError)
    EditorTemplateUnavailableError = namespace.get('EditorTemplateUnavailableError', EditorTemplateUnavailableError)
    MultiTrackClip = namespace.get('MultiTrackClip', MultiTrackClip)
    MultiTrackClipLane = namespace.get('MultiTrackClipLane', MultiTrackClipLane)
    SectionTemplate = namespace.get('SectionTemplate', SectionTemplate)
    TrackTemplate = namespace.get('TrackTemplate', TrackTemplate)
    _mapping_score = namespace.get('_mapping_score', _mapping_score)
    _project_version_plan = namespace.get('_project_version_plan', _project_version_plan)
    _range_from_payload = namespace.get('_range_from_payload', _range_from_payload)
    _role = namespace.get('_role', _role)
    _safe_child = namespace.get('_safe_child', _safe_child)
    _section_by_id = namespace.get('_section_by_id', _section_by_id)
    _track_by_id = namespace.get('_track_by_id', _track_by_id)
    item = namespace.get('item', item)
    note = namespace.get('note', note)
    validate_section_template_id = namespace.get('validate_section_template_id', validate_section_template_id)
    validate_track_template_id = namespace.get('validate_track_template_id', validate_track_template_id)
    _bind_deferred_defaults(namespace)


EDITOR_TEMPLATE_SCHEMA_VERSION = 1
MAX_TEMPLATE_LANES = 8
MAX_TEMPLATE_LANE_NOTES = 128
MAX_TEMPLATE_TOTAL_NOTES = 180
MAX_TEMPLATE_DURATION_BEATS = 64.0
MAX_TEMPLATE_OPERATIONS = 200
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

    def to_response(self, *, include_hidden: bool = False, project_store: ProjectStore | None = None) -> DomainDocument:
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
        payload: DomainDocument,
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
        payload: DomainDocument,
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

    def hide_template(self, template_type: str, template_id: str, hidden: bool = True) -> DomainDocument:
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

    def append_event(self, template_type: str, template_id: str, event_type: str, payload: DomainDocument, *, now: str | None = None) -> None:
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

def section_template_public_dict(template: SectionTemplate, *, project_store: ProjectStore | None = None) -> DomainDocument:
    data = template.to_dict()
    clip = template.clip
    data["clip"] = clip.summary() if clip else None
    data["source_status"] = section_template_source_status(template, project_store) if project_store is not None else {"status": "unknown"}
    return sanitize_metadata(data)

def track_template_public_dict(template: TrackTemplate) -> DomainDocument:
    data = template.to_dict()
    data["default_note_count"] = len(template.default_notes)
    data.pop("default_notes", None)
    return sanitize_metadata(data)

def section_template_source_status(template: SectionTemplate, project_store: ProjectStore | None) -> DomainDocument:
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
    include_roles: object = None,
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

def build_multitrack_clip_from_ref(source_ref: DomainDocument, *, template_store: EditorTemplateStore, project_store: ProjectStore, default_project_id: str) -> MultiTrackClip:
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

def suggest_lane_mappings(clip: MultiTrackClip, editor_state: DomainDocument) -> list[DomainDocument]:
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
