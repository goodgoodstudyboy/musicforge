from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list
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
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_assurance_watch_contracts import ASSURANCE_WATCH_ARCHIVE_ENTRIES as ASSURANCE_WATCH_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION, watch_hash as watch_hash, watch_manifest_hash as watch_manifest_hash


TRUST_OPERATIONS_ASSURANCE_WATCH_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_verification"
TRUST_OPERATIONS_ASSURANCE_WATCH_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_trust_operations_assurance_watch_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_clear: bool = False,
    require_current: bool = False,
    assurance_archive_path: Path | str | None = None,
    assurance_verification_report_path: Path | str | None = None,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _WatchVerifier(
        Path(zip_path),
        strict=strict,
        require_clear=require_clear,
        require_current=require_current,
        assurance_archive_path=Path(assurance_archive_path) if assurance_archive_path else None,
        assurance_verification_report_path=Path(assurance_verification_report_path) if assurance_verification_report_path else None,
        hub_package_path=Path(hub_package_path) if hub_package_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_assurance_watch_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_assurance_watch_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Assurance Watch verification")
    print(f"status: {report.get('status')}")
    print(f"queue: {summary.get('queue_id') or '-'}")
    print(f"clear: {report.get('clear')}")
    print(f"overdue: {report.get('overdue_count')}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def trust_operations_assurance_watch_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _WatchVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_clear: bool,
        require_current: bool,
        assurance_archive_path: Path | None,
        assurance_verification_report_path: Path | None,
        hub_package_path: Path | None,
        hub_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_clear = require_clear
        self.require_current = require_current
        self.assurance_archive_path = assurance_archive_path
        self.assurance_verification_report_path = assurance_verification_report_path
        self.hub_package_path = hub_package_path
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
        self.queue: dict[str, Any] = {}
        self.schedule: dict[str, Any] = {}
        self.run_index: dict[str, Any] = {}
        self.action_pack: dict[str, Any] = {}
        self.external_summary: dict[str, Any] = {}
        self.history_events: list[dict[str, Any]] = []
        self.assurance_report: dict[str, Any] = {}
        self.assurance_manifest: dict[str, Any] = {}
        self.hub_report: dict[str, Any] = {}
        self.hub_manifest: dict[str, Any] = {}
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
            self._add_check("zip", "toaw_zip_open", "failed", "blocking", "Assurance Watch ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "toaw_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "toaw_zip_open", "failed", "blocking", f"Assurance Watch ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "toaw_zip_open", "passed", "blocking", "Assurance Watch ZIP can be opened.")
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
        self._add_check("zip", "toaw_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP uncompressed size is within limit.")
        self._add_check("zip", "toaw_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "toaw_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "toaw_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "toaw_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")
        missing = sorted(ASSURANCE_WATCH_ARCHIVE_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - ASSURANCE_WATCH_ARCHIVE_ENTRIES)
        self._add_check("zip", "toaw_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Watch entries: " + ", ".join(missing) if missing else "All required Watch entries exist.")
        self._add_check("zip", "toaw_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Watch entries: " + ", ".join(unexpected[:5]) if unexpected else "Watch ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-assurance-watch-manifest.json", "manifest", "toaw_manifest_parse")
        self.queue = self._read_json_entry(archive, "watch-queue.json", "queue", "toaw_queue_parse")
        self.schedule = self._read_json_entry(archive, "schedule-snapshot.json", "schedule", "toaw_schedule_parse")
        self.run_index = self._read_json_entry(archive, "assurance-run-index.json", "run_index", "toaw_run_index_parse")
        self.action_pack = self._read_json_entry(archive, "drift-action-pack.json", "action_pack", "toaw_action_pack_parse")
        self.external_summary = self._read_json_entry(archive, "external-verification-summary.json", "external_summary", "toaw_external_summary_parse")
        try:
            history = archive.read("watch-history.jsonl").decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            history = ""
        self.history_events = []
        for line in history.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                self.history_events.append(item)

    def _read_json_entry(self, archive: zipfile.ZipFile, entry: str, label: str, check_id: str) -> ImplementationDocument:
        try:
            value = json.loads(archive.read(entry).decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(label, check_id, "failed", "blocking", f"{entry} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(label, check_id, "failed", "blocking", f"{entry} is not a JSON object.")
            return {}
        self._add_check(label, check_id, "passed", "blocking", f"{entry} parsed.")
        return value

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_exact_check("manifest", "toaw_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE, "Manifest package_type")
        self._add_exact_check("manifest", "toaw_manifest_integrity", self.manifest.get("integrity_hash"), watch_manifest_hash(self.manifest), "Manifest integrity hash")
        file_rows = _as_list(self.manifest.get("files"))
        expected_paths = sorted(ASSURANCE_WATCH_ARCHIVE_ENTRIES - {"trust-operations-assurance-watch-manifest.json"})
        manifest_paths = sorted(str(row.get("path") or "") for row in file_rows if isinstance(row, dict))
        self._add_exact_check("manifest", "toaw_manifest_fixed_file_list", manifest_paths, expected_paths, "Manifest file list matches fixed entries")
        by_path = {str(row.get("path") or ""): row for row in file_rows if isinstance(row, dict)}
        for path in expected_paths:
            info = self.entry_map.get(path)
            row = by_path.get(path, {})
            if not info:
                continue
            data = archive.read(info.filename)
            self.files.append({"path": path, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            self._add_exact_check("manifest", "toaw_manifest_file_" + _safe_check_id(path), row.get("sha256"), hashlib.sha256(data).hexdigest(), f"{path} sha256")
            self._add_exact_check("manifest", "toaw_manifest_size_" + _safe_check_id(path), row.get("size_bytes"), len(data), f"{path} size")
        zip_meta = _as_document(self.manifest.get("zip"))
        if zip_meta:
            self._add_exact_check("manifest", "toaw_manifest_zip_entries_reference_only", sorted(zip_meta.get("entries") or []), sorted(self.entry_names), "manifest.zip.entries mirrors actual entries")

    def _verify_documents(self) -> None:
        self._add_exact_check("queue", "toaw_queue_package_type", self.queue.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE, "Queue package_type")
        self._add_exact_check("queue", "toaw_queue_integrity", self.queue.get("integrity_hash"), watch_hash(self.queue), "Queue integrity")
        self._add_exact_check("schedule", "toaw_schedule_package_type", self.schedule.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE, "Schedule package_type")
        self._add_exact_check("schedule", "toaw_schedule_integrity", self.schedule.get("integrity_hash"), watch_hash(self.schedule), "Schedule integrity")
        self._add_exact_check("run_index", "toaw_run_index_package_type", self.run_index.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE, "Run index package_type")
        self._add_exact_check("run_index", "toaw_run_index_integrity", self.run_index.get("integrity_hash"), watch_hash(self.run_index), "Run index integrity")
        self._add_exact_check("action_pack", "toaw_action_pack_package_type", self.action_pack.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE, "Action pack package_type")
        self._add_exact_check("action_pack", "toaw_action_pack_integrity", self.action_pack.get("integrity_hash"), watch_hash(self.action_pack), "Action pack integrity")
        self._add_exact_check("external", "toaw_external_summary_package_type", self.external_summary.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE, "External summary package_type")
        self._add_exact_check("external", "toaw_external_summary_integrity", self.external_summary.get("integrity_hash"), watch_hash(self.external_summary), "External summary integrity")
        source = {
            "schedule_hash": self.schedule.get("integrity_hash"),
            "assurance_run_index_hash": self.run_index.get("integrity_hash"),
            "external_verification_summary_hash": self.external_summary.get("integrity_hash"),
            "drift_action_pack_hash": self.action_pack.get("integrity_hash"),
        }
        self._add_exact_check("queue", "toaw_queue_source_hash", self.queue.get("source_hash"), stable_hash(source), "Queue source hash")
        manifest_source = _as_document(self.manifest.get("source"))
        self._add_exact_check("manifest", "toaw_manifest_queue_hash", manifest_source.get("watch_queue_hash"), self.queue.get("integrity_hash"), "Manifest queue hash")
        self._add_exact_check("manifest", "toaw_manifest_schedule_hash", manifest_source.get("schedule_hash"), self.schedule.get("integrity_hash"), "Manifest schedule hash")
        self._add_exact_check("manifest", "toaw_manifest_run_index_hash", manifest_source.get("assurance_run_index_hash"), self.run_index.get("integrity_hash"), "Manifest run index hash")
        self._add_exact_check("manifest", "toaw_manifest_action_pack_hash", manifest_source.get("drift_action_pack_hash"), self.action_pack.get("integrity_hash"), "Manifest action pack hash")
        self._add_exact_check("manifest", "toaw_manifest_external_summary_hash", manifest_source.get("external_verification_summary_hash"), self.external_summary.get("integrity_hash"), "Manifest external summary hash")

    def _verify_semantics(self) -> None:
        rows = [row for row in self.queue.get("rows", []) if isinstance(row, dict)]
        expected_rows, expected_action_pack = _expected_rows_and_action_pack(self.queue, self.schedule, self.run_index, self.generated_at)
        self._add_exact_check(
            "semantics",
            "toaw_watch_queue_rows_match_sources",
            [_row_projection(row) for row in rows],
            [_row_projection(row) for row in expected_rows],
            "Queue rows match schedule and assurance run index",
        )
        expected_actions = [
            {"hub_id": action.get("hub_id"), "action_type": action.get("action_type"), "severity": action.get("severity"), "reason": action.get("reason")}
            for action in expected_action_pack.get("actions", [])
            if isinstance(action, dict)
        ]
        actual_actions = [
            {"hub_id": action.get("hub_id"), "action_type": action.get("action_type"), "severity": action.get("severity"), "reason": action.get("reason")}
            for action in self.action_pack.get("actions", [])
            if isinstance(action, dict)
        ]
        self._add_exact_check("semantics", "toaw_action_pack_semantics_match", actual_actions, expected_actions, "Action pack matches queue row semantics")
        self._add_exact_check("semantics", "toaw_action_pack_summary_match_sources", self.action_pack.get("summary"), expected_action_pack.get("summary"), "Action pack summary matches source-derived actions")
        self._add_exact_check("semantics", "toaw_action_pack_status_match_sources", self.action_pack.get("status"), expected_action_pack.get("status"), "Action pack status matches source-derived actions")
        expected_summary = _queue_summary(expected_rows, expected_action_pack)
        self._add_exact_check("semantics", "toaw_watch_queue_semantics_match", self.queue.get("summary"), expected_summary, "Queue summary matches rows and actions")
        self._add_exact_check("semantics", "toaw_watch_queue_status_match", self.queue.get("status"), _queue_status(expected_summary), "Queue status matches summary")
        for action in self.action_pack.get("actions", []):
            if isinstance(action, dict):
                self._add_exact_check("semantics", "toaw_action_integrity_" + _safe_check_id(str(action.get("action_id") or "")), action.get("integrity_hash"), watch_hash(action), "Action integrity")

    def _read_external_sources(self) -> None:
        if self.assurance_verification_report_path:
            self.assurance_report = _read_json_file(self.assurance_verification_report_path)
        if self.assurance_archive_path:
            self.assurance_manifest = _read_zip_json(self.assurance_archive_path, "trust-operations-assurance-manifest.json")
        if self.hub_verification_report_path:
            self.hub_report = _read_json_file(self.hub_verification_report_path)
        if self.hub_package_path:
            self.hub_manifest = _read_zip_json(self.hub_package_path, "trust-operations-hub-manifest.json")

    def _verify_external_bindings(self) -> None:
        if self.require_current:
            if not self.assurance_archive_path:
                self._add_check("external", "toaw_assurance_archive_required", "failed", "blocking", "Current Watch verification requires an external Assurance archive.")
            if not self.assurance_verification_report_path:
                self._add_check("external", "toaw_assurance_verification_required", "failed", "blocking", "Current Watch verification requires an external Assurance verification report.")
            if not self.hub_package_path:
                self._add_check("external", "toaw_hub_package_required", "failed", "blocking", "Current Watch verification requires an external Hub package.")
            if not self.hub_verification_report_path:
                self._add_check("external", "toaw_hub_verification_required", "failed", "blocking", "Current Watch verification requires an external Hub verification report.")
        assurance_row = _external_item(self.external_summary, "assurance")
        if self.assurance_report:
            archive_sha = _sha256_file(self.assurance_archive_path) if self.assurance_archive_path and self.assurance_archive_path.exists() else None
            archive_size = os.stat(_fs_path(self.assurance_archive_path)).st_size if self.assurance_archive_path and self.assurance_archive_path.exists() else None
            self._add_exact_check("external", "toaw_external_assurance_zip_sha256", assurance_row.get("zip_sha256"), archive_sha, "External Assurance ZIP sha256")
            self._add_exact_check("external", "toaw_external_assurance_zip_size_bytes", assurance_row.get("zip_size_bytes"), archive_size, "External Assurance ZIP size")
            self._add_exact_check("external", "toaw_external_assurance_manifest_hash", assurance_row.get("manifest_hash"), self.assurance_manifest.get("integrity_hash"), "External Assurance manifest hash")
            self._add_exact_check("external", "toaw_external_assurance_verification_hash", assurance_row.get("verification_report_hash"), verification_hash(self.assurance_report), "External Assurance verification report hash")
            self._add_exact_check("external", "toaw_external_assurance_status", assurance_row.get("verification_status"), self.assurance_report.get("status"), "External Assurance verification status")
            self._add_exact_check("external", "toaw_external_assurance_binding", self.assurance_report.get("zip_sha256"), archive_sha, "Assurance report binds current Assurance ZIP")
            self._add_exact_check("external", "toaw_external_assurance_manifest_binding", self.assurance_report.get("manifest_hash"), self.assurance_manifest.get("integrity_hash"), "Assurance report binds current Assurance manifest")
            for run in self.run_index.get("runs", []) if isinstance(self.run_index.get("runs"), list) else []:
                if not isinstance(run, dict) or not run.get("run_id"):
                    continue
                safe_id = _safe_check_id(str(run.get("hub_id") or run.get("run_id") or "run"))
                self._add_exact_check("external", "toaw_run_index_assurance_zip_" + safe_id, run.get("archive_zip_sha256"), assurance_row.get("zip_sha256"), "Run index Assurance ZIP sha256")
                self._add_exact_check("external", "toaw_run_index_assurance_manifest_" + safe_id, run.get("archive_manifest_hash"), assurance_row.get("manifest_hash"), "Run index Assurance manifest hash")
                self._add_exact_check("external", "toaw_run_index_assurance_verification_" + safe_id, run.get("verification_report_hash"), assurance_row.get("verification_report_hash"), "Run index Assurance verification hash")
                self._add_exact_check("external", "toaw_run_index_assurance_status_" + safe_id, run.get("verification_status"), assurance_row.get("verification_status"), "Run index Assurance verification status")
        hub_row = _external_item(self.external_summary, "hub")
        if self.hub_report:
            hub_sha = _sha256_file(self.hub_package_path) if self.hub_package_path and self.hub_package_path.exists() else None
            hub_size = os.stat(_fs_path(self.hub_package_path)).st_size if self.hub_package_path and self.hub_package_path.exists() else None
            self._add_exact_check("external", "toaw_external_hub_zip_sha256", hub_row.get("zip_sha256"), hub_sha, "External Hub ZIP sha256")
            self._add_exact_check("external", "toaw_external_hub_zip_size_bytes", hub_row.get("zip_size_bytes"), hub_size, "External Hub ZIP size")
            self._add_exact_check("external", "toaw_external_hub_manifest_hash", hub_row.get("manifest_hash"), self.hub_manifest.get("integrity_hash"), "External Hub manifest hash")
            self._add_exact_check("external", "toaw_external_hub_verification_hash", hub_row.get("verification_report_hash"), verification_hash(self.hub_report), "External Hub verification report hash")
            self._add_exact_check("external", "toaw_external_hub_status", hub_row.get("verification_status"), self.hub_report.get("status"), "External Hub verification status")
            self._add_exact_check("external", "toaw_external_hub_binding", self.hub_report.get("zip_sha256"), hub_sha, "Hub report binds current Hub ZIP")
            self._add_exact_check("external", "toaw_external_hub_manifest_binding", self.hub_report.get("manifest_hash"), self.hub_manifest.get("integrity_hash"), "Hub report binds current Hub manifest")

    def _verify_requirements(self) -> None:
        summary = _as_document(self.queue.get("summary"))
        clear = self.queue.get("status") == "clear" and int(summary.get("overdue_count") or 0) == 0 and int(summary.get("blocking_action_count") or 0) == 0 and int(summary.get("failed_count") or 0) == 0
        self._add_check("requirements", "toaw_require_clear", "passed" if clear or not self.require_clear else "failed", "blocking", "Assurance Watch queue is clear." if clear else "Assurance Watch queue is not clear.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in archive.infolist():
            if info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            lower = info.filename.lower()
            if not lower.endswith((".json", ".jsonl", ".txt", ".md", ".html")):
                continue
            try:
                text = archive.read(info.filename).decode("utf-8", errors="ignore")
            except (KeyError, OSError):
                continue
            if _contains_sensitive_text(text):
                findings.append({"entry": info.filename})
        self.redaction_findings = findings
        self._add_check("redaction", "toaw_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive or local path text found." if findings else "No sensitive text found.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
        warnings = [check for check in self.checks if check.get("status") in {"failed", "warning"} and check.get("severity") != "blocking"]
        summary = _as_document(self.queue.get("summary"))
        report = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_VERIFICATION_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_VERIFICATION_PACKAGE_TYPE,
            "status": "failed" if blockers else "passed",
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash"),
            "queue_hash": self.queue.get("integrity_hash"),
            "source_hash": self.queue.get("source_hash"),
            "clear": self.queue.get("status") == "clear" and not blockers,
            "overdue_count": int(summary.get("overdue_count") or 0),
            "blocking_action_count": int(summary.get("blocking_action_count") or 0),
            "assurance_verification_report_hashes": [
                item.get("verification_report_hash")
                for item in self.external_summary.get("items", [])
                if isinstance(item, dict) and item.get("component_type") == "assurance" and item.get("verification_report_hash")
            ],
            "hub_verification_report_hashes": [verification_hash(self.hub_report)] if self.hub_report else [],
            "generated_at": self.generated_at,
            "summary": {"queue_id": self.queue.get("queue_id"), "schedule_id": self.queue.get("schedule_id"), **summary},
            "checks": self.checks,
            "blockers": blockers,
            "warnings": warnings,
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_check(self, category: str, check_id: str, status: str, severity: str, message: str) -> None:
        item = {"category": category, "check_id": check_id, "status": status, "severity": severity, "message": message}
        item["integrity_hash"] = stable_hash(item)
        self.checks.append(item)

    def _add_exact_check(self, category: str, check_id: str, actual: Any, expected: Any, message: str) -> None:
        self._add_check(category, check_id, "passed" if actual == expected else "failed", "blocking", message if actual == expected else f"{message}: expected {expected!r}, got {actual!r}")


def _queue_summary(rows: list[ImplementationDocument], action_pack: ImplementationDocument) -> ImplementationDocument:
    actions_summary = _as_document(action_pack.get("summary"))
    return {
        "hub_count": len(rows),
        "clear_count": sum(1 for row in rows if row.get("readiness") == "clear"),
        "due_count": sum(1 for row in rows if row.get("due_status") == "due"),
        "overdue_count": sum(1 for row in rows if row.get("due_status") == "overdue"),
        "stale_count": sum(1 for row in rows if row.get("drift_status") == "stale"),
        "failed_count": sum(1 for row in rows if row.get("readiness") == "blocked" or row.get("drift_status") in {"failed", "missing"}),
        "blocking_action_count": int(actions_summary.get("blocking_count") or 0),
        "manual_action_count": int(actions_summary.get("manual_required_count") or 0),
    }


def _queue_status(summary: ImplementationDocument) -> str:
    if int(summary.get("failed_count") or 0) or int(summary.get("overdue_count") or 0) or int(summary.get("blocking_action_count") or 0):
        return "blocked"
    if int(summary.get("due_count") or 0) or int(summary.get("manual_action_count") or 0):
        return "warning"
    return "clear"


def _expected_rows_and_action_pack(queue: ImplementationDocument, schedule: ImplementationDocument, run_index: ImplementationDocument, now: str) -> tuple[list[ImplementationDocument], ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    queue_id = str(queue.get("queue_id") or "")
    hub_ids = _hub_ids_from_queue_or_run_index(queue, run_index)
    runs_by_hub = {str(row.get("hub_id") or ""): row for row in run_index.get("runs", []) if isinstance(row, dict)}
    cadence = _as_document(schedule.get("cadence"))
    interval_days = int(cadence.get("interval_days") or 7)
    grace_days = int(cadence.get("grace_days") or 1)
    requirements = _as_document(schedule.get("requirements"))
    require_verified = bool(requirements.get("require_latest_assurance_verified", True))
    for hub_id in hub_ids:
        run = runs_by_hub.get(hub_id, {"hub_id": hub_id, "status": "missing", "verification_status": "missing"})
        due_status, next_due_at = _due_status(str(run.get("verified_at") or run.get("created_at") or ""), now, interval_days, grace_days)
        reasons: list[str] = []
        readiness = "clear"
        drift_status = "clear"
        if not run.get("run_id"):
            due_status = "missing"
            readiness = "blocked"
            drift_status = "missing"
            reasons.append("assurance_run_missing")
        if run.get("status") not in {"passed", None}:
            readiness = "blocked"
            drift_status = "failed"
            reasons.append("assurance_run_failed")
        if require_verified and run.get("verification_status") != "passed":
            readiness = "blocked"
            drift_status = "failed" if run.get("verification_status") == "failed" else "missing"
            reasons.append("assurance_verification_not_passed")
        if due_status == "overdue":
            readiness = "blocked"
            reasons.append("assurance_overdue")
        elif due_status == "due" and readiness == "clear":
            readiness = "warning"
            reasons.append("assurance_due")
        row: ImplementationDocument = {
            "hub_id": hub_id,
            "latest_assurance_run_id": run.get("run_id"),
            "latest_assurance_status": run.get("status") or "missing",
            "latest_assurance_verified": run.get("verification_status") == "passed",
            "last_verified_at": run.get("verified_at"),
            "next_due_at": next_due_at,
            "due_status": due_status,
            "drift_status": drift_status,
            "readiness": readiness,
            "reasons": reasons,
            "action_ids": [],
        }
        for action_type, severity, reason in _expected_actions_for_row(row):
            action_id = f"toaa-{len(actions) + 1:06d}"
            action = {
                "action_id": action_id,
                "queue_id": queue_id,
                "hub_id": hub_id,
                "action_type": action_type,
                "status": "pending",
                "severity": severity,
                "reason": reason,
                "manual_required": True,
                "safe_to_auto_run": False,
            }
            action["integrity_hash"] = watch_hash(action)
            actions.append(action)
            row["action_ids"].append(action_id)
        row["integrity_hash"] = watch_hash(row)
        rows.append(row)
    action_pack: ImplementationDocument = {
        "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
        "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE,
        "queue_id": queue_id,
        "actions": actions,
        "summary": _action_summary(actions),
        "source": {"external_verification_summary_hash": _external_summary_hash_for_queue(queue)},
    }
    action_pack["status"] = "blocked" if action_pack["summary"]["blocking_count"] else "warning" if action_pack["summary"]["action_count"] else "clear"
    action_pack["integrity_hash"] = watch_hash(action_pack)
    return sorted(rows, key=lambda row: str(row.get("hub_id") or "")), action_pack


def _external_summary_hash_for_queue(queue: ImplementationDocument) -> str | None:
    source = _as_document(queue.get("source"))
    return source.get("external_verification_summary_hash")


def _hub_ids_from_queue_or_run_index(queue: ImplementationDocument, run_index: ImplementationDocument) -> list[str]:
    ids = [str(row.get("hub_id") or "") for row in queue.get("rows", []) if isinstance(row, dict) and row.get("hub_id")]
    if not ids:
        ids = [str(row.get("hub_id") or "") for row in run_index.get("runs", []) if isinstance(row, dict) and row.get("hub_id")]
    return sorted(dict.fromkeys(item for item in ids if item)) or ["hub"]


def _row_projection(row: ImplementationDocument) -> ImplementationDocument:
    keys = [
        "hub_id",
        "latest_assurance_run_id",
        "latest_assurance_status",
        "latest_assurance_verified",
        "last_verified_at",
        "next_due_at",
        "due_status",
        "drift_status",
        "readiness",
        "reasons",
        "action_ids",
    ]
    return {key: row.get(key) for key in keys}


def _action_summary(actions: list[ImplementationDocument]) -> ImplementationDocument:
    return {
        "action_count": len(actions),
        "blocking_count": sum(1 for action in actions if action.get("severity") in {"critical", "high"}),
        "manual_required_count": sum(1 for action in actions if action.get("manual_required")),
        "safe_auto_count": sum(1 for action in actions if action.get("safe_to_auto_run")),
    }


def _due_status(last_at: str, now: str, interval_days: int, grace_days: int) -> tuple[str, str | None]:
    base = _parse_dt(last_at)
    current = _parse_dt(now)
    if not base or not current:
        return "unknown", None
    next_due = base + timedelta(days=max(0, interval_days))
    if current <= next_due:
        return "not_due", next_due.isoformat()
    if current <= next_due + timedelta(days=max(0, grace_days)):
        return "due", next_due.isoformat()
    return "overdue", next_due.isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _expected_actions_for_row(row: ImplementationDocument) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    due_status = row.get("due_status")
    if due_status == "missing":
        actions.append(("refresh_assurance", "high", "Assurance run is missing."))
    elif due_status == "overdue":
        actions.append(("refresh_assurance", "high", "Assurance run is overdue."))
    elif due_status == "due":
        actions.append(("refresh_assurance", "medium", "Assurance run is due."))
    if "assurance_verification_not_passed" in row.get("reasons", []):
        actions.append(("verify_assurance_archive", "high", "Assurance archive verification is missing or failed."))
    if "assurance_run_failed" in row.get("reasons", []):
        actions.append(("manual_delivery_review_required", "high", "Assurance run failed and requires manual review."))
    return actions


def _external_item(summary: ImplementationDocument, component_type: str) -> ImplementationDocument:
    for item in summary.get("items", []) if isinstance(summary.get("items"), list) else []:
        if isinstance(item, dict) and item.get("component_type") == component_type:
            return item
    return {}


def _read_json_file(path: Path | None) -> ImplementationDocument:
    if not path:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return _as_document(value)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _read_zip_json(zip_path: Path | None, entry: str) -> ImplementationDocument:
    if not zip_path:
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _sha256_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or lower.endswith(".zip")


def _safe_check_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower() or "item"


def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _fs_path(path: Path) -> str:
    return str(path)
