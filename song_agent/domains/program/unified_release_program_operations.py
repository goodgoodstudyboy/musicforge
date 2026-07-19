# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, HistoryChain as HistoryChain, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package, write_unified_release_program_operations_verification_report as write_unified_release_program_operations_verification_report
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package
from song_agent.domains.program.v142_urpo_readiness import UnifiedReleaseProgramOperationsStoreReadinessMixin
from song_agent.domains.program import v142_urpo_readiness as _v142_urpo_readiness
from song_agent.domains.program.v142_urpo_evidence import UnifiedReleaseProgramOperationsStoreEvidenceMixin
from song_agent.domains.program import v142_urpo_evidence as _v142_urpo_evidence



class UnifiedReleaseProgramOperationsError(ValueError):
    pass


class UnifiedReleaseProgramOperationsNotFoundError(UnifiedReleaseProgramOperationsError):
    pass


class UnifiedReleaseProgramOperationsStateError(UnifiedReleaseProgramOperationsError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramOperationsStateError)


class UnifiedReleaseProgramOperationsStore(UnifiedReleaseProgramOperationsStoreReadinessMixin, UnifiedReleaseProgramOperationsStoreEvidenceMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")



















































def _operations_manifest(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": _archive_source(docs),
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "sidecars": {
                "program_signoff_binding_hash": docs["binding"].get("integrity_hash"),
                "continuous_review_hash": docs["review"].get("integrity_hash"),
                "lifecycle_audit_hash": docs["lifecycle"].get("integrity_hash"),
            },
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _archive_source(docs: ImplementationDocument) -> ImplementationDocument:
    return {
        "program_summary_hash": docs["program"].get("integrity_hash"),
        "program_verification_summary_hash": docs["program_verification"].get("integrity_hash"),
        "program_signoff_summary_hash": docs["signoff"].get("integrity_hash"),
        "program_signoff_binding_summary_hash": docs["binding"].get("integrity_hash"),
        "external_evidence_manifest_summary_hash": docs["external_manifest"].get("integrity_hash"),
        "change_control_summary_hash": docs["change_control"].get("integrity_hash"),
        "continuous_review_summary_hash": docs["review"].get("integrity_hash"),
        "lifecycle_audit_summary_hash": docs["lifecycle"].get("integrity_hash"),
        "evidence_index_hash": docs["evidence"].get("integrity_hash"),
    }


def _runbook_summary(items: list[ImplementationDocument]) -> ImplementationDocument:
    return {
        "safe_count": sum(1 for row in items if row.get("safe")),
        "completed_count": sum(1 for row in items if row.get("status") == "completed"),
        "manual_required_count": sum(1 for row in items if row.get("status") == "manual_required"),
        "failed_count": sum(1 for row in items if row.get("status") == "failed"),
        "skipped_unsupported_count": sum(1 for row in items if row.get("status") == "skipped_unsupported"),
    }


def _history_checks(prefix: str, rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    checks = []
    previous = ""
    for index, event in enumerate(rows):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"{prefix}_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History payload hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    return checks


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}}


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip("-")[:140]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


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

_v142_urpo_readiness.bind_globals(globals())
_v142_urpo_evidence.bind_globals(globals())
