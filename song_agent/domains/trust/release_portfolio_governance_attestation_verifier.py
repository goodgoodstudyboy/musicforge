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
from song_agent.domains.trust.release_portfolio_governance_attestation_contracts import ATTESTATION_BLOCKED_KEYS, ATTESTATION_CERTIFICATE_TYPE, ATTESTATION_PACKAGE_TYPE, attestation_certificate_hash, attestation_manifest_hash, attestation_report_integrity_hash, attestation_verification_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS


ATTESTATION_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"manifest.json", "attestation-report.json", "certificate.json", "certificate.md", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ATTESTATION_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_attestation(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_vault: bool = False,
    require_final_board: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AttestationVerifier(
        Path(zip_path),
        strict=strict,
        require_vault=require_vault,
        require_final_board=require_final_board,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_release_portfolio_governance_attestation_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_attestation_verification_report(report: dict[str, Any]) -> None:
    summary = attestation_verification_summary(report)
    print("MusicForge release portfolio governance public attestation verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"certificate: {summary.get('certificate_id') or 'unknown'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_attestation_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AttestationVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_vault: bool,
        require_final_board: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_vault = require_vault
        self.require_final_board = require_final_board
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.certificate: dict[str, Any] = {}
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
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "attestation_manifest_parse")
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
            self._add_check("zip", "attestation_zip_open", "failed", "blocking", "Public Attestation ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "attestation_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "attestation_zip_open", "failed", "blocking", f"Public Attestation ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "attestation_zip_open", "passed", "blocking", "Public Attestation ZIP can be opened.")
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
        self._add_check("zip", "attestation_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "attestation_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "attestation_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "attestation_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "attestation_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Public Attestation entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "attestation_zip_no_nested_packages", "failed" if forbidden else "passed", "blocking", "Forbidden nested package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "attestation_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "attestation_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = attestation_manifest_hash(self.manifest)
        self._add_check("manifest", "attestation_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Attestation manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Attestation manifest integrity hash does not match.")
        package_type_ok = self.manifest.get("package_type") == ATTESTATION_PACKAGE_TYPE
        self._add_check("manifest", "attestation_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", f"Manifest package_type is {ATTESTATION_PACKAGE_TYPE}." if package_type_ok else "Manifest package_type is not release_portfolio_governance_public_attestation.")
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
        self._add_check("manifest", "attestation_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "attestation_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Attestation file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Attestation manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "attestation_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "attestation_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "attestation-report.json", "report", "attestation_report_parse")
        self.certificate = self._read_json_entry(archive, "certificate.json", "certificate", "attestation_certificate_parse")

    def _verify_documents(self) -> None:
        if self.report_doc:
            self._add_hash_check("report", "attestation_report_integrity", self.report_doc.get("integrity_hash"), attestation_report_integrity_hash(self.report_doc), "Attestation Report integrity")
            row = self.manifest.get("attestation_report") if isinstance(self.manifest.get("attestation_report"), dict) else {}
            self._add_hash_check("report", "attestation_manifest_report_hash", row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
            self._add_hash_check("report", "attestation_report_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest report source hash")
        if self.certificate:
            self._add_hash_check("certificate", "attestation_certificate_payload_hash", self.certificate.get("payload_hash"), attestation_certificate_hash(self.certificate), "Certificate payload hash")
            row = self.manifest.get("certificate") if isinstance(self.manifest.get("certificate"), dict) else {}
            self._add_hash_check("certificate", "attestation_manifest_certificate_hash", row.get("payload_hash"), self.certificate.get("payload_hash"), "Manifest certificate payload hash")
            self._add_hash_check("certificate", "attestation_manifest_certificate_id", row.get("certificate_id"), self.certificate.get("certificate_id"), "Manifest certificate id")
        evidence_manifest = self.manifest.get("evidence_vault") if isinstance(self.manifest.get("evidence_vault"), dict) else {}
        evidence_cert = self.certificate.get("evidence_vault") if isinstance(self.certificate.get("evidence_vault"), dict) else {}
        final_cert = self.certificate.get("final_board") if isinstance(self.certificate.get("final_board"), dict) else {}
        coverage_cert = self.certificate.get("coverage") if isinstance(self.certificate.get("coverage"), dict) else {}
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        expected_status = "passed" if self.report_doc.get("status") == "passed" else self.report_doc.get("status")
        self._add_value_check("certificate", "attestation_certificate_status", self.certificate.get("governance_status"), expected_status, "Certificate governance status")
        self._add_value_check("certificate", "attestation_certificate_profile", self.certificate.get("attestation_profile"), source.get("attestation_profile") or self.manifest.get("attestation_profile"), "Certificate attestation profile")
        self._add_value_check("certificate", "attestation_certificate_coverage_signed_queue_count", coverage_cert.get("signed_queue_count"), source.get("signed_queue_count"), "Certificate signed queue coverage")
        self._add_value_check("certificate", "attestation_certificate_coverage_force_signed_queue_count", coverage_cert.get("force_signed_queue_count"), source.get("force_signed_queue_count"), "Certificate force-signed queue coverage")
        self._add_value_check("certificate", "attestation_certificate_reviewer_response_status", coverage_cert.get("reviewer_response_status"), source.get("reviewer_response_status"), "Certificate reviewer response status")
        self._add_hash_check("certificate", "attestation_evidence_vault_zip_sha256", evidence_manifest.get("zip_sha256"), evidence_cert.get("zip_sha256"), "Evidence Vault ZIP sha256")
        self._add_hash_check("certificate", "attestation_evidence_vault_manifest_hash", evidence_manifest.get("manifest_hash"), evidence_cert.get("manifest_hash"), "Evidence Vault manifest hash")
        self._add_hash_check("certificate", "attestation_evidence_vault_verification_hash", evidence_manifest.get("verification_hash"), evidence_cert.get("verification_hash"), "Evidence Vault verification hash")
        self._add_value_check("certificate", "attestation_evidence_vault_verification_status", evidence_cert.get("verification_status"), evidence_manifest.get("verification_status"), "Evidence Vault verification status")
        self._add_value_check("certificate", "attestation_evidence_vault_deep_verification_status", evidence_cert.get("deep_verification_status"), evidence_manifest.get("deep_verification_status"), "Evidence Vault deep verification status")
        self._add_hash_check("certificate", "attestation_source_evidence_vault_zip_sha256", evidence_manifest.get("zip_sha256"), source.get("evidence_vault_zip_sha256"), "Evidence Vault ZIP sha256 source binding")
        self._add_value_check("certificate", "attestation_source_evidence_vault_zip_size_bytes", evidence_manifest.get("zip_size_bytes"), source.get("evidence_vault_zip_size_bytes"), "Evidence Vault ZIP size source binding")
        self._add_hash_check("certificate", "attestation_source_evidence_vault_manifest_hash", evidence_manifest.get("manifest_hash"), source.get("evidence_vault_manifest_hash"), "Evidence Vault manifest hash source binding")
        self._add_hash_check("certificate", "attestation_source_evidence_vault_verification_hash", evidence_manifest.get("verification_hash"), source.get("evidence_vault_verification_hash"), "Evidence Vault verification hash source binding")
        self._add_value_check("certificate", "attestation_source_evidence_vault_verification_status", evidence_manifest.get("verification_status"), source.get("evidence_vault_verification_status"), "Evidence Vault verification status source binding")
        self._add_value_check("certificate", "attestation_source_evidence_vault_deep_verification_status", evidence_manifest.get("deep_verification_status"), source.get("evidence_vault_deep_verification_status"), "Evidence Vault deep verification status source binding")
        self._add_hash_check("certificate", "attestation_final_board_signoff_hash", source.get("final_board_signoff_hash"), final_cert.get("signoff_hash"), "Final Board signoff hash")
        self._add_hash_check("certificate", "attestation_final_board_report_hash", source.get("final_board_report_hash"), final_cert.get("report_hash"), "Final Board report hash")
        self._add_hash_check("certificate", "attestation_certificate_portfolio_id", self.report_doc.get("portfolio_id"), self.certificate.get("portfolio_id"), "Certificate portfolio id")
        type_ok = self.certificate.get("certificate_type") == ATTESTATION_CERTIFICATE_TYPE
        self._add_check("certificate", "attestation_certificate_type", "passed" if type_ok else "failed", "blocking", "Certificate type is valid." if type_ok else "Certificate type is invalid.")

    def _verify_requirements(self) -> None:
        evidence_cert = self.certificate.get("evidence_vault") if isinstance(self.certificate.get("evidence_vault"), dict) else {}
        final_cert = self.certificate.get("final_board") if isinstance(self.certificate.get("final_board"), dict) else {}
        if self.require_vault:
            ok = evidence_cert.get("verification_status") == "passed" and evidence_cert.get("deep_verification_status") == "passed" and bool(evidence_cert.get("zip_sha256"))
            self._add_check("requirements", "attestation_require_vault", "passed" if ok else "failed", "blocking", "Evidence Vault verification is passed and deep." if ok else "Evidence Vault verification is required.")
        if self.require_final_board:
            ok = final_cert.get("signoff_status") in {"signed", "force_signed"} and bool(final_cert.get("signoff_hash"))
            self._add_check("requirements", "attestation_require_final_board", "passed" if ok else "failed", "blocking", "Final Board signoff evidence is present." if ok else "Final Board signoff evidence is required.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".md", ".html")):
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
        self._add_check("redaction", "attestation_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if not name or info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name or 'entry'} is missing.")
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
        report = {
            "schema_version": ATTESTATION_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "summary": {
                "portfolio_id": self.manifest.get("portfolio_id") or self.report_doc.get("portfolio_id"),
                "certificate_id": self.certificate.get("certificate_id"),
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

    def _add_value_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected is not None and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _is_forbidden_public_entry(name: str) -> bool:
    text = str(name or "")
    lowered = text.lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")


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
    if "<script" in text.lower() or "http://" in text.lower() or "https://" in text.lower():
        findings.append({"entry": name, "pattern": "remote_or_script", "excerpt": "script or remote URL"})
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
