# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import re as re
import shutil as shutil
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.creation.edits import EditIntent as EditIntent, EditedSongPlanResult as EditedSongPlanResult, apply_edit_intent as apply_edit_intent, validate_edit_intent as validate_edit_intent
from song_agent.domains.studio.editor_audition import EditorAuditionManifest as EditorAuditionManifest
from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
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

ReviewEditError = _make_deferred_global('ReviewEditError')
keyword = _make_deferred_global('keyword')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReviewEditError, keyword
    ReviewEditError = namespace.get('ReviewEditError', ReviewEditError)
    keyword = namespace.get('keyword', keyword)
    _bind_deferred_defaults(namespace)


REVIEW_EDIT_SCHEMA_VERSION = 1
MAX_REVIEW_EDIT_INTENTS = 4
MAX_REVIEW_EDIT_TEXT = 2000
ENERGY_KEYWORDS = ("energy", "lift", "stronger", "bigger", "more intense", "更强", "能量", "加强", "高潮", "更炸")
REDUCE_KEYWORDS = ("too busy", "too dense", "crowded", "reduce", "less", "太满", "太密", "减少", "稀疏")
INCREASE_KEYWORDS = ("more", "add", "fill", "empty", "thin", "太空", "太少", "加一点", "更丰富")
MELODY_KEYWORDS = ("hook", "melody", "variation", "catchy", "旋律", "副歌", "变化")
ARRANGEMENT_KEYWORDS = ("arrangement", "transition", "drop", "build", "break", "编曲", "过渡", "铺垫")
TRACK_ROLE_KEYWORDS = {
    "bass": ("bass", "低音", "贝斯"),
    "drums": ("drum", "drums", "kick", "snare", "鼓", "军鼓", "底鼓"),
    "melody": ("melody", "lead", "hook", "旋律", "主旋律"),
    "chords": ("chord", "harmony", "pad", "和弦", "和声"),
}




def _find_section(plan: SongPlan, name: str) -> SongSection | None:
    for section in plan.sections:
        if section.name.lower() == str(name or "").lower():
            return section
    return None

def _section_for_beat(plan: SongPlan, beat: float) -> SongSection | None:
    for section in plan.sections:
        start = float((section.start_bar - 1) * 4)
        end = start + float(section.bars * 4)
        if start <= beat < end:
            return section
    return None

def _global_marker_beat(range_data: DomainDocument, marker_beat: float) -> float:
    start = _float_or_none(range_data.get("start_beat"))
    if start is None:
        return marker_beat
    return start + marker_beat

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
    if edit_type in {"section_energy", "melody_variation", "arrangement_variation"}:
        target["field"] = "notes"
    if edit_type == "track_density":
        target["field"] = "notes"
    return EditIntent.from_dict(
        {
            "edit_type": edit_type,
            "target": target,
            "instruction": instruction,
            "preserve": preserve,
            "strength": strength,
            "provider_mode": "local",
            "payload": payload,
        }
    )

def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)

def _mode(value: object) -> str:
    mode = str(value or "local").strip()
    if mode not in {"local", "provider"}:
        raise ReviewEditError("review edit mode must be local or provider.")
    return mode

def _confidence(value: object) -> float:
    try:
        confidence = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise ReviewEditError("confidence must be a number.") from exc
    return round(max(0.0, min(1.0, confidence)), 3)

def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
