# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import GenerationRef as GenerationRef, ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, GenerationService as GenerationService, HistoryChain as HistoryChain, ResetService as ResetService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore as UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore, _bounded as _bounded, _gate_failed as _gate_failed, _history_text as _history_text, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _read_optional_json as _read_optional_json, _safe_id as _safe_id, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import (
    ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, command_center_acceptance_change_lifecycle_semantic_checks as command_center_acceptance_change_lifecycle_semantic_checks, command_center_acceptance_change_previous_evidence_checks as command_center_acceptance_change_previous_evidence_checks, command_center_acceptance_change_reset_semantic_checks as command_center_acceptance_change_reset_semantic_checks, verify_unified_release_program_continuity_command_center_acceptance_change_package as verify_unified_release_program_continuity_command_center_acceptance_change_package, write_unified_release_program_continuity_command_center_acceptance_change_verification_report as write_unified_release_program_continuity_command_center_acceptance_change_verification_report
from song_agent.domains.program.v142_urpcccac_readiness import UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreReadinessMixin
from song_agent.domains.program import v142_urpcccac_readiness as _v142_urpcccac_readiness
from song_agent.domains.program.v142_urpcccac_evidence import UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreEvidenceMixin
from song_agent.domains.program import v142_urpcccac_evidence as _v142_urpcccac_evidence
from song_agent.domains.program.v142_urpcccac_lifecycle import UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreLifecycleMixin
from song_agent.domains.program import v142_urpcccac_lifecycle as _v142_urpcccac_lifecycle



RESET_ACTION = "reset_receiver_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_receiver_acceptance_signoff"


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError(ValueError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError)


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreReadinessMixin, UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreEvidenceMixin, UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreLifecycleMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.acceptance_store = UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write", on_commit=lambda: sync_active_v12_state(self.program_store.root.parent))



















































def _package_manifest(package_type: str, program_id: str, files: list[ImplementationDocument], source: ImplementationDocument) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
            "package_type": package_type,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: str(row.get("path") or "")),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _reject_forbidden_payload(value: Any, label: str) -> None:
    blocked = {"path", "source_path", "local_path", "file_path", "absolute_path", "token", "api_key", "password", "authorization"}
    if isinstance(value, dict):
        offenders = sorted(str(key) for key in value if str(key).lower() in blocked)
        if offenders:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                f"{label} contains forbidden path or secret fields: {', '.join(offenders)}"
            )
        for child in value.values():
            _reject_forbidden_payload(child, label)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_payload(child, label)


def _lifecycle_history_ok(rows: list[ImplementationDocument]) -> bool:
    previous = ""
    for row in rows:
        payload_hash = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in {**row, "payload_hash": payload_hash}.items() if key != "event_hash"})
        if row.get("payload_hash") != payload_hash or row.get("event_hash") != event_hash:
            return False
        if str(row.get("previous_event_hash") or "") != previous:
            return False
        previous = str(row.get("event_hash") or "")
    return True

_v142_urpcccac_readiness.bind_globals(globals())
_v142_urpcccac_evidence.bind_globals(globals())
_v142_urpcccac_lifecycle.bind_globals(globals())
