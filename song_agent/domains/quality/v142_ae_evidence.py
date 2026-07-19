# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import subprocess as subprocess
import threading as threading
from dataclasses import dataclass as dataclass
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Protocol as Protocol
from song_agent.domains.quality.audio_encoding_profiles import AudioEncodingProfile as AudioEncodingProfile, AudioEncodingProfileError as AudioEncodingProfileError, AudioEncodingProfileStore as AudioEncodingProfileStore, audio_encoding_profile_hash as audio_encoding_profile_hash, audio_encoding_profile_integrity_ok as audio_encoding_profile_integrity_ok
from song_agent.domains.quality.mastering_qa import mastering_summary_hash as mastering_summary_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

AudioEncodingError = _make_deferred_global('AudioEncodingError')
sep = _make_deferred_global('sep')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioEncodingError, sep
    AudioEncodingError = namespace.get('AudioEncodingError', AudioEncodingError)
    sep = namespace.get('sep', sep)
    _bind_deferred_defaults(namespace)


AUDIO_ENCODING_SCHEMA_VERSION = 1
AUDIO_ENCODING_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
AUDIO_ENCODING_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
ENCODER_CONFIG_FILENAME = "audio-encoder.json"
COMMAND_POLICY_VERSION = "v1"
MIN_ENCODED_AUDIO_BYTES = 8




def _executable_exists(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(sep in text for sep in ("/", "\\")):
        path = Path(text)
        return path.exists() and path.is_file()
    return shutil.which(text) is not None

def _int_range(value: object, field: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AudioEncodingError(f"{field} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise AudioEncodingError(f"{field} must be between {minimum} and {maximum}.")
    return parsed
