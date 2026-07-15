from __future__ import annotations

import hashlib
import json
import re
import struct
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import write_json
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.delivery.submission_evidence import SUBMISSION_EVIDENCE_SIGNOFF_EXCLUDE_KEYS, SUBMITTED_OR_LATER, submission_evidence_attachment_integrity_hash, submission_evidence_record_integrity_hash, submission_evidence_report_integrity_hash, submission_evidence_signoff_payload_hash
from song_agent.domains.delivery.submission_verifier import submission_verification_summary, verify_submission_package


SUBMISSION_EVIDENCE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 1024
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 4096
DEFAULT_MAX_ENTRY_COUNT = 10000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"submission-evidence-manifest.json", "submission-evidence-report.json", "submission-evidence-signoff.json", "submission-package.zip", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"submission-evidence-manifest.json", "submission-evidence-signoff.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


def verify_submission_evidence_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_submitted: bool = False,
    require_accepted: bool = False,
    require_rights_clearance: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _SubmissionEvidencePackageVerifier(
        Path(zip_path),
        strict=strict,
        deep=deep,
        require_submitted=require_submitted,
        require_accepted=require_accepted,
        require_rights_clearance=require_rights_clearance,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def submission_evidence_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "submission_id": summary.get("submission_id"),
            "item_count": summary.get("item_count", 0),
            "evidence_count": summary.get("evidence_count", 0),
            "attachment_count": summary.get("attachment_count", 0),
            "round_count": summary.get("round_count", 0),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def write_submission_evidence_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))


def print_submission_evidence_verification_report(report: dict[str, Any]) -> None:
    summary = submission_evidence_verification_summary(report)
    print("MusicForge submission evidence package verification")
    print(f"status: {summary.get('status')}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"submission: {summary.get('submission_id') or 'unknown'}")
    print(f"items: {summary.get('item_count', 0)}")
    print(f"evidence: {summary.get('evidence_count', 0)}")
    print(f"attachments: {summary.get('attachment_count', 0)}")
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


def submission_evidence_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _SubmissionEvidencePackageVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        deep: bool,
        require_submitted: bool,
        require_accepted: bool,
        require_rights_clearance: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.deep = deep
        self.require_submitted = require_submitted
        self.require_accepted = require_accepted
        self.require_rights_clearance = require_rights_clearance
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.item_checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
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
                if "submission-evidence-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "submission-evidence-manifest.json", "manifest", "submission_evidence_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_signoff()
                self._verify_report()
                self._verify_records_and_attachments(archive)
                self._verify_nested_submission(archive)
                self._verify_status_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "zip_open", "failed", "blocking", "Submission evidence ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.", count=self.zip_size_bytes)
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "zip_open", "failed", "blocking", f"Submission evidence ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "zip_open", "passed", "blocking", "Submission evidence ZIP can be opened.")
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
        self._add_check("zip", "zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required evidence entries exist.", count=len(missing))

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "submission_evidence_manifest_exists", "failed", "blocking", "submission-evidence-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "submission_evidence_manifest_exists", "passed", "blocking", "submission-evidence-manifest.json exists.")
        missing_fields = [field for field in ("schema_version", "release_id", "submission_id", "source_hash") if self.manifest.get(field) in (None, "")]
        if not isinstance(self.manifest.get("files"), list):
            missing_fields.append("files")
        if not isinstance(self.manifest.get("summary"), dict):
            missing_fields.append("summary")
        self._add_check("manifest", "submission_evidence_manifest_schema", "failed" if missing_fields else "passed", "blocking", "Missing manifest fields: " + ", ".join(missing_fields) if missing_fields else "Evidence manifest schema has required fields.", count=len(missing_fields))
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
        self._add_check("manifest", "submission_evidence_manifest_files_shape", "failed" if shape_errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(shape_errors[:5]) if shape_errors else "Manifest file rows are valid.", count=len(shape_errors))
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
        self._add_check("manifest", "submission_evidence_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Evidence file mismatches: " + "; ".join(mismatches[:5]) if mismatches else "Evidence manifest files match ZIP bytes.", count=len(mismatches))
        allowed = {str(item.get("path")) for item in valid_rows}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "submission_evidence_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.", count=len(extra))
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "submission_evidence_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.", count=len(spoofed))

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        if "submission-evidence-report.json" in self.entry_map:
            self.report_doc = self._read_json_entry(archive, "submission-evidence-report.json", "report", "submission_evidence_report_parse")
        if "submission-evidence-signoff.json" in self.entry_map:
            self.signoff = self._read_json_entry(archive, "submission-evidence-signoff.json", "signoff", "submission_evidence_signoff_parse")

    def _verify_signoff(self) -> None:
        if not self.signoff:
            self._add_check("signoff", "submission_evidence_signoff_exists", "failed", "blocking", "submission-evidence-signoff.json is missing or invalid.")
            return
        self._add_check("signoff", "submission_evidence_signoff_exists", "passed", "blocking", "submission-evidence-signoff.json exists.")
        signoff_status = self.signoff.get("status")
        self._add_check("signoff", "submission_evidence_signoff_status", "passed" if signoff_status in {"signed", "force_signed"} else "failed", "blocking", f"Submission evidence signoff status is {signoff_status!r}.")
        manifest_hash = stable_hash({key: value for key, value in self.manifest.items() if key != "zip"})
        signoff_hash = self.signoff.get("export_manifest_hash")
        self._add_check("signoff", "submission_evidence_signoff_manifest_hash", "passed" if signoff_hash == manifest_hash else "failed", "blocking", "Evidence signoff export_manifest_hash matches manifest without zip." if signoff_hash == manifest_hash else "Evidence signoff export_manifest_hash does not match manifest without zip.")
        sidecars = self.manifest.get("sidecars") if isinstance(self.manifest.get("sidecars"), dict) else {}
        sidecar = sidecars.get("submission_evidence_signoff") if isinstance(sidecars.get("submission_evidence_signoff"), dict) else {}
        expected_payload_hash = sidecar.get("payload_hash")
        payload_hash = submission_evidence_signoff_payload_hash(self.signoff)
        self._add_check("signoff", "submission_evidence_signoff_sidecar_payload_hash", "passed" if expected_payload_hash == payload_hash else "failed", "blocking", "submission-evidence-signoff.json payload hash matches manifest sidecar record." if expected_payload_hash == payload_hash else "submission-evidence-signoff.json payload hash does not match manifest sidecar record.")
        if self.signoff.get("payload_hash"):
            self._add_check("signoff", "submission_evidence_signoff_payload_hash", "passed" if self.signoff.get("payload_hash") == payload_hash else "failed", "blocking", "Evidence signoff payload_hash matches content." if self.signoff.get("payload_hash") == payload_hash else "Evidence signoff payload_hash does not match content.")

    def _verify_report(self) -> None:
        if not self.report_doc:
            self._add_check("report", "submission_evidence_report_exists", "failed", "blocking", "submission-evidence-report.json is missing or invalid.")
            return
        self._add_check("report", "submission_evidence_report_exists", "passed", "blocking", "submission-evidence-report.json exists.")
        expected = self.manifest.get("report", {}).get("report_hash") if isinstance(self.manifest.get("report"), dict) else None
        actual = submission_evidence_report_integrity_hash(self.report_doc)
        self._add_check("report", "submission_evidence_report_hash", "passed" if expected == actual else "failed", "blocking", "Evidence report hash matches manifest." if expected == actual else "Evidence report hash does not match manifest.")
        stored = self.report_doc.get("integrity_hash")
        self._add_check("report", "submission_evidence_report_integrity", "passed" if stored == actual else "failed", "blocking", "Evidence report integrity hash matches content." if stored == actual else "Evidence report integrity hash does not match content.")
        self._add_check("report", "submission_evidence_report_status", "passed" if self.report_doc.get("status") in {"passed", "warning"} else "failed", "blocking", f"Evidence report status is {self.report_doc.get('status')!r}.")

    def _verify_records_and_attachments(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.startswith("items/"):
                continue
            if "/evidence/" in name and name.endswith(".json"):
                record = self._read_json_entry(archive, name, "evidence", "submission_evidence_record_parse")
                if not record:
                    continue
                actual = submission_evidence_record_integrity_hash(record)
                self._add_item_check(str(record.get("item_id") or ""), "submission_evidence_record_integrity", "passed" if record.get("integrity_hash") == actual else "failed", "blocking", "Evidence record integrity hash matches content." if record.get("integrity_hash") == actual else "Evidence record integrity hash does not match content.", evidence_id=record.get("evidence_id"))
            if "/attachments/" in name and name.endswith(".json"):
                attachment = self._read_json_entry(archive, name, "attachment", "submission_evidence_attachment_parse")
                if not attachment:
                    continue
                actual = submission_evidence_attachment_integrity_hash(attachment)
                self._add_item_check(str(attachment.get("item_id") or ""), "submission_evidence_attachment_metadata_integrity", "passed" if attachment.get("integrity_hash") == actual else "failed", "blocking", "Attachment metadata integrity hash matches content." if attachment.get("integrity_hash") == actual else "Attachment metadata integrity hash does not match content.", attachment_id=attachment.get("attachment_id"))
                bin_name = name[:-5] + ".bin"
                if bin_name not in self.entry_map:
                    self._add_item_check(str(attachment.get("item_id") or ""), "submission_evidence_attachment_bytes_exist", "failed", "blocking", f"Attachment bytes {bin_name} are missing.", attachment_id=attachment.get("attachment_id"))
                    continue
                info = self.entry_map[bin_name]
                actual_sha = _sha256_entry(archive, info)
                actual_size = int(info.file_size or 0)
                ok = actual_sha == str(attachment.get("sha256") or "") and actual_size == int(attachment.get("size_bytes") or -1)
                self._add_item_check(str(attachment.get("item_id") or ""), "submission_evidence_attachment_bytes_hash", "passed" if ok else "failed", "blocking", "Attachment bytes match metadata hash and size." if ok else "Attachment bytes do not match metadata hash or size.", attachment_id=attachment.get("attachment_id"))

    def _verify_nested_submission(self, archive: zipfile.ZipFile) -> None:
        info = self.entry_map.get("submission-package.zip")
        if info is None:
            self._add_check("nested_submission", "submission_evidence_nested_submission_exists", "failed", "blocking", "submission-package.zip is missing.")
            return
        expected = self.manifest.get("submission_package", {}) if isinstance(self.manifest.get("submission_package"), dict) else {}
        actual_sha = _sha256_entry(archive, info)
        actual_size = int(info.file_size or 0)
        ok = actual_sha == str(expected.get("sha256") or "") and actual_size == int(expected.get("size_bytes") or -1)
        self._add_check("nested_submission", "submission_evidence_nested_submission_hash", "passed" if ok else "failed", "blocking", "Nested submission package hash matches manifest." if ok else "Nested submission package hash does not match manifest.")
        signoff_sha = self.signoff.get("submission_package_sha256") if isinstance(self.signoff, dict) else None
        self._add_check("nested_submission", "submission_evidence_signoff_submission_hash", "passed" if signoff_sha == actual_sha else "failed", "blocking", "Evidence signoff binds the nested submission package hash." if signoff_sha == actual_sha else "Evidence signoff submission package hash does not match nested package.")
        if self.deep or self.require_rights_clearance:
            with tempfile.TemporaryDirectory() as tmp:
                nested = Path(tmp) / "submission-package.zip"
                nested.write_bytes(archive.read(info))
                nested_report = verify_submission_package(
                    nested,
                    deep=True,
                    require_submitted=False,
                    require_accepted=False,
                    require_rights_clearance=self.require_rights_clearance,
                )
            self._add_check("nested_submission", "submission_evidence_nested_submission_deep_verify", "passed" if nested_report.get("status") in {"passed", "warning"} else "failed", "blocking", f"Nested submission verifier status is {nested_report.get('status')}.", verification_summary=submission_verification_summary(nested_report))

    def _verify_status_requirements(self) -> None:
        items = self.report_doc.get("item_summaries") if isinstance(self.report_doc.get("item_summaries"), list) else []
        if self.require_submitted:
            bad = [str(item.get("item_id") or "") for item in items if isinstance(item, dict) and item.get("status") not in SUBMITTED_OR_LATER]
            self._add_check("status", "submission_evidence_items_submitted", "failed" if bad else "passed", "blocking", "Items not submitted: " + ", ".join(bad[:5]) if bad else "All evidence items are submitted-or-later.", count=len(bad))
        if self.require_accepted:
            bad = [str(item.get("item_id") or "") for item in items if isinstance(item, dict) and item.get("status") != "accepted"]
            self._add_check("status", "submission_evidence_items_accepted", "failed" if bad else "passed", "blocking", "Items not accepted: " + ", ".join(bad[:5]) if bad else "All evidence items are accepted.", count=len(bad))

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        scan_names = [
            name
            for name in self.entry_names
            if name in {"submission-evidence-manifest.json", "submission-evidence-report.json", "submission-evidence-signoff.json", "README.txt"}
            or name.endswith((".json", ".txt", ".csv"))
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
        self._add_check("redaction", "submission_evidence_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.", count=len(self.redaction_findings))

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
        self.checks.append(sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _add_item_check(self, item_id: str, check_id: str, status: str, severity: str, message: str, **extra: Any) -> None:
        item: dict[str, Any] = {"scope": "item", "item_id": item_id, "check_id": check_id, "status": status, "severity": severity, "message": message}
        item.update(extra)
        self.item_checks.append(sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in [*self.checks, *self.item_checks] if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in [*self.checks, *self.item_checks] if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
        report = {
            "schema_version": SUBMISSION_EVIDENCE_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Submission Evidence Package Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "deep": self.deep,
            "require_submitted": self.require_submitted,
            "require_accepted": self.require_accepted,
            "summary": {
                "release_id": self.manifest.get("release_id"),
                "submission_id": self.manifest.get("submission_id"),
                "item_count": summary.get("item_count", 0),
                "evidence_count": summary.get("evidence_count", 0),
                "attachment_count": summary.get("attachment_count", 0),
                "round_count": summary.get("round_count", 0),
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
            if str(key).lower() in DISTRIBUTION_BLOCKED_KEYS or str(key).lower() in {"source_path", "local_path", "file_path"}:
                findings.append({"path": path, "field": child_path, "kind": "blocked_key", "message": f"{path} contains blocked key {child_path}."})
            findings.extend(_blocked_key_findings(path, item, prefix=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(path, item, prefix=f"{prefix}[{index}]"))
    return findings
