from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _document_or

import json as json
import re as re
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.edits import EDIT_TYPES as EDIT_TYPES, EditIntent as EditIntent, PRESERVE_FIELDS as PRESERVE_FIELDS, SUPPORTED_HARMONY_CHORDS as SUPPORTED_HARMONY_CHORDS, validate_edit_intent as validate_edit_intent
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan


SCHEMA_VERSION = 1
PRESET_PATH = Path(".musicforge") / "edit-presets.json"
PRESET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
BLOCKED_PAYLOAD_KEYS = {
    "path",
    "file",
    "absolute_path",
    "local_path",
    "token",
    "api_key",
    "secret",
    "password",
    "credential",
}
MAX_PRESET_JSON_BYTES = 16_384
MAX_PRESET_TEXT_FIELD = 240
MAX_PRESET_PAYLOAD_DEPTH = 6


@dataclass(frozen=True)
class EditPreset:
    preset_id: str
    name: str
    description: str
    edit_type: str
    strength: float = 0.5
    target_defaults: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    preserve: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    built_in: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, built_in: bool | None = None) -> "EditPreset":
        if not isinstance(data, dict):
            raise ValueError("preset must be an object.")
        preset = cls(
            preset_id=_clean_preset_id(data.get("preset_id")),
            name=_bounded_text(data.get("name"), "name", 80) or "Untitled Preset",
            description=_bounded_text(data.get("description"), "description", MAX_PRESET_TEXT_FIELD),
            edit_type=str(data.get("edit_type") or "").strip(),
            strength=float(data.get("strength", 0.5)),
            target_defaults=_mapping(data.get("target_defaults"), "target_defaults"),
            payload=_mapping(data.get("payload"), "payload"),
            preserve=_string_list(data.get("preserve"), "preserve", max_items=12),
            tags=_string_list(data.get("tags"), "tags", max_items=16),
            built_in=bool(data.get("built_in", False) if built_in is None else built_in),
            created_at=_optional_str(data.get("created_at")),
            updated_at=_optional_str(data.get("updated_at")),
        )
        preset.validate()
        return preset

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def public_ref(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "name": self.name,
            "built_in": self.built_in,
        }

    def validate(self) -> None:
        _clean_preset_id(self.preset_id)
        if self.edit_type not in EDIT_TYPES:
            raise ValueError(f"edit_type must be one of: {', '.join(sorted(EDIT_TYPES))}.")
        if self.strength < 0.0 or self.strength > 1.0:
            raise ValueError("strength must be between 0.0 and 1.0.")
        _validate_preset_json_size(self)
        unsupported = sorted(set(self.preserve) - PRESERVE_FIELDS)
        if unsupported:
            raise ValueError(f"preserve contains unsupported fields: {', '.join(unsupported)}.")
        _validate_payload_shape(self.payload, "payload")
        _validate_payload_shape(self.target_defaults, "target_defaults")
        if self.edit_type == "section_harmony":
            chords = self.payload.get("chords")
            if chords is not None:
                if not isinstance(chords, list):
                    raise ValueError("section_harmony payload.chords must be a list.")
                invalid = [
                    str(chord).strip()
                    for chord in chords
                    if str(chord).strip() and str(chord).strip() not in SUPPORTED_HARMONY_CHORDS
                ]
                if invalid:
                    raise ValueError(f"Unsupported chord names: {', '.join(invalid)}.")


class EditPresetStore:
    def __init__(self, path: Path | str = PRESET_PATH) -> None:
        self.path = Path(path)
        self.lock = threading.RLock()

    def list_presets(self) -> list[EditPreset]:
        with self.lock:
            return [*BUILT_IN_PRESETS, *self._read_user_presets()]

    def to_response(self) -> dict[str, Any]:
        presets = self.list_presets()
        return {
            "schema_version": SCHEMA_VERSION,
            "presets": [preset.to_dict() for preset in presets],
            "built_in_count": sum(1 for preset in presets if preset.built_in),
            "user_count": sum(1 for preset in presets if not preset.built_in),
        }

    def get_preset(self, preset_id: str) -> EditPreset:
        preset_id = _clean_preset_id(preset_id)
        for preset in self.list_presets():
            if preset.preset_id == preset_id:
                return preset
        raise FileNotFoundError(preset_id)

    def save_preset(self, data: dict[str, Any], *, preset_id: str | None = None) -> EditPreset:
        with self.lock:
            merged = dict(data)
            if preset_id is not None:
                merged["preset_id"] = _clean_preset_id(preset_id)
            now = now_iso()
            existing_user = {preset.preset_id: preset for preset in self._read_user_presets()}
            if any(preset.preset_id == merged.get("preset_id") for preset in BUILT_IN_PRESETS):
                raise ValueError("User presets cannot overwrite built-in presets.")
            previous = existing_user.get(str(merged.get("preset_id") or ""))
            merged["built_in"] = False
            merged["created_at"] = previous.created_at if previous else now
            merged["updated_at"] = now
            preset = EditPreset.from_dict(merged, built_in=False)
            existing_user[preset.preset_id] = preset
            self._write_user_presets(list(existing_user.values()))
            return preset

    def delete_preset(self, preset_id: str) -> None:
        with self.lock:
            preset_id = _clean_preset_id(preset_id)
            if any(preset.preset_id == preset_id for preset in BUILT_IN_PRESETS):
                raise PermissionError("Built-in presets cannot be deleted.")
            presets = [preset for preset in self._read_user_presets() if preset.preset_id != preset_id]
            self._write_user_presets(presets)

    def reset(self) -> None:
        with self.lock:
            if self.path.exists():
                self.path.unlink()

    def _read_user_presets(self) -> list[EditPreset]:
        if not self.path.exists():
            return []
        try:
            data = read_json(self.path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return []
        raw_presets = data.get("presets", []) if isinstance(data, dict) else []
        presets: list[EditPreset] = []
        for item in raw_presets:
            try:
                presets.append(EditPreset.from_dict(item, built_in=False))
            except ValueError:
                continue
        return presets

    def _write_user_presets(self, presets: list[EditPreset]) -> None:
        write_json(
            self.path,
            {
                "schema_version": SCHEMA_VERSION,
                "presets": [preset.to_dict() for preset in sorted(presets, key=lambda item: item.preset_id)],
            },
        )


def merge_preset_intent(preset: EditPreset, payload: dict[str, Any], plan: SongPlan) -> dict[str, Any]:
    explicit_intent = payload.get("intent")
    source = _document_or(explicit_intent, payload)
    merged: dict[str, Any] = {
        "edit_type": preset.edit_type,
        "target": resolve_target_defaults(preset, plan),
        "instruction": preset.description,
        "preserve": list(preset.preserve),
        "strength": _strength_to_int(preset.strength),
        "provider_mode": "local",
        "payload": dict(preset.payload),
    }
    for key in ("edit_type", "instruction", "preserve", "strength", "provider_mode"):
        if key in source:
            merged[key] = source[key]
    if isinstance(source.get("target"), dict):
        merged["target"] = {**merged["target"], **source["target"]}
    if isinstance(source.get("payload"), dict):
        merged["payload"] = {**merged["payload"], **source["payload"]}
    for key in ("name", "note", "change_summary", "start_immediately"):
        if key in payload:
            merged[key] = payload[key]
    intent = EditIntent.from_dict(merged)
    validate_edit_intent(plan, intent)
    return merged


def resolve_target_defaults(preset: EditPreset, plan: SongPlan) -> dict[str, str]:
    defaults = preset.target_defaults
    target: dict[str, str] = {}
    if defaults.get("field"):
        target["field"] = str(defaults["field"])
    section_name = _resolve_section_name(defaults, plan)
    if section_name:
        target["section_name"] = section_name
    track_name = _resolve_track_name(defaults, plan)
    if track_name:
        target["track_name"] = track_name
    return target


def _resolve_section_name(defaults: ImplementationDocument, plan: SongPlan) -> str | None:
    if defaults.get("section_name"):
        return str(defaults["section_name"])
    role = str(defaults.get("section_role") or "").lower().strip()
    if not role:
        return None
    matches = [section.name for section in plan.sections if role in section.name.lower()]
    if not matches:
        return None
    index = int(defaults.get("section_index", 0) or 0)
    try:
        return matches[index]
    except IndexError:
        return matches[-1] if index < 0 else matches[0]


def _resolve_track_name(defaults: ImplementationDocument, plan: SongPlan) -> str | None:
    if defaults.get("track_name"):
        return str(defaults["track_name"])
    role = str(defaults.get("track_role") or "").lower().strip()
    if not role:
        return None
    for track in plan.tracks:
        if role in track.name.lower():
            return track.name
    return None


def _strength_to_int(value: float) -> int:
    return max(1, min(10, round(float(value) * 10)))


def _clean_preset_id(value: Any) -> str:
    preset_id = str(value or "").strip()
    if not PRESET_ID_PATTERN.match(preset_id):
        raise ValueError("preset_id must use lowercase letters, numbers, hyphen, or underscore.")
    return preset_id


def _bounded_text(value: Any, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return text


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def _mapping(value: Any, field_name: str) -> ImplementationDocument:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object.")
    return dict(value)


def _string_list(value: Any, field_name: str, *, max_items: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    items = [str(item).strip() for item in value if str(item).strip()]
    return items[:max_items]


def _validate_preset_json_size(preset: EditPreset) -> None:
    size = len(json.dumps(preset.to_dict(), ensure_ascii=False).encode("utf-8"))
    if size > MAX_PRESET_JSON_BYTES:
        raise ValueError(f"preset JSON must be {MAX_PRESET_JSON_BYTES} bytes or fewer.")


def _validate_payload_shape(value: Any, field_name: str) -> None:
    _validate_no_blocked_payload_keys(value, field_name=field_name, depth=0)


def _validate_no_blocked_payload_keys(value: Any, *, field_name: str, depth: int) -> None:
    if depth > MAX_PRESET_PAYLOAD_DEPTH:
        raise ValueError(f"{field_name} is nested too deeply.")
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in BLOCKED_PAYLOAD_KEYS or lowered.endswith("_path"):
                raise ValueError(f"preset payload contains unsupported path or secret field: {key}.")
            _validate_no_blocked_payload_keys(item, field_name=field_name, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate_no_blocked_payload_keys(item, field_name=field_name, depth=depth + 1)
    elif isinstance(value, str) and len(value) > MAX_PRESET_TEXT_FIELD:
        raise ValueError(f"{field_name} text values must be {MAX_PRESET_TEXT_FIELD} characters or fewer.")


BUILT_IN_PRESETS = [
    EditPreset.from_dict(
        {
            "preset_id": "lift-final-chorus",
            "name": "Lift final chorus",
            "description": "Raise the final chorus energy without changing lyrics.",
            "edit_type": "section_energy",
            "strength": 0.8,
            "target_defaults": {"section_role": "chorus", "section_index": -1},
            "preserve": ["tempo", "key", "structure", "lyrics", "harmony"],
            "tags": ["chorus", "energy"],
        },
        built_in=True,
    ),
    EditPreset.from_dict(
        {
            "preset_id": "soften-first-verse",
            "name": "Soften first verse",
            "description": "Lower the first verse energy while preserving the arrangement shape.",
            "edit_type": "section_energy",
            "strength": 0.3,
            "target_defaults": {"section_role": "verse", "section_index": 0},
            "preserve": ["tempo", "key", "structure", "lyrics", "harmony"],
            "tags": ["verse", "energy"],
        },
        built_in=True,
    ),
    EditPreset.from_dict(
        {
            "preset_id": "denser-chorus-drums",
            "name": "Denser chorus drums",
            "description": "Add more drum activity in the chorus.",
            "edit_type": "track_density",
            "strength": 0.8,
            "target_defaults": {"section_role": "chorus", "section_index": -1, "track_role": "drums"},
            "preserve": ["tempo", "key", "structure", "lyrics", "harmony", "melody"],
            "tags": ["drums", "chorus"],
        },
        built_in=True,
    ),
    EditPreset.from_dict(
        {
            "preset_id": "simpler-verse-bass",
            "name": "Simpler verse bass",
            "description": "Reduce bass density in the first verse.",
            "edit_type": "track_density",
            "strength": 0.3,
            "target_defaults": {"section_role": "verse", "section_index": 0, "track_role": "bass"},
            "preserve": ["tempo", "key", "structure", "lyrics", "harmony", "melody"],
            "tags": ["bass", "verse"],
        },
        built_in=True,
    ),
    EditPreset.from_dict(
        {
            "preset_id": "brighter-chorus-harmony",
            "name": "Brighter chorus harmony",
            "description": "Move the chorus to a brighter supported local chord loop.",
            "edit_type": "section_harmony",
            "strength": 0.6,
            "target_defaults": {"section_role": "chorus", "section_index": -1, "field": "chords"},
            "payload": {"chords": ["Cmaj7", "Am7", "Fmaj7", "G7"]},
            "preserve": ["tempo", "key", "structure", "lyrics", "melody"],
            "tags": ["harmony", "chorus"],
        },
        built_in=True,
    ),
    EditPreset.from_dict(
        {
            "preset_id": "melody-small-variation",
            "name": "Melody small variation",
            "description": "Create a light melodic variation in the chorus.",
            "edit_type": "melody_variation",
            "strength": 0.6,
            "target_defaults": {"section_role": "chorus", "section_index": -1},
            "preserve": ["tempo", "key", "structure", "lyrics", "harmony"],
            "tags": ["melody", "variation"],
        },
        built_in=True,
    ),
    EditPreset.from_dict(
        {
            "preset_id": "rewrite-chorus-hook",
            "name": "Rewrite chorus hook",
            "description": "Rewrite the chorus hook text while preserving music structure.",
            "edit_type": "lyrics_rewrite",
            "strength": 0.7,
            "target_defaults": {"section_role": "chorus", "section_index": -1, "field": "lyrics"},
            "payload": {"lyrics": "A clearer hook line for the chorus"},
            "preserve": ["tempo", "key", "structure", "harmony", "melody", "arrangement"],
            "tags": ["lyrics", "hook"],
        },
        built_in=True,
    ),
]
