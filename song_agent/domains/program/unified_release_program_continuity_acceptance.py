# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_int as _as_int, document_or as _document_or

import json as json
import shutil as shutil
import zipfile as zipfile
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
from song_agent.domains.program.unified_release_program_continuity_distribution import UnifiedReleaseProgramContinuityDistributionStore as UnifiedReleaseProgramContinuityDistributionStore
from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_distribution_package as verify_unified_release_program_continuity_distribution_package
from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE, verify_unified_release_program_continuity_acceptance_package as verify_unified_release_program_continuity_acceptance_package, write_unified_release_program_continuity_acceptance_verification_report as write_unified_release_program_continuity_acceptance_verification_report
from song_agent.domains.program.v142_urpca_readiness import UnifiedReleaseProgramContinuityAcceptanceStoreReadinessMixin
from song_agent.domains.program import v142_urpca_readiness as _v142_urpca_readiness
from song_agent.domains.program.v142_urpca_evidence import UnifiedReleaseProgramContinuityAcceptanceStoreEvidenceMixin
from song_agent.domains.program import v142_urpca_evidence as _v142_urpca_evidence
from song_agent.domains.program.v142_urpca_lifecycle import UnifiedReleaseProgramContinuityAcceptanceStoreLifecycleMixin
from song_agent.domains.program import v142_urpca_lifecycle as _v142_urpca_lifecycle



DEFAULT_BOARD_POLICY = {
    "min_accepted_receipts": 2,
    "min_organizations": 2,
    "required_roles": ["recovery_owner", "external_custodian"],
    "block_on_needs_changes": True,
    "block_on_rejected": True,
    "require_current_continuity_distribution_kit": True,
    "require_accepted_evidence": True,
    "allow_synthetic_receiver": False,
}

BLOCKED_RESPONSE_KEYS = {
    "absolute_path",
    "api_key",
    "authorization",
    "file_path",
    "local_path",
    "password",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}


class UnifiedReleaseProgramContinuityAcceptanceError(ValueError):
    pass


class UnifiedReleaseProgramContinuityAcceptanceStateError(UnifiedReleaseProgramContinuityAcceptanceError):
    pass


class UnifiedReleaseProgramContinuityAcceptanceNotFoundError(UnifiedReleaseProgramContinuityAcceptanceError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityAcceptanceStateError)


class UnifiedReleaseProgramContinuityAcceptanceStore(UnifiedReleaseProgramContinuityAcceptanceStoreReadinessMixin, UnifiedReleaseProgramContinuityAcceptanceStoreEvidenceMixin, UnifiedReleaseProgramContinuityAcceptanceStoreLifecycleMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.kit_store = UnifiedReleaseProgramContinuityDistributionStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

















































def _board_policy(value: Any) -> ImplementationDocument:
    raw = _as_document(value)
    return {
        "min_accepted_receipts": _as_int(raw.get("min_accepted_receipts") or raw.get("minimum_acceptances") or DEFAULT_BOARD_POLICY["min_accepted_receipts"]),
        "min_organizations": _as_int(raw.get("min_organizations") or raw.get("minimum_organizations") or DEFAULT_BOARD_POLICY["min_organizations"]),
        "required_roles": [_bounded(role, 80) for role in raw.get("required_roles", DEFAULT_BOARD_POLICY["required_roles"])],
        "block_on_needs_changes": bool(raw.get("block_on_needs_changes", DEFAULT_BOARD_POLICY["block_on_needs_changes"])),
        "block_on_rejected": bool(raw.get("block_on_rejected", DEFAULT_BOARD_POLICY["block_on_rejected"])),
        "require_current_continuity_distribution_kit": bool(raw.get("require_current_continuity_distribution_kit", DEFAULT_BOARD_POLICY["require_current_continuity_distribution_kit"])),
        "require_accepted_evidence": bool(raw.get("require_accepted_evidence", DEFAULT_BOARD_POLICY["require_accepted_evidence"])),
        "allow_synthetic_receiver": bool(raw.get("allow_synthetic_receiver", DEFAULT_BOARD_POLICY["allow_synthetic_receiver"])),
    }


def _decision_readiness(policy: ImplementationDocument, participants: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {row.get("role") for row in accepted}
    orgs = {row.get("organization") for row in accepted}
    required_roles = set(policy.get("required_roles") or [])
    missing_roles = sorted(required_roles - roles)
    blockers: list[str] = []
    if len(accepted) < int(policy.get("min_accepted_receipts") or 2):
        blockers.append("min_accepted_receipts")
    if len(orgs) < int(policy.get("min_organizations") or 2):
        blockers.append("min_organizations")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("receiver_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(orgs), "missing_roles": missing_roles, "blockers": blockers}


def _matrix_rows(participants: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {
            "response_id": row.get("response_id"),
            "evidence_id": row.get("evidence_id"),
            "receiver_id": row.get("receiver_id"),
            "role": row.get("role"),
            "organization": row.get("organization"),
            "decision": row.get("decision"),
            "source": row.get("source"),
            "payload_hash": row.get("payload_hash"),
            "binding_hash": row.get("binding_hash"),
        }
        for row in sorted(participants, key=lambda item: str(item.get("evidence_id") or ""))
    ]


def _receiver_rows(participants: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [{"receiver_id": row.get("receiver_id"), "role": row.get("role"), "organization": row.get("organization"), "decision": row.get("decision"), "response_id": row.get("response_id")} for row in participants]


def _accepted_rows(participants: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [{"evidence_id": row.get("evidence_id"), "response_id": row.get("response_id"), "role": row.get("role"), "organization": row.get("organization"), "decision": row.get("decision"), "binding_hash": row.get("binding_hash")} for row in participants]


def _response_public_projection(response: ImplementationDocument) -> ImplementationDocument:
    return {
        "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
        "package_type": "musicforge_unified_release_program_continuity_acceptance_response_public_projection",
        "program_id": response.get("program_id"),
        "response_id": response.get("response_id"),
        "receiver_id": response.get("receiver_id"),
        "receiver_role": response.get("receiver_role"),
        "organization": response.get("organization"),
        "decision": response.get("decision"),
        "reviewed_at": response.get("reviewed_at"),
        "notes": _bounded(response.get("notes") or "", 1000),
    }


def _response_payload_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key not in {"payload_hash", "integrity_hash", "status", "imported_at"}})


def _package_manifest(package_type: str, program_id: str, files: list[ImplementationDocument], source: ImplementationDocument) -> ImplementationDocument:
    manifest = sanitize_metadata({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": package_type, "program_id": program_id, "created_at": now_iso(), "source": source, "files": sorted(files, key=lambda row: row.get("path") or ""), "zip": {}})
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


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


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _reject_forbidden(payload: ImplementationDocument, label: str) -> None:
    for key, value in payload.items():
        lowered = str(key).lower()
        if lowered in BLOCKED_RESPONSE_KEYS and value:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"{key} is not allowed for {label}.")


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip("-")[:140]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

_v142_urpca_readiness.bind_globals(globals())
_v142_urpca_evidence.bind_globals(globals())
_v142_urpca_lifecycle.bind_globals(globals())
