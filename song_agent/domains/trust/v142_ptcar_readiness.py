# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center import PublicTrustCenterStore as PublicTrustCenterStore
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_anchor_registry_contracts import ANCHOR_ENTRY_HASH_EXCLUDE_KEYS as ANCHOR_ENTRY_HASH_EXCLUDE_KEYS, ANCHOR_ENTRY_STATUSES as ANCHOR_ENTRY_STATUSES, ANCHOR_EVENT_HASH_EXCLUDE_KEYS as ANCHOR_EVENT_HASH_EXCLUDE_KEYS, ANCHOR_MANIFEST_HASH_EXCLUDE_KEYS as ANCHOR_MANIFEST_HASH_EXCLUDE_KEYS, ANCHOR_REGISTRY_BLOCKED_KEYS as ANCHOR_REGISTRY_BLOCKED_KEYS, ANCHOR_REGISTRY_HASH_EXCLUDE_KEYS as ANCHOR_REGISTRY_HASH_EXCLUDE_KEYS, ANCHOR_REGISTRY_PACKAGE_TYPE as ANCHOR_REGISTRY_PACKAGE_TYPE, ANCHOR_REPORT_HASH_EXCLUDE_KEYS as ANCHOR_REPORT_HASH_EXCLUDE_KEYS, _current_entry as _current_entry, _find_entry as _find_entry, anchor_entry_hash as anchor_entry_hash, anchor_entry_signature_ok as anchor_entry_signature_ok, anchor_event_hash as anchor_event_hash, anchor_registry_hash as anchor_registry_hash, anchor_registry_manifest_hash as anchor_registry_manifest_hash, anchor_registry_report_hash as anchor_registry_report_hash, anchor_registry_summary as anchor_registry_summary, anchor_registry_verification_summary as anchor_registry_verification_summary

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

ch = _make_deferred_global('ch')
item = _make_deferred_global('item')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, item, key
    ch = namespace.get('ch', ch)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


ANCHOR_REGISTRY_SCHEMA_VERSION = 1
ANCHOR_REGISTRY_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_registry_report"
ANCHOR_DELIVERY_PACKAGE_TYPE = "musicforge_public_trust_center_delivery_anchor"




class PublicTrustCenterAnchorRegistryError(ValueError):
    pass

class PublicTrustCenterAnchorRegistryNotFoundError(PublicTrustCenterAnchorRegistryError):
    pass

class PublicTrustCenterAnchorRegistryStateError(PublicTrustCenterAnchorRegistryError):
    pass

def anchor_registry_integrity_ok(registry: DomainDocument | None) -> bool:
    data = _as_document(registry)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_registry_hash(data)

def anchor_entry_integrity_ok(entry: DomainDocument | None) -> bool:
    data = _as_document(entry)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_entry_hash(data)

def anchor_registry_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_registry_report_hash(data)

def anchor_registry_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_registry_manifest_hash(data)

def build_chain_of_custody(registry: DomainDocument, report: DomainDocument, *, generated_at: str) -> DomainDocument:
    events = [dict(item) for item in registry.get("events", []) if isinstance(item, dict)]
    data = {"schema_version": ANCHOR_REGISTRY_SCHEMA_VERSION, "center_id": registry.get("center_id"), "generated_at": generated_at, "source_hash": report.get("source_hash"), "summary": {"event_count": len(events), "latest_event_type": events[-1].get("event_type") if events else None, "current_entry_id": registry.get("current_entry_id")}, "events": events}
    data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
    return sanitize_metadata(data, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

def _state_tuple(registry: DomainDocument, report: DomainDocument) -> dict[str, str]:
    current = _current_entry(registry)
    return {"registry_hash": str(registry.get("integrity_hash") or ""), "report_hash": str(report.get("integrity_hash") or ""), "current_entry_id": str(registry.get("current_entry_id") or ""), "current_entry_hash": str(current.get("integrity_hash") or "")}

def _manifest_state(manifest: DomainDocument) -> dict[str, str]:
    row = _as_document(manifest.get("registry"))
    report = _as_document(manifest.get("registry_report"))
    return {"registry_hash": str(row.get("integrity_hash") or ""), "report_hash": str(report.get("integrity_hash") or ""), "current_entry_id": str(row.get("current_entry_id") or ""), "current_entry_hash": str(row.get("current_entry_hash") or "")}

def _find_entry_mut(registry: DomainDocument, entry_id: str) -> DomainDocument:
    entry = _find_entry(registry, entry_id)
    if not entry:
        raise PublicTrustCenterAnchorRegistryNotFoundError("Public Trust Center Anchor Registry entry not found.")
    return entry

def _event_chain_ok(registry: DomainDocument) -> bool:
    previous = None
    for event in registry.get("events", []) if isinstance(registry.get("events"), list) else []:
        if not isinstance(event, dict):
            return False
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("event_hash") != anchor_event_hash(event):
            return False
        previous = event.get("event_hash")
    return True

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except Exception:
        return {}

def _write_json(path: Path, payload: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(payload, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS))

def _write_readme(export_dir: Path, registry: DomainDocument, report: DomainDocument) -> None:
    text = (
        "MusicForge Public Trust Center Anchor Registry\n"
        "This package records public delivery anchors for a Public Trust Center ZIP.\n"
        "The local deterministic signature envelope is not a third-party certificate signature.\n"
        "If a ZIP, delivery anchor, and registry package are all replaced together, pure offline verification still needs an external trust anchor.\n"
        f"Center: {registry.get('center_id')}\n"
        f"Status: {report.get('status')}\n"
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")

def _reason(payload: DomainDocument, *, default: str) -> str:
    reason = sanitize_sensitive_text(str(payload.get("reason") or default).strip())
    if len(reason) < 4:
        raise PublicTrustCenterAnchorRegistryStateError("reason must be at least 4 characters.")
    return reason[:1000]

def _safe_text(value: object) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:1000]

def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "").strip())
    return text.strip("-") or "default"

def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PublicTrustCenterAnchorRegistryStateError("Resolved path escapes Anchor Registry directory.") from exc
