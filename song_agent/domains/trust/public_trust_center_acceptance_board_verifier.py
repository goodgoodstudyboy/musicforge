from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import ACCEPTANCE_BOARD_BLOCKED_KEYS as ACCEPTANCE_BOARD_BLOCKED_KEYS, ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE as ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE, ACCEPTANCE_BOARD_PACKAGE_TYPE as ACCEPTANCE_BOARD_PACKAGE_TYPE, ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE, acceptance_board_conflict_hash as acceptance_board_conflict_hash, acceptance_board_manifest_hash as acceptance_board_manifest_hash, acceptance_board_policy_hash as acceptance_board_policy_hash, acceptance_board_report_hash as acceptance_board_report_hash, sidecar_hash as sidecar_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_contracts import distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import verification_hash as accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.domains.trust.public_trust_center_distribution_kit_core_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


ACCEPTANCE_BOARD_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 32
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 64
DEFAULT_MAX_ENTRY_COUNT = 160
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ACCEPTANCE_BOARD_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
ROOT_ENTRIES = {
    "acceptance-board-manifest.json",
    "board-report.json",
    "board-policy.json",
    "conflict-report.json",
    "board-summary.json",
    "accepted-evidence-index.json",
    "response-index.json",
    "quorum-evidence.json",
    "README.txt",
    "VERIFY.txt",
}


def verify_public_trust_center_acceptance_board_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_quorum: bool = False,
    require_no_conflicts: bool = False,
    min_accepted_count: int = 0,
    min_accepted_organizations: int = 0,
    required_roles: list[str] | None = None,
    distribution_kit_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AcceptanceBoardVerifier(
        Path(zip_path),
        strict=strict,
        require_ready=require_ready,
        require_quorum=require_quorum,
        require_no_conflicts=require_no_conflicts,
        min_accepted_count=min_accepted_count,
        min_accepted_organizations=min_accepted_organizations,
        required_roles=required_roles or [],
        distribution_kit_path=Path(distribution_kit_path) if distribution_kit_path else None,
        accepted_evidence_dir=Path(accepted_evidence_dir) if accepted_evidence_dir else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_acceptance_board_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_acceptance_board_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Public Trust Center Acceptance Board verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"readiness: {summary.get('readiness') or 'unknown'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")


def public_trust_center_acceptance_board_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AcceptanceBoardVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_ready: bool,
        require_quorum: bool,
        require_no_conflicts: bool,
        min_accepted_count: int,
        min_accepted_organizations: int,
        required_roles: list[str],
        distribution_kit_path: Path | None,
        accepted_evidence_dir: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_ready = require_ready
        self.require_quorum = require_quorum
        self.require_no_conflicts = require_no_conflicts
        self.min_accepted_count = max(0, int(min_accepted_count or 0))
        self.min_accepted_organizations = max(0, int(min_accepted_organizations or 0))
        self.required_roles = [_safe_id(role).lower() for role in required_roles if _safe_id(role)]
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
        self.policy: dict[str, Any] = {}
        self.conflict: dict[str, Any] = {}
        self.summary_doc: dict[str, Any] = {}
        self.response_index: dict[str, Any] = {}
        self.evidence_index: dict[str, Any] = {}
        self.quorum: dict[str, Any] = {}
        self.response_proofs: dict[str, dict[str, Any]] = {}
        self.evidence_summaries: dict[str, dict[str, Any]] = {}
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
                self._verify_gates()
                self._verify_external_distribution_kit()
                self._verify_external_accepted_evidence()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptcab_zip_open", "failed", "blocking", "Acceptance Board ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcab_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcab_zip_open", "failed", "blocking", f"Acceptance Board ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcab_zip_open", "passed", "blocking", "Acceptance Board ZIP can be opened.")
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
        self._add_check("zip", "ptcab_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptcab_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptcab_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcab_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(ROOT_ENTRIES - set(self.entry_names))
        self._add_check("zip", "ptcab_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Acceptance Board root entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "ptcab_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal/nested entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "acceptance-board-manifest.json", "manifest", "ptcab_manifest_parse")
        self.report = self._read_json_entry(archive, "board-report.json", "report", "ptcab_report_parse")
        self.policy = self._read_json_entry(archive, "board-policy.json", "policy", "ptcab_policy_parse")
        self.conflict = self._read_json_entry(archive, "conflict-report.json", "conflict", "ptcab_conflict_report_parse")
        self.summary_doc = self._read_json_entry(archive, "board-summary.json", "summary", "ptcab_board_summary_parse")
        self.response_index = self._read_json_entry(archive, "response-index.json", "response", "ptcab_response_index_parse")
        self.evidence_index = self._read_json_entry(archive, "accepted-evidence-index.json", "evidence", "ptcab_accepted_evidence_index_parse")
        self.quorum = self._read_json_entry(archive, "quorum-evidence.json", "quorum", "ptcab_quorum_evidence_parse")
        for name in self.entry_names:
            if name.startswith("response-proofs/") and name.endswith("-binding-proof.json"):
                response_id = name[len("response-proofs/") : -len("-binding-proof.json")]
                self.response_proofs.setdefault(response_id, {})["binding"] = self._read_json_entry(archive, name, "response", "ptcab_response_binding_proof_parse")
            if name.startswith("response-proofs/") and name.endswith("-verification-summary.json"):
                response_id = name[len("response-proofs/") : -len("-verification-summary.json")]
                self.response_proofs.setdefault(response_id, {})["verification"] = self._read_json_entry(archive, name, "response", "ptcab_response_verification_summary_parse")
            if name.startswith("evidence/") and name.endswith("-summary.json"):
                evidence_id = name[len("evidence/") : -len("-summary.json")]
                self.evidence_summaries[evidence_id] = self._read_json_entry(archive, name, "evidence", "ptcab_evidence_summary_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptcab_manifest_exists", "failed", "blocking", "acceptance-board-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptcab_manifest_integrity", self.manifest.get("integrity_hash"), acceptance_board_manifest_hash(self.manifest), "Acceptance Board manifest integrity")
        self._add_exact_check("manifest", "ptcab_manifest_package_type", self.manifest.get("package_type"), ACCEPTANCE_BOARD_PACKAGE_TYPE, "Manifest package_type")
        allowed_entries = self._expected_entries()
        unexpected = sorted(set(self.entry_names) - allowed_entries)
        self._add_check("zip", "ptcab_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Acceptance Board entries: " + ", ".join(unexpected[:5]) if unexpected else "Acceptance Board ZIP entries match report-derived allow-list.")
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
        self._add_check("manifest", "ptcab_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
        expected_paths = allowed_entries - {"acceptance-board-manifest.json"}
        actual_paths = {str(item.get("path") or "") for item in valid}
        self._add_exact_check("manifest", "ptcab_manifest_allowed_files", sorted(actual_paths), sorted(expected_paths), "Manifest file list matches report-derived Acceptance Board structure")
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
        self._add_check("manifest", "ptcab_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "ptcab_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        source = _as_document(self.report.get("source"))
        participants = _as_list(self.report.get("participants"))
        self._add_exact_check("report", "ptcab_report_package_type", self.report.get("package_type"), ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE, "Board report package_type")
        self._add_hash_check("report", "ptcab_report_integrity", self.report.get("integrity_hash"), acceptance_board_report_hash(self.report), "Board report integrity")
        self._add_hash_check("report", "ptcab_report_source_hash", self.report.get("source_hash"), stable_hash(source), "Board report source hash")
        self._add_hash_check("policy", "ptcab_policy_hash", self.policy.get("integrity_hash"), acceptance_board_policy_hash(self.policy), "Board policy integrity")
        self._add_exact_check("conflict", "ptcab_conflict_report_package_type", self.conflict.get("package_type"), ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE, "Conflict report package_type")
        self._add_hash_check("conflict", "ptcab_conflict_report_integrity", self.conflict.get("integrity_hash"), acceptance_board_conflict_hash(self.conflict), "Conflict report integrity")
        self._add_exact_check("summary", "ptcab_board_summary_match", self.summary_doc.get("summary"), self.report.get("summary"), "Board summary")
        self._add_hash_check("summary", "ptcab_board_summary_integrity", self.summary_doc.get("integrity_hash"), sidecar_hash(self.summary_doc), "Board summary integrity")
        self._add_exact_check("response", "ptcab_response_index_match", self.response_index.get("items"), source.get("responses"), "Response index")
        self._add_hash_check("response", "ptcab_response_index_integrity", self.response_index.get("integrity_hash"), sidecar_hash(self.response_index), "Response index integrity")
        self._add_exact_check("evidence", "ptcab_accepted_evidence_index_match", self.evidence_index.get("items"), source.get("accepted_evidence"), "Accepted evidence index")
        self._add_hash_check("evidence", "ptcab_accepted_evidence_index_integrity", self.evidence_index.get("integrity_hash"), sidecar_hash(self.evidence_index), "Accepted evidence index integrity")
        expected_quorum = _quorum_from_report(self.report)
        expected_quorum["integrity_hash"] = self.quorum.get("integrity_hash")
        self._add_exact_check("quorum", "ptcab_quorum_evidence_match", self.quorum, expected_quorum, "Quorum evidence")
        self._add_hash_check("quorum", "ptcab_quorum_evidence_integrity", self.quorum.get("integrity_hash"), sidecar_hash(self.quorum), "Quorum evidence integrity")
        self._verify_participant_proofs(participants)
        self._verify_evidence_summaries()

    def _verify_participant_proofs(self, participants: list[Any]) -> None:
        missing: list[str] = []
        mismatches: list[str] = []
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            response_id = str(participant.get("response_id") or "")
            proof = self.response_proofs.get(response_id)
            if not proof:
                missing.append(response_id)
                continue
            binding = _as_document(proof.get("binding"))
            verification = _as_document(proof.get("verification"))
            public = _as_document(binding.get("public_response"))
            reviewer = _as_document(public.get("reviewer"))
            expected_public_bits = {
                "result": public.get("result"),
                "review_mode": public.get("review_mode"),
                "reviewer_name": reviewer.get("name"),
                "organization": reviewer.get("organization"),
                "role": reviewer.get("role"),
            }
            actual_public_bits = {key: participant.get(key) for key in expected_public_bits}
            if actual_public_bits != expected_public_bits:
                mismatches.append(response_id)
            if binding.get("response_public_summary_hash") != stable_hash(public):
                mismatches.append(response_id + ":public_hash")
            source_row = _find_row(self.response_index.get("items"), "response_id", response_id)
            if source_row:
                if binding.get("binding_summary_hash") != source_row.get("binding_summary_hash"):
                    mismatches.append(response_id + ":binding")
                if verification.get("response_verification_hash") != source_row.get("verification_hash"):
                    mismatches.append(response_id + ":verification")
                if verification.get("response_payload_hash") != source_row.get("response_payload_hash"):
                    mismatches.append(response_id + ":payload")
        self._add_check("response", "ptcab_response_proofs_present", "failed" if missing else "passed", "blocking", "Missing response proofs: " + ", ".join(missing[:5]) if missing else "All participant response proofs are present.")
        self._add_check("response", "ptcab_response_proofs_match", "failed" if mismatches else "passed", "blocking", "Response proof mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Response proofs match participants and response index.")

    def _verify_evidence_summaries(self) -> None:
        missing: list[str] = []
        mismatches: list[str] = []
        rows = _as_list(self.evidence_index.get("items"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidence_id") or "")
            summary = self.evidence_summaries.get(evidence_id)
            if not summary:
                missing.append(evidence_id)
                continue
            if summary.get("evidence_integrity_hash") != row.get("evidence_integrity_hash") or summary.get("verification_report_hash") != row.get("verification_report_hash") or summary.get("zip_sha256") != row.get("zip_sha256"):
                mismatches.append(evidence_id)
        self._add_check("evidence", "ptcab_accepted_evidence_summaries_present", "failed" if missing else "passed", "blocking", "Missing evidence summaries: " + ", ".join(missing[:5]) if missing else "All accepted evidence summaries are present.")
        self._add_check("evidence", "ptcab_accepted_evidence_summaries_match", "failed" if mismatches else "passed", "blocking", "Accepted evidence summary mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Accepted evidence summaries match evidence index.")

    def _verify_gates(self) -> None:
        summary = _as_document(self.report.get("summary"))
        participants = _as_list(self.report.get("participants"))
        self._add_check("gate", "ptcab_quorum_status", "passed" if summary.get("quorum_status") == "passed" else "failed", "blocking", "Board quorum is passed." if summary.get("quorum_status") == "passed" else "Board quorum is not passed.")
        self._add_check("gate", "ptcab_required_roles_status", "passed" if summary.get("required_roles_status") == "passed" else "failed", "blocking", "Required roles are passed." if summary.get("required_roles_status") == "passed" else "Required roles are not passed.")
        self._add_check("gate", "ptcab_conflict_status", "passed" if summary.get("conflict_status") == "passed" else "failed", "blocking", "No blocking conflicts." if summary.get("conflict_status") == "passed" else "Blocking conflicts exist.")
        self._add_check("gate", "ptcab_no_stale_participants", "passed" if not [item for item in participants if isinstance(item, dict) and item.get("warnings")] else "failed", "blocking", "No stale participants." if not [item for item in participants if isinstance(item, dict) and item.get("warnings")] else "Stale or incomplete participants exist.")
        self._add_check("gate", "ptcab_no_blocking_findings", "passed" if not [item for item in participants if isinstance(item, dict) and item.get("critical_findings")] else "failed", "blocking", "No critical findings." if not [item for item in participants if isinstance(item, dict) and item.get("critical_findings")] else "Critical findings exist.")
        if self.require_ready:
            self._add_check("requirements", "ptcab_require_ready", "passed" if self.report.get("readiness") == "ready" and self.report.get("status") == "passed" else "failed", "blocking", "Board is ready." if self.report.get("readiness") == "ready" and self.report.get("status") == "passed" else "Ready board is required.")
        if self.require_quorum:
            self._add_check("requirements", "ptcab_require_quorum", "passed" if summary.get("quorum_status") == "passed" else "failed", "blocking", "Quorum is required and passed.")
        if self.require_no_conflicts:
            self._add_check("requirements", "ptcab_require_no_conflicts", "passed" if summary.get("conflict_status") == "passed" else "failed", "blocking", "No conflicts are required.")
        if self.min_accepted_count:
            self._add_check("requirements", "ptcab_require_min_accepted_count", "passed" if int(summary.get("accepted_count") or 0) >= self.min_accepted_count else "failed", "blocking", f"Accepted count must be at least {self.min_accepted_count}.")
        if self.min_accepted_organizations:
            self._add_check("requirements", "ptcab_require_min_accepted_organizations", "passed" if int(summary.get("accepted_organization_count") or 0) >= self.min_accepted_organizations else "failed", "blocking", f"Accepted organizations must be at least {self.min_accepted_organizations}.")
        if self.required_roles:
            roles = {str(item.get("role") or "").lower() for item in participants if isinstance(item, dict) and item.get("counts_for_quorum")}
            missing = [role for role in self.required_roles if role not in roles]
            self._add_check("requirements", "ptcab_require_required_roles", "passed" if not missing else "failed", "blocking", "Required roles are present." if not missing else "Missing required roles: " + ", ".join(missing))

    def _verify_external_distribution_kit(self) -> None:
        source = _as_document(self.report.get("source"))
        kit = _as_document(source.get("distribution_kit"))
        if self.distribution_kit_path is None:
            return
        if not self.distribution_kit_path.exists() or not self.distribution_kit_path.is_file():
            self._add_check("external", "ptcab_external_distribution_kit_match", "failed", "blocking", "External Distribution Kit ZIP is missing.")
            return
        self._add_exact_check("external", "ptcab_external_distribution_kit_hash", _sha256_file(self.distribution_kit_path), kit.get("zip_sha256"), "External Distribution Kit ZIP sha256")
        manifest = _read_zip_json(self.distribution_kit_path, "distribution-kit-manifest.json")
        self._add_exact_check("external", "ptcab_external_distribution_kit_manifest", manifest.get("integrity_hash"), kit.get("manifest_hash"), "External Distribution Kit manifest hash")
        self._add_hash_check("external", "ptcab_external_distribution_kit_manifest_integrity", manifest.get("integrity_hash"), distribution_kit_manifest_hash(manifest), "External Distribution Kit manifest integrity")
        verification = verify_public_trust_center_distribution_kit_package(self.distribution_kit_path, strict=True, deep=True, require_current=True, require_delivery_readiness=False)
        self._add_check("external", "ptcab_external_distribution_kit_verification", "passed" if verification.get("status") == "passed" else "failed", "blocking", "External Distribution Kit verification passed.")

    def _verify_external_accepted_evidence(self) -> None:
        participants = [item for item in (_as_list(self.report.get("participants"))) if isinstance(item, dict)]
        counted = [item for item in participants if item.get("counts_for_quorum")]
        strong_gate = bool(self.require_ready or self.require_quorum or self.min_accepted_count or self.min_accepted_organizations or self.required_roles)
        if not strong_gate and self.accepted_evidence_dir is None:
            return
        if self.accepted_evidence_dir is None:
            self._add_check("external", "ptcab_external_accepted_evidence_dir_required", "failed", "blocking", "External Accepted Evidence directory is required for ready/quorum Acceptance Board verification.")
            return
        if not self.accepted_evidence_dir.exists():
            self._add_check("external", "ptcab_external_accepted_evidence_dir_exists", "failed", "blocking", "External Accepted Evidence directory is missing.")
            return
        self._add_check("external", "ptcab_external_accepted_evidence_dir_exists", "passed", "blocking", "External Accepted Evidence directory exists.")
        missing: list[str] = []
        unverified: list[str] = []
        mismatches: list[str] = []
        for participant in counted:
            response_id = str(participant.get("response_id") or "")
            evidence_id = str(participant.get("evidence_id") or "")
            if not response_id or not evidence_id:
                missing.append(response_id or evidence_id or "participant")
                continue
            evidence_zip = self._find_external_accepted_evidence_zip(evidence_id)
            if evidence_zip is None:
                missing.append(evidence_id)
                continue
            verification = verify_public_trust_center_distribution_kit_accepted_evidence_package(
                evidence_zip,
                strict=True,
                require_current=True,
                distribution_kit_path=self.distribution_kit_path,
            )
            if verification.get("status") != "passed":
                unverified.append(evidence_id)
            evidence = _read_zip_json(evidence_zip, "evidence-report.json")
            public = _read_zip_json(evidence_zip, "original-response-public.json")
            manifest = _read_zip_json(evidence_zip, "evidence-manifest.json")
            reviewer = _as_document(public.get("reviewer"))
            response_row = _find_row(self.response_index.get("items"), "response_id", response_id)
            evidence_row = _find_row(self.evidence_index.get("items"), "evidence_id", evidence_id)
            expected_public = {
                "result": public.get("result"),
                "review_mode": public.get("review_mode"),
                "reviewer_name": reviewer.get("name"),
                "organization": reviewer.get("organization"),
                "role": reviewer.get("role"),
            }
            actual_public = {key: participant.get(key) for key in expected_public}
            if actual_public != expected_public:
                mismatches.append(response_id + ":public")
            if evidence.get("evidence_id") != evidence_id or evidence.get("response_id") != response_id:
                mismatches.append(response_id + ":identity")
            if evidence.get("status") != "current" or evidence.get("result") != "accepted" or evidence.get("review_mode") != "external_manual":
                mismatches.append(response_id + ":state")
            source = _as_document(evidence.get("source"))
            if source.get("response_payload_hash") != response_row.get("response_payload_hash"):
                mismatches.append(response_id + ":payload")
            if source.get("raw_response_sha256") != response_row.get("raw_response_sha256"):
                mismatches.append(response_id + ":raw")
            if source.get("response_verification_hash") != response_row.get("verification_hash"):
                mismatches.append(response_id + ":verification")
            if source.get("binding_summary_hash") != response_row.get("binding_summary_hash"):
                mismatches.append(response_id + ":binding")
            if source.get("response_public_summary_hash") != response_row.get("public_response_hash") or source.get("response_public_summary_hash") != stable_hash(public):
                mismatches.append(response_id + ":public_hash")
            if evidence.get("source_hash") != evidence_row.get("evidence_source_hash"):
                mismatches.append(response_id + ":evidence_source")
            if evidence.get("integrity_hash") != evidence_row.get("evidence_integrity_hash"):
                mismatches.append(response_id + ":evidence_integrity")
            if _sha256_file(evidence_zip) != evidence_row.get("zip_sha256"):
                mismatches.append(response_id + ":evidence_zip")
            if manifest.get("integrity_hash") and manifest.get("integrity_hash") != verification.get("manifest_hash"):
                mismatches.append(response_id + ":manifest")
            if accepted_evidence_verification_hash(verification) != evidence_row.get("verification_report_hash"):
                mismatches.append(response_id + ":verification_report")
        self._add_check("external", "ptcab_external_accepted_evidence_present", "failed" if missing else "passed", "blocking", "Missing external Accepted Evidence ZIPs: " + ", ".join(missing[:5]) if missing else "External Accepted Evidence ZIPs are present for quorum participants.")
        self._add_check("external", "ptcab_external_accepted_evidence_verified", "failed" if unverified else "passed", "blocking", "External Accepted Evidence verification failed: " + ", ".join(unverified[:5]) if unverified else "External Accepted Evidence ZIPs verify against the Distribution Kit.")
        self._add_check("external", "ptcab_participant_external_response_binding", "failed" if mismatches else "passed", "blocking", "Participant external Accepted Evidence mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Participants match external Accepted Evidence public response and verification fingerprints.")

    def _find_external_accepted_evidence_zip(self, evidence_id: str) -> Path | None:
        root = self.accepted_evidence_dir
        if root is None:
            return None
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
        self._add_check("redaction", "ptcab_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive issue(s)." if self.redaction_findings else "No sensitive values found in Acceptance Board package.")

    def _expected_entries(self) -> set[str]:
        entries = set(ROOT_ENTRIES)
        participants = _as_list(self.report.get("participants"))
        for item in participants:
            if not isinstance(item, dict):
                continue
            response_id = _safe_id(str(item.get("response_id") or "response"))
            entries.add(f"response-proofs/{response_id}-binding-proof.json")
            entries.add(f"response-proofs/{response_id}-verification-summary.json")
            evidence_id = str(item.get("evidence_id") or "")
            if evidence_id:
                entries.add(f"evidence/{_safe_id(evidence_id)}-summary.json")
        return entries

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
        summary = {"center_id": self.report.get("center_id"), "readiness": self.report.get("readiness"), "status": self.report.get("status"), "accepted_count": (_as_document(self.report.get("summary"))).get("accepted_count"), "blocker_count": len(blockers), "warning_count": len(warnings)}
        return sanitize_metadata({"schema_version": ACCEPTANCE_BOARD_VERIFICATION_SCHEMA_VERSION, "generated_at": self.generated_at, "status": "failed" if blockers else "warning" if warnings else "passed", "package_kind": "public_trust_center_acceptance_board", "zip_path": self.zip_path.name, "zip_sha256": self.zip_sha256, "zip_size_bytes": self.zip_size_bytes, "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None, "summary": summary, "checks": self.checks, "files": self.files, "blockers": blockers, "warnings": warnings, "redaction_findings": self.redaction_findings[:50]}, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _quorum_from_report(report: ImplementationDocument) -> ImplementationDocument:
    summary = _as_document(report.get("summary"))
    policy = _as_document(report.get("policy"))
    participants = _as_list(report.get("participants"))
    counted = [str(item.get("response_id") or "") for item in participants if isinstance(item, dict) and item.get("counts_for_quorum")]
    roles = {str(item.get("role") or "").lower(): "passed" for item in participants if isinstance(item, dict) and item.get("counts_for_quorum") and item.get("role")}
    return {"schema_version": 1, "source_hash": report.get("source_hash"), "policy_hash": policy.get("policy_hash"), "decision": {"readiness": report.get("readiness"), "quorum_status": summary.get("quorum_status"), "required_roles_status": summary.get("required_roles_status"), "conflict_status": summary.get("conflict_status")}, "counted_response_ids": counted, "required_roles": roles}


def _find_row(rows: Any, key: str, value: str) -> ImplementationDocument:
    for item in _as_list(rows):
        if isinstance(item, dict) and str(item.get(key) or "") == value:
            return item
    return {}


def _is_forbidden_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")


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


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return _as_document(value)


def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


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
