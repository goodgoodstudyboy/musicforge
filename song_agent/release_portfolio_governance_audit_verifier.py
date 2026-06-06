from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.projectio import write_json
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_portfolio_governance_audit import (
    PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS,
    audit_ledger_hash,
    audit_ledger_integrity_ok,
    audit_manifest_integrity_hash,
    audit_report_integrity_hash,
)
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS


PORTFOLIO_GOVERNANCE_AUDIT_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "manifest.json",
    "portfolio-governance-audit-report.json",
    "portfolio-governance-audit-ledger.jsonl",
    "portfolio-summary.json",
    "queue-summaries.json",
    "signoff-summaries.json",
    "archive-verification-summaries.json",
    "change-request-ledger.json",
    "GOVERNANCE_AUDIT.md",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_audit_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_archives: bool = False,
    require_no_force: bool = False,
    require_reset_cr_causality: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _PortfolioGovernanceAuditVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        require_archives=require_archives,
        require_no_force=require_no_force,
        require_reset_cr_causality=require_reset_cr_causality,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_portfolio_governance_audit_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "portfolio_id": summary.get("portfolio_id"),
            "audit_status": summary.get("audit_status"),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "ledger_hash": summary.get("ledger_hash"),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_portfolio_governance_audit_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_audit_verification_report(report: dict[str, Any]) -> None:
    summary = release_portfolio_governance_audit_verification_summary(report)
    print("MusicForge release portfolio governance audit verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"audit: {summary.get('audit_status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = report.get(key) if isinstance(report.get(key), list) else []
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_audit_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PortfolioGovernanceAuditVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_signed: bool,
        require_archives: bool,
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
        self.require_archives = require_archives
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
        self.portfolio_summary: dict[str, Any] = {}
        self.queue_summaries: dict[str, Any] = {}
        self.signoff_summaries: dict[str, Any] = {}
        self.archive_summaries: dict[str, Any] = {}
        self.change_request_ledger: dict[str, Any] = {}
        self.ledger_entries: list[dict[str, Any]] = []
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
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "portfolio_governance_audit_manifest_parse")
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
            self._add_check("zip", "portfolio_governance_audit_zip_open", "failed", "blocking", "Portfolio Governance Audit ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "portfolio_governance_audit_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "portfolio_governance_audit_zip_open", "failed", "blocking", f"Portfolio Governance Audit ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "portfolio_governance_audit_zip_open", "passed", "blocking", "Portfolio Governance Audit ZIP can be opened.")
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
        self._add_check("zip", "portfolio_governance_audit_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "portfolio_governance_audit_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "portfolio_governance_audit_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "portfolio_governance_audit_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "portfolio_governance_audit_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Portfolio Governance Audit entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "portfolio_governance_audit_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "portfolio_governance_audit_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = audit_manifest_integrity_hash(self.manifest)
        self._add_check("manifest", "portfolio_governance_audit_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Portfolio Governance Audit manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Portfolio Governance Audit manifest integrity hash does not match.")
        package_type_ok = self.manifest.get("package_type") == "release_portfolio_governance_audit"
        self._add_check("manifest", "portfolio_governance_audit_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is release_portfolio_governance_audit." if package_type_ok else "Manifest package_type is not release_portfolio_governance_audit.")
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
        self._add_check("manifest", "portfolio_governance_audit_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "portfolio_governance_audit_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Audit file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Portfolio Governance Audit manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "portfolio_governance_audit_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "portfolio_governance_audit_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "portfolio-governance-audit-report.json", "audit_report", "portfolio_governance_audit_report_parse")
        self.portfolio_summary = self._read_json_entry(archive, "portfolio-summary.json", "portfolio", "portfolio_governance_audit_portfolio_summary_parse")
        self.queue_summaries = self._read_json_entry(archive, "queue-summaries.json", "queues", "portfolio_governance_audit_queue_summaries_parse")
        self.signoff_summaries = self._read_json_entry(archive, "signoff-summaries.json", "signoffs", "portfolio_governance_audit_signoff_summaries_parse")
        self.archive_summaries = self._read_json_entry(archive, "archive-verification-summaries.json", "archives", "portfolio_governance_audit_archive_summaries_parse")
        self.change_request_ledger = self._read_json_entry(archive, "change-request-ledger.json", "change_requests", "portfolio_governance_audit_change_request_ledger_parse")
        self.ledger_entries = self._read_jsonl_entry(archive, "portfolio-governance-audit-ledger.jsonl", "ledger", "portfolio_governance_audit_ledger_parse")

    def _verify_documents(self) -> None:
        if self.report_doc:
            actual = audit_report_integrity_hash(self.report_doc)
            self._add_check("audit_report", "portfolio_governance_audit_report_integrity", "passed" if self.report_doc.get("integrity_hash") == actual else "failed", "blocking", "Portfolio Governance Audit Report integrity hash matches." if self.report_doc.get("integrity_hash") == actual else "Portfolio Governance Audit Report integrity hash does not match.")
            manifest_row = self.manifest.get("audit_report") if isinstance(self.manifest.get("audit_report"), dict) else {}
            ok = manifest_row.get("integrity_hash") == self.report_doc.get("integrity_hash") and manifest_row.get("source_hash") == self.report_doc.get("source_hash")
            self._add_check("audit_report", "portfolio_governance_audit_manifest_report_hash", "passed" if ok else "failed", "blocking", "Manifest Audit Report reference matches report." if ok else "Manifest Audit Report reference does not match report.")
        if self.ledger_entries:
            chain_ok = audit_ledger_integrity_ok(self.ledger_entries)
            ledger_hash = audit_ledger_hash(self.ledger_entries)
            self._add_check("ledger", "portfolio_governance_audit_ledger_chain", "passed" if chain_ok else "failed", "blocking", "Portfolio Governance Audit ledger hash chain is valid." if chain_ok else "Portfolio Governance Audit ledger hash chain failed.")
            report_hash_ok = bool(self.report_doc) and self.report_doc.get("ledger_hash") == ledger_hash
            self._add_check("ledger", "portfolio_governance_audit_report_ledger_hash", "passed" if report_hash_ok else "failed", "blocking", "Audit Report ledger hash matches ledger entries." if report_hash_ok else "Audit Report ledger hash does not match ledger entries.")
            manifest_hash_ok = self.manifest.get("ledger_hash") == ledger_hash
            self._add_check("ledger", "portfolio_governance_audit_manifest_ledger_hash", "passed" if manifest_hash_ok else "failed", "blocking", "Audit manifest ledger hash matches ledger entries." if manifest_hash_ok else "Audit manifest ledger hash does not match ledger entries.")
        else:
            self._add_check("ledger", "portfolio_governance_audit_ledger_exists", "failed", "blocking", "portfolio-governance-audit-ledger.jsonl has no valid entries.")
        self._verify_change_request_causality()
        failed = [item for item in self.ledger_entries if item.get("integrity_ok") is False]
        self._add_check("evidence", "portfolio_governance_audit_evidence_integrity", "failed" if failed else "passed", "blocking", "Evidence integrity failed in ledger entries: " + ", ".join(str(item.get("entry_id")) for item in failed[:5]) if failed else "Ledger evidence integrity is usable.")

    def _verify_change_request_causality(self) -> None:
        applied_by_id: dict[str, dict[str, Any]] = {}
        applied_by_entry_id: dict[str, dict[str, Any]] = {}
        for item in self.ledger_entries:
            if item.get("event_type") != "governance_change_request_applied":
                continue
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            entry_id = str(item.get("entry_id") or "")
            request_id = str(source.get("id") or "")
            if request_id:
                applied_by_id[request_id] = item
            if entry_id:
                applied_by_entry_id[entry_id] = item
        reset_entries = [item for item in self.ledger_entries if item.get("event_type") in {"governance_signoff_reset", "governance_signoff_history_reset", "governance_queue_governance_signoff_reset"}]
        errors: list[str] = []
        for entry in reset_entries:
            refs = entry.get("causal_refs") if isinstance(entry.get("causal_refs"), list) else []
            request_id = ""
            request_entry_id = ""
            for ref in refs:
                if isinstance(ref, dict) and ref.get("type") == "change_request" and ref.get("id"):
                    request_id = str(ref.get("id"))
                    request_entry_id = str(ref.get("entry_id") or "")
                    break
            if not request_id:
                errors.append(f"{entry.get('entry_id')} missing change request causal ref")
                continue
            request_entry = applied_by_entry_id.get(request_entry_id) or applied_by_id.get(request_id)
            if not request_entry:
                errors.append(f"{entry.get('entry_id')} missing applied change request {request_id}")
                continue
            reset_hash = str((entry.get("source") if isinstance(entry.get("source"), dict) else {}).get("payload_hash") or "")
            applied_refs = request_entry.get("causal_refs") if isinstance(request_entry.get("causal_refs"), list) else []
            applied_reset_hashes = {str(ref.get("payload_hash") or "") for ref in applied_refs if isinstance(ref, dict) and ref.get("type") == "governance_signoff_reset"}
            if reset_hash and reset_hash not in applied_reset_hashes:
                errors.append(f"{request_id} reset hash mismatch")
        self._add_check("change_requests", "portfolio_governance_audit_change_request_reset_causality", "failed" if errors else "passed", "blocking", "Invalid reset causality: " + "; ".join(errors[:5]) if errors else "Governance reset entries are bound to applied Change Requests.")

    def _verify_requirements(self) -> None:
        coverage = self.report_doc.get("coverage") if isinstance(self.report_doc.get("coverage"), dict) else {}
        if self.require_signed:
            signed = int(coverage.get("signed_queue_count") or 0)
            queues = int(coverage.get("queue_count") or 0)
            ok = queues > 0 and signed >= queues
            self._add_check("requirements", "portfolio_governance_audit_require_signed", "passed" if ok else "failed", "blocking", "All Governance Queues are signed." if ok else "Signed Governance Queue coverage is required.")
        if self.require_archives:
            signed = int(coverage.get("signed_queue_count") or 0)
            archives = int(coverage.get("archive_verified_count") or 0)
            ok = signed > 0 and archives >= signed
            self._add_check("requirements", "portfolio_governance_audit_require_archives", "passed" if ok else "failed", "blocking", "All signed Governance Queues have verified Archive evidence." if ok else "Verified Governance Archive evidence is required for signed queues.")
        if self.require_no_force:
            forced = int(coverage.get("force_signed_count") or 0)
            self._add_check("requirements", "portfolio_governance_audit_require_no_force", "failed" if forced else "passed", "blocking", "Force-signed Governance Queues are not allowed." if forced else "No force-signed Governance Queues are present.")
        if self.require_reset_cr_causality:
            reset_status = _check_status(self.checks, "portfolio_governance_audit_change_request_reset_causality")
            self._add_check("requirements", "portfolio_governance_audit_require_reset_cr_causality", "passed" if reset_status == "passed" else "failed", "blocking", "Reset Change Request causality is verified." if reset_status == "passed" else "Reset Change Request causality is required.")

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
        self._add_check("redaction", "portfolio_governance_audit_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
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

    def _read_jsonl_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> list[dict[str, Any]]:
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

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        report = {
            "schema_version": PORTFOLIO_GOVERNANCE_AUDIT_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "summary": {
                "portfolio_id": self.manifest.get("portfolio_id") or self.report_doc.get("portfolio_id"),
                "audit_status": self.report_doc.get("status"),
                "entry_count": len(self.ledger_entries),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "ledger_hash": audit_ledger_hash(self.ledger_entries) if self.ledger_entries else None,
            },
            "checks": self.checks,
            "files": self.files,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _check_status(checks: list[dict[str, Any]], check_id: str) -> str:
    for item in checks:
        if item.get("check_id") == check_id:
            return str(item.get("status") or "")
    return ""


def _is_safe_zip_entry(name: str) -> bool:
    text = str(name or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        return False
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    if ":" in path.parts[0]:
        return False
    return True


def _raw_zip_entry_names(path: Path) -> list[str]:
    data = path.read_bytes() if path.exists() else b""
    names: list[str] = []
    index = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, index)
        if index < 0 or index + 46 > len(data):
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        try:
            names.append(data[start:end].decode("utf-8"))
        except UnicodeDecodeError:
            names.append(data[start:end].decode("cp437", errors="replace"))
        index = end + extra_len + comment_len
    return names


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


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        for match in pattern.finditer(text):
            findings.append({"path": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "pattern": f"blocked_key:{path}", "excerpt": str(key)})
            findings.extend(_blocked_key_findings(name, item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{prefix}[{index}]"))
    return findings
