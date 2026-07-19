# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_path as _as_path
import hashlib as hashlib
import json as json
import os as os
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
from song_agent.domains.trust.trust_operations_hub_incidents import TrustOperationsIncidentStore as TrustOperationsIncidentStore
from song_agent.domains.trust.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore as TrustOperationsIncidentKnowledgeStore
from song_agent.domains.trust.trust_operations_controls_contracts import BASELINE_CONTROLS as BASELINE_CONTROLS, CONTROL_EXPORT_ENTRIES as CONTROL_EXPORT_ENTRIES, TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_CONTROL_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION as TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION, _blocker_summary as _blocker_summary, _blockers_from_results as _blockers_from_results, _catalog_summary as _catalog_summary, _evaluate_control as _evaluate_control, _expected_control_status as _expected_control_status, _manual_actions_from_blockers as _manual_actions_from_blockers, _results_summary as _results_summary, _safe_id as _safe_id, control_hash as control_hash, control_manifest_hash as control_manifest_hash

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

TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS = _make_deferred_global('TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS')

def bind_globals(namespace: dict[str, object]) -> None:
    global TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS
    TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS = namespace.get('TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS', TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS)
    _bind_deferred_defaults(namespace)






class TrustOperationsControlError(ValueError):
    pass

class TrustOperationsControlNotFoundError(TrustOperationsControlError):
    pass

class TrustOperationsControlStateError(TrustOperationsControlError):
    pass

def _existing_control(catalog: DomainDocument, control_id: str) -> DomainDocument:
    for control in catalog.get("controls", []) if isinstance(catalog.get("controls"), list) else []:
        if isinstance(control, dict) and control.get("control_id") == control_id:
            return control
    return {}

def _current_hub_verification_path(store: TrustOperationsHubStore, hub_id: str) -> Path:
    current = _read_json_default(store.current_report_path(hub_id), default={})
    report_id = str(current.get("report_id") or "")
    return store.verification_report_path(hub_id, report_id) if report_id else Path()

def _optional_path(value: object) -> str | None:
    if not value:
        return None
    return str(Path(value))

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"

def _read_required(path: Path) -> DomainDocument:
    if not path.exists():
        raise TrustOperationsControlNotFoundError(f"Trust Operations Control artifact missing: {path.name}")
    return _read_json(path)

def _read_json(path: Path) -> DomainDocument:
    return read_json(path)

def _read_json_default(path: Path, *, default: DomainDocument) -> DomainDocument:
    try:
        if not path or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)

def _write_json(path: Path, payload: DomainDocument) -> Path:
    return write_json(path, _sanitize(payload))

def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text("MusicForge Trust Operations Controls\n\nThis package contains local preventive control catalog and assessment evidence.\n", encoding="utf-8")

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}

def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]

def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def _sanitize(value: object) -> DomainDocument:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS)

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
