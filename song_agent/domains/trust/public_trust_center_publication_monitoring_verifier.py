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
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE as PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE, PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE as PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE, PUBLICATION_MONITORING_PACKAGE_TYPE as PUBLICATION_MONITORING_PACKAGE_TYPE, PUBLICATION_MONITORING_SCHEMA_VERSION as PUBLICATION_MONITORING_SCHEMA_VERSION, PUBLICATION_MONITOR_RUN_PACKAGE_TYPE as PUBLICATION_MONITOR_RUN_PACKAGE_TYPE, PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE as PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE, monitoring_hash as monitoring_hash, monitoring_manifest_hash as monitoring_manifest_hash, verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


PUBLICATION_MONITORING_VERIFICATION_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitoring_verification"
PUBLICATION_MONITORING_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
REQUIRED_ENTRIES = {
    "README.txt",
    "monitoring-manifest.json",
    "monitor-run.json",
    "probe-results.json",
    "drift-report.json",
    "incident-report.json",
    "incident-events.jsonl",
    "channel-state-snapshot.json",
    "file-index.json",
    "verification-reports/publication-verification-report.json",
    "verification-reports/mirror-verification-report.json",
    "checksum/SHA256SUMS.json",
    "checksum/SHA256SUMS.txt",
}


def verify_public_trust_center_publication_monitoring_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_no_revoked: bool = False,
    require_ready: bool = False,
    require_no_drift: bool = False,
    require_no_open_critical_incidents: bool = False,
    allow_waived_incidents: bool = False,
    publication_channel_state_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _MonitoringVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        require_no_revoked=require_no_revoked,
        require_ready=require_ready,
        require_no_drift=require_no_drift,
        require_no_open_critical_incidents=require_no_open_critical_incidents,
        allow_waived_incidents=allow_waived_incidents,
        publication_channel_state_path=Path(publication_channel_state_path) if publication_channel_state_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_publication_monitoring_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_publication_monitoring_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Public Trust Center Publication Monitoring verification")
    print(f"status: {report.get('status')}")
    print(f"run: {summary.get('run_id') or '-'}")
    print(f"publication: {summary.get('publication_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def public_trust_center_publication_monitoring_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _MonitoringVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        require_no_revoked: bool,
        require_ready: bool,
        require_no_drift: bool,
        require_no_open_critical_incidents: bool,
        allow_waived_incidents: bool,
        publication_channel_state_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.require_no_revoked = require_no_revoked
        self.require_ready = require_ready
        self.require_no_drift = require_no_drift
        self.require_no_open_critical_incidents = require_no_open_critical_incidents
        self.allow_waived_incidents = allow_waived_incidents
        self.publication_channel_state_path = publication_channel_state_path
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
        self.run_doc: ImplementationDocument = {}
        self.probe_results: ImplementationDocument = {}
        self.drift_report: ImplementationDocument = {}
        self.incident_report: ImplementationDocument = {}
        self.incident_events: list[ImplementationDocument] = []
        self.rebuilt_incidents: list[ImplementationDocument] = []
        self.rebuilt_incident_summary: dict[str, int] = {}
        self.channel_state_snapshot: ImplementationDocument = {}
        self.file_index: ImplementationDocument = {}
        self.checksum_json: ImplementationDocument = {}
        self.publication_verification: ImplementationDocument = {}
        self.mirror_verification: ImplementationDocument = {}
        self.external_channel_state: ImplementationDocument = {}

    def run(self) -> DomainDocument:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_checksums(archive)
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        zip_fs_path = _fs_path(self.zip_path)
        if not os.path.isfile(zip_fs_path) or os.path.islink(zip_fs_path):
            self._add_check("zip", "ptcpm_zip_open", "failed", "blocking", "Monitoring ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = os.stat(zip_fs_path).st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        limit = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcpm_zip_size_limit", "passed" if self.zip_size_bytes <= limit else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {limit} bytes.")
        try:
            archive = zipfile.ZipFile(zip_fs_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcpm_zip_open", "failed", "blocking", f"Monitoring ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcpm_zip_open", "passed", "blocking", "Monitoring ZIP can be opened.")
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
        uncompressed_limit = self.max_uncompressed_size_mb * 1024 * 1024
        self._add_check("zip", "ptcpm_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= uncompressed_limit else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {uncompressed_limit} bytes.")
        self._add_check("zip", "ptcpm_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "ptcpm_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcpm_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "ptcpm_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip"))
        self._add_check("zip", "ptcpm_zip_nested_allowlist", "failed" if nested else "passed", "blocking", "Nested ZIP entries are not allowed: " + ", ".join(nested[:5]) if nested else "No nested ZIP entries are present.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - REQUIRED_ENTRIES)
        self._add_check("zip", "ptcpm_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing monitoring entries: " + ", ".join(missing[:8]) if missing else "All required monitoring entries exist.")
        self._add_check("zip", "ptcpm_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected monitoring entries: " + ", ".join(unexpected[:8]) if unexpected else "Monitoring ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "monitoring-manifest.json", "manifest", "ptcpm_manifest_parse")
        self.run_doc = self._read_json_entry(archive, "monitor-run.json", "run", "ptcpm_run_parse")
        self.probe_results = self._read_json_entry(archive, "probe-results.json", "probe_results", "ptcpm_probe_results_parse")
        self.drift_report = self._read_json_entry(archive, "drift-report.json", "drift_report", "ptcpm_drift_report_parse")
        self.incident_report = self._read_json_entry(archive, "incident-report.json", "incident_report", "ptcpm_incident_report_parse")
        self.incident_events = self._read_jsonl_entry(archive, "incident-events.jsonl", "incident_events", "ptcpm_incident_events_parse")
        self.channel_state_snapshot = self._read_json_entry(archive, "channel-state-snapshot.json", "channel_state", "ptcpm_channel_state_snapshot_parse")
        self.file_index = self._read_json_entry(archive, "file-index.json", "file_index", "ptcpm_file_index_parse")
        self.checksum_json = self._read_json_entry(archive, "checksum/SHA256SUMS.json", "checksum", "ptcpm_checksum_json_parse")
        self.publication_verification = self._read_json_entry(archive, "verification-reports/publication-verification-report.json", "publication_verification", "ptcpm_publication_verification_parse")
        self.mirror_verification = self._read_json_entry(archive, "verification-reports/mirror-verification-report.json", "mirror_verification", "ptcpm_mirror_verification_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "ptcpm_manifest_integrity", self.manifest.get("integrity_hash"), monitoring_manifest_hash(self.manifest), "Monitoring manifest integrity")
        self._add_exact_check("manifest", "ptcpm_manifest_package_type", self.manifest.get("package_type"), PUBLICATION_MONITORING_PACKAGE_TYPE, "Monitoring manifest package_type")
        rows = _as_list(self.manifest.get("files"))
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "ptcpm_manifest_allowed_files", sorted(manifest_paths), sorted(REQUIRED_ENTRIES - {"monitoring-manifest.json"}), "Manifest file list matches fixed monitoring structure")
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
        self._add_check("manifest", "ptcpm_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "ptcpm_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        self._add_hash_check("run", "ptcpm_run_integrity", self.run_doc.get("integrity_hash"), monitoring_hash(self.run_doc), "Monitoring run integrity")
        self._add_hash_check("probe_results", "ptcpm_probe_results_integrity", self.probe_results.get("integrity_hash"), monitoring_hash(self.probe_results), "Probe results integrity")
        self._add_hash_check("drift_report", "ptcpm_drift_report_integrity", self.drift_report.get("integrity_hash"), monitoring_hash(self.drift_report), "Drift report integrity")
        self._add_hash_check("incident_report", "ptcpm_incident_report_integrity", self.incident_report.get("integrity_hash"), monitoring_hash(self.incident_report), "Incident report integrity")
        self._add_hash_check("file_index", "ptcpm_file_index_integrity", self.file_index.get("integrity_hash"), monitoring_hash(self.file_index), "File index integrity")
        self._add_exact_check("run", "ptcpm_run_source_probe_results", self.run_doc.get("source", {}).get("probe_results_hash"), self.probe_results.get("integrity_hash"), "Run probe results source")
        self._add_exact_check("run", "ptcpm_run_source_drift_report", self.run_doc.get("source", {}).get("drift_report_hash"), self.drift_report.get("integrity_hash"), "Run drift report source")
        self._add_exact_check("run", "ptcpm_run_source_incident_report", self.run_doc.get("source", {}).get("incident_report_hash"), self.incident_report.get("integrity_hash"), "Run incident report source")
        snapshot_hash = publication_channel_state_hash(self.channel_state_snapshot) if self.channel_state_snapshot else None
        self._add_exact_check("run", "ptcpm_run_source_channel_state_snapshot", self.run_doc.get("source", {}).get("channel_state_snapshot_hash"), snapshot_hash, "Run channel state snapshot source")
        self._add_exact_check("drift_report", "ptcpm_drift_source_probe_results", self.drift_report.get("source", {}).get("probe_results_hash"), self.probe_results.get("integrity_hash"), "Drift report probe source")
        self._add_exact_check("manifest", "ptcpm_manifest_run_hash", self.manifest.get("source", {}).get("monitor_run_hash"), self.run_doc.get("integrity_hash"), "Manifest run hash")
        self._add_exact_check("manifest", "ptcpm_manifest_probe_hash", self.manifest.get("source", {}).get("probe_results_hash"), self.probe_results.get("integrity_hash"), "Manifest probe hash")
        self._add_exact_check("manifest", "ptcpm_manifest_drift_hash", self.manifest.get("source", {}).get("drift_report_hash"), self.drift_report.get("integrity_hash"), "Manifest drift hash")
        self._add_exact_check("manifest", "ptcpm_manifest_incident_hash", self.manifest.get("source", {}).get("incident_report_hash"), self.incident_report.get("integrity_hash"), "Manifest incident hash")
        self._add_exact_check("manifest", "ptcpm_manifest_incident_events_hash", self.manifest.get("source", {}).get("incident_events_hash"), stable_hash(self.incident_events), "Manifest incident events hash")
        expected_file_index = sorted(REQUIRED_ENTRIES - {"monitoring-manifest.json", "file-index.json", "checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt"})
        actual_file_index = sorted(str(item.get("path") or "") for item in self.file_index.get("files", []) if isinstance(item, dict))
        self._add_exact_check("file_index", "ptcpm_file_index_allowed_files", actual_file_index, expected_file_index, "File index fixed entries")
        self._verify_incident_semantics()
        self._verify_probe_semantics()

    def _verify_incident_semantics(self) -> None:
        incidents = _as_list(self.incident_report.get("incidents"))
        open_count = sum(1 for item in incidents if isinstance(item, dict) and item.get("status") == "open")
        critical_count = sum(1 for item in incidents if isinstance(item, dict) and item.get("status") == "open" and item.get("severity") == "critical")
        waived_count = sum(1 for item in incidents if isinstance(item, dict) and item.get("status") == "waived")
        resolved_count = sum(1 for item in incidents if isinstance(item, dict) and item.get("status") == "resolved")
        expected_summary = {"incident_count": len(incidents), "open_count": open_count, "critical_count": critical_count, "waived_count": waived_count, "resolved_count": resolved_count}
        summary = _as_document(self.incident_report.get("summary"))
        actual = {key: summary.get(key) for key in expected_summary}
        self._add_exact_check("incident_report", "ptcpm_incident_summary_matches_incidents", actual, expected_summary, "Incident summary derives from incident rows")
        rebuilt_rows, rebuilt_summary, invalid = _rebuild_incidents_from_events(
            self.incident_events,
            center_id=str(self.incident_report.get("center_id") or self.manifest.get("center_id") or ""),
            channel_id=str(self.incident_report.get("channel_id") or self.manifest.get("channel_id") or ""),
            monitor_id=str(self.incident_report.get("monitor_id") or self.manifest.get("monitor_id") or ""),
            publication_id=self.incident_report.get("publication_id") or self.manifest.get("publication_id"),
        )
        self.rebuilt_incidents = rebuilt_rows
        self.rebuilt_incident_summary = rebuilt_summary
        self._add_check("incident_events", "ptcpm_incident_event_chain", "failed" if invalid else "passed", "blocking", "Invalid incident event chain: " + ", ".join(invalid[:5]) if invalid else "Incident event chain is valid.")
        expected_event_ids = sorted(str(item.get("incident_id") or "") for item in incidents if isinstance(item, dict))
        actual_event_ids = sorted(str(item.get("incident_id") or "") for item in rebuilt_rows if isinstance(item, dict))
        self._add_exact_check("incident_events", "ptcpm_incident_events_cover_report", actual_event_ids, expected_event_ids, "Incident event log covers incident report rows")
        comparable_report_rows = [_incident_comparable(item) for item in sorted(incidents, key=lambda row: str(row.get("incident_id") or "")) if isinstance(item, dict)]
        comparable_event_rows = [_incident_comparable(item) for item in sorted(rebuilt_rows, key=lambda row: str(row.get("incident_id") or "")) if isinstance(item, dict)]
        self._add_exact_check("incident_events", "ptcpm_incident_report_matches_events", comparable_event_rows, comparable_report_rows, "Incident report rows derive from event log")
        self._add_exact_check("incident_events", "ptcpm_incident_summary_matches_events", rebuilt_summary, expected_summary, "Incident summary derives from event log")
        waived = [str(item.get("incident_id") or "") for item in incidents if isinstance(item, dict) and item.get("status") == "waived" and item.get("severity") in {"critical", "high"}]
        if waived and not self.allow_waived_incidents:
            self._add_check("incident_report", "ptcpm_waived_incidents_blocking", "failed", "blocking", "Waived high/critical incidents require --allow-waived-incidents.")
        elif waived:
            self._add_check("incident_report", "ptcpm_waived_incidents_visible", "warning", "warning", "Waived high/critical incidents are present.")
        else:
            self._add_check("incident_report", "ptcpm_waived_incidents_blocking", "passed", "blocking", "No waived high/critical incidents.")

    def _verify_probe_semantics(self) -> None:
        publication_probe = _probe(self.probe_results, "publication_zip")
        mirror_probe = _probe(self.probe_results, "mirror_dir")
        self._add_exact_check("probe_results", "ptcpm_probe_publication_zip_sha256", publication_probe.get("zip_sha256"), self.publication_verification.get("zip_sha256"), "Probe publication ZIP sha256")
        self._add_exact_check("probe_results", "ptcpm_probe_publication_manifest_hash", publication_probe.get("manifest_hash"), self.publication_verification.get("manifest_hash"), "Probe publication manifest hash")
        self._add_exact_check("probe_results", "ptcpm_probe_publication_verification_hash", publication_probe.get("verification_report_hash"), verification_hash(self.publication_verification), "Probe publication verification report hash")
        if self.mirror_verification.get("status") == "skipped":
            self._add_check("probe_results", "ptcpm_probe_mirror_manifest_hash", "passed", "blocking", "Mirror probe was skipped by monitor target policy.")
            self._add_check("probe_results", "ptcpm_probe_mirror_verification_hash", "passed", "blocking", "Mirror probe was skipped by monitor target policy.")
        else:
            self._add_exact_check("probe_results", "ptcpm_probe_mirror_manifest_hash", mirror_probe.get("manifest_hash"), self.mirror_verification.get("manifest_hash"), "Probe mirror manifest hash")
            self._add_exact_check("probe_results", "ptcpm_probe_mirror_verification_hash", mirror_probe.get("verification_report_hash"), verification_hash(self.mirror_verification), "Probe mirror verification report hash")

    def _verify_checksums(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("checksum", "ptcpm_checksum_json_integrity", self.checksum_json.get("integrity_hash"), monitoring_hash(self.checksum_json), "Checksum JSON integrity")
        rows = _as_list(self.checksum_json.get("files"))
        mismatches: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            if _sha256_entry(archive, info) != item.get("sha256"):
                mismatches.append(path)
        self._add_check("checksum", "ptcpm_checksum_hashes", "failed" if mismatches else "passed", "blocking", "Checksum mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Checksum hashes match ZIP entries.")

    def _verify_requirements(self) -> None:
        drift_summary = _as_document(self.drift_report.get("summary"))
        incident_summary = self.rebuilt_incident_summary or (_as_document(self.incident_report.get("summary")))
        if self.require_ready:
            self._add_exact_check("requirements", "ptcpm_require_ready", [self.run_doc.get("status"), self.drift_report.get("status"), self.publication_verification.get("status")], ["passed", "passed", "passed"], "Monitoring ready state")
        if self.require_no_drift:
            self._add_exact_check("requirements", "ptcpm_require_no_drift", [drift_summary.get("critical_count"), drift_summary.get("high_count")], [0, 0], "No critical/high drift")
        if self.require_no_open_critical_incidents:
            self._add_exact_check("requirements", "ptcpm_require_no_open_critical_incidents", incident_summary.get("critical_count"), 0, "No open critical incidents")
        if self.require_current or self.require_no_revoked:
            self._verify_external_channel_state()

    def _verify_external_channel_state(self) -> None:
        if self.publication_channel_state_path is None:
            self._add_check("requirements", "ptcpm_channel_state_required", "failed", "blocking", "External publication-channel-state.json is required for current/no-revoked monitoring verification.")
            return
        state = _read_json_file(self.publication_channel_state_path)
        self.external_channel_state = state
        if not state:
            self._add_check("requirements", "ptcpm_channel_state_parse", "failed", "blocking", "External publication channel state cannot be read.")
            return
        self._add_check("requirements", "ptcpm_channel_state_parse", "passed", "blocking", "External publication channel state parses as JSON.")
        self._add_hash_check("requirements", "ptcpm_channel_state_integrity", state.get("integrity_hash"), publication_channel_state_hash(state), "External publication channel state integrity")
        self._add_exact_check("requirements", "ptcpm_channel_state_channel_id", state.get("channel_id"), self.manifest.get("channel_id") or self.run_doc.get("channel_id"), "External channel state channel_id")
        publication_id = str(self.manifest.get("publication_id") or self.run_doc.get("publication_id") or "")
        row = _publication_state_row(state, publication_id)
        if not row:
            self._add_check("requirements", "ptcpm_channel_state_publication_present", "failed", "blocking", "Publication is missing from external channel state.")
            return
        self._add_check("requirements", "ptcpm_channel_state_publication_present", "passed", "blocking", "Publication is present in external channel state.")
        manifest_source = _as_document(self.manifest.get("source"))
        self._add_exact_check("requirements", "ptcpm_channel_state_zip_sha256", row.get("zip_sha256"), manifest_source.get("publication_zip_sha256"), "External channel state publication ZIP sha256")
        self._add_exact_check("requirements", "ptcpm_channel_state_manifest_hash", row.get("manifest_hash"), manifest_source.get("publication_manifest_hash"), "External channel state manifest hash")
        self._add_exact_check("requirements", "ptcpm_channel_state_source_hash", row.get("source_hash"), manifest_source.get("publication_source_hash"), "External channel state source hash")
        self._add_exact_check("requirements", "ptcpm_channel_state_report_hash", row.get("report_hash"), manifest_source.get("publication_report_hash"), "External channel state report hash")
        if self.require_current:
            self._add_exact_check("requirements", "ptcpm_require_current_latest_event", state.get("latest_event_hash"), self.channel_state_snapshot.get("latest_event_hash"), "External channel latest event matches monitoring snapshot")
        if self.require_no_revoked:
            status = str(row.get("status") or "")
            self._add_check("requirements", "ptcpm_require_no_revoked", "passed" if status not in {"revoked", "superseded"} else "failed", "blocking", f"External channel state status is {status}.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[ImplementationDocument] = []
        for info in self.entry_infos:
            if int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            name = info.filename
            if not name.lower().endswith((".json", ".jsonl", ".txt", ".md", ".html", ".csv")):
                continue
            try:
                text = archive.read(info).decode("utf-8", errors="replace")
            except Exception:
                continue
            findings.extend(_redaction_findings(name, text))
            try:
                value = json.loads(text)
            except Exception:
                value = None
            if value is not None:
                findings.extend(_blocked_key_findings(name, value))
        self.redaction_findings = findings
        self._add_check("redaction", "ptcpm_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in monitoring package." if findings else "No sensitive values found in monitoring package.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parses as JSON.")
        return _as_document(value)

    def _read_jsonl_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> list[ImplementationDocument]:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return []
        try:
            text = archive.read(info).decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be read: {exc}")
            return []
        rows: list[ImplementationDocument] = []
        bad_lines: list[int] = []
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                bad_lines.append(index)
                continue
            if isinstance(value, dict):
                rows.append(value)
            else:
                bad_lines.append(index)
        self._add_check(scope, check_id, "failed" if bad_lines else "passed", "blocking", "Invalid incident event JSONL lines: " + ", ".join(str(item) for item in bad_lines[:8]) if bad_lines else f"{name} parses as JSONL.")
        return rows

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        incident_summary = self.rebuilt_incident_summary or (_as_document(self.incident_report.get("summary")))
        summary = {
            "run_id": self.run_doc.get("run_id") or self.manifest.get("run_id"),
            "monitor_id": self.run_doc.get("monitor_id") or self.manifest.get("monitor_id"),
            "publication_id": self.run_doc.get("publication_id") or self.manifest.get("publication_id"),
            "drift_status": self.drift_report.get("status"),
            "open_incidents": incident_summary.get("open_count"),
            "critical_incidents": incident_summary.get("critical_count"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        }
        report = {
            "schema_version": PUBLICATION_MONITORING_VERIFICATION_SCHEMA_VERSION,
            "package_type": PUBLICATION_MONITORING_VERIFICATION_PACKAGE_TYPE,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "channel_state_hash": self.external_channel_state.get("integrity_hash") if isinstance(self.external_channel_state, dict) else None,
            "summary": summary,
            "checks": self.checks,
            "files": self.files,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key not in {"integrity_hash", "generated_at"}})
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _probe(probe_results: ImplementationDocument, target_type: str) -> ImplementationDocument:
    for probe in probe_results.get("probes", []) if isinstance(probe_results.get("probes"), list) else []:
        if isinstance(probe, dict) and probe.get("target_type") == target_type:
            return probe
    return {}


from song_agent.domains.trust import v142_ptcpmv_readiness as _v142_ptcpmv_readiness
from song_agent.domains.trust.v142_ptcpmv_readiness import (
    _rebuild_incidents_from_events,
    _incident_from_events,
    _incident_comparable,
    _incident_title,
    _manual_action_for_drift,
    _incident_event_chain_valid,
    _publication_state_row,
    _is_safe_entry,
    _is_forbidden_entry,
    _sha256_file,
    _sha256_entry,
    _read_json_file,
    _counts,
    _redaction_findings,
    _blocked_key_findings,
    _fs_path,
)

_v142_ptcpmv_readiness.bind_globals(globals())
