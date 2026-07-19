from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_incident_knowledge_contracts import KNOWLEDGE_EXPORT_ENTRIES as KNOWLEDGE_EXPORT_ENTRIES, TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION as TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE, TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE as TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE, _classify_incident as _classify_incident, knowledge_hash as knowledge_hash, knowledge_manifest_hash as knowledge_manifest_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash


TRUST_OPERATIONS_KNOWLEDGE_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


def verify_trust_operations_incident_knowledge_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_guards_passed: bool = False,
    require_no_open_recurrence: bool = False,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _KnowledgeVerifier(
        Path(zip_path),
        strict=strict,
        require_guards_passed=require_guards_passed,
        require_no_open_recurrence=require_no_open_recurrence,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_incident_knowledge_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_incident_knowledge_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Incident Knowledge verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"entries: {summary.get('entry_count') or 0}")
    print(f"guards: {summary.get('guard_count') or 0}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")


def trust_operations_incident_knowledge_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _KnowledgeVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_guards_passed: bool,
        require_no_open_recurrence: bool,
        incident_board_package_path: Path | None,
        incident_board_verification_report_path: Path | None,
        hub_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_guards_passed = require_guards_passed
        self.require_no_open_recurrence = require_no_open_recurrence
        self.incident_board_package_path = incident_board_package_path
        self.incident_board_verification_report_path = incident_board_verification_report_path
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
        self.manifest: dict[str, Any] = {}
        self.base: dict[str, Any] = {}
        self.report: dict[str, Any] = {}
        self.entries_doc: dict[str, Any] = {}
        self.guards_doc: dict[str, Any] = {}
        self.runs_doc: dict[str, Any] = {}
        self.recurrence: dict[str, Any] = {}
        self.source_summary: dict[str, Any] = {}
        self.external_incident_manifest: dict[str, Any] = {}
        self.external_incidents_doc: dict[str, Any] = {}
        self.external_closeout_summary: dict[str, Any] = {}
        self.external_incident_verification: dict[str, Any] = {}
        self.external_hub_verification: dict[str, Any] = {}
        self.external_incident_zip_sha256: str | None = None
        self.external_incident_zip_size_bytes: int | None = None
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
                self._verify_external_sources()
                self._verify_external_incident_semantics()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        zip_fs_path = _fs_path(self.zip_path)
        if not os.path.isfile(zip_fs_path) or os.path.islink(zip_fs_path):
            self._add_check("zip", "tohk_zip_open", "failed", "blocking", "Knowledge ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = os.stat(zip_fs_path).st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "tohk_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "Knowledge ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(zip_fs_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "tohk_zip_open", "failed", "blocking", f"Knowledge ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "tohk_zip_open", "passed", "blocking", "Knowledge ZIP can be opened.")
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
        self._add_check("zip", "tohk_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "Knowledge ZIP uncompressed size is within limit.")
        self._add_check("zip", "tohk_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "Knowledge ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "tohk_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "tohk_zip_no_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "tohk_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip"))
        self._add_check("zip", "tohk_zip_no_nested_zip", "failed" if nested else "passed", "blocking", "Nested ZIP entries are not allowed." if nested else "No nested ZIP entries are present.")
        missing = sorted(KNOWLEDGE_EXPORT_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - KNOWLEDGE_EXPORT_ENTRIES)
        self._add_check("zip", "tohk_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Knowledge entries: " + ", ".join(missing[:8]) if missing else "All required Knowledge entries exist.")
        self._add_check("zip", "tohk_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Knowledge entries: " + ", ".join(unexpected[:8]) if unexpected else "Knowledge ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-knowledge-manifest.json", "manifest", "tohk_manifest_parse")
        self.base = self._read_json_entry(archive, "knowledge-base.json", "base", "tohk_base_parse")
        self.report = self._read_json_entry(archive, "knowledge-report.json", "report", "tohk_report_parse")
        self.entries_doc = self._read_json_entry(archive, "entries.json", "entries", "tohk_entries_parse")
        self.guards_doc = self._read_json_entry(archive, "regression-guards.json", "guards", "tohk_guards_parse")
        self.runs_doc = self._read_json_entry(archive, "guard-run-summary.json", "runs", "tohk_runs_parse")
        self.recurrence = self._read_json_entry(archive, "recurrence-report.json", "recurrence", "tohk_recurrence_parse")
        self.source_summary = self._read_json_entry(archive, "source-summary.json", "source", "tohk_source_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "tohk_manifest_integrity", self.manifest.get("integrity_hash"), knowledge_manifest_hash(self.manifest), "Knowledge manifest integrity")
        self._add_exact_check("manifest", "tohk_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE, "Knowledge manifest package_type")
        rows = _as_list(self.manifest.get("files"))
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "tohk_manifest_files_match_entries", sorted(manifest_paths), sorted(KNOWLEDGE_EXPORT_ENTRIES - {"trust-operations-knowledge-manifest.json"}), "Manifest file list matches fixed Knowledge structure")
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
        self._add_check("manifest", "tohk_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "tohk_manifest_zip_summary", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files." if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        self._add_hash_check("base", "tohk_base_integrity", self.base.get("integrity_hash"), knowledge_hash(self.base), "Knowledge base integrity")
        self._add_hash_check("report", "tohk_report_integrity", self.report.get("integrity_hash"), knowledge_hash(self.report), "Knowledge report integrity")
        self._add_hash_check("entries", "tohk_entries_integrity", self.entries_doc.get("integrity_hash"), knowledge_hash(self.entries_doc), "Entries integrity")
        self._add_hash_check("guards", "tohk_guards_integrity", self.guards_doc.get("integrity_hash"), knowledge_hash(self.guards_doc), "Regression guards integrity")
        self._add_hash_check("runs", "tohk_guard_run_summary_integrity", self.runs_doc.get("integrity_hash"), knowledge_hash(self.runs_doc), "Guard run summary integrity")
        self._add_hash_check("recurrence", "tohk_recurrence_integrity", self.recurrence.get("integrity_hash"), knowledge_hash(self.recurrence), "Recurrence report integrity")
        self._add_hash_check("source", "tohk_source_integrity", self.source_summary.get("integrity_hash"), knowledge_hash(self.source_summary), "Source summary integrity")
        self._add_exact_check("base", "tohk_base_package_type", self.base.get("package_type"), TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE, "Knowledge base package_type")
        self._add_exact_check("report", "tohk_report_package_type", self.report.get("package_type"), TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE, "Knowledge report package_type")
        self._add_exact_check("entries", "tohk_entries_package_type", self.entries_doc.get("package_type"), TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE, "Entries package_type")
        self._add_exact_check("guards", "tohk_guards_package_type", self.guards_doc.get("package_type"), TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE, "Regression guards package_type")
        self._add_exact_check("runs", "tohk_runs_package_type", self.runs_doc.get("package_type"), TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE, "Guard run summary package_type")
        self._add_exact_check("recurrence", "tohk_recurrence_package_type", self.recurrence.get("package_type"), TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE, "Recurrence package_type")
        self._add_exact_check("source", "tohk_source_package_type", self.source_summary.get("package_type"), TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE, "Source summary package_type")
        integrity = _as_document(self.manifest.get("integrity"))
        self._add_exact_check("manifest", "tohk_manifest_base_hash", integrity.get("knowledge_base_hash"), self.base.get("integrity_hash"), "Manifest base hash")
        self._add_exact_check("manifest", "tohk_manifest_report_hash", integrity.get("knowledge_report_hash"), self.report.get("integrity_hash"), "Manifest report hash")
        self._add_exact_check("manifest", "tohk_manifest_entries_hash", integrity.get("entries_hash"), self.entries_doc.get("integrity_hash"), "Manifest entries hash")
        self._add_exact_check("manifest", "tohk_manifest_guards_hash", integrity.get("guards_hash"), self.guards_doc.get("integrity_hash"), "Manifest guards hash")
        self._add_exact_check("manifest", "tohk_manifest_runs_hash", integrity.get("guard_run_summary_hash"), self.runs_doc.get("integrity_hash"), "Manifest guard run summary hash")
        self._add_exact_check("manifest", "tohk_manifest_recurrence_hash", integrity.get("recurrence_hash"), self.recurrence.get("integrity_hash"), "Manifest recurrence hash")
        self._add_exact_check("manifest", "tohk_manifest_source_hash", integrity.get("source_summary_hash"), self.source_summary.get("integrity_hash"), "Manifest source hash")

    def _verify_semantics(self) -> None:
        entries = _as_list(self.entries_doc.get("entries"))
        guards = _as_list(self.guards_doc.get("guards"))
        runs = _as_list(self.runs_doc.get("runs"))
        entry_hashes = {str(entry.get("integrity_hash") or "") for entry in entries if isinstance(entry, dict)}
        guard_by_id = {str(guard.get("guard_id") or ""): guard for guard in guards if isinstance(guard, dict)}
        bad_entries = [str(entry.get("entry_id") or "") for entry in entries if isinstance(entry, dict) and entry.get("integrity_hash") != knowledge_hash(entry)]
        bad_guards = [str(guard.get("guard_id") or "") for guard in guards if isinstance(guard, dict) and guard.get("integrity_hash") != knowledge_hash(guard)]
        bad_runs = [str(run.get("guard_id") or "") for run in runs if isinstance(run, dict) and run.get("integrity_hash") != knowledge_hash(run)]
        self._add_check("entries", "tohk_entry_integrity", "failed" if bad_entries else "passed", "blocking", "Entry integrity mismatch: " + ", ".join(bad_entries[:5]) if bad_entries else "All entries have valid integrity.")
        self._add_check("guards", "tohk_guard_integrity", "failed" if bad_guards else "passed", "blocking", "Guard integrity mismatch: " + ", ".join(bad_guards[:5]) if bad_guards else "All guards have valid integrity.")
        self._add_check("runs", "tohk_guard_run_integrity", "failed" if bad_runs else "passed", "blocking", "Guard run integrity mismatch: " + ", ".join(bad_runs[:5]) if bad_runs else "All guard runs have valid integrity.")
        missing_entry_source = [
            str(guard.get("guard_id") or "")
            for guard in guards
            if isinstance(guard, dict) and guard.get("source", {}).get("knowledge_entry_hash") not in entry_hashes and guard.get("status") != "archived"
        ]
        self._add_check("guards", "tohk_guard_source_entry_binding", "failed" if missing_entry_source else "passed", "blocking", "Guards reference missing entries: " + ", ".join(missing_entry_source[:5]) if missing_entry_source else "Guards reference package entries.")
        bad_run_source = []
        for run in runs:
            if not isinstance(run, dict):
                continue
            guard = guard_by_id.get(str(run.get("guard_id") or ""))
            last_run = guard.get("last_run") if isinstance(guard, dict) and isinstance(guard.get("last_run"), dict) else {}
            if not guard or _as_document(last_run).get("guard_run_hash") != run.get("integrity_hash") or _as_document(last_run).get("guard_hash_before_run") != run.get("source", {}).get("guard_hash"):
                bad_run_source.append(str(run.get("guard_id") or ""))
        self._add_check("runs", "tohk_guard_run_source_binding", "failed" if bad_run_source else "passed", "blocking", "Guard runs reference missing guards: " + ", ".join(bad_run_source[:5]) if bad_run_source else "Guard runs reference package guards.")
        high_entries = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") != "hidden" and entry.get("severity") in {"critical", "high"}]
        covered = {str(guard.get("source", {}).get("knowledge_entry_hash") or "") for guard in guards if isinstance(guard, dict) and guard.get("status") not in {"archived", "manual_required"}}
        missing_guard = [str(entry.get("entry_id") or "") for entry in high_entries if entry.get("integrity_hash") not in covered]
        self._add_check("guards", "tohk_guards_cover_high_severity_entries", "failed" if missing_guard else "passed", "blocking", "High severity entries without active guards: " + ", ".join(missing_guard[:5]) if missing_guard else "High severity entries are covered by active guards.")
        report_source = _as_document(self.report.get("source"))
        self._add_exact_check("report", "tohk_report_source_base_hash", report_source.get("knowledge_base_hash"), self.base.get("integrity_hash"), "Report base hash")
        self._add_exact_check("report", "tohk_report_source_entries_hash", report_source.get("entries_hash"), self.entries_doc.get("integrity_hash"), "Report entries hash")
        self._add_exact_check("report", "tohk_report_source_guards_hash", report_source.get("guards_hash"), self.guards_doc.get("integrity_hash"), "Report guards hash")
        self._add_exact_check("report", "tohk_report_source_runs_hash", report_source.get("guard_run_summary_hash"), self.runs_doc.get("integrity_hash"), "Report run summary hash")
        self._add_exact_check("report", "tohk_report_source_recurrence_hash", report_source.get("recurrence_hash"), self.recurrence.get("integrity_hash"), "Report recurrence hash")

    def _verify_external_sources(self) -> None:
        source = self.source_summary
        external_required = self.require_guards_passed or self.require_no_open_recurrence or bool(self.incident_board_verification_report_path)
        if self.incident_board_package_path:
            self._read_external_incident_package()
        elif external_required:
            self._add_check("external", "tohk_incident_package_required", "failed", "blocking", "Knowledge verification requires external Incident Board ZIP.")
        if self.incident_board_verification_report_path:
            self.external_incident_verification = _read_json_file(self.incident_board_verification_report_path)
            self._add_exact_check("external", "tohk_incident_verification_status", self.external_incident_verification.get("status"), source.get("incident_verification_status"), "Incident verification status")
            self._add_exact_check("external", "tohk_incident_verification_hash", verification_hash(self.external_incident_verification), source.get("incident_verification_report_hash"), "Incident verification report hash")
            self._add_exact_check("external", "tohk_incident_verification_zip_sha256", self.external_incident_verification.get("zip_sha256"), source.get("incident_zip_sha256"), "Incident ZIP sha256")
            self._add_exact_check("external", "tohk_incident_verification_manifest_hash", self.external_incident_verification.get("manifest_hash"), source.get("incident_manifest_hash"), "Incident manifest hash")
            if self.incident_board_package_path:
                self._add_exact_check("external", "tohk_incident_package_zip_sha256", self.external_incident_verification.get("zip_sha256"), self.external_incident_zip_sha256, "Incident verification report ZIP sha256 matches Incident ZIP")
                self._add_exact_check("external", "tohk_incident_package_zip_size_bytes", self.external_incident_verification.get("zip_size_bytes"), self.external_incident_zip_size_bytes, "Incident verification report ZIP size matches Incident ZIP")
                self._add_exact_check("external", "tohk_incident_package_manifest_hash", self.external_incident_verification.get("manifest_hash"), self.external_incident_manifest.get("integrity_hash"), "Incident verification report manifest hash matches Incident ZIP")
        elif self.require_guards_passed or self.require_no_open_recurrence:
            self._add_check("external", "tohk_incident_verification_required", "failed", "blocking", "Knowledge verification requires external Incident Board verification report.")
        if self.hub_verification_report_path:
            self.external_hub_verification = _read_json_file(self.hub_verification_report_path)
            self._add_exact_check("external", "tohk_hub_verification_status", self.external_hub_verification.get("status"), source.get("hub_verification_status"), "Hub verification status")
            self._add_exact_check("external", "tohk_hub_verification_hash", verification_hash(self.external_hub_verification), source.get("hub_verification_report_hash"), "Hub verification report hash")
            self._add_exact_check("external", "tohk_hub_verification_source_hash", self.external_hub_verification.get("source_hash"), source.get("hub_report_hash"), "Hub report hash")

    def _read_external_incident_package(self) -> None:
        assert self.incident_board_package_path is not None
        path = self.incident_board_package_path
        if not path.exists() or not path.is_file():
            self._add_check("external", "tohk_incident_package_open", "failed", "blocking", "External Incident Board ZIP does not exist.")
            return
        self.external_incident_zip_sha256 = _sha256_file(path)
        self.external_incident_zip_size_bytes = os.stat(_fs_path(path)).st_size
        try:
            with zipfile.ZipFile(_fs_path(path), "r") as archive:
                self.external_incident_manifest = self._read_external_json_entry(archive, "trust-operations-incident-manifest.json")
                self.external_incidents_doc = self._read_external_json_entry(archive, "incidents.json")
                self.external_closeout_summary = self._read_external_json_entry(archive, "closeout-summary.json")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("external", "tohk_incident_package_open", "failed", "blocking", f"External Incident Board ZIP cannot be opened: {exc}")
            return
        self._add_check("external", "tohk_incident_package_open", "passed", "blocking", "External Incident Board ZIP can be opened.")
        self._add_hash_check("external", "tohk_incident_package_manifest_integrity", self.external_incident_manifest.get("integrity_hash"), incident_manifest_hash(self.external_incident_manifest), "Incident package manifest integrity")
        self._add_hash_check("external", "tohk_incident_package_incidents_integrity", self.external_incidents_doc.get("integrity_hash"), incident_hash(self.external_incidents_doc), "Incident package incidents integrity")
        self._add_hash_check("external", "tohk_incident_package_closeouts_integrity", self.external_closeout_summary.get("integrity_hash"), incident_hash(self.external_closeout_summary), "Incident package closeout summary integrity")

    def _read_external_json_entry(self, archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
        try:
            value = json.loads(archive.read(name).decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return _as_document(value)

    def _verify_external_incident_semantics(self) -> None:
        if not self.external_incidents_doc:
            return
        facts = self._external_incident_facts()
        entries = _as_list(self.entries_doc.get("entries"))
        guards = _as_list(self.guards_doc.get("guards"))
        entry_by_incident_hash: dict[str, dict[str, Any]] = {}
        duplicate_entries: list[str] = []
        extra_entries: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            incident_ref = str((_as_document(entry.get("source"))).get("incident_hash") or "")
            if not incident_ref:
                extra_entries.append(str(entry.get("entry_id") or "missing-incident-hash"))
                continue
            if incident_ref in entry_by_incident_hash:
                duplicate_entries.append(str(entry.get("entry_id") or incident_ref))
            entry_by_incident_hash[incident_ref] = entry
            if incident_ref not in facts and entry.get("status") != "hidden":
                extra_entries.append(str(entry.get("entry_id") or incident_ref))
        missing_entries = [
            str(fact.get("incident_id") or incident_hash_value)
            for incident_hash_value, fact in facts.items()
            if incident_hash_value not in entry_by_incident_hash
        ]
        self._add_check("external", "tohk_entry_external_required_incidents", "failed" if missing_entries else "passed", "blocking", "Eligible external incidents missing Knowledge entries: " + ", ".join(missing_entries[:5]) if missing_entries else "All eligible external incidents have Knowledge entries.")
        self._add_check("external", "tohk_entry_external_duplicate_incidents", "failed" if duplicate_entries else "passed", "blocking", "Duplicate Knowledge entries for incidents: " + ", ".join(duplicate_entries[:5]) if duplicate_entries else "No duplicate Knowledge incident bindings.")
        self._add_check("external", "tohk_entry_external_no_unbound_entries", "failed" if extra_entries else "passed", "blocking", "Knowledge entries not backed by current external incidents: " + ", ".join(extra_entries[:5]) if extra_entries else "All active Knowledge entries are backed by external incidents.")
        fact_mismatches: list[str] = []
        for incident_hash_value, fact in facts.items():
            entry = entry_by_incident_hash.get(incident_hash_value)
            if not entry:
                continue
            if not _entry_matches_external_fact(entry, fact, self.source_summary):
                fact_mismatches.append(str(entry.get("entry_id") or fact.get("incident_id") or incident_hash_value))
        self._add_check("external", "tohk_entry_external_fact_binding", "failed" if fact_mismatches else "passed", "blocking", "Knowledge entries do not match external Incident facts: " + ", ".join(fact_mismatches[:5]) if fact_mismatches else "Knowledge entries match external Incident facts.")
        guard_type_mismatches: list[str] = []
        active_guards = [guard for guard in guards if isinstance(guard, dict) and guard.get("status") not in {"archived", "manual_required"}]
        for guard in active_guards:
            incident_ref = str((_as_document(guard.get("source"))).get("incident_hash") or "")
            fact = _as_document(facts.get(incident_ref))
            if fact and guard.get("guard_type") != fact.get("recommended_guard", {}).get("guard_type"):
                guard_type_mismatches.append(str(guard.get("guard_id") or incident_ref))
        self._add_check("external", "tohk_guard_external_recommended_type_binding", "failed" if guard_type_mismatches else "passed", "blocking", "Regression guards do not match external recommended guard type: " + ", ".join(guard_type_mismatches[:5]) if guard_type_mismatches else "Regression guard types match external Incident recommendations.")
        covered = {str((_as_document(guard.get("source"))).get("knowledge_entry_hash") or "") for guard in active_guards}
        missing_external_guard: list[str] = []
        for incident_hash_value, fact in facts.items():
            if fact.get("severity") not in {"critical", "high"}:
                continue
            entry = entry_by_incident_hash.get(incident_hash_value)
            if not entry or entry.get("status") == "hidden" or entry.get("integrity_hash") not in covered:
                missing_external_guard.append(str(fact.get("incident_id") or incident_hash_value))
        self._add_check("external", "tohk_external_high_severity_guard_coverage", "failed" if missing_external_guard else "passed", "blocking", "External high severity incidents missing active regression guards: " + ", ".join(missing_external_guard[:5]) if missing_external_guard else "External high severity incidents are covered by active guards.")

    def _external_incident_facts(self) -> dict[str, ImplementationDocument]:
        incidents = _as_list(self.external_incidents_doc.get("incidents"))
        closeouts = _as_list(self.external_closeout_summary.get("closeouts"))
        closeout_by_id = {str(closeout.get("incident_id") or ""): closeout for closeout in closeouts if isinstance(closeout, dict)}
        facts: dict[str, dict[str, Any]] = {}
        for incident in incidents:
            if not isinstance(incident, dict) or incident.get("status") != "closed" or incident.get("stale"):
                continue
            incident_integrity = str(incident.get("integrity_hash") or "")
            if not incident_integrity or incident_integrity != incident_hash(incident):
                continue
            incident_id = str(incident.get("incident_id") or "")
            closeout = closeout_by_id.get(incident_id) or {}
            closeout_integrity = str(closeout.get("integrity_hash") or "")
            if closeout.get("status") != "passed" or not closeout_integrity or closeout_integrity != incident_hash(closeout):
                continue
            detected = _as_document(incident.get("detected_from"))
            classification = _classify_incident(incident)
            facts[incident_integrity] = {
                "incident_id": incident_id,
                "severity": incident.get("severity"),
                "category": incident.get("category"),
                "component_type": detected.get("component_type"),
                "component_id": detected.get("component_id"),
                "source_fingerprint": detected.get("source_fingerprint"),
                "closeout_hash": closeout_integrity,
                "failure_mode": classification["failure_mode"],
                "root_cause": classification["root_cause"],
                "preventive_pattern": classification["preventive_pattern"],
                "recommended_guard": {
                    "guard_type": classification["guard_type"],
                    "title": classification["guard_title"],
                    "reason": classification["guard_reason"],
                },
            }
        return facts

    def _verify_requirements(self) -> None:
        runs_summary = _as_document(self.runs_doc.get("summary"))
        recurrence_summary = _as_document(self.recurrence.get("summary"))
        failed_runs = int(runs_summary.get("failed_count") or 0)
        guard_count = int((_as_document(self.guards_doc.get("summary"))).get("active_guard_count") or 0)
        passed_runs = int(runs_summary.get("passed_count") or 0)
        recurrence_count = int(recurrence_summary.get("recurrence_count") or 0)
        self._add_check("requirements", "tohk_require_guards_passed", "passed" if (not self.require_guards_passed or (guard_count > 0 and failed_runs == 0 and passed_runs >= guard_count)) else "failed", "blocking", "Regression guards have passed runs." if failed_runs == 0 and passed_runs >= guard_count else "Regression guards are missing or failed.")
        self._add_check("requirements", "tohk_require_no_open_recurrence", "passed" if (not self.require_no_open_recurrence or recurrence_count == 0) else "failed", "blocking", "No recurrence detected." if recurrence_count == 0 else "Incident recurrence remains open.")

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
            "base": self.base,
            "report": self.report,
            "entries": self.entries_doc,
            "guards": self.guards_doc,
            "runs": self.runs_doc,
            "recurrence": self.recurrence,
            "source": self.source_summary,
        }.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "tohk_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Knowledge package." if findings else "No sensitive values found in Knowledge package.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        summary = {
            "hub_id": self.base.get("hub_id"),
            "entry_count": int((_as_document(self.entries_doc.get("summary"))).get("entry_count") or 0),
            "guard_count": int((_as_document(self.guards_doc.get("summary"))).get("guard_count") or 0),
            "guards_passed_count": int((_as_document(self.runs_doc.get("summary"))).get("passed_count") or 0),
            "guard_failed_count": int((_as_document(self.runs_doc.get("summary"))).get("failed_count") or 0),
            "recurrence_count": int((_as_document(self.recurrence.get("summary"))).get("recurrence_count") or 0),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_KNOWLEDGE_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": self.base.get("integrity_hash"),
                "incident_verification_report_hash": self.source_summary.get("incident_verification_report_hash"),
                "incident_zip_sha256": self.source_summary.get("incident_zip_sha256"),
                "incident_zip_size_bytes": self.external_incident_zip_size_bytes,
                "incident_manifest_hash": self.source_summary.get("incident_manifest_hash"),
                "hub_verification_report_hash": self.source_summary.get("hub_verification_report_hash"),
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

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _read_json_file(path: Path) -> ImplementationDocument:
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return _as_document(value)


def _entry_matches_external_fact(entry: ImplementationDocument, fact: ImplementationDocument, source_summary: ImplementationDocument) -> bool:
    source = _as_document(entry.get("source"))
    expected_source = {
        "incident_hash": source.get("incident_hash"),
        "closeout_hash": source.get("closeout_hash"),
        "incident_verification_report_hash": source.get("incident_verification_report_hash"),
        "hub_verification_report_hash": source.get("hub_verification_report_hash"),
        "source_fingerprint": source.get("source_fingerprint"),
    }
    expected_source_hash = stable_hash(expected_source)
    recommended = _as_document(entry.get("recommended_guard"))
    return (
        entry.get("incident_id") == fact.get("incident_id")
        and entry.get("severity") == fact.get("severity")
        and entry.get("category") == fact.get("category")
        and entry.get("component_type") == fact.get("component_type")
        and entry.get("component_id") == fact.get("component_id")
        and entry.get("failure_mode") == fact.get("failure_mode")
        and entry.get("root_cause") == fact.get("root_cause")
        and entry.get("preventive_pattern") == fact.get("preventive_pattern")
        and recommended.get("guard_type") == fact.get("recommended_guard", {}).get("guard_type")
        and recommended.get("title") == fact.get("recommended_guard", {}).get("title")
        and recommended.get("reason") == fact.get("recommended_guard", {}).get("reason")
        and source.get("closeout_hash") == fact.get("closeout_hash")
        and source.get("incident_verification_report_hash") == source_summary.get("incident_verification_report_hash")
        and source.get("hub_verification_report_hash") == source_summary.get("hub_verification_report_hash")
        and source.get("source_fingerprint") == fact.get("source_fingerprint")
        and entry.get("source_hash") == expected_source_hash
    )


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
