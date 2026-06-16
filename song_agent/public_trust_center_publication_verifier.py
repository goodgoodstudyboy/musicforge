from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.projectio import write_json
from song_agent.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package
from song_agent.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package
from song_agent.public_trust_center_acceptance_board import acceptance_board_verification_hash
from song_agent.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package
from song_agent.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package
from song_agent.public_trust_center_distribution_kit_acceptance import verification_hash as accepted_evidence_verification_hash
from song_agent.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package
from song_agent.public_trust_center_publication import (
    PUBLICATION_BLOCKED_KEYS,
    PUBLICATION_PACKAGE_TYPE,
    PUBLICATION_REQUIRED_PACKAGE_KEYS,
    publication_manifest_hash,
    publication_report_hash,
    sidecar_hash,
)
from song_agent.public_trust_center_verifier import verify_public_trust_center_package
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash


PUBLICATION_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 512
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PUBLICATION_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
BASE_REQUIRED_ENTRIES = {
    "README.txt",
    "publication-manifest.json",
    "publication-report.json",
    "package-index.json",
    "verification-index.json",
    "mirror-policy.json",
    "checksum/SHA256SUMS.txt",
    "checksum/SHA256SUMS.json",
    "site/index.html",
    "site/trust-center.html",
    "site/packages.html",
    "site/verification.html",
    "anchors/ptc-anchor-checkpoint-current.json",
    "anchors/public-trust-center.delivery-anchor.json",
}
FIXED_PACKAGE_PATHS = {
    "packages/public-trust-center.zip",
    "packages/public-trust-center-distribution-kit.zip",
    "packages/public-trust-center-anchor-registry.zip",
    "packages/public-trust-center-anchor-transparency.zip",
    "packages/public-trust-center-acceptance-board.zip",
    "packages/public-trust-center-acceptance-board-signoff-archive.zip",
}
FIXED_VERIFICATION_PATHS = {
    "verification-reports/public-trust-center-verification-report.json",
    "verification-reports/distribution-kit-verification-report.json",
    "verification-reports/anchor-registry-verification-report.json",
    "verification-reports/anchor-transparency-verification-report.json",
    "verification-reports/acceptance-board-verification-report.json",
    "verification-reports/acceptance-board-signoff-archive-verification-report.json",
}


def verify_public_trust_center_publication_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_ready: bool = False,
    require_acceptance_board_signoff: bool = False,
    require_anchor_current: bool = False,
    require_no_revoked: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _PublicationVerifier(
        Path(zip_path),
        strict=strict,
        deep=deep,
        require_ready=require_ready,
        require_acceptance_board_signoff=require_acceptance_board_signoff,
        require_anchor_current=require_anchor_current,
        require_no_revoked=require_no_revoked,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def verify_public_trust_center_publication_mirror(
    mirror_dir: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_acceptance_board_signoff: bool = False,
    require_anchor_current: bool = False,
    require_no_revoked: bool = False,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    mirror = Path(mirror_dir)
    tmp_zip: Path | None = None
    if not mirror.exists() or not mirror.is_dir() or mirror.is_symlink():
        return _failed_report("mirror", "ptcpub_mirror_open", "Publication mirror directory does not exist or is not a regular directory.", now=now)
    entries = _walk_files(mirror)
    if len(entries) > max_entry_count:
        return _failed_report("mirror", "ptcpub_mirror_entry_count", "Publication mirror has too many files.", now=now)
    try:
        with tempfile.TemporaryDirectory(prefix="mf-ptc-pub-mirror-") as tmp:
            tmp_zip = Path(tmp) / "mirror.zip"
            with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in entries:
                    with open(_fs_path(path), "rb") as handle:
                        archive.writestr(path.relative_to(mirror).as_posix(), handle.read())
            report = verify_public_trust_center_publication_package(
                tmp_zip,
                strict=strict,
                deep=False,
                require_ready=require_ready,
                require_acceptance_board_signoff=require_acceptance_board_signoff,
                require_anchor_current=require_anchor_current,
                require_no_revoked=require_no_revoked,
                now=now,
            )
            report["package_kind"] = "public_trust_center_publication_mirror"
            report["mirror_root"] = mirror.name
            return report
    finally:
        if tmp_zip is not None and tmp_zip.exists():
            tmp_zip.unlink(missing_ok=True)


def write_public_trust_center_publication_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_publication_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Public Trust Center Publication verification")
    print(f"status: {report.get('status')}")
    print(f"publication: {summary.get('publication_id') or '-'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")


def public_trust_center_publication_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PublicationVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        deep: bool,
        require_ready: bool,
        require_acceptance_board_signoff: bool,
        require_anchor_current: bool,
        require_no_revoked: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.deep = deep
        self.require_ready = require_ready
        self.require_acceptance_board_signoff = require_acceptance_board_signoff
        self.require_anchor_current = require_anchor_current
        self.require_no_revoked = require_no_revoked
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
        self.total_uncompressed_size = 0
        self.zip_size_bytes = 0
        self.zip_sha256: str | None = None
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.package_index: dict[str, Any] = {}
        self.verification_index: dict[str, Any] = {}
        self.mirror_policy: dict[str, Any] = {}
        self.checksum_json: dict[str, Any] = {}
        self.deep_summary: dict[str, str] = {}

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_checksums(archive)
                self._verify_requirements()
                self._verify_html(archive)
                if self.deep:
                    self._verify_deep(archive)
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptcpub_zip_open", "failed", "blocking", "Publication ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        limit = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcpub_zip_size_limit", "passed" if self.zip_size_bytes <= limit else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {limit} bytes.")
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcpub_zip_open", "failed", "blocking", f"Publication ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcpub_zip_open", "passed", "blocking", "Publication ZIP can be opened.")
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
        uncompressed_limit = self.max_uncompressed_size_mb * 1024 * 1024
        self._add_check("zip", "ptcpub_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= uncompressed_limit else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {uncompressed_limit} bytes.")
        self._add_check("zip", "ptcpub_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "ptcpub_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcpub_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "ptcpub_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip") and not (name in FIXED_PACKAGE_PATHS or name.startswith("accepted-evidence/")))
        self._add_check("zip", "ptcpub_zip_nested_allowlist", "failed" if nested else "passed", "blocking", "Unexpected nested ZIP entries: " + ", ".join(nested[:5]) if nested else "Nested ZIP entries are allow-listed.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "publication-manifest.json", "manifest", "ptcpub_manifest_parse")
        self.report_doc = self._read_json_entry(archive, "publication-report.json", "report", "ptcpub_report_parse")
        self.package_index = self._read_json_entry(archive, "package-index.json", "package_index", "ptcpub_package_index_parse")
        self.verification_index = self._read_json_entry(archive, "verification-index.json", "verification_index", "ptcpub_verification_index_parse")
        self.mirror_policy = self._read_json_entry(archive, "mirror-policy.json", "mirror_policy", "ptcpub_mirror_policy_parse")
        self.checksum_json = self._read_json_entry(archive, "checksum/SHA256SUMS.json", "checksum", "ptcpub_checksum_json_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "ptcpub_manifest_integrity", self.manifest.get("integrity_hash"), publication_manifest_hash(self.manifest), "Publication manifest integrity")
        self._add_exact_check("manifest", "ptcpub_manifest_package_type", self.manifest.get("package_type"), PUBLICATION_PACKAGE_TYPE, "Publication manifest package_type")
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        expected = _expected_entries(source)
        missing = sorted(expected - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - expected)
        self._add_check("zip", "ptcpub_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing publication entries: " + ", ".join(missing[:8]) if missing else "All required publication entries exist.")
        self._add_check("zip", "ptcpub_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected publication entries: " + ", ".join(unexpected[:8]) if unexpected else "Publication ZIP contains only fixed/derived allowed entries.")
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "ptcpub_manifest_allowed_files", sorted(manifest_paths), sorted(expected - {"publication-manifest.json"}), "Manifest file list matches fixed/derived publication structure")
        mismatches: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            if actual_sha != item.get("sha256") or actual_size != item.get("size_bytes"):
                mismatches.append(path)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if path not in mismatches else "failed"})
        self._add_check("manifest", "ptcpub_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in ((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "ptcpub_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        self._add_hash_check("report", "ptcpub_report_integrity", self.report_doc.get("integrity_hash"), publication_report_hash(self.report_doc), "Publication report integrity")
        self._add_hash_check("report", "ptcpub_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Publication report source hash")
        self._add_exact_check("report", "ptcpub_manifest_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest source hash")
        self._add_exact_check("report", "ptcpub_manifest_report_hash", self.manifest.get("report_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
        self._add_hash_check("package_index", "ptcpub_package_index_integrity", self.package_index.get("integrity_hash"), sidecar_hash(self.package_index), "Package index integrity")
        self._add_exact_check("package_index", "ptcpub_package_index_source_hash", self.package_index.get("source_hash"), self.report_doc.get("source_hash"), "Package index source hash")
        expected_package_rows = _expected_package_index(source)
        self._add_exact_check("package_index", "ptcpub_package_index_matches_source", _strip_integrity_list(self.package_index.get("items")), expected_package_rows, "Package index matches publication source")
        self._add_hash_check("verification_index", "ptcpub_verification_index_integrity", self.verification_index.get("integrity_hash"), sidecar_hash(self.verification_index), "Verification index integrity")
        self._add_exact_check("verification_index", "ptcpub_verification_index_source_hash", self.verification_index.get("source_hash"), self.report_doc.get("source_hash"), "Verification index source hash")
        self._add_exact_check("verification_index", "ptcpub_verification_index_matches_source", self.verification_index.get("items"), source.get("verifications"), "Verification index matches publication source")
        self._add_hash_check("mirror_policy", "ptcpub_mirror_policy_integrity", self.mirror_policy.get("integrity_hash"), sidecar_hash(self.mirror_policy), "Mirror policy integrity")
        self._add_exact_check("mirror_policy", "ptcpub_mirror_policy_allowed_entries", sorted(self.mirror_policy.get("allowed_entries") or []), sorted(_expected_entries(source)), "Mirror policy allowed entries")

    def _verify_checksums(self, archive: zipfile.ZipFile) -> None:
        rows = self.checksum_json.get("files") if isinstance(self.checksum_json.get("files"), list) else []
        row_map = {str(item.get("path") or ""): item for item in rows if isinstance(item, dict)}
        expected_paths = sorted(_expected_entries(self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}) - {"publication-manifest.json", "checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt"})
        self._add_exact_check("checksum", "ptcpub_checksum_paths", sorted(row_map), expected_paths, "Checksum JSON paths")
        self._add_hash_check("checksum", "ptcpub_checksum_integrity", self.checksum_json.get("integrity_hash"), sidecar_hash(self.checksum_json), "Checksum JSON integrity")
        mismatches: list[str] = []
        for path in expected_paths:
            item = row_map.get(path) or {}
            info = self.entry_map.get(path)
            if info is None or item.get("sha256") != _sha256_entry(archive, info) or item.get("size_bytes") != int(info.file_size or 0):
                mismatches.append(path)
        self._add_check("checksum", "ptcpub_checksum_file_hashes", "failed" if mismatches else "passed", "blocking", "Checksum mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Checksum hashes match ZIP entries.")
        try:
            text = archive.read("checksum/SHA256SUMS.txt").decode("utf-8")
        except Exception:
            text = ""
        missing_lines = [path for path in expected_paths if path not in text]
        self._add_check("checksum", "ptcpub_sha256sums_text", "failed" if missing_lines else "passed", "blocking", "SHA256SUMS.txt missing entries: " + ", ".join(missing_lines[:8]) if missing_lines else "SHA256SUMS.txt lists expected files.")

    def _verify_requirements(self) -> None:
        summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        if self.require_ready:
            self._add_exact_check("requirements", "ptcpub_require_ready", [self.report_doc.get("status"), summary.get("ready_for_publication")], ["ready", True], "Publication ready status")
        if self.require_acceptance_board_signoff:
            self._add_check("requirements", "ptcpub_require_acceptance_board_signoff", "passed" if source.get("acceptance_board_signoff_hash") else "failed", "blocking", "Acceptance Board signoff is present." if source.get("acceptance_board_signoff_hash") else "Acceptance Board signoff is required.")
        if self.require_anchor_current:
            verifications = {str(item.get("verification_key") or ""): item for item in source.get("verifications", []) if isinstance(item, dict)}
            self._add_exact_check("requirements", "ptcpub_require_anchor_registry_current", (verifications.get("anchor_registry") or {}).get("status"), "passed", "Anchor Registry verification status")
            self._add_exact_check("requirements", "ptcpub_require_anchor_transparency_current", (verifications.get("anchor_transparency") or {}).get("status"), "passed", "Anchor Transparency verification status")
        if self.require_no_revoked:
            self._add_check("requirements", "ptcpub_require_no_revoked", "failed" if self.report_doc.get("status") == "revoked" else "passed", "blocking", "Publication is not revoked." if self.report_doc.get("status") != "revoked" else "Publication is revoked.")

    def _verify_html(self, archive: zipfile.ZipFile) -> None:
        bad: list[str] = []
        patterns = ("<script", "http://", "https://", "file://", "javascript:", "onload=", "onclick=", "<iframe", "<object", "<embed")
        for name in sorted(item for item in self.entry_names if item.startswith("site/") and item.endswith(".html")):
            try:
                text = archive.read(name).decode("utf-8", errors="replace").lower()
            except Exception:
                bad.append(name + ":read")
                continue
            if any(pattern in text for pattern in patterns):
                bad.append(name)
        self._add_check("html", "ptcpub_html_safe", "failed" if bad else "passed", "blocking", "Unsafe HTML pages: " + ", ".join(bad[:5]) if bad else "Static HTML pages are safe.")

    def _verify_deep(self, archive: zipfile.ZipFile) -> None:
        with tempfile.TemporaryDirectory(prefix="mf-ptc-pub-verify-") as tmp:
            tmp_dir = Path(tmp)
            paths: dict[str, Path] = {}
            for name in self.entry_names:
                target = tmp_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
                paths[name] = target
            accepted_dir = tmp_dir / "accepted-evidence"
            ptc = verify_public_trust_center_package(
                paths["packages/public-trust-center.zip"],
                strict=True,
                require_delivery_readiness=False,
                delivery_anchor_path=paths.get("anchors/public-trust-center.delivery-anchor.json"),
                anchor_registry_path=paths.get("packages/public-trust-center-anchor-registry.zip"),
                anchor_transparency_path=paths.get("packages/public-trust-center-anchor-transparency.zip"),
                anchor_checkpoint_path=paths.get("anchors/ptc-anchor-checkpoint-current.json"),
                require_anchor_registry_current=True,
                require_anchor_published=True,
                require_anchor_not_revoked=True,
                require_anchor_transparency_current=True,
                require_anchor_checkpoint=True,
                require_acceptance_board_signoff=True,
                acceptance_board_signoff_archive_path=paths.get("packages/public-trust-center-acceptance-board-signoff-archive.zip"),
                acceptance_board_path=paths.get("packages/public-trust-center-acceptance-board.zip"),
                acceptance_board_verification_report_path=paths.get("verification-reports/acceptance-board-verification-report.json"),
                distribution_kit_path=paths.get("packages/public-trust-center-distribution-kit.zip"),
                accepted_evidence_dir=accepted_dir,
            )
            kit = verify_public_trust_center_distribution_kit_package(
                paths["packages/public-trust-center-distribution-kit.zip"],
                strict=True,
                deep=True,
                require_current=True,
                require_delivery_readiness=False,
                require_acceptance_board_signoff=True,
                acceptance_board_signoff_archive_path=paths.get("packages/public-trust-center-acceptance-board-signoff-archive.zip"),
                acceptance_board_path=paths.get("packages/public-trust-center-acceptance-board.zip"),
                acceptance_board_verification_report_path=paths.get("verification-reports/acceptance-board-verification-report.json"),
                accepted_evidence_dir=accepted_dir,
            )
            registry = verify_public_trust_center_anchor_registry_package(paths["packages/public-trust-center-anchor-registry.zip"], strict=True, require_current=True, require_anchor_published=True, require_anchor_not_revoked=True)
            transparency = verify_public_trust_center_anchor_transparency_package(paths["packages/public-trust-center-anchor-transparency.zip"], strict=True, checkpoint_path=paths.get("anchors/ptc-anchor-checkpoint-current.json"), anchor_registry_path=paths.get("packages/public-trust-center-anchor-registry.zip"), require_current_checkpoint=True, require_published_anchor=True, require_not_revoked=True)
            board = verify_public_trust_center_acceptance_board_package(paths["packages/public-trust-center-acceptance-board.zip"], strict=True, require_ready=True, require_quorum=True, require_no_conflicts=True, distribution_kit_path=paths.get("packages/public-trust-center-distribution-kit.zip"), accepted_evidence_dir=accepted_dir)
            signoff = verify_public_trust_center_acceptance_board_signoff_archive_package(paths["packages/public-trust-center-acceptance-board-signoff-archive.zip"], strict=True, require_signed=True, require_current=True, require_ready=True, board_zip_path=paths.get("packages/public-trust-center-acceptance-board.zip"), board_verification_report_path=paths.get("verification-reports/acceptance-board-verification-report.json"), distribution_kit_path=paths.get("packages/public-trust-center-distribution-kit.zip"), accepted_evidence_dir=accepted_dir)
            reports = {"public_trust_center": ptc, "distribution_kit": kit, "anchor_registry": registry, "anchor_transparency": transparency, "acceptance_board": board, "acceptance_board_signoff_archive": signoff}
            for path in sorted(accepted_dir.rglob("accepted-evidence.zip")) if accepted_dir.exists() else []:
                evidence = _read_zip_json(path, "evidence-report.json")
                evidence_id = str(evidence.get("evidence_id") or path.parent.name)
                reports[f"accepted_evidence:{evidence_id}"] = verify_public_trust_center_distribution_kit_accepted_evidence_package(path, strict=True, require_current=True, distribution_kit_path=paths.get("packages/public-trust-center-distribution-kit.zip"))
            self.deep_summary = {key: str(value.get("status") or "missing") for key, value in reports.items()}
            failed = [key for key, value in self.deep_summary.items() if value != "passed"]
            self._add_check("deep", "ptcpub_deep_verification_status", "failed" if failed else "passed", "blocking", "Deep verification failed: " + ", ".join(failed[:8]) if failed else "Deep verification passed for nested packages.")
            verification_index = {str(item.get("verification_key") or ""): item for item in self.verification_index.get("items", []) if isinstance(item, dict)}
            mismatches: list[str] = []
            for key, report in reports.items():
                row = verification_index.get(key)
                if not row:
                    mismatches.append(key + ":missing-index")
                    continue
                if row.get("status") != report.get("status") or row.get("zip_sha256") != report.get("zip_sha256") or row.get("manifest_hash") != report.get("manifest_hash"):
                    mismatches.append(key)
            self._add_check("deep", "ptcpub_deep_verification_index_match", "failed" if mismatches else "passed", "blocking", "Deep verification index mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Deep verification reports match verification index.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in self.entry_infos:
            if int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            name = info.filename
            if not name.lower().endswith((".json", ".txt", ".md", ".html", ".csv")):
                continue
            try:
                text = archive.read(info).decode("utf-8", errors="replace")
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
        self._add_check("redaction", "ptcpub_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in publication." if findings else "No sensitive values found in publication.")

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

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
        summary = dict(summary)
        summary.update({"publication_id": self.manifest.get("publication_id") or self.report_doc.get("publication_id"), "channel_id": self.manifest.get("channel_id") or self.report_doc.get("channel_id"), "blocker_count": len(blockers), "warning_count": len(warnings), "deep_verification": self.deep_summary})
        return sanitize_metadata(
            {
                "schema_version": PUBLICATION_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "public_trust_center_publication",
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
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _failed_report(scope: str, check_id: str, message: str, *, now: str | None = None) -> dict[str, Any]:
    check = {"scope": scope, "check_id": check_id, "status": "failed", "severity": "blocking", "message": message}
    return {"schema_version": PUBLICATION_VERIFICATION_SCHEMA_VERSION, "generated_at": now or datetime.now(timezone.utc).isoformat(), "status": "failed", "package_kind": "public_trust_center_publication", "checks": [check], "blockers": [check], "warnings": [], "summary": {"blocker_count": 1, "warning_count": 0}}


def _expected_entries(source: dict[str, Any]) -> set[str]:
    entries = set(BASE_REQUIRED_ENTRIES)
    for item in source.get("packages", []) if isinstance(source.get("packages"), list) else []:
        if isinstance(item, dict) and item.get("path"):
            entries.add(str(item["path"]))
    for item in source.get("verifications", []) if isinstance(source.get("verifications"), list) else []:
        if isinstance(item, dict) and item.get("path"):
            entries.add(str(item["path"]))
    return entries


def _expected_package_index(source: dict[str, Any]) -> list[dict[str, Any]]:
    verifications = {str(item.get("verification_key") or ""): item for item in source.get("verifications", []) if isinstance(item, dict)}
    rows: list[dict[str, Any]] = []
    for item in source.get("packages", []) if isinstance(source.get("packages"), list) else []:
        if not isinstance(item, dict):
            continue
        verification = verifications.get(str(item.get("package_key") or "")) or {}
        rows.append({**item, "verification_report_path": verification.get("path"), "verification_report_hash": verification.get("report_hash"), "status": verification.get("status")})
    return rows


def _strip_integrity_list(value: Any) -> Any:
    return value if isinstance(value, list) else []


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or "/.musicforge/" in lower


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


def _verification_hash(report: dict[str, Any]) -> str | None:
    if not report:
        return None
    if report.get("package_kind") == "public_trust_center_acceptance_board":
        return acceptance_board_verification_hash(report)
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _raw_zip_entry_names(path: Path) -> list[str]:
    try:
        with open(_fs_path(path), "rb") as handle:
            data = handle.read()
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
        names.append(data[start:end].decode("utf-8", errors="replace"))
        index = end + extra_len + comment_len
    return names


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        regex = pattern[0] if isinstance(pattern, tuple) else pattern
        if regex.search(text):
            findings.append({"path": name, "pattern": regex.pattern[:80]})
    return findings


def _blocked_key_findings(name: str, value: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": str(key)})
            findings.extend(_blocked_key_findings(name, nested))
    elif isinstance(value, list):
        for nested in value:
            findings.extend(_blocked_key_findings(name, nested))
    return findings


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())


def _fs_path(path: Path) -> str:
    text = str(Path(path).resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _from_fs_path(value: str) -> Path:
    if os.name != "nt":
        return Path(value)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value.removeprefix("\\\\?\\UNC\\"))
    if value.startswith("\\\\?\\"):
        return Path(value.removeprefix("\\\\?\\"))
    return Path(value)
