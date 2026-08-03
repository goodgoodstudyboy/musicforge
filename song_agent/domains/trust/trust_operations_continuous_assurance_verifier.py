from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.contracts.packages import require_registered_package_type as _require_registered_package_type
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
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.trust.trust_operations_continuous_assurance_contracts import ASSURANCE_ARCHIVE_ENTRIES as ASSURANCE_ARCHIVE_ENTRIES, CORE_EVIDENCE_SPECS as CORE_EVIDENCE_SPECS, TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION, assurance_hash as assurance_hash, assurance_manifest_hash as assurance_manifest_hash
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS


TRUST_OPERATIONS_ASSURANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_continuous_assurance_verification"
TRUST_OPERATIONS_ASSURANCE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_trust_operations_assurance_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_passed: bool = False,
    require_current: bool = False,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    control_signoff_archive_path: Path | str | None = None,
    control_signoff_verification_report_path: Path | str | None = None,
    control_package_path: Path | str | None = None,
    control_verification_report_path: Path | str | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    release_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    distribution_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_evidence_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    release_operations_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AssuranceVerifier(
        Path(zip_path),
        strict=strict,
        require_passed=require_passed,
        require_current=require_current,
        core_paths={
            "hub": (Path(hub_package_path) if hub_package_path else None, Path(hub_verification_report_path) if hub_verification_report_path else None),
            "control_signoff": (Path(control_signoff_archive_path) if control_signoff_archive_path else None, Path(control_signoff_verification_report_path) if control_signoff_verification_report_path else None),
            "control": (Path(control_package_path) if control_package_path else None, Path(control_verification_report_path) if control_verification_report_path else None),
            "incident": (Path(incident_board_package_path) if incident_board_package_path else None, Path(incident_board_verification_report_path) if incident_board_verification_report_path else None),
            "knowledge": (Path(incident_knowledge_package_path) if incident_knowledge_package_path else None, Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None),
        },
        delivery_paths={
            "release_verification": _path_list(release_verification_paths),
            "distribution_verification": _path_list(distribution_verification_paths),
            "submission_verification": _path_list(submission_verification_paths),
            "submission_evidence_verification": _path_list(submission_evidence_verification_paths),
            "release_operations_verification": _path_list(release_operations_verification_paths),
        },
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_assurance_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_assurance_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Continuous Assurance verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"run: {summary.get('run_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def trust_operations_assurance_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AssuranceVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_passed: bool,
        require_current: bool,
        core_paths: dict[str, tuple[Path | None, Path | None]],
        delivery_paths: dict[str, list[Path]],
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_passed = require_passed
        self.require_current = require_current
        self.core_paths = core_paths
        self.delivery_paths = delivery_paths
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
        self.manifest: dict[str, Any] = {}
        self.run_doc: dict[str, Any] = {}
        self.report: dict[str, Any] = {}
        self.policy: dict[str, Any] = {}
        self.evidence_index: dict[str, Any] = {}
        self.external_summary: dict[str, Any] = {}
        self.history_events: list[dict[str, Any]] = []
        self.external_reports: dict[str, list[dict[str, Any]]] = {}
        self.external_manifests: dict[str, dict[str, Any]] = {}
        self.redaction_findings: list[dict[str, Any]] = []

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
                self._read_external_sources()
                self._verify_external_bindings()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "toa_zip_open", "failed", "blocking", "Assurance archive ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "toa_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "toa_zip_open", "failed", "blocking", f"Assurance archive ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "toa_zip_open", "passed", "blocking", "Assurance archive ZIP can be opened.")
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
        self._add_check("zip", "toa_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP uncompressed size is within limit.")
        self._add_check("zip", "toa_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "toa_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "toa_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "toa_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")
        missing = sorted(ASSURANCE_ARCHIVE_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - ASSURANCE_ARCHIVE_ENTRIES)
        self._add_check("zip", "toa_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Assurance entries: " + ", ".join(missing) if missing else "All required Assurance entries exist.")
        self._add_check("zip", "toa_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Assurance entries: " + ", ".join(unexpected[:5]) if unexpected else "Assurance ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-assurance-manifest.json", "manifest", "toa_manifest_parse")
        self.run_doc = self._read_json_entry(archive, "assurance-run.json", "run", "toa_run_parse")
        self.report = self._read_json_entry(archive, "assurance-report.json", "report", "toa_report_parse")
        self.policy = self._read_json_entry(archive, "assurance-policy.json", "policy", "toa_policy_parse")
        self.evidence_index = self._read_json_entry(archive, "evidence-index.json", "evidence", "toa_evidence_parse")
        self.external_summary = self._read_json_entry(archive, "external-verification-summary.json", "external", "toa_external_parse")
        try:
            raw = archive.read("assurance-history.jsonl").decode("utf-8")
            for line in raw.splitlines():
                value = json.loads(line)
                if isinstance(value, dict):
                    self.history_events.append(value)
            self._add_check("history", "toa_history_parse", "passed", "blocking", "assurance-history.jsonl parsed.")
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check("history", "toa_history_parse", "failed", "blocking", f"assurance-history.jsonl cannot be parsed: {exc}")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "toa_manifest_integrity", self.manifest.get("integrity_hash"), assurance_manifest_hash(self.manifest), "Assurance manifest integrity")
        self._add_exact_check("manifest", "toa_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE, "Assurance manifest package_type")
        rows = _as_list(self.manifest.get("files"))
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "toa_manifest_files_match_entries", sorted(manifest_paths), sorted(ASSURANCE_ARCHIVE_ENTRIES - {"trust-operations-assurance-manifest.json"}), "Manifest file list matches fixed Assurance structure")
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
        self._add_check("manifest", "toa_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "toa_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files." if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        self._add_exact_check("run", "toa_run_package_type", self.run_doc.get("package_type"), TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE, "Run package_type")
        self._add_hash_check("run", "toa_run_integrity", self.run_doc.get("integrity_hash"), assurance_hash(self.run_doc), "Run integrity")
        self._add_hash_check("run", "toa_run_source_hash", self.run_doc.get("source_hash"), stable_hash(_as_document(self.run_doc.get("source"))), "Run source hash")
        self._add_exact_check("report", "toa_report_package_type", self.report.get("package_type"), TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE, "Report package_type")
        self._add_hash_check("report", "toa_report_integrity", self.report.get("integrity_hash"), assurance_hash(self.report), "Report integrity")
        self._add_exact_check("report", "toa_report_source_hash", self.report.get("source_hash"), self.run_doc.get("source_hash"), "Report source hash")
        self._add_exact_check("policy", "toa_policy_package_type", self.policy.get("package_type"), TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE, "Policy package_type")
        self._add_hash_check("policy", "toa_policy_integrity", self.policy.get("integrity_hash"), assurance_hash(self.policy), "Policy integrity")
        self._add_exact_check("evidence", "toa_evidence_package_type", self.evidence_index.get("package_type"), TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE, "Evidence package_type")
        self._add_hash_check("evidence", "toa_evidence_integrity", self.evidence_index.get("integrity_hash"), assurance_hash(self.evidence_index), "Evidence index integrity")
        self._add_exact_check("external", "toa_external_package_type", self.external_summary.get("package_type"), TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE, "External summary package_type")
        self._add_hash_check("external", "toa_external_integrity", self.external_summary.get("integrity_hash"), assurance_hash(self.external_summary), "External summary integrity")
        report_source = _as_document(self.report.get("source"))
        self._add_exact_check("report", "toa_report_run_hash", report_source.get("run_hash"), self.run_doc.get("integrity_hash"), "Report run hash")
        self._add_exact_check("report", "toa_report_policy_hash", report_source.get("policy_hash"), self.policy.get("integrity_hash"), "Report policy hash")
        self._add_exact_check("report", "toa_report_evidence_index_hash", report_source.get("evidence_index_hash"), self.evidence_index.get("integrity_hash"), "Report evidence index hash")
        self._add_exact_check("report", "toa_report_external_summary_hash", report_source.get("external_verification_summary_hash"), self.external_summary.get("integrity_hash"), "Report external summary hash")
        manifest_source = _as_document(self.manifest.get("source"))
        expected_manifest_source = {
            "run_hash": self.run_doc.get("integrity_hash"),
            "report_hash": self.report.get("integrity_hash"),
            "policy_hash": self.policy.get("integrity_hash"),
            "evidence_index_hash": self.evidence_index.get("integrity_hash"),
            "external_verification_summary_hash": self.external_summary.get("integrity_hash"),
            "history_hash": stable_hash({"events": self.history_events}),
        }
        for key, value in expected_manifest_source.items():
            self._add_exact_check("manifest", "toa_manifest_source_" + key, manifest_source.get(key), value, f"Manifest source {key}")
        self._add_exact_check("manifest", "toa_manifest_source_hash", self.manifest.get("source_hash"), self.run_doc.get("source_hash"), "Manifest source hash")

    def _verify_semantics(self) -> None:
        checks = _as_list(self.run_doc.get("checks"))
        bad_checks = [str(item.get("check_id") or "unknown") for item in checks if isinstance(item, dict) and item.get("integrity_hash") != assurance_hash(item)]
        self._add_check("run", "toa_run_check_integrity", "failed" if bad_checks else "passed", "blocking", "Run checks have valid integrity." if not bad_checks else "Run check integrity failed: " + ", ".join(bad_checks[:5]))
        expected_summary = _checks_summary([item for item in checks if isinstance(item, dict)])
        self._add_exact_check("run", "toa_run_summary_matches_checks", self.run_doc.get("summary"), expected_summary, "Run summary matches checks")
        expected_status = "failed" if expected_summary["blocking_failed_count"] else "warning" if expected_summary["warning_count"] else "passed"
        expected_readiness = "blocked" if expected_status == "failed" else "ready_with_warnings" if expected_status == "warning" else "ready"
        self._add_exact_check("run", "toa_run_status_matches_checks", self.run_doc.get("status"), expected_status, "Run status matches checks")
        self._add_exact_check("run", "toa_run_readiness_matches_checks", self.run_doc.get("readiness"), expected_readiness, "Run readiness matches checks")
        self._add_exact_check("report", "toa_report_status_matches_run", self.report.get("status"), self.run_doc.get("status"), "Report status matches run")
        self._add_exact_check("report", "toa_report_readiness_matches_run", self.report.get("readiness"), self.run_doc.get("readiness"), "Report readiness matches run")
        self._add_exact_check("report", "toa_report_summary_matches_run", self.report.get("summary"), self.run_doc.get("summary"), "Report summary matches run")
        evidence_rows = [row for row in self.evidence_index.get("evidence", []) if isinstance(row, dict)]
        external_rows = [row for row in self.external_summary.get("external_verifications", []) if isinstance(row, dict)]
        expected_source = {
            "hub_id": self.run_doc.get("hub_id"),
            "external_verification_hashes": {f"{row.get('evidence_type')}:{row.get('component_id')}": row.get("verification_report_hash") for row in external_rows},
            "external_package_fingerprints": {
                f"{row.get('evidence_type')}:{row.get('component_id')}": {
                    "zip_sha256": row.get("zip_sha256"),
                    "zip_size_bytes": row.get("zip_size_bytes"),
                    "manifest_hash": row.get("manifest_hash"),
                    "package_type": row.get("package_type"),
                    "status": row.get("status"),
                }
                for row in external_rows
            },
            "external_summary_hash": self.external_summary.get("integrity_hash"),
            "evidence_index_hash": self.evidence_index.get("integrity_hash"),
        }
        self._add_exact_check("source", "toa_source_matches_external_summary", self.run_doc.get("source"), expected_source, "Run source is derived from external summary and evidence index")
        expected_evidence = sorted((_evidence_from_external(row) for row in external_rows), key=lambda item: str(item.get("evidence_id") or ""))
        actual_evidence = sorted((_evidence_projection(row) for row in evidence_rows), key=lambda item: str(item.get("evidence_id") or ""))
        self._add_exact_check("evidence", "toa_evidence_matches_external_summary", actual_evidence, expected_evidence, "Evidence index is derived from external summary")

    def _read_external_sources(self) -> None:
        for evidence_type, (archive_path, report_path) in self.core_paths.items():
            reports: list[dict[str, Any]] = []
            if report_path:
                reports.append(_read_json_file(report_path))
            elif self.require_current or CORE_EVIDENCE_SPECS.get(evidence_type, {}).get("required"):
                self._add_check("external", f"toa_external_{evidence_type}_verification_required", "failed", "blocking", f"Current Assurance verification requires external {evidence_type} verification report.")
            self.external_reports[evidence_type] = reports
            spec = CORE_EVIDENCE_SPECS.get(evidence_type, {})
            if archive_path:
                self.external_manifests[evidence_type] = _read_zip_json(archive_path, str(spec.get("manifest_entry") or ""))
            elif self.require_current or spec.get("required"):
                self._add_check("external", f"toa_external_{evidence_type}_package_required", "failed", "blocking", f"Current Assurance verification requires external {evidence_type} package.")
        for component_type, paths in self.delivery_paths.items():
            self.external_reports[component_type] = [_read_json_file(path) for path in paths]

    def _verify_external_bindings(self) -> None:
        external_rows = [row for row in self.external_summary.get("external_verifications", []) if isinstance(row, dict)]
        rows_by_key = {f"{row.get('evidence_type')}:{row.get('component_id')}": row for row in external_rows}
        for evidence_type, spec in CORE_EVIDENCE_SPECS.items():
            row = rows_by_key.get(f"{evidence_type}:{evidence_type}", {})
            reports = self.external_reports.get(evidence_type) or []
            report = reports[0] if reports else {}
            archive_path, _report_path = self.core_paths.get(evidence_type, (None, None))
            self._add_exact_check("external", f"toa_{evidence_type}_package_type", row.get("package_type"), spec.get("package_type"), f"{evidence_type} verification package_type")
            if report:
                self._add_exact_check("external", f"toa_{evidence_type}_verification_report_hash", row.get("verification_report_hash"), verification_hash(report), f"{evidence_type} verification report hash")
                self._add_exact_check("external", f"toa_{evidence_type}_verification_status", row.get("status"), report.get("status"), f"{evidence_type} verification status")
                self._add_exact_check("external", f"toa_{evidence_type}_report_zip_sha256", row.get("zip_sha256"), report.get("zip_sha256"), f"{evidence_type} report ZIP sha256")
                self._add_exact_check("external", f"toa_{evidence_type}_report_manifest_hash", row.get("manifest_hash"), report.get("manifest_hash"), f"{evidence_type} report manifest hash")
            if archive_path:
                self._add_exact_check("external", f"toa_{evidence_type}_package_zip_sha256", row.get("zip_sha256"), _sha256_file(archive_path), f"{evidence_type} package ZIP sha256")
                self._add_exact_check("external", f"toa_{evidence_type}_package_zip_size_bytes", row.get("zip_size_bytes"), os.stat(_fs_path(archive_path)).st_size if archive_path.exists() else None, f"{evidence_type} package ZIP size")
                package_manifest = self.external_manifests.get(evidence_type, {})
                self._add_exact_check("external", f"toa_{evidence_type}_package_manifest_hash", row.get("manifest_hash"), package_manifest.get("integrity_hash"), f"{evidence_type} package manifest hash")
        for delivery_spec in DELIVERY_VERIFICATION_COMPONENTS:
            component_type = str(delivery_spec["component_type"])
            reports = self.external_reports.get(component_type) or []
            expected = [row for row in external_rows if row.get("evidence_type") == component_type]
            self._verify_delivery_reports(component_type, expected, reports)

    def _verify_delivery_reports(self, component_type: str, expected: list[ImplementationDocument], reports: list[ImplementationDocument]) -> None:
        expected_by_hash = {str(row.get("verification_report_hash") or ""): row for row in expected}
        actual_hashes = {verification_hash(report): report for report in reports if report}
        self._add_exact_check("external", f"toa_{component_type}_verification_component_coverage", sorted(actual_hashes), sorted(expected_by_hash), f"{component_type} external report coverage")
        for report_hash, row in expected_by_hash.items():
            report = actual_hashes.get(report_hash, {})
            if not report:
                continue
            safe_id = _safe_id(str(row.get("component_id") or component_type))
            self._add_exact_check("external", f"toa_{component_type}_{safe_id}_status", row.get("status"), report.get("status"), f"{component_type} status")
            self._add_exact_check("external", f"toa_{component_type}_{safe_id}_zip_sha256", row.get("zip_sha256"), report.get("zip_sha256"), f"{component_type} ZIP sha256")
            self._add_exact_check("external", f"toa_{component_type}_{safe_id}_manifest_hash", row.get("manifest_hash"), report.get("manifest_hash"), f"{component_type} manifest hash")

    def _verify_requirements(self) -> None:
        passed = self.run_doc.get("status") == "passed" and self.report.get("status") == "passed"
        self._add_check("requirements", "toa_require_passed", "passed" if passed or not self.require_passed else "failed", "blocking", "Assurance report passed." if passed else "Assurance report is not passed.")

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
            "run": self.run_doc,
            "report": self.report,
            "policy": self.policy,
            "evidence": self.evidence_index,
            "external": self.external_summary,
        }.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "toa_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Assurance archive." if findings else "No sensitive values found in Assurance archive.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        source = _as_document(self.run_doc.get("source"))
        fingerprints = _as_document(source.get("external_package_fingerprints"))
        hub = _as_document(fingerprints.get("hub:hub"))
        control_signoff = _as_document(fingerprints.get("control_signoff:control_signoff"))
        external_hashes = _as_document(source.get("external_verification_hashes"))
        summary = {
            "hub_id": self.run_doc.get("hub_id"),
            "run_id": self.run_doc.get("run_id"),
            "readiness": self.run_doc.get("readiness"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
            "entry_count": len(self.entry_names),
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_VERIFICATION_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "assurance_report_hash": self.report.get("integrity_hash"),
                "source_hash": self.run_doc.get("source_hash"),
                "hub_zip_sha256": hub.get("zip_sha256"),
                "hub_zip_size_bytes": hub.get("zip_size_bytes"),
                "hub_manifest_hash": hub.get("manifest_hash"),
                "hub_verification_report_hash": external_hashes.get("hub:hub"),
                "control_signoff_zip_sha256": control_signoff.get("zip_sha256"),
                "control_signoff_manifest_hash": control_signoff.get("manifest_hash"),
                "control_signoff_verification_report_hash": external_hashes.get("control_signoff:control_signoff"),
                "delivery_verification_report_hashes": sorted(str(row.get("verification_report_hash") or "") for row in self.external_summary.get("external_verifications", []) if isinstance(row, dict) and str(row.get("evidence_type") or "") in _delivery_types()),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": summary,
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        try:
            value = json.loads(archive.read(name).decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parsed.")
        return value

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _checks_summary(checks: list[ImplementationDocument]) -> ImplementationDocument:
    blocking_failed = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") in {"failed", "warning"} and check.get("severity") != "blocking"]
    return {
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check.get("status") == "passed"),
        "blocking_failed_count": len(blocking_failed),
        "warning_count": len(warnings),
        "score": 0 if blocking_failed else max(0, 100 - 5 * len(warnings)),
    }


def _evidence_from_external(row: ImplementationDocument) -> ImplementationDocument:
    required = str(row.get("evidence_type") or "") in CORE_EVIDENCE_SPECS
    return {
        "evidence_id": f"{row.get('evidence_type')}:{row.get('component_id')}",
        "evidence_type": row.get("evidence_type"),
        "component_id": row.get("component_id"),
        "required": required,
        "package_type": _require_registered_package_type(row.get("package_type"), writer_id="song_agent.domains.trust.trust_operations_continuous_assurance_verifier._evidence_from_external"),
        "status": row.get("status"),
        "zip_sha256": row.get("zip_sha256"),
        "zip_size_bytes": row.get("zip_size_bytes"),
        "manifest_hash": row.get("manifest_hash"),
        "verification_report_hash": row.get("verification_report_hash"),
        "source_hash": row.get("source_hash"),
        "summary": _as_document(row.get("summary")),
    }


def _evidence_projection(row: ImplementationDocument) -> ImplementationDocument:
    return {key: row.get(key) for key in ("evidence_id", "evidence_type", "component_id", "required", "package_type", "status", "zip_sha256", "zip_size_bytes", "manifest_hash", "verification_report_hash", "source_hash", "summary")}


def _read_json_file(path: Path) -> ImplementationDocument:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return _as_document(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _sha256_file(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        digest = hashlib.sha256()
        with open(_fs_path(path), "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or lower.endswith(".zip")


def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".jsonl", ".txt", ".md"))


def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for item in LOCAL_PATH_VALUE_PATTERNS:
        pattern = item[0] if isinstance(item, tuple) else item
        if pattern.search(text):
            return True
    return False


def _walk_json_values(value: Any, prefix: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_json_values(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json_values(child, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _path_list(value: Any) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, (list, tuple)):
        return [Path(item) for item in value if item]
    return []


def _delivery_types() -> set[str]:
    return {str(spec["component_type"]) for spec in DELIVERY_VERIFICATION_COMPONENTS}


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"


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
