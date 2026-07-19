# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.coercion import as_list as _as_list
from song_agent.platform.contracts.documents import DomainDocument
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore as UnifiedCommandCenterReleaseTrainStore
from song_agent.domains.program.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore as UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package as verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, verify_unified_command_center_release_train_lifecycle_package as verify_unified_command_center_release_train_lifecycle_package, write_unified_command_center_release_train_lifecycle_verification_report as write_unified_command_center_release_train_lifecycle_verification_report
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package

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

key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global key, value
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)






def _gap_items(readiness: DomainDocument, coverage: DomainDocument, has_reset: bool, change_summary: DomainDocument) -> list[DomainDocument]:
    gaps = []
    for index, check in enumerate(readiness.get("checks", []), start=1):
        if check.get("status") != "passed":
            gaps.append({"gap_id": f"gap-{index:03d}", "severity": "blocking", "category": check.get("check_id"), "message": f"{check.get('check_id')} failed.", "recommended_action": "Refresh required train lifecycle evidence and rebuild lifecycle audit."})
    if has_reset and not change_summary.get("configured"):
        gaps.append({"gap_id": "gap-change-control", "severity": "blocking", "category": "change_control", "message": "Release Train has reset history but Change Control evidence is missing.", "recommended_action": "Export and verify Change Control package with reset proof."})
    for row in coverage.get("items", []):
        if row.get("status") != "passed":
            gaps.append({"gap_id": f"gap-reset-{row.get('change_request_id')}", "severity": "blocking", "category": "reset_coverage", "message": "Reset coverage is incomplete.", "recommended_action": "Provide reset proof and archive-history evidence."})
    return gaps

def _evidence_index_doc(train_id: str, source_hash: str, train_summary: DomainDocument, change_summary: DomainDocument, reset_proofs: list[DomainDocument]) -> DomainDocument:
    items = [
        {"evidence_type": "current_train", **{key: train_summary.get(key) for key in ("zip_sha256", "manifest_hash", "verification_report_hash", "signoff_binding_hash", "external_evidence_manifest_hash", "runtime_status")}},
    ]
    if change_summary.get("configured"):
        items.append({"evidence_type": "change_control", **{key: change_summary.get(key) for key in ("zip_sha256", "manifest_hash", "verification_report_hash", "runtime_status", "applied_reset_count")}})
    for proof in reset_proofs:
        items.append({"evidence_type": "reset_proof", "change_request_id": proof.get("change_request_id"), "reset_proof_hash": proof.get("reset_proof_hash"), "reset_event_hash": proof.get("reset_event_hash")})
    return {"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_lifecycle_evidence_fingerprint_index", "train_id": train_id, "source_hash": source_hash, "items": sanitize_metadata(items), "summary": {"item_count": len(items)}}

def _lifecycle_event_type(event_type: str) -> str:
    mapping = {
        "ucc_release_train_signoff_created": "train_signoff_created",
        "ucc_release_train_archive_exported": "train_archive_exported",
        "ucc_release_train_archive_built": "train_archive_built",
        "ucc_release_train_signoff_reset": "train_signoff_reset",
        "train_change_request_submitted": "train_change_request_submitted",
        "train_change_request_approved": "train_change_request_approved",
        "train_change_request_reset_applied": "train_change_request_reset_applied",
    }
    return mapping.get(event_type, event_type or "unknown")

def _manifest_document(train_id: str, docs: DomainDocument, files: list[DomainDocument]) -> DomainDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE,
            "train_id": train_id,
            "created_at": now_iso(),
            "source_hash": docs["report"].get("source_hash"),
            "source": {
                "report_hash": docs["report"].get("integrity_hash"),
                "succession_hash": docs["succession"].get("integrity_hash"),
                "coverage_hash": docs["coverage"].get("integrity_hash"),
                "archive_history_hash": docs["archive_history"].get("integrity_hash"),
                "readiness_hash": docs["readiness"].get("integrity_hash"),
                "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
                "evidence_index_hash": docs["evidence_index"].get("integrity_hash"),
                "ledger_hash": stable_hash(docs["ledger"]),
            },
            "summary": docs["report"].get("summary", {}),
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest

def _reviewer_guide(docs: DomainDocument) -> str:
    summary = docs["report"].get("summary", {})
    return "\n".join(
        [
            "# Release Train Lifecycle Audit",
            "",
            f"Status: {docs['report'].get('status')}",
            f"Signoffs: {summary.get('signoff_count')}",
            f"Resets: {summary.get('reset_count')}",
            "",
            "Use the offline verifier with the current Release Train archive, Change Control package, signoff binding, external evidence manifest, and reset proof files.",
            "",
        ]
    )

def _with_integrity(doc: DomainDocument) -> DomainDocument:
    doc = sanitize_metadata(doc)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
