# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Protocol as Protocol
from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, score_song_plan as score_song_plan
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
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

ProjectDocument = _make_deferred_global('ProjectDocument')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global ProjectDocument, item
    ProjectDocument = namespace.get('ProjectDocument', ProjectDocument)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


PROJECT_STATUSES = {"active", "archived", "finalized"}
VARIANT_TYPES = {
    "original",
    "style_variation",
    "tempo_key_variation",
    "lyrics_variation",
    "arrangement_variation",
    "quality_repair",
    "manual",
    "section_edit",
    "track_edit",
    "lyrics_edit",
    "melody_edit",
    "arrangement_edit",
    "provider_edit",
    "manual_editor_edit",
    "mix_control_edit",
    "audio_revision_mix_edit",
}
QUALITY_GATE_STATUSES = {
    "not_evaluated",
    "passed",
    "warning",
    "failed",
    "missing_plan",
    "error",
}
VERSION_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
    "stalled",
    "missing_job",
}
BLOCKED_ASSET_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "token",
}




def _collect_project_context_packs(project_dir: Path, document: ProjectDocument) -> list[DomainDocument]:
    packs: dict[str, DomainDocument] = {}

    def add_pack(data: DomainDocument, *, version_id: str | None = None, candidate_group_id: str | None = None) -> None:
        pack_id = str(data.get("pack_id") or "").strip()
        if not pack_id:
            return
        record = packs.setdefault(
            pack_id,
            {
                "pack_id": pack_id,
                "name": str(data.get("name") or pack_id),
                "asset_count": len(data.get("asset_refs") or []) if isinstance(data.get("asset_refs"), list) else int(data.get("asset_count") or 0),
                "reference_count": len(data.get("reference_refs") or []) if isinstance(data.get("reference_refs"), list) else int(data.get("reference_count") or 0),
                "created_from": _sanitize_asset_metadata(data.get("created_from")) if isinstance(data.get("created_from"), dict) else {},
                "query": _sanitize_asset_metadata(data.get("query")) if isinstance(data.get("query"), dict) else {},
                "used_by_versions": [],
                "used_by_candidate_groups": [],
            },
        )
        if data.get("name") and record.get("name") == pack_id:
            record["name"] = str(data.get("name"))
        if version_id and version_id not in record["used_by_versions"]:
            record["used_by_versions"].append(version_id)
        if candidate_group_id and candidate_group_id not in record["used_by_candidate_groups"]:
            record["used_by_candidate_groups"].append(candidate_group_id)

    for version in document.versions:
        path = Path(version.output_dir) / "data" / "context-pack.json"
        if not path.exists():
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            add_pack(data, version_id=version.version_id)

    candidate_root = project_dir / "candidate-groups"
    if candidate_root.exists():
        for group_json in candidate_root.glob("*/group.json"):
            try:
                data = read_json(group_json)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            source = data.get("source") if isinstance(data, dict) else None
            context_pack = source.get("context_pack") if isinstance(source, dict) else None
            if isinstance(context_pack, dict):
                add_pack(context_pack, candidate_group_id=str(data.get("group_id") or group_json.parent.name))

    return sorted((_sanitize_asset_metadata(record) for record in packs.values()), key=lambda item: item["pack_id"])

def _sanitize_asset_metadata(value: object) -> DomainDocument:
    return sanitize_metadata(value, blocked_keys=BLOCKED_ASSET_METADATA_KEYS)
