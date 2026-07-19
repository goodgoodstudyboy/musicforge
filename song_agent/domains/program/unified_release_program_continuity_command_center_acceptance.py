# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list

import base64 as base64
import hashlib as hashlib
import io as io
import json as json
import os as os
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import ACCEPTED_EVIDENCE_ENTRIES as ACCEPTED_EVIDENCE_ENTRIES, ACCEPTED_EVIDENCE_PACKAGE_TYPE as ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE as ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, ARCHIVE_ENTRIES as ARCHIVE_ENTRIES, ARCHIVE_PACKAGE_TYPE as ARCHIVE_PACKAGE_TYPE, ARCHIVE_VERIFICATION_PACKAGE_TYPE as ARCHIVE_VERIFICATION_PACKAGE_TYPE, BOARD_REPORT_PACKAGE_TYPE as BOARD_REPORT_PACKAGE_TYPE, RESPONSE_PACKAGE_TYPE as RESPONSE_PACKAGE_TYPE, RESPONSE_VERIFICATION_PACKAGE_TYPE as RESPONSE_VERIFICATION_PACKAGE_TYPE, REVIEW_PACK_ENTRIES as REVIEW_PACK_ENTRIES, REVIEW_PACK_PACKAGE_TYPE as REVIEW_PACK_PACKAGE_TYPE, REVIEW_PACK_VERIFICATION_PACKAGE_TYPE as REVIEW_PACK_VERIFICATION_PACKAGE_TYPE, SCHEMA_VERSION as SCHEMA_VERSION, SIGNOFF_BINDING_PACKAGE_TYPE as SIGNOFF_BINDING_PACKAGE_TYPE, SIGNOFF_PACKAGE_TYPE as SIGNOFF_PACKAGE_TYPE, validate_response_proof as validate_response_proof, verify_accepted_evidence as verify_accepted_evidence, verify_review_pack as verify_review_pack, verify_unified_release_program_continuity_command_center_acceptance_package as verify_unified_release_program_continuity_command_center_acceptance_package, write_verification_report as write_verification_report
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff import UnifiedReleaseProgramContinuityCommandCenterSignoffStore as UnifiedReleaseProgramContinuityCommandCenterSignoffStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package
from song_agent.domains.program.v142_urpccca_readiness import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreReadinessMixin
from song_agent.domains.program import v142_urpccca_readiness as _v142_urpccca_readiness
from song_agent.domains.program.v142_urpccca_evidence import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreEvidenceMixin
from song_agent.domains.program import v142_urpccca_evidence as _v142_urpccca_evidence
from song_agent.domains.program.v142_urpccca_lifecycle import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreLifecycleMixin
from song_agent.domains.program import v142_urpccca_lifecycle as _v142_urpccca_lifecycle
from song_agent.domains.program.v142_urpccca_archive import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreArchiveMixin
from song_agent.domains.program import v142_urpccca_archive as _v142_urpccca_archive


DEFAULT_POLICY = {
    "min_accepted_count": 2,
    "min_organization_count": 2,
    "required_roles": ["continuity_owner", "operations_owner"],
    "block_on_rejected": True,
    "block_on_needs_changes": True,
    "block_on_critical_findings": True,
}

BLOCKED_INPUT_KEYS = {
    "absolute_path",
    "api_key",
    "authorization",
    "file_path",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceError(ValueError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError
):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError(
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError
):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError)


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreReadinessMixin, UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreEvidenceMixin, UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreLifecycleMixin, UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreArchiveMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.signoff_store = UnifiedReleaseProgramContinuityCommandCenterSignoffStore(self.program_store)
        self.root = self.program_store.root.parent / "urpccca"
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write", on_commit=lambda: sync_active_v12_state(self.program_store.root.parent))








































































def _response_payload_documents(payload: ImplementationDocument) -> tuple[ImplementationDocument, ImplementationDocument, ImplementationDocument]:
    _reject_forbidden(payload, "Receiver response import")
    if payload.get("response_zip_base64"):
        try:
            data = base64.b64decode(str(payload["response_zip_base64"]), validate=True)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = [item.filename for item in archive.infolist()]
                expected = {"response.json", "response-verification-report.json", "response-binding-summary.json"}
                if set(names) != expected or len(names) != len(expected):
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response ZIP must contain the fixed proof entries.")
                return tuple(json.loads(archive.read(name).decode("utf-8")) for name in ("response.json", "response-verification-report.json", "response-binding-summary.json"))
        except (ValueError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response ZIP is invalid.") from exc
    if payload.get("response_base64"):
        try:
            wrapper = json.loads(base64.b64decode(str(payload["response_base64"]), validate=True).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response base64 JSON is invalid.") from exc
        payload = _as_document(wrapper)
    response = payload.get("response") or payload.get("response_json")
    verification = payload.get("response_verification_report")
    binding = payload.get("response_binding_summary")
    if not all(isinstance(value, dict) for value in (response, verification, binding)):
        raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
            "Receiver response requires external response, verification report, and binding summary."
        )
    return _as_document(response), _as_document(verification), _as_document(binding)


def _policy(value: Any) -> ImplementationDocument:
    incoming = _as_document(value)
    return {
        "min_accepted_count": max(1, _as_int(incoming.get("min_accepted_count") or DEFAULT_POLICY["min_accepted_count"])),
        "min_organization_count": max(1, _as_int(incoming.get("min_organization_count") or DEFAULT_POLICY["min_organization_count"])),
        "required_roles": sorted({_bounded(role, 80) for role in _as_list(incoming.get("required_roles") or DEFAULT_POLICY["required_roles"]) if str(role).strip()}),
        "block_on_rejected": bool(incoming.get("block_on_rejected", DEFAULT_POLICY["block_on_rejected"])),
        "block_on_needs_changes": bool(incoming.get("block_on_needs_changes", DEFAULT_POLICY["block_on_needs_changes"])),
        "block_on_critical_findings": bool(incoming.get("block_on_critical_findings", DEFAULT_POLICY["block_on_critical_findings"])),
    }


def _quorum_summary(policy: ImplementationDocument, participants: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {str(row.get("role") or "") for row in accepted}
    organizations = {str(row.get("organization") or "") for row in accepted}
    missing_roles = sorted(set(policy.get("required_roles") or []) - roles)
    blockers: list[str] = []
    if len(accepted) < int(policy.get("min_accepted_count") or 2):
        blockers.append("min_accepted_count")
    if len(organizations) < int(policy.get("min_organization_count") or 2):
        blockers.append("min_organization_count")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("receiver_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(organizations), "required_roles": sorted(policy.get("required_roles") or []), "missing_roles": missing_roles, "blockers": blockers}


def _findings_rows(responses: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    for response_id, bundle in sorted(responses.items()):
        for index, finding in enumerate(bundle["response"].get("findings") or [], start=1):
            if not isinstance(finding, dict):
                continue
            rows.append({"response_id": response_id, "finding_id": str(finding.get("finding_id") or f"finding-{index:03d}"), "severity": str(finding.get("severity") or "info").lower(), "category": _bounded(finding.get("category") or "general", 120), "summary": _bounded(finding.get("summary") or "", 500), "finding_hash": stable_hash(finding)})
    return rows


def _response_public_projection(response: ImplementationDocument) -> ImplementationDocument:
    return {"schema_version": SCHEMA_VERSION, "package_type": f"{RESPONSE_PACKAGE_TYPE}_public_projection", "program_id": response.get("program_id"), "response_id": response.get("response_id"), "reviewer": response.get("reviewer"), "organization": response.get("organization"), "role": response.get("role"), "decision": response.get("decision"), "findings": response.get("findings") or [], "created_at": response.get("created_at")}


def _manifest(package_type: str, program_id: str, docs: ImplementationDocument, source: ImplementationDocument, required: set[str]) -> ImplementationDocument:
    files = []
    for rel in sorted(required - {"manifest.json"}):
        data = _serialize(docs[rel])
        files.append({"path": rel, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": package_type, "program_id": program_id, "source": source, "files": files, "zip": {"entries": sorted(required)}})


def _build_zip_from_values(path: Path, docs: ImplementationDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ArchiveBuilder.build_payload_zip(path, {rel: _serialize(value) for rel, value in docs.items()})


def _build_zip_from_dir(root: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ArchiveBuilder.build_directory_zip(root, path)


def _serialize(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.replace("\n", os.linesep).encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(doc, payload_hash=False)


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_result(path: Path, report: ImplementationDocument) -> ImplementationDocument:
    return {"status": "passed", "zip_path": str(path), "zip_sha256": _sha256_path(path), "zip_size_bytes": path.stat().st_size, "manifest_hash": report.get("manifest_hash")}


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.is_file():
        return {}
    try:
        return read_json(path)
    except (OSError, ValueError):
        return {}


def _reject_forbidden(value: Any, label: str) -> None:
    if isinstance(value, dict):
        forbidden = sorted(str(key) for key in value if str(key).lower() in BLOCKED_INPUT_KEYS)
        if forbidden:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"{label} contains forbidden path or secret fields: {', '.join(forbidden)}")
        for child in value.values():
            _reject_forbidden(child, label)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden(child, label)


def _reject_sensitive_mutation(value: ImplementationDocument, label: str) -> None:
    if sanitize_metadata(value) != value:
        raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"{label} contains sensitive or local-path content.")


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

_v142_urpccca_readiness.bind_globals(globals())
_v142_urpccca_evidence.bind_globals(globals())
_v142_urpccca_lifecycle.bind_globals(globals())
_v142_urpccca_archive.bind_globals(globals())
