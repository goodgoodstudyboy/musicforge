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
) -> dict[str, Any]:
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


def write_trust_operations_final_handoff_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_final_handoff_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Final Handoff verification")
    print(f"status: {report.get('status')}")
    print(f"certificate: {summary.get('certificate_id') or '-'}")
    print(f"signoff: {summary.get('signoff_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def trust_operations_final_handoff_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _FinalHandoffVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_signed: bool,
        require_current: bool,
        external_paths: ImplementationDocument,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_signed = require_signed
        self.require_current = require_current
        self.external_paths = external_paths
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.manifest: dict[str, Any] = {}
        self.report: dict[str, Any] = {}
        self.certificate: dict[str, Any] = {}
        self.evidence_index: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.change_requests: dict[str, Any] = {}
        self.summaries: dict[str, dict[str, Any]] = {}
        self.history_events: list[dict[str, Any]] = []
        self.external_reports: dict[str, dict[str, Any]] = {}

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
                self._verify_summaries()
                self._verify_current_external_sources()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "tofr_zip_open", "failed", "blocking", "Final Handoff ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "tofr_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "tofr_zip_open", "failed", "blocking", f"Final Handoff ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "tofr_zip_open", "passed", "blocking", "Final Handoff ZIP can be opened.")
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
        self._add_check("zip", "tofr_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "ZIP uncompressed size is within limit.")
        self._add_check("zip", "tofr_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "tofr_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "tofr_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "tofr_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")
        missing = sorted(FINAL_READINESS_EXPORT_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - FINAL_READINESS_EXPORT_ENTRIES)
        self._add_check("zip", "tofr_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Final Handoff entries: " + ", ".join(missing) if missing else "All required Final Handoff entries exist.")
        self._add_check("zip", "tofr_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Final Handoff entries: " + ", ".join(unexpected[:5]) if unexpected else "Final Handoff ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-final-readiness-manifest.json", "manifest", "tofr_manifest_parse")
        self.report = self._read_json_entry(archive, "final-readiness-report.json", "report", "tofr_report_parse")
        self.certificate = self._read_json_entry(archive, "final-readiness-certificate.json", "certificate", "tofr_certificate_parse")
        self.evidence_index = self._read_json_entry(archive, "final-evidence-index.json", "evidence_index", "tofr_evidence_index_parse")
        self.signoff = self._read_json_entry(archive, "final-handoff-signoff.json", "signoff", "tofr_signoff_parse")
        self.change_requests = self._read_json_entry(archive, "change-requests.json", "change_requests", "tofr_change_requests_parse")
        for entry in sorted(path for path in FINAL_READINESS_EXPORT_ENTRIES if path.startswith("verification-summaries/")):
            self.summaries[entry] = self._read_json_entry(archive, entry, "summary", "tofr_summary_parse_" + _safe_check_id(entry))
        try:
            raw = archive.read("final-handoff-history.jsonl").decode("utf-8")
            for line in raw.splitlines():
                item = json.loads(line)
                if isinstance(item, dict):
                    self.history_events.append(item)
            self._add_check("history", "tofr_history_parse", "passed", "blocking", "final-handoff-history.jsonl parsed.")
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check("history", "tofr_history_parse", "failed", "blocking", f"final-handoff-history.jsonl cannot be parsed: {exc}")

    def _read_json_entry(self, archive: zipfile.ZipFile, entry: str, label: str, check_id: str) -> ImplementationDocument:
        try:
            value = json.loads(archive.read(entry).decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            self._add_check(label, check_id, "failed", "blocking", f"{entry} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(label, check_id, "failed", "blocking", f"{entry} is not a JSON object.")
            return {}
        self._add_check(label, check_id, "passed", "blocking", f"{entry} parsed.")
        return value

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_exact_check("manifest", "tofr_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE, "Manifest package_type")
        self._add_hash_check("manifest", "tofr_manifest_integrity", self.manifest.get("integrity_hash"), final_readiness_manifest_hash(self.manifest), "Manifest integrity")
        file_rows = _as_list(self.manifest.get("files"))
        expected_paths = sorted(FINAL_READINESS_EXPORT_ENTRIES - {"trust-operations-final-readiness-manifest.json"})
        manifest_paths = sorted(str(row.get("path") or "") for row in file_rows if isinstance(row, dict))
        self._add_exact_check("manifest", "tofr_manifest_fixed_file_list", manifest_paths, expected_paths, "Manifest file list matches fixed entries")
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
        self._add_check("manifest", "tofr_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        zip_entries = sorted(str(item) for item in (((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) or []))
        spoof = sorted(set(zip_entries) - set(self.entry_names))
        self._add_check("manifest", "tofr_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        self._add_exact_check("report", "tofr_report_package_type", self.report.get("package_type"), TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE, "Report package_type")
        self._add_hash_check("report", "tofr_report_integrity", self.report.get("integrity_hash"), final_readiness_hash(self.report), "Report integrity")
        self._add_exact_check("report", "tofr_report_status", self.report.get("status"), "ready", "Report status")
        self._add_exact_check("certificate", "tofr_certificate_package_type", self.certificate.get("package_type"), TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE, "Certificate package_type")
        self._add_hash_check("certificate", "tofr_certificate_integrity", self.certificate.get("integrity_hash"), final_readiness_hash(self.certificate), "Certificate integrity")
        self._add_exact_check("evidence", "tofr_evidence_index_package_type", self.evidence_index.get("package_type"), TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE, "Evidence index package_type")
        self._add_hash_check("evidence", "tofr_evidence_index_integrity", self.evidence_index.get("integrity_hash"), final_readiness_hash(self.evidence_index), "Evidence index integrity")
        self._add_exact_check("evidence", "tofr_report_rows_match_evidence", self.report.get("rows"), self.evidence_index.get("items"), "Report rows match evidence index")
        cert_source = _as_document(self.certificate.get("source"))
        self._add_exact_check("certificate", "tofr_certificate_report_hash", cert_source.get("report_hash"), self.report.get("integrity_hash"), "Certificate report hash")
        self._add_exact_check("certificate", "tofr_certificate_evidence_hash", cert_source.get("evidence_index_hash"), self.evidence_index.get("integrity_hash"), "Certificate evidence index hash")
        self._verify_signoff()
        self._add_exact_check("change_requests", "tofr_change_requests_package_type", self.change_requests.get("package_type"), TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE, "Change requests package_type")
        self._add_hash_check("change_requests", "tofr_change_requests_integrity", self.change_requests.get("integrity_hash"), final_readiness_hash(self.change_requests), "Change requests integrity")
        manifest_source = _as_document(self.manifest.get("source"))
        expected_source = {
            "report_hash": self.report.get("integrity_hash"),
            "certificate_hash": self.certificate.get("integrity_hash"),
            "evidence_index_hash": self.evidence_index.get("integrity_hash"),
            "signoff_hash": self.signoff.get("integrity_hash"),
            "change_requests_hash": self.change_requests.get("integrity_hash"),
            "history_hash": final_readiness_history_hash(self.history_events),
            "verification_summaries_hash": stable_summary_hash(self.summaries),
        }
        for key, value in expected_source.items():
            self._add_exact_check("manifest", "tofr_manifest_source_" + key, manifest_source.get(key), value, f"Manifest source {key}")

    def _verify_signoff(self) -> None:
        self._add_exact_check("signoff", "tofr_signoff_package_type", self.signoff.get("package_type"), TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE, "Signoff package_type")
        self._add_hash_check("signoff", "tofr_signoff_integrity", self.signoff.get("integrity_hash"), final_readiness_hash(self.signoff), "Signoff integrity")
        self._add_exact_check("signoff", "tofr_signoff_status", self.signoff.get("status"), "signed", "Signoff status")
        source = _as_document(self.signoff.get("source"))
        expected_source = {
            "final_readiness_report_hash": self.report.get("integrity_hash"),
            "final_readiness_certificate_hash": self.certificate.get("integrity_hash"),
            "final_evidence_index_hash": self.evidence_index.get("integrity_hash"),
            "hub_verification_report_hash": (_as_document(self.report.get("source"))).get("hub_verification_report_hash"),
            "assurance_watch_signoff_verification_report_hash": (_as_document(self.report.get("source"))).get("assurance_watch_signoff_verification_report_hash"),
            "delivery_verification_set_hash": (_as_document(self.report.get("source"))).get("delivery_verification_set_hash"),
        }
        self._add_exact_check("signoff", "tofr_signoff_source", source, expected_source, "Signoff source")
        expected_payload_hash = stable_hash(
            {
                "signoff_id": self.signoff.get("signoff_id"),
                "signed_by": self.signoff.get("signed_by"),
                "role": self.signoff.get("role"),
                "reason": self.signoff.get("reason"),
                "source": source,
                "decision": self.signoff.get("decision"),
            }
        )
        self._add_exact_check("signoff", "tofr_signoff_payload_hash", self.signoff.get("payload_hash"), expected_payload_hash, "Signoff payload hash")

    def _verify_history(self) -> None:
        previous_hash: str | None = None
        chain_errors: list[str] = []
        payload_errors: list[str] = []
        for index, event in enumerate(self.history_events):
            event_id = str(event.get("event_id") or event.get("event_type") or f"event-{index}")
            if event.get("previous_event_hash") != previous_hash:
                chain_errors.append(event_id)
            if event.get("payload_hash") != final_readiness_history_event_payload_hash(event):
                payload_errors.append(event_id)
            expected_event_hash = final_readiness_history_event_hash(event)
            if event.get("event_hash") != expected_event_hash:
                chain_errors.append(event_id)
            previous_hash = str(event.get("event_hash") or "")
        self._add_check("history", "tofr_history_event_payload_hashes", "failed" if payload_errors else "passed", "blocking", "History event payload hash failed: " + ", ".join(payload_errors[:5]) if payload_errors else "History event payload hashes are valid.")
        self._add_check("history", "tofr_history_event_chain", "failed" if chain_errors else "passed", "blocking", "History event chain failed: " + ", ".join(chain_errors[:5]) if chain_errors else "History event hash chain is valid.")
        signoff_hash = str(self.signoff.get("integrity_hash") or "")
        signed_events = [
            item
            for item in self.history_events
            if item.get("event_type") == "final_handoff_signed"
            and isinstance(item.get("payload"), dict)
            and item["payload"].get("signoff_hash") == signoff_hash
        ]
        self._add_check("history", "tofr_history_signed_event", "passed" if signed_events else "failed", "blocking", "Signed history contains current signoff hash." if signed_events else "Signed history is missing current signoff hash.")
        signoff_event_payload = signed_events[-1].get("payload", {}) if signed_events else {}
        expected_fields = {
            "signoff_id": self.signoff.get("signoff_id"),
            "signoff_hash": self.signoff.get("integrity_hash"),
            "signed_by": self.signoff.get("signed_by"),
            "role": self.signoff.get("role"),
            "reason": self.signoff.get("reason"),
            "signoff_payload_hash": self.signoff.get("payload_hash"),
            "report_hash": self.report.get("integrity_hash"),
            "certificate_hash": self.certificate.get("integrity_hash"),
            "evidence_index_hash": self.evidence_index.get("integrity_hash"),
        }
        mismatches = [key for key, expected in expected_fields.items() if signoff_event_payload.get(key) != expected]
        self._add_check("history", "tofr_history_signoff_payload_binding", "failed" if mismatches else "passed", "blocking", "Signoff history payload mismatch: " + ", ".join(mismatches) if mismatches else "Signoff history payload matches current signoff.")
        reset_events = [item for item in self.history_events if item.get("event_type") == "final_handoff_reset"]
        change_requests = _as_list(self.change_requests.get("change_requests"))
        by_id = {str(item.get("change_request_id") or ""): item for item in change_requests if isinstance(item, dict)}
        bad_resets: list[str] = []
        for event in reset_events:
            payload = _as_document(event.get("payload"))
            cr = by_id.get(str(payload.get("change_request_id") or ""))
            applied = cr.get("applied") if isinstance(cr, dict) and isinstance(cr.get("applied"), dict) else {}
            if not cr or cr.get("status") != "applied" or cr.get("integrity_hash") != payload.get("change_request_hash") or _as_document(applied).get("applied_reset_hash") != payload.get("signoff_hash"):
                bad_resets.append(str(payload.get("change_request_id") or "unknown"))
        self._add_check("history", "tofr_history_reset_cr_causality", "failed" if bad_resets else "passed", "blocking", "Reset events without applied CR: " + ", ".join(bad_resets[:5]) if bad_resets else "Reset events are bound to applied change requests.")

    def _verify_summaries(self) -> None:
        for entry, summary in self.summaries.items():
            self._add_hash_check("summaries", "tofr_summary_integrity_" + _safe_check_id(entry), summary.get("integrity_hash"), final_readiness_hash(summary), f"{entry} integrity")
        rows = _as_list(self.evidence_index.get("items"))
        by_key = {(row.get("component_type"), row.get("component_id")): row for row in rows if isinstance(row, dict)}
        for spec in FINAL_READINESS_SINGLE_SPECS:
            summary = self.summaries.get(str(spec["summary_path"]), {})
            row = by_key.get((spec["component_type"], spec["component_id"]), {})
            self._add_exact_check("summaries", "tofr_summary_row_binding_" + spec["component_type"], _summary_projection(summary), _row_summary_projection(row), f"{spec['component_type']} summary binds evidence row")
        delivery_summary = self.summaries.get("verification-summaries/delivery-verification-summary.json", {})
        delivery_items = _as_list(delivery_summary.get("items"))
        delivery_rows = [row for row in rows if isinstance(row, dict) and row.get("component_type") in {spec["component_type"] for spec in DELIVERY_VERIFICATION_COMPONENTS}]
        self._add_exact_check("summaries", "tofr_delivery_summary_rows", sorted(delivery_items, key=_row_key), sorted(delivery_rows, key=_row_key), "Delivery summary rows match evidence index.")

    def _verify_current_external_sources(self) -> None:
        if not self.require_current:
            return
        rows = _as_list(self.evidence_index.get("items"))
        by_key = {(str(row.get("component_type") or ""), str(row.get("component_id") or "")): row for row in rows if isinstance(row, dict)}
        for spec in FINAL_READINESS_SINGLE_SPECS:
            row = by_key.get((str(spec["component_type"]), str(spec["component_id"])), {})
            package_path = self.external_paths.get(str(spec["payload_path"]))
            report_path = self.external_paths.get(str(spec["payload_report"]))
            if not package_path:
                self._add_check("external", "tofr_current_" + spec["component_type"] + "_package_required", "failed", "blocking", f"{spec['component_type']} package is required.")
                continue
            if not report_path:
                self._add_check("external", "tofr_current_" + spec["component_type"] + "_verification_required", "failed", "blocking", f"{spec['component_type']} verification report is required.")
                continue
            report = _read_json_file(report_path)
            self.external_reports[str(spec["component_type"])] = report
            manifest = _read_zip_json(package_path, str(spec["manifest_entry"])) if package_path.exists() else {}
            self._add_exact_check("external", "tofr_current_" + spec["component_type"] + "_verification_package_type", report.get("package_type"), spec["verification_package_type"], f"{spec['component_type']} verification package_type")
            self._add_exact_check("external", "tofr_current_" + spec["component_type"] + "_verification_status", report.get("status"), "passed", f"{spec['component_type']} verification status")
            self._add_exact_check("external", "tofr_current_" + spec["component_type"] + "_verification_hash", row.get("verification_report_hash"), verification_hash(report), f"{spec['component_type']} verification report hash")
            self._add_exact_check("external", "tofr_current_" + spec["component_type"] + "_zip_sha256", row.get("package_sha256"), _sha256_file(package_path), f"{spec['component_type']} ZIP sha256")
            self._add_exact_check("external", "tofr_current_" + spec["component_type"] + "_zip_size", row.get("package_size_bytes"), os.stat(_fs_path(package_path)).st_size if package_path.exists() else None, f"{spec['component_type']} ZIP size")
            self._add_exact_check("external", "tofr_current_" + spec["component_type"] + "_manifest_hash", row.get("manifest_hash"), manifest.get("integrity_hash"), f"{spec['component_type']} manifest hash")
        self._verify_current_delivery_sources(rows)

    def _verify_current_delivery_sources(self, rows: list[ImplementationDocument]) -> None:
        package_types = {str(spec["component_type"]) for spec in DELIVERY_VERIFICATION_COMPONENTS}
        expected_rows = {
            (str(row.get("component_type") or ""), str(row.get("component_id") or "")): row
            for row in rows
            if isinstance(row, dict) and str(row.get("component_type") or "") in package_types
        }
        actual_rows: dict[tuple[str, str], dict[str, Any]] = {}
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            paths = self.external_paths.get(str(spec["payload_keys"])) or []
            for index, path in enumerate(paths):
                report = _read_json_file(path)
                component_id = _component_id_from_report(report, str(spec["component_id_prefix"]), index)
                key = (str(spec["component_type"]), component_id)
                actual_rows[key] = report
                expected = expected_rows.get(key, {})
                self._add_exact_check("external", "tofr_delivery_" + _safe_check_id("_".join(key)) + "_hash", expected.get("verification_report_hash"), verification_hash(report), f"{key} verification hash")
                self._add_exact_check("external", "tofr_delivery_" + _safe_check_id("_".join(key)) + "_status", report.get("status"), "passed", f"{key} verification status")
                self._add_exact_check("external", "tofr_delivery_" + _safe_check_id("_".join(key)) + "_zip_sha256", expected.get("package_sha256"), report.get("zip_sha256"), f"{key} package sha256")
                self._add_exact_check("external", "tofr_delivery_" + _safe_check_id("_".join(key)) + "_manifest_hash", expected.get("manifest_hash"), report.get("manifest_hash"), f"{key} manifest hash")
        missing = sorted(set(expected_rows) - set(actual_rows))
        extra = sorted(set(actual_rows) - set(expected_rows))
        self._add_check("external", "tofr_delivery_external_reports_complete", "failed" if missing or extra else "passed", "blocking", f"Delivery external reports mismatch. missing={missing[:4]} extra={extra[:4]}" if missing or extra else "Delivery external reports exactly match evidence index.")

    def _verify_requirements(self) -> None:
        signed = self.signoff.get("status") == "signed"
        self._add_check("requirements", "tofr_require_signed", "passed" if signed or not self.require_signed else "failed", "blocking", "Final Handoff is signed." if signed else "Final Handoff is not signed.")
        ready = self.report.get("status") == "ready" and self.certificate.get("status") == "ready" and self.signoff.get("status") == "signed"
        self._add_check("requirements", "tofr_require_ready", "passed" if ready else "failed", "blocking", "Final Handoff readiness evidence is ready." if ready else "Final Handoff readiness evidence is not ready.")

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
            "report": self.report,
            "certificate": self.certificate,
            "evidence_index": self.evidence_index,
            "signoff": self.signoff,
            "change_requests": self.change_requests,
            **{name: doc for name, doc in self.summaries.items()},
        }.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "tofr_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Final Handoff package." if findings else "No sensitive values found in Final Handoff package.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        summary = {
            "report_id": self.report.get("report_id"),
            "certificate_id": self.certificate.get("certificate_id"),
            "signoff_id": self.signoff.get("signoff_id"),
            "readiness": self.report.get("status"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
            "entry_count": len(self.entry_names),
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_path": self.zip_path.name,
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": stable_hash(_as_document(self.signoff.get("source"))),
                "final_readiness_report_hash": self.report.get("integrity_hash"),
                "final_readiness_certificate_hash": self.certificate.get("integrity_hash"),
                "final_evidence_index_hash": self.evidence_index.get("integrity_hash"),
                "signoff_hash": self.signoff.get("integrity_hash"),
                "hub_verification_report_hash": (_as_document(self.signoff.get("source"))).get("hub_verification_report_hash"),
                "hub_zip_sha256": _row_by_type(self.evidence_index, "hub").get("package_sha256"),
                "hub_manifest_hash": _row_by_type(self.evidence_index, "hub").get("manifest_hash"),
                "assurance_watch_signoff_verification_report_hash": (_as_document(self.signoff.get("source"))).get("assurance_watch_signoff_verification_report_hash"),
                "delivery_verification_set_hash": (_as_document(self.signoff.get("source"))).get("delivery_verification_set_hash"),
                "summary": summary,
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "redaction_findings": self.redaction_findings,
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _add_check(self, category: str, check_id: str, status: str, severity: str, message: str, details: ImplementationDocument | None = None) -> None:
        self.checks.append({"category": category, "check_id": check_id, "status": status, "severity": severity, "message": message, "details": details or {}})

    def _add_exact_check(self, category: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        passed = actual == expected
        self._add_check(category, check_id, "passed" if passed else "failed", "blocking", f"{label} matches." if passed else f"{label} mismatch.", {"actual": actual, "expected": expected})

    def _add_hash_check(self, category: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_exact_check(category, check_id, actual, expected, label)


def stable_summary_hash(summaries: dict[str, dict[str, Any]]) -> str:
    return stable_hash({"summaries": summaries})


def _row_by_type(evidence_index: ImplementationDocument, component_type: str) -> ImplementationDocument:
    for row in evidence_index.get("items", []) if isinstance(evidence_index.get("items"), list) else []:
        if isinstance(row, dict) and row.get("component_type") == component_type:
            return row
    return {}


def _summary_projection(summary: ImplementationDocument) -> ImplementationDocument:
    return {
        "component_type": summary.get("component_type"),
        "component_id": summary.get("component_id"),
        "status": summary.get("status"),
        "package_sha256": summary.get("package_sha256"),
        "package_size_bytes": summary.get("package_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
        "verification_package_type": summary.get("verification_package_type"),
        "verification_report_hash": summary.get("verification_report_hash"),
        "verification_status": summary.get("verification_status"),
    }


def _row_summary_projection(row: ImplementationDocument) -> ImplementationDocument:
    return {
        "component_type": row.get("component_type"),
        "component_id": row.get("component_id"),
        "status": row.get("status"),
        "package_sha256": row.get("package_sha256"),
        "package_size_bytes": row.get("package_size_bytes"),
        "manifest_hash": row.get("manifest_hash"),
        "verification_package_type": row.get("verification_package_type"),
        "verification_report_hash": row.get("verification_report_hash"),
        "verification_status": row.get("verification_status"),
    }


def _row_key(row: ImplementationDocument) -> tuple[str, str]:
    return (str(row.get("component_type") or ""), str(row.get("component_id") or ""))


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


def _first_path(*values: Path | str | None) -> Path | None:
    for value in values:
        if value:
            return Path(value)
    return None


def _component_id_from_report(report: ImplementationDocument, prefix: str, index: int) -> str:
    summary = _as_document(report.get("summary"))
    for key in ("component_id", "target_id", "submission_id", "release_id", "operations_id", "package_id"):
        value = report.get(key) or summary.get(key)
        if value:
            return _safe_id(str(value))
    return f"{prefix}-{index + 1:03d}"


def _read_json_file(path: Path | None) -> ImplementationDocument:
    if path is None or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return _as_document(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _read_zip_json(zip_path: Path | None, entry: str) -> ImplementationDocument:
    if not zip_path or not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _is_forbidden_entry(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".musicforge/") or "/.musicforge/" in lowered or lowered.endswith(".zip")


def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".jsonl", ".txt", ".md", ".html", ".csv"))


def _contains_sensitive_text(text: str) -> bool:
    if not text:
        return False
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _walk_json_values(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_walk_json_values(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_json_values(item, f"{prefix}[{index}]"))
    else:
        rows.append((prefix, value))
    return rows


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sha256_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_check_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower() or "item"


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
