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

from song_agent.projectio import write_json
from song_agent.public_trust_center_distribution_kit import (
    DISTRIBUTION_KIT_BLOCKED_KEYS,
    DISTRIBUTION_KIT_PACKAGE_TYPE,
    distribution_kit_manifest_hash,
    distribution_kit_report_hash,
)
from song_agent.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package
from song_agent.public_trust_center_anchor_transparency import anchor_checkpoint_hash
from song_agent.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package
from song_agent.public_trust_center_verifier import verify_public_trust_center_package
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash


DISTRIBUTION_KIT_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 256
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 400
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = DISTRIBUTION_KIT_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
REQUIRED_ENTRIES = {
    "distribution-kit-manifest.json",
    "distribution-kit-report.json",
    "README.txt",
    "VERIFY.txt",
    "file-index.json",
    "verification-index.json",
    "chain-of-custody.json",
    "packages/public-trust-center.zip",
    "packages/public-trust-center-anchor-registry.zip",
    "packages/public-trust-center-anchor-transparency.zip",
    "anchors/public-trust-center.delivery-anchor.json",
    "anchors/ptc-anchor-checkpoint-current.json",
    "verification-reports/public-trust-center-verification-report.json",
    "verification-reports/anchor-registry-verification-report.json",
    "verification-reports/anchor-transparency-verification-report.json",
}
ALLOWED_NESTED_ZIPS = {
    "packages/public-trust-center.zip",
    "packages/public-trust-center-anchor-registry.zip",
    "packages/public-trust-center-anchor-transparency.zip",
}
FILE_INDEX_ALLOWED_ENTRIES = {
    "distribution-kit-report.json",
    "packages/public-trust-center.zip",
    "packages/public-trust-center-anchor-registry.zip",
    "packages/public-trust-center-anchor-transparency.zip",
    "anchors/public-trust-center.delivery-anchor.json",
    "anchors/ptc-anchor-checkpoint-current.json",
    "verification-reports/public-trust-center-verification-report.json",
    "verification-reports/anchor-registry-verification-report.json",
    "verification-reports/anchor-transparency-verification-report.json",
}


def verify_public_trust_center_distribution_kit_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_current: bool = False,
    require_delivery_readiness: bool = True,
    require_anchor_registry_current: bool = True,
    require_anchor_published: bool = True,
    require_anchor_not_revoked: bool = True,
    require_anchor_transparency_current: bool = True,
    require_anchor_checkpoint: bool = True,
    require_acceptance_board_signoff: bool = False,
    acceptance_board_signoff_archive_path: Path | str | None = None,
    acceptance_board_path: Path | str | None = None,
    acceptance_board_verification_report_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _DistributionKitVerifier(
        Path(zip_path),
        strict=strict,
        deep=deep,
        require_current=require_current,
        require_delivery_readiness=require_delivery_readiness,
        require_anchor_registry_current=require_anchor_registry_current,
        require_anchor_published=require_anchor_published,
        require_anchor_not_revoked=require_anchor_not_revoked,
        require_anchor_transparency_current=require_anchor_transparency_current,
        require_anchor_checkpoint=require_anchor_checkpoint,
        require_acceptance_board_signoff=require_acceptance_board_signoff,
        acceptance_board_signoff_archive_path=Path(acceptance_board_signoff_archive_path) if acceptance_board_signoff_archive_path is not None else None,
        acceptance_board_path=Path(acceptance_board_path) if acceptance_board_path is not None else None,
        acceptance_board_verification_report_path=Path(acceptance_board_verification_report_path) if acceptance_board_verification_report_path is not None else None,
        accepted_evidence_dir=Path(accepted_evidence_dir) if accepted_evidence_dir is not None else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_distribution_kit_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_distribution_kit_verification_report(report: dict[str, Any]) -> None:
    print("MusicForge Public Trust Center Distribution Kit verification")
    print(f"status: {report.get('status')}")
    print(f"center: {(report.get('summary') if isinstance(report.get('summary'), dict) else {}).get('center_id') or 'unknown'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def public_trust_center_distribution_kit_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _DistributionKitVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        deep: bool,
        require_current: bool,
        require_delivery_readiness: bool,
        require_anchor_registry_current: bool,
        require_anchor_published: bool,
        require_anchor_not_revoked: bool,
        require_anchor_transparency_current: bool,
        require_anchor_checkpoint: bool,
        require_acceptance_board_signoff: bool,
        acceptance_board_signoff_archive_path: Path | None,
        acceptance_board_path: Path | None,
        acceptance_board_verification_report_path: Path | None,
        accepted_evidence_dir: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.deep = deep
        self.require_current = require_current
        self.require_delivery_readiness = require_delivery_readiness
        self.require_anchor_registry_current = require_anchor_registry_current
        self.require_anchor_published = require_anchor_published
        self.require_anchor_not_revoked = require_anchor_not_revoked
        self.require_anchor_transparency_current = require_anchor_transparency_current
        self.require_anchor_checkpoint = require_anchor_checkpoint
        self.require_acceptance_board_signoff = require_acceptance_board_signoff
        self.acceptance_board_signoff_archive_path = acceptance_board_signoff_archive_path
        self.acceptance_board_path = acceptance_board_path
        self.acceptance_board_verification_report_path = acceptance_board_verification_report_path
        self.accepted_evidence_dir = accepted_evidence_dir
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.file_index: dict[str, Any] = {}
        self.verification_index: dict[str, Any] = {}
        self.chain: dict[str, Any] = {}
        self.ptc_verification: dict[str, Any] = {}
        self.registry_verification: dict[str, Any] = {}
        self.transparency_verification: dict[str, Any] = {}
        self.checkpoint: dict[str, Any] = {}
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
                self.manifest = self._read_json_entry(archive, "distribution-kit-manifest.json", "manifest", "ptcdk_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_deep(archive)
                self._verify_acceptance_board_signoff()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptcdk_zip_open", "failed", "blocking", "Distribution Kit ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcdk_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcdk_zip_open", "failed", "blocking", f"Distribution Kit ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcdk_zip_open", "passed", "blocking", "Distribution Kit ZIP can be opened.")
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
        self._add_check("zip", "ptcdk_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptcdk_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptcdk_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcdk_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "ptcdk_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Distribution Kit entries exist.")
        unexpected = sorted(set(self.entry_names) - REQUIRED_ENTRIES)
        self._add_check("zip", "ptcdk_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Distribution Kit entries: " + ", ".join(unexpected[:5]) if unexpected else "Distribution Kit ZIP contains only fixed allowed entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "ptcdk_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip") and name not in ALLOWED_NESTED_ZIPS)
        self._add_check("zip", "ptcdk_zip_nested_allowlist", "failed" if nested else "passed", "blocking", "Unexpected nested ZIP entries: " + ", ".join(nested[:5]) if nested else "Nested ZIP entries are limited to the allowed public packages.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptcdk_manifest_exists", "failed", "blocking", "distribution-kit-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptcdk_manifest_integrity", self.manifest.get("integrity_hash"), distribution_kit_manifest_hash(self.manifest), "Distribution Kit manifest integrity")
        self._add_exact_check("manifest", "ptcdk_manifest_package_type", self.manifest.get("package_type"), DISTRIBUTION_KIT_PACKAGE_TYPE, "Manifest package_type")
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
        self._add_check("manifest", "ptcdk_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
        manifest_paths = {str(item.get("path") or "") for item in valid}
        expected_manifest_paths = REQUIRED_ENTRIES - {"distribution-kit-manifest.json"}
        self._add_exact_check("manifest", "ptcdk_manifest_allowed_files", sorted(manifest_paths), sorted(expected_manifest_paths), "Manifest file list matches fixed Distribution Kit structure")
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
            if actual_sha != item.get("sha256") or actual_size != item.get("size_bytes"):
                mismatches.append(path)
        self._add_check("manifest", "ptcdk_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest file hashes match ZIP entries.")
        allowed = {str(item.get("path") or "") for item in valid} | {"distribution-kit-manifest.json"}
        extras = sorted(set(self.entry_names) - allowed)
        self._add_check("manifest", "ptcdk_manifest_no_extra_entries", "failed" if extras else "passed", "blocking", "ZIP has entries outside manifest.files: " + ", ".join(extras[:5]) if extras else "ZIP has no entries outside manifest.files.")
        manifest_zip_entries = set(str(item) for item in ((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "ptcdk_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "distribution-kit-report.json", "report", "ptcdk_report_parse")
        self.file_index = self._read_json_entry(archive, "file-index.json", "file_index", "ptcdk_file_index_parse")
        self.verification_index = self._read_json_entry(archive, "verification-index.json", "verification_index", "ptcdk_verification_index_parse")
        self.chain = self._read_json_entry(archive, "chain-of-custody.json", "chain", "ptcdk_chain_parse")
        self.checkpoint = self._read_json_entry(archive, "anchors/ptc-anchor-checkpoint-current.json", "checkpoint", "ptcdk_checkpoint_parse")

    def _verify_documents(self) -> None:
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        self._add_hash_check("report", "ptcdk_report_integrity", self.report_doc.get("integrity_hash"), distribution_kit_report_hash(self.report_doc), "Distribution Kit report integrity")
        self._add_hash_check("report", "ptcdk_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Distribution Kit report source hash")
        self._add_exact_check("report", "ptcdk_manifest_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest source hash")
        self._add_exact_check("report", "ptcdk_manifest_report_hash", (self.manifest.get("report") or {}).get("integrity_hash") if isinstance(self.manifest.get("report"), dict) else None, self.report_doc.get("integrity_hash"), "Manifest report hash")
        self._add_hash_check("file_index", "ptcdk_file_index_integrity", self.file_index.get("integrity_hash"), stable_hash({key: value for key, value in self.file_index.items() if key != "integrity_hash"}), "File index integrity")
        self._add_exact_check("file_index", "ptcdk_file_index_source_hash", self.file_index.get("source_hash"), self.report_doc.get("source_hash"), "File index source hash")
        file_index_rows = self.file_index.get("files") if isinstance(self.file_index.get("files"), list) else []
        file_index_paths = {str(item.get("path") or "") for item in file_index_rows if isinstance(item, dict)}
        expected_file_index_paths = FILE_INDEX_ALLOWED_ENTRIES
        self._add_exact_check("file_index", "ptcdk_file_index_allowed_files", sorted(file_index_paths), sorted(expected_file_index_paths), "File index list matches fixed Distribution Kit structure")
        self._add_hash_check("verification_index", "ptcdk_verification_index_integrity", self.verification_index.get("integrity_hash"), stable_hash({key: value for key, value in self.verification_index.items() if key != "integrity_hash"}), "Verification index integrity")
        self._add_exact_check("verification_index", "ptcdk_verification_index_source_hash", self.verification_index.get("source_hash"), self.report_doc.get("source_hash"), "Verification index source hash")
        self._add_hash_check("chain", "ptcdk_chain_integrity", self.chain.get("integrity_hash"), stable_hash({key: value for key, value in self.chain.items() if key != "integrity_hash"}), "Chain of custody integrity")
        self._add_exact_check("chain", "ptcdk_chain_source_hash", self.chain.get("source_hash"), self.report_doc.get("source_hash"), "Chain of custody source hash")
        self._add_hash_check("checkpoint", "ptcdk_checkpoint_integrity", self.checkpoint.get("integrity_hash"), anchor_checkpoint_hash(self.checkpoint), "Checkpoint integrity")
        self._add_exact_check("checkpoint", "ptcdk_checkpoint_source_hash", self.checkpoint.get("integrity_hash"), source.get("checkpoint_hash"), "Checkpoint hash")

    def _verify_deep(self, archive: zipfile.ZipFile) -> None:
        with tempfile.TemporaryDirectory(prefix="mf-ptc-kit-verify-") as tmp:
            tmp_dir = Path(tmp)
            paths: dict[str, Path] = {}
            for entry in REQUIRED_ENTRIES:
                if entry not in self.entry_map:
                    continue
                target = tmp_dir / entry
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(self.entry_map[entry]))
                paths[entry] = target
            required = [
                "packages/public-trust-center.zip",
                "packages/public-trust-center-anchor-registry.zip",
                "packages/public-trust-center-anchor-transparency.zip",
            ]
            missing = [entry for entry in required if entry not in paths]
            self._add_check(
                "deep",
                "ptcdk_deep_required_packages",
                "failed" if missing else "passed",
                "blocking",
                "Missing required nested packages: " + ", ".join(missing) if missing else "Required nested packages are available for deep verification.",
            )
            if missing:
                return
            self.ptc_verification = verify_public_trust_center_package(
                paths["packages/public-trust-center.zip"],
                strict=True,
                require_delivery_readiness=self.require_delivery_readiness,
                delivery_anchor_path=paths.get("anchors/public-trust-center.delivery-anchor.json"),
                anchor_registry_path=paths.get("packages/public-trust-center-anchor-registry.zip"),
                anchor_transparency_path=paths.get("packages/public-trust-center-anchor-transparency.zip"),
                anchor_checkpoint_path=paths.get("anchors/ptc-anchor-checkpoint-current.json"),
                require_anchor_registry_current=self.require_anchor_registry_current,
                require_anchor_published=self.require_anchor_published,
                require_anchor_not_revoked=self.require_anchor_not_revoked,
                require_anchor_transparency_current=self.require_anchor_transparency_current,
                require_anchor_checkpoint=self.require_anchor_checkpoint,
            )
            self.registry_verification = verify_public_trust_center_anchor_registry_package(
                paths["packages/public-trust-center-anchor-registry.zip"],
                strict=True,
                require_current=self.require_anchor_registry_current or self.require_current,
                require_anchor_published=self.require_anchor_published,
                require_anchor_not_revoked=self.require_anchor_not_revoked,
            )
            self.transparency_verification = verify_public_trust_center_anchor_transparency_package(
                paths["packages/public-trust-center-anchor-transparency.zip"],
                strict=True,
                checkpoint_path=paths.get("anchors/ptc-anchor-checkpoint-current.json"),
                anchor_registry_path=paths.get("packages/public-trust-center-anchor-registry.zip"),
                require_current_checkpoint=self.require_anchor_checkpoint,
                require_published_anchor=self.require_anchor_published,
                require_not_revoked=self.require_anchor_not_revoked,
            )
            self._compare_deep_reports("ptc", self.ptc_verification, self._read_json_file(paths.get("verification-reports/public-trust-center-verification-report.json")), "ptcdk_deep_public_trust_center")
            self._compare_deep_reports("registry", self.registry_verification, self._read_json_file(paths.get("verification-reports/anchor-registry-verification-report.json")), "ptcdk_deep_anchor_registry")
            self._compare_deep_reports("transparency", self.transparency_verification, self._read_json_file(paths.get("verification-reports/anchor-transparency-verification-report.json")), "ptcdk_deep_anchor_transparency")
            source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
            self._add_exact_check("deep", "ptcdk_source_ptc_zip_sha256", self.ptc_verification.get("zip_sha256"), source.get("ptc_zip_sha256"), "PTC ZIP sha256")
            self._add_exact_check("deep", "ptcdk_source_anchor_registry_zip_sha256", self.registry_verification.get("zip_sha256"), source.get("anchor_registry_zip_sha256"), "Anchor Registry ZIP sha256")
            self._add_exact_check("deep", "ptcdk_source_anchor_transparency_zip_sha256", self.transparency_verification.get("zip_sha256"), source.get("anchor_transparency_zip_sha256"), "Anchor Transparency ZIP sha256")
            self._add_exact_check("deep", "ptcdk_source_checkpoint_hash", self.checkpoint.get("integrity_hash"), source.get("checkpoint_hash"), "Checkpoint hash")

    def _verify_acceptance_board_signoff(self) -> None:
        required = self.require_acceptance_board_signoff or self.acceptance_board_signoff_archive_path is not None
        if not required:
            return
        if self.acceptance_board_signoff_archive_path is None:
            self._add_check("requirements", "ptcdk_require_acceptance_board_signoff", "failed", "blocking", "Acceptance Board signoff archive is required.")
            return
        if not self.acceptance_board_signoff_archive_path.exists() or not self.acceptance_board_signoff_archive_path.is_file() or self.acceptance_board_signoff_archive_path.is_symlink():
            self._add_check("requirements", "ptcdk_acceptance_board_signoff_archive_present", "failed", "blocking", "Acceptance Board signoff archive ZIP does not exist or is not a regular file.")
            return
        try:
            from song_agent.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package
        except Exception as exc:
            self._add_check("requirements", "ptcdk_acceptance_board_signoff_import", "failed", "blocking", f"Acceptance Board signoff verifier cannot be imported: {exc}")
            return
        report = verify_public_trust_center_acceptance_board_signoff_archive_package(
            self.acceptance_board_signoff_archive_path,
            strict=True,
            require_signed=True,
            require_current=True,
            require_ready=True,
            board_zip_path=self.acceptance_board_path,
            board_verification_report_path=self.acceptance_board_verification_report_path,
            distribution_kit_path=self.zip_path,
            accepted_evidence_dir=self.accepted_evidence_dir,
            now=self.generated_at,
        )
        self._add_exact_check("requirements", "ptcdk_acceptance_board_signoff_verification_status", report.get("status"), "passed", "Acceptance Board signoff archive verification status")
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        self._add_exact_check("requirements", "ptcdk_acceptance_board_signoff_status", summary.get("signoff_status"), "signed", "Acceptance Board signoff status")
        self._add_exact_check("requirements", "ptcdk_acceptance_board_signoff_ready", summary.get("board_readiness"), "ready", "Acceptance Board readiness")

    def _compare_deep_reports(self, scope: str, actual: dict[str, Any], copied: dict[str, Any], prefix: str) -> None:
        self._add_exact_check(scope, f"{prefix}_status", actual.get("status"), copied.get("status"), f"{scope} copied verification status")
        self._add_exact_check(scope, f"{prefix}_zip_sha256", actual.get("zip_sha256"), copied.get("zip_sha256"), f"{scope} copied verification ZIP sha256")
        self._add_exact_check(scope, f"{prefix}_manifest_hash", actual.get("manifest_hash"), copied.get("manifest_hash"), f"{scope} copied verification manifest hash")
        self._add_exact_check(scope, f"{prefix}_report_hash", _verification_hash(actual), _verification_hash(copied), f"{scope} copied verification report hash")
        if self.deep or self.require_current:
            self._add_check(scope, f"{prefix}_passed", "passed" if actual.get("status") == "passed" else "failed", "blocking", f"{scope} deep verification passed." if actual.get("status") == "passed" else f"{scope} deep verification failed.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in self.entry_infos:
            if int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            name = info.filename
            if name.lower().endswith((".zip", ".png", ".jpg", ".jpeg", ".wav", ".mp3", ".flac", ".aac")):
                continue
            try:
                data = archive.read(info)
                text = data.decode("utf-8")
            except Exception:
                continue
            findings.extend(_redaction_findings(name, text))
            try:
                value = json.loads(text)
            except Exception:
                value = None
            if value is not None:
                findings.extend(_blocked_key_findings(name, value))
        self.redaction_findings = findings
        self._add_check("redaction", "ptcdk_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Distribution Kit." if findings else "No sensitive values found in Distribution Kit.")

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
        return value if isinstance(value, dict) else {}

    def _read_json_file(self, path: Path | None) -> dict[str, Any]:
        if path is None or not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
        summary = dict(summary)
        summary.update({"center_id": self.manifest.get("center_id") or self.report_doc.get("center_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": DISTRIBUTION_KIT_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "summary": summary,
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

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _is_safe_zip_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _is_forbidden_public_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or "/.musicforge/" in lower


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verification_hash(report: dict[str, Any]) -> str | None:
    if not report:
        return None
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _raw_zip_entry_names(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    names: list[str] = []
    signature = b"\x50\x4b\x01\x02"
    index = 0
    while True:
        index = data.find(signature, index)
        if index < 0 or index + 46 > len(data):
            break
        name_len = struct.unpack_from("<H", data, index + 28)[0]
        extra_len = struct.unpack_from("<H", data, index + 30)[0]
        comment_len = struct.unpack_from("<H", data, index + 32)[0]
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        try:
            names.append(data[start:end].decode("utf-8", errors="replace"))
        except Exception:
            pass
        index = end + extra_len + comment_len
    return names


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern in SENSITIVE_VALUE_PATTERNS + LOCAL_PATH_VALUE_PATTERNS:
        compiled = pattern[0] if isinstance(pattern, tuple) and pattern else pattern
        label = pattern[1] if isinstance(pattern, tuple) and len(pattern) > 1 else getattr(compiled, "pattern", str(compiled))
        if compiled.search(text):
            findings.append({"path": name, "pattern": label})
    return findings


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": path})
            findings.extend(_blocked_key_findings(name, item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{prefix}[{index}]"))
    return findings
