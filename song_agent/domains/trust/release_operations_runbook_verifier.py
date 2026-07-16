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

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.trust.release_operations_contracts import operations_report_integrity_hash as operations_report_integrity_hash
from song_agent.domains.trust.release_operations_runbook_contracts import RUNBOOK_BLOCKED_KEYS as RUNBOOK_BLOCKED_KEYS, execution_report_integrity_hash as execution_report_integrity_hash, runbook_integrity_hash as runbook_integrity_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS


RUNBOOK_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"runbook-manifest.json", "runbook.json", "execution-report.json", "operations-report-before.json", "operations-report-after.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"runbook-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = RUNBOOK_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_operations_runbook_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_completed: bool = False,
    require_current: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _RunbookVerifier(
        Path(zip_path),
        strict=strict,
        require_completed=require_completed,
        require_current=require_current,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_operations_runbook_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "runbook_id": summary.get("runbook_id"),
            "runbook_status": summary.get("runbook_status"),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_operations_runbook_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_operations_runbook_verification_report(report: dict[str, Any]) -> None:
    summary = release_operations_runbook_verification_summary(report)
    print("MusicForge release operations runbook package verification")
    print(f"status: {summary.get('status')}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"runbook: {summary.get('runbook_id') or 'unknown'}")
    print(f"runbook status: {summary.get('runbook_status') or '-'}")
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


def release_operations_runbook_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _RunbookVerifier:
    def __init__(self, zip_path: Path, *, strict: bool, require_completed: bool, require_current: bool, max_zip_size_mb: int, max_uncompressed_size_mb: int, max_entry_count: int, now: str | None) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_completed = require_completed
        self.require_current = require_current
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.runbook: dict[str, Any] = {}
        self.execution: dict[str, Any] = {}
        self.operations_before: dict[str, Any] = {}
        self.operations_after: dict[str, Any] = {}
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
                if "runbook-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "runbook-manifest.json", "manifest", "runbook_manifest_parse")
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
            self._add_check("zip", "runbook_zip_open", "failed", "blocking", "Runbook ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "runbook_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "runbook_zip_open", "failed", "blocking", f"Runbook ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "runbook_zip_open", "passed", "blocking", "Runbook ZIP can be opened.")
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
        self._add_check("zip", "runbook_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "runbook_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "runbook_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "runbook_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "runbook_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required runbook entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "runbook_manifest_exists", "failed", "blocking", "runbook-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "runbook_manifest_exists", "passed", "blocking", "runbook-manifest.json exists.")
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
            if not errors or (path and _is_safe_zip_entry(path) and isinstance(item.get("size_bytes"), int) and HEX_SHA256.fullmatch(str(item.get("sha256") or ""))):
                valid.append(item)
        self._add_check("manifest", "runbook_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "runbook_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Runbook file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Runbook manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "runbook_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "runbook_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.runbook = self._read_json_entry(archive, "runbook.json", "runbook", "runbook_parse")
        self.execution = self._read_json_entry(archive, "execution-report.json", "execution", "runbook_execution_parse")
        self.operations_before = self._read_json_entry(archive, "operations-report-before.json", "operations", "runbook_operations_before_parse")
        self.operations_after = self._read_json_entry(archive, "operations-report-after.json", "operations", "runbook_operations_after_parse")

    def _verify_documents(self) -> None:
        if self.runbook:
            actual = runbook_integrity_hash(self.runbook)
            self._add_check("runbook", "runbook_integrity", "passed" if self.runbook.get("integrity_hash") == actual else "failed", "blocking", "Runbook integrity hash matches content." if self.runbook.get("integrity_hash") == actual else "Runbook integrity hash does not match content.")
            manifest_row = self.manifest.get("runbook") if isinstance(self.manifest.get("runbook"), dict) else {}
            self._add_check("runbook", "runbook_manifest_hash", "passed" if manifest_row.get("runbook_hash") == actual else "failed", "blocking", "Manifest runbook hash matches." if manifest_row.get("runbook_hash") == actual else "Manifest runbook hash does not match.")
        if self.execution:
            actual = execution_report_integrity_hash(self.execution)
            self._add_check("execution", "runbook_execution_integrity", "passed" if self.execution.get("integrity_hash") == actual else "failed", "blocking", "Execution report integrity hash matches content." if self.execution.get("integrity_hash") == actual else "Execution report integrity hash does not match content.")
        for label, doc in (("before", self.operations_before), ("after", self.operations_after)):
            if doc:
                actual = operations_report_integrity_hash(doc)
                self._add_check("operations", f"runbook_operations_{label}_integrity", "passed" if doc.get("integrity_hash") == actual else "failed", "blocking", f"Operations {label} report integrity hash matches." if doc.get("integrity_hash") == actual else f"Operations {label} report integrity hash does not match.")
        if self.manifest:
            expected_stale = str(self.manifest.get("source_hash") or "") != str(self.manifest.get("current_operations_source_hash") or "")
            self._add_check("manifest", "runbook_manifest_stale_flag", "passed" if bool(self.manifest.get("stale")) == expected_stale else "failed", "blocking", "Runbook manifest stale flag matches source hashes." if bool(self.manifest.get("stale")) == expected_stale else "Runbook manifest stale flag does not match source hashes.")

    def _verify_requirements(self) -> None:
        if self.require_completed and self.runbook:
            status = str(self.runbook.get("status") or "")
            failed_safe = [item for item in self.runbook.get("items", []) if isinstance(item, dict) and item.get("risk") == "auto_safe" and item.get("status") == "failed"]
            ok = status in {"completed", "blocked"} and not failed_safe
            self._add_check("requirements", "runbook_require_completed", "passed" if ok else "failed", "blocking", f"Runbook status is {status!r}; completed/blocking evidence required.")
        if self.require_current and self.manifest:
            ok = not bool(self.manifest.get("stale"))
            self._add_check("requirements", "runbook_require_current", "passed" if ok else "failed", "blocking", "Runbook manifest is current." if ok else "Runbook manifest is stale.")

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
        self._add_check("redaction", "runbook_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not valid UTF-8 JSON: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} is valid JSON.")
        return value

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str, **extra: Any) -> None:
        row = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message, **extra}
        self.checks.append(sanitize_metadata(row, blocked_keys=VERIFIER_BLOCKED_KEYS))

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": RUNBOOK_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Release Operations Runbook Package Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "require_completed": self.require_completed,
            "require_current": self.require_current,
            "summary": {
                "release_id": self.manifest.get("release_id"),
                "runbook_id": self.manifest.get("runbook_id"),
                "runbook_status": self.runbook.get("status"),
                "entry_count": len(self.entry_infos),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "total_uncompressed_size_bytes": self.total_uncompressed_size,
            },
            "checks": self.checks,
            "files": self.files,
            "redaction_findings": self.redaction_findings,
            "warnings": warnings,
            "blockers": blockers,
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)


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


def _counts(values: list[str]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for value in values:
        rows[value] = rows.get(value, 0) + 1
    return rows


def _redaction_findings(path: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"path": path, "kind": kind, "pattern": pattern.pattern[:80], "excerpt": match.group(0)[:120]})
            if len(findings) >= 50:
                return findings
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"path": path, "kind": replacement, "pattern": pattern.pattern[:80], "excerpt": match.group(0)[:120]})
            if len(findings) >= 50:
                return findings
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            full = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS and child not in (None, "", [], {}):
                findings.append({"path": path, "key": full})
            findings.extend(_blocked_key_findings(path, child, prefix=full))
            if len(findings) >= 50:
                break
    elif isinstance(value, list):
        for index, child in enumerate(value[:200]):
            findings.extend(_blocked_key_findings(path, child, prefix=f"{prefix}[{index}]"))
            if len(findings) >= 50:
                break
    return findings
