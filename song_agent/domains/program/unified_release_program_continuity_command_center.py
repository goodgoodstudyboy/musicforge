# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import shutil as shutil
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity import UnifiedReleaseProgramContinuityStore as UnifiedReleaseProgramContinuityStore
from song_agent.domains.program.unified_release_program_continuity_acceptance import UnifiedReleaseProgramContinuityAcceptanceStore as UnifiedReleaseProgramContinuityAcceptanceStore, _file_record as _file_record, _gate_failed as _gate_failed, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _package_manifest as _package_manifest, _read_optional_json as _read_optional_json, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_acceptance_change import UnifiedReleaseProgramContinuityAcceptanceChangeStore as UnifiedReleaseProgramContinuityAcceptanceChangeStore
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import EXPECTED_VERIFICATION_TYPES as EXPECTED_VERIFICATION_TYPES, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, runtime_verify_continuity_command_center_component as runtime_verify_continuity_command_center_component, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package, write_unified_release_program_continuity_command_center_verification_report as write_unified_release_program_continuity_command_center_verification_report
from song_agent.domains.program.unified_release_program_continuity_distribution import UnifiedReleaseProgramContinuityDistributionStore as UnifiedReleaseProgramContinuityDistributionStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore as UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore as UnifiedReleaseProgramVaultOperationsStore
from song_agent.domains.program.v142_urpccc_readiness import UnifiedReleaseProgramContinuityCommandCenterStoreReadinessMixin
from song_agent.domains.program import v142_urpccc_readiness as _v142_urpccc_readiness
from song_agent.domains.program.v142_urpccc_evidence import UnifiedReleaseProgramContinuityCommandCenterStoreEvidenceMixin
from song_agent.domains.program import v142_urpccc_evidence as _v142_urpccc_evidence



COMMAND_CENTER_COMPONENTS = (
    "evidence_vault",
    "vault_operations",
    "continuity_recovery",
    "continuity_distribution_kit",
    "continuity_acceptance_board",
    "continuity_acceptance_change_control",
)


class UnifiedReleaseProgramContinuityCommandCenterError(ValueError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterStateError(UnifiedReleaseProgramContinuityCommandCenterError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityCommandCenterStateError)


class UnifiedReleaseProgramContinuityCommandCenterStore(UnifiedReleaseProgramContinuityCommandCenterStoreReadinessMixin, UnifiedReleaseProgramContinuityCommandCenterStoreEvidenceMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.vault_store = UnifiedReleaseProgramVaultStore(self.program_store)
        self.vault_operations_store = UnifiedReleaseProgramVaultOperationsStore(self.program_store)
        self.continuity_store = UnifiedReleaseProgramContinuityStore(self.program_store)
        self.distribution_store = UnifiedReleaseProgramContinuityDistributionStore(self.program_store)
        self.acceptance_store = UnifiedReleaseProgramContinuityAcceptanceStore(self.program_store)
        self.change_store = UnifiedReleaseProgramContinuityAcceptanceChangeStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write", on_commit=lambda: sync_active_v12_state(self.program_store.root.parent))


























def _runtime_fingerprint(runtime: ImplementationDocument) -> ImplementationDocument:
    verification = _as_document(runtime.get("verification"))
    summary = _as_document(runtime.get("summary"))
    verification_summary = _as_document(verification.get("summary"))
    return {
        "zip_sha256": runtime.get("zip_sha256") or verification.get("zip_sha256") or summary.get("zip_sha256") or verification_summary.get("zip_sha256"),
        "zip_size_bytes": runtime.get("zip_size_bytes") or verification.get("zip_size_bytes") or summary.get("zip_size_bytes") or verification_summary.get("zip_size_bytes"),
        "manifest_hash": runtime.get("manifest_hash") or verification.get("manifest_hash") or summary.get("manifest_hash") or verification_summary.get("manifest_hash"),
    }


def _runtime_blockers(runtime: ImplementationDocument) -> list[str]:
    verification = _as_document(runtime.get("verification"))
    values = runtime.get("blockers") or verification.get("blockers") or []
    if values:
        return [sanitize_sensitive_text(str(item)) for item in values]
    if runtime.get("status") != "passed" and runtime.get("message"):
        return [sanitize_sensitive_text(str(runtime.get("message")))]
    return []


def _evidence_status(blockers: list[str]) -> str:
    if any(item.endswith(("_package_missing", "_verification_missing")) for item in blockers):
        return "missing_external_evidence"
    if any(item.endswith("_wrong_package_type") for item in blockers):
        return "wrong_package_type"
    if any(item.endswith("_reset_pending") for item in blockers):
        return "reset_pending"
    if any(item.endswith(("_runtime_failed", "_runtime_exception")) for item in blockers):
        return "runtime_failed"
    if any(item.endswith("_verification_projection_invalid") for item in blockers):
        return "stale"
    if any("verification_zip_" in item or item.endswith("_verification_manifest_hash") for item in blockers):
        return "stale"
    if blockers:
        return "verification_failed"
    return "ready"


def _gap_actions(readiness_rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    actions = []
    for row in readiness_rows:
        if row.get("status") != "ready":
            actions.append({"action_id": f"gap-{row.get('component_type')}", "component_type": row.get("component_type"), "action_type": "manual_required", "reason": ",".join(row.get("blockers") or [])})
    return actions


def _safe_actions(readiness_rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    actions = [
        {"action_id": "uccc-refresh", "action_type": "continuity_command_center.refresh", "mode": "safe"},
        {"action_id": "uccc-export", "action_type": "continuity_command_center.export", "mode": "safe"},
        {"action_id": "uccc-zip", "action_type": "continuity_command_center.zip", "mode": "safe"},
        {"action_id": "uccc-verify", "action_type": "continuity_command_center.verify", "mode": "safe"},
    ]
    for row in readiness_rows:
        if row.get("status") != "ready":
            actions.append({"action_id": f"verify-{row.get('component_type')}", "action_type": f"{row.get('component_type')}.verify", "mode": "safe", "status": "manual_required"})
    return actions


def _sanitize_payload(payload: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(payload)

_v142_urpccc_readiness.bind_globals(globals())
_v142_urpccc_evidence.bind_globals(globals())
