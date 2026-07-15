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

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.trust.release_operations_contracts import OPERATIONS_BLOCKED_KEYS, operations_report_integrity_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS


OPERATIONS_VERIFICATION_SCHEMA_VERSION = 1
OPERATIONS_VERIFICATION_PACKAGE_TYPE = "musicforge_release_operations_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"operations-manifest.json", "operations-report.json", "readiness-summary.json", "evidence-graph.json", "verifier-summaries.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"operations-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


def verify_release_operations_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_accepted: bool = False,
    require_submission_evidence: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _ReleaseOperationsVerifier(
        Path(zip_path),
        strict=strict,
        require_accepted=require_accepted,
        require_submission_evidence=require_submission_evidence,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_operations_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "current_stage": summary.get("current_stage"),
            "next_stage": summary.get("next_stage"),
            "entry_count": summary.get("entry_count", 0),
            "checked_file_count": summary.get("checked_file_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_operations_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_operations_verification_report(report: dict[str, Any]) -> None:
    summary = release_operations_verification_summary(report)
    print("MusicForge release operations package verification")
    print(f"status: {summary.get('status')}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"stage: {summary.get('current_stage') or '-'} -> {summary.get('next_stage') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"checked files: {summary.get('checked_file_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = report.get(key) if isinstance(report.get(key), list) else []
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            check_id = item.get("check_id", "unknown") if isinstance(item, dict) else "unknown"
            message = item.get("message", str(item)) if isinstance(item, dict) else str(item)
            print(f"  [{check_id}] {message}")
        if len(items) > 10:
            print(f"  ... {len(items) - 10} more")


def release_operations_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _ReleaseOperationsVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_accepted: bool,
        require_submission_evidence: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_accepted = require_accepted
        self.require_submission_evidence = require_submission_evidence
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.readiness: dict[str, Any] = {}
        self.evidence_graph: dict[str, Any] = {}
        self.verifier_summaries: dict[str, Any] = {}
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
                if "operations-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "operations-manifest.json", "manifest", "operations_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents(archive)
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "zip_open", "failed", "blocking", "Operations ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.", count=self.zip_size_bytes)
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "zip_open", "failed", "blocking", f"Operations ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "zip_open", "passed", "blocking", "Operations ZIP can be opened.")
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
        self._add_check("zip", "zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.", count=self.total_uncompressed_size)
        self._add_check("zip", "zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.", count=len(self.entry_infos))
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.", count=len(unsafe))
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.", count=len(duplicates))
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Operations entries exist.", count=len(missing))

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "operations_manifest_exists", "failed", "blocking", "operations-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "operations_manifest_exists", "passed", "blocking", "operations-manifest.json exists.")
        missing_fields = [field for field in ("schema_version", "release_id", "source_hash") if self.manifest.get(field) in (None, "")]
        if not isinstance(self.manifest.get("files"), list):
            missing_fields.append("files")
        if not isinstance(self.manifest.get("summary"), dict):
            missing_fields.append("summary")
        self._add_check("manifest", "operations_manifest_schema", "failed" if missing_fields else "passed", "blocking", "Missing manifest fields: " + ", ".join(missing_fields) if missing_fields else "Operations manifest schema has required fields.", count=len(missing_fields))
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        valid_rows: list[dict[str, Any]] = []
        shape_errors: list[str] = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                shape_errors.append(f"files[{index}] is not an object")
                continue
            path = str(item.get("path") or "")
            size = item.get("size_bytes")
            sha = str(item.get("sha256") or "")
            label = path or f"files[{index}]"
            if not _is_safe_zip_entry(path):
                shape_errors.append(f"{label} has unsafe path")
            if not isinstance(size, int) or size < 0:
                shape_errors.append(f"{label} has invalid size")
            if not HEX_SHA256.fullmatch(sha):
                shape_errors.append(f"{label} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(size, int) and size >= 0 and HEX_SHA256.fullmatch(sha):
                valid_rows.append(item)
        self._add_check("manifest", "operations_manifest_files_shape", "failed" if shape_errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(shape_errors[:5]) if shape_errors else "Manifest file rows are valid.", count=len(shape_errors))
        mismatches: list[str] = []
        for item in valid_rows:
            path = str(item["path"])
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(f"{path} missing from ZIP")
                continue
            actual_size = int(info.file_size or 0)
            actual_sha = _sha256_entry(archive, info)
            expected_size = int(item["size_bytes"])
            expected_sha = str(item["sha256"])
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_size == expected_size and actual_sha == expected_sha else "failed"})
            if actual_size != expected_size:
                mismatches.append(f"{path} size mismatch")
            if actual_sha != expected_sha:
                mismatches.append(f"{path} hash mismatch")
        self._add_check("manifest", "operations_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Operations file mismatches: " + "; ".join(mismatches[:5]) if mismatches else "Operations manifest files match ZIP bytes.", count=len(mismatches))
        allowed = {str(item.get("path")) for item in valid_rows}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "operations_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.", count=len(extra))
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "operations_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.", count=len(spoofed))

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        if "operations-report.json" in self.entry_map:
            self.report_doc = self._read_json_entry(archive, "operations-report.json", "report", "operations_report_parse")
        if "readiness-summary.json" in self.entry_map:
            self.readiness = self._read_json_entry(archive, "readiness-summary.json", "readiness", "operations_readiness_parse")
        if "evidence-graph.json" in self.entry_map:
            self.evidence_graph = self._read_json_entry(archive, "evidence-graph.json", "evidence_graph", "operations_evidence_graph_parse")
        if "verifier-summaries.json" in self.entry_map:
            self.verifier_summaries = self._read_json_entry(archive, "verifier-summaries.json", "verifiers", "operations_verifier_summaries_parse")

    def _verify_documents(self, archive: zipfile.ZipFile) -> None:
        if not self.report_doc:
            self._add_check("report", "operations_report_exists", "failed", "blocking", "operations-report.json is missing or invalid.")
            return
        self._add_check("report", "operations_report_exists", "passed", "blocking", "operations-report.json exists.")
        actual_report_hash = operations_report_integrity_hash(self.report_doc)
        stored_integrity = self.report_doc.get("integrity_hash")
        manifest_report = self.manifest.get("report") if isinstance(self.manifest.get("report"), dict) else {}
        self._add_check("report", "operations_report_integrity", "passed" if stored_integrity == actual_report_hash else "failed", "blocking", "Operations report integrity hash matches content." if stored_integrity == actual_report_hash else "Operations report integrity hash does not match content.")
        self._add_check("report", "operations_manifest_report_hash", "passed" if manifest_report.get("report_hash") == actual_report_hash and manifest_report.get("integrity_hash") == stored_integrity else "failed", "blocking", "Operations manifest report hash matches report content." if manifest_report.get("report_hash") == actual_report_hash and manifest_report.get("integrity_hash") == stored_integrity else "Operations manifest report hash does not match report content.")
        self._add_check("report", "operations_report_source_hash", "passed" if self.report_doc.get("source_hash") == self.manifest.get("source_hash") else "failed", "blocking", "Operations report source hash matches manifest." if self.report_doc.get("source_hash") == self.manifest.get("source_hash") else "Operations report source hash does not match manifest.")
        self._verify_sidecar_hash(archive, "readiness", "readiness-summary.json", self.readiness, self.manifest.get("readiness") if isinstance(self.manifest.get("readiness"), dict) else {})
        self._verify_sidecar_hash(archive, "evidence_graph", "evidence-graph.json", self.evidence_graph, self.manifest.get("evidence_graph") if isinstance(self.manifest.get("evidence_graph"), dict) else {})
        self._verify_sidecar_hash(archive, "verifiers", "verifier-summaries.json", self.verifier_summaries, self.manifest.get("verifier_summaries") if isinstance(self.manifest.get("verifier_summaries"), dict) else {})
        blockers = self.report_doc.get("blockers") if isinstance(self.report_doc.get("blockers"), list) else []
        warnings = self.report_doc.get("warnings") if isinstance(self.report_doc.get("warnings"), list) else []
        bad_shape = [
            item
            for item in [*blockers, *warnings]
            if not isinstance(item, dict) or not item.get("domain") or not item.get("check_id") or not item.get("message")
        ]
        self._add_check("report", "operations_blocker_warning_shape", "failed" if bad_shape else "passed", "blocking", "Invalid blocker/warning rows found." if bad_shape else "Blocker and warning rows have required fields.", count=len(bad_shape))

    def _verify_sidecar_hash(self, archive: zipfile.ZipFile, scope: str, path: str, document: dict[str, Any], manifest_row: dict[str, Any]) -> None:
        if not document:
            self._add_check(scope, f"operations_{scope}_exists", "failed", "blocking", f"{path} is missing or invalid.")
            return
        expected = manifest_row.get("sha256")
        info = self.entry_map.get(path)
        actual = _sha256_entry(archive, info) if info is not None else ""
        self._add_check(scope, f"operations_{scope}_hash", "passed" if expected == actual else "failed", "blocking", f"{path} hash matches manifest." if expected == actual else f"{path} hash does not match manifest.")

    def _verify_requirements(self) -> None:
        if not self.report_doc:
            return
        if self.require_accepted:
            stage = str(self.report_doc.get("current_stage") or "")
            ok = stage in {"accepted", "archived"}
            self._add_check("requirements", "operations_require_accepted", "passed" if ok else "failed", "blocking", f"Operations current stage is {stage!r}; accepted required.")
        if self.require_submission_evidence:
            evidence = self.report_doc.get("domains", {}).get("submission_evidence") if isinstance(self.report_doc.get("domains"), dict) else {}
            ok = isinstance(evidence, dict) and evidence.get("status") in {"passed", "warning"}
            self._add_check("requirements", "operations_require_submission_evidence", "passed" if ok else "failed", "blocking", "Submission Evidence domain is ready." if ok else "Submission Evidence domain is not ready.")

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
        self._add_check("redaction", "operations_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.", count=len(self.redaction_findings))

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
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

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str, *, count: int | None = None, **extra: Any) -> None:
        item: dict[str, Any] = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if count is not None:
            item["count"] = count
        item.update(extra)
        self.checks.append(sanitize_metadata(item, blocked_keys=VERIFIER_BLOCKED_KEYS))

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": OPERATIONS_VERIFICATION_SCHEMA_VERSION,
            "package_type": OPERATIONS_VERIFICATION_PACKAGE_TYPE,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Release Operations Package Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "require_accepted": self.require_accepted,
            "require_submission_evidence": self.require_submission_evidence,
            "summary": {
                "release_id": self.manifest.get("release_id"),
                "current_stage": self.report_doc.get("current_stage"),
                "next_stage": self.report_doc.get("next_stage"),
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
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(values: list[str]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for value in values:
        rows[value] = rows.get(value, 0) + 1
    return rows


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"path": name, "kind": replacement, "excerpt": match.group(0)[:120]})
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"path": name, "kind": kind, "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in OPERATIONS_BLOCKED_KEYS:
                findings.append({"path": name, "kind": "blocked_key", "key": child})
            findings.extend(_blocked_key_findings(name, item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{prefix}[{index}]"))
    return findings
