# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import hashlib as hashlib
import json as json
import math as math
import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, TrackPlan as TrackPlan
from song_agent.domains.studio.song_editor import section_id_for_index as section_id_for_index, track_id_for_index as track_id_for_index

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

MixControlError = _make_deferred_global('MixControlError')
MixPatch = _make_deferred_global('MixPatch')
MixState = _make_deferred_global('MixState')
MixTrackState = _make_deferred_global('MixTrackState')
SectionAutomation = _make_deferred_global('SectionAutomation')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
mix_state_integrity_hash = _make_deferred_global('mix_state_integrity_hash')
mix_state_integrity_ok = _make_deferred_global('mix_state_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global MixControlError, MixPatch, MixState, MixTrackState, SectionAutomation, item, key
    global mix_state_integrity_hash, mix_state_integrity_ok
    MixControlError = namespace.get('MixControlError', MixControlError)
    MixPatch = namespace.get('MixPatch', MixPatch)
    MixState = namespace.get('MixState', MixState)
    MixTrackState = namespace.get('MixTrackState', MixTrackState)
    SectionAutomation = namespace.get('SectionAutomation', SectionAutomation)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    mix_state_integrity_hash = namespace.get('mix_state_integrity_hash', mix_state_integrity_hash)
    mix_state_integrity_ok = namespace.get('mix_state_integrity_ok', mix_state_integrity_ok)
    _bind_deferred_defaults(namespace)


MIX_STATE_SCHEMA_VERSION = 1
MIX_PATCH_SCHEMA_VERSION = 1
SUPPORTED_MIX_OPS = {
    "set_track_volume",
    "set_track_pan",
    "set_track_mute",
    "set_track_solo",
    "set_track_velocity_scale",
    "set_section_track_volume_delta",
    "set_section_track_velocity_scale",
    "reset_track_mix",
    "reset_section_track_mix",
}
MIX_STATE_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "current_source_hash", "stale_reasons"}
MIX_PATCH_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "current_source_hash", "stale_reasons"}




def with_mix_state_integrity(state: MixState) -> MixState:
    data = state.to_dict()
    data["integrity_hash"] = mix_state_integrity_hash(data)
    return MixState.from_dict(data)

def mix_patch_hash(patch: MixPatch | DomainDocument) -> str:
    data = patch.to_dict() if isinstance(patch, MixPatch) else dict(patch)
    return stable_hash({key: value for key, value in data.items() if key not in MIX_PATCH_INTEGRITY_EXCLUDE_KEYS})

def mix_patch_integrity_ok(patch: MixPatch | DomainDocument) -> bool:
    data = patch.to_dict() if isinstance(patch, MixPatch) else dict(patch)
    expected = str(data.get("integrity_hash") or "")
    return bool(expected) and expected == mix_patch_hash(data)

def with_mix_patch_integrity(patch: MixPatch) -> MixPatch:
    data = patch.to_dict()
    data["integrity_hash"] = mix_patch_hash(data)
    return MixPatch.from_dict(data)

def mix_state_stale_reasons(state: MixState | DomainDocument, *, plan: SongPlan, midi_path: Path) -> list[str]:
    data = state.to_dict() if isinstance(state, MixState) else dict(state)
    reasons = []
    if not mix_state_integrity_ok(data):
        reasons.append("mix_state_integrity")
    if data.get("base_song_plan_hash") != song_plan_hash(plan):
        reasons.append("base_song_plan_hash")
    if data.get("base_midi_hash") != file_sha256(midi_path):
        reasons.append("base_midi_hash")
    source = _as_document(data.get("source"))
    expected_source = _source_state(plan=plan, midi_path=midi_path, project_id=str(data.get("project_id") or ""), version_id=str(data.get("version_id") or ""))
    if any(source.get(key) != value for key, value in expected_source.items()):
        reasons.append("source_state")
    if data.get("source_hash") != stable_hash(source):
        reasons.append("source_hash")
    return reasons

def source_state_for_version(*, project_id: str, version_id: str, plan_path: Path, midi_path: Path) -> DomainDocument:
    return _source_state(plan=SongPlan.from_dict(read_json(plan_path)), midi_path=midi_path, project_id=project_id, version_id=version_id)

def song_plan_hash(plan: SongPlan) -> str:
    payload = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def stable_hash(value: object) -> str:
    clean = sanitize_metadata(value)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def track_role(name: str) -> str:
    lower = str(name or "").lower()
    for role in ("melody", "chords", "bass", "drums", "pad", "harmony"):
        if role in lower:
            return role
    return re.sub(r"[^a-z0-9]+", "-", lower).strip("-") or "track"

def pan_to_midi_cc(pan: int) -> int:
    return int(round((_pan(pan) + 100) * 127 / 200))

def _source_state(*, plan: SongPlan, midi_path: Path, project_id: str, version_id: str) -> DomainDocument:
    return {
        "project_id": project_id,
        "version_id": version_id,
        "song_plan_hash": song_plan_hash(plan),
        "midi_sha256": file_sha256(midi_path),
        "track_count": len(plan.tracks),
        "tracks": [{"track_id": track_id_for_index(index), "name": track.name, "role": track_role(track.name), "note_count": len(track.notes)} for index, track in enumerate(plan.tracks)],
        "sections": [{"section_id": section_id_for_index(index), "name": section.name, "start_bar": section.start_bar, "bars": section.bars} for index, section in enumerate(plan.sections)],
    }

def _clean_operation(operation: DomainDocument) -> DomainDocument:
    op = str(operation.get("op") or "").strip()
    if op not in SUPPORTED_MIX_OPS:
        raise MixControlError(f"Unsupported mix operation: {op}.")
    cleaned: DomainDocument = {"op": op, "track_id": _validate_track_id(str(operation.get("track_id") or ""))}
    if op == "set_track_volume":
        cleaned["volume_db"] = _volume_db(operation.get("volume_db"))
    elif op == "set_track_pan":
        cleaned["pan"] = _pan(operation.get("pan"))
    elif op == "set_track_mute":
        cleaned["mute"] = bool(operation.get("mute", True))
    elif op == "set_track_solo":
        cleaned["solo"] = bool(operation.get("solo", True))
    elif op == "set_track_velocity_scale":
        cleaned["velocity_scale"] = _velocity_scale(operation.get("velocity_scale"))
    elif op == "set_section_track_volume_delta":
        cleaned["section_id"] = _validate_section_id(str(operation.get("section_id") or ""))
        cleaned["volume_db_delta"] = _volume_db_delta(operation.get("volume_db_delta"))
    elif op == "set_section_track_velocity_scale":
        cleaned["section_id"] = _validate_section_id(str(operation.get("section_id") or ""))
        cleaned["velocity_scale"] = _velocity_scale(operation.get("velocity_scale"))
    elif op == "reset_section_track_mix":
        cleaned["section_id"] = _validate_section_id(str(operation.get("section_id") or ""))
    return cleaned

def _automation_for_note(note: NoteEvent, plan: SongPlan, automation: dict[str, SectionAutomation]) -> SectionAutomation | None:
    for index, section in enumerate(plan.sections):
        start = max(0, section.start_bar - 1) * 4.0
        end = start + max(0, section.bars) * 4.0
        if start <= note.start_beat < end:
            return automation.get(section_id_for_index(index))
    return None

def _scaled_velocity(note: NoteEvent, mix: MixTrackState, automation: SectionAutomation | None) -> int:
    volume_db = mix.volume_db + (automation.volume_db_delta if automation else 0.0)
    velocity_scale = mix.velocity_scale * (automation.velocity_scale if automation else 1.0)
    gain = math.pow(10.0, volume_db / 20.0)
    value = int(round(note.velocity * gain * velocity_scale))
    return max(1, min(127, value))

def _replace_track(track: MixTrackState, **changes: object) -> MixTrackState:
    data = track.to_dict()
    data.update(changes)
    if "section_automation" in data:
        data["section_automation"] = [item.to_dict() if isinstance(item, SectionAutomation) else item for item in data["section_automation"]]
    return MixTrackState.from_dict(data)

def _first_track(plan: SongPlan, *, preferred_roles: list[str] | None = None) -> str:
    preferred = [role.lower() for role in (preferred_roles or []) if role]
    for role in preferred:
        for index, track in enumerate(plan.tracks):
            if role in track_role(track.name):
                return track_id_for_index(index)
    return track_id_for_index(0) if plan.tracks else "track-001"

def _roles_from_payload(payload: DomainDocument) -> list[str]:
    value = payload.get("target_roles")
    if isinstance(value, list):
        return [str(item) for item in value]
    value = payload.get("target_role")
    return [str(value)] if value else []

def _volume_db(value: object) -> float:
    try:
        number = round(float(value), 3)
    except (TypeError, ValueError) as exc:
        raise MixControlError("volume_db must be numeric.") from exc
    if number < -36.0 or number > 12.0:
        raise MixControlError("volume_db must be between -36 and 12.")
    return number

def _volume_db_delta(value: object) -> float:
    try:
        number = round(float(value), 3)
    except (TypeError, ValueError) as exc:
        raise MixControlError("volume_db_delta must be numeric.") from exc
    if number < -24.0 or number > 12.0:
        raise MixControlError("volume_db_delta must be between -24 and 12.")
    return number

def _pan(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise MixControlError("pan must be an integer.") from exc
    if number < -100 or number > 100:
        raise MixControlError("pan must be between -100 and 100.")
    return number

def _velocity_scale(value: object) -> float:
    try:
        number = round(float(value), 4)
    except (TypeError, ValueError) as exc:
        raise MixControlError("velocity_scale must be numeric.") from exc
    if number < 0.0 or number > 2.0:
        raise MixControlError("velocity_scale must be between 0 and 2.")
    return number

def _validate_track_id(value: str) -> str:
    if not re.match(r"^track-[0-9]{3}$", value):
        raise MixControlError("track_id must look like track-001.")
    return value

def _validate_section_id(value: str) -> str:
    if not re.match(r"^section-[0-9]{3}$", value):
        raise MixControlError("section_id must look like section-001.")
    return value

def _validate_mix_state_id(value: str) -> str:
    if not re.match(r"^mixstate-[0-9]{6}$|^mixstate-[0-9]{3}$", value):
        raise MixControlError("Invalid mix_state_id.")
    return value

def _validate_mix_patch_id(value: str) -> str:
    if not re.match(r"^mixpatch-[0-9]{6}$|^mixpatch-[0-9]{3}$", value):
        raise MixControlError("Invalid mix_patch_id.")
    return value

def _validate_version_id(value: str) -> str:
    if not re.match(r"^v[0-9]{3,}$", value):
        raise MixControlError("Invalid version_id.")
    return value
