from __future__ import annotations

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
from song_agent.domains.trust.release_portfolio_audit_contracts import PORTFOLIO_AUDIT_BLOCKED_KEYS, portfolio_manifest_integrity_hash, portfolio_report_integrity_hash, portfolio_risk_register_integrity_hash, portfolio_trend_integrity_hash
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS


PORTFOLIO_AUDIT_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "manifest.json",
    "portfolio-audit-report.json",
    "portfolio-trend-report.json",
    "portfolio-risks.json",
    "release-index.json",
    "reviewer-pack-summary.json",
    "change-request-summary.json",
    "runbook-summary.json",
    "audit-summary.json",
    "PORTFOLIO_REVIEW.md",
    "PORTFOLIO_RETROSPECTIVE.md",
    "RISK_REGISTER.md",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PORTFOLIO_AUDIT_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_audit_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_reviewer_packs: bool = False,
    require_audit: bool = False,
    require_archive: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _PortfolioAuditVerifier(
        Path(zip_path),
        strict=strict,
        require_reviewer_packs=require_reviewer_packs,
        require_audit=require_audit,
        require_archive=require_archive,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_portfolio_audit_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "portfolio_id": summary.get("portfolio_id"),
            "release_count": summary.get("release_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "risk_score": summary.get("risk_score"),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_portfolio_audit_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_audit_verification_report(report: dict[str, Any]) -> None:
    summary = release_portfolio_audit_verification_summary(report)
    print("MusicForge release portfolio audit verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"releases: {summary.get('release_count', 0)}")
    print(f"risk score: {summary.get('risk_score') if summary.get('risk_score') is not None else '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = report.get(key) if isinstance(report.get(key), list) else []
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_audit_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PortfolioAuditVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_reviewer_packs: bool,
        require_audit: bool,
        require_archive: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_reviewer_packs = require_reviewer_packs
        self.require_audit = require_audit
        self.require_archive = require_archive
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.audit_report: dict[str, Any] = {}
        self.trend_report: dict[str, Any] = {}
        self.risk_register: dict[str, Any] = {}
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
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "portfolio_audit_manifest_parse")
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
            self._add_check("zip", "portfolio_audit_zip_open", "failed", "blocking", "Portfolio Audit ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "portfolio_audit_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "portfolio_audit_zip_open", "failed", "blocking", f"Portfolio Audit ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "portfolio_audit_zip_open", "passed", "blocking", "Portfolio Audit ZIP can be opened.")
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
        self._add_check("zip", "portfolio_audit_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "portfolio_audit_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "portfolio_audit_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "portfolio_audit_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "portfolio_audit_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Portfolio Audit entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "portfolio_audit_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "portfolio_audit_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = portfolio_manifest_integrity_hash(self.manifest)
        self._add_check("manifest", "portfolio_audit_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Portfolio Audit manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Portfolio Audit manifest integrity hash does not match.")
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
        self._add_check("manifest", "portfolio_audit_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "portfolio_audit_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Portfolio Audit file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Portfolio Audit manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "portfolio_audit_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "portfolio_audit_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.audit_report = self._read_json_entry(archive, "portfolio-audit-report.json", "portfolio_report", "portfolio_audit_report_parse")
        self.trend_report = self._read_json_entry(archive, "portfolio-trend-report.json", "trend_report", "portfolio_trend_report_parse")
        self.risk_register = self._read_json_entry(archive, "portfolio-risks.json", "risk_register", "portfolio_risk_register_parse")

    def _verify_documents(self) -> None:
        if self.audit_report:
            actual = portfolio_report_integrity_hash(self.audit_report)
            self._add_check("portfolio_report", "portfolio_audit_report_integrity", "passed" if self.audit_report.get("integrity_hash") == actual else "failed", "blocking", "Portfolio Audit Report integrity hash matches." if self.audit_report.get("integrity_hash") == actual else "Portfolio Audit Report integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("portfolio_audit_report") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.audit_report.get("integrity_hash") and sidecar.get("source_hash") == self.audit_report.get("source_hash")
            self._add_check("portfolio_report", "portfolio_audit_manifest_report_hash", "passed" if ok else "failed", "blocking", "Manifest Portfolio Audit Report reference matches report." if ok else "Manifest Portfolio Audit Report reference does not match report.")
        if self.trend_report:
            actual = portfolio_trend_integrity_hash(self.trend_report)
            self._add_check("trend_report", "portfolio_trend_report_integrity", "passed" if self.trend_report.get("integrity_hash") == actual else "failed", "blocking", "Portfolio Trend Report integrity hash matches." if self.trend_report.get("integrity_hash") == actual else "Portfolio Trend Report integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("portfolio_trend_report") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.trend_report.get("integrity_hash") and sidecar.get("source_hash") == self.trend_report.get("source_hash")
            self._add_check("trend_report", "portfolio_audit_manifest_trend_hash", "passed" if ok else "failed", "blocking", "Manifest Portfolio Trend Report reference matches report." if ok else "Manifest Portfolio Trend Report reference does not match report.")
        if self.risk_register:
            actual = portfolio_risk_register_integrity_hash(self.risk_register)
            self._add_check("risk_register", "portfolio_risk_register_integrity", "passed" if self.risk_register.get("integrity_hash") == actual else "failed", "blocking", "Portfolio Risk Register integrity hash matches." if self.risk_register.get("integrity_hash") == actual else "Portfolio Risk Register integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("portfolio_risk_register") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.risk_register.get("integrity_hash") and sidecar.get("source_hash") == self.risk_register.get("source_hash")
            self._add_check("risk_register", "portfolio_audit_manifest_risk_hash", "passed" if ok else "failed", "blocking", "Manifest Portfolio Risk Register reference matches report." if ok else "Manifest Portfolio Risk Register reference does not match report.")

    def _verify_requirements(self) -> None:
        summaries = self.audit_report.get("release_summaries") if isinstance(self.audit_report.get("release_summaries"), list) else []
        if self.require_reviewer_packs:
            bad = [str(item.get("release_id")) for item in summaries if isinstance(item, dict) and item.get("reviewer_pack_verification_status") != "passed"]
            self._add_check("requirements", "portfolio_audit_require_reviewer_packs", "failed" if bad else "passed", "blocking", "Passed Reviewer Pack verification is required: " + ", ".join(bad[:5]) if bad else "All releases include passed Reviewer Pack verification.")
        if self.require_audit:
            bad = [str(item.get("release_id")) for item in summaries if isinstance(item, dict) and (item.get("audit_verification_status") != "passed" or item.get("audit_summary", {}).get("status") == "failed")]
            self._add_check("requirements", "portfolio_audit_require_audit", "failed" if bad else "passed", "blocking", "Passed Audit package verification is required: " + ", ".join(bad[:5]) if bad else "All releases include passed Audit verification.")
        if self.require_archive:
            bad = [str(item.get("release_id")) for item in summaries if isinstance(item, dict) and item.get("archive_summary", {}).get("verification_status") != "passed"]
            self._add_check("requirements", "portfolio_audit_require_archive", "failed" if bad else "passed", "blocking", "Passed Operations Archive verification is required: " + ", ".join(bad[:5]) if bad else "All releases include passed Archive verification.")

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
        self._add_check("redaction", "portfolio_audit_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = self.audit_report.get("summary") if isinstance(self.audit_report.get("summary"), dict) else {}
        risk_score = self.audit_report.get("risk_score") if isinstance(self.audit_report.get("risk_score"), dict) else {}
        report = {
            "schema_version": PORTFOLIO_AUDIT_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "summary": {
                "portfolio_id": self.manifest.get("portfolio_id") or self.audit_report.get("portfolio_id"),
                "portfolio_status": self.audit_report.get("status"),
                "release_count": summary.get("release_count", 0),
                "risk_score": risk_score.get("score"),
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


def _is_safe_zip_entry(name: str) -> bool:
    if "\\" in name:
        return False
    if not name or name.startswith("/") or name.startswith("//"):
        return False
    path = PurePosixPath(name)
    if path.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    if ":" in path.parts[0]:
        return False
    return True


def _raw_zip_entry_names(path: Path) -> list[str]:
    data = path.read_bytes()
    names: list[str] = []
    offset = 0
    signature = b"\x50\x4b\x01\x02"
    while True:
        index = data.find(signature, offset)
        if index < 0:
            break
        if index + 46 > len(data):
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        raw = data[start:end]
        try:
            names.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            names.append(raw.decode("cp437", errors="replace"))
        offset = end + extra_len + comment_len
    return names


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        for match in pattern.finditer(text):
            findings.append({"path": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                key_text = str(key)
                next_path = f"{path}.{key_text}" if path else key_text
                if key_text.lower() in {item.lower() for item in VERIFIER_BLOCKED_KEYS}:
                    findings.append({"path": name, "key": next_path, "pattern": "blocked_key", "excerpt": key_text})
                visit(item, next_path)
        elif isinstance(node, list):
            for index, item in enumerate(node[:200]):
                visit(item, f"{path}[{index}]")

    visit(value, "")
    return findings
