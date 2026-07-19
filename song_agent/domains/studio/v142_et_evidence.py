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

EditorTemplateError = _make_deferred_global('EditorTemplateError')
EditorTemplateUnavailableError = _make_deferred_global('EditorTemplateUnavailableError')
MAX_TEMPLATE_JSON_BYTES = _make_deferred_global('MAX_TEMPLATE_JSON_BYTES')
MultiTrackClip = _make_deferred_global('MultiTrackClip')
MultiTrackClipLane = _make_deferred_global('MultiTrackClipLane')
SAFE_ROLES = _make_deferred_global('SAFE_ROLES')
SECTION_TEMPLATE_PATTERN = _make_deferred_global('SECTION_TEMPLATE_PATTERN')
TRACK_TEMPLATE_PATTERN = _make_deferred_global('TRACK_TEMPLATE_PATTERN')
existing = _make_deferred_global('existing')
key = _make_deferred_global('key')
summary = _make_deferred_global('summary')
word = _make_deferred_global('word')

def bind_globals(namespace: dict[str, object]) -> None:
    global EditorTemplateError, EditorTemplateUnavailableError, MAX_TEMPLATE_JSON_BYTES, MultiTrackClip, MultiTrackClipLane, SAFE_ROLES, SECTION_TEMPLATE_PATTERN, TRACK_TEMPLATE_PATTERN
    global existing, key, summary, word
    EditorTemplateError = namespace.get('EditorTemplateError', EditorTemplateError)
    EditorTemplateUnavailableError = namespace.get('EditorTemplateUnavailableError', EditorTemplateUnavailableError)
    MAX_TEMPLATE_JSON_BYTES = namespace.get('MAX_TEMPLATE_JSON_BYTES', MAX_TEMPLATE_JSON_BYTES)
    MultiTrackClip = namespace.get('MultiTrackClip', MultiTrackClip)
    MultiTrackClipLane = namespace.get('MultiTrackClipLane', MultiTrackClipLane)
    SAFE_ROLES = namespace.get('SAFE_ROLES', SAFE_ROLES)
    SECTION_TEMPLATE_PATTERN = namespace.get('SECTION_TEMPLATE_PATTERN', SECTION_TEMPLATE_PATTERN)
    TRACK_TEMPLATE_PATTERN = namespace.get('TRACK_TEMPLATE_PATTERN', TRACK_TEMPLATE_PATTERN)
    existing = namespace.get('existing', existing)
    key = namespace.get('key', key)
    summary = namespace.get('summary', summary)
    word = namespace.get('word', word)
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




def build_multitrack_clip_insert_patch(
    parent_plan: SongPlan,
    clip: MultiTrackClip,
    payload: DomainDocument,
    *,
    draft_plan: SongPlan | None = None,
    draft_state: DomainDocument | None = None,
) -> tuple[DomainDocument, DomainDocument, list[str]]:
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
    operations: list[DomainDocument] = []
    warnings: list[str] = []
    lane_summaries: list[DomainDocument] = []
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

def _track_by_id(state: DomainDocument, track_id: str) -> DomainDocument:
    track = next((item for item in state.get("tracks", []) if item.get("track_id") == track_id), None)
    if track is None:
        raise EditorTemplateError("Unknown track_id.")
    return dict(track)

def _section_by_id(state: DomainDocument, section_id: str) -> DomainDocument:
    section = next((item for item in state.get("sections", []) if item.get("section_id") == section_id), None)
    if section is None:
        raise EditorTemplateError("Unknown section_id.")
    return dict(section)

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
    raise EditorTemplateError("target.start_beat is required when section_id is not provided.")

def _clean_lane_mappings(value: list[object], *, valid_lane_ids: set[str] | None = None) -> dict[str, dict[str, str]]:
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

def _lane_summary(lane: MultiTrackClipLane, *, target_track_id: str | None, mode: str, inserted: int, replaced: int) -> DomainDocument:
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
    target: DomainDocument,
    options: DomainDocument,
    lane_mappings: list[DomainDocument],
) -> DomainDocument:
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

def _template_group_id(clip: MultiTrackClip, *, start_beat: float, operations: list[DomainDocument], lane_summaries: list[DomainDocument]) -> str:
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

def _mapping_score(lane: MultiTrackClipLane, track: DomainDocument) -> tuple[float, str]:
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

def _range_from_payload(payload: DomainDocument, *, default_start: float, default_end: float) -> tuple[float, float]:
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

def _validate_template_size(data: DomainDocument) -> None:
    raw = json.dumps(data, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_TEMPLATE_JSON_BYTES:
        raise EditorTemplateError(f"editor template must be {MAX_TEMPLATE_JSON_BYTES} bytes or fewer.")

def _safe_id(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,120}$", text):
        raise EditorTemplateError(f"{name} is required.")
    return text

def _role(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in SAFE_ROLES:
        return raw
    haystack = raw
    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return role
    return "unknown"

def _tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tags = []
    for item in value[:20]:
        tag = _bounded(item, 40)
        if tag and tag not in tags:
            tags.append(tag)
    return tags

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]

def _choice(value: object, name: str, choices: set[str]) -> str:
    text = str(value or "").strip()
    if text not in choices:
        raise EditorTemplateError(f"{name} must be one of: {', '.join(sorted(choices))}.")
    return text

def _int_range(value: object, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EditorTemplateError(f"{name} must be an integer.") from exc
    if number < low or number > high:
        raise EditorTemplateError(f"{name} must be between {low} and {high}.")
    return number

def _float_min(value: object, name: str, minimum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorTemplateError(f"{name} must be a number.") from exc
    if number < minimum:
        raise EditorTemplateError(f"{name} must be >= {minimum}.")
    return round(number, 6)

def _float_range(value: object, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorTemplateError(f"{name} must be a number.") from exc
    if number < low or number > high:
        raise EditorTemplateError(f"{name} must be between {low} and {high}.")
    return number

def _optional_tempo(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _int_range(value, "tempo_bpm", 40, 240)

def _quantize_grid(value: object) -> float | None:
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
