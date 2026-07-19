# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_operations import ReleaseOperationsStore as ReleaseOperationsStore, operations_report_integrity_hash as operations_report_integrity_hash, operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore as ReleaseOperationsRunbookStore, runbook_integrity_hash as runbook_integrity_hash, runbook_integrity_ok as runbook_integrity_ok, runbook_summary as runbook_summary
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore as ReleaseOperationsSignoffStore, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_archive_manifest_integrity_ok as operations_archive_manifest_integrity_ok, operations_change_request_hash as operations_change_request_hash, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_hash as operations_signoff_hash, operations_signoff_integrity_ok as operations_signoff_integrity_ok, operations_signoff_summary as operations_signoff_summary
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.release_operations_audit_contracts import AUDIT_ENTRY_HASH_EXCLUDE_KEYS as AUDIT_ENTRY_HASH_EXCLUDE_KEYS, AUDIT_MANIFEST_HASH_EXCLUDE_KEYS as AUDIT_MANIFEST_HASH_EXCLUDE_KEYS, AUDIT_REPORT_HASH_EXCLUDE_KEYS as AUDIT_REPORT_HASH_EXCLUDE_KEYS, OPERATIONS_AUDIT_BLOCKED_KEYS as OPERATIONS_AUDIT_BLOCKED_KEYS, _entry_hash_payload as _entry_hash_payload, audit_entry_hash as audit_entry_hash, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_manifest_integrity_hash as audit_manifest_integrity_hash, audit_report_integrity_hash as audit_report_integrity_hash


OPERATIONS_AUDIT_SCHEMA_VERSION = 1
OPERATIONS_AUDIT_EXPORT_SCHEMA_VERSION = 1





DOMAIN_PRIORITY = {
    "release": 10,
    "release_export": 20,
    "metadata": 30,
    "audio": 40,
    "rights": 50,
    "format_decision": 60,
    "distribution": 70,
    "submission": 80,
    "submission_evidence": 90,
    "operations_report": 100,
    "operations_runbook": 110,
    "operations_signoff": 120,
    "operations_change_request": 130,
    "operations_archive": 140,
    "operations_audit": 150,
}


class ReleaseOperationsAuditError(ValueError):
    pass


class ReleaseOperationsAuditNotFoundError(ReleaseOperationsAuditError):
    pass


class ReleaseOperationsAuditStateError(ReleaseOperationsAuditError):
    pass


from song_agent.domains.trust import v142_roa_readiness as _v142_roa_readiness
from song_agent.domains.trust.v142_roa_readiness import ReleaseOperationsAuditStore, audit_report_integrity_ok, audit_manifest_integrity_ok, audit_summary
from song_agent.domains.trust import v142_roa_evidence as _v142_roa_evidence
from song_agent.domains.trust.v142_roa_evidence import (
    _entry_seed,
    _finalize_entries,
    _bind_change_request_causal_refs,
    _write_ledger,
    _latest_runbook,
    _read_optional_json,
    _read_jsonl,
    _reset_hash_by_change_request_id,
    _verifier_entries_from_operations_report,
    _stage_timeline,
    _critical_milestones,
    _change_control_summary,
    _package_verifier_summary,
    _coverage,
    _operations_report_summary,
    _write_audit_readme,
    _write_json,
    _file_record,
    _zip_entries,
    _validate_relative_path,
    _ensure_within,
    _sha256,
    _redaction_summary,
    _safe_text,
    _safe_time,
    _safe_event_type,
    _slug,
    _path_hint,
    _blocker,
    _warning,
)

_v142_roa_readiness.bind_globals(globals())
_v142_roa_evidence.bind_globals(globals())
