from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument
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
from song_agent.domains.trust.release_operations_contracts import operations_report_integrity_hash as operations_report_integrity_hash
from song_agent.domains.trust.release_operations_signoff_contracts import OPERATIONS_SIGNOFF_BLOCKED_KEYS as OPERATIONS_SIGNOFF_BLOCKED_KEYS, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_hash as operations_signoff_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


OPERATIONS_ARCHIVE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"operations-archive-manifest.json", "operations-signoff.json", "operations-report.json", "latest-runbook-summary.json", "verifier-summaries.json", "package-ledger.json", "change-request-summary.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"operations-archive-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = OPERATIONS_SIGNOFF_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_operations_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _OperationsArchiveVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_operations_archive_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "signoff_status": summary.get("signoff_status"),
            "current_stage": summary.get("current_stage"),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_operations_archive_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_operations_archive_verification_report(report: dict[str, Any]) -> None:
    summary = release_operations_archive_verification_summary(report)
    print("MusicForge release operations archive verification")
    print(f"status: {summary.get('status')}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"signoff: {summary.get('signoff_status') or '-'}")
    print(f"stage: {summary.get('current_stage') or '-'}")
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


def release_operations_archive_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _OperationsArchiveVerifier:
    def __init__(self, zip_path: Path, *, strict: bool, require_signed: bool, max_zip_size_mb: int, max_uncompressed_size_mb: int, max_entry_count: int, now: str | None) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_signed = require_signed
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.runbook_summary: dict[str, Any] = {}
        self.verifier_summaries: dict[str, Any] = {}
        self.package_ledger: dict[str, Any] = {}
        self.change_summary: dict[str, Any] = {}
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
                if "operations-archive-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "operations-archive-manifest.json", "manifest", "operations_archive_manifest_parse")
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
            self._add_check("zip", "operations_archive_zip_open", "failed", "blocking", "Operations Archive ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "operations_archive_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "operations_archive_zip_open", "failed", "blocking", f"Operations Archive ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "operations_archive_zip_open", "passed", "blocking", "Operations Archive ZIP can be opened.")
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
        self._add_check("zip", "operations_archive_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "operations_archive_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "operations_archive_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "operations_archive_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "operations_archive_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Operations Archive entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "operations_archive_manifest_exists", "failed", "blocking", "operations-archive-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "operations_archive_manifest_exists", "passed", "blocking", "operations-archive-manifest.json exists.")
        actual_manifest_hash = operations_archive_manifest_hash(self.manifest)
        self._add_check("manifest", "operations_archive_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Operations Archive manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Operations Archive manifest integrity hash does not match.")
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
        self._add_check("manifest", "operations_archive_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "operations_archive_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Archive file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Operations Archive manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "operations_archive_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "operations_archive_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.signoff = self._read_json_entry(archive, "operations-signoff.json", "signoff", "operations_archive_signoff_parse")
        self.report_doc = self._read_json_entry(archive, "operations-report.json", "operations", "operations_archive_report_parse")
        self.runbook_summary = self._read_json_entry(archive, "latest-runbook-summary.json", "runbook", "operations_archive_runbook_parse")
        self.verifier_summaries = self._read_json_entry(archive, "verifier-summaries.json", "verifiers", "operations_archive_verifier_summary_parse")
        self.package_ledger = self._read_json_entry(archive, "package-ledger.json", "ledger", "operations_archive_package_ledger_parse")
        self.change_summary = self._read_json_entry(archive, "change-request-summary.json", "change_requests", "operations_archive_change_summary_parse")

    def _verify_documents(self) -> None:
        if self.signoff:
            actual = operations_signoff_hash(self.signoff)
            self._add_check("signoff", "operations_archive_signoff_payload_hash", "passed" if self.signoff.get("payload_hash") == actual else "failed", "blocking", "Operations Signoff payload hash matches." if self.signoff.get("payload_hash") == actual else "Operations Signoff payload hash does not match.")
            manifest_row = self.manifest.get("operations_signoff") if isinstance(self.manifest.get("operations_signoff"), dict) else {}
            self._add_check("signoff", "operations_archive_manifest_signoff_hash", "passed" if manifest_row.get("payload_hash") == actual else "failed", "blocking", "Manifest signoff hash matches." if manifest_row.get("payload_hash") == actual else "Manifest signoff hash does not match.")
        if self.report_doc:
            actual = operations_report_integrity_hash(self.report_doc)
            self._add_check("operations", "operations_archive_report_integrity", "passed" if self.report_doc.get("integrity_hash") == actual else "failed", "blocking", "Operations Report integrity hash matches." if self.report_doc.get("integrity_hash") == actual else "Operations Report integrity hash does not match.")
            manifest_row = self.manifest.get("operations_report") if isinstance(self.manifest.get("operations_report"), dict) else {}
            self._add_check("operations", "operations_archive_manifest_report_hash", "passed" if manifest_row.get("report_hash") == actual else "failed", "blocking", "Manifest Operations Report hash matches." if manifest_row.get("report_hash") == actual else "Manifest Operations Report hash does not match.")
        if self.package_ledger:
            actual = stable_hash({key: value for key, value in self.package_ledger.items() if key != "ledger_hash"})
            self._add_check("ledger", "operations_archive_package_ledger_hash", "passed" if self.package_ledger.get("ledger_hash") == actual else "failed", "blocking", "Package ledger hash matches." if self.package_ledger.get("ledger_hash") == actual else "Package ledger hash does not match.")
            manifest_row = self.manifest.get("package_ledger") if isinstance(self.manifest.get("package_ledger"), dict) else {}
            self._add_check("ledger", "operations_archive_manifest_ledger_hash", "passed" if manifest_row.get("ledger_hash") == actual else "failed", "blocking", "Manifest package ledger hash matches." if manifest_row.get("ledger_hash") == actual else "Manifest package ledger hash does not match.")
        if self.verifier_summaries:
            failed = _failed_verifiers(self.verifier_summaries)
            self._add_check("verifiers", "operations_archive_verifier_status", "failed" if failed else "passed", "blocking", "Verifier summaries failed: " + ", ".join(failed[:5]) if failed else "All verifier summaries are passed, warning, or missing.")
        if self.change_summary:
            self._add_check("change_requests", "operations_archive_change_summary_hash", "passed" if self.manifest.get("change_request_summary", {}).get("summary_hash") == stable_hash(self.change_summary) else "failed", "blocking", "Change request summary hash matches." if self.manifest.get("change_request_summary", {}).get("summary_hash") == stable_hash(self.change_summary) else "Change request summary hash does not match.")
        if self.signoff and self.report_doc:
            ok = str(self.signoff.get("source_hash") or "") == str(self.report_doc.get("source_hash") or "")
            self._add_check("signoff", "operations_archive_signoff_source_hash", "passed" if ok else "failed", "blocking", "Operations Signoff source hash matches Operations Report." if ok else "Operations Signoff source hash does not match Operations Report.")

    def _verify_requirements(self) -> None:
        if self.require_signed:
            status = str(self.signoff.get("status") or "")
            self._add_check("requirements", "operations_archive_require_signed", "passed" if status in {"signed", "force_signed"} else "failed", "blocking", f"Operations Signoff status is {status!r}; signed required.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".csv")):
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
        self._add_check("redaction", "operations_archive_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": OPERATIONS_ARCHIVE_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": status,
            "zip_path": self.zip_path.name,
            "summary": {
                "release_id": self.manifest.get("release_id") or self.signoff.get("release_id") or self.report_doc.get("release_id"),
                "signoff_status": self.signoff.get("status"),
                "current_stage": self.report_doc.get("current_stage"),
                "entry_count": len(self.entry_infos),
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

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _failed_verifiers(value: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict) and item.get("status") not in {"passed", "warning", "missing"}:
                rows.append(str(key))
            elif isinstance(item, (list, dict)):
                rows.extend(_failed_verifiers(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("status") not in {"passed", "warning", "missing"}:
                rows.append(str(item.get("target_id") or item.get("submission_id") or item.get("status") or "package"))
            elif isinstance(item, (list, dict)):
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
    findings: list[dict[str, Any]] = []
    for pattern, replacement in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        for match in pattern.finditer(text):
            findings.append({"path": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
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
