from __future__ import annotations
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_contracts import ACK_BLOCKED_KEYS, ACK_EVIDENCE_PACKAGE_TYPE, ACK_PACK_PACKAGE_TYPE, ack_evidence_hash, ack_manifest_hash, ack_pack_hash, acknowledgement_summary, response_template
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash


ACK_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
PACK_REQUIRED_ENTRIES = {
    "acknowledgement-pack-manifest.json",
    "transparency-acknowledgement-pack.json",
    "data/transparency-verification-summary.json",
    "data/transparency-feed-summary.json",
    "data/current-public-state-summary.json",
    "data/events-summary.json",
    "data/notices-summary.json",
    "data/package-fingerprints.json",
    "forms/response-template.json",
    "forms/response-schema.json",
    "README.txt",
}
EVIDENCE_REQUIRED_ENTRIES = {
    "acknowledgement-evidence-manifest.json",
    "acknowledgement-evidence.json",
    "acknowledgement-evidence-summary.json",
    "data/response-binding-summary.json",
    "data/response-verification-summary.json",
    "data/original-response-binding-summary.json",
    "data/public-summary.json",
    "README.txt",
}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ACK_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_pack: bool = False,
    require_response: bool = False,
    require_accepted: bool = False,
    require_transparency: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AckVerifier(
        Path(zip_path),
        strict=strict,
        require_pack=require_pack,
        require_response=require_response,
        require_accepted=require_accepted,
        require_transparency=require_transparency,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge release portfolio governance attestation transparency acknowledgement verification")
    print(f"status: {report.get('status')}")
    print(f"package: {report.get('detected_package_type') or 'unknown'}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"acknowledgement: {summary.get('acknowledgement_id') or '-'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")


def release_portfolio_governance_attestation_transparency_acknowledgement_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AckVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_pack: bool,
        require_response: bool,
        require_accepted: bool,
        require_transparency: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_pack = require_pack
        self.require_response = require_response
        self.require_accepted = require_accepted
        self.require_transparency = require_transparency
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
        self.manifest: dict[str, Any] = {}
        self.main_doc: dict[str, Any] = {}
        self.summary_doc: dict[str, Any] = {}
        self.data_docs: dict[str, dict[str, Any]] = {}
        self.package_type = ""
        self.manifest_name = ""
        self.main_name = ""
        self.required_entries: set[str] = set()
        self.check_prefix = "ack"
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._detect_package(archive)
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ack_zip_open", "failed", "blocking", "Acknowledgement ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ack_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ack_zip_open", "failed", "blocking", f"Acknowledgement ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ack_zip_open", "passed", "blocking", "Acknowledgement ZIP can be opened.")
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
        max_uncompressed = self.max_uncompressed_size_mb * 1024 * 1024
        self._add_check("zip", "ack_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ack_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ack_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ack_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "ack_zip_no_nested_packages", "failed" if forbidden else "passed", "blocking", "Forbidden package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _detect_package(self, archive: zipfile.ZipFile) -> None:
        if "acknowledgement-pack-manifest.json" in self.entry_map:
            self.manifest_name = "acknowledgement-pack-manifest.json"
            self.main_name = "transparency-acknowledgement-pack.json"
            self.required_entries = PACK_REQUIRED_ENTRIES
            self.check_prefix = "ack_pack"
        elif "acknowledgement-evidence-manifest.json" in self.entry_map:
            self.manifest_name = "acknowledgement-evidence-manifest.json"
            self.main_name = "acknowledgement-evidence.json"
            self.required_entries = EVIDENCE_REQUIRED_ENTRIES
            self.check_prefix = "ack_evidence"
        else:
            self._add_check("manifest", "ack_manifest_exists", "failed", "blocking", "No acknowledgement manifest found.")
            return
        self.manifest = self._read_json_entry(archive, self.manifest_name, "manifest", f"{self.check_prefix}_manifest_parse")
        self.package_type = str(self.manifest.get("package_type") or "")
        missing = sorted(self.required_entries - set(self.entry_names))
        self._add_check("zip", f"{self.check_prefix}_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required acknowledgement entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            return
        expected_type = ACK_PACK_PACKAGE_TYPE if self.manifest_name == "acknowledgement-pack-manifest.json" else ACK_EVIDENCE_PACKAGE_TYPE
        self._add_hash_check("manifest", f"{self.check_prefix}_manifest_integrity", self.manifest.get("integrity_hash"), ack_manifest_hash(self.manifest), "Acknowledgement manifest integrity")
        self._add_check("manifest", f"{self.check_prefix}_manifest_package_type", "passed" if self.manifest.get("package_type") == expected_type else "failed", "blocking", "Manifest package_type is valid." if self.manifest.get("package_type") == expected_type else "Manifest package_type is invalid.")
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        valid: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                errors.append(f"files[{index}] is not an object")
                continue
            path = str(item.get("path") or "")
            if not _is_safe_zip_entry(path):
                errors.append(f"{path or index} has unsafe path")
            if not isinstance(item.get("size_bytes"), int):
                errors.append(f"{path or index} has invalid size")
            if not HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                errors.append(f"{path or index} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(item.get("size_bytes"), int) and HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                valid.append(item)
        self._add_check("manifest", f"{self.check_prefix}_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
        mismatches: list[str] = []
        for item in valid:
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(f"{path} missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_size == item.get("size_bytes") and actual_sha == item.get("sha256") else "failed"})
            if actual_size != item.get("size_bytes") or actual_sha != item.get("sha256"):
                mismatches.append(path)
        self._add_check("manifest", f"{self.check_prefix}_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.add(self.manifest_name)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", f"{self.check_prefix}_manifest_files_match_zip", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", f"{self.check_prefix}_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        if not self.main_name:
            return
        self.main_doc = self._read_json_entry(archive, self.main_name, "document", f"{self.check_prefix}_document_parse")
        if self.package_type == ACK_PACK_PACKAGE_TYPE:
            for name in ("transparency-verification-summary.json", "transparency-feed-summary.json", "current-public-state-summary.json", "events-summary.json", "notices-summary.json", "package-fingerprints.json"):
                self.data_docs[name] = self._read_json_entry(archive, f"data/{name}", "data", f"{self.check_prefix}_data_{name.replace('-', '_').replace('.', '_')}_parse")
            for name in ("response-template.json", "response-schema.json"):
                self.data_docs[name] = self._read_json_entry(archive, f"forms/{name}", "template", f"{self.check_prefix}_forms_{name.replace('-', '_').replace('.', '_')}_parse")
        elif self.package_type == ACK_EVIDENCE_PACKAGE_TYPE:
            self.summary_doc = self._read_json_entry(archive, "acknowledgement-evidence-summary.json", "summary", "ack_evidence_summary_parse")
            for name in ("response-binding-summary.json", "response-verification-summary.json", "original-response-binding-summary.json", "public-summary.json"):
                self.data_docs[name] = self._read_json_entry(archive, f"data/{name}", "data", f"{self.check_prefix}_data_{name.replace('-', '_').replace('.', '_')}_parse")

    def _verify_documents(self) -> None:
        if not self.main_doc:
            self._add_check("document", f"{self.check_prefix}_document_exists", "failed", "blocking", "Acknowledgement document must contain a JSON object.")
            return
        if self.package_type == ACK_PACK_PACKAGE_TYPE:
            self._verify_pack_document()
        elif self.package_type == ACK_EVIDENCE_PACKAGE_TYPE:
            self._verify_evidence_document()

    def _verify_pack_document(self) -> None:
        self._add_hash_check("pack", "ack_pack_integrity", self.main_doc.get("integrity_hash"), ack_pack_hash(self.main_doc), "Pack integrity")
        source = self.main_doc.get("source") if isinstance(self.main_doc.get("source"), dict) else {}
        self._add_hash_check("pack", "ack_pack_source_hash", self.main_doc.get("source_hash"), stable_hash(source), "Pack source hash")
        self._add_exact_check("manifest", "ack_manifest_source_hash", self.manifest.get("source_hash"), self.main_doc.get("source_hash"), "Manifest source_hash")
        row = self.manifest.get("pack") if isinstance(self.manifest.get("pack"), dict) else {}
        self._add_exact_check("manifest", "ack_manifest_pack_integrity", row.get("integrity_hash"), self.main_doc.get("integrity_hash"), "Manifest pack integrity")
        verification = self.data_docs.get("transparency-verification-summary.json", {})
        feed_summary = self.data_docs.get("transparency-feed-summary.json", {})
        public_state = self.data_docs.get("current-public-state-summary.json", {})
        events_summary = self.data_docs.get("events-summary.json", {})
        notices_summary = self.data_docs.get("notices-summary.json", {})
        package = self.data_docs.get("package-fingerprints.json", {})
        self._add_exact_check("data", "ack_pack_transparency_verification_status", verification.get("status"), source.get("transparency_verification_status"), "Transparency verification status")
        self._add_exact_check("data", "ack_pack_transparency_verification_hash", verification.get("verification_hash"), source.get("transparency_verification_hash"), "Transparency verification hash")
        self._add_exact_check("data", "ack_pack_event_semantics_status", verification.get("event_semantics"), source.get("transparency_event_semantics_status"), "Event semantics status")
        self._add_exact_check("data", "ack_pack_notice_semantics_status", verification.get("notice_semantics"), source.get("transparency_notice_semantics_status"), "Notice semantics status")
        self._add_exact_check("data", "ack_pack_feed_source_hash", feed_summary.get("feed_source_hash"), source.get("transparency_feed_source_hash"), "Transparency feed source hash")
        self._add_exact_check("data", "ack_pack_feed_event_count", feed_summary.get("event_count"), len(source.get("event_ids", []) if isinstance(source.get("event_ids"), list) else []), "Transparency feed event count")
        self._add_exact_check("data", "ack_pack_feed_notice_count", feed_summary.get("notice_count"), len(source.get("notice_ids", []) if isinstance(source.get("notice_ids"), list) else []), "Transparency feed notice count")
        self._add_exact_check("data", "ack_pack_current_public_state_hash", public_state.get("current_public_state_hash"), source.get("current_public_state_hash"), "Current public state hash")
        self._add_exact_check("data", "ack_pack_current_entry_id", public_state.get("current_entry_id"), source.get("current_entry_id"), "Current entry id")
        self._add_exact_check("data", "ack_pack_current_certificate_id", public_state.get("current_certificate_id"), source.get("current_certificate_id"), "Current certificate id")
        expected_events = [{"event_id": item, "event_type": None, "severity": None} for item in source.get("event_ids", []) if item]
        actual_events = events_summary.get("events") if isinstance(events_summary.get("events"), list) else []
        self._add_exact_check("data", "ack_pack_event_ids_match", [item.get("event_id") for item in actual_events if isinstance(item, dict)], [item["event_id"] for item in expected_events], "Event summary ids")
        actual_notices = notices_summary.get("notices") if isinstance(notices_summary.get("notices"), list) else []
        self._add_exact_check("data", "ack_pack_notice_ids_match", [item.get("notice_id") for item in actual_notices if isinstance(item, dict)], list(source.get("notice_ids", []) if isinstance(source.get("notice_ids"), list) else []), "Notice summary ids")
        for key, value in source.items():
            self._add_exact_check("data", f"ack_pack_data_package_{key}", package.get(key), value, f"Package fingerprint {key}")
        template = self.data_docs.get("response-template.json", {})
        expected_template = response_template(self.main_doc)
        for key in ("package_type", "review_pack_id", "review_pack_source_hash", "portfolio_id", "profile", "transparency_zip_sha256", "transparency_manifest_hash", "transparency_feed_source_hash"):
            self._add_exact_check("template", f"ack_pack_response_template_{key}", template.get(key), expected_template.get(key), f"Response template {key}")
        schema = self._read_schema_doc()
        self._add_exact_check("template", "ack_pack_response_schema_package_type", schema.get("package_type"), expected_template.get("package_type"), "Response schema package type")

    def _verify_evidence_document(self) -> None:
        self._add_hash_check("evidence", "ack_evidence_integrity", self.main_doc.get("integrity_hash"), ack_evidence_hash(self.main_doc), "Evidence integrity")
        source = self.main_doc.get("source") if isinstance(self.main_doc.get("source"), dict) else {}
        self._add_hash_check("evidence", "ack_evidence_source_hash", self.main_doc.get("source_hash"), stable_hash(source), "Evidence source hash")
        self._add_exact_check("manifest", "ack_manifest_source_hash", self.manifest.get("source_hash"), self.main_doc.get("source_hash"), "Manifest source_hash")
        row = self.manifest.get("acknowledgement") if isinstance(self.manifest.get("acknowledgement"), dict) else {}
        self._add_exact_check("manifest", "ack_evidence_manifest_integrity", row.get("integrity_hash"), self.main_doc.get("integrity_hash"), "Manifest evidence integrity")
        response_binding = self.data_docs.get("response-binding-summary.json", {})
        response_verification = self.data_docs.get("response-verification-summary.json", {})
        original_response = self.data_docs.get("original-response-binding-summary.json", {})
        public_summary_doc = self.data_docs.get("public-summary.json", {})
        for key, value in source.items():
            self._add_exact_check("data", f"ack_evidence_data_response_{key}", response_binding.get(key), value, f"Response binding {key}")
        public = self.main_doc.get("public_summary") if isinstance(self.main_doc.get("public_summary"), dict) else {}
        self._add_exact_check("data", "ack_evidence_data_public_summary", public_summary_doc.get("public_summary"), public, "Public summary data")
        self._add_exact_check("evidence", "ack_evidence_semantics_match", source.get("response_public_summary_hash"), stable_hash(public), "Evidence public summary response binding")
        self._add_exact_check("data", "ack_evidence_response_verification_status", response_verification.get("status"), source.get("response_verification_status"), "Response verification status sidecar")
        self._add_exact_check("data", "ack_evidence_response_verification_hash", response_verification.get("verification_hash"), source.get("response_verification_hash"), "Response verification hash sidecar")
        self._add_exact_check("data", "ack_evidence_response_verification_response_id", response_verification.get("response_id"), source.get("response_id"), "Response verification response id")
        self._add_exact_check("data", "ack_evidence_response_verification_payload_hash", response_verification.get("response_payload_hash"), source.get("response_payload_hash"), "Response verification payload hash")
        self._add_exact_check("data", "ack_evidence_response_verification_integrity_hash", response_verification.get("response_integrity_hash"), source.get("response_integrity_hash"), "Response verification integrity hash")
        self._add_exact_check("data", "ack_evidence_original_response_id", original_response.get("response_id"), source.get("response_id"), "Original response id")
        self._add_exact_check("data", "ack_evidence_original_response_payload_hash", original_response.get("response_payload_hash"), source.get("response_payload_hash"), "Original response payload hash")
        self._add_exact_check("data", "ack_evidence_original_response_integrity_hash", original_response.get("response_integrity_hash"), source.get("response_integrity_hash"), "Original response integrity hash")
        self._add_exact_check("data", "ack_evidence_original_response_public_summary", original_response.get("public_summary"), public, "Original response public summary")
        self._add_exact_check("data", "ack_evidence_original_response_public_summary_hash", original_response.get("response_public_summary_hash"), stable_hash(public), "Original response public summary hash")
        self._add_exact_check("data", "ack_evidence_original_response_pack_id", original_response.get("review_pack_id"), source.get("response_review_pack_id"), "Original response pack id")
        self._add_exact_check("data", "ack_evidence_original_response_pack_source_hash", original_response.get("review_pack_source_hash"), source.get("response_review_pack_source_hash"), "Original response pack source hash")
        self._add_exact_check("data", "ack_evidence_original_response_transparency_zip", original_response.get("transparency_zip_sha256"), source.get("transparency_zip_sha256"), "Original response transparency ZIP hash")
        self._add_exact_check("data", "ack_evidence_original_response_transparency_manifest", original_response.get("transparency_manifest_hash"), source.get("transparency_manifest_hash"), "Original response transparency manifest hash")
        self._add_exact_check("data", "ack_evidence_original_response_transparency_feed", original_response.get("transparency_feed_source_hash"), source.get("transparency_feed_source_hash"), "Original response transparency feed source hash")
        self._add_exact_check("evidence", "ack_evidence_status_binding", source.get("response_status"), self.main_doc.get("external_review_status"), "Evidence response status binding")
        self._add_exact_check("evidence", "ack_evidence_verification_binding", source.get("response_verification_status"), "passed", "Evidence response verification binding")
        self._add_exact_check("summary", "ack_evidence_summary_status", self.summary_doc.get("summary", {}).get("status") if isinstance(self.summary_doc.get("summary"), dict) else None, acknowledgement_summary(self.main_doc).get("status"), "Evidence summary status")

    def _verify_requirements(self) -> None:
        if self.require_pack:
            self._add_check("requirements", "ack_require_pack", "passed" if self.package_type == ACK_PACK_PACKAGE_TYPE else "failed", "blocking", "Pack package is present." if self.package_type == ACK_PACK_PACKAGE_TYPE else "Acknowledgement pack package is required.")
        if self.require_response:
            self._add_check("requirements", "ack_require_response", "passed" if self.package_type == ACK_EVIDENCE_PACKAGE_TYPE else "failed", "blocking", "Acknowledgement response evidence is present." if self.package_type == ACK_EVIDENCE_PACKAGE_TYPE else "Acknowledgement response evidence is required.")
        if self.require_accepted:
            accepted = self.package_type == ACK_EVIDENCE_PACKAGE_TYPE and self.main_doc.get("external_review_status") == "accepted" and self.main_doc.get("status") == "current"
            self._add_check("requirements", "ack_require_accepted", "passed" if accepted else "failed", "blocking", "Accepted acknowledgement evidence is present." if accepted else "Accepted acknowledgement evidence is required.")
        if self.require_transparency and self.package_type == ACK_PACK_PACKAGE_TYPE:
            source = self.main_doc.get("source") if isinstance(self.main_doc.get("source"), dict) else {}
            ok = source.get("transparency_verification_status") == "passed" and source.get("transparency_event_semantics_status") == "passed" and source.get("transparency_notice_semantics_status") == "passed"
            self._add_check("requirements", "ack_require_transparency", "passed" if ok else "failed", "blocking", "Transparency verification and semantics are passed." if ok else "Current verified Transparency evidence is required.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".md", ".html")):
                continue
            info = self.entry_map.get(name)
            if info is None or info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
        self._add_check("redaction", "ack_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
        info = self.entry_map.get(name)
        if not name or info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name or 'entry'} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parses as JSON.")
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _read_schema_doc(self) -> dict[str, Any]:
        value = self.data_docs.get("response-schema.json")
        return value if isinstance(value, dict) else {}

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = acknowledgement_summary(self.main_doc if self.package_type == ACK_EVIDENCE_PACKAGE_TYPE else {})
        summary.update({"portfolio_id": self.manifest.get("portfolio_id") or self.main_doc.get("portfolio_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        return sanitize_metadata(
            {
                "schema_version": ACK_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "attestation_transparency_acknowledgement",
                "detected_package_type": self.package_type,
                "zip_path": self.zip_path.name,
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
                "summary": summary,
                "checks": self.checks,
                "files": self.files,
                "blockers": blockers,
                "warnings": warnings,
                "redaction_findings": self.redaction_findings[:50],
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _is_forbidden_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_findings(scope: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "local_path", "message": "Local path pattern found."})
    lowered = text.lower()
    blocked_markers = (
        "github" + "key",
        "x-access-" + "token",
        "api_" + "key",
        "access_" + "token",
        "tok" + "en",
        "sec" + "ret",
        "pass" + "word",
        "source_" + "path",
        "local_" + "path",
        "file_" + "path",
    )
    for marker in blocked_markers:
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    return findings
