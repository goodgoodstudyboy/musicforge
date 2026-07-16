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
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack_contracts import PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS, evidence_index_integrity_hash as evidence_index_integrity_hash, retrospective_report_integrity_hash as retrospective_report_integrity_hash, reviewer_pack_manifest_integrity_hash as reviewer_pack_manifest_integrity_hash, reviewer_report_integrity_hash as reviewer_report_integrity_hash, timeline_integrity_hash as timeline_integrity_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS


PORTFOLIO_GOVERNANCE_REVIEWER_PACK_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "manifest.json",
    "reviewer-report.json",
    "retrospective-report.json",
    "evidence-index.json",
    "timeline.json",
    "audit-summary.json",
    "queue-summaries.json",
    "signoff-summaries.json",
    "archive-verification-summaries.json",
    "change-request-ledger.json",
    "risk-summary.json",
    "REVIEWER_GUIDE.md",
    "RETROSPECTIVE.md",
    "evidence-index.md",
    "timeline.md",
    "report.md",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_reviewer_pack(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_audit: bool = False,
    require_signed: bool = False,
    require_archives: bool = False,
    require_no_force: bool = False,
    require_reset_cr_causality: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _PortfolioGovernanceReviewerPackVerifier(
        Path(zip_path),
        strict=strict,
        require_audit=require_audit,
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


def release_portfolio_governance_reviewer_pack_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "zip_sha256": report.get("zip_sha256"),
            "zip_size_bytes": report.get("zip_size_bytes"),
            "manifest_hash": report.get("manifest_hash"),
            "portfolio_id": summary.get("portfolio_id"),
            "reviewer_status": summary.get("reviewer_status"),
            "audit_status": summary.get("audit_status"),
            "queue_count": summary.get("queue_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_portfolio_governance_reviewer_pack_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_reviewer_pack_verification_report(report: dict[str, Any]) -> None:
    summary = release_portfolio_governance_reviewer_pack_verification_summary(report)
    print("MusicForge release portfolio governance reviewer pack verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"reviewer: {summary.get('reviewer_status') or '-'}")
    print(f"audit: {summary.get('audit_status') or '-'}")
    print(f"queues: {summary.get('queue_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = report.get(key) if isinstance(report.get(key), list) else []
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_reviewer_pack_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PortfolioGovernanceReviewerPackVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_audit: bool,
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
        self.require_audit = require_audit
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
        self.reviewer_report: dict[str, Any] = {}
        self.retrospective_report: dict[str, Any] = {}
        self.evidence_index: dict[str, Any] = {}
        self.timeline: dict[str, Any] = {}
        self.audit_summary: dict[str, Any] = {}
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
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "portfolio_governance_reviewer_pack_manifest_parse")
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
            self._add_check("zip", "portfolio_governance_reviewer_pack_zip_open", "failed", "blocking", "Portfolio Governance Reviewer Pack ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "portfolio_governance_reviewer_pack_zip_open", "failed", "blocking", f"Portfolio Governance Reviewer Pack ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_open", "passed", "blocking", "Portfolio Governance Reviewer Pack ZIP can be opened.")
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
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "portfolio_governance_reviewer_pack_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Portfolio Governance Reviewer Pack entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = reviewer_pack_manifest_integrity_hash(self.manifest)
        self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Reviewer Pack manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Reviewer Pack manifest integrity hash does not match.")
        package_type_ok = self.manifest.get("package_type") == "release_portfolio_governance_reviewer_pack"
        self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is release_portfolio_governance_reviewer_pack." if package_type_ok else "Manifest package_type is not release_portfolio_governance_reviewer_pack.")
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
        self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Reviewer Pack file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Reviewer Pack manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "portfolio_governance_reviewer_pack_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.reviewer_report = self._read_json_entry(archive, "reviewer-report.json", "reviewer_report", "portfolio_governance_reviewer_pack_report_parse")
        self.retrospective_report = self._read_json_entry(archive, "retrospective-report.json", "retrospective", "portfolio_governance_reviewer_pack_retrospective_parse")
        self.evidence_index = self._read_json_entry(archive, "evidence-index.json", "evidence_index", "portfolio_governance_reviewer_pack_evidence_index_parse")
        self.timeline = self._read_json_entry(archive, "timeline.json", "timeline", "portfolio_governance_reviewer_pack_timeline_parse")
        self.audit_summary = self._read_json_entry(archive, "audit-summary.json", "audit_summary", "portfolio_governance_reviewer_pack_audit_summary_parse")

    def _verify_documents(self) -> None:
        if self.reviewer_report:
            actual = reviewer_report_integrity_hash(self.reviewer_report)
            self._add_check("reviewer_report", "portfolio_governance_reviewer_pack_report_integrity", "passed" if self.reviewer_report.get("integrity_hash") == actual else "failed", "blocking", "Reviewer Report integrity hash matches." if self.reviewer_report.get("integrity_hash") == actual else "Reviewer Report integrity hash does not match.")
            manifest_row = self.manifest.get("reviewer_report") if isinstance(self.manifest.get("reviewer_report"), dict) else {}
            ok = manifest_row.get("integrity_hash") == self.reviewer_report.get("integrity_hash") and manifest_row.get("source_hash") == self.reviewer_report.get("source_hash")
            self._add_check("reviewer_report", "portfolio_governance_reviewer_pack_manifest_report_hash", "passed" if ok else "failed", "blocking", "Manifest Reviewer Report reference matches report." if ok else "Manifest Reviewer Report reference does not match report.")
        if self.retrospective_report:
            actual = retrospective_report_integrity_hash(self.retrospective_report)
            self._add_check("retrospective", "portfolio_governance_reviewer_pack_retrospective_integrity", "passed" if self.retrospective_report.get("integrity_hash") == actual else "failed", "blocking", "Retrospective Report integrity hash matches." if self.retrospective_report.get("integrity_hash") == actual else "Retrospective Report integrity hash does not match.")
            manifest_row = self.manifest.get("retrospective_report") if isinstance(self.manifest.get("retrospective_report"), dict) else {}
            ok = manifest_row.get("integrity_hash") == self.retrospective_report.get("integrity_hash") and manifest_row.get("source_hash") == self.retrospective_report.get("source_hash")
            self._add_check("retrospective", "portfolio_governance_reviewer_pack_manifest_retrospective_hash", "passed" if ok else "failed", "blocking", "Manifest Retrospective reference matches report." if ok else "Manifest Retrospective reference does not match report.")
        if self.evidence_index:
            actual = evidence_index_integrity_hash(self.evidence_index)
            self._add_check("evidence_index", "portfolio_governance_reviewer_pack_evidence_index_integrity", "passed" if self.evidence_index.get("integrity_hash") == actual else "failed", "blocking", "Evidence Index integrity hash matches." if self.evidence_index.get("integrity_hash") == actual else "Evidence Index integrity hash does not match.")
            manifest_row = self.manifest.get("evidence_index") if isinstance(self.manifest.get("evidence_index"), dict) else {}
            ok = manifest_row.get("integrity_hash") == self.evidence_index.get("integrity_hash") and manifest_row.get("source_hash") == self.evidence_index.get("source_hash")
            self._add_check("evidence_index", "portfolio_governance_reviewer_pack_manifest_evidence_index_hash", "passed" if ok else "failed", "blocking", "Manifest Evidence Index reference matches index." if ok else "Manifest Evidence Index reference does not match index.")
        if self.timeline:
            actual = timeline_integrity_hash(self.timeline)
            self._add_check("timeline", "portfolio_governance_reviewer_pack_timeline_integrity", "passed" if self.timeline.get("integrity_hash") == actual else "failed", "blocking", "Timeline integrity hash matches." if self.timeline.get("integrity_hash") == actual else "Timeline integrity hash does not match.")
            manifest_row = self.manifest.get("timeline") if isinstance(self.manifest.get("timeline"), dict) else {}
            ok = manifest_row.get("integrity_hash") == self.timeline.get("integrity_hash") and manifest_row.get("source_hash") == self.timeline.get("source_hash")
            self._add_check("timeline", "portfolio_governance_reviewer_pack_manifest_timeline_hash", "passed" if ok else "failed", "blocking", "Manifest Timeline reference matches timeline." if ok else "Manifest Timeline reference does not match timeline.")

    def _verify_requirements(self) -> None:
        summary = self.reviewer_report.get("summary") if isinstance(self.reviewer_report.get("summary"), dict) else {}
        manifest_audit = self.manifest.get("audit_summary") if isinstance(self.manifest.get("audit_summary"), dict) else {}
        if self.require_audit:
            report_integrity_ok = bool(self.reviewer_report) and self.reviewer_report.get("integrity_hash") == reviewer_report_integrity_hash(self.reviewer_report)
            ok = bool(
                self.reviewer_report
                and report_integrity_ok
                and self.reviewer_report.get("status") != "failed"
                and summary.get("audit_status") == "passed"
                and manifest_audit.get("audit_package_verification_status") == "passed"
            )
            self._add_check("requirements", "portfolio_governance_reviewer_pack_require_audit", "passed" if ok else "failed", "blocking", "Reviewer Pack contains usable Governance Audit evidence." if ok else "Usable Governance Audit evidence is required.")
        if self.require_signed:
            queues = int(summary.get("queue_count") or 0)
            signed = int(summary.get("signed_queue_count") or 0)
            ok = queues > 0 and signed >= queues
            self._add_check("requirements", "portfolio_governance_reviewer_pack_require_signed", "passed" if ok else "failed", "blocking", "All Governance Queues are signed." if ok else "Signed Governance Queue coverage is required.")
        if self.require_archives:
            signed = int(summary.get("signed_queue_count") or 0)
            archives = int(summary.get("archive_verified_count") or 0)
            ok = signed > 0 and archives >= signed
            self._add_check("requirements", "portfolio_governance_reviewer_pack_require_archives", "passed" if ok else "failed", "blocking", "All signed Governance Queues have verified Archive evidence." if ok else "Verified Governance Archive evidence is required.")
        if self.require_no_force:
            forced = int(summary.get("force_signed_queue_count") or 0)
            self._add_check("requirements", "portfolio_governance_reviewer_pack_require_no_force", "failed" if forced else "passed", "blocking", "Force-signed Governance Queues are not allowed." if forced else "No force-signed Governance Queues are present.")
        if self.require_reset_cr_causality:
            status = str(summary.get("reset_causality_status") or "")
            ok = status in {"passed", "not_applicable"}
            self._add_check("requirements", "portfolio_governance_reviewer_pack_require_reset_cr_causality", "passed" if ok else "failed", "blocking", "Reset Change Request causality is verified." if ok else "Reset Change Request causality is required.")

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
        self._add_check("redaction", "portfolio_governance_reviewer_pack_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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
        summary = self.reviewer_report.get("summary") if isinstance(self.reviewer_report.get("summary"), dict) else {}
        report = {
            "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "summary": {
                "portfolio_id": self.manifest.get("portfolio_id") or self.reviewer_report.get("portfolio_id"),
                "reviewer_status": self.reviewer_report.get("status"),
                "audit_status": summary.get("audit_status"),
                "queue_count": summary.get("queue_count", 0),
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
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "pattern": f"blocked_key:{path}", "excerpt": str(key)})
            findings.extend(_blocked_key_findings(name, item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{prefix}[{index}]"))
    return findings
