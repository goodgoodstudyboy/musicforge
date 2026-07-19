# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_float as _as_float, as_list as _as_list, document_or as _document_or
import json as json
import re as re
from pathlib import Path as Path
from song_agent.domains.studio.assets import AssetStore as AssetStore
from song_agent.domains.studio.context_packs import ContextPackStore as ContextPackStore
from song_agent.domains.studio.library_index import asset_source_hash as asset_source_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.studio.references import ReferenceStore as ReferenceStore
from song_agent.domains.delivery.release_metadata import read_release_metadata as read_release_metadata
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

RIGHTS_BLOCKED_KEYS = _make_deferred_global('RIGHTS_BLOCKED_KEYS')
RightsClearanceError = _make_deferred_global('RightsClearanceError')

def bind_globals(namespace: dict[str, object]) -> None:
    global RIGHTS_BLOCKED_KEYS, RightsClearanceError
    RIGHTS_BLOCKED_KEYS = namespace.get('RIGHTS_BLOCKED_KEYS', RIGHTS_BLOCKED_KEYS)
    RightsClearanceError = namespace.get('RightsClearanceError', RightsClearanceError)
    _bind_deferred_defaults(namespace)


RIGHTS_SCHEMA_VERSION = 1
RIGHTS_REPORT_INTEGRITY_EXCLUDE = {"integrity_hash", "integrity_ok", "stale", "stale_reasons", "current_source_hash"}
RIGHTS_TRACK_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons"}
RIGHTS_SUMMARY_INTEGRITY_EXCLUDE = {"summary_hash"}
CONTRIBUTOR_ROLES_REQUIRING_SPLITS = {"composer", "lyricist"}
SOURCE_BLOCKING_STATUSES = {"uncleared", "blocked", "unknown", "pending"}
SOURCE_SAFE_STATUSES = {"cleared", "waived", "owned", "public_domain", "original"}




def _context_pack_required_source(ref: DomainDocument, *, context_pack_store: ContextPackStore, detected_in: str, version_id: str) -> DomainDocument:
    pack_id = _safe_id(str(ref.get("pack_id") or ""), "pack")
    status = "current"
    stale_reasons: list[str] = []
    try:
        pack = context_pack_store.read_pack(pack_id)
        if pack.hidden:
            status = "hidden"
            stale_reasons.append("context_pack_hidden")
    except (OSError, ValueError, TypeError, FileNotFoundError):
        status = "missing"
        stale_reasons.append("context_pack_missing")
    return {
        "source_id": pack_id,
        "source_type": "context_pack",
        "name": _text(ref.get("name") or pack_id, 180),
        "source_status": status,
        "source_hash": str(ref.get("source_hash") or ""),
        "detected_in": [detected_in],
        "used_by_versions": sorted(set([version_id, *[str(item) for item in _list(ref.get("used_by_versions")) if str(item).strip()]])),
        "stale_reasons": stale_reasons,
    }

def _metadata_required_source(ref: DomainDocument, *, source_type: str, detected_in: str, version_id: str) -> DomainDocument:
    source_id = _metadata_source_id(ref, source_type)
    return {
        "source_id": source_id,
        "source_type": source_type,
        "name": _text(ref.get("name") or ref.get("title") or ref.get("source_id") or source_id, 180),
        "source_status": "current",
        "source_hash": stable_hash(sanitize_metadata(ref, blocked_keys=RIGHTS_BLOCKED_KEYS)),
        "detected_in": [detected_in],
        "used_by_versions": [version_id] if version_id else [],
        "stale_reasons": [],
    }

def _metadata_source_id(ref: DomainDocument, source_type: str) -> str:
    for key in ("source_id", "asset_id", "reference_id", "clip_id", "template_id", "candidate_id", "group_id", "preview_id", "task_id", "provider_id", "template_name"):
        value = str(ref.get(key) or "").strip()
        if value:
            return _safe_id(value, source_type)
    return _safe_id(stable_hash(ref)[:16], source_type)

def _normalize_required_source(source: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "source_id": _safe_id(str(source.get("source_id") or ""), "source") if str(source.get("source_id") or "").strip() else "",
            "source_type": _text(source.get("source_type") or "source", 80).lower(),
            "name": _text(source.get("name"), 180),
            "role": _text(source.get("role"), 120),
            "source_status": _text(source.get("source_status") or "current", 80).lower(),
            "source_hash": _text(source.get("source_hash"), 128),
            "detected_in": sorted(set(str(item)[:160] for item in _list(source.get("detected_in")) if str(item).strip())),
            "used_by_versions": sorted(set(str(item)[:80] for item in _list(source.get("used_by_versions")) if str(item).strip())),
            "stale_reasons": sorted(set(str(item)[:160] for item in _list(source.get("stale_reasons")) if str(item).strip())),
        },
        blocked_keys=RIGHTS_BLOCKED_KEYS,
    )

def _used_by_version(ref: DomainDocument, version_id: str) -> bool:
    if not version_id:
        return False
    return version_id in {str(item) for item in _list(ref.get("used_by_versions"))}

def _normalize_contributor(item: object) -> DomainDocument:
    data = _as_document(item)
    role = str(data.get("role") or "composer").strip().lower()
    share = data.get("share") if data.get("share") is not None else data.get("split_percent")
    try:
        share_value = round(_as_float(share), 4)
    except (TypeError, ValueError):
        share_value = 0.0
    return sanitize_metadata(
        {
            "party_id": _safe_id(str(data.get("party_id") or ""), "party") if str(data.get("party_id") or "").strip() else "",
            "role": role,
            "share": share_value,
            "territory": _text(data.get("territory") or "worldwide", 120),
            "rights_type": _text(data.get("rights_type") or role, 120),
            "notes": _text(data.get("notes"), 1000),
        },
        blocked_keys=RIGHTS_BLOCKED_KEYS,
    )

def _normalize_source_usage(item: object) -> DomainDocument:
    data = _as_document(item)
    return sanitize_metadata(
        {
            "source_id": _safe_id(str(data.get("source_id") or ""), "source") if str(data.get("source_id") or "").strip() else "",
            "name": _text(data.get("name") or data.get("title"), 180),
            "source_type": _text(data.get("source_type") or data.get("type") or "original", 80),
            "status": str(data.get("status") or "original").strip().lower(),
            "risk_level": str(data.get("risk_level") or data.get("risk") or "low").strip().lower(),
            "license_ref": _text(data.get("license_ref") or data.get("license"), 240),
            "notes": _text(data.get("notes"), 1000),
        },
        blocked_keys=RIGHTS_BLOCKED_KEYS,
    )

def _release_track(release: object, track_id: str) -> object | None:
    for track in getattr(release, "tracks", []):
        if getattr(track, "track_id", "") == track_id:
            return track
    return None

def _track_snapshot(track: object) -> DomainDocument:
    return {
        "track_id": getattr(track, "track_id", None),
        "disc_number": getattr(track, "disc_number", None),
        "track_number": getattr(track, "track_number", None),
        "title": getattr(track, "title", None),
        "artist": getattr(track, "artist", None),
        "project_id": getattr(track, "project_id", None),
        "version_id": getattr(track, "version_id", None),
        "final_export_hash": getattr(track, "final_export_hash", None),
    }

def _metadata_track(release_store: ReleaseStore, release_id: str, track_id: str) -> DomainDocument:
    metadata = read_release_metadata(release_store, release_id, default={})
    return _metadata_track_from_doc(metadata, track_id)

def _metadata_track_from_doc(metadata: DomainDocument, track_id: str) -> DomainDocument:
    for track in metadata.get("tracks", []) if isinstance(metadata.get("tracks"), list) else []:
        if isinstance(track, dict) and str(track.get("track_id") or "") == track_id:
            return track
    return {}

def _metadata_snapshot(metadata_track: DomainDocument) -> DomainDocument:
    return {
        "track_id": metadata_track.get("track_id"),
        "title": metadata_track.get("title"),
        "display_artist": metadata_track.get("display_artist"),
        "primary_artist": metadata_track.get("primary_artist"),
        "instrumental": metadata_track.get("instrumental"),
        "lyrics_hash": stable_hash({"lyrics": metadata_track.get("lyrics")}) if metadata_track.get("lyrics") else None,
        "credits": [
            {"role": credit.get("role"), "name": credit.get("name")}
            for credit in metadata_track.get("credits", [])
            if isinstance(credit, dict)
        ],
    }

def _metadata_credit_names(metadata_track: DomainDocument) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for credit in metadata_track.get("credits", []) if isinstance(metadata_track.get("credits"), list) else []:
        if not isinstance(credit, dict):
            continue
        role = str(credit.get("role") or "").lower()
        name = _norm_name(credit.get("name"))
        if role and name:
            result.setdefault(role, set()).add(name)
    return result

def _read_json_default(path: Path, default: DomainDocument) -> DomainDocument:
    if not path.exists():
        return dict(default)
    value = read_json(path)
    return _document_or(value, dict(default))

def _safe_id(value: str, prefix: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-")
    return clean or f"{prefix}-000001"

def _next_id(rows: list[object], prefix: str, field: str) -> str:
    used = {str(item.get(field) or "") for item in rows if isinstance(item, dict)}
    for index in range(1, 1_000_000):
        candidate = f"{prefix}-{index:06d}"
        if candidate not in used:
            return candidate
    raise RightsClearanceError("Unable to allocate rights id.")

def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]

def _norm_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def _list(value: object) -> list[object]:
    return _as_list(value)

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value), blocked_keys=RIGHTS_BLOCKED_KEYS)

def _looks_like_local_path(value: str) -> bool:
    text = str(value)
    return bool(re.search(r"(?i)\b[A-Z]:[\\/]", text) or re.search(r"(?<!\S)/(?:Users|home)/", text) or re.search(r"\\\\[^\\/]+[\\/]", text))
