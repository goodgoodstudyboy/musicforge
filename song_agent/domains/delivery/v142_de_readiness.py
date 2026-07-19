# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import csv as csv
import hashlib as hashlib
import io as io
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, DistributionTarget as DistributionTarget, build_distribution_signoff_record as build_distribution_signoff_record, distribution_signoff_summary as distribution_signoff_summary
from song_agent.domains.delivery.distribution_artwork import distribution_artwork_file_path as distribution_artwork_file_path, latest_distribution_artwork as latest_distribution_artwork, read_distribution_artwork as read_distribution_artwork
from song_agent.domains.delivery.distribution_checklist import checklist_export_payload as checklist_export_payload, checklist_markdown as checklist_markdown, checklist_summary as checklist_summary, reconcile_distribution_checklist as reconcile_distribution_checklist
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS, get_distribution_profile as get_distribution_profile
from song_agent.domains.delivery.distribution_layout import build_distribution_layout_plan as build_distribution_layout_plan, layout_file_tree_text as layout_file_tree_text, layout_manifest_payload as layout_manifest_payload, layout_summary as layout_summary
from song_agent.domains.delivery.distribution_templates import resolve_mapping_source as resolve_mapping_source, template_mapping as template_mapping, template_summary as template_summary
from song_agent.domains.delivery.distribution_qa import distribution_qa_allows_export as distribution_qa_allows_export, distribution_source_state as distribution_source_state
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_export import read_release_export_manifest as read_release_export_manifest
from song_agent.domains.delivery.release_metadata import read_release_metadata as read_release_metadata
from song_agent.domains.delivery.release_qa import scan_release_payload_for_sensitive_values as scan_release_payload_for_sensitive_values
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.quality.audio_encoding import AudioEncodingStore as AudioEncodingStore, resolve_target_audio_format_profiles as resolve_target_audio_format_profiles
from song_agent.domains.creation.encoded_audio_acceptance import export_distribution_encoded_audio_acceptance as export_distribution_encoded_audio_acceptance
from song_agent.domains.delivery.format_decisions import FormatDecisionStore as FormatDecisionStore
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore as RightsClearanceStore

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

DistributionExportError = _make_deferred_global('DistributionExportError')
key = _make_deferred_global('key')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global DistributionExportError, key, part
    DistributionExportError = namespace.get('DistributionExportError', DistributionExportError)
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_EXPORT_SCHEMA_VERSION = 1
DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS = {"export_manifest_hash"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")




def _write_template_platform_csv(export_dir: Path, store: DistributionStore, release_id: str, template: DomainDocument) -> Path | None:
    mapping = template_mapping(template)
    rows = _as_list(mapping.get("platform_csv"))
    if not rows:
        return None
    from song_agent.domains.delivery.release_metadata import read_release_metadata

    metadata = read_release_metadata(store.release_store, release_id, default={})
    tracks = _as_list(metadata.get("tracks"))
    headers = [str(row.get("column") or "") for row in rows if isinstance(row, dict) and row.get("column")]
    if not headers:
        return None
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for track in tracks:
        if not isinstance(track, dict):
            continue
        out: DomainDocument = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            column = str(row.get("column") or "")
            value = resolve_mapping_source(str(row.get("source") or ""), release_metadata=metadata, track_metadata=track)
            out[column] = _escape_csv_cell(str(value or ""))
        writer.writerow(out)
    target = export_dir / "template-platform-metadata.csv"
    target.write_text(buffer.getvalue(), encoding="utf-8")
    return target

def _write_json(path: Path, data: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp-{os.getpid()}-{threading.get_ident()}.json"
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path

def _profile_public(profile_id: str) -> DomainDocument:
    profile = get_distribution_profile(profile_id)
    return {key: profile.get(key) for key in ("profile_id", "name", "description", "profile_hash")}

def _escape_csv_formulas(text: str) -> str:
    reader = csv.reader(io.StringIO(text))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    for row in reader:
        writer.writerow([_escape_csv_cell(cell) for cell in row])
    return buffer.getvalue()

def _escape_csv_cell(cell: str) -> str:
    text = str(cell or "")
    if text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"):
        return "'" + text
    return text

def _distribution_signoff_export_summary(signoff: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "status": signoff.get("status") or "not_signed",
            "signed_at": signoff.get("signed_at"),
            "signed_by": signoff.get("signed_by"),
            "forced": bool(signoff.get("forced", False)),
            "qa_source_hash": signoff.get("qa_source_hash"),
            "export_manifest_hash": signoff.get("export_manifest_hash"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def _distribution_signoff_sidecar_record(signoff_public: DomainDocument) -> DomainDocument:
    return {
        "path": "distribution-signoff.json",
        "payload_hash": stable_hash(_distribution_signoff_hash_payload(signoff_public)),
        "payload_hash_excludes": sorted(DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS),
    }

def _distribution_signoff_hash_payload(signoff_public: DomainDocument) -> DomainDocument:
    return {key: value for key, value in signoff_public.items() if key not in DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}

def _file_record(export_dir: Path, path: Path) -> DomainDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}

def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir, resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir).as_posix())
        if entry in seen:
            raise DistributionExportError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise DistributionExportError("Unsafe relative path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise DistributionExportError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise DistributionExportError("Refusing to operate outside distribution export boundaries.") from exc

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
