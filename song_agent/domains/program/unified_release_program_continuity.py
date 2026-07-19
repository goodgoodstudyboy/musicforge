# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import shutil as shutil
import tempfile as tempfile
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
from song_agent.domains.program.unified_release_program_continuity_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION, verify_unified_release_program_continuity_package as verify_unified_release_program_continuity_package, write_unified_release_program_continuity_verification_report as write_unified_release_program_continuity_verification_report
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore as UnifiedReleaseProgramVaultOperationsStore
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package
from song_agent.domains.program.v142_urpc_readiness import UnifiedReleaseProgramContinuityStoreReadinessMixin
from song_agent.domains.program import v142_urpc_readiness as _v142_urpc_readiness
from song_agent.domains.program.v142_urpc_evidence import UnifiedReleaseProgramContinuityStoreEvidenceMixin
from song_agent.domains.program import v142_urpc_evidence as _v142_urpc_evidence



CONTINUITY_BLOCKED_METADATA_KEYS = {
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


class UnifiedReleaseProgramContinuityError(ValueError):
    pass


class UnifiedReleaseProgramContinuityNotFoundError(UnifiedReleaseProgramContinuityError):
    pass


class UnifiedReleaseProgramContinuityStateError(UnifiedReleaseProgramContinuityError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityStateError)


class UnifiedReleaseProgramContinuityStore(UnifiedReleaseProgramContinuityStoreReadinessMixin, UnifiedReleaseProgramContinuityStoreEvidenceMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.vault_operations_store = UnifiedReleaseProgramVaultOperationsStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

















































def _source_binding_from_context(context: ImplementationDocument) -> ImplementationDocument:
    return {
        "vault_operations_archive_sha256": _sha256_path(context["archive_path"]),
        "vault_operations_archive_size_bytes": context["archive_path"].stat().st_size if context["archive_path"].exists() else None,
        "vault_operations_manifest_hash": context["runtime"].get("manifest_hash"),
        "vault_operations_verification_report_hash": context["external"].get("integrity_hash"),
        "vault_operations_runtime_verification_hash": context["runtime"].get("integrity_hash"),
        "vault_operations_signoff_binding_hash": context["signoff_binding"].get("integrity_hash"),
        "vault_operations_signoff_hash": context["signoff_binding"].get("signoff_hash"),
    }


def _signoff_binding_document(program_id: str, signoff: ImplementationDocument, event: ImplementationDocument, policy: ImplementationDocument, plan: ImplementationDocument, drill: ImplementationDocument, readiness: ImplementationDocument, runbook: ImplementationDocument, report: ImplementationDocument, evidence_manifest: ImplementationDocument) -> ImplementationDocument:
    source = {key: signoff.get(key) for key in signoff if key.startswith("vault_operations_")}
    return _with_integrity(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_continuity_signoff_binding_summary",
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
            "policy_hash": policy.get("integrity_hash"),
            "recovery_plan_hash": plan.get("integrity_hash"),
            "drill_report_hash": drill.get("integrity_hash"),
            "readiness_hash": readiness.get("integrity_hash"),
            "runbook_hash": runbook.get("integrity_hash"),
            "continuity_report_hash": report.get("integrity_hash"),
            "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
            **source,
        }
    )


def _archive_manifest_document(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    source = {
        "policy_hash": docs["policy"].get("integrity_hash"),
        "recovery_plan_hash": docs["plan"].get("integrity_hash"),
        "drill_report_hash": docs["drill"].get("integrity_hash"),
        "readiness_hash": docs["readiness"].get("integrity_hash"),
        "runbook_hash": docs["runbook"].get("integrity_hash"),
        "continuity_report_hash": docs["report"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["evidence_manifest"].get("integrity_hash"),
        "signoff_hash": docs["signoff"].get("integrity_hash"),
        "signoff_binding_hash": docs["binding"].get("integrity_hash"),
        "vault_operations_archive_sha256": docs["binding"].get("vault_operations_archive_sha256"),
        "vault_operations_archive_size_bytes": docs["binding"].get("vault_operations_archive_size_bytes"),
        "vault_operations_manifest_hash": docs["binding"].get("vault_operations_manifest_hash"),
        "vault_operations_verification_report_hash": docs["binding"].get("vault_operations_verification_report_hash"),
        "vault_operations_signoff_binding_hash": docs["binding"].get("vault_operations_signoff_binding_hash"),
    }
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=CONTINUITY_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _read_required_doc(path: Path, label: str) -> ImplementationDocument:
    if not path.exists():
        raise UnifiedReleaseProgramContinuityNotFoundError(f"{label} is missing.")
    doc = read_json(path)
    if not _integrity_ok(doc):
        raise UnifiedReleaseProgramContinuityStateError(f"{label} integrity failed.")
    return doc


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
            raise UnifiedReleaseProgramContinuityStateError(f"{forbidden} is not allowed for Continuity.")
    return payload


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(
        sanitize_metadata(doc, blocked_keys=CONTINUITY_BLOCKED_METADATA_KEYS),
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

_v142_urpc_readiness.bind_globals(globals())
_v142_urpc_evidence.bind_globals(globals())
