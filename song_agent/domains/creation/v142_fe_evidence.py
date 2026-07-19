# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from song_agent.domains.studio.project_quality import QualityGateResult as QualityGateResult
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stems import read_stem_manifest as read_stem_manifest, stem_audio_path as stem_audio_path, stem_manifest_stale as stem_manifest_stale, stem_midi_path as stem_midi_path

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

FinalExportError = _make_deferred_global('FinalExportError')
FinalExportOptions = _make_deferred_global('FinalExportOptions')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global FinalExportError, FinalExportOptions, item, key, part
    FinalExportError = namespace.get('FinalExportError', FinalExportError)
    FinalExportOptions = namespace.get('FinalExportOptions', FinalExportOptions)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


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




def _final_delivery_signoff(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("delivery_signoff_summary"), dict):
        return {}
    summary = project_export["delivery_signoff_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "signed_at": summary.get("signed_at"),
                "signed_by": summary.get("signed_by"),
                "forced": summary.get("forced"),
                "delivery_qa_status": summary.get("delivery_qa_status"),
                "final_version_id": summary.get("final_version_id"),
                "zip_sha256": summary.get("zip_sha256"),
            }
        )
    )

def _context_pack_export_summary(pack: DomainDocument) -> DomainDocument:
    summary = {
        "pack_id": str(pack.get("pack_id") or ""),
        "name": str(pack.get("name") or pack.get("pack_id") or ""),
        "asset_count": len(pack.get("asset_refs") or []) if isinstance(pack.get("asset_refs"), list) else int(pack.get("asset_count") or 0),
        "reference_count": len(pack.get("reference_refs") or []) if isinstance(pack.get("reference_refs"), list) else int(pack.get("reference_count") or 0),
        "created_from": _sanitize_asset_metadata(pack.get("created_from")) if isinstance(pack.get("created_from"), dict) else {},
        "query": _sanitize_asset_metadata(pack.get("query")) if isinstance(pack.get("query"), dict) else {},
        "used_by_versions": [str(item) for item in pack.get("used_by_versions", []) if str(item).strip()] if isinstance(pack.get("used_by_versions"), list) else [],
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _reference_ref_export_summary(ref: DomainDocument) -> DomainDocument:
    summary = {
        "reference_id": _safe_reference_id(str(ref.get("reference_id") or "")),
        "reference_type": str(ref.get("reference_type") or ""),
        "title": str(ref.get("title") or ref.get("reference_id") or ""),
        "roles": [str(item) for item in ref.get("roles", []) if str(item).strip()] if isinstance(ref.get("roles"), list) else [],
        "role": str(ref.get("role") or "") if ref.get("role") else None,
        "strength": ref.get("strength") if isinstance(ref.get("strength"), (int, float)) else None,
        "used_by_versions": [str(item) for item in ref.get("used_by_versions", []) if str(item).strip()] if isinstance(ref.get("used_by_versions"), list) else [],
        "used_by_candidate_groups": [str(item) for item in ref.get("used_by_candidate_groups", []) if str(item).strip()] if isinstance(ref.get("used_by_candidate_groups"), list) else [],
        "linked_to_project": True if ref.get("linked_to_project") else None,
        "metadata_summary": _sanitize_asset_metadata(ref.get("metadata_summary")) if isinstance(ref.get("metadata_summary"), dict) else {},
        "analysis_summary": _sanitize_asset_metadata(ref.get("analysis_summary")) if isinstance(ref.get("analysis_summary"), dict) else {},
    }
    return _drop_empty(summary)

def _asset_ref_export_summary(ref: DomainDocument) -> DomainDocument:
    summary = {
        "asset_id": _safe_asset_id(str(ref.get("asset_id") or "")),
        "asset_type": str(ref.get("asset_type") or ""),
        "name": str(ref.get("name") or ref.get("asset_id") or ""),
        "roles": [str(item) for item in ref.get("roles", []) if str(item).strip()] if isinstance(ref.get("roles"), list) else [],
        "role": str(ref.get("role") or "") if ref.get("role") else None,
        "strength": ref.get("strength") if isinstance(ref.get("strength"), (int, float)) else None,
        "used_by_versions": [str(item) for item in ref.get("used_by_versions", []) if str(item).strip()] if isinstance(ref.get("used_by_versions"), list) else [],
        "used_by_candidate_groups": [str(item) for item in ref.get("used_by_candidate_groups", []) if str(item).strip()] if isinstance(ref.get("used_by_candidate_groups"), list) else [],
        "content_summary": _sanitize_asset_metadata(ref.get("content_summary")) if isinstance(ref.get("content_summary"), dict) else {},
        "source": _sanitize_asset_metadata(ref.get("source")) if isinstance(ref.get("source"), dict) else {},
    }
    return _drop_empty(summary)

def _drop_empty(value: DomainDocument) -> DomainDocument:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }

def _safe_asset_id(asset_id: str) -> str:
    if not re.match(r"^asset-[0-9]{3,6}$", asset_id):
        raise FinalExportError("Invalid asset id in asset refs.")
    return asset_id

def _safe_reference_id(reference_id: str) -> str:
    if not re.match(r"^ref-[0-9]{3,6}$", reference_id):
        raise FinalExportError("Invalid reference id in reference refs.")
    return reference_id

def _sanitize_asset_metadata(value: object) -> DomainDocument:
    return sanitize_metadata(value, blocked_keys=BLOCKED_ASSET_METADATA_KEYS)

def _write_readme(export_dir: Path, project: object, version: object, gate: QualityGateResult, manifest: DomainDocument) -> None:
    lines = [
        "MusicForge Final Export",
        "",
        f"Project: {project.name}",
        f"Version: {version.version_id} {version.name}",
        f"Job: {version.job_id}",
        f"Generated: {manifest['generated_at']}",
        f"Quality Overall: {gate.score if gate.score is not None else '-'}",
        f"Quality Gate: {gate.status}",
        "",
        "Files:",
    ]
    lines.extend(f"- {file['path']}" for file in manifest["files"] if file.get("exists"))
    if version.note:
        lines.extend(["", "Notes:", version.note])
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _prepare_export_dir(project_dir: Path) -> Path:
    project_dir = project_dir.resolve()
    export_dir = (project_dir / "final-export").resolve()
    _ensure_within(project_dir, export_dir)
    if export_dir == project_dir:
        raise FinalExportError("Refusing to replace the project directory.")
    if export_dir.exists():
        if export_dir.is_symlink():
            raise FinalExportError("Refusing to replace a symlinked final export directory.")
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir

def _load_song_plan(plan_path: Path) -> SongPlan | None:
    if not plan_path.exists():
        return None
    try:
        return SongPlan.from_dict(read_json(plan_path))
    except (OSError, TypeError, ValueError):
        return None

def _relative_to_run_dir(run_dir: Path, source: Path) -> str:
    try:
        return source.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("Refusing to copy a source outside the job run directory.") from exc

def _unsafe_stem_path_records(run_dir: Path, manifest: object, options: FinalExportOptions) -> list[DomainDocument]:
    records: list[DomainDocument] = []
    for stem in manifest.stems:
        try:
            stem_midi_path(run_dir, manifest, stem.stem_id)
        except (FileNotFoundError, ValueError) as exc:
            records.append(_skipped_stem_record("stem_midi", stem.midi_path, exc))
        if options.include_stem_audio:
            try:
                stem_audio_path(run_dir, manifest, stem.stem_id)
            except (FileNotFoundError, ValueError) as exc:
                records.append(_skipped_stem_record("stem_audio", stem.audio_path, exc))
    return records

def _skipped_stem_record(kind: str, path: str, exc: Exception) -> DomainDocument:
    return {
        "kind": kind,
        "path": path,
        "exists": False,
        "required": False,
        "skipped": "unsafe_path",
        "error": str(exc),
    }

def _ensure_within(base: Path, target: Path) -> None:
    base = base.resolve()
    target = target.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside the expected directory.") from exc

def _safe_zip_entry(entry: str) -> str:
    normalized = entry.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if (
        not normalized
        or normalized.startswith("/")
        or normalized.startswith("\\")
        or ".." in parts
        or any(part == "." for part in parts)
        or (parts and ":" in parts[0])
    ):
        raise FinalExportError(f"Unsafe ZIP entry: {entry}.")
    return "/".join(parts)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _optional_str(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()
