# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
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
from song_agent.domains.trust.public_trust_center_anchor_registry import ANCHOR_REGISTRY_BLOCKED_KEYS as ANCHOR_REGISTRY_BLOCKED_KEYS, PublicTrustCenterAnchorRegistryStore as PublicTrustCenterAnchorRegistryStore, anchor_registry_summary as anchor_registry_summary, anchor_registry_verification_summary as anchor_registry_verification_summary
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_anchor_transparency_contracts import ANCHOR_CHECKPOINT_HASH_EXCLUDE_KEYS as ANCHOR_CHECKPOINT_HASH_EXCLUDE_KEYS, ANCHOR_CHECKPOINT_PACKAGE_TYPE as ANCHOR_CHECKPOINT_PACKAGE_TYPE, ANCHOR_TRANSPARENCY_BLOCKED_KEYS as ANCHOR_TRANSPARENCY_BLOCKED_KEYS, ANCHOR_TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS as ANCHOR_TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS, ANCHOR_TRANSPARENCY_HASH_EXCLUDE_KEYS as ANCHOR_TRANSPARENCY_HASH_EXCLUDE_KEYS, ANCHOR_TRANSPARENCY_PACKAGE_TYPE as ANCHOR_TRANSPARENCY_PACKAGE_TYPE, ANCHOR_TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS as ANCHOR_TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS, _checkpoint_payload_hash as _checkpoint_payload_hash, anchor_checkpoint_hash as anchor_checkpoint_hash, anchor_checkpoint_integrity_ok as anchor_checkpoint_integrity_ok, anchor_checkpoint_signature_ok as anchor_checkpoint_signature_ok, anchor_transparency_event_hash as anchor_transparency_event_hash, anchor_transparency_ledger_hash as anchor_transparency_ledger_hash, anchor_transparency_manifest_hash as anchor_transparency_manifest_hash, anchor_transparency_report_hash as anchor_transparency_report_hash, anchor_transparency_summary as anchor_transparency_summary

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

PublicTrustCenterAnchorTransparencyStateError = _make_deferred_global('PublicTrustCenterAnchorTransparencyStateError')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterAnchorTransparencyStateError
    PublicTrustCenterAnchorTransparencyStateError = namespace.get('PublicTrustCenterAnchorTransparencyStateError', PublicTrustCenterAnchorTransparencyStateError)
    _bind_deferred_defaults(namespace)


ANCHOR_TRANSPARENCY_SCHEMA_VERSION = 1
ANCHOR_TRANSPARENCY_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_transparency_report"




def _signature_envelope(payload_hash: str, *, key_id: str) -> DomainDocument:
    signature = {
        "mode": "local_deterministic_checkpoint",
        "key_id": key_id,
        "payload_hash": payload_hash,
    }
    signature["key_fingerprint"] = stable_hash({"key_id": signature["key_id"], "mode": signature["mode"]})
    signature["signature_hash"] = stable_hash(signature)
    return signature

def _event_type_for_state(state: DomainDocument) -> str:
    if state.get("current_entry_status") == "revoked":
        return "anchor_revoked"
    if state.get("current_entry_status") == "published":
        return "anchor_published" if state.get("registry_verification_status") != "passed" else "anchor_registry_verified"
    return "anchor_registered"

def _summary_from_source(source: DomainDocument, blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
    return {
        "center_id": source.get("center_id"),
        "status": "failed" if blockers else "warning" if warnings else "current",
        "event_count": source.get("event_count", 0),
        "latest_sequence": source.get("latest_sequence"),
        "latest_event_hash": source.get("latest_event_hash"),
        "checkpoint_id": source.get("checkpoint_id"),
        "checkpoint_hash": source.get("checkpoint_hash"),
        "current_entry_id": source.get("current_entry_id"),
        "current_anchor_hash": source.get("current_anchor_hash"),
        "current_entry_status": source.get("current_entry_status"),
        "registry_verification_status": source.get("registry_verification_status"),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }

def _registry_verification_summary(report: DomainDocument) -> DomainDocument:
    summary = anchor_registry_verification_summary(_as_document(report))
    return sanitize_metadata(
        {
            "status": report.get("status") if isinstance(report, dict) else "missing",
            "zip_sha256": report.get("zip_sha256") if isinstance(report, dict) else None,
            "zip_size_bytes": report.get("zip_size_bytes") if isinstance(report, dict) else None,
            "manifest_hash": report.get("manifest_hash") if isinstance(report, dict) else None,
            "verification_report_hash": stable_hash(report) if report else None,
            "summary": summary,
        },
        blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS,
    )

def _current_entry_summary(entry: DomainDocument) -> DomainDocument:
    anchor = _as_document(entry.get("anchor"))
    return {
        "entry_id": entry.get("entry_id"),
        "status": entry.get("status"),
        "integrity_hash": entry.get("integrity_hash"),
        "anchor_hash": entry.get("anchor_hash"),
        "ptc_zip_sha256": anchor.get("zip_sha256"),
        "ptc_manifest_hash": anchor.get("manifest_hash"),
        "ptc_source_hash": anchor.get("source_hash"),
    }

def _current_entry(registry: DomainDocument) -> DomainDocument:
    current_id = str(registry.get("current_entry_id") or "")
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == current_id:
            return entry
    return {}

def _event_chain_ok(events: list[DomainDocument]) -> bool:
    previous = None
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            return False
        if event.get("sequence") != index:
            return False
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("event_hash") != anchor_transparency_event_hash(event):
            return False
        previous = event.get("event_hash")
    return True

def source_or_none(report: DomainDocument, key: str) -> object:
    source = _as_document(report.get("source"))
    return source.get(key)

def _state_row(report: DomainDocument) -> dict[str, str]:
    return {
        "source_hash": str(report.get("source_hash") or ""),
        "report_hash": str(report.get("integrity_hash") or ""),
        "latest_event_hash": str(source_or_none(report, "latest_event_hash") or ""),
        "checkpoint_hash": str(source_or_none(report, "checkpoint_hash") or ""),
    }

def _manifest_state(manifest: DomainDocument) -> dict[str, str]:
    report = _as_document(manifest.get("report"))
    ledger = _as_document(manifest.get("ledger"))
    checkpoint = _as_document(manifest.get("checkpoint"))
    return {
        "source_hash": str(manifest.get("source_hash") or ""),
        "report_hash": str(report.get("integrity_hash") or ""),
        "latest_event_hash": str(ledger.get("latest_event_hash") or ""),
        "checkpoint_hash": str(checkpoint.get("integrity_hash") or ""),
    }

def _ledger_text(events: list[DomainDocument]) -> str:
    return "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events)

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
    return write_json(Path(path), sanitize_metadata(payload, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS))

def _write_readme(export_dir: Path, report: DomainDocument) -> None:
    text = (
        "MusicForge Public Trust Center Anchor Transparency\n"
        "This package records an append-only local transparency ledger for Public Trust Center Anchor Registry states.\n"
        "External checkpoint files are the portable trust anchor for detecting whole-package replacement.\n"
        f"Center: {report.get('center_id')}\n"
        f"Status: {report.get('status')}\n"
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")

def _safe_text(value: object) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:1000]

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
        raise PublicTrustCenterAnchorTransparencyStateError("Resolved path escapes Anchor Transparency directory.") from exc
