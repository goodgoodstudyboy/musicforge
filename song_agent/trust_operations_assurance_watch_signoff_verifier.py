from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.projectio import write_json
from song_agent.public_trust_center_publication_monitoring import verification_hash
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash
from song_agent.trust_operations_assurance_watch_signoff import (
    ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES,
    TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
    TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE,
    watch_signoff_hash,
    watch_signoff_manifest_hash,
)


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_verification"
TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_trust_operations_assurance_watch_signoff_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    watch_package_path: Path | str | None = None,
    watch_verification_report_path: Path | str | None = None,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    continuous_assurance_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _WatchSignoffVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        require_current=require_current,
        watch_package_path=Path(watch_package_path) if watch_package_path else None,
        watch_verification_report_path=Path(watch_verification_report_path) if watch_verification_report_path else None,
        hub_package_path=Path(hub_package_path) if hub_package_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        continuous_assurance_report_path=Path(continuous_assurance_report_path) if continuous_assurance_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_assurance_watch_signoff_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_assurance_watch_signoff_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Trust Operations Assurance Watch Signoff Archive verification")
    print(f"status: {report.get('status')}")
    print(f"queue: {summary.get('queue_id') or '-'}")
    print(f"signoff: {summary.get('signoff_id') or '-'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")


def trust_operations_assurance_watch_signoff_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _WatchSignoffVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_signed: bool,
        require_current: bool,
        watch_package_path: Path | None,
        watch_verification_report_path: Path | None,
        hub_package_path: Path | None,
        hub_verification_report_path: Path | None,
        continuous_assurance_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_signed = require_signed
        self.require_current = require_current
        self.watch_package_path = watch_package_path
        self.watch_verification_report_path = watch_verification_report_path
        self.hub_package_path = hub_package_path
        self.hub_verification_report_path = hub_verification_report_path
        self.continuous_assurance_report_path = continuous_assurance_report_path
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
        self.closeout: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.queue_summary: dict[str, Any] = {}
        self.action_summary: dict[str, Any] = {}
        self.external_summary: dict[str, Any] = {}
        self.change_requests_doc: dict[str, Any] = {}
        self.history_events: list[dict[str, Any]] = []
        self.watch_report: dict[str, Any] = {}
        self.watch_manifest: dict[str, Any] = {}
        self.hub_report: dict[str, Any] = {}
        self.hub_manifest: dict[str, Any] = {}
        self.assurance_report: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_history()
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
            self._add_check("zip", "toaws_zip_open", "failed", "blocking", "Assurance Watch Signoff archive ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "toaws_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "toaws_zip_open", "failed", "blocking", f"Assurance Watch Signoff archive ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "toaws_zip_open", "passed", "blocking", "Assurance Watch Signoff archive ZIP can be opened.")
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
        self._add_check("zip", "toaws_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP uncompressed size is within limit.")
        self._add_check("zip", "toaws_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "toaws_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "toaws_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "toaws_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")
        missing = sorted(ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES)
        self._add_check("zip", "toaws_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Watch Signoff entries: " + ", ".join(missing) if missing else "All required Watch Signoff entries exist.")
        self._add_check("zip", "toaws_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Watch Signoff entries: " + ", ".join(unexpected[:5]) if unexpected else "Watch Signoff ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-assurance-watch-signoff-manifest.json", "manifest", "toaws_manifest_parse")
        self.closeout = self._read_json_entry(archive, "watch-closeout.json", "closeout", "toaws_closeout_parse")
        self.signoff = self._read_json_entry(archive, "watch-signoff.json", "signoff", "toaws_signoff_parse")
        self.queue_summary = self._read_json_entry(archive, "watch-queue-summary.json", "queue_summary", "toaws_queue_summary_parse")
        self.action_summary = self._read_json_entry(archive, "drift-action-pack-summary.json", "action_summary", "toaws_action_summary_parse")
        self.external_summary = self._read_json_entry(archive, "external-verification-summary.json", "external_summary", "toaws_external_summary_parse")
        self.change_requests_doc = self._read_json_entry(archive, "change-requests.json", "change_requests", "toaws_change_requests_parse")
        try:
            raw = archive.read("watch-signoff-history.jsonl").decode("utf-8")
            for line in raw.splitlines():
                item = json.loads(line)
                if isinstance(item, dict):
                    self.history_events.append(item)
            self._add_check("history", "toaws_history_parse", "passed", "blocking", "watch-signoff-history.jsonl parsed.")
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check("history", "toaws_history_parse", "failed", "blocking", f"watch-signoff-history.jsonl cannot be parsed: {exc}")

    def _read_json_entry(self, archive: zipfile.ZipFile, entry: str, label: str, check_id: str) -> dict[str, Any]:
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
        self._add_exact_check("manifest", "toaws_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE, "Manifest package_type")
        self._add_hash_check("manifest", "toaws_manifest_integrity", self.manifest.get("integrity_hash"), watch_signoff_manifest_hash(self.manifest), "Manifest integrity")
        file_rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        expected_paths = sorted(ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES - {"trust-operations-assurance-watch-signoff-manifest.json"})
        manifest_paths = sorted(str(row.get("path") or "") for row in file_rows if isinstance(row, dict))
        self._add_exact_check("manifest", "toaws_manifest_fixed_file_list", manifest_paths, expected_paths, "Manifest file list matches fixed entries")
        by_path = {str(row.get("path") or ""): row for row in file_rows if isinstance(row, dict)}
        mismatches: list[str] = []
        for path in expected_paths:
            info = self.entry_map.get(path)
            row = by_path.get(path, {})
            if not info:
                continue
            data = archive.read(info.filename)
            actual_sha = hashlib.sha256(data).hexdigest()
            actual_size = len(data)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha})
            if row.get("sha256") != actual_sha or row.get("size_bytes") != actual_size:
                mismatches.append(path)
        self._add_check("manifest", "toaws_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        zip_meta = self.manifest.get("zip") if isinstance(self.manifest.get("zip"), dict) else {}
        if zip_meta:
            self._add_exact_check("manifest", "toaws_manifest_zip_entries_reference_only", sorted(zip_meta.get("entries") or []), sorted(self.entry_names), "manifest.zip.entries mirrors actual entries")

    def _verify_documents(self) -> None:
        closeout_source = self.closeout.get("source") if isinstance(self.closeout.get("source"), dict) else {}
        signoff_source = self.signoff.get("source") if isinstance(self.signoff.get("source"), dict) else {}
        self._add_exact_check("closeout", "toaws_closeout_package_type", self.closeout.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE, "Closeout package_type")
        self._add_hash_check("closeout", "toaws_closeout_integrity", self.closeout.get("integrity_hash"), watch_signoff_hash(self.closeout), "Closeout integrity")
        self._add_exact_check("closeout", "toaws_closeout_status", self.closeout.get("status"), "passed", "Closeout status")
        self._add_exact_check("signoff", "toaws_signoff_package_type", self.signoff.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE, "Signoff package_type")
        self._add_hash_check("signoff", "toaws_signoff_integrity", self.signoff.get("integrity_hash"), watch_signoff_hash(self.signoff), "Signoff integrity")
        self._add_exact_check("signoff", "toaws_signoff_status", self.signoff.get("status"), "signed", "Signoff status")
        expected_payload_hash = stable_hash(
            {
                "queue_id": self.signoff.get("queue_id"),
                "closeout_id": self.signoff.get("closeout_id"),
                "signed_by": self.signoff.get("signed_by"),
                "role": self.signoff.get("role"),
                "reason": self.signoff.get("reason"),
                "source": signoff_source,
                "decision": self.signoff.get("decision"),
            }
        )
        self._add_exact_check("signoff", "toaws_signoff_payload_hash", self.signoff.get("payload_hash"), expected_payload_hash, "Signoff payload hash")
        self._add_exact_check("signoff", "toaws_signoff_closeout_hash", signoff_source.get("closeout_integrity_hash"), self.closeout.get("integrity_hash"), "Signoff closeout hash")
        self._add_exact_check("signoff", "toaws_signoff_watch_zip_sha256", signoff_source.get("watch_zip_sha256"), closeout_source.get("watch_zip_sha256"), "Signoff Watch ZIP sha256")
        self._add_exact_check("signoff", "toaws_signoff_watch_verification_hash", signoff_source.get("watch_verification_report_hash"), closeout_source.get("watch_verification_report_hash"), "Signoff Watch verification hash")
        self._add_exact_check("queue_summary", "toaws_queue_summary_integrity", self.queue_summary.get("integrity_hash"), watch_signoff_hash(self.queue_summary), "Queue summary integrity")
        self._add_exact_check("action_summary", "toaws_action_summary_integrity", self.action_summary.get("integrity_hash"), watch_signoff_hash(self.action_summary), "Action summary integrity")
        self._add_exact_check("external", "toaws_external_summary_integrity", self.external_summary.get("integrity_hash"), watch_signoff_hash(self.external_summary), "External summary integrity")
        self._add_exact_check("change_requests", "toaws_change_requests_package_type", self.change_requests_doc.get("package_type"), TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, "Change Requests package_type")
        self._add_hash_check("change_requests", "toaws_change_requests_integrity", self.change_requests_doc.get("integrity_hash"), watch_signoff_hash(self.change_requests_doc), "Change Requests integrity")
        manifest_source = self.manifest.get("source") if isinstance(self.manifest.get("source"), dict) else {}
        self._add_exact_check("manifest", "toaws_manifest_closeout_hash", manifest_source.get("closeout_hash"), self.closeout.get("integrity_hash"), "Manifest closeout hash")
        self._add_exact_check("manifest", "toaws_manifest_signoff_hash", manifest_source.get("signoff_hash"), self.signoff.get("integrity_hash"), "Manifest signoff hash")
        self._add_exact_check("manifest", "toaws_manifest_history_hash", manifest_source.get("history_hash"), stable_hash({"events": self.history_events}), "Manifest history hash")
        self._add_exact_check("manifest", "toaws_manifest_queue_summary_hash", manifest_source.get("queue_summary_hash"), self.queue_summary.get("integrity_hash"), "Manifest queue summary hash")
        self._add_exact_check("manifest", "toaws_manifest_action_summary_hash", manifest_source.get("drift_action_pack_summary_hash"), self.action_summary.get("integrity_hash"), "Manifest action summary hash")
        self._add_exact_check("manifest", "toaws_manifest_external_summary_hash", manifest_source.get("external_verification_summary_hash"), self.external_summary.get("integrity_hash"), "Manifest external summary hash")

    def _verify_history(self) -> None:
        signoff_hash = str(self.signoff.get("integrity_hash") or "")
        signed_events = [item for item in self.history_events if item.get("event_type") == "watch_signoff_created" and item.get("signoff_hash") == signoff_hash]
        self._add_check("history", "toaws_history_signed_event", "passed" if signed_events else "failed", "blocking", "Signed history contains the current signoff hash." if signed_events else "Signed history is missing the current signoff hash.")
        reset_events = [item for item in self.history_events if item.get("event_type") == "watch_signoff_reset"]
        change_requests = self.change_requests_doc.get("change_requests") if isinstance(self.change_requests_doc.get("change_requests"), list) else []
        by_id = {str(item.get("change_request_id") or ""): item for item in change_requests if isinstance(item, dict)}
        bad_resets: list[str] = []
        for event in reset_events:
            cr = by_id.get(str(event.get("change_request_id") or ""))
            applied = cr.get("applied") if isinstance(cr, dict) and isinstance(cr.get("applied"), dict) else {}
            if not cr or cr.get("status") != "applied" or cr.get("integrity_hash") != event.get("change_request_hash") or applied.get("applied_signoff_reset_hash") != event.get("signoff_hash"):
                bad_resets.append(str(event.get("change_request_id") or "unknown"))
        self._add_check("history", "toaws_history_reset_cr_causality", "failed" if bad_resets else "passed", "blocking", "Reset events without applied CR: " + ", ".join(bad_resets[:5]) if bad_resets else "Reset events are bound to applied change requests.")

    def _read_external_sources(self) -> None:
        if self.watch_verification_report_path:
            self.watch_report = _read_json_file(self.watch_verification_report_path)
        elif self.require_current:
            self._add_check("external", "toaws_watch_verification_required", "failed", "blocking", "External Watch verification report is required.")
        if self.watch_package_path:
            self.watch_manifest = _read_zip_json(self.watch_package_path, "trust-operations-assurance-watch-manifest.json")
        elif self.require_current:
            self._add_check("external", "toaws_watch_package_required", "failed", "blocking", "External Watch package is required.")
        if self.hub_verification_report_path:
            self.hub_report = _read_json_file(self.hub_verification_report_path)
        elif self.require_current:
            self._add_check("external", "toaws_hub_verification_required", "failed", "blocking", "External Hub verification report is required.")
        if self.hub_package_path:
            self.hub_manifest = _read_zip_json(self.hub_package_path, "trust-operations-hub-manifest.json")
        if self.continuous_assurance_report_path:
            self.assurance_report = _read_json_file(self.continuous_assurance_report_path)
        elif self.require_current:
            self._add_check("external", "toaws_continuous_assurance_verification_required", "failed", "blocking", "Continuous Assurance verification report is required.")

    def _verify_external_bindings(self) -> None:
        source = self.signoff.get("source") if isinstance(self.signoff.get("source"), dict) else {}
        closeout_source = self.closeout.get("source") if isinstance(self.closeout.get("source"), dict) else {}
        if self.watch_report:
            watch_sha = _sha256_file(self.watch_package_path) if self.watch_package_path else None
            watch_size = os.stat(_fs_path(self.watch_package_path)).st_size if self.watch_package_path and self.watch_package_path.exists() else None
            self._add_exact_check("external", "toaws_watch_verification_package_type", self.watch_report.get("package_type"), "musicforge_trust_operations_assurance_watch_verification", "Watch verification package_type")
            self._add_exact_check("external", "toaws_watch_verification_status", self.watch_report.get("status"), "passed", "Watch verification status")
            self._add_exact_check("external", "toaws_watch_zip_sha256", self.watch_report.get("zip_sha256"), source.get("watch_zip_sha256"), "Watch verification ZIP sha256")
            self._add_exact_check("external", "toaws_watch_zip_size_bytes", self.watch_report.get("zip_size_bytes"), closeout_source.get("watch_zip_size_bytes"), "Watch verification ZIP size")
            self._add_exact_check("external", "toaws_watch_report_hash", verification_hash(self.watch_report), source.get("watch_verification_report_hash"), "Watch verification report hash")
            self._add_exact_check("external", "toaws_watch_report_zip_current", watch_sha, source.get("watch_zip_sha256"), "Current Watch package sha256")
            self._add_exact_check("external", "toaws_watch_report_size_current", watch_size, closeout_source.get("watch_zip_size_bytes"), "Current Watch package size")
            self._add_exact_check("external", "toaws_watch_manifest_hash", self.watch_manifest.get("integrity_hash"), source.get("watch_manifest_hash"), "Watch manifest hash")
        if self.hub_report:
            hub_sha = _sha256_file(self.hub_package_path) if self.hub_package_path else None
            self._add_exact_check("external", "toaws_hub_verification_status", self.hub_report.get("status"), "passed", "Hub verification status")
            self._add_exact_check("external", "toaws_hub_verification_hash", verification_hash(self.hub_report), source.get("hub_verification_report_hash"), "Hub verification report hash")
            hashes = {str(item) for item in self.watch_report.get("hub_verification_report_hashes", []) if item} if self.watch_report else set()
            if hashes:
                self._add_check("external", "toaws_watch_binds_hub_verification", "passed" if source.get("hub_verification_report_hash") in hashes else "failed", "blocking", "Watch verification binds Hub verification." if source.get("hub_verification_report_hash") in hashes else "Watch verification does not bind Hub verification.")
            if hub_sha is not None:
                self._add_exact_check("external", "toaws_hub_zip_sha256", hub_sha, closeout_source.get("hub_zip_sha256"), "Hub ZIP sha256")
            if self.hub_manifest:
                self._add_exact_check("external", "toaws_hub_manifest_hash", self.hub_manifest.get("integrity_hash"), closeout_source.get("hub_manifest_hash"), "Hub manifest hash")
        if self.assurance_report:
            self._add_exact_check("external", "toaws_continuous_assurance_status", self.assurance_report.get("status"), "passed", "Continuous Assurance verification status")
            self._add_exact_check("external", "toaws_continuous_assurance_hash", verification_hash(self.assurance_report), source.get("continuous_assurance_report_hash"), "Continuous Assurance verification hash")
            hashes = {str(item) for item in self.watch_report.get("assurance_verification_report_hashes", []) if item} if self.watch_report else set()
            if hashes:
                self._add_check("external", "toaws_watch_binds_continuous_assurance", "passed" if source.get("continuous_assurance_report_hash") in hashes else "failed", "blocking", "Watch verification binds Continuous Assurance." if source.get("continuous_assurance_report_hash") in hashes else "Watch verification does not bind Continuous Assurance.")

    def _verify_requirements(self) -> None:
        signed = self.signoff.get("status") == "signed"
        self._add_check("requirements", "toaws_require_signed", "passed" if signed or not self.require_signed else "failed", "blocking", "Assurance Watch signoff is signed." if signed else "Assurance Watch signoff is not signed.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in self.entry_infos:
            if not _is_text_scan_entry(info.filename) or int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info.filename).decode("utf-8", errors="ignore")
            except (KeyError, OSError):
                continue
            if _contains_sensitive_text(text):
                findings.append({"path": info.filename, "reason": "sensitive_text"})
        for name, doc in {"manifest": self.manifest, "closeout": self.closeout, "signoff": self.signoff, "queue_summary": self.queue_summary, "action_summary": self.action_summary, "external": self.external_summary, "change_requests": self.change_requests_doc}.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{name}:{path}", "reason": "sensitive_value"})
        self._add_check("security", "toaws_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Assurance Watch Signoff archive." if findings else "No sensitive values found in Assurance Watch Signoff archive.")

    def _build_report(self) -> dict[str, Any]:
        blockers = [check for check in self.checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
        warnings = [check for check in self.checks if check.get("status") in {"failed", "warning"} and check.get("severity") != "blocking"]
        source = self.signoff.get("source") if isinstance(self.signoff.get("source"), dict) else {}
        closeout_summary = self.closeout.get("summary") if isinstance(self.closeout.get("summary"), dict) else {}
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_VERIFICATION_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": stable_hash(source),
                "signoff_hash": self.signoff.get("integrity_hash"),
                "closeout_hash": self.closeout.get("integrity_hash"),
                "watch_zip_sha256": source.get("watch_zip_sha256"),
                "watch_manifest_hash": source.get("watch_manifest_hash"),
                "watch_verification_report_hash": source.get("watch_verification_report_hash"),
                "hub_zip_sha256": source.get("hub_zip_sha256"),
                "hub_manifest_hash": source.get("hub_manifest_hash"),
                "hub_verification_report_hash": source.get("hub_verification_report_hash"),
                "continuous_assurance_report_hash": source.get("continuous_assurance_report_hash"),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": {
                    "queue_id": self.signoff.get("queue_id") or self.closeout.get("queue_id"),
                    "signoff_id": self.signoff.get("signoff_id"),
                    "closeout_id": self.closeout.get("closeout_id"),
                    "watch_clear": bool(closeout_summary.get("watch_clear")),
                    "blocking_drift_count": int(closeout_summary.get("blocking_drift_count") or 0),
                    "overdue_items": int(closeout_summary.get("overdue_items") or 0),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                },
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        item = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
        item["integrity_hash"] = stable_hash(item)
        self.checks.append(item)


def _read_json_file(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _read_zip_json(zip_path: Path | None, entry: str) -> dict[str, Any]:
    if not zip_path:
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _sha256_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_zip_entry_names(zip_path: Path) -> list[str]:
    try:
        data = zip_path.read_bytes()
    except OSError:
        return []
    names: list[str] = []
    signature = b"PK\x01\x02"
    index = 0
    while True:
        index = data.find(signature, index)
        if index == -1 or index + 46 > len(data):
            break
        try:
            name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        except struct.error:
            break
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        names.append(data[start:end].decode("utf-8", errors="replace"))
        index = end + extra_len + comment_len
    return names


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _is_safe_zip_entry(name: str) -> bool:
    if "\\" in name or "\x00" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or lower.endswith(".zip")


def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".jsonl", ".txt", ".md", ".html"))


def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _walk_json_values(value: Any, prefix: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_json_values(item, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_json_values(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _safe_check_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower() or "item"


def _fs_path(path: Path) -> str:
    return str(path)
