from __future__ import annotations
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib
import json
import re
import struct
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.trust.release_portfolio_governance_evidence_vault_contracts import EVIDENCE_VAULT_BLOCKED_KEYS, EVIDENCE_VAULT_PACKAGE_TYPE, evidence_vault_chain_hash, evidence_vault_manifest_hash, evidence_vault_package_index_hash, evidence_vault_report_integrity_hash, evidence_vault_verification_index_hash, evidence_vault_verification_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS


EVIDENCE_VAULT_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 1024
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 4096
DEFAULT_MAX_ENTRY_COUNT = 20000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "manifest.json",
    "vault-report.json",
    "package-index.json",
    "verification-index.json",
    "chain-of-custody.json",
    "evidence-vault.md",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = EVIDENCE_VAULT_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_evidence_vault_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_final_board: bool = False,
    require_reviewer_pack: bool = False,
    require_audit: bool = False,
    require_archives: bool = False,
    require_queue_packages: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _EvidenceVaultVerifier(
        Path(zip_path),
        strict=strict,
        deep=deep,
        require_final_board=require_final_board,
        require_reviewer_pack=require_reviewer_pack,
        require_audit=require_audit,
        require_archives=require_archives,
        require_queue_packages=require_queue_packages,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_release_portfolio_governance_evidence_vault_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_evidence_vault_verification_report(report: dict[str, Any]) -> None:
    summary = evidence_vault_verification_summary(report)
    print("MusicForge release portfolio governance evidence vault verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"deep: {summary.get('deep_verification_status') or 'missing'}")
    print(f"packages: {summary.get('checked_package_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_evidence_vault_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _EvidenceVaultVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        deep: bool,
        require_final_board: bool,
        require_reviewer_pack: bool,
        require_audit: bool,
        require_archives: bool,
        require_queue_packages: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.deep = deep
        self.require_final_board = require_final_board
        self.require_reviewer_pack = require_reviewer_pack
        self.require_audit = require_audit
        self.require_archives = require_archives
        self.require_queue_packages = require_queue_packages
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.nested_results: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.package_index: dict[str, Any] = {}
        self.verification_index: dict[str, Any] = {}
        self.chain: dict[str, Any] = {}
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
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "evidence_vault_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_nested_packages(archive)
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "evidence_vault_zip_open", "failed", "blocking", "Evidence Vault ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "evidence_vault_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "evidence_vault_zip_open", "failed", "blocking", f"Evidence Vault ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "evidence_vault_zip_open", "passed", "blocking", "Evidence Vault ZIP can be opened.")
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
        self._add_check("zip", "evidence_vault_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "evidence_vault_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "evidence_vault_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "evidence_vault_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "evidence_vault_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Evidence Vault entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "evidence_vault_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "evidence_vault_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = evidence_vault_manifest_hash(self.manifest)
        self._add_check("manifest", "evidence_vault_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Evidence Vault manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Evidence Vault manifest integrity hash does not match.")
        package_type_ok = self.manifest.get("package_type") == EVIDENCE_VAULT_PACKAGE_TYPE
        self._add_check("manifest", "evidence_vault_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", f"Manifest package_type is {EVIDENCE_VAULT_PACKAGE_TYPE}." if package_type_ok else "Manifest package_type is not release_portfolio_governance_evidence_vault.")
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
        self._add_check("manifest", "evidence_vault_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "evidence_vault_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Evidence Vault file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Evidence Vault manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "evidence_vault_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "evidence_vault_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "vault-report.json", "report", "evidence_vault_report_parse")
        self.package_index = self._read_json_entry(archive, "package-index.json", "package_index", "evidence_vault_package_index_parse")
        self.verification_index = self._read_json_entry(archive, "verification-index.json", "verification_index", "evidence_vault_verification_index_parse")
        self.chain = self._read_json_entry(archive, "chain-of-custody.json", "chain", "evidence_vault_chain_parse")

    def _verify_documents(self) -> None:
        manifest_source_hash = self.manifest.get("source_hash")
        if self.report_doc:
            self._add_hash_check("report", "evidence_vault_report_integrity", self.report_doc.get("integrity_hash"), evidence_vault_report_integrity_hash(self.report_doc), "Evidence Vault Report integrity")
            row = self.manifest.get("vault_report") if isinstance(self.manifest.get("vault_report"), dict) else {}
            self._add_hash_check("report", "evidence_vault_manifest_report_hash", row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
            self._add_hash_check("report", "evidence_vault_report_source_hash", manifest_source_hash, self.report_doc.get("source_hash"), "Manifest report source hash")
        if self.package_index:
            self._add_hash_check("package_index", "evidence_vault_package_index_integrity", self.package_index.get("integrity_hash"), evidence_vault_package_index_hash(self.package_index), "Package index integrity")
            row = self.manifest.get("package_index") if isinstance(self.manifest.get("package_index"), dict) else {}
            self._add_hash_check("package_index", "evidence_vault_manifest_package_index_hash", row.get("integrity_hash"), self.package_index.get("integrity_hash"), "Manifest package index hash")
            self._add_hash_check("package_index", "evidence_vault_package_index_source_hash", manifest_source_hash, self.package_index.get("source_hash"), "Package index source hash")
            self._add_hash_check("package_index", "evidence_vault_manifest_package_index_source_hash", row.get("source_hash"), self.package_index.get("source_hash"), "Manifest package index source hash")
        if self.verification_index:
            self._add_hash_check("verification_index", "evidence_vault_verification_index_integrity", self.verification_index.get("integrity_hash"), evidence_vault_verification_index_hash(self.verification_index), "Verification index integrity")
            row = self.manifest.get("verification_index") if isinstance(self.manifest.get("verification_index"), dict) else {}
            self._add_hash_check("verification_index", "evidence_vault_manifest_verification_index_hash", row.get("integrity_hash"), self.verification_index.get("integrity_hash"), "Manifest verification index hash")
            self._add_hash_check("verification_index", "evidence_vault_verification_index_source_hash", manifest_source_hash, self.verification_index.get("source_hash"), "Verification index source hash")
            self._add_hash_check("verification_index", "evidence_vault_manifest_verification_index_source_hash", row.get("source_hash"), self.verification_index.get("source_hash"), "Manifest verification index source hash")
        if self.chain:
            self._add_hash_check("chain", "evidence_vault_chain_integrity", self.chain.get("integrity_hash"), evidence_vault_chain_hash(self.chain), "Chain of custody integrity")
            row = self.manifest.get("chain_of_custody") if isinstance(self.manifest.get("chain_of_custody"), dict) else {}
            self._add_hash_check("chain", "evidence_vault_manifest_chain_hash", row.get("integrity_hash"), self.chain.get("integrity_hash"), "Manifest chain hash")
            self._add_hash_check("chain", "evidence_vault_chain_source_hash", manifest_source_hash, self.chain.get("source_hash"), "Chain of custody source hash")
            self._add_hash_check("chain", "evidence_vault_manifest_chain_source_hash", row.get("source_hash"), self.chain.get("source_hash"), "Manifest chain source hash")

    def _verify_nested_packages(self, archive: zipfile.ZipFile) -> None:
        manifest_rows = self.manifest.get("nested_packages") if isinstance(self.manifest.get("nested_packages"), list) else []
        index_rows = self.package_index.get("items") if isinstance(self.package_index.get("items"), list) else []
        verification_rows = self.verification_index.get("items") if isinstance(self.verification_index.get("items"), list) else []
        index_by_id = {str(item.get("package_id") or ""): item for item in index_rows if isinstance(item, dict)}
        verification_by_id = {str(item.get("package_id") or ""): item for item in verification_rows if isinstance(item, dict)}
        for item in manifest_rows:
            if not isinstance(item, dict):
                continue
            package_id = str(item.get("package_id") or "")
            path = str(item.get("path") or "")
            vpath = str(item.get("verification_path") or "")
            package_type = str(item.get("package_type") or "")
            role = str(item.get("role") or "")
            required = bool(item.get("required"))
            result = {"package_id": package_id, "role": role, "package_type": package_type, "required": required, "status": "pending", "checks": []}
            info = self.entry_map.get(path)
            if info is None:
                self._add_nested_check(result, "evidence_vault_nested_package_exists", "failed", "blocking", f"{package_id} nested ZIP is missing.")
            else:
                actual_sha = _sha256_entry(archive, info)
                actual_size = int(info.file_size or 0)
                self._add_nested_check(result, "evidence_vault_nested_package_sha256", "passed" if actual_sha == item.get("sha256") else "failed", "blocking", f"{package_id} nested ZIP sha256 matches." if actual_sha == item.get("sha256") else f"{package_id} nested ZIP sha256 mismatch.")
                self._add_nested_check(result, "evidence_vault_nested_package_size", "passed" if actual_size == item.get("size_bytes") else "failed", "blocking", f"{package_id} nested ZIP size matches." if actual_size == item.get("size_bytes") else f"{package_id} nested ZIP size mismatch.")
                index_row = index_by_id.get(package_id, {})
                self._add_nested_check(result, "evidence_vault_nested_package_index_sha256", "passed" if index_row.get("sha256") == item.get("sha256") else "failed", "blocking", f"{package_id} package index sha256 matches." if index_row.get("sha256") == item.get("sha256") else f"{package_id} package index sha256 mismatch.")
            verification = self._read_json_entry(archive, vpath, "nested", "evidence_vault_nested_verification_parse") if vpath else {}
            if verification:
                expected_hash = item.get("verification_hash")
                actual_hash = _stable_hash(verification)
                self._add_nested_check(result, "evidence_vault_nested_verification_hash", "passed" if actual_hash == expected_hash else "failed", "blocking", f"{package_id} verification report hash matches." if actual_hash == expected_hash else f"{package_id} verification report hash mismatch.")
                vindex_row = verification_by_id.get(package_id, {})
                self._add_nested_check(result, "evidence_vault_nested_verification_index_hash", "passed" if vindex_row.get("verification_hash") == expected_hash else "failed", "blocking", f"{package_id} verification index hash matches." if vindex_row.get("verification_hash") == expected_hash else f"{package_id} verification index hash mismatch.")
                self._add_nested_check(result, "evidence_vault_nested_verification_status", "passed" if verification.get("status") == "passed" else "failed", "blocking", f"{package_id} verification report passed." if verification.get("status") == "passed" else f"{package_id} verification report is not passed.")
                self._add_nested_check(result, "evidence_vault_nested_verification_zip_sha256", "passed" if verification.get("zip_sha256") == item.get("sha256") else "failed", "blocking", f"{package_id} verification zip sha256 matches nested ZIP." if verification.get("zip_sha256") == item.get("sha256") else f"{package_id} verification zip sha256 mismatch.")
                self._add_nested_check(result, "evidence_vault_nested_verification_zip_size", "passed" if verification.get("zip_size_bytes") == item.get("size_bytes") else "failed", "blocking", f"{package_id} verification ZIP size matches nested ZIP." if verification.get("zip_size_bytes") == item.get("size_bytes") else f"{package_id} verification ZIP size mismatch.")
                self._add_nested_check(result, "evidence_vault_nested_verification_manifest_hash", "passed" if verification.get("manifest_hash") == item.get("manifest_hash") else "failed", "blocking", f"{package_id} verification manifest hash matches." if verification.get("manifest_hash") == item.get("manifest_hash") else f"{package_id} verification manifest hash mismatch.")
            elif required:
                self._add_nested_check(result, "evidence_vault_nested_verification_exists", "failed", "blocking", f"{package_id} verification report is missing.")
            if self.deep and info is not None:
                self._deep_verify_nested(archive, info, result)
            failed = [row for row in result["checks"] if row.get("status") == "failed" and row.get("severity") == "blocking"]
            warnings = [row for row in result["checks"] if row.get("status") in {"warning", "failed"} and row.get("severity") == "warning"]
            result["status"] = "failed" if failed else "warning" if warnings else "passed"
            self.nested_results.append(sanitize_metadata(result, blocked_keys=VERIFIER_BLOCKED_KEYS))
        required_failed = [item for item in self.nested_results if item.get("required") and item.get("status") == "failed"]
        self._add_check("nested", "evidence_vault_nested_required_packages", "failed" if required_failed else "passed", "blocking", "Required nested package checks failed: " + ", ".join(str(item.get("package_id")) for item in required_failed[:5]) if required_failed else "All required nested packages passed Vault checks.")

    def _deep_verify_nested(self, archive: zipfile.ZipFile, info: zipfile.ZipInfo, result: dict[str, Any]) -> None:
        package_type = str(result.get("package_type") or "")
        package_id = str(result.get("package_id") or "nested")
        try:
            data = archive.read(info)
        except OSError as exc:
            self._add_nested_check(result, "evidence_vault_deep_read", "failed", "blocking", f"{package_id} could not be read for deep verification: {exc}")
            return
        with tempfile.TemporaryDirectory(prefix="musicforge-vault-") as temp_dir:
            nested_path = Path(temp_dir) / "nested.zip"
            nested_path.write_bytes(data)
            try:
                if package_type == "release_portfolio_governance_final_board_archive":
                    from song_agent.domains.trust.release_portfolio_governance_final_board_verifier import verify_release_portfolio_governance_final_board_package

                    nested_report = verify_release_portfolio_governance_final_board_package(nested_path, strict=self.strict, require_signed=self.require_final_board, require_reviewer_pack=self.require_reviewer_pack, require_audit=self.require_audit, require_archives=self.require_archives, require_reviewer_response=True)
                elif package_type == "release_portfolio_governance_reviewer_pack":
                    from song_agent.domains.trust.release_portfolio_governance_reviewer_pack_verifier import verify_release_portfolio_governance_reviewer_pack

                    nested_report = verify_release_portfolio_governance_reviewer_pack(nested_path, strict=self.strict, require_audit=self.require_audit, require_signed=True, require_archives=self.require_archives)
                elif package_type == "release_portfolio_governance_audit":
                    from song_agent.domains.trust.release_portfolio_governance_audit_verifier import verify_release_portfolio_governance_audit_package

                    nested_report = verify_release_portfolio_governance_audit_package(nested_path, strict=self.strict, require_signed=True, require_archives=self.require_archives)
                elif package_type == "release_portfolio_governance_archive":
                    from song_agent.domains.trust.release_portfolio_governance_archive_verifier import verify_release_portfolio_governance_archive_package

                    nested_report = verify_release_portfolio_governance_archive_package(nested_path, strict=self.strict, require_signed=True)
                elif package_type == "release_portfolio_governance_queue":
                    from song_agent.domains.trust.release_portfolio_governance_verifier import verify_release_portfolio_governance_package

                    nested_report = verify_release_portfolio_governance_package(nested_path, strict=self.strict, require_manual_actions=False)
                else:
                    self._add_nested_check(result, "evidence_vault_deep_package_type", "failed", "blocking", f"{package_id} has unsupported package_type {package_type}.")
                    return
            except Exception as exc:
                self._add_nested_check(result, "evidence_vault_deep_verifier", "failed", "blocking", f"{package_id} deep verifier raised: {exc}")
                return
        result["deep_report_summary"] = {
            "status": nested_report.get("status"),
            "manifest_hash": nested_report.get("manifest_hash"),
            "zip_sha256": nested_report.get("zip_sha256"),
            "zip_size_bytes": nested_report.get("zip_size_bytes"),
        }
        self._add_nested_check(result, "evidence_vault_deep_verifier", "passed" if nested_report.get("status") != "failed" else "failed", "blocking", f"{package_id} deep verifier passed." if nested_report.get("status") != "failed" else f"{package_id} deep verifier failed.")

    def _verify_requirements(self) -> None:
        by_role: dict[str, list[dict[str, Any]]] = {}
        for item in self.nested_results:
            by_role.setdefault(str(item.get("role") or ""), []).append(item)

        def role_ok(role: str) -> bool:
            rows = by_role.get(role, [])
            return bool(rows) and all(item.get("status") != "failed" for item in rows if item.get("required"))

        if self.require_final_board:
            self._add_check("requirements", "evidence_vault_require_final_board", "passed" if role_ok("final_board_archive") else "failed", "blocking", "Final Board Archive evidence is present and verified." if role_ok("final_board_archive") else "Final Board Archive evidence is required.")
        if self.require_reviewer_pack:
            self._add_check("requirements", "evidence_vault_require_reviewer_pack", "passed" if role_ok("governance_reviewer_pack") else "failed", "blocking", "Reviewer Pack evidence is present and verified." if role_ok("governance_reviewer_pack") else "Reviewer Pack evidence is required.")
        if self.require_audit:
            self._add_check("requirements", "evidence_vault_require_audit", "passed" if role_ok("governance_audit") else "failed", "blocking", "Governance Audit evidence is present and verified." if role_ok("governance_audit") else "Governance Audit evidence is required.")
        if self.require_archives:
            archives = by_role.get("governance_archive", [])
            ok = bool(archives) and all(item.get("status") != "failed" for item in archives if item.get("required"))
            self._add_check("requirements", "evidence_vault_require_archives", "passed" if ok else "failed", "blocking", "Governance Archive evidence is present and verified." if ok else "Governance Archive evidence is required.")
        if self.require_queue_packages:
            queues = by_role.get("governance_queue", [])
            ok = bool(queues) and all(item.get("status") != "failed" for item in queues if item.get("required"))
            self._add_check("requirements", "evidence_vault_require_queue_packages", "passed" if ok else "failed", "blocking", "Governance Queue evidence is present and verified." if ok else "Governance Queue evidence is required.")
        if self.deep:
            failed = [item for item in self.nested_results if item.get("required") and item.get("status") == "failed"]
            self._add_check("requirements", "evidence_vault_require_deep", "failed" if failed else "passed", "blocking", "Deep nested verification failed." if failed else "Deep nested verification passed for required packages.")

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
        self._add_check("redaction", "evidence_vault_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
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

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        nested_failed = [item for item in self.nested_results if item.get("status") == "failed"]
        deep_status = "skipped"
        if self.deep:
            deep_status = "failed" if nested_failed else "passed"
        report = {
            "schema_version": EVIDENCE_VAULT_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "summary": {
                "portfolio_id": self.manifest.get("portfolio_id") or self.report_doc.get("portfolio_id"),
                "report_status": self.report_doc.get("status"),
                "deep_verification_status": deep_status,
                "checked_file_count": len(self.files),
                "checked_package_count": len(self.nested_results),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
            },
            "checks": self.checks,
            "files": self.files,
            "nested_results": self.nested_results,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_nested_check(self, result: dict[str, Any], check_id: str, status: str, severity: str, message: str) -> None:
        row = {"scope": "nested", "check_id": check_id, "status": status, "severity": severity, "message": message}
        result.setdefault("checks", []).append(row)
        if status == "failed" and severity == "blocking":
            self.checks.append(row)

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


def _stable_hash(value: Any) -> str:
    from song_agent.domains.delivery.releases import stable_hash

    return stable_hash(value)


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": "local_path", "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any) -> list[dict[str, Any]]:
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
