# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import os as os
import re as re
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir, final_export_zip_path as final_export_zip_path
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, now_iso as now_iso
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text

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

key = _make_deferred_global('key')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global key, part
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


DELIVERY_QA_SCHEMA_VERSION = 1
DELIVERY_SIGNOFF_SCHEMA_VERSION = 1
DELIVERY_QA_STATUSES = {"passed", "warning", "failed", "stale", "not_ready"}
DELIVERY_READINESS_VALUES = {"ready_to_handoff", "needs_export", "needs_zip", "needs_review", "blocked", "stale", "no_data"}
BLOCKED_DELIVERY_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "local_path",
    "password",
    "provider_snapshot",
    "raw_provider_response",
    "secret",
    "token",
}
ALLOWED_SENSITIVE_KEYS = {"provider_tokens", "token_count", "total_tokens", "input_tokens", "output_tokens"}
SENSITIVE_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}", re.IGNORECASE), "github token"),
    (re.compile(r"ghp_[A-Za-z0-9_]{20,}", re.IGNORECASE), "github token"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}", re.IGNORECASE), "provider key"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}"), "bearer token"),
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"), "secret assignment"),
    (re.compile(r"(?i)\b[A-Z]:[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "local path"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "unc path"),
    (re.compile(r"(?<!\S)/Users/[^/\s,;]+(?:/[^\s,;]+)*"), "local path"),
    (re.compile(r"(?<!\S)/home/[^/\s,;]+(?:/[^\s,;]+)*"), "local path"),
)
CORE_REQUIRED_EXPORT_FILES: tuple[tuple[str, str], ...] = (
    ("manifest", "manifest.json"),
    ("readme", "README.txt"),
    ("project_export", "project-export.json"),
    ("song_plan", "song-plan.json"),
    ("midi", "song.mid"),
)




def _validate_relative_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if "\x00" in normalized:
        raise ValueError("Path contains NUL.")
    if not normalized or normalized.startswith("/") or normalized.startswith("\\") or normalized.startswith("//"):
        raise ValueError("Path must be relative.")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {"..", "."} for part in parts) or ".." in parts:
        raise ValueError("Path contains traversal.")
    if ":" in parts[0]:
        raise ValueError("Path must not include a drive prefix.")
    safe = PurePosixPath(*parts).as_posix()
    if safe.endswith("/"):
        raise ValueError("Path must reference a file.")
    return safe

def _path_presence(value: object) -> str | None:
    return "set" if value else None

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _source_hash(source: DomainDocument) -> str:
    return _stable_hash({key: value for key, value in source.items() if key != "raw_manifest"})

def _stable_hash(value: object) -> str:
    clean = sanitize_metadata(value, blocked_keys=BLOCKED_DELIVERY_KEYS)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _raw_stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
