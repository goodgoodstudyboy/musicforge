# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path
import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_hub_incidents import TrustOperationsIncidentStore as TrustOperationsIncidentStore, incident_hash as incident_hash
from song_agent.domains.trust.trust_operations_incident_knowledge_contracts import KNOWLEDGE_EXPORT_ENTRIES as KNOWLEDGE_EXPORT_ENTRIES, TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_KNOWLEDGE_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION as TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE, TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE as TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE, _classify_incident as _classify_incident, knowledge_hash as knowledge_hash, knowledge_manifest_hash as knowledge_manifest_hash

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

TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS = _make_deferred_global('TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS')
guard = _make_deferred_global('guard')
item = _make_deferred_global('item')
run = _make_deferred_global('run')

def bind_globals(namespace: dict[str, object]) -> None:
    global TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS, guard, item, run
    TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS = namespace.get('TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS', TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS)
    guard = namespace.get('guard', guard)
    item = namespace.get('item', item)
    run = namespace.get('run', run)
    _bind_deferred_defaults(namespace)






class TrustOperationsKnowledgeError(ValueError):
    pass

class TrustOperationsKnowledgeNotFoundError(TrustOperationsKnowledgeError):
    pass

class TrustOperationsKnowledgeStateError(TrustOperationsKnowledgeError):
    pass

def _knowledge_report_status(base: DomainDocument, guards_doc: DomainDocument, runs_doc: DomainDocument, recurrence: DomainDocument) -> str:
    del base
    guards = _as_list(guards_doc.get("guards"))
    runs = _as_list(runs_doc.get("runs"))
    active_guard_count = sum(1 for guard in guards if isinstance(guard, dict) and guard.get("status") not in {"archived", "manual_required"})
    failed_run_count = sum(1 for run in runs if isinstance(run, dict) and run.get("status") == "failed")
    if recurrence.get("status") == "failed" or failed_run_count:
        return "failed"
    if active_guard_count == 0:
        return "warning"
    return "passed"

def _knowledge_summary(entries: list[DomainDocument], guards: list[DomainDocument], recurrence: DomainDocument | None = None, runs: list[DomainDocument] | None = None) -> DomainDocument:
    recurrence = recurrence or {}
    runs = runs or []
    active_entries = [item for item in entries if item.get("status") != "hidden"]
    return {
        "entry_count": len(entries),
        "active_entry_count": len(active_entries),
        "hidden_entry_count": len(entries) - len(active_entries),
        "high_severity_entry_count": sum(1 for item in active_entries if item.get("severity") in {"critical", "high"}),
        "guard_count": len([item for item in guards if item.get("status") != "archived"]),
        "guards_passed_count": sum(1 for item in runs if item.get("status") == "passed"),
        "guards_failed_count": sum(1 for item in runs if item.get("status") == "failed"),
        "manual_required_guard_count": sum(1 for item in guards if item.get("status") == "manual_required"),
        "recurrence_count": int((_as_document(recurrence.get("summary"))).get("recurrence_count") or 0),
    }

def _entries_summary(entries: list[DomainDocument]) -> DomainDocument:
    return _knowledge_summary(entries, [], {})

def _guards_summary(guards: list[DomainDocument]) -> DomainDocument:
    return {
        "guard_count": len(guards),
        "active_guard_count": sum(1 for item in guards if item.get("status") == "active"),
        "manual_required_guard_count": sum(1 for item in guards if item.get("status") == "manual_required"),
        "archived_guard_count": sum(1 for item in guards if item.get("status") == "archived"),
    }

def _guard_run_summary(runs: list[DomainDocument]) -> DomainDocument:
    return {
        "run_count": len(runs),
        "passed_count": sum(1 for item in runs if item.get("status") == "passed"),
        "failed_count": sum(1 for item in runs if item.get("status") == "failed"),
        "manual_required_count": sum(1 for item in runs if item.get("status") == "manual_required"),
    }

def _incident_matches_entry(incident: DomainDocument, entry: DomainDocument) -> bool:
    detected = _as_document(incident.get("detected_from"))
    return (
        str(detected.get("component_type") or "") == str(entry.get("component_type") or "")
        and str(incident.get("category") or "") == str(entry.get("category") or "")
    )

def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text(
        "MusicForge Trust Operations Incident Knowledge package.\n"
        "This package contains closed incident lessons, regression guards, guard run summaries, and recurrence checks.\n",
        encoding="utf-8",
    )

def _file_record(root: Path, path: Path) -> DomainDocument:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}

def _walk_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return sorted(((path, path.relative_to(root).as_posix()) for path in _walk_files(root)), key=lambda item: item[1])

def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), arcname=entry)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _read_json(path: Path) -> DomainDocument:
    return read_json(path)

def _read_json_default(path: Path, default: DomainDocument | None = None) -> DomainDocument:
    try:
        return _as_document(read_json(path))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {} if default is None else default

def _write_json(path: Path, payload: DomainDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))

def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    max_value = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)")
    for path in root.iterdir():
        match = pattern.match(path.stem if path.is_file() else path.name)
        if match:
            max_value = max(max_value, int(match.group(1)))
    return f"{prefix}-{max_value + 1:06d}"

def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned or "item"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sanitize(payload: object) -> DomainDocument:
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS)

def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
