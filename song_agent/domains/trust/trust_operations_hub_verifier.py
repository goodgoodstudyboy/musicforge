# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
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
from song_agent.domains.trust.public_trust_center_publication_contracts import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES as HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HUB_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION as TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash as hub_hash, hub_manifest_hash as hub_manifest_hash
from song_agent.domains.trust.v142_tohv_readiness import _HubVerifierReadinessMixin
from song_agent.domains.trust import v142_tohv_readiness as _v142_tohv_readiness
from song_agent.domains.trust.v142_tohv_evidence import _HubVerifierEvidenceMixin
from song_agent.domains.trust import v142_tohv_evidence as _v142_tohv_evidence



TRUST_OPERATIONS_HUB_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_hub_verification"
TRUST_OPERATIONS_HUB_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


def verify_trust_operations_hub_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    require_no_critical_blockers: bool = False,
    require_publication_monitoring_clean: bool = False,
    require_delivery_ready: bool = False,
    require_incident_closeout: bool = False,
    require_incident_regression_guards: bool = False,
    require_trust_controls: bool = False,
    require_trust_control_signoff: bool = False,
    require_continuous_assurance: bool = False,
    require_assurance_watch_clear: bool = False,
    require_assurance_watch_signoff: bool = False,
    require_final_readiness: bool = False,
    publication_channel_state_path: Path | str | None = None,
    public_trust_center_verification_path: Path | str | None = None,
    publication_monitoring_verification_path: Path | str | None = None,
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
    hub_signoff_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    trust_control_package_path: Path | str | None = None,
    trust_control_verification_report_path: Path | str | None = None,
    trust_control_signoff_archive_path: Path | str | None = None,
    trust_control_signoff_verification_report_path: Path | str | None = None,
    continuous_assurance_archive_path: Path | str | None = None,
    continuous_assurance_verification_report_path: Path | str | None = None,
    assurance_watch_package_path: Path | str | None = None,
    assurance_watch_verification_report_path: Path | str | None = None,
    assurance_watch_signoff_archive_path: Path | str | None = None,
    assurance_watch_signoff_verification_report_path: Path | str | None = None,
    final_handoff_package_path: Path | str | None = None,
    final_handoff_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _HubVerifier(
        Path(zip_path),
        strict=strict,
        require_ready=require_ready,
        require_signed=require_signed,
        require_current=require_current,
        require_no_critical_blockers=require_no_critical_blockers,
        require_publication_monitoring_clean=require_publication_monitoring_clean,
        require_delivery_ready=require_delivery_ready,
        require_incident_closeout=require_incident_closeout,
        require_incident_regression_guards=require_incident_regression_guards,
        require_trust_controls=require_trust_controls,
        require_trust_control_signoff=require_trust_control_signoff,
        require_continuous_assurance=require_continuous_assurance,
        require_assurance_watch_clear=require_assurance_watch_clear,
        require_assurance_watch_signoff=require_assurance_watch_signoff,
        require_final_readiness=require_final_readiness,
        publication_channel_state_path=Path(publication_channel_state_path) if publication_channel_state_path else None,
        public_trust_center_verification_path=Path(public_trust_center_verification_path) if public_trust_center_verification_path else None,
        publication_monitoring_verification_path=Path(publication_monitoring_verification_path) if publication_monitoring_verification_path else None,
        release_verification_paths=_combine_paths(release_verification_paths, release_verification_path),
        distribution_verification_paths=_combine_paths(distribution_verification_paths, distribution_verification_path),
        submission_verification_paths=_combine_paths(submission_verification_paths, submission_verification_path),
        submission_evidence_verification_paths=_combine_paths(submission_evidence_verification_paths, submission_evidence_verification_path),
        release_operations_verification_paths=_combine_paths(release_operations_verification_paths, release_operations_verification_path),
        hub_signoff_path=Path(hub_signoff_path) if hub_signoff_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        incident_knowledge_package_path=Path(incident_knowledge_package_path) if incident_knowledge_package_path else None,
        incident_knowledge_verification_report_path=Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None,
        trust_control_package_path=Path(trust_control_package_path) if trust_control_package_path else None,
        trust_control_verification_report_path=Path(trust_control_verification_report_path) if trust_control_verification_report_path else None,
        trust_control_signoff_archive_path=Path(trust_control_signoff_archive_path) if trust_control_signoff_archive_path else None,
        trust_control_signoff_verification_report_path=Path(trust_control_signoff_verification_report_path) if trust_control_signoff_verification_report_path else None,
        continuous_assurance_archive_path=Path(continuous_assurance_archive_path) if continuous_assurance_archive_path else None,
        continuous_assurance_verification_report_path=Path(continuous_assurance_verification_report_path) if continuous_assurance_verification_report_path else None,
        assurance_watch_package_path=Path(assurance_watch_package_path) if assurance_watch_package_path else None,
        assurance_watch_verification_report_path=Path(assurance_watch_verification_report_path) if assurance_watch_verification_report_path else None,
        assurance_watch_signoff_archive_path=Path(assurance_watch_signoff_archive_path) if assurance_watch_signoff_archive_path else None,
        assurance_watch_signoff_verification_report_path=Path(assurance_watch_signoff_verification_report_path) if assurance_watch_signoff_verification_report_path else None,
        final_handoff_package_path=Path(final_handoff_package_path) if final_handoff_package_path else None,
        final_handoff_verification_report_path=Path(final_handoff_verification_report_path) if final_handoff_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_hub_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_hub_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Hub verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def trust_operations_hub_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _HubVerifier(_HubVerifierReadinessMixin, _HubVerifierEvidenceMixin):
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_ready: bool,
        require_signed: bool,
        require_current: bool,
        require_no_critical_blockers: bool,
        require_publication_monitoring_clean: bool,
        require_delivery_ready: bool,
        require_incident_closeout: bool,
        require_incident_regression_guards: bool,
        require_trust_controls: bool,
        require_trust_control_signoff: bool,
        require_continuous_assurance: bool,
        require_assurance_watch_clear: bool,
        require_assurance_watch_signoff: bool,
        require_final_readiness: bool,
        publication_channel_state_path: Path | None,
        public_trust_center_verification_path: Path | None,
        publication_monitoring_verification_path: Path | None,
        release_verification_paths: list[Path],
        distribution_verification_paths: list[Path],
        submission_verification_paths: list[Path],
        submission_evidence_verification_paths: list[Path],
        release_operations_verification_paths: list[Path],
        hub_signoff_path: Path | None,
        hub_verification_report_path: Path | None,
        incident_board_package_path: Path | None,
        incident_board_verification_report_path: Path | None,
        incident_knowledge_package_path: Path | None,
        incident_knowledge_verification_report_path: Path | None,
        trust_control_package_path: Path | None,
        trust_control_verification_report_path: Path | None,
        trust_control_signoff_archive_path: Path | None,
        trust_control_signoff_verification_report_path: Path | None,
        continuous_assurance_archive_path: Path | None,
        continuous_assurance_verification_report_path: Path | None,
        assurance_watch_package_path: Path | None,
        assurance_watch_verification_report_path: Path | None,
        assurance_watch_signoff_archive_path: Path | None,
        assurance_watch_signoff_verification_report_path: Path | None,
        final_handoff_package_path: Path | None,
        final_handoff_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_ready = require_ready
        self.require_signed = require_signed
        self.require_current = require_current
        self.require_no_critical_blockers = require_no_critical_blockers
        self.require_publication_monitoring_clean = require_publication_monitoring_clean
        self.require_delivery_ready = require_delivery_ready
        self.require_incident_closeout = require_incident_closeout
        self.require_incident_regression_guards = require_incident_regression_guards
        self.require_trust_controls = require_trust_controls
        self.require_trust_control_signoff = require_trust_control_signoff
        self.require_continuous_assurance = require_continuous_assurance
        self.require_assurance_watch_clear = require_assurance_watch_clear
        self.require_assurance_watch_signoff = require_assurance_watch_signoff
        self.require_final_readiness = require_final_readiness
        self.publication_channel_state_path = publication_channel_state_path
        self.public_trust_center_verification_path = public_trust_center_verification_path
        self.publication_monitoring_verification_path = publication_monitoring_verification_path
        self.delivery_verification_paths = {
            "release_verification": release_verification_paths,
            "distribution_verification": distribution_verification_paths,
            "submission_verification": submission_verification_paths,
            "submission_evidence_verification": submission_evidence_verification_paths,
            "release_operations_verification": release_operations_verification_paths,
        }
        self.hub_signoff_path = hub_signoff_path
        self.hub_verification_report_path = hub_verification_report_path
        self.incident_board_package_path = incident_board_package_path
        self.incident_board_verification_report_path = incident_board_verification_report_path
        self.incident_knowledge_package_path = incident_knowledge_package_path
        self.incident_knowledge_verification_report_path = incident_knowledge_verification_report_path
        self.trust_control_package_path = trust_control_package_path
        self.trust_control_verification_report_path = trust_control_verification_report_path
        self.trust_control_signoff_archive_path = trust_control_signoff_archive_path
        self.trust_control_signoff_verification_report_path = trust_control_signoff_verification_report_path
        self.continuous_assurance_archive_path = continuous_assurance_archive_path
        self.continuous_assurance_verification_report_path = continuous_assurance_verification_report_path
        self.assurance_watch_package_path = assurance_watch_package_path
        self.assurance_watch_verification_report_path = assurance_watch_verification_report_path
        self.assurance_watch_signoff_archive_path = assurance_watch_signoff_archive_path
        self.assurance_watch_signoff_verification_report_path = assurance_watch_signoff_verification_report_path
        self.final_handoff_package_path = final_handoff_package_path
        self.final_handoff_verification_report_path = final_handoff_verification_report_path
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.manifest: ImplementationDocument = {}
        self.report: ImplementationDocument = {}
        self.matrix: ImplementationDocument = {}
        self.blockers_doc: ImplementationDocument = {}
        self.actions: ImplementationDocument = {}
        self.evidence: ImplementationDocument = {}
        self.verifications: ImplementationDocument = {}
        self.source_state: ImplementationDocument = {}
        self.delivery_evidence: ImplementationDocument = {}
        self.delivery_matrix: ImplementationDocument = {}
        self.delivery_blockers: ImplementationDocument = {}
        self.delivery_actions: ImplementationDocument = {}
        self.signoff_summary: ImplementationDocument = {}
        self.checksum_json: ImplementationDocument = {}
        self.external_channel_state: ImplementationDocument = {}
        self.external_ptc_verification: ImplementationDocument = {}
        self.external_monitoring_verification: ImplementationDocument = {}
        self.external_delivery_verifications: dict[str, list[ImplementationDocument]] = {}
        self.external_hub_signoff: ImplementationDocument = {}
        self.external_hub_verification_report: ImplementationDocument = {}
        self.external_incident_verification_report: ImplementationDocument = {}
        self.external_incident_knowledge_verification_report: ImplementationDocument = {}
        self.external_trust_control_verification_report: ImplementationDocument = {}
        self.external_trust_control_signoff_verification_report: ImplementationDocument = {}
        self.external_continuous_assurance_verification_report: ImplementationDocument = {}
        self.external_assurance_watch_verification_report: ImplementationDocument = {}
        self.external_assurance_watch_signoff_verification_report: ImplementationDocument = {}
        self.external_final_handoff_verification_report: ImplementationDocument = {}




























def _expected_matrix_rows(source_state: ImplementationDocument, evidence: ImplementationDocument) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    ptc = _evidence_by_type(evidence, "public_trust_center_verification")
    rows.append(_matrix_row_projection("public-trust-center:ptc-default", "public_trust_center", "public_trust_center_verified", _status_from_evidence(ptc)))
    states = _source_publication_states(source_state)
    state = states[0] if states else {}
    current_status = str(state.get("current_status") or "")
    publication_status = "ready" if state and current_status not in {"revoked", "superseded"} else "blocked"
    rows.append(_matrix_row_projection("publication-channel:" + str(state.get("channel_id") or "missing"), "publication_channel", "publication_current", publication_status))
    monitoring = _evidence_by_type(evidence, "publication_monitoring_verification")
    rows.append(_matrix_row_projection("publication-monitoring:public-release", "publication_monitoring", "publication_monitoring_clean", _status_from_evidence(monitoring)))
    summary = _as_document(monitoring.get("summary"))
    critical = int(summary.get("critical_incidents") or summary.get("open_critical_incidents") or 0)
    if monitoring and critical > 0:
        rows.append(_matrix_row_projection("publication-monitoring:public-release", "publication_monitoring", "no_open_critical_incidents", "blocked"))
    return sorted(rows, key=lambda item: (str(item.get("component_id") or ""), str(item.get("requirement") or "")))


def _expected_delivery_matrix_rows(delivery_evidence: ImplementationDocument) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    evidence_rows = [row for row in delivery_evidence.get("evidence", []) if isinstance(row, dict)]
    by_type: dict[str, list[ImplementationDocument]] = {}
    for row in evidence_rows:
        by_type.setdefault(str(row.get("component_type") or ""), []).append(row)
    for spec in DELIVERY_VERIFICATION_COMPONENTS:
        component_type = str(spec["component_type"])
        requirement = str(spec["requirement"])
        typed = by_type.get(component_type, [])
        if not typed:
            continue
        for row in typed:
            rows.append(_matrix_row_projection(str(row.get("component_id") or component_type + ":missing"), component_type, requirement, _status_from_evidence(row)))
    return sorted(rows, key=lambda item: (str(item.get("component_id") or ""), str(item.get("requirement") or "")))


def _status_from_evidence(evidence: ImplementationDocument) -> str:
    if not evidence:
        return "missing"
    status = str(evidence.get("status") or "")
    if status == "passed":
        return "ready"
    if status == "failed":
        return "blocked"
    if status == "stale":
        return "stale"
    return "missing"


def _matrix_row_projection(component_id: str, component_type: str, requirement: str, status: str) -> ImplementationDocument:
    return {"component_id": component_id, "component_type": component_type, "requirement": requirement, "status": status}


def _matrix_projection(row: ImplementationDocument) -> ImplementationDocument:
    return {"component_id": row.get("component_id"), "component_type": row.get("component_type"), "requirement": row.get("requirement"), "status": row.get("status")}


def _readiness_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "row_count": len(rows),
        "ready_count": sum(1 for row in rows if row.get("status") == "ready"),
        "blocked_count": sum(1 for row in rows if row.get("status") == "blocked"),
        "warning_count": sum(1 for row in rows if row.get("status") == "warning"),
        "stale_count": sum(1 for row in rows if row.get("status") == "stale"),
        "missing_count": sum(1 for row in rows if row.get("status") in {"missing", "not_configured"}),
    }


def _combine_readiness_summaries(*summaries: ImplementationDocument) -> dict[str, int]:
    keys = ("row_count", "ready_count", "blocked_count", "warning_count", "stale_count", "missing_count")
    return {key: sum(int(summary.get(key) or 0) for summary in summaries if isinstance(summary, dict)) for key in keys}


def _expected_blockers(rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    blockers = []
    for row in rows:
        if row.get("status") not in {"blocked", "stale", "missing", "not_configured"} or row.get("severity") != "blocking":
            continue
        blockers.append(
            {
                "component_id": row.get("component_id"),
                "requirement": row.get("requirement"),
                "severity": "critical" if row.get("status") == "blocked" else "high",
                "source_check_id": row.get("source_check_id") or row.get("requirement"),
            }
        )
    return sorted(blockers, key=lambda item: (str(item.get("component_id")), str(item.get("requirement"))))


def _normalize_blockers(rows: list[Any]) -> list[ImplementationDocument]:
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append({"component_id": row.get("component_id"), "requirement": row.get("requirement"), "severity": row.get("severity"), "source_check_id": row.get("source_check_id")})
    return sorted(normalized, key=lambda item: (str(item.get("component_id")), str(item.get("requirement"))))


def _evidence_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {"evidence_count": len(rows), "failed_count": sum(1 for row in rows if row.get("status") == "failed"), "stale_count": sum(1 for row in rows if row.get("status") == "stale")}


def _verification_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {"verification_count": len(rows), "passed_count": sum(1 for row in rows if row.get("status") == "passed"), "failed_count": sum(1 for row in rows if row.get("status") == "failed")}


def _verification_from_evidence(row: ImplementationDocument) -> ImplementationDocument:
    return _strip_none(
        {
            "verification_id": row.get("evidence_id"),
            "component_type": row.get("component_type"),
            "status": row.get("status"),
            "verification_report_hash": row.get("verification_report_hash"),
            "package_zip_sha256": row.get("zip_sha256"),
            "manifest_hash": row.get("manifest_hash"),
            "required_by": [_requirement_for_component(str(row.get("component_type") or ""))],
        }
    )


def _requirement_for_component(component_type: str) -> str:
    return {"public_trust_center_verification": "public_trust_center_verified", "publication_monitoring_verification": "publication_monitoring_clean"}.get(component_type, component_type)


def _evidence_by_type(evidence: ImplementationDocument, component_type: str) -> ImplementationDocument:
    for row in evidence.get("evidence", []) if isinstance(evidence.get("evidence"), list) else []:
        if isinstance(row, dict) and row.get("component_type") == component_type:
            return row
    return {}


def _delivery_evidence_by_type(evidence: ImplementationDocument, component_type: str) -> ImplementationDocument:
    for row in evidence.get("evidence", []) if isinstance(evidence.get("evidence"), list) else []:
        if isinstance(row, dict) and row.get("component_type") == component_type:
            return row
    return {}


def _delivery_evidence_rows(evidence: ImplementationDocument, component_type: str) -> list[ImplementationDocument]:
    return [row for row in evidence.get("evidence", []) if isinstance(row, dict) and row.get("component_type") == component_type]


def _combine_paths(paths: list[Path | str] | tuple[Path | str, ...] | None, path: Path | str | None = None) -> list[Path]:
    combined: list[Path] = []
    seen: set[str] = set()
    for item in paths or []:
        if item:
            candidate = Path(item)
            key = str(candidate)
            if key not in seen:
                combined.append(candidate)
                seen.add(key)
    if path:
        candidate = Path(path)
        key = str(candidate)
        if key not in seen:
            combined.append(candidate)
    return combined


def _external_delivery_component_id(component_type: str, report: ImplementationDocument, index: int) -> str:
    summary = _as_document(report.get("summary"))
    prefix = {
        "release_verification": "release",
        "distribution_verification": "distribution",
        "submission_verification": "submission",
        "submission_evidence_verification": "submission-evidence",
        "release_operations_verification": "release-operations",
    }.get(component_type, component_type)
    for key in ("release_id", "target_id", "submission_id", "evidence_id", "operations_id", "package_id"):
        value = report.get(key) or summary.get(key)
        if value:
            return f"{prefix}:{_safe_component_id(str(value))}"
    return f"{prefix}:{index:03d}"


def _safe_component_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip()).strip("-")
    return cleaned or "unknown"


def _check_safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")
    return cleaned or "unknown"


from song_agent.domains.trust import v142_tohv_readiness_2 as _v142_tohv_readiness_2
from song_agent.domains.trust.v142_tohv_readiness_2 import (
    _source_publication_states,
    _strip_none,
    _read_json_file,
    _read_zip_json,
    _sha256_entry,
    _sha256_file,
    _counts,
    _is_safe_entry,
    _is_forbidden_entry,
    _is_text_scan_entry,
    _contains_sensitive_text,
    _walk_json_values,
    _fs_path,
)


























_v142_tohv_readiness.bind_globals(globals())
_v142_tohv_evidence.bind_globals(globals())

_v142_tohv_readiness_2.bind_globals(globals())
