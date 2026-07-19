from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.trust.release_operations_audit_contracts import OPERATIONS_AUDIT_BLOCKED_KEYS as OPERATIONS_AUDIT_BLOCKED_KEYS, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_manifest_integrity_hash as audit_manifest_integrity_hash, audit_report_integrity_hash as audit_report_integrity_hash
from song_agent.domains.trust.release_operations_signoff_contracts import operations_change_request_hash as operations_change_request_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS


OPERATIONS_AUDIT_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "operations-audit-manifest.json",
    "operations-audit-report.json",
    "operations-audit-ledger.jsonl",
    "operations-report-summary.json",
    "operations-signoff-summary.json",
    "latest-runbook-summary.json",
    "change-request-ledger.json",
    "package-verifier-ledger.json",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"operations-audit-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = OPERATIONS_AUDIT_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_operations_audit_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_signed: bool = False,
    require_archive: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _OperationsAuditVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        require_signed=require_signed,
        require_archive=require_archive,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_operations_audit_verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "audit_status": summary.get("audit_status"),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "ledger_hash": summary.get("ledger_hash"),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_operations_audit_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_operations_audit_verification_report(report: DomainDocument) -> None:
    summary = release_operations_audit_verification_summary(report)
    print("MusicForge release operations audit verification")
    print(f"status: {summary.get('status')}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"audit: {summary.get('audit_status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = _as_list(report.get(key))
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_operations_audit_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _OperationsAuditVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        require_signed: bool,
        require_archive: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.require_signed = require_signed
        self.require_archive = require_archive
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.manifest: ImplementationDocument = {}
        self.report_doc: ImplementationDocument = {}
        self.operations_summary: ImplementationDocument = {}
        self.signoff_summary: ImplementationDocument = {}
        self.runbook_summary: ImplementationDocument = {}
        self.change_request_ledger: ImplementationDocument = {}
        self.package_verifier_ledger: ImplementationDocument = {}
        self.ledger_entries: list[ImplementationDocument] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> DomainDocument:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "operations-audit-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "operations-audit-manifest.json", "manifest", "operations_audit_manifest_parse")
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
            self._add_check("zip", "operations_audit_zip_open", "failed", "blocking", "Operations Audit ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "operations_audit_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "operations_audit_zip_open", "failed", "blocking", f"Operations Audit ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "operations_audit_zip_open", "passed", "blocking", "Operations Audit ZIP can be opened.")
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
        self._add_check("zip", "operations_audit_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "operations_audit_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "operations_audit_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "operations_audit_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "operations_audit_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Operations Audit entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "operations_audit_manifest_exists", "failed", "blocking", "operations-audit-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "operations_audit_manifest_exists", "passed", "blocking", "operations-audit-manifest.json exists.")
        actual_manifest_hash = audit_manifest_integrity_hash(self.manifest)
        self._add_check("manifest", "operations_audit_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Operations Audit manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Operations Audit manifest integrity hash does not match.")
        rows = _as_list(self.manifest.get("files"))
        valid: list[ImplementationDocument] = []
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
        self._add_check("manifest", "operations_audit_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "operations_audit_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Audit file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Operations Audit manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "operations_audit_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "operations_audit_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "operations-audit-report.json", "audit_report", "operations_audit_report_parse")
        self.operations_summary = self._read_json_entry(archive, "operations-report-summary.json", "operations", "operations_audit_operations_summary_parse")
        self.signoff_summary = self._read_json_entry(archive, "operations-signoff-summary.json", "signoff", "operations_audit_signoff_summary_parse")
        self.runbook_summary = self._read_json_entry(archive, "latest-runbook-summary.json", "runbook", "operations_audit_runbook_summary_parse")
        self.change_request_ledger = self._read_json_entry(archive, "change-request-ledger.json", "change_requests", "operations_audit_change_request_ledger_parse")
        self.package_verifier_ledger = self._read_json_entry(archive, "package-verifier-ledger.json", "package_verifiers", "operations_audit_package_verifier_parse")
        self.ledger_entries = self._read_jsonl_entry(archive, "operations-audit-ledger.jsonl", "ledger", "operations_audit_ledger_parse")

    def _verify_documents(self) -> None:
        if self.report_doc:
            actual = audit_report_integrity_hash(self.report_doc)
            self._add_check("audit_report", "operations_audit_report_integrity", "passed" if self.report_doc.get("integrity_hash") == actual else "failed", "blocking", "Operations Audit Report integrity hash matches." if self.report_doc.get("integrity_hash") == actual else "Operations Audit Report integrity hash does not match.")
            manifest_row = _as_document(self.manifest.get("audit_report"))
            ok = manifest_row.get("integrity_hash") == self.report_doc.get("integrity_hash") and manifest_row.get("source_hash") == self.report_doc.get("source_hash")
            self._add_check("audit_report", "operations_audit_manifest_report_hash", "passed" if ok else "failed", "blocking", "Manifest Audit Report reference matches report." if ok else "Manifest Audit Report reference does not match report.")
        if self.ledger_entries:
            chain_ok = audit_ledger_integrity_ok(self.ledger_entries)
            ledger_hash = audit_ledger_hash(self.ledger_entries)
            self._add_check("ledger", "operations_audit_ledger_chain", "passed" if chain_ok else "failed", "blocking", "Operations Audit ledger hash chain is valid." if chain_ok else "Operations Audit ledger hash chain failed.")
            report_hash_ok = bool(self.report_doc) and self.report_doc.get("ledger_hash") == ledger_hash
            self._add_check("ledger", "operations_audit_report_ledger_hash", "passed" if report_hash_ok else "failed", "blocking", "Audit Report ledger hash matches ledger entries." if report_hash_ok else "Audit Report ledger hash does not match ledger entries.")
            manifest_row = _as_document(self.manifest.get("audit_report"))
            manifest_hash_ok = manifest_row.get("ledger_hash") == ledger_hash
            self._add_check("ledger", "operations_audit_manifest_ledger_hash", "passed" if manifest_hash_ok else "failed", "blocking", "Audit manifest ledger hash matches ledger entries." if manifest_hash_ok else "Audit manifest ledger hash does not match ledger entries.")
        else:
            self._add_check("ledger", "operations_audit_ledger_exists", "failed", "blocking", "operations-audit-ledger.jsonl has no valid entries.")
        self._verify_change_request_causality()
        failed_verifiers = _failed_verifiers(self.package_verifier_ledger)
        self._add_check("package_verifiers", "operations_audit_package_verifier_status", "failed" if failed_verifiers else "passed", "blocking", "Package verifier evidence failed: " + ", ".join(failed_verifiers[:5]) if failed_verifiers else "Package verifier evidence is passed, warning, or missing.")

    def _verify_change_request_causality(self) -> None:
        requests = _as_list(self.change_request_ledger.get("change_requests"))
        requests_by_id = {str(item.get("change_request_id") or ""): item for item in requests if isinstance(item, dict)}
        reset_event_types = {
            "operations_signoff_reset",
            "operations_signoff_history_reset",
            "release_event_operations_signoff_reset",
        }
        reset_entries = [item for item in self.ledger_entries if item.get("event_type") in reset_event_types]
        errors: list[str] = []
        for entry in reset_entries:
            causal_refs = _as_list(entry.get("causal_refs"))
            change_request_id = ""
            for ref in causal_refs:
                if isinstance(ref, dict) and ref.get("type") == "change_request" and ref.get("id"):
                    change_request_id = str(ref.get("id"))
                    break
            if not change_request_id:
                errors.append(f"{entry.get('entry_id')} missing change request causal ref")
                continue
            request = requests_by_id.get(change_request_id)
            if not request:
                errors.append(f"{entry.get('entry_id')} missing change request {change_request_id}")
                continue
            if request.get("status") != "applied":
                errors.append(f"{change_request_id} is not applied")
            if request.get("integrity_hash") != operations_change_request_hash(request):
                errors.append(f"{change_request_id} integrity failed")
            reset_hash = (entry.get("evidence_ref") or {}).get("payload_hash")
            if not reset_hash:
                errors.append(f"{entry.get('entry_id')} missing reset payload hash")
                continue
            if str(request.get("applied_signoff_reset_hash") or "") != str(reset_hash or ""):
                errors.append(f"{change_request_id} reset hash mismatch")
        self._add_check("change_requests", "operations_audit_change_request_reset_causality", "failed" if errors else "passed", "blocking", "Invalid reset causality: " + "; ".join(errors[:5]) if errors else "Operations reset entries are bound to applied Change Requests.")

    def _verify_requirements(self) -> None:
        if self.require_current:
            ok = bool(self.report_doc) and self.report_doc.get("status") != "failed" and not self.report_doc.get("blockers")
            self._add_check("requirements", "operations_audit_require_current", "passed" if ok else "failed", "blocking", "Operations Audit Report is current enough for export." if ok else "Current Operations Audit Report is required.")
        if self.require_signed:
            status = str(self.signoff_summary.get("status") or "")
            ok = status in {"signed", "force_signed"}
            self._add_check("requirements", "operations_audit_require_signed", "passed" if ok else "failed", "blocking", f"Operations Signoff status is {status!r}; signed required.")
        if self.require_archive:
            exported = any(item.get("event_type") == "operations_archive_exported" for item in self.ledger_entries)
            verified_entries = [item for item in self.ledger_entries if item.get("event_type") == "operations_archive_verified"]
            verified = bool(verified_entries) and all(((item.get("evidence_ref") or {}).get("integrity_ok") is not False) for item in verified_entries)
            ok = exported and verified
            if ok:
                message = "Operations Archive export and verification evidence exist."
            elif not exported:
                message = "Operations Archive export evidence is required."
            else:
                message = "Operations Archive verification evidence is required."
            self._add_check("requirements", "operations_audit_require_archive", "passed" if ok else "failed", "blocking", message)

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".jsonl", ".txt", ".csv")):
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
        self._add_check("redaction", "operations_audit_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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
        return sanitize_metadata(_as_document(value), blocked_keys=VERIFIER_BLOCKED_KEYS)

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
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": OPERATIONS_AUDIT_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": status,
            "zip_path": self.zip_path.name,
            "summary": {
                "release_id": self.manifest.get("release_id") or self.report_doc.get("release_id"),
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


def _failed_verifiers(value: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        status = value.get("status")
        if isinstance(status, str) and status not in {"passed", "warning", "missing", "not_required"}:
            rows.append(str(value.get("profile_id") or value.get("target_id") or status))
        for key, item in value.items():
            if key == "status":
                continue
            if isinstance(item, dict) and item.get("status") not in {None, "passed", "warning", "missing", "not_required"}:
                rows.append(str(key))
            elif isinstance(item, (list, dict)):
                rows.extend(_failed_verifiers(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_failed_verifiers(item))
    return rows


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
    findings: list[ImplementationDocument] = []
    for pattern, replacement in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        for match in pattern.finditer(text):
            findings.append({"path": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[ImplementationDocument] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "pattern": f"blocked_key:{path}", "excerpt": path})
            findings.extend(_blocked_key_findings(name, child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_blocked_key_findings(name, child, f"{prefix}[{index}]"))
    return findings
