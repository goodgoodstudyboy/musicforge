# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import os as os
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.lifecycle import HistoryChain as HistoryChain
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center import UnifiedReleaseProgramContinuityCommandCenterStore as UnifiedReleaseProgramContinuityCommandCenterStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import ARCHIVE_REQUIRED_ENTRIES as ARCHIVE_REQUIRED_ENTRIES, COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION as COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION, HANDOFF_REQUIRED_ENTRIES as HANDOFF_REQUIRED_ENTRIES, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package, write_unified_release_program_continuity_command_center_final_handoff_verification_report as write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report as write_unified_release_program_continuity_command_center_signoff_verification_report
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package
from song_agent.domains.program.v142_urpcccs_readiness import UnifiedReleaseProgramContinuityCommandCenterSignoffStoreReadinessMixin
from song_agent.domains.program import v142_urpcccs_readiness as _v142_urpcccs_readiness
from song_agent.domains.program.v142_urpcccs_evidence import UnifiedReleaseProgramContinuityCommandCenterSignoffStoreEvidenceMixin
from song_agent.domains.program import v142_urpcccs_evidence as _v142_urpcccs_evidence
from song_agent.domains.program.v142_urpcccs_lifecycle import UnifiedReleaseProgramContinuityCommandCenterSignoffStoreLifecycleMixin
from song_agent.domains.program import v142_urpcccs_lifecycle as _v142_urpcccs_lifecycle



RESET_ACTION = "reset_command_center_signoff"
RESET_CHANGE_TYPE = "reset_command_center_signoff"


class UnifiedReleaseProgramContinuityCommandCenterSignoffError(ValueError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError(
    UnifiedReleaseProgramContinuityCommandCenterSignoffError
):
    pass


class UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
    UnifiedReleaseProgramContinuityCommandCenterSignoffError
):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError)


class UnifiedReleaseProgramContinuityCommandCenterSignoffStore(UnifiedReleaseProgramContinuityCommandCenterSignoffStoreReadinessMixin, UnifiedReleaseProgramContinuityCommandCenterSignoffStoreEvidenceMixin, UnifiedReleaseProgramContinuityCommandCenterSignoffStoreLifecycleMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.command_store = UnifiedReleaseProgramContinuityCommandCenterStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write", on_commit=lambda: sync_active_v12_state(self.program_store.root.parent))
























































def _check(check_id: str, passed: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}


def _archive_readme(program_id: str, signoff: ImplementationDocument) -> str:
    return f"MusicForge Continuity Command Center Signoff Archive\n\nProgram: {program_id}\nSigned by: {signoff.get('signed_by')}\nSigned at: {signoff.get('signed_at')}\n"


def _handoff_readme(program_id: str) -> str:
    return f"MusicForge Continuity Command Center Final Handoff\n\nProgram: {program_id}\nThis package contains public-safe fingerprints and no nested ZIP.\n"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    return re_sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def re_sub(pattern: str, replacement: str, value: str) -> str:
    import re

    return re.sub(pattern, replacement, value)


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _with_manifest_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    output = sanitize_metadata(doc, blocked_keys=DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
    output["integrity_hash"] = _integrity_hash(output)
    return output


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _serialize_value(value: ImplementationDocument | str) -> bytes:
    if isinstance(value, str):
        return value.replace("\n", os.linesep).encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")


def _memory_file_record(path: str, value: ImplementationDocument | str) -> ImplementationDocument:
    data = _serialize_value(value)
    return {"path": path, "size_bytes": len(data), "sha256": _sha256_bytes(data)}


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _build_zip(root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    ArchiveBuilder.build_directory_zip(root, zip_path)


def _zip_result(program_id: str, zip_path: Path, manifest_hash: Any) -> ImplementationDocument:
    return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": manifest_hash}


def _read_optional_json(path: Path) -> ImplementationDocument:
    return read_json(path) if path.exists() else {}


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

_v142_urpcccs_readiness.bind_globals(globals())
_v142_urpcccs_evidence.bind_globals(globals())
_v142_urpcccs_lifecycle.bind_globals(globals())
