from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import ACCEPTANCE_BLOCKED_KEYS, ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE, accepted_evidence_hash, accepted_evidence_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_contracts import distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_core_verifier import verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash


ACCEPTED_EVIDENCE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ACCEPTANCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
REQUIRED_ENTRIES = {
    "evidence-manifest.json",
    "evidence-report.json",
    "original-response-public.json",
    "original-response-binding-summary.json",
    "response-verification-summary.json",
    "response-verification-report-summary.json",
    "original-response-binding-proof.json",
    "distribution-kit-verification-summary.json",
    "README.txt",
    "VERIFY.txt",
}


def verify_public_trust_center_distribution_kit_accepted_evidence_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    distribution_kit_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AcceptedEvidenceVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        distribution_kit_path=Path(distribution_kit_path) if distribution_kit_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_distribution_kit_accepted_evidence_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_distribution_kit_accepted_evidence_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Public Trust Center Distribution Kit Accepted Evidence verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"evidence: {summary.get('evidence_id') or '-'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")


def public_trust_center_distribution_kit_accepted_evidence_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AcceptedEvidenceVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        distribution_kit_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.distribution_kit_path = distribution_kit_path
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.manifest: dict[str, Any] = {}
        self.evidence: dict[str, Any] = {}
        self.public_response: dict[str, Any] = {}
        self.binding_summary: dict[str, Any] = {}
        self.response_verification: dict[str, Any] = {}
        self.response_verification_report_summary: dict[str, Any] = {}
        self.response_binding_proof: dict[str, Any] = {}
        self.distribution_kit_summary: dict[str, Any] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_external_distribution_kit()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptcdkae_zip_open", "failed", "blocking", "Accepted Evidence ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcdkae_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcdkae_zip_open", "failed", "blocking", f"Accepted Evidence ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcdkae_zip_open", "passed", "blocking", "Accepted Evidence ZIP can be opened.")
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
        self._add_check("zip", "ptcdkae_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptcdkae_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptcdkae_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcdkae_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "ptcdkae_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Accepted Evidence entries exist.")
        unexpected = sorted(set(self.entry_names) - REQUIRED_ENTRIES)
        self._add_check("zip", "ptcdkae_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Accepted Evidence entries: " + ", ".join(unexpected[:5]) if unexpected else "Accepted Evidence ZIP contains only fixed allowed entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "ptcdkae_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "evidence-manifest.json", "manifest", "ptcdkae_manifest_parse")
        self.evidence = self._read_json_entry(archive, "evidence-report.json", "report", "ptcdkae_report_parse")
        self.public_response = self._read_json_entry(archive, "original-response-public.json", "response", "ptcdkae_public_response_parse")
        self.binding_summary = self._read_json_entry(archive, "original-response-binding-summary.json", "binding", "ptcdkae_binding_summary_parse")
        self.response_verification = self._read_json_entry(archive, "response-verification-summary.json", "verification", "ptcdkae_response_verification_parse")
        self.response_verification_report_summary = self._read_json_entry(archive, "response-verification-report-summary.json", "verification", "ptcdkae_response_verification_report_summary_parse")
        self.response_binding_proof = self._read_json_entry(archive, "original-response-binding-proof.json", "binding", "ptcdkae_response_binding_proof_parse")
        self.distribution_kit_summary = self._read_json_entry(archive, "distribution-kit-verification-summary.json", "kit", "ptcdkae_distribution_kit_summary_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptcdkae_manifest_exists", "failed", "blocking", "evidence-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptcdkae_manifest_integrity", self.manifest.get("integrity_hash"), accepted_evidence_manifest_hash(self.manifest), "Accepted Evidence manifest integrity")
        self._add_exact_check("manifest", "ptcdkae_manifest_package_type", self.manifest.get("package_type"), ACCEPTED_EVIDENCE_PACKAGE_TYPE, "Manifest package_type")
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
        self._add_check("manifest", "ptcdkae_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
        expected_paths = REQUIRED_ENTRIES - {"evidence-manifest.json"}
        actual_paths = {str(item.get("path") or "") for item in valid}
        self._add_exact_check("manifest", "ptcdkae_manifest_allowed_files", sorted(actual_paths), sorted(expected_paths), "Manifest file list matches fixed Accepted Evidence structure")
        mismatches: list[str] = []
        for item in valid:
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(f"{path} missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_sha == item.get("sha256") and actual_size == item.get("size_bytes") else "failed"})
            if actual_sha != item.get("sha256") or actual_size != item.get("size_bytes"):
                mismatches.append(path)
        self._add_check("manifest", "ptcdkae_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in ((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "ptcdkae_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        self._add_exact_check("report", "ptcdkae_report_package_type", self.evidence.get("package_type"), ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE, "Evidence report package_type")
        self._add_hash_check("report", "ptcdkae_report_integrity", self.evidence.get("integrity_hash"), accepted_evidence_hash(self.evidence), "Evidence report integrity")
        source = self.evidence.get("source") if isinstance(self.evidence.get("source"), dict) else {}
        self._add_hash_check("report", "ptcdkae_report_source_hash", self.evidence.get("source_hash"), stable_hash(source), "Evidence report source hash")
        row = self.manifest.get("evidence") if isinstance(self.manifest.get("evidence"), dict) else {}
        self._add_exact_check("manifest", "ptcdkae_manifest_evidence_hash", row.get("integrity_hash"), self.evidence.get("integrity_hash"), "Manifest evidence hash")
        self._add_exact_check("manifest", "ptcdkae_manifest_source_hash", self.manifest.get("source_hash"), self.evidence.get("source_hash"), "Manifest source hash")
        self._add_exact_check("response", "ptcdkae_response_public_projection_match", self.public_response, self.evidence.get("public_response"), "Public response projection")
        self._add_exact_check("response", "ptcdkae_response_reviewer_summary_match", self.evidence.get("reviewer_summary"), self.public_response.get("reviewer"), "Reviewer public summary")
        for key, value in source.items():
            self._add_exact_check("binding", f"ptcdkae_original_response_binding_{key}", self.binding_summary.get(key), value, f"Original response binding {key}")
        self._add_exact_check("binding", "ptcdkae_original_response_public_hash", self.binding_summary.get("response_public_summary_hash"), stable_hash(self.public_response), "Original response public summary hash")
        self._add_exact_check("verification", "ptcdkae_response_verification_status", self.response_verification.get("status"), source.get("response_verification_status"), "Response verification status")
        self._add_exact_check("verification", "ptcdkae_response_verification_hash", self.response_verification.get("verification_hash"), source.get("response_verification_hash"), "Response verification hash")
        self._add_exact_check("verification", "ptcdkae_response_verification_payload", self.response_verification.get("response_payload_hash"), source.get("response_payload_hash"), "Response payload hash")
        self._add_exact_check("verification", "ptcdkae_response_verification_report_status", self.response_verification_report_summary.get("status"), source.get("response_verification_status"), "Stored response verification status")
        self._add_exact_check("verification", "ptcdkae_response_verification_report_hash", self.response_verification_report_summary.get("response_verification_hash"), source.get("response_verification_hash"), "Stored response verification report hash")
        self._add_exact_check("verification", "ptcdkae_original_response_payload_hash", self.response_verification_report_summary.get("response_payload_hash"), source.get("response_payload_hash"), "Stored original response payload hash")
        self._add_exact_check("verification", "ptcdkae_original_response_raw_sha256", self.response_verification_report_summary.get("raw_response_sha256"), source.get("raw_response_sha256"), "Stored original response raw sha256")
        self._add_exact_check("verification", "ptcdkae_original_response_public_summary", self.response_verification_report_summary.get("response_public_summary_hash"), stable_hash(self.public_response), "Stored original response public summary hash")
        self._add_exact_check("verification", "ptcdkae_original_response_public_summary_source", self.response_verification_report_summary.get("response_public_summary_hash"), source.get("response_public_summary_hash"), "Stored original response public summary source")
        self._add_exact_check("binding", "ptcdkae_original_response_binding_proof_hash", self.response_binding_proof.get("binding_summary_hash"), source.get("binding_summary_hash"), "Stored original response binding summary hash")
        self._add_exact_check("binding", "ptcdkae_original_response_binding_proof_public_summary", self.response_binding_proof.get("response_public_summary_hash"), stable_hash(self.public_response), "Stored original response binding proof public hash")
        self._add_exact_check("binding", "ptcdkae_original_response_binding_proof_payload_hash", self.response_binding_proof.get("response_payload_hash"), source.get("response_payload_hash"), "Stored original response binding proof payload hash")
        self._add_exact_check("kit", "ptcdkae_distribution_kit_verification_summary_match", self.distribution_kit_summary.get("distribution_kit_verification_report_hash"), source.get("distribution_kit_verification_report_hash"), "Distribution Kit verification report hash")
        for key in ("distribution_kit_zip_sha256", "distribution_kit_manifest_hash", "distribution_kit_report_hash", "distribution_kit_source_hash"):
            self._add_exact_check("kit", f"ptcdkae_distribution_kit_{key}", self.distribution_kit_summary.get(key), source.get(key), f"Distribution Kit {key}")

    def _verify_external_distribution_kit(self) -> None:
        source = self.evidence.get("source") if isinstance(self.evidence.get("source"), dict) else {}
        if self.distribution_kit_path is None:
            status = "failed" if self.require_current else "warning"
            severity = "blocking" if self.require_current else "warning"
            self._add_check("external", "ptcdkae_external_distribution_kit_supplied", status, severity, "External Distribution Kit ZIP is required for current verification." if self.require_current else "External Distribution Kit ZIP was not supplied.")
            return
        if not self.distribution_kit_path.exists() or not self.distribution_kit_path.is_file():
            self._add_check("external", "ptcdkae_external_distribution_kit_supplied", "failed", "blocking", "External Distribution Kit ZIP is missing.")
            return
        self._add_check("external", "ptcdkae_external_distribution_kit_supplied", "passed", "blocking", "External Distribution Kit ZIP is supplied.")
        self._add_exact_check("external", "ptcdkae_external_distribution_kit_hash_match", _sha256_file(self.distribution_kit_path), source.get("distribution_kit_zip_sha256"), "External Distribution Kit ZIP sha256")
        manifest = _read_zip_json(self.distribution_kit_path, "distribution-kit-manifest.json")
        self._add_exact_check("external", "ptcdkae_external_distribution_kit_manifest_match", manifest.get("integrity_hash"), source.get("distribution_kit_manifest_hash"), "External Distribution Kit manifest hash")
        self._add_hash_check("external", "ptcdkae_external_distribution_kit_manifest_integrity", manifest.get("integrity_hash"), distribution_kit_manifest_hash(manifest), "External Distribution Kit manifest integrity")
        if self.require_current:
            report = verify_public_trust_center_distribution_kit_package(self.distribution_kit_path, strict=True, deep=True, require_current=True, require_delivery_readiness=False)
            self._add_exact_check("external", "ptcdkae_external_distribution_kit_verification_status", report.get("status"), "passed", "External Distribution Kit verification status")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for info in self.entry_infos:
            if int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            name = info.filename
            if not name.endswith((".json", ".txt", ".md", ".html")):
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except Exception:
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
        self._add_check("redaction", "ptcdkae_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive issue(s)." if self.redaction_findings else "No sensitive values found in accepted evidence.")

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
        summary = {"center_id": self.evidence.get("center_id"), "evidence_id": self.evidence.get("evidence_id"), "response_id": self.evidence.get("response_id"), "status": self.evidence.get("status"), "result": self.evidence.get("result"), "blocker_count": len(blockers), "warning_count": len(warnings)}
        return sanitize_metadata({"schema_version": ACCEPTED_EVIDENCE_VERIFICATION_SCHEMA_VERSION, "generated_at": self.generated_at, "status": "failed" if blockers else "warning" if warnings else "passed", "package_kind": "public_trust_center_distribution_kit_accepted_evidence", "zip_path": self.zip_path.name, "zip_sha256": self.zip_sha256, "zip_size_bytes": self.zip_size_bytes, "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None, "summary": summary, "checks": self.checks, "files": self.files, "blockers": blockers, "warnings": warnings, "redaction_findings": self.redaction_findings[:50]}, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


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


def _is_forbidden_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")


def _raw_zip_entry_names(path: Path) -> list[str]:
    data = Path(_fs_path(path)).read_bytes() if path.exists() else b""
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
        names.append(data[start:end].decode("utf-8", errors="replace"))
        index = end + extra_len + comment_len
    return names


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _redaction_findings(scope: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "local_path", "message": "Local path pattern found."})
    lowered = text.lower()
    for marker in ("github" + "key", "x-access-" + "token", "api_" + "key", "access_" + "token", "source_" + "path", "local_" + "path", "file_" + "path"):
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    return findings
