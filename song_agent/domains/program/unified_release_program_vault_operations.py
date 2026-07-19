# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import shutil as shutil
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore as UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package as verify_unified_release_program_vault_package
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package, write_unified_release_program_vault_operations_verification_report as write_unified_release_program_vault_operations_verification_report
from song_agent.domains.program.v142_urpvo_readiness import UnifiedReleaseProgramVaultOperationsStoreReadinessMixin
from song_agent.domains.program import v142_urpvo_readiness as _v142_urpvo_readiness
from song_agent.domains.program.v142_urpvo_evidence import UnifiedReleaseProgramVaultOperationsStoreEvidenceMixin
from song_agent.domains.program import v142_urpvo_evidence as _v142_urpvo_evidence



VAULT_OPERATIONS_BLOCKED_METADATA_KEYS = {
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


class UnifiedReleaseProgramVaultOperationsError(ValueError):
    pass


class UnifiedReleaseProgramVaultOperationsNotFoundError(UnifiedReleaseProgramVaultOperationsError):
    pass


class UnifiedReleaseProgramVaultOperationsStateError(UnifiedReleaseProgramVaultOperationsError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramVaultOperationsStateError)


class UnifiedReleaseProgramVaultOperationsStore(UnifiedReleaseProgramVaultOperationsStoreReadinessMixin, UnifiedReleaseProgramVaultOperationsStoreEvidenceMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.vault_store = UnifiedReleaseProgramVaultStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")


















































def _signoff_binding_document(program_id: str, signoff: ImplementationDocument, event: ImplementationDocument, report: ImplementationDocument, registry: ImplementationDocument, policy: ImplementationDocument, review: ImplementationDocument, transfer: ImplementationDocument) -> ImplementationDocument:
    current = next((row for row in registry.get("generations", []) if isinstance(row, dict) and row.get("generation_id") == registry.get("current_generation_id")), {})
    vault = _as_document(current.get("vault"))
    return _with_integrity(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_vault_operations_signoff_binding_summary",
            "program_id": program_id,
            "status": "signed",
            "signed_by": signoff.get("signed_by"),
            "role": signoff.get("role"),
            "reason": signoff.get("reason"),
            "signed_at": signoff.get("signed_at"),
            "signoff_hash": signoff.get("integrity_hash"),
            "signoff_payload_hash": signoff.get("payload_hash"),
            "latest_history_event_hash": event.get("event_hash"),
            "latest_history_payload_hash": event.get("payload_hash"),
            "report_hash": report.get("integrity_hash"),
            "registry_hash": registry.get("integrity_hash"),
            "policy_hash": policy.get("integrity_hash"),
            "latest_review_hash": review.get("integrity_hash"),
            "transfer_report_hash": transfer.get("integrity_hash"),
            "current_generation_id": registry.get("current_generation_id"),
            "vault_zip_sha256": vault.get("vault_zip_sha256"),
            "vault_zip_size_bytes": vault.get("vault_zip_size_bytes"),
            "vault_manifest_hash": vault.get("vault_manifest_hash"),
            "vault_anchor_hash": vault.get("vault_anchor_hash"),
            "vault_verification_report_hash": vault.get("vault_verification_report_hash"),
        }
    )


def _archive_manifest_document(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    source = {
        "report_hash": docs["report"].get("integrity_hash"),
        "registry_hash": docs["registry"].get("integrity_hash"),
        "policy_hash": docs["policy"].get("integrity_hash"),
        "latest_review_hash": docs["review"].get("integrity_hash"),
        "rotation_plan_hash": docs["rotation"].get("integrity_hash"),
        "transfer_report_hash": docs["transfer"].get("integrity_hash"),
        "signoff_hash": docs["signoff"].get("integrity_hash"),
        "signoff_binding_hash": docs["binding"].get("integrity_hash"),
        "vault_zip_sha256": docs["current_vault"].get("vault_zip_sha256"),
        "vault_anchor_hash": docs["current_vault"].get("vault_anchor_hash"),
        "vault_verification_report_hash": docs["current_vault"].get("vault_verification_report_hash"),
    }
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=VAULT_OPERATIONS_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _recipient_guide(program_id: str, transfer: ImplementationDocument) -> str:
    return "\n".join(
        [
            "# Unified Release Program Vault Transfer",
            "",
            f"Program: {program_id}",
            f"Transfer: {transfer.get('transfer_id') or 'pending'}",
            "",
            "Verify the Vault Operations Archive before storing or mirroring the Vault.",
            "",
        ]
    )


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _read_history(path: Path) -> list[ImplementationDocument]:
    return HistoryChain(path).read()


def _json_line(doc: ImplementationDocument) -> str:
    import json

    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sanitize_payload(payload: ImplementationDocument) -> ImplementationDocument:
    for forbidden in ("source_path", "local_path", "file_path"):
        if payload.get(forbidden):
            raise UnifiedReleaseProgramVaultOperationsStateError(f"{forbidden} is not allowed for Vault Operations.")
    return payload


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(
        sanitize_metadata(doc, blocked_keys=VAULT_OPERATIONS_BLOCKED_METADATA_KEYS),
        payload_hash=False,
    )


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
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


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _safe_id(value: str) -> str:
    import re

    value = sanitize_sensitive_text(str(value or "")).strip()
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value[:120] or "item"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

_v142_urpvo_readiness.bind_globals(globals())
_v142_urpvo_evidence.bind_globals(globals())
