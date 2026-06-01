from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import struct
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent import __version__
from song_agent.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS
from song_agent.distribution_verifier import verify_distribution_package, distribution_verification_summary
from song_agent.projectio import write_json
from song_agent.redaction import SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash
from song_agent.rights_clearance import verify_rights_summary_evidence
from song_agent.submission_export import SUBMISSION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS


SUBMISSION_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 1024
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 4096
DEFAULT_MAX_ENTRY_COUNT = 10000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"submission-manifest.json", "submission-signoff.json", "submission-report.json", "submission-targets.csv", "submission-events.jsonl", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"submission-manifest.json", "submission-signoff.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def verify_submission_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_submitted: bool = False,
    require_accepted: bool = False,
    require_rights_clearance: bool = False,
    deep: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _SubmissionPackageVerifier(
        Path(zip_path),
        strict=strict,
        require_submitted=require_submitted,
        require_accepted=require_accepted,
        require_rights_clearance=require_rights_clearance,
        deep=deep,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def submission_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "submission_id": summary.get("submission_id"),
            "item_count": summary.get("item_count", 0),
            "entry_count": summary.get("entry_count", 0),
            "checked_file_count": summary.get("checked_file_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def write_submission_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))


def print_submission_verification_report(report: dict[str, Any]) -> None:
    summary = submission_verification_summary(report)
    print("MusicForge submission package verification")
    print(f"status: {summary.get('status')}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"submission: {summary.get('submission_id') or 'unknown'}")
    print(f"items: {summary.get('item_count', 0)}")
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


def submission_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _SubmissionPackageVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_submitted: bool,
        require_accepted: bool,
        require_rights_clearance: bool,
        deep: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_submitted = require_submitted
        self.require_accepted = require_accepted
        self.require_rights_clearance = require_rights_clearance
        self.deep = deep
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.item_checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
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
                if "submission-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "submission-manifest.json", "manifest", "submission_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_signoff()
                self._verify_items(archive)
                self._verify_status_requirements()
                self._verify_csv(archive)
                self._verify_rights_clearance(archive)
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "zip_open", "failed", "blocking", "Submission ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.", count=self.zip_size_bytes)
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "zip_open", "failed", "blocking", f"Submission ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "zip_open", "passed", "blocking", "Submission ZIP can be opened.")
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
        self._add_check("zip", "zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required submission entries exist.", count=len(missing))

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "submission_manifest_exists", "failed", "blocking", "submission-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "submission_manifest_exists", "passed", "blocking", "submission-manifest.json exists.")
        missing_fields = [field for field in ("schema_version", "release_id", "submission_id", "source_hash", "qa_source_hash") if self.manifest.get(field) in (None, "")]
        if not isinstance(self.manifest.get("files"), list):
            missing_fields.append("files")
        if not isinstance(self.manifest.get("items"), list):
            missing_fields.append("items")
        if not isinstance(self.manifest.get("summary"), dict):
            missing_fields.append("summary")
        self._add_check("manifest", "submission_manifest_schema", "failed" if missing_fields else "passed", "blocking", "Missing manifest fields: " + ", ".join(missing_fields) if missing_fields else "Submission manifest schema has required fields.", count=len(missing_fields))
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
            if not _is_safe_zip_entry(path):
                shape_errors.append(f"{path or f'files[{index}]'} has unsafe path")
            if not isinstance(size, int) or size < 0:
                shape_errors.append(f"{path or f'files[{index}]'} has invalid size")
            if not HEX_SHA256.fullmatch(sha):
                shape_errors.append(f"{path or f'files[{index}]'} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(size, int) and size >= 0 and HEX_SHA256.fullmatch(sha):
                valid_rows.append(item)
        self._add_check("manifest", "submission_manifest_files_shape", "failed" if shape_errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(shape_errors[:5]) if shape_errors else "Manifest file rows are valid.", count=len(shape_errors))
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
        self._add_check("manifest", "submission_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Submission file mismatches: " + "; ".join(mismatches[:5]) if mismatches else "Submission manifest files match ZIP bytes.", count=len(mismatches))
        allowed = {str(item.get("path")) for item in valid_rows}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "submission_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.", count=len(extra))
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "submission_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.", count=len(spoofed))

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        if "submission-signoff.json" in self.entry_map:
            self.signoff = self._read_json_entry(archive, "submission-signoff.json", "signoff", "submission_signoff_parse")
        if "submission-report.json" in self.entry_map:
            self.report_doc = self._read_json_entry(archive, "submission-report.json", "report", "submission_report_parse")

    def _verify_signoff(self) -> None:
        if not self.signoff:
            self._add_check("signoff", "submission_signoff_exists", "failed", "blocking", "submission-signoff.json is missing or invalid.")
            return
        self._add_check("signoff", "submission_signoff_exists", "passed", "blocking", "submission-signoff.json exists.")
        signoff_status = self.signoff.get("status")
        self._add_check("signoff", "submission_signoff_status", "passed" if signoff_status in {"signed", "force_signed"} else "failed", "blocking", f"Submission signoff status is {signoff_status!r}.")
        manifest_hash = stable_hash({key: value for key, value in self.manifest.items() if key != "zip"})
        signoff_hash = self.signoff.get("export_manifest_hash")
        self._add_check("signoff", "submission_signoff_manifest_hash", "passed" if signoff_hash == manifest_hash else "failed", "blocking", "Submission signoff export_manifest_hash matches manifest without zip." if signoff_hash == manifest_hash else "Submission signoff export_manifest_hash does not match manifest without zip.")
        sidecars = self.manifest.get("sidecars") if isinstance(self.manifest.get("sidecars"), dict) else {}
        signoff_sidecar = sidecars.get("submission_signoff") if isinstance(sidecars.get("submission_signoff"), dict) else {}
        expected_payload_hash = signoff_sidecar.get("payload_hash")
        payload_hash = stable_hash(_submission_signoff_hash_payload(self.signoff))
        self._add_check("signoff", "submission_signoff_sidecar_payload_hash", "passed" if expected_payload_hash == payload_hash else "failed", "blocking", "submission-signoff.json payload hash matches manifest sidecar record." if expected_payload_hash == payload_hash else "submission-signoff.json payload hash does not match manifest sidecar record.")
        qa_source = self.signoff.get("qa_source_hash")
        manifest_qa_source = self.manifest.get("qa_source_hash")
        self._add_check("signoff", "submission_signoff_qa_source", "passed" if qa_source and qa_source == manifest_qa_source else "failed", "blocking", "Submission signoff qa_source_hash matches manifest." if qa_source and qa_source == manifest_qa_source else "Submission signoff qa_source_hash is missing or does not match manifest.")

    def _verify_items(self, archive: zipfile.ZipFile) -> None:
        items = self.manifest.get("items") if isinstance(self.manifest.get("items"), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id") or "unknown")
            target_id = str(item.get("target_id") or "unknown")
            base = f"targets/{target_id}"
            zip_entry = f"{base}/distribution-package.zip"
            manifest_entry = f"{base}/distribution-manifest.json"
            report_entry = f"{base}/distribution-verify-report.json"
            missing = [path for path in (zip_entry, manifest_entry, report_entry) if path not in self.entry_map]
            self._add_item_check(item_id, "submission_target_entries_exist", "failed" if missing else "passed", "blocking", "Missing target entries: " + ", ".join(missing) if missing else "Target distribution entries exist.", target_id=target_id, count=len(missing))
            if zip_entry in self.entry_map:
                actual_sha = _sha256_entry(archive, self.entry_map[zip_entry])
                expected_sha = str(item.get("package_zip_sha256") or "")
                self._add_item_check(item_id, "target_distribution_zip_hash_match", "passed" if actual_sha == expected_sha else "failed", "blocking", "Distribution ZIP hash matches item snapshot." if actual_sha == expected_sha else "Distribution ZIP hash does not match item snapshot.", target_id=target_id)
                if self.deep:
                    with tempfile.TemporaryDirectory() as tmp:
                        nested = Path(tmp) / "distribution-package.zip"
                        nested.write_bytes(archive.read(self.entry_map[zip_entry]))
                        nested_report = verify_distribution_package(nested)
                    self._add_item_check(item_id, "target_distribution_deep_verify", "passed" if nested_report.get("status") in {"passed", "warning"} else "failed", "blocking", f"Nested distribution verifier status is {nested_report.get('status')}.", target_id=target_id, extra={"verification_summary": distribution_verification_summary(nested_report)})
            if report_entry in self.entry_map:
                report = self._read_json_entry(archive, report_entry, "item", "target_distribution_verify_report_parse")
                status = report.get("status")
                self._add_item_check(item_id, "target_distribution_verify_report_status", "passed" if status in {"passed", "warning"} else "failed", "blocking", f"Distribution verify report status is {status!r}.", target_id=target_id)

    def _verify_status_requirements(self) -> None:
        items = [item for item in self.manifest.get("items", []) if isinstance(item, dict)]
        if self.require_submitted:
            bad = [str(item.get("item_id") or item.get("target_id")) for item in items if item.get("status") not in {"submitted", "feedback_received", "needs_changes", "accepted"}]
            self._add_check("status", "submission_items_submitted", "failed" if bad else "passed", "blocking", "Items not submitted: " + ", ".join(bad[:5]) if bad else "All items have submitted-or-later status.", count=len(bad))
        if self.require_accepted:
            bad = [str(item.get("item_id") or item.get("target_id")) for item in items if item.get("status") != "accepted"]
            self._add_check("status", "submission_items_accepted", "failed" if bad else "passed", "blocking", "Items not accepted: " + ", ".join(bad[:5]) if bad else "All items are accepted.", count=len(bad))

    def _verify_csv(self, archive: zipfile.ZipFile) -> None:
        info = self.entry_map.get("submission-targets.csv")
        if info is None:
            self._add_check("csv", "submission_targets_csv_parse", "failed", "blocking", "submission-targets.csv is missing.")
            return
        issues: list[str] = []
        try:
            rows = list(csv.reader(io.StringIO(archive.read(info).decode("utf-8"))))
        except (OSError, UnicodeDecodeError, csv.Error, RuntimeError) as exc:
            self._add_check("csv", "submission_targets_csv_parse", "failed", "blocking", f"submission-targets.csv is not valid UTF-8 CSV: {exc}")
            return
        for row_index, row in enumerate(rows, start=1):
            for col_index, cell in enumerate(row, start=1):
                if _formula_cell(cell):
                    issues.append(f"{row_index}:{col_index}")
        self._add_check("csv", "submission_targets_csv_formula_safe", "failed" if issues else "passed", "blocking", "CSV formula issues: " + ", ".join(issues[:5]) if issues else "Submission target CSV cells are formula-safe.", count=len(issues))

    def _verify_rights_clearance(self, archive: zipfile.ZipFile) -> None:
        manifest_rights = self.manifest.get("rights_clearance") if isinstance(self.manifest.get("rights_clearance"), dict) else {}
        signoff_rights = self.signoff.get("rights_clearance") if isinstance(self.signoff.get("rights_clearance"), dict) else {}
        required = bool(self.require_rights_clearance or signoff_rights.get("require_rights_clearance") or manifest_rights.get("report_hash"))
        if not required and str(manifest_rights.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("rights_clearance", "submission_rights_clearance_optional", "passed", "warning", "Rights clearance evidence is not required.")
            return
        summary_path = str(manifest_rights.get("summary_path") or "rights/summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("rights_clearance", "submission_rights_clearance_summary_exists", status, "blocking" if status == "failed" else "warning", "rights/summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "rights_clearance", "submission_rights_summary_parse")
        failures = verify_rights_summary_evidence(manifest_summary=manifest_rights, summary=summary, required=required)
        if signoff_rights and str(signoff_rights.get("report_hash") or "") != str(manifest_rights.get("report_hash") or ""):
            failures.append("signoff_report_hash")
        self._add_check(
            "rights_clearance",
            "submission_rights_clearance_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Submission rights clearance evidence is present." if not failures else "Submission rights clearance failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        scan_names = [
            name
            for name in self.entry_names
            if name in {"submission-manifest.json", "submission-signoff.json", "submission-report.json", "submission-targets.csv", "submission-events.jsonl", "README.txt"}
            or name.endswith(("/distribution-manifest.json", "/distribution-verify-report.json"))
        ]
        for name in scan_names:
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
        self._add_check("redaction", "submission_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.", count=len(self.redaction_findings))

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

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str, *, count: int | None = None) -> None:
        item: dict[str, Any] = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if count is not None:
            item["count"] = count
        self.checks.append(sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _add_item_check(self, item_id: str, check_id: str, status: str, severity: str, message: str, *, target_id: str | None = None, count: int | None = None, extra: dict[str, Any] | None = None) -> None:
        item: dict[str, Any] = {"scope": "item", "item_id": item_id, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if target_id:
            item["target_id"] = target_id
        if count is not None:
            item["count"] = count
        if extra:
            item.update(extra)
        self.item_checks.append(sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in [*self.checks, *self.item_checks] if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in [*self.checks, *self.item_checks] if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        items = self.manifest.get("items") if isinstance(self.manifest.get("items"), list) else []
        report = {
            "schema_version": SUBMISSION_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Submission Package Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "require_submitted": self.require_submitted,
            "require_accepted": self.require_accepted,
            "deep": self.deep,
            "summary": {
                "release_id": self.manifest.get("release_id"),
                "submission_id": self.manifest.get("submission_id"),
                "item_count": len(items),
                "entry_count": len(self.entry_infos),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "total_uncompressed_size_bytes": self.total_uncompressed_size,
            },
            "checks": self.checks,
            "item_checks": self.item_checks,
            "files": self.files,
            "redaction_findings": self.redaction_findings,
            "warnings": warnings,
            "blockers": blockers,
        }
        return sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _is_safe_zip_entry(name: str) -> bool:
    raw = str(name or "")
    if "\\" in raw:
        return False
    if not raw or raw.endswith("/") or raw.startswith("/") or raw.startswith("//"):
        return False
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return PurePosixPath(*parts).as_posix() == raw


def _raw_zip_entry_names(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    names: list[str] = []
    offset = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, offset)
        if index < 0 or index + 46 > len(data):
            break
        flags = struct.unpack_from("<H", data, index + 8)[0]
        name_len = struct.unpack_from("<H", data, index + 28)[0]
        extra_len = struct.unpack_from("<H", data, index + 30)[0]
        comment_len = struct.unpack_from("<H", data, index + 32)[0]
        name_start = index + 46
        name_end = name_start + name_len
        if name_end > len(data):
            break
        raw = data[name_start:name_end]
        encoding = "utf-8" if flags & 0x800 else "cp437"
        try:
            names.append(raw.decode(encoding))
        except UnicodeDecodeError:
            names.append(raw.decode("utf-8", errors="replace"))
        offset = name_end + extra_len + comment_len
    return names


def _submission_signoff_hash_payload(signoff: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in signoff.items() if key not in SUBMISSION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}


def _formula_cell(cell: str) -> bool:
    text = str(cell or "")
    return bool(text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"))


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


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


def _redaction_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": kind, "message": f"{path} contains a local path-like value."})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "message": f"{path} contains a sensitive value pattern: {replacement}."})
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in DISTRIBUTION_BLOCKED_KEYS:
                findings.append({"path": path, "field": child_path, "kind": "blocked_key", "message": f"{path} contains blocked key {child_path}."})
            findings.extend(_blocked_key_findings(path, item, prefix=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(path, item, prefix=f"{prefix}[{index}]"))
    return findings


def _main() -> None:
    report = verify_submission_package(Path(sys.argv[1]))
    print_submission_verification_report(report)
    raise SystemExit(submission_verification_exit_code(report))


if __name__ == "__main__":
    _main()
