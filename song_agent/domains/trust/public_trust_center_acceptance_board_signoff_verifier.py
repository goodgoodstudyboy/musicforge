from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import ACCEPTANCE_BOARD_BLOCKED_KEYS as ACCEPTANCE_BOARD_BLOCKED_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE, SIGNOFF_ARCHIVE_ENTRIES as SIGNOFF_ARCHIVE_ENTRIES, acceptance_board_manifest_hash as acceptance_board_manifest_hash, acceptance_board_signoff_archive_hash as acceptance_board_signoff_archive_hash, acceptance_board_signoff_hash as acceptance_board_signoff_hash, acceptance_board_verification_hash as acceptance_board_verification_hash, sidecar_hash as sidecar_hash
from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package as verify_public_trust_center_acceptance_board_package
from song_agent.domains.trust.public_trust_center_distribution_kit_contracts import distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import verification_hash as accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.domains.trust.public_trust_center_distribution_kit_core_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ACCEPTANCE_BOARD_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_public_trust_center_acceptance_board_signoff_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    require_ready: bool = False,
    board_zip_path: Path | str | None = None,
    board_verification_report_path: Path | str | None = None,
    distribution_kit_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AcceptanceBoardSignoffArchiveVerifier(
        Path(zip_path),
        strict=strict,
        require_signed=require_signed,
        require_current=require_current,
        require_ready=require_ready,
        board_zip_path=Path(board_zip_path) if board_zip_path else None,
        board_verification_report_path=Path(board_verification_report_path) if board_verification_report_path else None,
        distribution_kit_path=Path(distribution_kit_path) if distribution_kit_path else None,
        accepted_evidence_dir=Path(accepted_evidence_dir) if accepted_evidence_dir else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_acceptance_board_signoff_archive_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_acceptance_board_signoff_archive_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Public Trust Center Acceptance Board Signoff Archive verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"signoff: {summary.get('signoff_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")


def public_trust_center_acceptance_board_signoff_archive_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AcceptanceBoardSignoffArchiveVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_signed: bool,
        require_current: bool,
        require_ready: bool,
        board_zip_path: Path | None,
        board_verification_report_path: Path | None,
        distribution_kit_path: Path | None,
        accepted_evidence_dir: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_signed = require_signed
        self.require_current = require_current
        self.require_ready = require_ready
        self.board_zip_path = board_zip_path
        self.board_verification_report_path = board_verification_report_path
        self.distribution_kit_path = distribution_kit_path
        self.accepted_evidence_dir = accepted_evidence_dir
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
        self.report: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.board_verification: dict[str, Any] = {}
        self.board_fingerprint: dict[str, Any] = {}
        self.quorum: dict[str, Any] = {}
        self.accepted_index: dict[str, Any] = {}
        self.accepted_verification_index: dict[str, Any] = {}
        self.distribution: dict[str, Any] = {}
        self.change_request: dict[str, Any] = {}
        self.chain: dict[str, Any] = {}
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
                self._verify_requirements()
                self._verify_external_board()
                self._verify_external_distribution_kit()
                self._verify_external_accepted_evidence()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptcabs_zip_open", "failed", "blocking", "Acceptance Board signoff archive ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcabs_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcabs_zip_open", "failed", "blocking", f"Acceptance Board signoff archive ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcabs_zip_open", "passed", "blocking", "Acceptance Board signoff archive ZIP can be opened.")
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
        self._add_check("zip", "ptcabs_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptcabs_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptcabs_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcabs_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(SIGNOFF_ARCHIVE_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - SIGNOFF_ARCHIVE_ENTRIES)
        self._add_check("zip", "ptcabs_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required signoff archive entries exist.")
        self._add_check("zip", "ptcabs_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected signoff archive entries: " + ", ".join(unexpected[:5]) if unexpected else "Signoff archive ZIP contains only fixed allowed entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "ptcabs_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "board-signoff-archive-manifest.json", "manifest", "ptcabs_manifest_parse")
        self.report = self._read_json_entry(archive, "board-signoff-archive-report.json", "report", "ptcabs_report_parse")
        self.signoff = self._read_json_entry(archive, "board-signoff.json", "signoff", "ptcabs_signoff_parse")
        self.board_verification = self._read_json_entry(archive, "board-verification-summary.json", "board", "ptcabs_board_verification_parse")
        self.board_fingerprint = self._read_json_entry(archive, "board-fingerprint-summary.json", "board", "ptcabs_board_fingerprint_parse")
        self.quorum = self._read_json_entry(archive, "quorum-fingerprint-summary.json", "quorum", "ptcabs_quorum_parse")
        self.accepted_index = self._read_json_entry(archive, "accepted-evidence-fingerprint-index.json", "evidence", "ptcabs_evidence_index_parse")
        self.accepted_verification_index = self._read_json_entry(archive, "accepted-evidence-verification-index.json", "evidence", "ptcabs_evidence_verification_index_parse")
        self.distribution = self._read_json_entry(archive, "distribution-kit-fingerprint-summary.json", "kit", "ptcabs_distribution_parse")
        self.change_request = self._read_json_entry(archive, "change-request-summary.json", "change", "ptcabs_change_parse")
        self.chain = self._read_json_entry(archive, "chain-of-custody.json", "chain", "ptcabs_chain_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptcabs_manifest_exists", "failed", "blocking", "board-signoff-archive-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptcabs_manifest_integrity", self.manifest.get("integrity_hash"), acceptance_board_signoff_archive_hash(self.manifest), "Signoff archive manifest integrity")
        self._add_exact_check("manifest", "ptcabs_manifest_package_type", self.manifest.get("package_type"), ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE, "Manifest package_type")
        rows = _as_list(self.manifest.get("files"))
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
        self._add_check("manifest", "ptcabs_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
        expected_paths = SIGNOFF_ARCHIVE_ENTRIES - {"board-signoff-archive-manifest.json"}
        actual_paths = {str(item.get("path") or "") for item in valid}
        self._add_exact_check("manifest", "ptcabs_manifest_allowed_files", sorted(actual_paths), sorted(expected_paths), "Manifest file list matches fixed signoff archive structure")
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
        self._add_check("manifest", "ptcabs_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "ptcabs_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        source = _as_document(self.signoff.get("source"))
        self._add_exact_check("report", "ptcabs_report_package_type", self.report.get("package_type"), ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE, "Archive report package_type")
        self._add_hash_check("report", "ptcabs_report_integrity", self.report.get("integrity_hash"), acceptance_board_signoff_archive_hash(self.report), "Archive report integrity")
        self._add_exact_check("report", "ptcabs_report_signoff_hash", self.report.get("signoff_hash"), self.signoff.get("integrity_hash"), "Archive report signoff hash")
        self._add_exact_check("manifest", "ptcabs_manifest_signoff_hash", self.manifest.get("signoff_hash"), self.signoff.get("integrity_hash"), "Manifest signoff hash")
        self._add_exact_check("manifest", "ptcabs_manifest_source_hash", self.manifest.get("source_hash"), self.signoff.get("source_hash"), "Manifest source hash")
        self._add_exact_check("signoff", "ptcabs_signoff_package_type", self.signoff.get("package_type"), ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE, "Signoff package_type")
        self._add_hash_check("signoff", "ptcabs_signoff_integrity", self.signoff.get("integrity_hash"), acceptance_board_signoff_hash(self.signoff), "Signoff integrity")
        self._add_hash_check("signoff", "ptcabs_signoff_source_hash", self.signoff.get("source_hash"), stable_hash(source), "Signoff source hash")
        self._add_exact_check("board", "ptcabs_board_fingerprint_match", self.board_fingerprint.get("board"), source.get("board"), "Board fingerprint source")
        self._add_exact_check("board", "ptcabs_board_verification_match", self.board_fingerprint.get("verification"), source.get("verification"), "Board verification fingerprint")
        self._add_hash_check("board", "ptcabs_board_fingerprint_integrity", self.board_fingerprint.get("integrity_hash"), sidecar_hash(self.board_fingerprint), "Board fingerprint integrity")
        self._add_exact_check("board", "ptcabs_board_verification_summary_hash", self.board_verification.get("verification_report_hash"), (_as_document(source.get("verification"))).get("verification_report_hash"), "Board verification report hash")
        self._add_exact_check("board", "ptcabs_board_verification_zip_hash", self.board_verification.get("zip_sha256"), (_as_document(source.get("verification"))).get("zip_sha256"), "Board verification ZIP hash")
        self._add_hash_check("board", "ptcabs_board_verification_integrity", self.board_verification.get("integrity_hash"), sidecar_hash(self.board_verification), "Board verification sidecar integrity")
        self._add_exact_check("quorum", "ptcabs_quorum_match", self.quorum.get("quorum"), source.get("quorum"), "Quorum source")
        self._add_hash_check("quorum", "ptcabs_quorum_integrity", self.quorum.get("integrity_hash"), sidecar_hash(self.quorum), "Quorum sidecar integrity")
        self._add_exact_check("evidence", "ptcabs_accepted_evidence_index_match", self.accepted_index.get("items"), source.get("accepted_evidence"), "Accepted Evidence index")
        self._add_hash_check("evidence", "ptcabs_accepted_evidence_index_integrity", self.accepted_index.get("integrity_hash"), sidecar_hash(self.accepted_index), "Accepted Evidence index integrity")
        expected_verification_items = [
            {
                "evidence_id": item.get("evidence_id"),
                "response_id": item.get("response_id"),
                "verification_status": item.get("verification_status"),
                "verification_report_hash": item.get("verification_report_hash"),
                "zip_sha256": item.get("zip_sha256"),
            }
            for item in (_as_list(source.get("accepted_evidence")))
            if isinstance(item, dict)
        ]
        self._add_exact_check("evidence", "ptcabs_accepted_evidence_verification_index_match", self.accepted_verification_index.get("items"), expected_verification_items, "Accepted Evidence verification index")
        self._add_hash_check("evidence", "ptcabs_accepted_evidence_verification_index_integrity", self.accepted_verification_index.get("integrity_hash"), sidecar_hash(self.accepted_verification_index), "Accepted Evidence verification index integrity")
        self._add_exact_check("kit", "ptcabs_distribution_kit_match", self.distribution.get("distribution_kit"), source.get("distribution_kit"), "Distribution Kit source")
        self._add_hash_check("kit", "ptcabs_distribution_kit_integrity", self.distribution.get("integrity_hash"), sidecar_hash(self.distribution), "Distribution Kit sidecar integrity")
        self._add_hash_check("change", "ptcabs_change_request_integrity", self.change_request.get("integrity_hash"), sidecar_hash(self.change_request), "Change Request sidecar integrity")
        self._add_hash_check("chain", "ptcabs_chain_integrity", self.chain.get("integrity_hash"), sidecar_hash(self.chain), "Chain of custody integrity")

    def _verify_requirements(self) -> None:
        board = _as_document(self.signoff.get("board"))
        verification = _as_document(self.signoff.get("verification"))
        if self.require_signed:
            self._add_exact_check("requirements", "ptcabs_require_signed", self.signoff.get("status"), "signed", "Signed signoff")
        if self.require_ready:
            self._add_exact_check("requirements", "ptcabs_require_ready_board", [board.get("readiness"), board.get("status"), verification.get("status")], ["ready", "passed", "passed"], "Ready and verified board")
        if self.require_current and self.board_zip_path is None:
            self._add_check("external", "ptcabs_external_board_zip_required", "failed", "blocking", "External Acceptance Board ZIP is required for current signoff archive verification.")

    def _verify_external_board(self) -> None:
        source = _as_document(self.signoff.get("source"))
        board = _as_document(source.get("board"))
        verification = _as_document(source.get("verification"))
        if self.board_zip_path is not None:
            if not self.board_zip_path.exists() or not self.board_zip_path.is_file():
                self._add_check("external", "ptcabs_external_board_zip_present", "failed", "blocking", "External Acceptance Board ZIP is missing.")
                return
            self._add_exact_check("external", "ptcabs_external_board_zip_sha256", _sha256_file(self.board_zip_path), board.get("zip_sha256"), "External Acceptance Board ZIP sha256")
            manifest = _read_zip_json(self.board_zip_path, "acceptance-board-manifest.json")
            self._add_exact_check("external", "ptcabs_external_board_manifest_hash", manifest.get("integrity_hash"), board.get("manifest_hash"), "External Acceptance Board manifest hash")
            self._add_hash_check("external", "ptcabs_external_board_manifest_integrity", manifest.get("integrity_hash"), acceptance_board_manifest_hash(manifest), "External Acceptance Board manifest integrity")
            external_report = verify_public_trust_center_acceptance_board_package(
                self.board_zip_path,
                strict=True,
                require_ready=True,
                require_quorum=True,
                require_no_conflicts=True,
                min_accepted_count=int(((_as_document(source.get("quorum"))).get("requirements") or {}).get("min_accepted_count") or 0),
                min_accepted_organizations=int(((_as_document(source.get("quorum"))).get("requirements") or {}).get("min_accepted_organizations") or 0),
                required_roles=list(((_as_document(source.get("quorum"))).get("requirements") or {}).get("required_roles") or []),
                distribution_kit_path=self.distribution_kit_path,
                accepted_evidence_dir=self.accepted_evidence_dir,
            )
            self._add_exact_check("external", "ptcabs_external_board_verification_status", external_report.get("status"), "passed", "External Acceptance Board verifier status")
            self._add_exact_check("external", "ptcabs_external_board_verification_zip_sha256", external_report.get("zip_sha256"), verification.get("zip_sha256"), "External Acceptance Board verification ZIP sha")
            self._add_exact_check("external", "ptcabs_external_board_verification_manifest", external_report.get("manifest_hash"), verification.get("manifest_hash"), "External Acceptance Board verification manifest hash")
        if self.board_verification_report_path is not None:
            stored = _read_json_file(self.board_verification_report_path)
            self._add_exact_check("external", "ptcabs_external_board_verification_report_hash", acceptance_board_verification_hash(stored), verification.get("verification_report_hash"), "Stored Acceptance Board verification report hash")
            self._add_exact_check("external", "ptcabs_external_board_verification_report_zip", stored.get("zip_sha256"), verification.get("zip_sha256"), "Stored Acceptance Board verification ZIP sha")
            self._add_exact_check("external", "ptcabs_external_board_verification_report_manifest", stored.get("manifest_hash"), verification.get("manifest_hash"), "Stored Acceptance Board verification manifest hash")

    def _verify_external_distribution_kit(self) -> None:
        distribution = (_as_document(self.signoff.get("source"))).get("distribution_kit")
        distribution = _as_document(distribution)
        if self.distribution_kit_path is None:
            return
        if not self.distribution_kit_path.exists() or not self.distribution_kit_path.is_file():
            self._add_check("external", "ptcabs_external_distribution_kit_present", "failed", "blocking", "External Distribution Kit ZIP is missing.")
            return
        self._add_exact_check("external", "ptcabs_external_distribution_kit_sha256", _sha256_file(self.distribution_kit_path), distribution.get("zip_sha256"), "External Distribution Kit ZIP sha256")
        manifest = _read_zip_json(self.distribution_kit_path, "distribution-kit-manifest.json")
        self._add_exact_check("external", "ptcabs_external_distribution_kit_manifest", manifest.get("integrity_hash"), distribution.get("manifest_hash"), "External Distribution Kit manifest hash")
        self._add_hash_check("external", "ptcabs_external_distribution_kit_manifest_integrity", manifest.get("integrity_hash"), distribution_kit_manifest_hash(manifest), "External Distribution Kit manifest integrity")
        verification = verify_public_trust_center_distribution_kit_package(self.distribution_kit_path, strict=True, deep=True, require_current=True, require_delivery_readiness=False)
        self._add_exact_check("external", "ptcabs_external_distribution_kit_verification_status", verification.get("status"), "passed", "External Distribution Kit verification status")

    def _verify_external_accepted_evidence(self) -> None:
        rows = _as_list(self.accepted_index.get("items"))
        if not rows:
            return
        if self.accepted_evidence_dir is None:
            if self.require_current:
                self._add_check("external", "ptcabs_external_accepted_evidence_dir_required", "failed", "blocking", "External Accepted Evidence directory is required for current signoff archive verification.")
            return
        missing: list[str] = []
        mismatches: list[str] = []
        unverified: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidence_id") or "")
            response_id = str(row.get("response_id") or "")
            evidence_zip = _find_accepted_evidence_zip(self.accepted_evidence_dir, evidence_id)
            if evidence_zip is None:
                missing.append(evidence_id)
                continue
            verification = verify_public_trust_center_distribution_kit_accepted_evidence_package(evidence_zip, strict=True, require_current=True, distribution_kit_path=self.distribution_kit_path)
            if verification.get("status") != "passed":
                unverified.append(evidence_id)
            evidence = _read_zip_json(evidence_zip, "evidence-report.json")
            public = _read_zip_json(evidence_zip, "original-response-public.json")
            reviewer = _as_document(public.get("reviewer"))
            participant = _find_participant(self.signoff, response_id, evidence_id)
            if evidence.get("evidence_id") != evidence_id or evidence.get("response_id") != response_id:
                mismatches.append(response_id + ":identity")
            if _sha256_file(evidence_zip) != row.get("zip_sha256"):
                mismatches.append(response_id + ":zip")
            if accepted_evidence_verification_hash(verification) != row.get("verification_report_hash"):
                mismatches.append(response_id + ":verification")
            if evidence.get("integrity_hash") != row.get("evidence_integrity_hash") or evidence.get("source_hash") != row.get("evidence_source_hash"):
                mismatches.append(response_id + ":evidence_hash")
            expected = {"reviewer_name": reviewer.get("name"), "organization": reviewer.get("organization"), "role": reviewer.get("role")}
            actual = {key: participant.get(key) for key in expected} if isinstance(participant, dict) else {}
            if actual != expected:
                mismatches.append(response_id + ":participant")
        self._add_check("external", "ptcabs_external_accepted_evidence_present", "failed" if missing else "passed", "blocking", "Missing external Accepted Evidence ZIPs: " + ", ".join(missing[:5]) if missing else "External Accepted Evidence ZIPs are present.")
        self._add_check("external", "ptcabs_external_accepted_evidence_verified", "failed" if unverified else "passed", "blocking", "External Accepted Evidence verification failed: " + ", ".join(unverified[:5]) if unverified else "External Accepted Evidence ZIPs verify.")
        self._add_check("external", "ptcabs_external_accepted_evidence_binding", "failed" if mismatches else "passed", "blocking", "External Accepted Evidence mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Signoff archive participants match external Accepted Evidence.")

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
        self._add_check("redaction", "ptcabs_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive issue(s)." if self.redaction_findings else "No sensitive values found in signoff archive.")

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
        return sanitize_metadata(_as_document(value), blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = {
            "center_id": self.signoff.get("center_id"),
            "signoff_id": self.signoff.get("signoff_id"),
            "signoff_status": self.signoff.get("status"),
            "board_readiness": (_as_document(self.signoff.get("board"))).get("readiness"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        }
        return sanitize_metadata(
            {
                "schema_version": ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "public_trust_center_acceptance_board_signoff_archive",
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


def _find_participant(signoff: ImplementationDocument, response_id: str, evidence_id: str) -> ImplementationDocument:
    quorum = _as_document(signoff.get("quorum"))
    for item in quorum.get("participants", []) if isinstance(quorum.get("participants"), list) else []:
        if isinstance(item, dict) and item.get("response_id") == response_id and item.get("evidence_id") == evidence_id:
            return item
    return {}


def _find_accepted_evidence_zip(root: Path, evidence_id: str) -> Path | None:
    safe = _safe_id(evidence_id)
    if root.is_file() and root.suffix.lower() == ".zip":
        evidence = _read_zip_json(root, "evidence-report.json")
        return root if evidence.get("evidence_id") == evidence_id else None
    candidates = [
        root / safe / "accepted-evidence.zip",
        root / evidence_id / "accepted-evidence.zip",
        root / f"{safe}.zip",
        root / f"{evidence_id}.zip",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and not candidate.is_symlink():
            return candidate
    if root.exists() and root.is_dir():
        for candidate in sorted(root.rglob("accepted-evidence.zip")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            evidence = _read_zip_json(candidate, "evidence-report.json")
            if evidence.get("evidence_id") == evidence_id:
                return candidate
    return None


def _read_json_file(path: Path) -> ImplementationDocument:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=VERIFIER_BLOCKED_KEYS)


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=VERIFIER_BLOCKED_KEYS)


def _sha256_file(path: Path) -> str | None:
    try:
        if not os.path.isfile(_fs_path(path)):
            return None
    except OSError:
        return None
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


def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or lower.endswith(".zip") or "/.musicforge/" in lower


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"


def _redaction_findings(scope: str, text: str) -> list[ImplementationDocument]:
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


def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text
