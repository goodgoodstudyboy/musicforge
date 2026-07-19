# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_handoff import UnifiedReleaseProgramHandoffStore as UnifiedReleaseProgramHandoffStore
from song_agent.domains.program.unified_release_program_operations import UnifiedReleaseProgramOperationsStore as UnifiedReleaseProgramOperationsStore
from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, verify_unified_release_program_vault_package as verify_unified_release_program_vault_package, write_unified_release_program_vault_verification_report as write_unified_release_program_vault_verification_report

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

UnifiedReleaseProgramVaultStateError = _make_deferred_global('UnifiedReleaseProgramVaultStateError')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramVaultStateError, key, read_json, value
    UnifiedReleaseProgramVaultStateError = namespace.get('UnifiedReleaseProgramVaultStateError', UnifiedReleaseProgramVaultStateError)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


VAULT_BLOCKED_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}




def _manifest_document(program_id: str, docs: DomainDocument, files: list[DomainDocument]) -> DomainDocument:
    source = {
        "vault_report_hash": docs["report"].get("integrity_hash"),
        "source_summary_hash": docs["source"].get("integrity_hash"),
        "package_index_hash": docs["package_index"].get("integrity_hash"),
        "verification_index_hash": docs["verification_index"].get("integrity_hash"),
        "proof_index_hash": docs["proof_index"].get("integrity_hash"),
        "chain_of_custody_hash": docs["chain"].get("integrity_hash"),
        "public_summary_hash": docs["public_summary"].get("integrity_hash"),
        "replay_plan_hash": docs["replay_plan"].get("integrity_hash"),
    }
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE,
            "program_id": program_id,
            "vault_id": docs["report"].get("vault_id"),
            "created_at": now_iso(),
            "source_hash": docs["source"].get("source_hash"),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=VAULT_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest

def _anchor_document(program_id: str, zip_path: Path, manifest: DomainDocument, docs: DomainDocument) -> DomainDocument:
    anchor = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE,
            "program_id": program_id,
            "vault_id": docs["report"].get("vault_id"),
            "created_at": now_iso(),
            "vault_zip_sha256": _sha256_path(zip_path),
            "vault_zip_size_bytes": zip_path.stat().st_size,
            "vault_manifest_hash": manifest.get("integrity_hash"),
            "vault_source_hash": docs["source"].get("source_hash"),
            "vault_report_hash": docs["report"].get("integrity_hash"),
            "package_index_hash": docs["package_index"].get("integrity_hash"),
            "verification_index_hash": docs["verification_index"].get("integrity_hash"),
            "proof_index_hash": docs["proof_index"].get("integrity_hash"),
            "chain_of_custody_hash": docs["chain"].get("integrity_hash"),
        },
        blocked_keys=VAULT_BLOCKED_METADATA_KEYS,
    )
    anchor["integrity_hash"] = _integrity_hash(anchor)
    return anchor

def _chain_events(program_id: str, packages: list[DomainDocument], verifications: list[DomainDocument], proofs: list[DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    previous = ""
    for index, row in enumerate(packages + verifications + proofs, start=1):
        event = HistoryChain.build_event(
            {"event_index": index, "program_id": program_id, "event_type": f"vault_{row.get('component_type')}_{'indexed'}", "component_type": row.get("component_type"), "component_id": row.get("component_id"), "path": row.get("path")},
            previous_event_hash=previous,
        )
        previous = event["event_hash"]
        rows.append(event)
    return rows

def _replay_steps(packages: list[DomainDocument], verifications: list[DomainDocument], proofs: list[DomainDocument]) -> list[DomainDocument]:
    return [
        {"step": "verify_package_index", "package_count": len(packages)},
        {"step": "verify_verification_index", "verification_count": len(verifications)},
        {"step": "verify_proof_index", "proof_count": len(proofs)},
        {"step": "deep_verify_program_operations_handoff", "status": "required"},
        {"step": "deep_verify_accepted_evidence", "status": "required"},
    ]

def _auditor_guide(docs: DomainDocument) -> str:
    summary = docs["report"].get("summary", {})
    return "\n".join(
        [
            "# Unified Release Program Evidence Vault",
            "",
            f"Status: {docs['report'].get('status')}",
            f"Packages: {summary.get('package_count')}",
            f"Verifications: {summary.get('verification_count')}",
            "",
            "Run the verifier with --deep and the external vault-anchor.json before relying on this package.",
            "",
        ]
    )

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _public_row(row: DomainDocument) -> DomainDocument:
    return {key: value for key, value in row.items() if key not in {"source_path"}}

def _with_integrity(doc: DomainDocument) -> DomainDocument:
    doc = sanitize_metadata(doc, blocked_keys=VAULT_BLOCKED_METADATA_KEYS)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _integrity_hash(doc: DomainDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})

def _integrity_ok(doc: DomainDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)

def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()

def _json_bytes(doc: DomainDocument) -> bytes:
    import json
    import os

    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if os.linesep != "\n":
        text = text.replace("\n", os.linesep)
    return text.encode("utf-8")

def _read_optional_json(path: Path) -> DomainDocument:
    if not path.exists():
        return {}
    return read_json(path)

def _sanitize_payload(payload: DomainDocument) -> DomainDocument:
    for forbidden in ("source_path", "local_path", "file_path"):
        if payload.get(forbidden):
            raise UnifiedReleaseProgramVaultStateError(f"{forbidden} is not allowed for Vault operations.")
    return payload

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
