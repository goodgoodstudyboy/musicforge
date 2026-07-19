# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_final_readiness_contracts import FINAL_READINESS_EXPORT_ENTRIES as FINAL_READINESS_EXPORT_ENTRIES, FINAL_READINESS_SINGLE_SPECS as FINAL_READINESS_SINGLE_SPECS, TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS as TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS, TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION as TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION, final_readiness_hash as final_readiness_hash, final_readiness_history_event_hash as final_readiness_history_event_hash, final_readiness_history_event_payload_hash as final_readiness_history_event_payload_hash, final_readiness_history_hash as final_readiness_history_hash, final_readiness_manifest_hash as final_readiness_manifest_hash
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS


TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_verification"
TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 96
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_trust_operations_final_handoff_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    release_verification_path: Path | str | None = None,
    release_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    distribution_verification_path: Path | str | None = None,
    distribution_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_verification_path: Path | str | None = None,
    submission_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_evidence_verification_path: Path | str | None = None,
    submission_evidence_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    release_operations_verification_path: Path | str | None = None,
    release_operations_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    control_assessment_package_path: Path | str | None = None,
    control_package_path: Path | str | None = None,
    trust_control_package_path: Path | str | None = None,
    control_verification_report_path: Path | str | None = None,
    trust_control_verification_report_path: Path | str | None = None,
    control_signoff_archive_path: Path | str | None = None,
    trust_control_signoff_archive_path: Path | str | None = None,
    control_signoff_verification_report_path: Path | str | None = None,
    trust_control_signoff_verification_report_path: Path | str | None = None,
    continuous_assurance_archive_path: Path | str | None = None,
    assurance_archive_path: Path | str | None = None,
    continuous_assurance_verification_report_path: Path | str | None = None,
    assurance_verification_report_path: Path | str | None = None,
    assurance_watch_package_path: Path | str | None = None,
    watch_package_path: Path | str | None = None,
    assurance_watch_verification_report_path: Path | str | None = None,
    watch_verification_report_path: Path | str | None = None,
    assurance_watch_signoff_archive_path: Path | str | None = None,
    assurance_watch_signoff_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _FinalHandoffVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        require_current=require_current,
        external_paths={
            "hub_package_path": Path(hub_package_path) if hub_package_path else None,
            "hub_verification_report_path": Path(hub_verification_report_path) if hub_verification_report_path else None,
            "release_verification_paths": _combine_paths(release_verification_paths, release_verification_path),
            "distribution_verification_paths": _combine_paths(distribution_verification_paths, distribution_verification_path),
            "submission_verification_paths": _combine_paths(submission_verification_paths, submission_verification_path),
            "submission_evidence_verification_paths": _combine_paths(submission_evidence_verification_paths, submission_evidence_verification_path),
            "release_operations_verification_paths": _combine_paths(release_operations_verification_paths, release_operations_verification_path),
            "incident_board_package_path": Path(incident_board_package_path) if incident_board_package_path else None,
            "incident_board_verification_report_path": Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
            "incident_knowledge_package_path": Path(incident_knowledge_package_path) if incident_knowledge_package_path else None,
            "incident_knowledge_verification_report_path": Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None,
            "control_assessment_package_path": _first_path(control_assessment_package_path, control_package_path, trust_control_package_path),
            "control_verification_report_path": _first_path(control_verification_report_path, trust_control_verification_report_path),
            "control_signoff_archive_path": _first_path(control_signoff_archive_path, trust_control_signoff_archive_path),
            "control_signoff_verification_report_path": _first_path(control_signoff_verification_report_path, trust_control_signoff_verification_report_path),
            "continuous_assurance_archive_path": _first_path(continuous_assurance_archive_path, assurance_archive_path),
            "continuous_assurance_verification_report_path": _first_path(continuous_assurance_verification_report_path, assurance_verification_report_path),
            "assurance_watch_package_path": _first_path(assurance_watch_package_path, watch_package_path),
            "assurance_watch_verification_report_path": _first_path(assurance_watch_verification_report_path, watch_verification_report_path),
            "assurance_watch_signoff_archive_path": Path(assurance_watch_signoff_archive_path) if assurance_watch_signoff_archive_path else None,
            "assurance_watch_signoff_verification_report_path": Path(assurance_watch_signoff_verification_report_path) if assurance_watch_signoff_verification_report_path else None,
        },
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_final_handoff_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_final_handoff_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Final Handoff verification")
    print(f"status: {report.get('status')}")
    print(f"certificate: {summary.get('certificate_id') or '-'}")
    print(f"signoff: {summary.get('signoff_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def trust_operations_final_handoff_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


from song_agent.domains.trust import v142_tofrv_readiness as _v142_tofrv_readiness
from song_agent.domains.trust.v142_tofrv_readiness import _FinalHandoffVerifier, stable_summary_hash, _row_by_type
from song_agent.domains.trust import v142_tofrv_evidence as _v142_tofrv_evidence
from song_agent.domains.trust.v142_tofrv_evidence import (
    _summary_projection,
    _row_summary_projection,
    _row_key,
    _combine_paths,
    _first_path,
    _component_id_from_report,
    _read_json_file,
    _read_zip_json,
    _is_forbidden_entry,
    _is_text_scan_entry,
    _contains_sensitive_text,
    _walk_json_values,
    _counts,
    _sha256_file,
    _safe_check_id,
    _safe_id,
    _fs_path,
)

_v142_tofrv_readiness.bind_globals(globals())
_v142_tofrv_evidence.bind_globals(globals())
