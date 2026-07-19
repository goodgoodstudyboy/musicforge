# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import hashlib as hashlib
import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.creation.edits import EditIntent as EditIntent, EditedSongPlanResult as EditedSongPlanResult, SUPPORTED_HARMONY_CHORDS as SUPPORTED_HARMONY_CHORDS, apply_edit_intent as apply_edit_intent, validate_edit_intent as validate_edit_intent
from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.prompt_templates import PromptTemplate as PromptTemplate, render_prompt_template as render_prompt_template
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig, ProviderConfigError as ProviderConfigError, ProviderEditResponse as ProviderEditResponse, ProviderOutputError as ProviderOutputError
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.quality.quality import validate_song_plan as validate_song_plan
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan

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

ProviderEditError = _make_deferred_global('ProviderEditError')
ProviderEditOperation = _make_deferred_global('ProviderEditOperation')

def bind_globals(namespace: dict[str, object]) -> None:
    global ProviderEditError, ProviderEditOperation
    ProviderEditError = namespace.get('ProviderEditError', ProviderEditError)
    ProviderEditOperation = namespace.get('ProviderEditOperation', ProviderEditOperation)
    _bind_deferred_defaults(namespace)


SCHEMA_VERSION = 1
MAX_PATCH_JSON_BYTES = 32_768
MAX_CANDIDATE_SET_JSON_BYTES = 128_000
MAX_OPERATION_COUNT = 8
MIN_CANDIDATE_COUNT = 2
MAX_CANDIDATE_COUNT = 5
MAX_PATCH_TEXT = 800
MAX_LYRIC_TEXT = 2_000
ALLOWED_OPS = {
    "set_section_energy",
    "set_section_chords",
    "set_track_density",
    "rewrite_section_lyrics",
    "melody_variation",
    "arrangement_variation",
}
BLOCKED_KEYS = {"path", "file", "absolute_path", "local_path", "token", "api_key", "secret", "password", "credential"}




def _operation_to_intent(operation: ProviderEditOperation) -> EditIntent:
    preserve = list(operation.preserve)
    strength = operation.strength or 6
    if operation.op == "set_section_energy":
        if operation.energy is not None:
            strength = 8 if operation.energy >= 0.55 else 3
        return EditIntent.from_dict(
            {
                "edit_type": "section_energy",
                "target": {"section_name": operation.section_name},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "set_section_chords":
        return EditIntent.from_dict(
            {
                "edit_type": "section_harmony",
                "target": {"section_name": operation.section_name, "field": "chords"},
                "payload": {"chords": operation.chords},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "set_track_density":
        return EditIntent.from_dict(
            {
                "edit_type": "track_density",
                "target": {"section_name": operation.section_name, "track_name": operation.track_name},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "rewrite_section_lyrics":
        return EditIntent.from_dict(
            {
                "edit_type": "lyrics_rewrite",
                "target": {"section_name": operation.section_name, "field": "lyrics"},
                "payload": {"lyrics": operation.lyrics},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "melody_variation":
        return EditIntent.from_dict(
            {
                "edit_type": "melody_variation",
                "target": {"section_name": operation.section_name},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "arrangement_variation":
        target: DomainDocument = {}
        if operation.section_name:
            target["section_name"] = operation.section_name
        if operation.track_name:
            target["track_name"] = operation.track_name
        payload = {"instrument": operation.instrument} if operation.instrument else {}
        return EditIntent.from_dict(
            {
                "edit_type": "arrangement_variation",
                "target": target,
                "payload": payload,
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    raise ProviderEditError(f"Unsupported provider edit operation: {operation.op}.")

def _client_for_config(config: ProviderConfig) -> object:
    if config.wire_api == "mock":
        from song_agent.domains.creation.providers.mock import MockProviderClient

        return MockProviderClient()
    if config.wire_api == "openai_chat_completions":
        from song_agent.domains.creation.providers.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient()
    raise ProviderConfigError(f"Unsupported provider wire_api: {config.wire_api}.")

def _provider_edit_response_parts(response: object) -> tuple[DomainDocument, DomainDocument, str | None]:
    if isinstance(response, ProviderEditResponse):
        return response.data, dict(response.usage or {}), response.request_id
    if isinstance(response, dict) and "data" in response and isinstance(response.get("data"), dict):
        usage = _as_document(response.get("usage"))
        request_id = response.get("request_id")
        return response["data"], dict(usage), None if request_id is None else str(request_id)
    if isinstance(response, dict):
        return response, {}, None
    raise ProviderEditError("provider edit response must be a JSON object.")

def _scan_blocked_fields(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in BLOCKED_KEYS or lowered.endswith("_path"):
                raise ProviderEditError(f"provider edit patch contains unsupported path or secret field: {key}.")
            _scan_blocked_fields(item)
    elif isinstance(value, list):
        for item in value:
            _scan_blocked_fields(item)

def _optional_text(value: object, field_name: str, max_length: int) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _bounded_text(value, field_name, max_length)

def _bounded_text(value: object, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ProviderEditError(f"{field_name} must be {max_length} characters or fewer.")
    return text

def _optional_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ProviderEditError("energy must be between 0.0 and 1.0.")
    return number

def _optional_strength(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    strength = int(value)
    if strength < 1 or strength > 10:
        raise ProviderEditError("strength must be between 1 and 10.")
    return strength

def _chord_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProviderEditError("chords must be a list.")
    result = []
    invalid = []
    supported = {chord.lower(): chord for chord in SUPPORTED_HARMONY_CHORDS}
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        chord = supported.get(text.lower())
        if chord is None:
            invalid.append(text)
        else:
            result.append(chord)
    if invalid:
        raise ProviderEditError(f"Unsupported chord names: {', '.join(invalid)}.")
    return result[:8]

def _string_list(value: object, field_name: str, *, max_items: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProviderEditError(f"{field_name} must be a list.")
    return [str(item).strip() for item in value if str(item).strip()][:max_items]

def _confidence(value: object) -> float:
    if value is None or str(value).strip() == "":
        return 0.0
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ProviderEditError("confidence must be between 0.0 and 1.0.")
    return number

def _candidate_count(value: object) -> int:
    count = int(value or MIN_CANDIDATE_COUNT)
    if count < MIN_CANDIDATE_COUNT or count > MAX_CANDIDATE_COUNT:
        raise ProviderEditError(f"candidate_count must be between {MIN_CANDIDATE_COUNT} and {MAX_CANDIDATE_COUNT}.")
    return count

def _merge_usage(left: DomainDocument, right: DomainDocument) -> DomainDocument:
    result = dict(left)
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        result[key] = int(result.get(key) or 0) + int(right.get(key) or 0)
    return result

def _next_preview_id(preview_root: Path) -> str:
    for index in range(1, 10_000):
        preview_id = f"preview-{index:03d}"
        if not (preview_root / preview_id).exists():
            return preview_id
    raise RuntimeError("Could not allocate a provider edit preview id.")

def _safe_preview_dir(project_dir: Path, preview_id: str) -> Path:
    if not re.match(r"^preview-[0-9]{3,5}$", preview_id):
        raise ValueError("Invalid preview id.")
    base = (project_dir / "edit-previews").resolve()
    target = (base / preview_id).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside edit-previews.") from exc
    return target
