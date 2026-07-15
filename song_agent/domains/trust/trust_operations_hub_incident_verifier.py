from __future__ import annotations
from song_agent.platform.verification import (
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib
import json
import os
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import INCIDENT_EXPORT_ENTRIES, TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, incident_hash, incident_manifest_hash


TRUST_OPERATIONS_INCIDENT_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
EVIDENCE_PACKAGE_TYPES = {
    "release_verification": "musicforge_release_verification",
    "distribution_verification": "musicforge_distribution_verification",
    "submission_verification": "musicforge_submission_verification",
    "submission_evidence_verification": "musicforge_submission_evidence_verification",
    "release_operations_verification": "musicforge_release_operations_verification",
    "publication_monitoring_verification": "musicforge_public_trust_center_publication_monitoring_verification",
}


def verify_trust_operations_hub_incident_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_no_open_critical: bool = False,
    require_no_open_blocking: bool = False,
    require_current_hub: bool = False,
    hub_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _IncidentVerifier(
        Path(zip_path),
        strict=strict,
        require_no_open_critical=require_no_open_critical,
        require_no_open_blocking=require_no_open_blocking,
        require_current_hub=require_current_hub,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_hub_incident_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_hub_incident_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Trust Operations Incident Board verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"incidents: {summary.get('total_incidents') or 0}")
    print(f"open blocking: {summary.get('blocking_open_count') or 0}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")


def trust_operations_hub_incident_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


def _invalid_passed_evidence_bindings(rows: list[Any]) -> list[str]:
    invalid = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "passed":
            continue
        if not _evidence_binding_valid(row):
            invalid.append(str(row.get("evidence_id") or row.get("component_id") or "unknown"))
    return invalid


def _evidence_binding_valid(evidence: dict[str, Any]) -> bool:
    expected_package = EVIDENCE_PACKAGE_TYPES.get(str(evidence.get("component_type") or ""))
    if expected_package and evidence.get("package_type") != expected_package:
        return False
    if evidence.get("binding_status") != "passed":
        return False
    if evidence.get("package_type") != evidence.get("expected_package_type"):
        return False
    if evidence.get("component_type") != evidence.get("expected_component_type"):
        return False
    if evidence.get("component_id") != evidence.get("expected_component_id"):
        return False
    if evidence.get("verification_report_hash") != evidence.get("expected_verification_report_hash"):
        return False
    for key in ("zip_sha256", "zip_size_bytes", "manifest_hash", "source_hash"):
        expected_key = "expected_" + key
        if evidence.get(expected_key) is not None and evidence.get(key) != evidence.get(expected_key):
            return False
    checks = evidence.get("binding_checks") if isinstance(evidence.get("binding_checks"), list) else []
    return bool(checks) and all(isinstance(check, dict) and check.get("status") == "passed" for check in checks)


def _missing_components_from_hub_verification(report: dict[str, Any]) -> set[str]:
    missing: set[str] = set()
    for item in report.get("blockers", []) if isinstance(report.get("blockers"), list) else []:
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("check_id") or "")
        message = str(item.get("message") or "")
        if not check_id.endswith("_component_coverage"):
            continue
        match = re.search(r"missing=\[(.*?)\]", message)
        if not match:
            continue
        for component_id in re.findall(r"'([^']+)'|\"([^\"]+)\"", match.group(1)):
            value = component_id[0] or component_id[1]
            if value:
                missing.add(value)
    return missing


class _IncidentVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_no_open_critical: bool,
        require_no_open_blocking: bool,
        require_current_hub: bool,
        hub_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_no_open_critical = require_no_open_critical
        self.require_no_open_blocking = require_no_open_blocking
        self.require_current_hub = require_current_hub
        self.hub_verification_report_path = hub_verification_report_path
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.board: dict[str, Any] = {}
        self.report: dict[str, Any] = {}
        self.source_summary: dict[str, Any] = {}
        self.incidents_doc: dict[str, Any] = {}
        self.plans_doc: dict[str, Any] = {}
        self.results_doc: dict[str, Any] = {}
        self.evidence_index: dict[str, Any] = {}
        self.closeout_summary: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.hub_verification_report: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_semantics()
                self._verify_external_hub()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        zip_fs_path = _fs_path(self.zip_path)
        if not os.path.isfile(zip_fs_path) or os.path.islink(zip_fs_path):
            self._add_check("zip", "tohi_zip_open", "failed", "blocking", "Incident ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = os.stat(zip_fs_path).st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "tohi_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "Incident ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(zip_fs_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "tohi_zip_open", "failed", "blocking", f"Incident ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "tohi_zip_open", "passed", "blocking", "Incident ZIP can be opened.")
        return archive

    def _verify_zip_structure(self, archive: zipfile.ZipFile) -> None:
        self.entry_infos = archive.infolist()
        self.entry_names = [info.filename for info in self.entry_infos]
        self.raw_entry_names = _raw_zip_entry_names(self.zip_path)
        self.entry_map = {}
        for info in self.entry_infos:
            if info.filename not in self.entry_map:
                self.entry_map[info.filename] = info
        self.total_uncompressed_size = sum(max(0, int(info.file_size or 0)) for info in self.entry_infos)
        self._add_check("zip", "tohi_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "Incident ZIP uncompressed size is within limit.")
        self._add_check("zip", "tohi_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "Incident ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "tohi_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "tohi_zip_no_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "tohi_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip"))
        self._add_check("zip", "tohi_zip_no_nested_zip", "failed" if nested else "passed", "blocking", "Nested ZIP entries are not allowed." if nested else "No nested ZIP entries are present.")
        missing = sorted(INCIDENT_EXPORT_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - INCIDENT_EXPORT_ENTRIES)
        self._add_check("zip", "tohi_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Incident entries: " + ", ".join(missing[:8]) if missing else "All required Incident entries exist.")
        self._add_check("zip", "tohi_zip_no_extra_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Incident entries: " + ", ".join(unexpected[:8]) if unexpected else "Incident ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-incident-manifest.json", "manifest", "tohi_manifest_parse")
        self.board = self._read_json_entry(archive, "incident-board.json", "board", "tohi_board_parse")
        self.report = self._read_json_entry(archive, "incident-board-report.json", "report", "tohi_report_parse")
        self.source_summary = self._read_json_entry(archive, "incident-source-summary.json", "source", "tohi_source_parse")
        self.incidents_doc = self._read_json_entry(archive, "incidents.json", "incidents", "tohi_incidents_parse")
        self.plans_doc = self._read_json_entry(archive, "remediation-plans.json", "plans", "tohi_plans_parse")
        self.results_doc = self._read_json_entry(archive, "remediation-results.json", "results", "tohi_results_parse")
        self.evidence_index = self._read_json_entry(archive, "evidence-index.json", "evidence", "tohi_evidence_parse")
        self.closeout_summary = self._read_json_entry(archive, "closeout-summary.json", "closeouts", "tohi_closeouts_parse")
        self.events = self._read_jsonl_entry(archive, "incident-events.jsonl", "events", "tohi_events_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "tohi_manifest_integrity", self.manifest.get("integrity_hash"), incident_manifest_hash(self.manifest), "Incident manifest integrity")
        self._add_exact_check("manifest", "tohi_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE, "Incident manifest package_type")
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "tohi_manifest_files_match_entries", sorted(manifest_paths), sorted(INCIDENT_EXPORT_ENTRIES - {"trust-operations-incident-manifest.json"}), "Manifest file list matches fixed Incident structure")
        mismatches: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            if actual_sha != item.get("sha256") or actual_size != item.get("size_bytes"):
                mismatches.append(path)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if path not in mismatches else "failed"})
        self._add_check("manifest", "tohi_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in ((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "tohi_manifest_zip_summary", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files." if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        for label, doc in {
            "board": self.board,
            "report": self.report,
            "incidents": self.incidents_doc,
            "plans": self.plans_doc,
            "results": self.results_doc,
            "evidence_index": self.evidence_index,
            "closeout_summary": self.closeout_summary,
        }.items():
            self._add_hash_check(label, f"tohi_{label}_integrity", doc.get("integrity_hash"), incident_hash(doc), f"{label} integrity")
        self._add_exact_check("board", "tohi_board_package_type", self.board.get("package_type"), TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE, "Incident Board package_type")
        integrity = self.manifest.get("integrity") if isinstance(self.manifest.get("integrity"), dict) else {}
        self._add_exact_check("manifest", "tohi_manifest_board_hash", integrity.get("board_hash"), self.board.get("integrity_hash"), "Manifest board hash")
        self._add_exact_check("manifest", "tohi_manifest_report_hash", integrity.get("report_hash"), self.report.get("integrity_hash"), "Manifest report hash")
        self._add_exact_check("manifest", "tohi_manifest_evidence_index_hash", integrity.get("evidence_index_hash"), self.evidence_index.get("integrity_hash"), "Manifest evidence index hash")
        self._add_exact_check("manifest", "tohi_manifest_closeout_summary_hash", integrity.get("closeout_summary_hash"), self.closeout_summary.get("integrity_hash"), "Manifest closeout summary hash")

    def _verify_semantics(self) -> None:
        incidents = self.incidents_doc.get("incidents") if isinstance(self.incidents_doc.get("incidents"), list) else []
        closeouts = self.closeout_summary.get("closeouts") if isinstance(self.closeout_summary.get("closeouts"), list) else []
        self._add_exact_check("board", "tohi_board_summary_matches_incidents", self.board.get("summary"), _board_summary(incidents), "Board summary matches incidents")
        self._add_exact_check("report", "tohi_report_summary_matches_incidents", self.report.get("summary"), _board_summary(incidents), "Report summary matches incidents")
        event_rebuild = _rebuild_status_from_events(self.events)
        mismatches = []
        for incident in incidents:
            if not isinstance(incident, dict):
                continue
            incident_id = str(incident.get("incident_id") or "")
            rebuilt = event_rebuild.get(incident_id)
            if rebuilt and rebuilt != incident.get("status"):
                mismatches.append(incident_id)
        self._add_check("events", "tohi_incident_events_chain", "passed" if _event_chain_ok(self.events) else "failed", "blocking", "Incident event chain is intact." if _event_chain_ok(self.events) else "Incident event chain is broken.")
        self._add_check("events", "tohi_incident_status_matches_events", "failed" if mismatches else "passed", "blocking", "Incident status differs from event chain: " + ", ".join(mismatches[:5]) if mismatches else "Incident status matches event chain.")
        closeout_by_id = {str(row.get("incident_id") or ""): row for row in closeouts if isinstance(row, dict)}
        evidence_rows = self.evidence_index.get("evidence") if isinstance(self.evidence_index.get("evidence"), list) else []
        invalid_evidence = _invalid_passed_evidence_bindings(evidence_rows)
        self._add_check("evidence", "tohi_evidence_binding_integrity", "failed" if invalid_evidence else "passed", "blocking", "Invalid passed evidence bindings: " + ", ".join(invalid_evidence[:5]) if invalid_evidence else "Passed evidence is bound to current Hub verification evidence.")
        hub_verification_report = self.hub_verification_report
        if not hub_verification_report and self.hub_verification_report_path:
            hub_verification_report = _read_json_file(self.hub_verification_report_path)
        missing_components = _missing_components_from_hub_verification(hub_verification_report)
        evidence_components = {str(evidence.get("component_id") or "") for evidence in evidence_rows if isinstance(evidence, dict) and _evidence_binding_valid(evidence)}
        missing_uncovered = sorted(component_id for component_id in missing_components if component_id not in evidence_components)
        self._add_check("evidence", "tohi_evidence_covers_hub_verifier_blockers", "failed" if missing_uncovered else "passed", "blocking", "Incident evidence does not cover Hub verifier blockers: " + ", ".join(missing_uncovered[:5]) if missing_uncovered else "Incident evidence covers Hub verifier blockers.")
        valid_evidence_by_incident: dict[str, list[dict[str, Any]]] = {}
        for evidence in evidence_rows:
            if isinstance(evidence, dict) and _evidence_binding_valid(evidence):
                valid_evidence_by_incident.setdefault(str(evidence.get("incident_id") or ""), []).append(evidence)
        closeout_mismatches = [
            str(item.get("incident_id") or "")
            for item in incidents
            if isinstance(item, dict) and item.get("status") == "closed" and closeout_by_id.get(str(item.get("incident_id") or ""), {}).get("status") != "passed"
        ]
        self._add_check("closeouts", "tohi_closeout_summary_integrity", "failed" if closeout_mismatches else "passed", "blocking", "Closed incidents missing passed closeout: " + ", ".join(closeout_mismatches[:5]) if closeout_mismatches else "Closed incidents have passed closeout evidence.")
        valid_evidence_missing = [
            str(item.get("incident_id") or "")
            for item in incidents
            if isinstance(item, dict) and item.get("status") == "closed" and not valid_evidence_by_incident.get(str(item.get("incident_id") or ""))
        ]
        self._add_check("evidence", "tohi_closed_incident_valid_evidence", "failed" if valid_evidence_missing else "passed", "blocking", "Closed incidents missing valid external evidence: " + ", ".join(valid_evidence_missing[:5]) if valid_evidence_missing else "Closed incidents have valid external evidence.")
        report_source = self.report.get("source") if isinstance(self.report.get("source"), dict) else {}
        self._add_exact_check("report", "tohi_report_source_board_hash", report_source.get("board_hash"), self.board.get("integrity_hash"), "Report board hash")
        self._add_exact_check("report", "tohi_report_source_event_chain_hash", report_source.get("event_chain_hash"), self.events[-1].get("event_hash") if self.events else None, "Report event chain hash")

    def _verify_external_hub(self) -> None:
        if self.hub_verification_report_path:
            self.hub_verification_report = _read_json_file(self.hub_verification_report_path)
            self._add_exact_check("external", "tohi_hub_verification_status", self.hub_verification_report.get("status"), self.source_summary.get("hub_verification_status"), "Hub verification status")
            self._add_exact_check("external", "tohi_source_matches_hub_verification", verification_hash(self.hub_verification_report), self.source_summary.get("hub_verification_report_hash"), "Hub verification report hash")
            self._add_exact_check("external", "tohi_hub_verification_zip_sha256", self.hub_verification_report.get("zip_sha256"), self.source_summary.get("hub_zip_sha256"), "Hub ZIP sha256")
            self._add_exact_check("external", "tohi_hub_verification_manifest_hash", self.hub_verification_report.get("manifest_hash"), self.source_summary.get("hub_manifest_hash"), "Hub manifest hash")
            self._add_exact_check("external", "tohi_hub_verification_source_hash", self.hub_verification_report.get("source_hash"), self.source_summary.get("hub_report_hash"), "Hub report hash")
        elif self.require_current_hub:
            self._add_check("external", "tohi_hub_verification_required", "failed", "blocking", "Current Incident verification requires external Hub verification report.")

    def _verify_requirements(self) -> None:
        summary = self.report.get("summary") if isinstance(self.report.get("summary"), dict) else {}
        critical = int(summary.get("critical_count") or 0)
        blocking = int(summary.get("blocking_open_count") or 0)
        stale = int(summary.get("stale_count") or 0)
        self._add_check("requirements", "tohi_no_open_critical", "passed" if critical == 0 or not self.require_no_open_critical else "failed", "blocking", "No open critical incidents." if critical == 0 else "Open critical incidents remain.")
        self._add_check("requirements", "tohi_no_open_blocking", "passed" if blocking == 0 or not self.require_no_open_blocking else "failed", "blocking", "No open blocking incidents." if blocking == 0 else "Open blocking incidents remain.")
        self._add_check("requirements", "tohi_no_stale_incidents", "passed" if stale == 0 else "failed", "blocking", "No stale incidents." if stale == 0 else "Stale incidents remain.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in self.entry_infos:
            name = info.filename
            if not _is_text_scan_entry(name) or int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8", errors="ignore")
            except (KeyError, OSError):
                continue
            if _contains_sensitive_text(text):
                findings.append({"path": name, "reason": "sensitive_text"})
        for doc_name, doc in {
            "manifest": self.manifest,
            "board": self.board,
            "report": self.report,
            "source": self.source_summary,
            "incidents": self.incidents_doc,
            "evidence": self.evidence_index,
            "closeouts": self.closeout_summary,
        }.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "tohi_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Incident package." if findings else "No sensitive values found in Incident package.")

    def _build_report(self) -> dict[str, Any]:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        summary = {
            "hub_id": self.board.get("hub_id"),
            "board_id": self.board.get("board_id"),
            **(_board_summary(self.incidents_doc.get("incidents") if isinstance(self.incidents_doc.get("incidents"), list) else [])),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_INCIDENT_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": self.board.get("integrity_hash"),
                "hub_report_hash": self.source_summary.get("hub_report_hash"),
                "hub_verification_report_hash": self.source_summary.get("hub_verification_report_hash"),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": summary,
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
        try:
            raw = archive.read(name)
            value = json.loads(raw.decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parsed.")
        return value

    def _read_jsonl_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> list[dict[str, Any]]:
        try:
            raw = archive.read(name)
        except (KeyError, OSError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be read: {exc}")
            return []
        rows: list[dict[str, Any]] = []
        for line in raw.decode("utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                self._add_check(scope, check_id, "failed", "blocking", f"{name} contains invalid JSONL.")
                return []
            if isinstance(value, dict):
                rows.append(value)
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parsed.")
        return rows

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _board_summary(incidents: list[Any]) -> dict[str, Any]:
    rows = [item for item in incidents if isinstance(item, dict)]
    open_rows = [item for item in rows if item.get("status") in {"open", "triaged", "in_progress", "waiting_verification", "verified"}]
    return {
        "total_incidents": len(rows),
        "open_count": len(open_rows),
        "closed_count": sum(1 for item in rows if item.get("status") == "closed"),
        "critical_count": sum(1 for item in open_rows if item.get("severity") == "critical"),
        "high_count": sum(1 for item in open_rows if item.get("severity") == "high"),
        "blocking_open_count": sum(1 for item in open_rows if item.get("blocking")),
        "stale_count": sum(1 for item in rows if item.get("stale")),
        "ready_for_hub_signoff": len(open_rows) == 0 and not any(item.get("stale") for item in rows),
    }


def _rebuild_status_from_events(events: list[dict[str, Any]]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for event in events:
        incident_id = str(event.get("incident_id") or "")
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type in {"incident_created", "incident_refreshed"}:
            statuses[incident_id] = str(payload.get("status") or "open")
        elif event_type == "incident_triaged":
            statuses[incident_id] = "triaged"
        elif event_type == "incident_plan_created":
            statuses[incident_id] = "in_progress"
        elif event_type == "incident_evidence_added":
            statuses[incident_id] = "waiting_verification"
        elif event_type == "incident_fix_verified":
            statuses[incident_id] = "verified"
        elif event_type == "incident_closed":
            statuses[incident_id] = "closed"
        elif event_type == "incident_archived":
            statuses[incident_id] = "archived"
    return statuses


def _event_chain_ok(events: list[dict[str, Any]]) -> bool:
    by_incident: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_incident.setdefault(str(event.get("incident_id") or ""), []).append(event)
    for rows in by_incident.values():
        previous_hash = None
        for event in rows:
            if event.get("previous_event_hash") != previous_hash:
                return False
            expected = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
            if event.get("event_hash") != expected:
                return False
            previous_hash = event.get("event_hash")
    return True


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _is_forbidden_entry(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".musicforge/") or "/.musicforge/" in lowered


def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".txt", ".md", ".csv", ".html", ".jsonl"))


def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    lowered = text.lower()
    return any(marker in lowered for marker in ("github" + "key", "x-access" + "-token", "github" + "_pat_"))


def _walk_json_values(value: Any, prefix: str = "$") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_walk_json_values(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_json_values(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        rows.append((prefix, value))
    return rows


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
