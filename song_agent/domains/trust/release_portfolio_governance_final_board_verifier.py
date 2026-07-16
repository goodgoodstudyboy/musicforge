from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument
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
from song_agent.domains.trust.release_portfolio_governance_final_board_contracts import FINAL_BOARD_BLOCKED_KEYS, final_board_archive_manifest_hash, final_board_change_request_integrity_ok, final_board_report_integrity_hash, final_board_response_integrity_hash, final_board_signoff_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash


FINAL_BOARD_ARCHIVE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "manifest.json",
    "final-board-report.json",
    "final-board-signoff.json",
    "final-board-history.jsonl",
    "reviewer-response-summary.json",
    "change-requests.json",
    "governance-reviewer-pack-summary.json",
    "governance-audit-summary.json",
    "governance-archive-summary.json",
    "final-board.md",
    "reviewer-response-summary.md",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = FINAL_BOARD_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_final_board_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_reviewer_pack: bool = False,
    require_audit: bool = False,
    require_archives: bool = False,
    require_reviewer_response: bool = False,
    require_no_force: bool = False,
    require_reset_cr_causality: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _FinalBoardArchiveVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        require_reviewer_pack=require_reviewer_pack,
        require_audit=require_audit,
        require_archives=require_archives,
        require_reviewer_response=require_reviewer_response,
        require_no_force=require_no_force,
        require_reset_cr_causality=require_reset_cr_causality,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_portfolio_governance_final_board_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "zip_sha256": report.get("zip_sha256"),
            "zip_size_bytes": report.get("zip_size_bytes"),
            "manifest_hash": report.get("manifest_hash"),
            "portfolio_id": summary.get("portfolio_id"),
            "report_status": summary.get("report_status"),
            "signoff_status": summary.get("signoff_status"),
            "reviewer_response_status": summary.get("reviewer_response_status"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_portfolio_governance_final_board_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_final_board_verification_report(report: dict[str, Any]) -> None:
    summary = release_portfolio_governance_final_board_verification_summary(report)
    print("MusicForge release portfolio governance final board verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"report: {summary.get('report_status') or '-'}")
    print(f"signoff: {summary.get('signoff_status') or '-'}")
    print(f"reviewer response: {summary.get('reviewer_response_status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = report.get(key) if isinstance(report.get(key), list) else []
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_final_board_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _FinalBoardArchiveVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_signed: bool,
        require_reviewer_pack: bool,
        require_audit: bool,
        require_archives: bool,
        require_reviewer_response: bool,
        require_no_force: bool,
        require_reset_cr_causality: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_signed = require_signed
        self.require_reviewer_pack = require_reviewer_pack
        self.require_audit = require_audit
        self.require_archives = require_archives
        self.require_reviewer_response = require_reviewer_response
        self.require_no_force = require_no_force
        self.require_reset_cr_causality = require_reset_cr_causality
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.response_summary: dict[str, Any] = {}
        self.change_requests: dict[str, Any] = {}
        self.reviewer_pack_summary: dict[str, Any] = {}
        self.audit_summary: dict[str, Any] = {}
        self.archive_summary: dict[str, Any] = {}
        self.history_entries: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "final_board_manifest_parse")
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
            self._add_check("zip", "final_board_zip_open", "failed", "blocking", "Final Board Archive ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "final_board_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "final_board_zip_open", "failed", "blocking", f"Final Board Archive ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "final_board_zip_open", "passed", "blocking", "Final Board Archive ZIP can be opened.")
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
        self._add_check("zip", "final_board_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "final_board_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "final_board_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "final_board_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "final_board_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Final Board entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "final_board_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "final_board_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = final_board_archive_manifest_hash(self.manifest)
        self._add_check("manifest", "final_board_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Final Board manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Final Board manifest integrity hash does not match.")
        package_type_ok = self.manifest.get("package_type") == "release_portfolio_governance_final_board_archive"
        self._add_check("manifest", "final_board_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is release_portfolio_governance_final_board_archive." if package_type_ok else "Manifest package_type is not release_portfolio_governance_final_board_archive.")
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
            if not isinstance(item.get("size_bytes"), int) or int(item.get("size_bytes") or 0) < 0:
                errors.append(f"{path or index} has invalid size")
            if not HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                errors.append(f"{path or index} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(item.get("size_bytes"), int) and HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                valid.append(item)
        self._add_check("manifest", "final_board_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "final_board_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Final Board file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Final Board manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "final_board_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "final_board_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "final-board-report.json", "report", "final_board_report_parse")
        self.signoff = self._read_json_entry(archive, "final-board-signoff.json", "signoff", "final_board_signoff_parse")
        self.response_summary = self._read_json_entry(archive, "reviewer-response-summary.json", "responses", "final_board_response_summary_parse")
        self.change_requests = self._read_json_entry(archive, "change-requests.json", "change_requests", "final_board_change_requests_parse")
        self.reviewer_pack_summary = self._read_json_entry(archive, "governance-reviewer-pack-summary.json", "reviewer_pack", "final_board_reviewer_pack_summary_parse")
        self.audit_summary = self._read_json_entry(archive, "governance-audit-summary.json", "audit", "final_board_audit_summary_parse")
        self.archive_summary = self._read_json_entry(archive, "governance-archive-summary.json", "archives", "final_board_archive_summary_parse")
        self.history_entries = self._read_jsonl_entry(archive, "final-board-history.jsonl", "history", "final_board_history_parse")

    def _verify_documents(self) -> None:
        if self.report_doc:
            self._add_hash_check("report", "final_board_report_integrity", self.report_doc.get("integrity_hash"), final_board_report_integrity_hash(self.report_doc), "Final Board Report integrity")
            row = self.manifest.get("final_board_report") if isinstance(self.manifest.get("final_board_report"), dict) else {}
            self._add_hash_check("report", "final_board_manifest_report_hash", row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
        if self.signoff:
            self._add_hash_check("signoff", "final_board_signoff_integrity", self.signoff.get("integrity_hash"), final_board_signoff_hash(self.signoff), "Final Board Signoff integrity")
            row = self.manifest.get("final_board_signoff") if isinstance(self.manifest.get("final_board_signoff"), dict) else {}
            self._add_hash_check("signoff", "final_board_manifest_signoff_hash", row.get("integrity_hash"), self.signoff.get("integrity_hash"), "Manifest signoff hash")
            source = self.signoff.get("source") if isinstance(self.signoff.get("source"), dict) else {}
            self._add_hash_check("signoff", "final_board_signoff_report_hash", source.get("final_board_report_hash"), self.report_doc.get("integrity_hash"), "Signoff report evidence hash")
            reviewer_evidence = self.manifest.get("reviewer_pack_evidence") if isinstance(self.manifest.get("reviewer_pack_evidence"), dict) else {}
            audit_evidence = self.manifest.get("audit_evidence") if isinstance(self.manifest.get("audit_evidence"), dict) else {}
            self._add_hash_check("signoff", "final_board_signoff_reviewer_pack_verification_hash", source.get("reviewer_pack_verification_hash"), reviewer_evidence.get("verification_hash"), "Signoff Reviewer Pack verification hash")
            self._add_hash_check("signoff", "final_board_signoff_audit_verification_hash", source.get("governance_audit_verification_hash"), audit_evidence.get("verification_hash"), "Signoff Audit verification hash")
        if self.response_summary:
            actual = stable_hash({key: value for key, value in self.response_summary.items() if key != "payload_hash"})
            self._add_hash_check("responses", "final_board_response_summary_integrity", self.response_summary.get("payload_hash"), actual, "Reviewer response summary hash")
        if self.change_requests:
            actual = stable_hash({key: value for key, value in self.change_requests.items() if key != "payload_hash"})
            self._add_hash_check("change_requests", "final_board_change_requests_hash", self.change_requests.get("payload_hash"), actual, "Change request bundle hash")
            invalid = [str(item.get("change_request_id") or "?") for item in self.change_requests.get("items", []) if isinstance(item, dict) and not final_board_change_request_integrity_ok(item)]
            self._add_check("change_requests", "final_board_change_request_integrity", "failed" if invalid else "passed", "blocking", "Change Request integrity failed: " + ", ".join(invalid[:5]) if invalid else "All Change Requests have valid integrity hashes.")

    def _verify_requirements(self) -> None:
        summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
        signoff_status = str(self.signoff.get("status") or "")
        if self.require_signed:
            self._add_check("requirements", "final_board_require_signed", "passed" if signoff_status in {"signed", "force_signed"} else "failed", "blocking", "Final Board Signoff is signed." if signoff_status in {"signed", "force_signed"} else "Signed Final Board Signoff is required.")
        if self.require_reviewer_pack:
            ok = summary.get("reviewer_pack_status") == "passed" and summary.get("reviewer_pack_verification_status") == "passed"
            self._add_check("requirements", "final_board_require_reviewer_pack", "passed" if ok else "failed", "blocking", "Reviewer Pack evidence is passed." if ok else "Passed Reviewer Pack evidence is required.")
        if self.require_audit:
            ok = summary.get("audit_status") == "passed" and summary.get("audit_verification_status") == "passed"
            self._add_check("requirements", "final_board_require_audit", "passed" if ok else "failed", "blocking", "Governance Audit evidence is passed." if ok else "Passed Governance Audit evidence is required.")
        if self.require_archives:
            signed = int(summary.get("signed_queue_count") or 0)
            archives = int(summary.get("archive_verified_count") or 0)
            ok = signed > 0 and archives >= signed
            self._add_check("requirements", "final_board_require_archives", "passed" if ok else "failed", "blocking", "Governance Archive coverage is passed." if ok else "Verified Governance Archive evidence is required.")
        if self.require_reviewer_response:
            ok = self.response_summary.get("status") in {"accepted", "accepted_with_notes"}
            self._add_check("requirements", "final_board_require_reviewer_response", "passed" if ok else "failed", "blocking", "Accepted reviewer response exists." if ok else "Accepted reviewer response is required.")
        if self.require_no_force:
            forced = bool(self.signoff.get("force")) or signoff_status == "force_signed" or int(summary.get("force_signed_queue_count") or 0) > 0
            self._add_check("requirements", "final_board_require_no_force", "failed" if forced else "passed", "blocking", "Force-signed evidence is not allowed." if forced else "No force-signed evidence is present.")
        if self.require_reset_cr_causality:
            resets = int(summary.get("reset_count") or 0)
            applied = int(summary.get("applied_change_request_count") or 0)
            ok = resets == 0 or applied >= resets
            self._add_check("requirements", "final_board_require_reset_cr_causality", "passed" if ok else "failed", "blocking", "Reset Change Request causality is covered." if ok else "Reset Change Request causality is required.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".jsonl", ".txt", ".csv", ".md")):
                continue
            info = self.entry_map.get(name)
            if info is None or info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
            if name.endswith(".json"):
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    continue
                self.redaction_findings.extend(_blocked_key_findings(name, value))
            elif name.endswith(".jsonl"):
                for line in text.splitlines():
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.redaction_findings.extend(_blocked_key_findings(name, value))
        self._add_check("redaction", "final_board_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=VERIFIER_BLOCKED_KEYS)

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
        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {index}: {exc}")
                continue
            if not isinstance(value, dict):
                errors.append(f"line {index}: not an object")
                continue
            rows.append(sanitize_metadata(value, blocked_keys=VERIFIER_BLOCKED_KEYS))
        self._add_check(scope, check_id, "failed" if errors else "passed", "blocking", "Invalid JSONL rows: " + "; ".join(errors[:5]) if errors else f"{name} parses as JSONL.")
        return rows

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        report = {
            "schema_version": FINAL_BOARD_ARCHIVE_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "summary": {
                "portfolio_id": self.manifest.get("portfolio_id") or self.report_doc.get("portfolio_id"),
                "report_status": self.report_doc.get("status"),
                "signoff_status": self.signoff.get("status"),
                "reviewer_response_status": self.response_summary.get("status"),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
            },
            "checks": self.checks,
            "files": self.files,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


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


def _redaction_findings(name: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": "local_path", "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"entry": name, "pattern": "blocked_key", "key": str(key)})
            findings.extend(_blocked_key_findings(name, item))
    elif isinstance(value, list):
        for item in value:
            findings.extend(_blocked_key_findings(name, item))
    return findings
