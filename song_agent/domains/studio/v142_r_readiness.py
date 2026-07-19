# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.documents import DomainDocument
import base64 as base64
import binascii as binascii
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.assets import AssetStore as AssetStore, asset_public_dict as asset_public_dict, sanitize_asset_metadata as sanitize_asset_metadata
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.studio.reference_paths import reference_file_path as reference_file_path, stored_reference_filename as stored_reference_filename
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text

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

MAX_REFERENCE_MIDI_BYTES = _make_deferred_global('MAX_REFERENCE_MIDI_BYTES')
MAX_REFERENCE_TEXT_BYTES = _make_deferred_global('MAX_REFERENCE_TEXT_BYTES')
MAX_REFERENCE_WAV_BYTES = _make_deferred_global('MAX_REFERENCE_WAV_BYTES')
ReferenceItem = _make_deferred_global('ReferenceItem')
SAFE_FILENAME_PATTERN = _make_deferred_global('SAFE_FILENAME_PATTERN')
char = _make_deferred_global('char')
index = _make_deferred_global('index')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_REFERENCE_MIDI_BYTES, MAX_REFERENCE_TEXT_BYTES, MAX_REFERENCE_WAV_BYTES, ReferenceItem, SAFE_FILENAME_PATTERN, char, index
    MAX_REFERENCE_MIDI_BYTES = namespace.get('MAX_REFERENCE_MIDI_BYTES', MAX_REFERENCE_MIDI_BYTES)
    MAX_REFERENCE_TEXT_BYTES = namespace.get('MAX_REFERENCE_TEXT_BYTES', MAX_REFERENCE_TEXT_BYTES)
    MAX_REFERENCE_WAV_BYTES = namespace.get('MAX_REFERENCE_WAV_BYTES', MAX_REFERENCE_WAV_BYTES)
    ReferenceItem = namespace.get('ReferenceItem', ReferenceItem)
    SAFE_FILENAME_PATTERN = namespace.get('SAFE_FILENAME_PATTERN', SAFE_FILENAME_PATTERN)
    char = namespace.get('char', char)
    index = namespace.get('index', index)
    _bind_deferred_defaults(namespace)


REFERENCE_SCHEMA_VERSION = 1
MAX_REFERENCE_REFS = 5
MAX_REFERENCE_TEXT_LINES = 5000
REFERENCE_TYPES = {"audio_wav", "midi", "lyrics_text", "style_note"}
REFERENCE_EXTENSIONS = {
    "audio_wav": {".wav"},
    "midi": {".mid", ".midi"},
    "lyrics_text": {".txt", ".md"},
    "style_note": {".txt", ".md"},
}
REFERENCE_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}




def _decode_base64(value: object) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("content_base64 is required.")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("content_base64 must be valid base64.") from exc

def _validate_reference_content(reference_type: str, content: bytes) -> str:
    if not content:
        raise ValueError("reference content must not be empty.")
    if reference_type == "audio_wav":
        if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
            raise ValueError("audio_wav references must be valid WAV RIFF/WAVE files.")
        return ""
    if reference_type == "midi":
        if len(content) < 14 or content[:4] != b"MThd":
            raise ValueError("midi references must start with a MIDI MThd header.")
        return ""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("text references must be valid UTF-8.") from exc
    if "\x00" in text:
        raise ValueError("text references must not contain null bytes.")
    if len(text.splitlines()) > MAX_REFERENCE_TEXT_LINES:
        raise ValueError(f"text references support at most {MAX_REFERENCE_TEXT_LINES} lines.")
    return text.strip()[:2000]

def _validate_size(reference_type: str, size_bytes: int) -> None:
    limits = {
        "audio_wav": MAX_REFERENCE_WAV_BYTES,
        "midi": MAX_REFERENCE_MIDI_BYTES,
        "lyrics_text": MAX_REFERENCE_TEXT_BYTES,
        "style_note": MAX_REFERENCE_TEXT_BYTES,
    }
    limit = limits[reference_type]
    if size_bytes <= 0:
        raise ValueError("reference content must not be empty.")
    if size_bytes > limit:
        raise ValueError(f"{reference_type} references must be {limit} bytes or fewer.")

def _safe_filename(value: str, *, strict: bool = True) -> str:
    filename = value.strip()
    if not filename:
        raise ValueError("filename is required.")
    if not _filename_is_safe(filename):
        if strict:
            if "\x00" in filename or any(ord(char) < 32 or char == "\x7f" for char in filename):
                raise ValueError("filename must not contain control characters.")
            if "/" in filename or "\\" in filename or ":" in filename:
                raise ValueError("filename must not contain path separators.")
            raise ValueError("filename contains unsupported characters.")
        filename = _fallback_safe_filename(filename)
    if filename in {".", ".."} or len(filename) > 160:
        raise ValueError("filename is invalid.")
    stem = Path(filename).stem.upper().rstrip(". ")
    if stem in WINDOWS_RESERVED_NAMES:
        raise ValueError("filename uses a reserved system name.")
    return filename

def _filename_is_safe(filename: str) -> bool:
    if "\x00" in filename or any(ord(char) < 32 or char == "\x7f" for char in filename):
        return False
    if "/" in filename or "\\" in filename or ":" in filename:
        return False
    if '"' in filename or "'" in filename or "\t" in filename:
        return False
    return bool(SAFE_FILENAME_PATTERN.match(filename))

def _fallback_safe_filename(filename: str) -> str:
    suffix = _extension(Path(filename).suffix or ".bin")
    prefix = re.split(r"[\x00-\x1f\x7f]+", filename, maxsplit=1)[0]
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(prefix).stem)
    stem = stem.strip(" ._") or "reference"
    if len(stem) > 120:
        stem = stem[:120].rstrip(" ._") or "reference"
    return f"{stem}{suffix}"

def _extension(value: str) -> str:
    extension = value.strip().lower()
    if not extension.startswith("."):
        extension = f".{extension}"
    return extension

def _stored_filename(reference_type: str, extension: str) -> str:
    return stored_reference_filename(reference_type, extension)

def _clean_tags(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list.")
    tags = []
    for item in value:
        tag = str(item).strip()
        if not tag:
            continue
        if len(tag) > 48:
            raise ValueError("reference tags must be 48 characters or fewer.")
        if tag not in tags:
            tags.append(tag)
    if len(tags) > 32:
        raise ValueError("reference tags supports at most 32 items.")
    return tags

def _clean_ids(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} ids must be a list.")
    cleaned = []
    for item in value:
        cleaned_id = _validate_external_id(str(item), label)
        if cleaned_id not in cleaned:
            cleaned.append(cleaned_id)
    return cleaned

def _validate_external_id(value: str, label: str) -> str:
    text = value.strip()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}", text):
        raise ValueError(f"Invalid {label} id.")
    return text

def _bounded_text(value: object, field_name: str, max_length: int) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return text

def _optional_tempo(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    tempo = int(value)
    if tempo < 40 or tempo > 240:
        raise ValueError("tempo_bpm must be between 40 and 240.")
    return tempo

def _reference_matches(reference: ReferenceItem, filters: DomainDocument) -> bool:
    q = str(filters.get("q") or "").strip().lower()
    if q and q not in f"{reference.title} {reference.description} {' '.join(reference.tags)}".lower():
        return False
    type_filter = str(filters.get("type") or filters.get("reference_type") or "").strip()
    if type_filter and reference.reference_type != type_filter:
        return False
    tag = str(filters.get("tag") or "").strip()
    if tag and tag not in reference.tags:
        return False
    project_id = str(filters.get("project_id") or "").strip()
    if project_id and project_id not in reference.linked_project_ids:
        return False
    if filters.get("favorite") in {True, "1", "true", "yes"} and not reference.favorite:
        return False
    return True

def _strength(value: object) -> float:
    strength = 0.7 if value is None or str(value).strip() == "" else float(value)
    if strength < 0 or strength > 1:
        raise ValueError("reference ref strength must be between 0 and 1.")
    return round(strength, 3)

def _default_reference_role(reference_type: str) -> str:
    return {
        "audio_wav": "reference_audio",
        "midi": "reference_midi",
        "lyrics_text": "reference_lyrics",
        "style_note": "reference_style",
    }.get(reference_type, "reference")

def _read_text_excerpt(reference: ReferenceItem, payload: DomainDocument) -> str:
    text = _bounded_text(payload.get("text"), "text", 2000)
    return text or reference.text_excerpt or reference.title

def _midi_seed_content(reference: ReferenceItem, asset_type: str) -> DomainDocument:
    if asset_type == "motif":
        return {
            "kind": "motif",
            "reference_id": reference.reference_id,
            "pitch_intervals": [0, 2, 4, 7],
            "rhythm_pattern": [1.0, 1.0, 1.0, 1.0],
            "anchor_pitch": 64,
            "midi_sha256": reference.sha256,
        }
    if asset_type == "chord_progression":
        return {"kind": "chord_progression", "reference_id": reference.reference_id, "chords": ["Cmaj7", "Am7", "Fmaj7", "G7"], "midi_sha256": reference.sha256}
    if asset_type == "drum_pattern":
        return {
            "kind": "drum_pattern",
            "reference_id": reference.reference_id,
            "notes": [
                {"pitch": 36, "start_beat": 0.0, "duration_beats": 0.25, "velocity": 96},
                {"pitch": 38, "start_beat": 1.0, "duration_beats": 0.25, "velocity": 88},
                {"pitch": 42, "start_beat": 0.5, "duration_beats": 0.25, "velocity": 72},
            ],
            "midi_sha256": reference.sha256,
        }
    return {
        "kind": "bass_pattern",
        "reference_id": reference.reference_id,
        "notes": [
            {"pitch": 36, "start_beat": 0.0, "duration_beats": 1.0, "velocity": 86},
            {"pitch": 43, "start_beat": 2.0, "duration_beats": 1.0, "velocity": 82},
        ],
        "midi_sha256": reference.sha256,
    }

def _append_reference_event(reference_dir: Path, event_type: str, payload: DomainDocument, timestamp: str | None = None) -> None:
    event = {"timestamp": timestamp or now_iso(), "type": event_type, "payload": payload}
    reference_dir.mkdir(parents=True, exist_ok=True)
    with (reference_dir / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
