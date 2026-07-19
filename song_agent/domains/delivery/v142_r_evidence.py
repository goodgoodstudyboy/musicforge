# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir, final_export_zip_path as final_export_zip_path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, ProjectStore as ProjectStore, ProjectVersion as ProjectVersion, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata

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

ReleaseConflictError = _make_deferred_global('ReleaseConflictError')
ReleaseDocument = _make_deferred_global('ReleaseDocument')
ReleaseTrack = _make_deferred_global('ReleaseTrack')
ReleaseValidationError = _make_deferred_global('ReleaseValidationError')
item = _make_deferred_global('item')
section = _make_deferred_global('section')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseConflictError, ReleaseDocument, ReleaseTrack, ReleaseValidationError, item, section
    ReleaseConflictError = namespace.get('ReleaseConflictError', ReleaseConflictError)
    ReleaseDocument = namespace.get('ReleaseDocument', ReleaseDocument)
    ReleaseTrack = namespace.get('ReleaseTrack', ReleaseTrack)
    ReleaseValidationError = namespace.get('ReleaseValidationError', ReleaseValidationError)
    item = namespace.get('item', item)
    section = namespace.get('section', section)
    _bind_deferred_defaults(namespace)


RELEASE_SCHEMA_VERSION = 1
RELEASE_TRACK_SCHEMA_VERSION = 1
RELEASE_TYPES = {"single_pack", "ep", "album", "demo_pack"}
RELEASE_STATUSES = {"draft", "qa_failed", "qa_warning", "qa_passed", "exported", "signed", "archived"}
SIGNED_RELEASE_STATUSES = {"signed"}
BLOCKED_RELEASE_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "provider_snapshot",
    "raw_provider_response",
    "secret",
    "token",
}




def release_document_source(document: ReleaseDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "schema_version": document.schema_version,
            "release_id": document.release_id,
            "name": document.name,
            "release_type": document.release_type,
            "primary_artist": document.primary_artist,
            "label": document.label,
            "language": document.language,
            "notes": document.notes,
            "metadata": document.metadata,
            "tracks": [
                {
                    "track_id": track.track_id,
                    "disc_number": track.disc_number,
                    "track_number": track.track_number,
                    "title": track.title,
                    "artist": track.artist,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "final_export_hash": track.final_export_hash,
                    "delivery_qa_hash": track.delivery_qa_hash,
                    "delivery_signoff_hash": track.delivery_signoff_hash,
                }
                for track in sorted(document.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))
            ],
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )

def stable_hash(value: object) -> str:
    return _stable_hash(value)

def _project_snapshot(document: ProjectDocument, version: ProjectVersion, plan: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "name": document.state.name,
            "hidden": document.state.hidden,
            "final_version_id": document.state.final_version_id,
            "version_id": version.version_id,
            "quality_score": version.quality_score,
            "quality_gate_status": version.quality_gate_status,
            "quality_gate_score": version.quality_gate_score,
            "tempo_bpm": plan.get("tempo_bpm"),
            "key": plan.get("key"),
            "duration_beats": _duration_beats(plan),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )

def _export_snapshot(project_dir: Path, manifest: DomainDocument) -> DomainDocument:
    zip_path = final_export_zip_path(project_dir)
    return sanitize_metadata(
        {
            "exists": bool(manifest),
            "version_id": manifest.get("version_id") if manifest else None,
            "file_count": len(manifest.get("files", [])) if isinstance(manifest.get("files"), list) else 0,
            "generated_at": manifest.get("generated_at") if manifest else None,
            "zip_exists": zip_path.exists(),
            "zip_sha256": _file_sha256(zip_path),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )

def _qa_snapshot(qa: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "status": qa.get("status"),
            "readiness": qa.get("readiness"),
            "handoff_allowed": qa.get("handoff_allowed"),
            "source_hash": qa.get("source_hash"),
            "final_version_id": (qa.get("final_version") or {}).get("version_id") if isinstance(qa.get("final_version"), dict) else None,
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )

def _signoff_snapshot(signoff: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "status": signoff.get("status"),
            "signed_at": signoff.get("signed_at"),
            "final_version_id": signoff.get("final_version_id"),
            "delivery_qa_source_hash": signoff.get("delivery_qa_source_hash"),
            "delivery_qa_hash": signoff.get("delivery_qa_hash"),
            "forced": bool(signoff.get("forced", False)),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )

def _track_title(document: ProjectDocument, version: ProjectVersion, manifest: DomainDocument, plan: DomainDocument) -> str:
    for value in (manifest.get("version_name"), plan.get("title"), version.name, document.state.name):
        text = _bounded_text(value, 120)
        if text:
            return text
    return "Untitled Track"

def _duration_beats(plan: DomainDocument) -> float | None:
    sections = _as_list(plan.get("sections"))
    try:
        return max((float(section.get("start_beat", 0) or 0) + float(section.get("length_bars", 0) or 0) * 4 for section in sections if isinstance(section, dict)), default=None)
    except (TypeError, ValueError):
        return None

def _find_version(document: ProjectDocument, version_id: str) -> ProjectVersion:
    for version in document.versions:
        if version.version_id == version_id:
            return version
    raise ReleaseConflictError("Project version does not exist.")

def _read_optional_json(path: Path) -> DomainDocument:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return _as_document(data)

def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _stable_hash(value: object) -> str:
    clean = sanitize_metadata(value, blocked_keys=BLOCKED_RELEASE_KEYS)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _renumber_tracks(tracks: list[ReleaseTrack]) -> list[ReleaseTrack]:
    ordered = sorted(tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))
    counters: dict[int, int] = {}
    for track in ordered:
        track.disc_number = max(1, int(track.disc_number or 1))
        counters[track.disc_number] = counters.get(track.disc_number, 0) + 1
        track.track_number = counters[track.disc_number]
    return ordered

def _next_track_id(tracks: list[ReleaseTrack]) -> str:
    used = {track.track_id for track in tracks}
    for index in range(1, 1_000_000):
        track_id = f"track-{index:06d}"
        if track_id not in used:
            return track_id
    raise ReleaseConflictError("Unable to allocate a unique track id.")

def _stale_summary(summary: DomainDocument) -> DomainDocument:
    data = _safe_dict(summary)
    if not data:
        return {}
    data["stale"] = True
    if data.get("status") in {"passed", "warning", "signed", "force_signed", "exported"}:
        data["status"] = "stale"
    return data

def _safe_dict(value: object) -> DomainDocument:
    if not isinstance(value, dict):
        return {}
    return sanitize_metadata(value, blocked_keys=BLOCKED_RELEASE_KEYS)

def _release_type(value: object) -> str:
    release_type = str(value or "demo_pack").strip()
    if release_type not in RELEASE_TYPES:
        raise ReleaseValidationError(f"Unsupported release_type: {release_type}.")
    return release_type

def _validate_release_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("release-") or not text.removeprefix("release-").isdigit():
        raise ReleaseValidationError("Invalid release_id.")
    return text

def _validate_track_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("track-") or not text.removeprefix("track-").isdigit():
        raise ReleaseValidationError("Invalid track_id.")
    return text

def _required_id(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ReleaseValidationError(f"{field} is required.")
    return text

def _bounded_text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]

def _optional_bounded_text(value: object, limit: int) -> str | None:
    text = _bounded_text(value, limit)
    return text or None
