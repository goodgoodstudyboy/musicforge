# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field, replace as replace
from pathlib import Path as Path
from song_agent.domains.quality.candidate_scoring import score_provider_edit_candidate as score_provider_edit_candidate
from song_agent.domains.creation.edits import EditIntent as EditIntent, EditedSongPlanResult as EditedSongPlanResult, apply_edit_intent as apply_edit_intent, validate_edit_intent as validate_edit_intent
from song_agent.domains.studio.editor_audition import EditorAuditionManifest as EditorAuditionManifest
from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig
from song_agent.domains.creation.provider_edits import ProviderEditPatch as ProviderEditPatch, apply_provider_edit_patch as apply_provider_edit_patch, generate_provider_edit_candidates as generate_provider_edit_candidates, provider_patch_to_intents as provider_patch_to_intents
from song_agent.domains.studio.prompt_templates import PromptTemplate as PromptTemplate
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.quality.review_edits import build_review_edit as build_review_edit
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan
from song_agent.domains.studio.song_editor import song_plan_hash as song_plan_hash

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

_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
keyword = _make_deferred_global('keyword')
marker = _make_deferred_global('marker')
tag = _make_deferred_global('tag')

def bind_globals(namespace: dict[str, object]) -> None:
    global _LOCKS_GUARD, keyword, marker, tag
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    keyword = namespace.get('keyword', keyword)
    marker = namespace.get('marker', marker)
    tag = namespace.get('tag', tag)
    _bind_deferred_defaults(namespace)


REVIEW_TASK_SCHEMA_VERSION = 1
REVIEW_CANDIDATE_SCHEMA_VERSION = 1
REVIEW_DECISION_REPORT_SCHEMA_VERSION = 1
TASK_STATUSES = {"open", "candidate_ready", "applied", "resolved", "needs_more_work", "archived", "stale"}
CANDIDATE_STATUSES = {"queued", "ready", "failed", "applied", "stale", "deleted"}
STRATEGIES = ("conservative", "balanced", "bold")
PROVIDER_STRATEGY = "provider"
TERMINAL_TASK_STATUSES = {"resolved", "archived", "stale", "needs_more_work"}
FIX_MARKERS = {"fix", "issue", "drop"}
PRESERVE_MARKERS = {"keep", "hook"}
_STORE_LOCKS: dict[str, threading.RLock] = {}




def _section_from_range_or_marker(plan: SongPlan, range_data: DomainDocument, global_beat: float | None) -> SongSection:
    if global_beat is not None:
        section = _section_for_beat(plan, global_beat)
        if section is not None:
            return section
    if range_data.get("mode") == "section":
        section = _find_section(plan, str(range_data.get("section_name") or ""))
        if section is not None:
            return section
    start = _float_or_none(range_data.get("start_beat"))
    if start is not None:
        section = _section_for_beat(plan, start)
        if section is not None:
            return section
    for section in plan.sections:
        if "chorus" in section.name.lower():
            return section
    return plan.sections[0]

def _target_track(parent_plan: SongPlan, audition: EditorAuditionManifest, text: str) -> TrackPlan | None:
    if audition.track_mode == "solo" and len(audition.track_ids) == 1:
        index = _track_state(parent_plan).get(audition.track_ids[0])
        if index is not None:
            return parent_plan.tracks[index]
    role = _role_from_text(text)
    return _track_by_role(parent_plan, role) if role else None

def _review_text(review: DomainDocument, audition: EditorAuditionManifest) -> str:
    parts = [
        str(review.get("notes") or ""),
        " ".join(str(tag) for tag in review.get("tags", [])),
        str(review.get("status") or ""),
        " ".join(str(marker.get("kind") or "") + " " + str(marker.get("label") or "") for marker in review.get("markers", []) if isinstance(marker, dict)),
        str(audition.range.get("section_name") if isinstance(audition.range, dict) else ""),
    ]
    return sanitize_sensitive_text(" ".join(parts))[:2000].lower()

def _role_from_text(text: str) -> str | None:
    roles = {
        "bass": ("bass", "低音", "贝斯"),
        "drums": ("drum", "drums", "kick", "snare", "鼓", "军鼓", "底鼓"),
        "melody": ("melody", "lead", "hook", "旋律", "主旋律"),
        "chords": ("chord", "harmony", "pad", "和弦", "和声"),
    }
    for role, keywords in roles.items():
        if any(keyword in text for keyword in keywords):
            return role
    return None

def _track_by_role(plan: SongPlan, role: str | None) -> TrackPlan | None:
    if not role:
        return None
    for track in plan.tracks:
        text = f"{track.name} {track.instrument}".lower()
        if role in text or (role == "drums" and "drum" in text) or (role == "chords" and ("chord" in text or "pad" in text)):
            return track
    return None

def _role_for_track(track: TrackPlan | None, text: str) -> str:
    if track is None:
        return _role_from_text(text) or ""
    lowered = f"{track.name} {track.instrument}".lower()
    for role in ("bass", "drums", "melody", "chords"):
        if role in lowered:
            return role
    return _role_from_text(text) or ""

def _track_id(plan: SongPlan, track: TrackPlan | None) -> str:
    if track is None:
        return ""
    for index, item in enumerate(plan.tracks):
        if item.name == track.name:
            return f"track-{index + 1:03d}"
    return ""

def _track_state(plan: SongPlan) -> dict[str, int]:
    return {f"track-{index + 1:03d}": index for index, _track in enumerate(plan.tracks)}

def _find_section(plan: SongPlan, name: str) -> SongSection | None:
    for section in plan.sections:
        if section.name.lower() == str(name or "").lower():
            return section
    return None

def _section_for_beat(plan: SongPlan, beat: float) -> SongSection | None:
    for section in plan.sections:
        if _section_start(section) <= beat < _section_end(section):
            return section
    return None

def _section_start(section: SongSection) -> float:
    return float((section.start_bar - 1) * 4)

def _section_end(section: SongSection) -> float:
    return _section_start(section) + float(section.bars * 4)

def _range_start(range_data: DomainDocument) -> float:
    return _float_or_none(range_data.get("start_beat")) or 0.0

def _intent(
    edit_type: str,
    *,
    section_name: str | None = None,
    track_name: str | None = None,
    strength: int,
    instruction: str,
    preserve: list[str],
    payload: DomainDocument,
) -> EditIntent:
    target: DomainDocument = {}
    if section_name:
        target["section_name"] = section_name
    if track_name:
        target["track_name"] = track_name
    target["field"] = "notes"
    return EditIntent.from_dict({"edit_type": edit_type, "target": target, "instruction": instruction, "preserve": preserve, "strength": strength, "provider_mode": "local", "payload": payload})

def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)

def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    try:
        return _clamp(int(value), low, high)
    except (TypeError, ValueError):
        return default

def _clamp(value: int | float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))

def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _optional_str(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)

def _lock_for_project(project_dir: Path) -> threading.RLock:
    key = str(project_dir.resolve())
    with _LOCKS_GUARD:
        if key not in _STORE_LOCKS:
            _STORE_LOCKS[key] = threading.RLock()
        return _STORE_LOCKS[key]

def _append_event(root: Path, event_type: str, payload: DomainDocument, now: str) -> None:
    event_path = root / "events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"timestamp": now, "event": event_type, **sanitize_metadata(payload)}, ensure_ascii=False) + "\n")
