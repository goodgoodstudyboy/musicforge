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
from song_agent.domains.trust.trust_operations_control_signoff_contracts import CONTROL_SIGNOFF_ARCHIVE_ENTRIES as CONTROL_SIGNOFF_ARCHIVE_ENTRIES, TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS as TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS, TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION as TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION, TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE, control_signoff_hash as control_signoff_hash, control_signoff_manifest_hash as control_signoff_manifest_hash


TRUST_OPERATIONS_CONTROL_SIGNOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_verification"
TRUST_OPERATIONS_CONTROL_SIGNOFF_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_trust_operations_control_signoff_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    control_package_path: Path | str | None = None,
    control_verification_report_path: Path | str | None = None,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _ControlSignoffVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        require_current=require_current,
        control_package_path=Path(control_package_path) if control_package_path else None,
        control_verification_report_path=Path(control_verification_report_path) if control_verification_report_path else None,
        hub_package_path=Path(hub_package_path) if hub_package_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        incident_knowledge_package_path=Path(incident_knowledge_package_path) if incident_knowledge_package_path else None,
        incident_knowledge_verification_report_path=Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_control_signoff_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_control_signoff_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Control Signoff Archive verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"signoff: {summary.get('signoff_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")


def trust_operations_control_signoff_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _ControlSignoffVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_signed: bool,
        require_current: bool,
        control_package_path: Path | None,
        control_verification_report_path: Path | None,
        hub_package_path: Path | None,
        hub_verification_report_path: Path | None,
        incident_board_package_path: Path | None,
        incident_board_verification_report_path: Path | None,
        incident_knowledge_package_path: Path | None,
        incident_knowledge_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_signed = require_signed
        self.require_current = require_current
        self.control_package_path = control_package_path
        self.control_verification_report_path = control_verification_report_path
        self.hub_package_path = hub_package_path
        self.hub_verification_report_path = hub_verification_report_path
        self.incident_board_package_path = incident_board_package_path
        self.incident_board_verification_report_path = incident_board_verification_report_path
        self.incident_knowledge_package_path = incident_knowledge_package_path
        self.incident_knowledge_verification_report_path = incident_knowledge_verification_report_path
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
        self.signoff: ImplementationDocument = {}
        self.history_events: list[ImplementationDocument] = []
        self.exceptions_doc: ImplementationDocument = {}
        self.change_requests_doc: ImplementationDocument = {}
        self.report: ImplementationDocument = {}
        self.source_summary: ImplementationDocument = {}
        self.external_reports: dict[str, ImplementationDocument] = {}
        self.external_manifests: dict[str, ImplementationDocument] = {}

    def run(self) -> DomainDocument:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_history()
                self._verify_exceptions()
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
            self._add_check("zip", "tocs_zip_open", "failed", "blocking", "Control Signoff archive ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "tocs_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "tocs_zip_open", "failed", "blocking", f"Control Signoff archive ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "tocs_zip_open", "passed", "blocking", "Control Signoff archive ZIP can be opened.")
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
        self._add_check("zip", "tocs_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP uncompressed size is within limit.")
        self._add_check("zip", "tocs_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "tocs_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "tocs_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "tocs_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")
        missing = sorted(CONTROL_SIGNOFF_ARCHIVE_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - CONTROL_SIGNOFF_ARCHIVE_ENTRIES)
        self._add_check("zip", "tocs_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Control Signoff entries: " + ", ".join(missing) if missing else "All required Control Signoff entries exist.")
        self._add_check("zip", "tocs_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Control Signoff entries: " + ", ".join(unexpected[:5]) if unexpected else "Control Signoff ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-control-signoff-manifest.json", "manifest", "tocs_manifest_parse")
        self.signoff = self._read_json_entry(archive, "control-signoff.json", "signoff", "tocs_signoff_parse")
        self.exceptions_doc = self._read_json_entry(archive, "control-exceptions.json", "exceptions", "tocs_exceptions_parse")
        self.change_requests_doc = self._read_json_entry(archive, "control-change-requests.json", "change_requests", "tocs_change_requests_parse")
        self.report = self._read_json_entry(archive, "control-signoff-report.json", "report", "tocs_report_parse")
        self.source_summary = self._read_json_entry(archive, "source-verification-summary.json", "source", "tocs_source_parse")
        try:
            raw = archive.read("control-signoff-history.jsonl").decode("utf-8")
            for line in raw.splitlines():
                item = json.loads(line)
                if isinstance(item, dict):
                    self.history_events.append(item)
            self._add_check("history", "tocs_history_parse", "passed", "blocking", "control-signoff-history.jsonl parsed.")
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check("history", "tocs_history_parse", "failed", "blocking", f"control-signoff-history.jsonl cannot be parsed: {exc}")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "tocs_manifest_integrity", self.manifest.get("integrity_hash"), control_signoff_manifest_hash(self.manifest), "Control Signoff manifest integrity")
        self._add_exact_check("manifest", "tocs_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE, "Control Signoff manifest package_type")
        rows = _as_list(self.manifest.get("files"))
        valid_rows = [item for item in rows if isinstance(item, dict)]
        manifest_paths = {str(item.get("path") or "") for item in valid_rows}
        self._add_exact_check("manifest", "tocs_manifest_files_match_entries", sorted(manifest_paths), sorted(CONTROL_SIGNOFF_ARCHIVE_ENTRIES - {"trust-operations-control-signoff-manifest.json"}), "Manifest file list matches fixed Control Signoff structure")
        mismatches: list[str] = []
        for item in valid_rows:
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_sha == item.get("sha256") and actual_size == item.get("size_bytes") else "failed"})
            if actual_sha != item.get("sha256") or actual_size != item.get("size_bytes"):
                mismatches.append(path)
        self._add_check("manifest", "tocs_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "tocs_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files." if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        source = _as_document(self.signoff.get("source"))
        self._add_exact_check("signoff", "tocs_signoff_package_type", self.signoff.get("package_type"), TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE, "Signoff package_type")
        self._add_hash_check("signoff", "tocs_signoff_integrity", self.signoff.get("integrity_hash"), control_signoff_hash(self.signoff), "Signoff integrity")
        self._add_hash_check("signoff", "tocs_signoff_source_hash", self.signoff.get("source_hash"), stable_hash(source), "Signoff source hash")
        self._add_exact_check("report", "tocs_report_package_type", self.report.get("package_type"), TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE, "Archive report package_type")
        self._add_hash_check("report", "tocs_report_integrity", self.report.get("integrity_hash"), control_signoff_hash(self.report), "Archive report integrity")
        self._add_exact_check("report", "tocs_report_signoff_hash", self.report.get("signoff_hash"), self.signoff.get("integrity_hash"), "Archive report signoff hash")
        self._add_exact_check("source", "tocs_source_package_type", self.source_summary.get("package_type"), TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE, "Source summary package_type")
        self._add_hash_check("source", "tocs_source_integrity", self.source_summary.get("integrity_hash"), control_signoff_hash(self.source_summary), "Source summary integrity")
        self._add_exact_check("source", "tocs_source_matches_signoff", self.source_summary.get("source"), source, "Source summary matches signoff source")
        self._add_exact_check("source", "tocs_source_hash_matches_signoff", self.source_summary.get("source_hash"), self.signoff.get("source_hash"), "Source summary source hash")
        self._add_exact_check("exceptions", "tocs_exceptions_package_type", self.exceptions_doc.get("package_type"), TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE, "Exceptions package_type")
        self._add_hash_check("exceptions", "tocs_exceptions_integrity", self.exceptions_doc.get("integrity_hash"), control_signoff_hash(self.exceptions_doc), "Exceptions integrity")
        self._add_exact_check("change_requests", "tocs_change_requests_package_type", self.change_requests_doc.get("package_type"), TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, "Change Requests package_type")
        self._add_hash_check("change_requests", "tocs_change_requests_integrity", self.change_requests_doc.get("integrity_hash"), control_signoff_hash(self.change_requests_doc), "Change Requests integrity")
        manifest_source = _as_document(self.manifest.get("source"))
        self._add_exact_check("manifest", "tocs_manifest_signoff_hash", manifest_source.get("signoff_hash"), self.signoff.get("integrity_hash"), "Manifest signoff hash")
        self._add_exact_check("manifest", "tocs_manifest_history_hash", manifest_source.get("history_hash"), stable_hash({"events": self.history_events}), "Manifest history hash")
        self._add_exact_check("manifest", "tocs_manifest_exceptions_hash", manifest_source.get("exceptions_hash"), self.exceptions_doc.get("integrity_hash"), "Manifest exceptions hash")
        self._add_exact_check("manifest", "tocs_manifest_change_requests_hash", manifest_source.get("change_requests_hash"), self.change_requests_doc.get("integrity_hash"), "Manifest change request hash")
        self._add_exact_check("manifest", "tocs_manifest_report_hash", manifest_source.get("report_hash"), self.report.get("integrity_hash"), "Manifest report hash")
        self._add_exact_check("manifest", "tocs_manifest_source_summary_hash", manifest_source.get("source_verification_summary_hash"), self.source_summary.get("integrity_hash"), "Manifest source summary hash")

    def _verify_history(self) -> None:
        signoff_hash = str(self.signoff.get("integrity_hash") or "")
        signed_events = [item for item in self.history_events if item.get("event_type") == "control_signoff_signed" and item.get("signoff_hash") == signoff_hash]
        self._add_check("history", "tocs_history_signed_event", "passed" if signed_events else "failed", "blocking", "Signed history contains the current signoff hash." if signed_events else "Signed history is missing the current signoff hash.")
        reset_events = [item for item in self.history_events if item.get("event_type") == "control_signoff_reset"]
        change_requests = _as_list(self.change_requests_doc.get("change_requests"))
        by_id = {str(item.get("change_request_id") or ""): item for item in change_requests if isinstance(item, dict)}
        bad_resets: list[str] = []
        for event in reset_events:
            cr = by_id.get(str(event.get("change_request_id") or ""))
            applied = cr.get("applied") if isinstance(cr, dict) and isinstance(cr.get("applied"), dict) else {}
            if not cr or cr.get("status") != "applied" or cr.get("integrity_hash") != event.get("change_request_hash") or _as_document(applied).get("applied_signoff_reset_hash") != event.get("signoff_hash"):
                bad_resets.append(str(event.get("change_request_id") or "unknown"))
        self._add_check("history", "tocs_history_reset_cr_causality", "failed" if bad_resets else "passed", "blocking", "Reset events without applied CR: " + ", ".join(bad_resets[:5]) if bad_resets else "Reset events are bound to applied change requests.")

    def _verify_exceptions(self) -> None:
        exceptions = _as_list(self.exceptions_doc.get("exceptions"))
        bad_integrity = [str(item.get("exception_id") or "unknown") for item in exceptions if isinstance(item, dict) and item.get("integrity_hash") != control_signoff_hash(item)]
        self._add_check("exceptions", "tocs_exception_integrity_rows", "failed" if bad_integrity else "passed", "blocking", "Exception row integrity failed: " + ", ".join(bad_integrity[:5]) if bad_integrity else "Exception rows have valid integrity.")
        forbidden: list[str] = []
        expired: list[str] = []
        for item in exceptions:
            if not isinstance(item, dict) or item.get("status") != "approved":
                continue
            risk = _as_document(item.get("risk"))
            if risk.get("severity") in {"critical", "high"} or risk.get("required"):
                forbidden.append(str(item.get("exception_id") or "unknown"))
            expires_at = risk.get("expires_at")
            if expires_at and str(expires_at) < self.generated_at:
                expired.append(str(item.get("exception_id") or "unknown"))
        self._add_check("exceptions", "tocs_exception_no_forbidden_approvals", "failed" if forbidden else "passed", "blocking", "Forbidden approved exceptions: " + ", ".join(forbidden[:5]) if forbidden else "No critical/high/required approved exceptions.")
        self._add_check("exceptions", "tocs_exception_not_expired", "failed" if expired else "passed", "blocking", "Expired approved exceptions: " + ", ".join(expired[:5]) if expired else "No approved exceptions are expired.")

    def _read_external_sources(self) -> None:
        specs = {
            "control": (self.control_package_path, self.control_verification_report_path, "trust-operations-controls-manifest.json"),
            "hub": (self.hub_package_path, self.hub_verification_report_path, "trust-operations-hub-manifest.json"),
            "incident": (self.incident_board_package_path, self.incident_board_verification_report_path, "trust-operations-incident-manifest.json"),
            "knowledge": (self.incident_knowledge_package_path, self.incident_knowledge_verification_report_path, "trust-operations-knowledge-manifest.json"),
        }
        for kind, (zip_path, report_path, manifest_entry) in specs.items():
            if report_path:
                self.external_reports[kind] = _read_json_file(report_path)
            elif self.require_current:
                self._add_check("external", f"tocs_{kind}_verification_required", "failed", "blocking", f"External {kind} verification report is required.")
            if zip_path:
                self.external_manifests[kind] = _read_zip_json(zip_path, manifest_entry)
                self._add_exact_check("external", f"tocs_{kind}_zip_sha256", _sha256_file(zip_path), (_as_document(self.signoff.get("source"))).get(f"{kind}_zip_sha256"), f"External {kind} ZIP sha256")
            elif self.require_current:
                self._add_check("external", f"tocs_{kind}_package_required", "failed", "blocking", f"External {kind} package is required.")

    def _verify_external_bindings(self) -> None:
        source = _as_document(self.signoff.get("source"))
        control_report = self.external_reports.get("control", {})
        if control_report:
            self._add_exact_check("external", "tocs_control_verification_package_type", control_report.get("package_type"), "musicforge_trust_operations_control_verification", "Control verification package_type")
            self._add_exact_check("external", "tocs_control_verification_status", control_report.get("status"), "passed", "Control verification status")
            self._add_exact_check("external", "tocs_control_verification_report_hash", verification_hash(control_report), source.get("control_verification_report_hash"), "Control verification report hash")
            self._add_exact_check("external", "tocs_control_report_zip_sha256", control_report.get("zip_sha256"), source.get("control_zip_sha256"), "Control report ZIP sha256")
            self._add_exact_check("external", "tocs_control_report_zip_size_bytes", control_report.get("zip_size_bytes"), source.get("control_zip_size_bytes"), "Control report ZIP size")
            self._add_exact_check("external", "tocs_control_report_manifest_hash", control_report.get("manifest_hash"), source.get("control_manifest_hash"), "Control report manifest hash")
            for kind in ("hub", "incident", "knowledge"):
                self._add_exact_check("external", f"tocs_control_{kind}_verification_hash", control_report.get(f"{kind}_verification_report_hash"), source.get(f"{kind}_verification_report_hash"), f"Control report {kind} verification hash")
                self._add_exact_check("external", f"tocs_control_{kind}_zip_sha256", control_report.get(f"{kind}_zip_sha256"), source.get(f"{kind}_zip_sha256"), f"Control report {kind} ZIP sha256")
                self._add_exact_check("external", f"tocs_control_{kind}_manifest_hash", control_report.get(f"{kind}_manifest_hash"), source.get(f"{kind}_manifest_hash"), f"Control report {kind} manifest hash")
            summary = _as_document(control_report.get("summary"))
            self._add_check("external", "tocs_control_required_controls_passed", "passed" if int(summary.get("required_failed_count") or 0) == 0 else "failed", "blocking", "Control verification has no failed required controls." if int(summary.get("required_failed_count") or 0) == 0 else "Control verification has failed required controls.")
            self._add_exact_check("summary", "tocs_signoff_summary_required_failed", (_as_document(self.signoff.get("summary"))).get("required_failed_count"), int(summary.get("required_failed_count") or 0), "Signoff summary required failed count")
        for kind in ("hub", "incident", "knowledge"):
            report = self.external_reports.get(kind, {})
            if report:
                self._add_exact_check("external", f"tocs_{kind}_verification_report_hash", verification_hash(report), source.get(f"{kind}_verification_report_hash"), f"{kind} verification report hash")
                self._add_exact_check("external", f"tocs_{kind}_verification_zip_sha256", report.get("zip_sha256"), source.get(f"{kind}_zip_sha256"), f"{kind} verification ZIP sha256")
                self._add_exact_check("external", f"tocs_{kind}_verification_manifest_hash", report.get("manifest_hash"), source.get(f"{kind}_manifest_hash"), f"{kind} verification manifest hash")
            manifest = self.external_manifests.get(kind, {})
            if manifest:
                self._add_exact_check("external", f"tocs_{kind}_manifest_hash", manifest.get("integrity_hash"), source.get(f"{kind}_manifest_hash"), f"{kind} manifest hash")
        control_manifest = self.external_manifests.get("control", {})
        if control_manifest:
            self._add_exact_check("external", "tocs_control_manifest_hash", control_manifest.get("integrity_hash"), source.get("control_manifest_hash"), "Control manifest hash")

    def _verify_requirements(self) -> None:
        signed = self.signoff.get("status") == "signed"
        self._add_check("requirements", "tocs_require_signed", "passed" if signed or not self.require_signed else "failed", "blocking", "Control signoff is signed." if signed else "Control signoff is not signed.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[ImplementationDocument] = []
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
        for doc_name, doc in {"manifest": self.manifest, "signoff": self.signoff, "exceptions": self.exceptions_doc, "change_requests": self.change_requests_doc, "report": self.report, "source": self.source_summary}.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "tocs_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Control Signoff archive." if findings else "No sensitive values found in Control Signoff archive.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        source = _as_document(self.signoff.get("source"))
        summary = _as_document(self.signoff.get("summary"))
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_CONTROL_SIGNOFF_VERIFICATION_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_SIGNOFF_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": self.signoff.get("source_hash"),
                "signoff_hash": self.signoff.get("integrity_hash"),
                "control_zip_sha256": source.get("control_zip_sha256"),
                "control_zip_size_bytes": source.get("control_zip_size_bytes"),
                "control_manifest_hash": source.get("control_manifest_hash"),
                "control_verification_report_hash": source.get("control_verification_report_hash"),
                "hub_zip_sha256": source.get("hub_zip_sha256"),
                "hub_zip_size_bytes": source.get("hub_zip_size_bytes"),
                "hub_manifest_hash": source.get("hub_manifest_hash"),
                "hub_verification_report_hash": source.get("hub_verification_report_hash"),
                "incident_zip_sha256": source.get("incident_zip_sha256"),
                "incident_zip_size_bytes": source.get("incident_zip_size_bytes"),
                "incident_manifest_hash": source.get("incident_manifest_hash"),
                "incident_verification_report_hash": source.get("incident_verification_report_hash"),
                "knowledge_zip_sha256": source.get("knowledge_zip_sha256"),
                "knowledge_zip_size_bytes": source.get("knowledge_zip_size_bytes"),
                "knowledge_manifest_hash": source.get("knowledge_manifest_hash"),
                "knowledge_verification_report_hash": source.get("knowledge_verification_report_hash"),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": {
                    "hub_id": self.signoff.get("hub_id"),
                    "assessment_id": self.signoff.get("assessment_id"),
                    "signoff_id": self.signoff.get("signoff_id"),
                    "control_count": int(summary.get("control_count") or 0),
                    "required_failed_count": int(summary.get("required_failed_count") or 0),
                    "approved_exception_count": int(summary.get("approved_exception_count") or 0),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                },
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


def _read_json_file(path: Path) -> ImplementationDocument:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _sha256_file(path: Path) -> str | None:
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
    lower = name.lower()
    return lower.endswith((".json", ".jsonl", ".txt", ".md"))


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
