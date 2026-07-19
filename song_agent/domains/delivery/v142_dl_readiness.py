# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
from pathlib import Path as Path, PurePosixPath as PurePosixPath
import hashlib as hashlib
import json as json
from song_agent.domains.quality.audio_encoding import normalize_required_profiles as normalize_required_profiles
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_templates import DistributionTemplateError as DistributionTemplateError, template_file_naming as template_file_naming, template_summary as template_summary
from song_agent.domains.studio.projectio import slugify as slugify
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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

LYRICS_VARIABLES = _make_deferred_global('LYRICS_VARIABLES')
key = _make_deferred_global('key')
validate_layout_path = _make_deferred_global('validate_layout_path')

def bind_globals(namespace: dict[str, object]) -> None:
    global LYRICS_VARIABLES, key, validate_layout_path
    LYRICS_VARIABLES = namespace.get('LYRICS_VARIABLES', LYRICS_VARIABLES)
    key = namespace.get('key', key)
    validate_layout_path = namespace.get('validate_layout_path', validate_layout_path)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_LAYOUT_SCHEMA_VERSION = 1
DISTRIBUTION_LAYOUT_COLLISION_STRATEGY = "append-index"
DEFAULT_FILE_NAMING = {
    "audio": "audio/{track_number:02d}-{slug_title}.{ext}",
    "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt",
    "artwork": "artwork/cover.{ext}",
}
RESERVED_LAYOUT_PATHS = {
    "distribution-manifest.json",
    "distribution-signoff.json",
    "package.json",
    "release.json",
    "tracklist.json",
    "README.txt",
    "template-pack.json",
    "template-summary.json",
    "docs/checklist.json",
    "docs/checklist.md",
    "docs/submission-notes.md",
    "release-metadata.json",
    "platform-metadata.csv",
    "template-platform-metadata.csv",
    "credits.csv",
    "layout/manifest-layout.json",
    "layout/file-tree.txt",
}
AUDIO_VARIABLES = {"track_number", "track_number:02d", "disc_number", "slug_title", "track_id", "isrc", "ext", "format", "profile_id", "codec", "bitrate_kbps"}
ARTWORK_VARIABLES = {"release_slug", "release_id", "upc", "profile_id", "target_id", "ext"}
KIND_VARIABLES = {"audio": AUDIO_VARIABLES, "lyrics": LYRICS_VARIABLES, "artwork": ARTWORK_VARIABLES}




def _track_context(track: DomainDocument, metadata: DomainDocument | None, release_info: DomainDocument) -> DomainDocument:
    metadata = _as_document(metadata)
    merged = {**track, **{key: value for key, value in metadata.items() if value not in (None, "", [])}}
    merged["language"] = merged.get("language") or release_info.get("language")
    return merged

def _audio_source_rel(root: Path | None, track: DomainDocument, *, target_info: DomainDocument, encoded_audio_summary: DomainDocument | None, encoded_audio_root: Path | None, profile_id: str) -> tuple[str, str, str, DomainDocument]:
    profile_id = _validate_profile_id(profile_id or "wav_master")
    if profile_id != "wav_master":
        profile = _encoded_profile_summary(encoded_audio_summary, profile_id)
        ext = str(profile.get("extension") or "").strip(".").lower()
        if ext:
            track_id = str(track.get("track_id") or "")
            rel = validate_layout_path(f"formats/{profile_id}/tracks/{track_id}/song.{ext}")
            return rel, ext, "encoded_audio", profile
    directory = str(track.get("directory") or "").strip("/")
    candidates = [f"{directory}/song.wav" if directory else "song.wav", f"{directory}/song.mid" if directory else "song.mid"]
    for rel in candidates:
        if _source_exists(root, rel):
            return validate_layout_path(rel), Path(rel).suffix.lower().lstrip(".") or "wav", "release_export", {"profile_id": "wav_master", "format": "wav", "extension": "wav", "codec": "pcm_s16le"}
    fallback = candidates[0]
    return validate_layout_path(fallback), Path(fallback).suffix.lower().lstrip(".") or "wav", "release_export", {"profile_id": "wav_master", "format": "wav", "extension": "wav", "codec": "pcm_s16le"}

def _encoded_profile_summary(summary: DomainDocument | None, profile_id: str) -> DomainDocument:
    profiles = summary.get("profiles") if isinstance(summary, dict) and isinstance(summary.get("profiles"), list) else []
    for row in _as_list(profiles):
        if isinstance(row, dict) and row.get("profile_id") == profile_id:
            return row
    return {"profile_id": profile_id, "format": profile_id.split("_", 1)[0], "extension": profile_id.split("_", 1)[0], "codec": ""}

def _target_audio_profile_ids(target_info: DomainDocument, rules: DomainDocument) -> list[str]:
    options = _as_document(target_info.get("options"))
    profiles = _normalize_profile_ids(options.get("audio_format_profiles"))
    if not profiles:
        profiles = _normalize_profile_ids(rules.get("required_audio_formats"))
    if not profiles:
        profiles = _normalize_profile_ids(options.get("primary_audio_format") or rules.get("primary_audio_format"))
    return profiles or ["wav_master"]

def _normalize_profile_ids(value: object) -> list[str]:
    return normalize_required_profiles(value)

def _validate_profile_id(value: str) -> str:
    return normalize_required_profiles([value])[0]

def _lyrics_source_rel(track: DomainDocument) -> str:
    title = slugify(str(track.get("title") or track.get("track_id") or "track"))[:60]
    return validate_layout_path(f"lyrics/{int(track.get('track_number') or 1):02d}-{title}.txt")

def _artwork_source_rel(artwork: DomainDocument | None) -> str:
    if not artwork:
        return "distribution-artwork/missing"
    return validate_layout_path(f"distribution-artwork/{_slug_value(artwork.get('artwork_id') or artwork.get('stored_filename'), 'cover')}")

def _source_exists(root: Path | None, rel: str) -> bool:
    if root is None:
        return False
    try:
        path = (root / validate_layout_path(rel)).resolve()
        path.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return path.exists() and path.is_file() and not path.is_symlink()

def _slug_value(value: object, default: str) -> str:
    return slugify(str(value or default))[:80] or default

def _attr(value: object, name: str) -> object:
    return getattr(value, name, None)

def _entry_hash_payload(entry: DomainDocument) -> DomainDocument:
    return {key: entry.get(key) for key in ("entry_id", "kind", "track_id", "source_rel", "source_kind", "path", "pattern", "ext", "audio_format", "required", "exists", "status", "collision", "original_path", "collision_index")}

def _layout_hash_payload(plan: DomainDocument) -> DomainDocument:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"layout_hash", "summary"}
    }

def _check(check_id: str, passed: bool, severity: str, message: str, *, count: int | None = None, warning_when_false: bool = False) -> DomainDocument:
    status = "passed" if passed else "warning" if warning_when_false else "failed"
    item: DomainDocument = {"scope": "layout", "check_id": check_id, "status": status, "severity": severity, "message": message}
    if count is not None:
        item["count"] = count
    return sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
