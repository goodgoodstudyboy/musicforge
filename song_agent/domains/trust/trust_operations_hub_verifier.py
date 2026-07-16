from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument
from song_agent.platform.verification import (
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
from song_agent.domains.trust.public_trust_center_publication_contracts import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES as HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HUB_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION as TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash as hub_hash, hub_manifest_hash as hub_manifest_hash


TRUST_OPERATIONS_HUB_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_hub_verification"
TRUST_OPERATIONS_HUB_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


def verify_trust_operations_hub_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    require_no_critical_blockers: bool = False,
    require_publication_monitoring_clean: bool = False,
    require_delivery_ready: bool = False,
    require_incident_closeout: bool = False,
    require_incident_regression_guards: bool = False,
    require_trust_controls: bool = False,
    require_trust_control_signoff: bool = False,
    require_continuous_assurance: bool = False,
    require_assurance_watch_clear: bool = False,
    require_assurance_watch_signoff: bool = False,
    require_final_readiness: bool = False,
    publication_channel_state_path: Path | str | None = None,
    public_trust_center_verification_path: Path | str | None = None,
    publication_monitoring_verification_path: Path | str | None = None,
    release_verification_path: Path | str | None = None,
    release_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    distribution_verification_path: Path | str | None = None,
    distribution_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_verification_path: Path | str | None = None,
    submission_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_evidence_verification_path: Path | str | None = None,
    submission_evidence_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    release_operations_verification_path: Path | str | None = None,
    release_operations_verification_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    hub_signoff_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    trust_control_package_path: Path | str | None = None,
    trust_control_verification_report_path: Path | str | None = None,
    trust_control_signoff_archive_path: Path | str | None = None,
    trust_control_signoff_verification_report_path: Path | str | None = None,
    continuous_assurance_archive_path: Path | str | None = None,
    continuous_assurance_verification_report_path: Path | str | None = None,
    assurance_watch_package_path: Path | str | None = None,
    assurance_watch_verification_report_path: Path | str | None = None,
    assurance_watch_signoff_archive_path: Path | str | None = None,
    assurance_watch_signoff_verification_report_path: Path | str | None = None,
    final_handoff_package_path: Path | str | None = None,
    final_handoff_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _HubVerifier(
        Path(zip_path),
        strict=strict,
        require_ready=require_ready,
        require_signed=require_signed,
        require_current=require_current,
        require_no_critical_blockers=require_no_critical_blockers,
        require_publication_monitoring_clean=require_publication_monitoring_clean,
        require_delivery_ready=require_delivery_ready,
        require_incident_closeout=require_incident_closeout,
        require_incident_regression_guards=require_incident_regression_guards,
        require_trust_controls=require_trust_controls,
        require_trust_control_signoff=require_trust_control_signoff,
        require_continuous_assurance=require_continuous_assurance,
        require_assurance_watch_clear=require_assurance_watch_clear,
        require_assurance_watch_signoff=require_assurance_watch_signoff,
        require_final_readiness=require_final_readiness,
        publication_channel_state_path=Path(publication_channel_state_path) if publication_channel_state_path else None,
        public_trust_center_verification_path=Path(public_trust_center_verification_path) if public_trust_center_verification_path else None,
        publication_monitoring_verification_path=Path(publication_monitoring_verification_path) if publication_monitoring_verification_path else None,
        release_verification_paths=_combine_paths(release_verification_paths, release_verification_path),
        distribution_verification_paths=_combine_paths(distribution_verification_paths, distribution_verification_path),
        submission_verification_paths=_combine_paths(submission_verification_paths, submission_verification_path),
        submission_evidence_verification_paths=_combine_paths(submission_evidence_verification_paths, submission_evidence_verification_path),
        release_operations_verification_paths=_combine_paths(release_operations_verification_paths, release_operations_verification_path),
        hub_signoff_path=Path(hub_signoff_path) if hub_signoff_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        incident_knowledge_package_path=Path(incident_knowledge_package_path) if incident_knowledge_package_path else None,
        incident_knowledge_verification_report_path=Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None,
        trust_control_package_path=Path(trust_control_package_path) if trust_control_package_path else None,
        trust_control_verification_report_path=Path(trust_control_verification_report_path) if trust_control_verification_report_path else None,
        trust_control_signoff_archive_path=Path(trust_control_signoff_archive_path) if trust_control_signoff_archive_path else None,
        trust_control_signoff_verification_report_path=Path(trust_control_signoff_verification_report_path) if trust_control_signoff_verification_report_path else None,
        continuous_assurance_archive_path=Path(continuous_assurance_archive_path) if continuous_assurance_archive_path else None,
        continuous_assurance_verification_report_path=Path(continuous_assurance_verification_report_path) if continuous_assurance_verification_report_path else None,
        assurance_watch_package_path=Path(assurance_watch_package_path) if assurance_watch_package_path else None,
        assurance_watch_verification_report_path=Path(assurance_watch_verification_report_path) if assurance_watch_verification_report_path else None,
        assurance_watch_signoff_archive_path=Path(assurance_watch_signoff_archive_path) if assurance_watch_signoff_archive_path else None,
        assurance_watch_signoff_verification_report_path=Path(assurance_watch_signoff_verification_report_path) if assurance_watch_signoff_verification_report_path else None,
        final_handoff_package_path=Path(final_handoff_package_path) if final_handoff_package_path else None,
        final_handoff_verification_report_path=Path(final_handoff_verification_report_path) if final_handoff_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_hub_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_hub_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Trust Operations Hub verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")


def trust_operations_hub_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _HubVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_ready: bool,
        require_signed: bool,
        require_current: bool,
        require_no_critical_blockers: bool,
        require_publication_monitoring_clean: bool,
        require_delivery_ready: bool,
        require_incident_closeout: bool,
        require_incident_regression_guards: bool,
        require_trust_controls: bool,
        require_trust_control_signoff: bool,
        require_continuous_assurance: bool,
        require_assurance_watch_clear: bool,
        require_assurance_watch_signoff: bool,
        require_final_readiness: bool,
        publication_channel_state_path: Path | None,
        public_trust_center_verification_path: Path | None,
        publication_monitoring_verification_path: Path | None,
        release_verification_paths: list[Path],
        distribution_verification_paths: list[Path],
        submission_verification_paths: list[Path],
        submission_evidence_verification_paths: list[Path],
        release_operations_verification_paths: list[Path],
        hub_signoff_path: Path | None,
        hub_verification_report_path: Path | None,
        incident_board_package_path: Path | None,
        incident_board_verification_report_path: Path | None,
        incident_knowledge_package_path: Path | None,
        incident_knowledge_verification_report_path: Path | None,
        trust_control_package_path: Path | None,
        trust_control_verification_report_path: Path | None,
        trust_control_signoff_archive_path: Path | None,
        trust_control_signoff_verification_report_path: Path | None,
        continuous_assurance_archive_path: Path | None,
        continuous_assurance_verification_report_path: Path | None,
        assurance_watch_package_path: Path | None,
        assurance_watch_verification_report_path: Path | None,
        assurance_watch_signoff_archive_path: Path | None,
        assurance_watch_signoff_verification_report_path: Path | None,
        final_handoff_package_path: Path | None,
        final_handoff_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_ready = require_ready
        self.require_signed = require_signed
        self.require_current = require_current
        self.require_no_critical_blockers = require_no_critical_blockers
        self.require_publication_monitoring_clean = require_publication_monitoring_clean
        self.require_delivery_ready = require_delivery_ready
        self.require_incident_closeout = require_incident_closeout
        self.require_incident_regression_guards = require_incident_regression_guards
        self.require_trust_controls = require_trust_controls
        self.require_trust_control_signoff = require_trust_control_signoff
        self.require_continuous_assurance = require_continuous_assurance
        self.require_assurance_watch_clear = require_assurance_watch_clear
        self.require_assurance_watch_signoff = require_assurance_watch_signoff
        self.require_final_readiness = require_final_readiness
        self.publication_channel_state_path = publication_channel_state_path
        self.public_trust_center_verification_path = public_trust_center_verification_path
        self.publication_monitoring_verification_path = publication_monitoring_verification_path
        self.delivery_verification_paths = {
            "release_verification": release_verification_paths,
            "distribution_verification": distribution_verification_paths,
            "submission_verification": submission_verification_paths,
            "submission_evidence_verification": submission_evidence_verification_paths,
            "release_operations_verification": release_operations_verification_paths,
        }
        self.hub_signoff_path = hub_signoff_path
        self.hub_verification_report_path = hub_verification_report_path
        self.incident_board_package_path = incident_board_package_path
        self.incident_board_verification_report_path = incident_board_verification_report_path
        self.incident_knowledge_package_path = incident_knowledge_package_path
        self.incident_knowledge_verification_report_path = incident_knowledge_verification_report_path
        self.trust_control_package_path = trust_control_package_path
        self.trust_control_verification_report_path = trust_control_verification_report_path
        self.trust_control_signoff_archive_path = trust_control_signoff_archive_path
        self.trust_control_signoff_verification_report_path = trust_control_signoff_verification_report_path
        self.continuous_assurance_archive_path = continuous_assurance_archive_path
        self.continuous_assurance_verification_report_path = continuous_assurance_verification_report_path
        self.assurance_watch_package_path = assurance_watch_package_path
        self.assurance_watch_verification_report_path = assurance_watch_verification_report_path
        self.assurance_watch_signoff_archive_path = assurance_watch_signoff_archive_path
        self.assurance_watch_signoff_verification_report_path = assurance_watch_signoff_verification_report_path
        self.final_handoff_package_path = final_handoff_package_path
        self.final_handoff_verification_report_path = final_handoff_verification_report_path
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
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.manifest: dict[str, Any] = {}
        self.report: dict[str, Any] = {}
        self.matrix: dict[str, Any] = {}
        self.blockers_doc: dict[str, Any] = {}
        self.actions: dict[str, Any] = {}
        self.evidence: dict[str, Any] = {}
        self.verifications: dict[str, Any] = {}
        self.source_state: dict[str, Any] = {}
        self.delivery_evidence: dict[str, Any] = {}
        self.delivery_matrix: dict[str, Any] = {}
        self.delivery_blockers: dict[str, Any] = {}
        self.delivery_actions: dict[str, Any] = {}
        self.signoff_summary: dict[str, Any] = {}
        self.checksum_json: dict[str, Any] = {}
        self.external_channel_state: dict[str, Any] = {}
        self.external_ptc_verification: dict[str, Any] = {}
        self.external_monitoring_verification: dict[str, Any] = {}
        self.external_delivery_verifications: dict[str, list[dict[str, Any]]] = {}
        self.external_hub_signoff: dict[str, Any] = {}
        self.external_hub_verification_report: dict[str, Any] = {}
        self.external_incident_verification_report: dict[str, Any] = {}
        self.external_incident_knowledge_verification_report: dict[str, Any] = {}
        self.external_trust_control_verification_report: dict[str, Any] = {}
        self.external_trust_control_signoff_verification_report: dict[str, Any] = {}
        self.external_continuous_assurance_verification_report: dict[str, Any] = {}
        self.external_assurance_watch_verification_report: dict[str, Any] = {}
        self.external_assurance_watch_signoff_verification_report: dict[str, Any] = {}
        self.external_final_handoff_verification_report: dict[str, Any] = {}

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
                self._verify_semantics()
                self._verify_external_bindings()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        zip_fs_path = _fs_path(self.zip_path)
        if not os.path.isfile(zip_fs_path) or os.path.islink(zip_fs_path):
            self._add_check("zip", "toh_zip_open", "failed", "blocking", "Trust Operations Hub ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = os.stat(zip_fs_path).st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        limit = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "toh_zip_size_limit", "passed" if self.zip_size_bytes <= limit else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {limit} bytes.")
        try:
            archive = zipfile.ZipFile(zip_fs_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "toh_zip_open", "failed", "blocking", f"Trust Operations Hub ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "toh_zip_open", "passed", "blocking", "Trust Operations Hub ZIP can be opened.")
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
        self._add_check("zip", "toh_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= uncompressed_limit else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {uncompressed_limit} bytes.")
        self._add_check("zip", "toh_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "toh_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "toh_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "toh_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip"))
        self._add_check("zip", "toh_zip_nested_allowlist", "failed" if nested else "passed", "blocking", "Nested ZIP entries are not allowed: " + ", ".join(nested[:5]) if nested else "No nested ZIP entries are present.")
        missing = sorted(HUB_EXPORT_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - HUB_EXPORT_ENTRIES)
        self._add_check("zip", "toh_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Hub entries: " + ", ".join(missing[:8]) if missing else "All required Hub entries exist.")
        self._add_check("zip", "toh_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Hub entries: " + ", ".join(unexpected[:8]) if unexpected else "Hub ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-hub-manifest.json", "manifest", "toh_manifest_parse")
        self.report = self._read_json_entry(archive, "hub-report.json", "hub_report", "toh_report_parse")
        self.matrix = self._read_json_entry(archive, "readiness-matrix.json", "readiness_matrix", "toh_readiness_matrix_parse")
        self.blockers_doc = self._read_json_entry(archive, "blocker-register.json", "blocker_register", "toh_blocker_register_parse")
        self.actions = self._read_json_entry(archive, "manual-action-queue.json", "manual_action_queue", "toh_manual_action_queue_parse")
        self.evidence = self._read_json_entry(archive, "evidence-binding-index.json", "evidence_binding_index", "toh_evidence_binding_index_parse")
        self.verifications = self._read_json_entry(archive, "verification-summary-index.json", "verification_summary_index", "toh_verification_summary_index_parse")
        self.source_state = self._read_json_entry(archive, "source-state.json", "source_state", "toh_source_state_parse")
        self.delivery_evidence = self._read_json_entry(archive, "delivery-evidence-index.json", "delivery_evidence_index", "toh_delivery_evidence_index_parse")
        self.delivery_matrix = self._read_json_entry(archive, "delivery-readiness-matrix.json", "delivery_readiness_matrix", "toh_delivery_readiness_matrix_parse")
        self.delivery_blockers = self._read_json_entry(archive, "delivery-blocker-register.json", "delivery_blocker_register", "toh_delivery_blocker_register_parse")
        self.delivery_actions = self._read_json_entry(archive, "delivery-manual-action-queue.json", "delivery_manual_action_queue", "toh_delivery_manual_action_queue_parse")
        self.signoff_summary = self._read_json_entry(archive, "signoff-summary.json", "signoff_summary", "toh_signoff_summary_parse")
        self.checksum_json = self._read_json_entry(archive, "checksum/SHA256SUMS.json", "checksum", "toh_checksum_json_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "toh_manifest_integrity", self.manifest.get("integrity_hash"), hub_manifest_hash(self.manifest), "Hub manifest integrity")
        self._add_exact_check("manifest", "toh_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_HUB_PACKAGE_TYPE, "Hub manifest package_type")
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "toh_manifest_allowed_files", sorted(manifest_paths), sorted(HUB_EXPORT_ENTRIES - {"trust-operations-hub-manifest.json"}), "Manifest file list matches fixed Hub structure")
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
        self._add_check("manifest", "toh_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in ((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "toh_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files: " + ", ".join(spoof[:5]) if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        docs = {
            "hub_report": self.report,
            "readiness_matrix": self.matrix,
            "blocker_register": self.blockers_doc,
            "manual_action_queue": self.actions,
            "evidence_binding_index": self.evidence,
            "verification_summary_index": self.verifications,
            "source_state": self.source_state,
            "delivery_evidence_index": self.delivery_evidence,
            "delivery_readiness_matrix": self.delivery_matrix,
            "delivery_blocker_register": self.delivery_blockers,
            "delivery_manual_action_queue": self.delivery_actions,
            "signoff_summary": self.signoff_summary,
            "checksum": self.checksum_json,
        }
        for label, doc in docs.items():
            expected = hub_hash(doc)
            self._add_hash_check(label, f"toh_{label}_integrity", doc.get("integrity_hash"), expected, f"{label} integrity")
        source = self.report.get("source") if isinstance(self.report.get("source"), dict) else {}
        expected_source = {
            "source_state_hash": self.source_state.get("integrity_hash"),
            "readiness_matrix_hash": self.matrix.get("integrity_hash"),
            "blocker_register_hash": self.blockers_doc.get("integrity_hash"),
            "manual_action_queue_hash": self.actions.get("integrity_hash"),
            "evidence_binding_index_hash": self.evidence.get("integrity_hash"),
            "verification_summary_index_hash": self.verifications.get("integrity_hash"),
            "delivery_evidence_index_hash": self.delivery_evidence.get("integrity_hash"),
            "delivery_readiness_matrix_hash": self.delivery_matrix.get("integrity_hash"),
            "delivery_blocker_register_hash": self.delivery_blockers.get("integrity_hash"),
            "delivery_manual_action_queue_hash": self.delivery_actions.get("integrity_hash"),
        }
        for key, value in expected_source.items():
            self._add_exact_check("hub_report", "toh_report_source_" + key, source.get(key), value, f"Hub report source {key}")
        manifest_source = self.manifest.get("source") if isinstance(self.manifest.get("source"), dict) else {}
        manifest_expected = {"hub_report_hash": self.report.get("integrity_hash"), **expected_source, "signoff_summary_hash": self.signoff_summary.get("integrity_hash")}
        for key, value in manifest_expected.items():
            self._add_exact_check("manifest", "toh_manifest_source_" + key, manifest_source.get(key), value, f"Manifest source {key}")

    def _verify_checksums(self, archive: zipfile.ZipFile) -> None:
        rows = self.checksum_json.get("files") if isinstance(self.checksum_json.get("files"), list) else []
        row_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        expected_paths = HUB_EXPORT_ENTRIES - {"trust-operations-hub-manifest.json", "checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt"}
        self._add_exact_check("checksum", "toh_checksum_allowed_files", sorted(row_paths), sorted(expected_paths), "Checksum file list matches fixed Hub payload files")
        mismatches: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            if _sha256_entry(archive, info) != item.get("sha256") or int(info.file_size or 0) != item.get("size_bytes"):
                mismatches.append(path)
        self._add_check("checksum", "toh_checksum_file_hashes", "failed" if mismatches else "passed", "blocking", "Checksum mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Checksum hashes match ZIP entries.")

    def _verify_semantics(self) -> None:
        rows = [row for row in self.matrix.get("rows", []) if isinstance(row, dict)]
        expected_summary = _readiness_summary(rows)
        self._add_exact_check("readiness", "toh_readiness_summary_matches_rows", self.matrix.get("summary"), expected_summary, "Readiness summary matches matrix rows")
        expected_blockers = _expected_blockers(rows)
        actual_blockers = _normalize_blockers(self.blockers_doc.get("blockers") if isinstance(self.blockers_doc.get("blockers"), list) else [])
        self._add_exact_check("blockers", "toh_blocker_register_matches_readiness", actual_blockers, expected_blockers, "Blocker register matches blocking readiness rows")
        actions = self.actions.get("actions") if isinstance(self.actions.get("actions"), list) else []
        actual_action_ids = sorted(str(item.get("action_id") or "") for item in actions if isinstance(item, dict))
        expected_action_ids = sorted(str(item.get("manual_action_id") or "") for item in self.blockers_doc.get("blockers", []) if isinstance(item, dict))
        self._add_exact_check("actions", "toh_manual_actions_match_blockers", actual_action_ids, expected_action_ids, "Manual action queue matches blockers")
        evidence_rows = [row for row in self.evidence.get("evidence", []) if isinstance(row, dict)]
        verification_rows = [row for row in self.verifications.get("verifications", []) if isinstance(row, dict)]
        self._add_exact_check("evidence", "toh_evidence_summary_matches_rows", self.evidence.get("summary"), _evidence_summary(evidence_rows), "Evidence summary matches rows")
        self._add_exact_check("verifications", "toh_verification_summary_matches_rows", self.verifications.get("summary"), _verification_summary(verification_rows), "Verification summary matches rows")
        expected_verifications = sorted(
            (_verification_from_evidence(row) for row in evidence_rows if row.get("verification_report_hash")),
            key=lambda item: str(item.get("verification_id") or ""),
        )
        actual_verifications = sorted(
            (
                _strip_none({"verification_id": row.get("verification_id"), "component_type": row.get("component_type"), "status": row.get("status"), "verification_report_hash": row.get("verification_report_hash"), "package_zip_sha256": row.get("package_zip_sha256"), "manifest_hash": row.get("manifest_hash"), "required_by": row.get("required_by")})
                for row in verification_rows
            ),
            key=lambda item: str(item.get("verification_id") or ""),
        )
        self._add_exact_check("verifications", "toh_verification_index_matches_evidence", actual_verifications, expected_verifications, "Verification summary index is derived from evidence rows")
        expected_matrix_rows = _expected_matrix_rows(self.source_state, self.evidence)
        actual_matrix_projection = sorted(
            (_matrix_projection(row) for row in rows),
            key=lambda item: (str(item.get("component_id") or ""), str(item.get("requirement") or "")),
        )
        self._add_exact_check("readiness", "toh_readiness_matrix_semantics_match", actual_matrix_projection, expected_matrix_rows, "Readiness matrix matches source and evidence semantics")
        delivery_rows = [row for row in self.delivery_matrix.get("rows", []) if isinstance(row, dict)]
        delivery_expected_summary = _readiness_summary(delivery_rows)
        self._add_exact_check("delivery", "toh_delivery_readiness_summary_matches_rows", self.delivery_matrix.get("summary"), delivery_expected_summary, "Delivery readiness summary matches rows")
        delivery_expected_rows = _expected_delivery_matrix_rows(self.delivery_evidence)
        delivery_actual_rows = sorted((_matrix_projection(row) for row in delivery_rows), key=lambda item: (str(item.get("component_id") or ""), str(item.get("requirement") or "")))
        self._add_exact_check("delivery", "toh_delivery_readiness_semantics_match", delivery_actual_rows, delivery_expected_rows, "Delivery readiness matrix matches delivery evidence")
        delivery_expected_blockers = _expected_blockers(delivery_rows)
        delivery_actual_blockers = _normalize_blockers(self.delivery_blockers.get("blockers") if isinstance(self.delivery_blockers.get("blockers"), list) else [])
        self._add_exact_check("delivery", "toh_delivery_blockers_match_readiness", delivery_actual_blockers, delivery_expected_blockers, "Delivery blocker register matches delivery readiness")
        delivery_actions = self.delivery_actions.get("actions") if isinstance(self.delivery_actions.get("actions"), list) else []
        delivery_action_ids = sorted(str(item.get("action_id") or "") for item in delivery_actions if isinstance(item, dict))
        delivery_expected_action_ids = sorted(str(item.get("manual_action_id") or "") for item in self.delivery_blockers.get("blockers", []) if isinstance(item, dict))
        self._add_exact_check("delivery", "toh_delivery_actions_match_blockers", delivery_action_ids, delivery_expected_action_ids, "Delivery manual actions match delivery blockers")
        combined_summary = _combine_readiness_summaries(expected_summary, delivery_expected_summary)
        expected_status = "ready" if combined_summary.get("blocked_count") == 0 and combined_summary.get("stale_count") == 0 and combined_summary.get("missing_count") == 0 and len(expected_blockers) == 0 and len(delivery_expected_blockers) == 0 else "blocked"
        self._add_exact_check("hub_report", "toh_report_status_matches_readiness", self.report.get("status"), expected_status, "Hub report status matches readiness")
        report_readiness = self.report.get("readiness") if isinstance(self.report.get("readiness"), dict) else {}
        self._add_exact_check("hub_report", "toh_report_readiness_matches_matrix", {key: report_readiness.get(key) for key in ["row_count", "ready_count", "blocked_count", "warning_count", "stale_count", "missing_count"]}, combined_summary, "Hub report readiness summary matches matrix")

    def _verify_external_bindings(self) -> None:
        if self.hub_verification_report_path and not self.external_hub_verification_report:
            self.external_hub_verification_report = _read_json_file(self.hub_verification_report_path)
        elif self.require_signed or self.hub_signoff_path:
            self._add_check("external", "toh_hub_verification_report_required", "failed", "blocking", "--require-signed requires the Hub verification report used for signoff.")

        if self.hub_signoff_path:
            self.external_hub_signoff = _read_json_file(self.hub_signoff_path)
            self._verify_external_signoff(self.external_hub_signoff)
        elif self.require_signed:
            self._add_check("external", "toh_hub_signoff_required", "failed", "blocking", "--require-signed requires an external Hub signoff sidecar.")

        if self.publication_channel_state_path:
            self.external_channel_state = _read_json_file(self.publication_channel_state_path)
            expected_hash = publication_channel_state_hash(self.external_channel_state)
            states = _source_publication_states(self.source_state)
            state_hashes = {str(item.get("state_hash") or "") for item in states}
            self._add_check("external", "toh_external_channel_state_integrity", "passed" if self.external_channel_state else "failed", "blocking", "External publication channel state is readable." if self.external_channel_state else "External publication channel state is missing.")
            self._add_check("external", "toh_external_channel_state_hash", "passed" if expected_hash in state_hashes else "failed", "blocking", "External channel state matches Hub source state." if expected_hash in state_hashes else "External channel state does not match Hub source state.")
            current = self.external_channel_state.get("current_publication") if isinstance(self.external_channel_state.get("current_publication"), dict) else {}
            current_status = str(current.get("status") or "")
            bad = current_status in {"revoked", "superseded"} or not current
            self._add_check("external", "toh_external_channel_state_current", "failed" if bad else "passed", "blocking", "External publication channel state is current." if not bad else "External publication channel is missing, revoked, or superseded.")
        elif self.require_current:
            self._add_check("external", "toh_external_channel_state_required", "failed", "blocking", "Current verification requires an external publication channel state file.")

        if self.public_trust_center_verification_path:
            self.external_ptc_verification = _read_json_file(self.public_trust_center_verification_path)
            self._verify_external_report("public_trust_center_verification", self.external_ptc_verification, "toh_external_ptc_verification")
        elif self.require_current:
            self._add_check("external", "toh_external_ptc_verification_required", "failed", "blocking", "Current verification requires a Public Trust Center verification report.")

        if self.publication_monitoring_verification_path:
            self.external_monitoring_verification = _read_json_file(self.publication_monitoring_verification_path)
            self._verify_external_report("publication_monitoring_verification", self.external_monitoring_verification, "toh_external_monitoring_verification")
        elif self.require_current or self.require_publication_monitoring_clean:
            self._add_check("external", "toh_external_monitoring_verification_required", "failed", "blocking", "Current monitoring verification requires a Publication Monitoring verification report.")

        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            component_type = str(spec["component_type"])
            paths = self.delivery_verification_paths.get(component_type) or []
            expected_rows = _delivery_evidence_rows(self.delivery_evidence, component_type)
            reports = [_read_json_file(path) for path in paths]
            self.external_delivery_verifications[component_type] = reports
            if reports:
                self._verify_external_delivery_reports(component_type, expected_rows, reports, "toh_external_" + component_type)
            elif self.require_delivery_ready or (self.require_current and expected_rows):
                self._add_check("external", "toh_external_" + component_type + "_required", "failed", "blocking", f"Current delivery verification requires external {component_type} report.")
        self._verify_external_incidents()
        self._verify_external_trust_controls()
        self._verify_external_trust_control_signoff()
        self._verify_external_continuous_assurance()
        self._verify_external_assurance_watch()
        self._verify_external_assurance_watch_signoff()
        self._verify_external_final_readiness()

    def _verify_external_report(self, component_type: str, report: ImplementationDocument, check_prefix: str) -> None:
        expected = _evidence_by_type(self.evidence, component_type)
        report_hash = verification_hash(report)
        status = "passed" if report and report_hash == expected.get("verification_report_hash") else "failed"
        self._add_check("external", check_prefix + "_hash", status, "blocking", f"External {component_type} report matches Hub evidence." if status == "passed" else f"External {component_type} report does not match Hub evidence.")
        self._add_exact_check("external", check_prefix + "_status", report.get("status"), expected.get("status"), f"External {component_type} status")
        if component_type == "publication_monitoring_verification":
            summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            critical = int(summary.get("critical_incidents") or summary.get("open_critical_incidents") or 0)
            self._add_check("external", "toh_external_monitoring_no_open_critical_incidents", "passed" if critical == 0 else "failed", "blocking", "External monitoring report has no open critical incidents." if critical == 0 else "External monitoring report has open critical incidents.")

    def _verify_external_delivery_reports(self, component_type: str, expected_rows: list[ImplementationDocument], reports: list[ImplementationDocument], check_prefix: str) -> None:
        expected_by_id = {str(row.get("component_id") or ""): row for row in expected_rows if str(row.get("component_id") or "")}
        report_by_id: dict[str, dict[str, Any]] = {}
        duplicate_ids: list[str] = []
        unknown_ids: list[str] = []
        for index, report in enumerate(reports, start=1):
            component_id = _external_delivery_component_id(component_type, report, index)
            if component_id in report_by_id:
                duplicate_ids.append(component_id)
            report_by_id[component_id] = report
            if component_id not in expected_by_id:
                unknown_ids.append(component_id)
        missing_ids = sorted(set(expected_by_id) - set(report_by_id))
        extra_ids = sorted(set(report_by_id) - set(expected_by_id))
        self._add_check("external", check_prefix + "_component_coverage", "failed" if missing_ids or extra_ids or duplicate_ids else "passed", "blocking", f"External {component_type} reports do not match Hub delivery evidence. missing={missing_ids[:5]}, extra={extra_ids[:5]}, duplicates={duplicate_ids[:5]}" if missing_ids or extra_ids or duplicate_ids else f"External {component_type} reports cover all delivery evidence rows.")
        for component_id in sorted(set(expected_by_id) & set(report_by_id)):
            expected = expected_by_id[component_id]
            report = report_by_id[component_id]
            report_hash = verification_hash(report)
            safe_id = _check_safe_id(component_id)
            status = "passed" if report and report_hash == expected.get("verification_report_hash") else "failed"
            self._add_check("external", f"{check_prefix}_{safe_id}_hash", status, "blocking", f"External {component_type} report {component_id} matches delivery evidence." if status == "passed" else f"External {component_type} report {component_id} does not match delivery evidence.")
            self._add_exact_check("external", f"{check_prefix}_{safe_id}_status", report.get("status"), expected.get("status"), f"External {component_type} {component_id} status")
            self._add_exact_check("external", f"{check_prefix}_{safe_id}_zip_sha256", report.get("zip_sha256"), expected.get("zip_sha256"), f"External {component_type} {component_id} ZIP sha256")
            self._add_exact_check("external", f"{check_prefix}_{safe_id}_manifest_hash", report.get("manifest_hash"), expected.get("manifest_hash"), f"External {component_type} {component_id} manifest hash")

    def _verify_external_signoff(self, signoff: ImplementationDocument) -> None:
        self._add_exact_check("external", "toh_hub_signoff_package_type", signoff.get("package_type"), TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, "Hub signoff package_type")
        self._add_exact_check("external", "toh_hub_signoff_status", signoff.get("status"), "signed", "Hub signoff status")
        self._add_hash_check("external", "toh_hub_signoff_integrity", signoff.get("integrity_hash"), hub_hash(signoff), "Hub signoff integrity")
        source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
        self._add_exact_check("external", "toh_hub_signoff_zip_sha256", source.get("zip_sha256"), self.zip_sha256, "Hub signoff ZIP sha256")
        self._add_exact_check("external", "toh_hub_signoff_zip_size_bytes", source.get("zip_size_bytes"), self.zip_size_bytes, "Hub signoff ZIP size")
        self._add_exact_check("external", "toh_hub_signoff_manifest_hash", source.get("manifest_hash"), self.manifest.get("integrity_hash"), "Hub signoff manifest hash")
        self._add_exact_check("external", "toh_hub_signoff_report_hash", source.get("hub_report_hash"), self.report.get("integrity_hash"), "Hub signoff report hash")
        report = self.external_hub_verification_report
        if report:
            self._add_exact_check("external", "toh_hub_verification_package_type", report.get("package_type"), TRUST_OPERATIONS_HUB_VERIFICATION_PACKAGE_TYPE, "Hub verification package_type")
            self._add_exact_check("external", "toh_hub_signoff_verification_report_hash", source.get("verification_report_hash"), verification_hash(report), "Hub signoff verification report hash")
            self._add_exact_check("external", "toh_hub_verification_status", report.get("status"), source.get("verification_status"), "Hub verification status")
            self._add_exact_check("external", "toh_hub_verification_zip_sha256", report.get("zip_sha256"), self.zip_sha256, "Hub verification ZIP sha256")
            self._add_exact_check("external", "toh_hub_verification_zip_size_bytes", report.get("zip_size_bytes"), self.zip_size_bytes, "Hub verification ZIP size")
            self._add_exact_check("external", "toh_hub_verification_manifest_hash", report.get("manifest_hash"), self.manifest.get("integrity_hash"), "Hub verification manifest hash")
            self._add_exact_check("external", "toh_hub_verification_source_hash", report.get("source_hash"), self.report.get("integrity_hash"), "Hub verification source hash")

    def _verify_external_incidents(self) -> None:
        if not (self.require_incident_closeout or self.require_incident_regression_guards or self.incident_board_package_path or self.incident_board_verification_report_path or self.incident_knowledge_package_path or self.incident_knowledge_verification_report_path):
            return
        if (self.require_incident_closeout or self.incident_board_package_path or self.incident_board_verification_report_path) and not self.incident_board_package_path:
            self._add_check("external", "toh_incident_board_package_required", "failed", "blocking", "Incident closeout requires an external Incident Board ZIP.")
            if self.require_incident_closeout:
                return
        if (self.require_incident_closeout or self.incident_board_package_path or self.incident_board_verification_report_path) and not self.incident_board_verification_report_path:
            self._add_check("external", "toh_incident_board_verification_required", "failed", "blocking", "Incident closeout requires an external Incident Board verification report.")
            if self.require_incident_closeout:
                return
        if self.incident_board_package_path and self.incident_board_verification_report_path:
            report = _read_json_file(self.incident_board_verification_report_path)
            self.external_incident_verification_report = report
            zip_path = self.incident_board_package_path
            zip_sha256 = _sha256_file(zip_path) if zip_path.exists() else None
            zip_size = os.stat(_fs_path(zip_path)).st_size if zip_path.exists() else None
            self._add_exact_check("external", "toh_incident_verification_status", report.get("status"), "passed", "Incident verification status")
            self._add_exact_check("external", "toh_incident_verification_zip_sha256", report.get("zip_sha256"), zip_sha256, "Incident verification ZIP sha256")
            self._add_exact_check("external", "toh_incident_verification_zip_size_bytes", report.get("zip_size_bytes"), zip_size, "Incident verification ZIP size")
            self._add_exact_check("external", "toh_incident_verification_hub_report_hash", report.get("hub_report_hash"), self.report.get("integrity_hash"), "Incident package Hub report hash")
            hub_report_hash = None
            if self.external_hub_verification_report:
                hub_report_hash = verification_hash(self.external_hub_verification_report)
            self._add_exact_check("external", "toh_incident_verification_hub_verification_hash", report.get("hub_verification_report_hash"), hub_report_hash, "Incident package Hub verification hash")
            summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            self._add_check("external", "toh_incident_verification_no_open_blocking", "passed" if int(summary.get("blocking_open_count") or 0) == 0 else "failed", "blocking", "Incident package has no open blocking incidents." if int(summary.get("blocking_open_count") or 0) == 0 else "Incident package has open blocking incidents.")
            self._add_check("external", "toh_incident_verification_no_stale", "passed" if int(summary.get("stale_count") or 0) == 0 else "failed", "blocking", "Incident package has no stale incidents." if int(summary.get("stale_count") or 0) == 0 else "Incident package has stale incidents.")
        if not (self.require_incident_regression_guards or self.incident_knowledge_package_path or self.incident_knowledge_verification_report_path):
            return
        if not self.incident_knowledge_package_path:
            self._add_check("external", "toh_incident_knowledge_package_required", "failed", "blocking", "Incident regression guards require an external Knowledge ZIP.")
            return
        if not self.incident_knowledge_verification_report_path:
            self._add_check("external", "toh_incident_knowledge_verification_required", "failed", "blocking", "Incident regression guards require an external Knowledge verification report.")
            return
        knowledge_report = _read_json_file(self.incident_knowledge_verification_report_path)
        self.external_incident_knowledge_verification_report = knowledge_report
        knowledge_zip = self.incident_knowledge_package_path
        knowledge_zip_sha256 = _sha256_file(knowledge_zip) if knowledge_zip.exists() else None
        knowledge_zip_size = os.stat(_fs_path(knowledge_zip)).st_size if knowledge_zip.exists() else None
        self._add_exact_check("external", "toh_incident_knowledge_verification_status", knowledge_report.get("status"), "passed", "Knowledge verification status")
        self._add_exact_check("external", "toh_incident_knowledge_zip_sha256", knowledge_report.get("zip_sha256"), knowledge_zip_sha256, "Knowledge ZIP sha256")
        self._add_exact_check("external", "toh_incident_knowledge_zip_size_bytes", knowledge_report.get("zip_size_bytes"), knowledge_zip_size, "Knowledge ZIP size")
        if self.external_incident_verification_report:
            self._add_exact_check("external", "toh_incident_knowledge_incident_verification_hash", knowledge_report.get("incident_verification_report_hash"), verification_hash(self.external_incident_verification_report), "Knowledge Incident verification report hash")
            self._add_exact_check("external", "toh_incident_knowledge_incident_zip_sha256", knowledge_report.get("incident_zip_sha256"), self.external_incident_verification_report.get("zip_sha256"), "Knowledge Incident ZIP sha256")
            self._add_exact_check("external", "toh_incident_knowledge_incident_zip_size_bytes", knowledge_report.get("incident_zip_size_bytes"), self.external_incident_verification_report.get("zip_size_bytes"), "Knowledge Incident ZIP size")
            self._add_exact_check("external", "toh_incident_knowledge_incident_manifest_hash", knowledge_report.get("incident_manifest_hash"), self.external_incident_verification_report.get("manifest_hash"), "Knowledge Incident manifest hash")
        elif self.require_incident_regression_guards:
            self._add_check("external", "toh_incident_knowledge_incident_verification_required", "failed", "blocking", "Knowledge gate requires the current Incident verification report.")
        if self.external_hub_verification_report:
            self._add_exact_check("external", "toh_incident_knowledge_hub_verification_hash", knowledge_report.get("hub_verification_report_hash"), verification_hash(self.external_hub_verification_report), "Knowledge Hub verification report hash")
        summary = knowledge_report.get("summary") if isinstance(knowledge_report.get("summary"), dict) else {}
        self._add_check("external", "toh_incident_knowledge_guards_passed", "passed" if int(summary.get("guard_failed_count") or 0) == 0 and int(summary.get("guards_passed_count") or 0) > 0 else "failed", "blocking", "Knowledge regression guards passed." if int(summary.get("guard_failed_count") or 0) == 0 and int(summary.get("guards_passed_count") or 0) > 0 else "Knowledge regression guards are missing or failed.")
        self._add_check("external", "toh_incident_knowledge_no_recurrence", "passed" if int(summary.get("recurrence_count") or 0) == 0 else "failed", "blocking", "Knowledge recurrence report has no open recurrence." if int(summary.get("recurrence_count") or 0) == 0 else "Knowledge recurrence report has open recurrence.")

    def _verify_external_trust_controls(self) -> None:
        if not (self.require_trust_controls or self.trust_control_package_path or self.trust_control_verification_report_path):
            return
        if not self.trust_control_package_path:
            self._add_check("external", "toh_trust_control_package_required", "failed", "blocking", "Trust control gate requires an external Control ZIP.")
            return
        if not self.trust_control_verification_report_path:
            self._add_check("external", "toh_trust_control_verification_required", "failed", "blocking", "Trust control gate requires an external Control verification report.")
            return
        report = _read_json_file(self.trust_control_verification_report_path)
        self.external_trust_control_verification_report = report
        zip_path = self.trust_control_package_path
        zip_sha256 = _sha256_file(zip_path) if zip_path.exists() else None
        zip_size = os.stat(_fs_path(zip_path)).st_size if zip_path.exists() else None
        self._add_exact_check("external", "toh_trust_control_verification_package_type", report.get("package_type"), "musicforge_trust_operations_control_verification", "Control verification package_type")
        self._add_exact_check("external", "toh_trust_control_verification_status", report.get("status"), "passed", "Control verification status")
        self._add_exact_check("external", "toh_trust_control_zip_sha256", report.get("zip_sha256"), zip_sha256, "Control ZIP sha256")
        self._add_exact_check("external", "toh_trust_control_zip_size_bytes", report.get("zip_size_bytes"), zip_size, "Control ZIP size")
        self._add_exact_check("external", "toh_trust_control_hub_zip_sha256", report.get("hub_zip_sha256"), self.zip_sha256, "Control Hub ZIP sha256")
        self._add_exact_check("external", "toh_trust_control_hub_zip_size_bytes", report.get("hub_zip_size_bytes"), self.zip_size_bytes, "Control Hub ZIP size")
        self._add_exact_check("external", "toh_trust_control_hub_manifest_hash", report.get("hub_manifest_hash"), self.manifest.get("integrity_hash"), "Control Hub manifest hash")
        if self.external_hub_verification_report:
            self._add_exact_check("external", "toh_trust_control_hub_verification_hash", report.get("hub_verification_report_hash"), verification_hash(self.external_hub_verification_report), "Control Hub verification report hash")
        elif self.require_trust_controls:
            self._add_check("external", "toh_trust_control_hub_verification_required", "failed", "blocking", "Trust control gate requires the current Hub verification report.")
        if self.external_incident_verification_report:
            self._add_exact_check("external", "toh_trust_control_incident_verification_hash", report.get("incident_verification_report_hash"), verification_hash(self.external_incident_verification_report), "Control Incident verification report hash")
            self._add_exact_check("external", "toh_trust_control_incident_zip_sha256", report.get("incident_zip_sha256"), self.external_incident_verification_report.get("zip_sha256"), "Control Incident ZIP sha256")
            self._add_exact_check("external", "toh_trust_control_incident_manifest_hash", report.get("incident_manifest_hash"), self.external_incident_verification_report.get("manifest_hash"), "Control Incident manifest hash")
        elif self.require_trust_controls:
            self._add_check("external", "toh_trust_control_incident_verification_required", "failed", "blocking", "Trust control gate requires the current Incident verification report.")
        if self.external_incident_knowledge_verification_report:
            self._add_exact_check("external", "toh_trust_control_knowledge_verification_hash", report.get("knowledge_verification_report_hash"), verification_hash(self.external_incident_knowledge_verification_report), "Control Knowledge verification report hash")
            self._add_exact_check("external", "toh_trust_control_knowledge_zip_sha256", report.get("knowledge_zip_sha256"), self.external_incident_knowledge_verification_report.get("zip_sha256"), "Control Knowledge ZIP sha256")
            self._add_exact_check("external", "toh_trust_control_knowledge_manifest_hash", report.get("knowledge_manifest_hash"), self.external_incident_knowledge_verification_report.get("manifest_hash"), "Control Knowledge manifest hash")
        elif self.require_trust_controls:
            self._add_check("external", "toh_trust_control_knowledge_verification_required", "failed", "blocking", "Trust control gate requires the current Knowledge verification report.")
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        self._add_check("external", "toh_trust_control_required_controls_passed", "passed" if int(summary.get("required_failed_count") or 0) == 0 else "failed", "blocking", "Trust control policy passed." if int(summary.get("required_failed_count") or 0) == 0 else "Trust control policy has failed required controls.")

    def _verify_external_trust_control_signoff(self) -> None:
        if not (self.require_trust_control_signoff or self.trust_control_signoff_archive_path or self.trust_control_signoff_verification_report_path):
            return
        if not self.trust_control_signoff_archive_path:
            self._add_check("external", "toh_trust_control_signoff_archive_required", "failed", "blocking", "Trust control signoff gate requires an external Control Signoff archive ZIP.")
            return
        if not self.trust_control_signoff_verification_report_path:
            self._add_check("external", "toh_trust_control_signoff_verification_required", "failed", "blocking", "Trust control signoff gate requires an external Control Signoff verification report.")
            return
        report = _read_json_file(self.trust_control_signoff_verification_report_path)
        self.external_trust_control_signoff_verification_report = report
        archive_path = self.trust_control_signoff_archive_path
        archive_sha = _sha256_file(archive_path) if archive_path.exists() else None
        archive_size = os.stat(_fs_path(archive_path)).st_size if archive_path.exists() else None
        self._add_exact_check("external", "toh_trust_control_signoff_verification_package_type", report.get("package_type"), "musicforge_trust_operations_control_signoff_verification", "Control Signoff verification package_type")
        self._add_exact_check("external", "toh_trust_control_signoff_verification_status", report.get("status"), "passed", "Control Signoff verification status")
        self._add_exact_check("external", "toh_trust_control_signoff_archive_zip_sha256", report.get("zip_sha256"), archive_sha, "Control Signoff archive ZIP sha256")
        self._add_exact_check("external", "toh_trust_control_signoff_archive_zip_size_bytes", report.get("zip_size_bytes"), archive_size, "Control Signoff archive ZIP size")
        if self.external_trust_control_verification_report:
            self._add_exact_check("external", "toh_trust_control_signoff_control_verification_hash", report.get("control_verification_report_hash"), verification_hash(self.external_trust_control_verification_report), "Control Signoff Control verification hash")
            self._add_exact_check("external", "toh_trust_control_signoff_control_zip_sha256", report.get("control_zip_sha256"), self.external_trust_control_verification_report.get("zip_sha256"), "Control Signoff Control ZIP sha256")
            self._add_exact_check("external", "toh_trust_control_signoff_control_manifest_hash", report.get("control_manifest_hash"), self.external_trust_control_verification_report.get("manifest_hash"), "Control Signoff Control manifest hash")
        elif self.require_trust_control_signoff:
            self._add_check("external", "toh_trust_control_signoff_control_verification_required", "failed", "blocking", "Trust control signoff gate requires the current Control verification report.")
        if self.external_hub_verification_report:
            self._add_exact_check("external", "toh_trust_control_signoff_hub_verification_hash", report.get("hub_verification_report_hash"), verification_hash(self.external_hub_verification_report), "Control Signoff Hub verification hash")
        elif self.require_trust_control_signoff:
            self._add_check("external", "toh_trust_control_signoff_hub_verification_required", "failed", "blocking", "Trust control signoff gate requires the current Hub verification report.")
        self._add_exact_check("external", "toh_trust_control_signoff_hub_zip_sha256", report.get("hub_zip_sha256"), self.zip_sha256, "Control Signoff Hub ZIP sha256")
        self._add_exact_check("external", "toh_trust_control_signoff_hub_manifest_hash", report.get("hub_manifest_hash"), self.manifest.get("integrity_hash"), "Control Signoff Hub manifest hash")
        if self.external_incident_verification_report:
            self._add_exact_check("external", "toh_trust_control_signoff_incident_binding", report.get("incident_verification_report_hash"), verification_hash(self.external_incident_verification_report), "Control Signoff Incident verification hash")
            self._add_exact_check("external", "toh_trust_control_signoff_incident_zip_sha256", report.get("incident_zip_sha256"), self.external_incident_verification_report.get("zip_sha256"), "Control Signoff Incident ZIP sha256")
            self._add_exact_check("external", "toh_trust_control_signoff_incident_manifest_hash", report.get("incident_manifest_hash"), self.external_incident_verification_report.get("manifest_hash"), "Control Signoff Incident manifest hash")
        elif self.require_trust_control_signoff:
            self._add_check("external", "toh_trust_control_signoff_incident_verification_required", "failed", "blocking", "Trust control signoff gate requires the current Incident verification report.")
        if self.external_incident_knowledge_verification_report:
            self._add_exact_check("external", "toh_trust_control_signoff_knowledge_binding", report.get("knowledge_verification_report_hash"), verification_hash(self.external_incident_knowledge_verification_report), "Control Signoff Knowledge verification hash")
            self._add_exact_check("external", "toh_trust_control_signoff_knowledge_zip_sha256", report.get("knowledge_zip_sha256"), self.external_incident_knowledge_verification_report.get("zip_sha256"), "Control Signoff Knowledge ZIP sha256")
            self._add_exact_check("external", "toh_trust_control_signoff_knowledge_manifest_hash", report.get("knowledge_manifest_hash"), self.external_incident_knowledge_verification_report.get("manifest_hash"), "Control Signoff Knowledge manifest hash")
        elif self.require_trust_control_signoff:
            self._add_check("external", "toh_trust_control_signoff_knowledge_verification_required", "failed", "blocking", "Trust control signoff gate requires the current Knowledge verification report.")

    def _verify_external_continuous_assurance(self) -> None:
        if not (self.require_continuous_assurance or self.continuous_assurance_archive_path or self.continuous_assurance_verification_report_path):
            return
        if not self.continuous_assurance_archive_path:
            self._add_check("external", "toh_continuous_assurance_archive_required", "failed", "blocking", "Continuous Assurance gate requires an external Assurance archive ZIP.")
            return
        if not self.continuous_assurance_verification_report_path:
            self._add_check("external", "toh_continuous_assurance_verification_required", "failed", "blocking", "Continuous Assurance gate requires an external Assurance verification report.")
            return
        report = _read_json_file(self.continuous_assurance_verification_report_path)
        self.external_continuous_assurance_verification_report = report
        archive_path = self.continuous_assurance_archive_path
        archive_sha = _sha256_file(archive_path) if archive_path.exists() else None
        archive_size = os.stat(_fs_path(archive_path)).st_size if archive_path.exists() else None
        assurance_manifest = _read_zip_json(archive_path, "trust-operations-assurance-manifest.json") if archive_path.exists() else {}
        self._add_exact_check("external", "toh_continuous_assurance_verification_package_type", report.get("package_type"), "musicforge_trust_operations_continuous_assurance_verification", "Continuous Assurance verification package_type")
        self._add_exact_check("external", "toh_continuous_assurance_verification_status", report.get("status"), "passed", "Continuous Assurance verification status")
        self._add_exact_check("external", "toh_continuous_assurance_archive_zip_sha256", report.get("zip_sha256"), archive_sha, "Continuous Assurance archive ZIP sha256")
        self._add_exact_check("external", "toh_continuous_assurance_archive_zip_size_bytes", report.get("zip_size_bytes"), archive_size, "Continuous Assurance archive ZIP size")
        self._add_exact_check("external", "toh_continuous_assurance_manifest_hash", report.get("manifest_hash"), assurance_manifest.get("integrity_hash"), "Continuous Assurance manifest hash")
        self._add_exact_check("external", "toh_continuous_assurance_hub_zip_sha256", report.get("hub_zip_sha256"), self.zip_sha256, "Continuous Assurance Hub ZIP sha256")
        self._add_exact_check("external", "toh_continuous_assurance_hub_zip_size_bytes", report.get("hub_zip_size_bytes"), self.zip_size_bytes, "Continuous Assurance Hub ZIP size")
        self._add_exact_check("external", "toh_continuous_assurance_hub_manifest_hash", report.get("hub_manifest_hash"), self.manifest.get("integrity_hash"), "Continuous Assurance Hub manifest hash")
        if self.external_hub_verification_report:
            self._add_exact_check("external", "toh_continuous_assurance_hub_verification_hash", report.get("hub_verification_report_hash"), verification_hash(self.external_hub_verification_report), "Continuous Assurance Hub verification report hash")
        elif self.require_continuous_assurance:
            self._add_check("external", "toh_continuous_assurance_hub_verification_required", "failed", "blocking", "Continuous Assurance gate requires the current Hub verification report.")

    def _verify_external_assurance_watch(self) -> None:
        if not (self.require_assurance_watch_clear or self.assurance_watch_package_path or self.assurance_watch_verification_report_path):
            return
        if not self.assurance_watch_package_path:
            self._add_check("external", "toh_assurance_watch_package_required", "failed", "blocking", "Assurance Watch gate requires an external Assurance Watch ZIP.")
            return
        if not self.assurance_watch_verification_report_path:
            self._add_check("external", "toh_assurance_watch_verification_required", "failed", "blocking", "Assurance Watch gate requires an external Assurance Watch verification report.")
            return
        report = _read_json_file(self.assurance_watch_verification_report_path)
        self.external_assurance_watch_verification_report = report
        watch_path = self.assurance_watch_package_path
        watch_sha = _sha256_file(watch_path) if watch_path.exists() else None
        watch_size = os.stat(_fs_path(watch_path)).st_size if watch_path.exists() else None
        watch_manifest = _read_zip_json(watch_path, "trust-operations-assurance-watch-manifest.json") if watch_path.exists() else {}
        self._add_exact_check("external", "toh_assurance_watch_verification_package_type", report.get("package_type"), "musicforge_trust_operations_assurance_watch_verification", "Assurance Watch verification package_type")
        self._add_exact_check("external", "toh_assurance_watch_verification_status", report.get("status"), "passed", "Assurance Watch verification status")
        self._add_exact_check("external", "toh_assurance_watch_zip_sha256", report.get("zip_sha256"), watch_sha, "Assurance Watch ZIP sha256")
        self._add_exact_check("external", "toh_assurance_watch_zip_size_bytes", report.get("zip_size_bytes"), watch_size, "Assurance Watch ZIP size")
        self._add_exact_check("external", "toh_assurance_watch_manifest_hash", report.get("manifest_hash"), watch_manifest.get("integrity_hash"), "Assurance Watch manifest hash")
        self._add_exact_check("external", "toh_assurance_watch_clear", report.get("clear"), True, "Assurance Watch clear status")
        self._add_exact_check("external", "toh_assurance_watch_overdue_count", int(report.get("overdue_count") or 0), 0, "Assurance Watch overdue count")
        self._add_exact_check("external", "toh_assurance_watch_blocking_action_count", int(report.get("blocking_action_count") or 0), 0, "Assurance Watch blocking action count")
        if self.external_hub_verification_report:
            expected = verification_hash(self.external_hub_verification_report)
            hashes = {str(item) for item in report.get("hub_verification_report_hashes", []) if item}
            self._add_check("external", "toh_assurance_watch_hub_verification_hash", "passed" if expected in hashes else "failed", "blocking", "Assurance Watch binds the current Hub verification report." if expected in hashes else "Assurance Watch does not bind the current Hub verification report.")
        elif self.require_assurance_watch_clear:
            self._add_check("external", "toh_assurance_watch_hub_verification_required", "failed", "blocking", "Assurance Watch gate requires the current Hub verification report.")

    def _verify_external_assurance_watch_signoff(self) -> None:
        if not (self.require_assurance_watch_signoff or self.assurance_watch_signoff_archive_path or self.assurance_watch_signoff_verification_report_path):
            return
        if not self.assurance_watch_signoff_archive_path:
            self._add_check("external", "toh_assurance_watch_signoff_archive_required", "failed", "blocking", "Assurance Watch signoff gate requires an external Assurance Watch Signoff archive ZIP.")
            return
        if not self.assurance_watch_signoff_verification_report_path:
            self._add_check("external", "toh_assurance_watch_signoff_verification_required", "failed", "blocking", "Assurance Watch signoff gate requires an external Assurance Watch Signoff verification report.")
            return
        report = _read_json_file(self.assurance_watch_signoff_verification_report_path)
        self.external_assurance_watch_signoff_verification_report = report
        archive_path = self.assurance_watch_signoff_archive_path
        archive_sha = _sha256_file(archive_path) if archive_path.exists() else None
        archive_size = os.stat(_fs_path(archive_path)).st_size if archive_path.exists() else None
        archive_manifest = _read_zip_json(archive_path, "trust-operations-assurance-watch-signoff-manifest.json") if archive_path.exists() else {}
        self._add_exact_check("external", "toh_assurance_watch_signoff_verification_package_type", report.get("package_type"), "musicforge_trust_operations_assurance_watch_signoff_verification", "Assurance Watch Signoff verification package_type")
        self._add_exact_check("external", "toh_assurance_watch_signoff_verification_status", report.get("status"), "passed", "Assurance Watch Signoff verification status")
        self._add_exact_check("external", "toh_assurance_watch_signoff_archive_zip_sha256", report.get("zip_sha256"), archive_sha, "Assurance Watch Signoff archive ZIP sha256")
        self._add_exact_check("external", "toh_assurance_watch_signoff_archive_zip_size_bytes", report.get("zip_size_bytes"), archive_size, "Assurance Watch Signoff archive ZIP size")
        self._add_exact_check("external", "toh_assurance_watch_signoff_manifest_hash", report.get("manifest_hash"), archive_manifest.get("integrity_hash"), "Assurance Watch Signoff archive manifest hash")
        if self.external_hub_verification_report:
            self._add_exact_check("external", "toh_assurance_watch_signoff_hub_verification_hash", report.get("hub_verification_report_hash"), verification_hash(self.external_hub_verification_report), "Assurance Watch Signoff Hub verification report hash")
            self._add_exact_check("external", "toh_assurance_watch_signoff_hub_manifest_hash", report.get("hub_manifest_hash"), self.manifest.get("integrity_hash"), "Assurance Watch Signoff Hub manifest hash")
        elif self.require_assurance_watch_signoff:
            self._add_check("external", "toh_assurance_watch_signoff_hub_verification_required", "failed", "blocking", "Assurance Watch Signoff gate requires the current Hub verification report.")
        if self.external_assurance_watch_verification_report:
            self._add_exact_check("external", "toh_assurance_watch_signoff_watch_verification_hash", report.get("watch_verification_report_hash"), verification_hash(self.external_assurance_watch_verification_report), "Assurance Watch Signoff Watch verification report hash")
            self._add_exact_check("external", "toh_assurance_watch_signoff_watch_zip_sha256", report.get("watch_zip_sha256"), self.external_assurance_watch_verification_report.get("zip_sha256"), "Assurance Watch Signoff Watch ZIP sha256")
            self._add_exact_check("external", "toh_assurance_watch_signoff_watch_manifest_hash", report.get("watch_manifest_hash"), self.external_assurance_watch_verification_report.get("manifest_hash"), "Assurance Watch Signoff Watch manifest hash")
        elif self.require_assurance_watch_signoff:
            self._add_check("external", "toh_assurance_watch_signoff_watch_verification_required", "failed", "blocking", "Assurance Watch Signoff gate requires the current Watch verification report.")
        if self.external_continuous_assurance_verification_report:
            self._add_exact_check("external", "toh_assurance_watch_signoff_continuous_assurance_hash", report.get("continuous_assurance_report_hash"), verification_hash(self.external_continuous_assurance_verification_report), "Assurance Watch Signoff Continuous Assurance verification hash")
        elif self.require_assurance_watch_signoff:
            self._add_check("external", "toh_assurance_watch_signoff_continuous_assurance_required", "failed", "blocking", "Assurance Watch Signoff gate requires the current Continuous Assurance verification report.")

    def _verify_external_final_readiness(self) -> None:
        if not (self.require_final_readiness or self.final_handoff_package_path or self.final_handoff_verification_report_path):
            return
        if not self.final_handoff_package_path:
            self._add_check("external", "toh_final_readiness_package_required", "failed", "blocking", "Final Readiness gate requires an external Final Handoff ZIP.")
            return
        if not self.final_handoff_verification_report_path:
            self._add_check("external", "toh_final_readiness_verification_required", "failed", "blocking", "Final Readiness gate requires an external Final Handoff verification report.")
            return
        report = _read_json_file(self.final_handoff_verification_report_path)
        self.external_final_handoff_verification_report = report
        package_path = self.final_handoff_package_path
        package_sha = _sha256_file(package_path) if package_path.exists() else None
        package_size = os.stat(_fs_path(package_path)).st_size if package_path.exists() else None
        package_manifest = _read_zip_json(package_path, "trust-operations-final-readiness-manifest.json") if package_path.exists() else {}
        self._add_exact_check("external", "toh_final_readiness_verification_package_type", report.get("package_type"), "musicforge_trust_operations_final_handoff_verification", "Final Handoff verification package_type")
        self._add_exact_check("external", "toh_final_readiness_verification_status", report.get("status"), "passed", "Final Handoff verification status")
        self._add_exact_check("external", "toh_final_readiness_zip_sha256", report.get("zip_sha256"), package_sha, "Final Handoff ZIP sha256")
        self._add_exact_check("external", "toh_final_readiness_zip_size_bytes", report.get("zip_size_bytes"), package_size, "Final Handoff ZIP size")
        self._add_exact_check("external", "toh_final_readiness_manifest_hash", report.get("manifest_hash"), package_manifest.get("integrity_hash"), "Final Handoff manifest hash")
        self._add_exact_check("external", "toh_final_readiness_hub_zip_sha256", report.get("hub_zip_sha256"), self.zip_sha256, "Final Handoff Hub ZIP sha256")
        self._add_exact_check("external", "toh_final_readiness_hub_manifest_hash", report.get("hub_manifest_hash"), self.manifest.get("integrity_hash"), "Final Handoff Hub manifest hash")
        if self.external_hub_verification_report:
            self._add_exact_check("external", "toh_final_readiness_hub_verification_hash", report.get("hub_verification_report_hash"), verification_hash(self.external_hub_verification_report), "Final Handoff Hub verification report hash")
        elif self.require_final_readiness:
            self._add_check("external", "toh_final_readiness_hub_verification_required", "failed", "blocking", "Final Readiness gate requires the current Hub verification report.")
        if self.external_assurance_watch_signoff_verification_report:
            self._add_exact_check("external", "toh_final_readiness_watch_signoff_hash", report.get("assurance_watch_signoff_verification_report_hash"), verification_hash(self.external_assurance_watch_signoff_verification_report), "Final Handoff Assurance Watch Signoff verification report hash")
        elif self.require_final_readiness:
            self._add_check("external", "toh_final_readiness_watch_signoff_required", "failed", "blocking", "Final Readiness gate requires the current Assurance Watch Signoff verification report.")

    def _verify_requirements(self) -> None:
        report_readiness = self.report.get("readiness") if isinstance(self.report.get("readiness"), dict) else {}
        ready = self.report.get("status") == "ready" and report_readiness.get("blocked_count") == 0 and report_readiness.get("stale_count") == 0 and report_readiness.get("missing_count") == 0
        self._add_check("requirements", "toh_require_ready", "passed" if ready or not self.require_ready else "failed", "blocking", "Hub is ready." if ready else "Hub is not ready.")
        signed = self.external_hub_signoff.get("status") == "signed"
        self._add_check("requirements", "toh_require_signed", "passed" if signed or not self.require_signed else "failed", "blocking", "Hub is signed." if signed else "Hub is not signed.")
        critical = int((self.blockers_doc.get("summary") if isinstance(self.blockers_doc.get("summary"), dict) else {}).get("critical_count") or 0)
        self._add_check("requirements", "toh_require_no_critical_blockers", "passed" if critical == 0 or not self.require_no_critical_blockers else "failed", "blocking", "No critical Hub blockers." if critical == 0 else "Hub has critical blockers.")
        monitoring_row = next((row for row in self.matrix.get("rows", []) if isinstance(row, dict) and row.get("requirement") == "publication_monitoring_clean"), {})
        monitoring_ready = monitoring_row.get("status") == "ready"
        self._add_check("requirements", "toh_require_publication_monitoring_clean", "passed" if monitoring_ready or not self.require_publication_monitoring_clean else "failed", "blocking", "Publication monitoring is clean." if monitoring_ready else "Publication monitoring is not clean.")
        delivery_summary = self.delivery_matrix.get("summary") if isinstance(self.delivery_matrix.get("summary"), dict) else {}
        delivery_rows = self.delivery_matrix.get("rows") if isinstance(self.delivery_matrix.get("rows"), list) else []
        present_types = {str(row.get("component_type") or "") for row in delivery_rows if isinstance(row, dict)}
        expected_types = {str(spec["component_type"]) for spec in DELIVERY_VERIFICATION_COMPONENTS}
        delivery_ready = bool(delivery_rows) and expected_types.issubset(present_types) and delivery_summary.get("blocked_count") == 0 and delivery_summary.get("stale_count") == 0 and delivery_summary.get("missing_count") == 0
        self._add_check("requirements", "toh_require_delivery_ready", "passed" if delivery_ready or not self.require_delivery_ready else "failed", "blocking", "Delivery evidence is ready." if delivery_ready else "Delivery evidence is not ready.")
        incident_ready = self.external_incident_verification_report.get("status") == "passed"
        self._add_check("requirements", "toh_require_incident_closeout", "passed" if incident_ready or not self.require_incident_closeout else "failed", "blocking", "Incident closeout evidence is passed." if incident_ready else "Incident closeout evidence is missing or failed.")
        knowledge_summary = self.external_incident_knowledge_verification_report.get("summary") if isinstance(self.external_incident_knowledge_verification_report.get("summary"), dict) else {}
        knowledge_ready = self.external_incident_knowledge_verification_report.get("status") == "passed" and int(knowledge_summary.get("guards_passed_count") or 0) > 0 and int(knowledge_summary.get("guard_failed_count") or 0) == 0 and int(knowledge_summary.get("recurrence_count") or 0) == 0
        self._add_check("requirements", "toh_require_incident_regression_guards", "passed" if knowledge_ready or not self.require_incident_regression_guards else "failed", "blocking", "Incident regression guards are passed." if knowledge_ready else "Incident regression guard evidence is missing or failed.")
        controls_summary = self.external_trust_control_verification_report.get("summary") if isinstance(self.external_trust_control_verification_report.get("summary"), dict) else {}
        controls_ready = self.external_trust_control_verification_report.get("status") == "passed" and int(controls_summary.get("required_failed_count") or 0) == 0
        self._add_check("requirements", "toh_require_trust_controls", "passed" if controls_ready or not self.require_trust_controls else "failed", "blocking", "Trust controls are passed." if controls_ready else "Trust control evidence is missing or failed.")
        control_signoff_ready = self.external_trust_control_signoff_verification_report.get("status") == "passed"
        self._add_check("requirements", "toh_require_trust_control_signoff", "passed" if control_signoff_ready or not self.require_trust_control_signoff else "failed", "blocking", "Trust control signoff is passed." if control_signoff_ready else "Trust control signoff evidence is missing or failed.")
        assurance_ready = self.external_continuous_assurance_verification_report.get("status") == "passed"
        self._add_check("requirements", "toh_require_continuous_assurance", "passed" if assurance_ready or not self.require_continuous_assurance else "failed", "blocking", "Continuous Assurance is passed." if assurance_ready else "Continuous Assurance evidence is missing or failed.")
        watch_ready = self.external_assurance_watch_verification_report.get("status") == "passed" and self.external_assurance_watch_verification_report.get("clear") is True and int(self.external_assurance_watch_verification_report.get("overdue_count") or 0) == 0 and int(self.external_assurance_watch_verification_report.get("blocking_action_count") or 0) == 0
        self._add_check("requirements", "toh_require_assurance_watch_clear", "passed" if watch_ready or not self.require_assurance_watch_clear else "failed", "blocking", "Assurance Watch is clear." if watch_ready else "Assurance Watch evidence is missing, stale, or blocked.")
        watch_signoff_ready = self.external_assurance_watch_signoff_verification_report.get("status") == "passed"
        self._add_check("requirements", "toh_require_assurance_watch_signoff", "passed" if watch_signoff_ready or not self.require_assurance_watch_signoff else "failed", "blocking", "Assurance Watch signoff is passed." if watch_signoff_ready else "Assurance Watch signoff evidence is missing, stale, or failed.")
        final_ready = self.external_final_handoff_verification_report.get("status") == "passed"
        self._add_check("requirements", "toh_require_final_readiness", "passed" if final_ready or not self.require_final_readiness else "failed", "blocking", "Final Readiness handoff is passed." if final_ready else "Final Readiness handoff evidence is missing, stale, or failed.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in self.entry_infos:
            name = info.filename
            if not _is_text_scan_entry(name) or int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8", errors="ignore")
            except (KeyError, OSError):
                continue
            if _contains_sensitive_text(text):
                findings.append({"path": name, "reason": "sensitive_text"})
        for doc_name, doc in {
            "manifest": self.manifest,
            "hub_report": self.report,
            "readiness_matrix": self.matrix,
            "blocker_register": self.blockers_doc,
            "manual_action_queue": self.actions,
            "evidence_binding_index": self.evidence,
            "verification_summary_index": self.verifications,
            "source_state": self.source_state,
            "delivery_evidence_index": self.delivery_evidence,
            "delivery_readiness_matrix": self.delivery_matrix,
            "delivery_blocker_register": self.delivery_blockers,
            "delivery_manual_action_queue": self.delivery_actions,
            "signoff_summary": self.signoff_summary,
            "hub_signoff": self.external_hub_signoff,
            "hub_verification_report": self.external_hub_verification_report,
        }.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "toh_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Hub package." if findings else "No sensitive values found in Hub package.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        summary = {
            "hub_id": self.report.get("hub_id"),
            "report_id": self.report.get("report_id"),
            "readiness": self.report.get("status"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
            "entry_count": len(self.entry_names),
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_HUB_VERIFICATION_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": self.report.get("integrity_hash"),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": summary,
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        try:
            raw = archive.read(name)
            value = json.loads(raw.decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parsed.")
        return value

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _expected_matrix_rows(source_state: ImplementationDocument, evidence: ImplementationDocument) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    ptc = _evidence_by_type(evidence, "public_trust_center_verification")
    rows.append(_matrix_row_projection("public-trust-center:ptc-default", "public_trust_center", "public_trust_center_verified", _status_from_evidence(ptc)))
    states = _source_publication_states(source_state)
    state = states[0] if states else {}
    current_status = str(state.get("current_status") or "")
    publication_status = "ready" if state and current_status not in {"revoked", "superseded"} else "blocked"
    rows.append(_matrix_row_projection("publication-channel:" + str(state.get("channel_id") or "missing"), "publication_channel", "publication_current", publication_status))
    monitoring = _evidence_by_type(evidence, "publication_monitoring_verification")
    rows.append(_matrix_row_projection("publication-monitoring:public-release", "publication_monitoring", "publication_monitoring_clean", _status_from_evidence(monitoring)))
    summary = monitoring.get("summary") if isinstance(monitoring.get("summary"), dict) else {}
    critical = int(summary.get("critical_incidents") or summary.get("open_critical_incidents") or 0)
    if monitoring and critical > 0:
        rows.append(_matrix_row_projection("publication-monitoring:public-release", "publication_monitoring", "no_open_critical_incidents", "blocked"))
    return sorted(rows, key=lambda item: (str(item.get("component_id") or ""), str(item.get("requirement") or "")))


def _expected_delivery_matrix_rows(delivery_evidence: ImplementationDocument) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    evidence_rows = [row for row in delivery_evidence.get("evidence", []) if isinstance(row, dict)]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in evidence_rows:
        by_type.setdefault(str(row.get("component_type") or ""), []).append(row)
    for spec in DELIVERY_VERIFICATION_COMPONENTS:
        component_type = str(spec["component_type"])
        requirement = str(spec["requirement"])
        typed = by_type.get(component_type, [])
        if not typed:
            continue
        for row in typed:
            rows.append(_matrix_row_projection(str(row.get("component_id") or component_type + ":missing"), component_type, requirement, _status_from_evidence(row)))
    return sorted(rows, key=lambda item: (str(item.get("component_id") or ""), str(item.get("requirement") or "")))


def _status_from_evidence(evidence: ImplementationDocument) -> str:
    if not evidence:
        return "missing"
    status = str(evidence.get("status") or "")
    if status == "passed":
        return "ready"
    if status == "failed":
        return "blocked"
    if status == "stale":
        return "stale"
    return "missing"


def _matrix_row_projection(component_id: str, component_type: str, requirement: str, status: str) -> ImplementationDocument:
    return {"component_id": component_id, "component_type": component_type, "requirement": requirement, "status": status}


def _matrix_projection(row: ImplementationDocument) -> ImplementationDocument:
    return {"component_id": row.get("component_id"), "component_type": row.get("component_type"), "requirement": row.get("requirement"), "status": row.get("status")}


def _readiness_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "row_count": len(rows),
        "ready_count": sum(1 for row in rows if row.get("status") == "ready"),
        "blocked_count": sum(1 for row in rows if row.get("status") == "blocked"),
        "warning_count": sum(1 for row in rows if row.get("status") == "warning"),
        "stale_count": sum(1 for row in rows if row.get("status") == "stale"),
        "missing_count": sum(1 for row in rows if row.get("status") in {"missing", "not_configured"}),
    }


def _combine_readiness_summaries(*summaries: ImplementationDocument) -> dict[str, int]:
    keys = ("row_count", "ready_count", "blocked_count", "warning_count", "stale_count", "missing_count")
    return {key: sum(int(summary.get(key) or 0) for summary in summaries if isinstance(summary, dict)) for key in keys}


def _expected_blockers(rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    blockers = []
    for row in rows:
        if row.get("status") not in {"blocked", "stale", "missing", "not_configured"} or row.get("severity") != "blocking":
            continue
        blockers.append(
            {
                "component_id": row.get("component_id"),
                "requirement": row.get("requirement"),
                "severity": "critical" if row.get("status") == "blocked" else "high",
                "source_check_id": row.get("source_check_id") or row.get("requirement"),
            }
        )
    return sorted(blockers, key=lambda item: (str(item.get("component_id")), str(item.get("requirement"))))


def _normalize_blockers(rows: list[Any]) -> list[ImplementationDocument]:
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append({"component_id": row.get("component_id"), "requirement": row.get("requirement"), "severity": row.get("severity"), "source_check_id": row.get("source_check_id")})
    return sorted(normalized, key=lambda item: (str(item.get("component_id")), str(item.get("requirement"))))


def _evidence_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {"evidence_count": len(rows), "failed_count": sum(1 for row in rows if row.get("status") == "failed"), "stale_count": sum(1 for row in rows if row.get("status") == "stale")}


def _verification_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {"verification_count": len(rows), "passed_count": sum(1 for row in rows if row.get("status") == "passed"), "failed_count": sum(1 for row in rows if row.get("status") == "failed")}


def _verification_from_evidence(row: ImplementationDocument) -> ImplementationDocument:
    return _strip_none(
        {
            "verification_id": row.get("evidence_id"),
            "component_type": row.get("component_type"),
            "status": row.get("status"),
            "verification_report_hash": row.get("verification_report_hash"),
            "package_zip_sha256": row.get("zip_sha256"),
            "manifest_hash": row.get("manifest_hash"),
            "required_by": [_requirement_for_component(str(row.get("component_type") or ""))],
        }
    )


def _requirement_for_component(component_type: str) -> str:
    return {"public_trust_center_verification": "public_trust_center_verified", "publication_monitoring_verification": "publication_monitoring_clean"}.get(component_type, component_type)


def _evidence_by_type(evidence: ImplementationDocument, component_type: str) -> ImplementationDocument:
    for row in evidence.get("evidence", []) if isinstance(evidence.get("evidence"), list) else []:
        if isinstance(row, dict) and row.get("component_type") == component_type:
            return row
    return {}


def _delivery_evidence_by_type(evidence: ImplementationDocument, component_type: str) -> ImplementationDocument:
    for row in evidence.get("evidence", []) if isinstance(evidence.get("evidence"), list) else []:
        if isinstance(row, dict) and row.get("component_type") == component_type:
            return row
    return {}


def _delivery_evidence_rows(evidence: ImplementationDocument, component_type: str) -> list[ImplementationDocument]:
    return [row for row in evidence.get("evidence", []) if isinstance(row, dict) and row.get("component_type") == component_type]


def _combine_paths(paths: list[Path | str] | tuple[Path | str, ...] | None, path: Path | str | None = None) -> list[Path]:
    combined: list[Path] = []
    seen: set[str] = set()
    for item in paths or []:
        if item:
            candidate = Path(item)
            key = str(candidate)
            if key not in seen:
                combined.append(candidate)
                seen.add(key)
    if path:
        candidate = Path(path)
        key = str(candidate)
        if key not in seen:
            combined.append(candidate)
    return combined


def _external_delivery_component_id(component_type: str, report: ImplementationDocument, index: int) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    prefix = {
        "release_verification": "release",
        "distribution_verification": "distribution",
        "submission_verification": "submission",
        "submission_evidence_verification": "submission-evidence",
        "release_operations_verification": "release-operations",
    }.get(component_type, component_type)
    for key in ("release_id", "target_id", "submission_id", "evidence_id", "operations_id", "package_id"):
        value = report.get(key) or summary.get(key)
        if value:
            return f"{prefix}:{_safe_component_id(str(value))}"
    return f"{prefix}:{index:03d}"


def _safe_component_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip()).strip("-")
    return cleaned or "unknown"


def _check_safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")
    return cleaned or "unknown"


def _source_publication_states(source_state: ImplementationDocument) -> list[ImplementationDocument]:
    sources = source_state.get("sources") if isinstance(source_state.get("sources"), dict) else {}
    return [row for row in sources.get("publication_channel_states", []) if isinstance(row, dict)]


def _strip_none(payload: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in payload.items() if value is not None}


def _read_json_file(path: Path) -> ImplementationDocument:
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _is_forbidden_entry(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".musicforge/") or "/.musicforge/" in lowered


def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".txt", ".md", ".csv", ".html", ".jsonl"))


def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    lowered = text.lower()
    extra_markers = ("github" + "key", "x-access" + "-token", "github" + "_pat_")
    return any(marker in lowered for marker in extra_markers)


def _walk_json_values(value: Any, prefix: str = "$") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_walk_json_values(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_json_values(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        rows.append((prefix, value))
    return rows


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
