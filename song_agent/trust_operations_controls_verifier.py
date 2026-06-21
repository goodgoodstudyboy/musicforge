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

from song_agent.projectio import write_json
from song_agent.public_trust_center_publication_monitoring import verification_hash
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash
from song_agent.trust_operations_controls import (
    BASELINE_CONTROLS,
    CONTROL_EXPORT_ENTRIES,
    TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE,
    TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
    _blocker_summary,
    _blockers_from_results,
    _catalog_summary,
    _evaluate_control,
    _manual_actions_from_blockers,
    _results_summary,
    control_hash,
    control_manifest_hash,
)
from song_agent.trust_operations_hub import hub_manifest_hash
from song_agent.trust_operations_hub_incidents import incident_hash, incident_manifest_hash
from song_agent.trust_operations_incident_knowledge import _classify_incident, knowledge_hash, knowledge_manifest_hash


TRUST_OPERATIONS_CONTROL_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_control_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


def verify_trust_operations_control_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_policy_passed: bool = False,
    hub_package_path: Path | str | None = None,
    hub_verification_report_path: Path | str | None = None,
    incident_board_package_path: Path | str | None = None,
    incident_board_verification_report_path: Path | str | None = None,
    incident_knowledge_package_path: Path | str | None = None,
    incident_knowledge_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _ControlVerifier(
        Path(zip_path),
        strict=strict,
        require_policy_passed=require_policy_passed,
        hub_package_path=Path(hub_package_path) if hub_package_path else None,
        hub_verification_report_path=Path(hub_verification_report_path) if hub_verification_report_path else None,
        incident_board_package_path=Path(incident_board_package_path) if incident_board_package_path else None,
        incident_board_verification_report_path=Path(incident_board_verification_report_path) if incident_board_verification_report_path else None,
        incident_knowledge_package_path=Path(incident_knowledge_package_path) if incident_knowledge_package_path else None,
        incident_knowledge_verification_report_path=Path(incident_knowledge_verification_report_path) if incident_knowledge_verification_report_path else None,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_control_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_control_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Trust Operations Control verification")
    print(f"status: {report.get('status')}")
    print(f"hub: {summary.get('hub_id') or '-'}")
    print(f"controls: {summary.get('control_count') or 0}")
    print(f"required failed: {summary.get('required_failed_count') or 0}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")


def trust_operations_control_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _ControlVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_policy_passed: bool,
        hub_package_path: Path | None,
        hub_verification_report_path: Path | None,
        incident_board_package_path: Path | None,
        incident_board_verification_report_path: Path | None,
        incident_knowledge_package_path: Path | None,
        incident_knowledge_verification_report_path: Path | None,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_policy_passed = require_policy_passed
        self.hub_package_path = hub_package_path
        self.hub_verification_report_path = hub_verification_report_path
        self.incident_board_package_path = incident_board_package_path
        self.incident_board_verification_report_path = incident_board_verification_report_path
        self.incident_knowledge_package_path = incident_knowledge_package_path
        self.incident_knowledge_verification_report_path = incident_knowledge_verification_report_path
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.manifest: dict[str, Any] = {}
        self.catalog: dict[str, Any] = {}
        self.policy: dict[str, Any] = {}
        self.assessment: dict[str, Any] = {}
        self.results_doc: dict[str, Any] = {}
        self.bindings_doc: dict[str, Any] = {}
        self.blockers_doc: dict[str, Any] = {}
        self.actions_doc: dict[str, Any] = {}
        self.external_reports: dict[str, dict[str, Any]] = {}
        self.external_hub_manifest: dict[str, Any] = {}
        self.external_incident_manifest: dict[str, Any] = {}
        self.external_knowledge_manifest: dict[str, Any] = {}
        self.external_incidents_doc: dict[str, Any] = {}
        self.external_closeouts_doc: dict[str, Any] = {}
        self.external_knowledge_entries_doc: dict[str, Any] = {}
        self.external_knowledge_guards_doc: dict[str, Any] = {}
        self.external_knowledge_runs_doc: dict[str, Any] = {}
        self.redaction_findings: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._read_external_sources()
                self._verify_semantics()
                self._verify_external_bindings()
                self._verify_external_knowledge_semantics()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not os.path.isfile(_fs_path(self.zip_path)) or os.path.islink(_fs_path(self.zip_path)):
            self._add_check("zip", "tohc_zip_open", "failed", "blocking", "Control ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = os.stat(_fs_path(self.zip_path)).st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        self._add_check("zip", "tohc_zip_size_limit", "passed" if self.zip_size_bytes <= self.max_zip_size_mb * 1024 * 1024 else "failed", "blocking", "Control ZIP compressed size is within limit.")
        try:
            archive = zipfile.ZipFile(_fs_path(self.zip_path), "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "tohc_zip_open", "failed", "blocking", f"Control ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "tohc_zip_open", "passed", "blocking", "Control ZIP can be opened.")
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
        self._add_check("zip", "tohc_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "Control ZIP uncompressed size is within limit.")
        self._add_check("zip", "tohc_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "Control ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "tohc_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "tohc_zip_no_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "tohc_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip"))
        self._add_check("zip", "tohc_zip_no_nested_zip", "failed" if nested else "passed", "blocking", "Nested ZIP entries are not allowed." if nested else "No nested ZIP entries are present.")
        missing = sorted(CONTROL_EXPORT_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - CONTROL_EXPORT_ENTRIES)
        self._add_check("zip", "tohc_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Control entries: " + ", ".join(missing[:8]) if missing else "All required Control entries exist.")
        self._add_check("zip", "tohc_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Control entries: " + ", ".join(unexpected[:8]) if unexpected else "Control ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-controls-manifest.json", "manifest", "tohc_manifest_parse")
        self.catalog = self._read_json_entry(archive, "control-catalog.json", "catalog", "tohc_catalog_parse")
        self.policy = self._read_json_entry(archive, "policy-bundle.json", "policy", "tohc_policy_parse")
        self.assessment = self._read_json_entry(archive, "control-assessment-report.json", "assessment", "tohc_assessment_parse")
        self.results_doc = self._read_json_entry(archive, "control-results.json", "results", "tohc_results_parse")
        self.bindings_doc = self._read_json_entry(archive, "evidence-bindings.json", "bindings", "tohc_bindings_parse")
        self.blockers_doc = self._read_json_entry(archive, "blocker-summary.json", "blockers", "tohc_blockers_parse")
        self.actions_doc = self._read_json_entry(archive, "manual-actions.json", "actions", "tohc_actions_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "tohc_manifest_integrity", self.manifest.get("integrity_hash"), control_manifest_hash(self.manifest), "Control manifest integrity")
        self._add_exact_check("manifest", "tohc_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE, "Control manifest package_type")
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "tohc_manifest_files_match_entries", sorted(manifest_paths), sorted(CONTROL_EXPORT_ENTRIES - {"trust-operations-controls-manifest.json"}), "Manifest file list matches fixed Control structure")
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
        self._add_check("manifest", "tohc_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in ((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else []) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "tohc_manifest_zip_summary", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files." if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        docs = {
            "catalog": (self.catalog, TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE),
            "policy": (self.policy, TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE),
            "assessment": (self.assessment, TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE),
            "results": (self.results_doc, TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE),
            "bindings": (self.bindings_doc, TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE),
            "blockers": (self.blockers_doc, TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE),
            "actions": (self.actions_doc, TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE),
        }
        for label, (doc, package_type) in docs.items():
            self._add_hash_check(label, f"tohc_{label}_integrity", doc.get("integrity_hash"), control_hash(doc), f"{label} integrity")
            self._add_exact_check(label, f"tohc_{label}_package_type", doc.get("package_type"), package_type, f"{label} package_type")
        source = self.manifest.get("source") if isinstance(self.manifest.get("source"), dict) else {}
        expected_source = {
            "catalog_hash": self.catalog.get("integrity_hash"),
            "policy_hash": self.policy.get("integrity_hash"),
            "assessment_hash": self.assessment.get("integrity_hash"),
            "control_results_hash": self.results_doc.get("integrity_hash"),
            "evidence_bindings_hash": self.bindings_doc.get("integrity_hash"),
            "blocker_summary_hash": self.blockers_doc.get("integrity_hash"),
            "manual_actions_hash": self.actions_doc.get("integrity_hash"),
        }
        for key, value in expected_source.items():
            self._add_exact_check("manifest", "tohc_manifest_source_" + key, source.get(key), value, f"Manifest source {key}")
        report_source = self.assessment.get("source") if isinstance(self.assessment.get("source"), dict) else {}
        self._add_exact_check("assessment", "tohc_assessment_results_hash", report_source.get("control_results_hash"), self.results_doc.get("integrity_hash"), "Assessment results hash")
        self._add_exact_check("assessment", "tohc_assessment_bindings_hash", report_source.get("evidence_bindings_hash"), self.bindings_doc.get("integrity_hash"), "Assessment evidence bindings hash")
        self._add_exact_check("assessment", "tohc_assessment_blockers_hash", report_source.get("blocker_summary_hash"), self.blockers_doc.get("integrity_hash"), "Assessment blocker summary hash")
        self._add_exact_check("assessment", "tohc_assessment_actions_hash", report_source.get("manual_actions_hash"), self.actions_doc.get("integrity_hash"), "Assessment manual actions hash")

    def _read_external_sources(self) -> None:
        specs = {
            "hub": (self.hub_package_path, self.hub_verification_report_path),
            "incident": (self.incident_board_package_path, self.incident_board_verification_report_path),
            "knowledge": (self.incident_knowledge_package_path, self.incident_knowledge_verification_report_path),
        }
        for kind, (package_path, report_path) in specs.items():
            if report_path:
                self.external_reports[kind] = _read_json_file(report_path)
            elif self.require_policy_passed:
                self._add_check("external", f"tohc_{kind}_verification_required", "failed", "blocking", f"Control verification requires external {kind} verification report.")
            if package_path:
                self._read_external_package(kind, package_path)
            elif self.require_policy_passed:
                self._add_check("external", f"tohc_{kind}_package_required", "failed", "blocking", f"Control verification requires external {kind} package.")

    def _read_external_package(self, kind: str, package_path: Path) -> None:
        if not package_path.exists() or not package_path.is_file():
            self._add_check("external", f"tohc_{kind}_package_open", "failed", "blocking", f"External {kind} package does not exist.")
            return
        try:
            with zipfile.ZipFile(_fs_path(package_path), "r") as archive:
                if kind == "hub":
                    self.external_hub_manifest = self._read_external_json_entry(archive, "trust-operations-hub-manifest.json")
                elif kind == "incident":
                    self.external_incident_manifest = self._read_external_json_entry(archive, "trust-operations-incident-manifest.json")
                    self.external_incidents_doc = self._read_external_json_entry(archive, "incidents.json")
                    self.external_closeouts_doc = self._read_external_json_entry(archive, "closeout-summary.json")
                elif kind == "knowledge":
                    self.external_knowledge_manifest = self._read_external_json_entry(archive, "trust-operations-knowledge-manifest.json")
                    self.external_knowledge_entries_doc = self._read_external_json_entry(archive, "entries.json")
                    self.external_knowledge_guards_doc = self._read_external_json_entry(archive, "regression-guards.json")
                    self.external_knowledge_runs_doc = self._read_external_json_entry(archive, "guard-run-summary.json")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("external", f"tohc_{kind}_package_open", "failed", "blocking", f"External {kind} package cannot be opened: {exc}")
            return
        self._add_check("external", f"tohc_{kind}_package_open", "passed", "blocking", f"External {kind} package can be opened.")
        if kind == "hub":
            self._add_hash_check("external", "tohc_hub_manifest_integrity", self.external_hub_manifest.get("integrity_hash"), hub_manifest_hash(self.external_hub_manifest), "Hub manifest integrity")
        elif kind == "incident":
            self._add_hash_check("external", "tohc_incident_manifest_integrity", self.external_incident_manifest.get("integrity_hash"), incident_manifest_hash(self.external_incident_manifest), "Incident manifest integrity")
            self._add_hash_check("external", "tohc_incident_incidents_integrity", self.external_incidents_doc.get("integrity_hash"), incident_hash(self.external_incidents_doc), "Incident incidents integrity")
            self._add_hash_check("external", "tohc_incident_closeouts_integrity", self.external_closeouts_doc.get("integrity_hash"), incident_hash(self.external_closeouts_doc), "Incident closeout integrity")
        elif kind == "knowledge":
            self._add_hash_check("external", "tohc_knowledge_manifest_integrity", self.external_knowledge_manifest.get("integrity_hash"), knowledge_manifest_hash(self.external_knowledge_manifest), "Knowledge manifest integrity")
            self._add_hash_check("external", "tohc_knowledge_entries_integrity", self.external_knowledge_entries_doc.get("integrity_hash"), knowledge_hash(self.external_knowledge_entries_doc), "Knowledge entries integrity")
            self._add_hash_check("external", "tohc_knowledge_guards_integrity", self.external_knowledge_guards_doc.get("integrity_hash"), knowledge_hash(self.external_knowledge_guards_doc), "Knowledge guards integrity")
            self._add_hash_check("external", "tohc_knowledge_runs_integrity", self.external_knowledge_runs_doc.get("integrity_hash"), knowledge_hash(self.external_knowledge_runs_doc), "Knowledge guard runs integrity")

    def _verify_semantics(self) -> None:
        controls = [item for item in self.catalog.get("controls", []) if isinstance(item, dict)]
        policy_ids = [str(item) for item in self.policy.get("control_ids", []) if item]
        controls_by_id = {str(item.get("control_id") or ""): item for item in controls}
        duplicate_policy = sorted(value for value, count in _counts(policy_ids).items() if count > 1)
        missing_controls = sorted(control_id for control_id in policy_ids if control_id not in controls_by_id)
        self._add_check("policy", "tohc_policy_no_duplicate_controls", "failed" if duplicate_policy else "passed", "blocking", "Duplicate policy controls: " + ", ".join(duplicate_policy[:5]) if duplicate_policy else "Policy has no duplicate controls.")
        self._add_check("policy", "tohc_policy_controls_exist", "failed" if missing_controls else "passed", "blocking", "Policy references missing controls: " + ", ".join(missing_controls[:5]) if missing_controls else "Policy controls exist in catalog.")
        bad_control_hashes = [str(item.get("control_id") or "") for item in controls if item.get("integrity_hash") != control_hash(item)]
        self._add_check("catalog", "tohc_control_integrity", "failed" if bad_control_hashes else "passed", "blocking", "Control integrity mismatch: " + ", ".join(bad_control_hashes[:5]) if bad_control_hashes else "All controls have valid integrity.")
        baseline_ids = {item["control_id"] for item in BASELINE_CONTROLS}
        present_baseline = {str(item.get("control_id") or "") for item in controls if item.get("source", {}).get("source_type") == "baseline"}
        self._add_exact_check("catalog", "tohc_baseline_controls_present", sorted(present_baseline), sorted(baseline_ids), "Baseline controls")
        baseline_mismatches = []
        baseline_by_id = {item["control_id"]: item for item in BASELINE_CONTROLS}
        for control in controls:
            if not isinstance(control, dict) or control.get("source", {}).get("source_type") != "baseline":
                continue
            spec = baseline_by_id.get(str(control.get("control_id") or ""))
            if not spec:
                continue
            if (
                control.get("title") != spec["title"]
                or control.get("category") != spec["category"]
                or control.get("severity") != spec["severity"]
                or control.get("evaluation", {}).get("method") != spec["evaluation_method"]
            ):
                baseline_mismatches.append(str(control.get("control_id") or "unknown"))
        self._add_check("catalog", "tohc_baseline_control_spec_binding", "failed" if baseline_mismatches else "passed", "blocking", "Baseline controls were modified: " + ", ".join(baseline_mismatches[:5]) if baseline_mismatches else "Baseline control specs match the built-in catalog.")
        expected_catalog_summary = _catalog_summary(controls)
        self._add_exact_check("catalog", "tohc_catalog_summary_matches_controls", self.catalog.get("summary"), expected_catalog_summary, "Catalog summary")
        required = {str(item.get("control_id") or ""): bool(item.get("required")) for item in self.policy.get("requirements", []) if isinstance(item, dict)}
        expected_results = [_evaluate_control(controls_by_id[control_id], self._assessment_external_source(), required=required.get(control_id, False)) for control_id in policy_ids if control_id in controls_by_id]
        actual_results = self.results_doc.get("results") if isinstance(self.results_doc.get("results"), list) else []
        self._add_exact_check("results", "tohc_control_results_semantics_match", _result_projection(actual_results), _result_projection(expected_results), "Control results match external evidence semantics")
        self._add_exact_check("results", "tohc_results_summary_matches_rows", self.results_doc.get("summary"), _results_summary(actual_results), "Control results summary")
        expected_blockers = _blockers_from_results(actual_results, required)
        actual_blockers = self.blockers_doc.get("blockers") if isinstance(self.blockers_doc.get("blockers"), list) else []
        self._add_exact_check("blockers", "tohc_blocker_summary_semantics_match", _blocker_projection(actual_blockers), _blocker_projection(expected_blockers), "Blocker summary matches required failed controls")
        self._add_exact_check("blockers", "tohc_blocker_summary_counts", self.blockers_doc.get("summary"), _blocker_summary(actual_blockers), "Blocker summary counts")
        expected_actions = _manual_actions_from_blockers(actual_blockers)
        actual_actions = self.actions_doc.get("actions") if isinstance(self.actions_doc.get("actions"), list) else []
        self._add_exact_check("actions", "tohc_manual_actions_match_blockers", _action_projection(actual_actions), _action_projection(expected_actions), "Manual actions match blockers")
        expected_status = "passed" if not actual_blockers else "failed"
        self._add_exact_check("assessment", "tohc_assessment_status_matches_blockers", self.assessment.get("status"), expected_status, "Assessment status")
        self._add_exact_check("assessment", "tohc_assessment_summary_matches_results", {key: self.assessment.get("summary", {}).get(key) for key in ("result_count", "passed_count", "failed_count", "required_failed_count", "blocker_count", "manual_action_count")}, {**_results_summary(actual_results), "blocker_count": len(actual_blockers), "manual_action_count": len(actual_actions)}, "Assessment summary")

    def _assessment_external_source(self) -> dict[str, Any]:
        source = dict(self.assessment.get("source") if isinstance(self.assessment.get("source"), dict) else {})
        for kind, report in self.external_reports.items():
            if report:
                source[f"{kind}_verification_status"] = report.get("status")
                source[f"{kind}_verification_report_hash"] = verification_hash(report)
                source[f"{kind}_zip_sha256"] = report.get("zip_sha256")
                source[f"{kind}_zip_size_bytes"] = report.get("zip_size_bytes")
                source[f"{kind}_manifest_hash"] = report.get("manifest_hash")
                source[f"{kind}_source_hash"] = report.get("source_hash")
                source[f"{kind}_summary"] = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        return source

    def _verify_external_bindings(self) -> None:
        source = self.assessment.get("source") if isinstance(self.assessment.get("source"), dict) else {}
        bindings = {str(item.get("evidence_type") or ""): item for item in self.bindings_doc.get("bindings", []) if isinstance(item, dict)}
        for kind, report in self.external_reports.items():
            if not report:
                continue
            binding = bindings.get(f"{kind}_verification") or {}
            self._add_exact_check("external", f"tohc_{kind}_verification_status", report.get("status"), source.get(f"{kind}_verification_status"), f"{kind} verification status")
            self._add_exact_check("external", f"tohc_{kind}_verification_hash", verification_hash(report), source.get(f"{kind}_verification_report_hash"), f"{kind} verification hash")
            self._add_exact_check("external", f"tohc_{kind}_binding_report_hash", binding.get("verification_report_hash"), verification_hash(report), f"{kind} binding verification hash")
            self._add_exact_check("external", f"tohc_{kind}_binding_zip_sha256", binding.get("zip_sha256"), report.get("zip_sha256"), f"{kind} binding ZIP sha256")
            self._add_exact_check("external", f"tohc_{kind}_binding_manifest_hash", binding.get("manifest_hash"), report.get("manifest_hash"), f"{kind} binding manifest hash")
        if self.hub_package_path and self.external_reports.get("hub"):
            self._add_exact_check("external", "tohc_hub_package_zip_sha256", _sha256_file(self.hub_package_path), self.external_reports["hub"].get("zip_sha256"), "Hub package ZIP sha256")
            self._add_exact_check("external", "tohc_hub_package_zip_size_bytes", os.stat(_fs_path(self.hub_package_path)).st_size, self.external_reports["hub"].get("zip_size_bytes"), "Hub package ZIP size")
            self._add_exact_check("external", "tohc_hub_package_manifest_hash", self.external_hub_manifest.get("integrity_hash"), self.external_reports["hub"].get("manifest_hash"), "Hub package manifest hash")
        if self.incident_board_package_path and self.external_reports.get("incident"):
            self._add_exact_check("external", "tohc_incident_package_zip_sha256", _sha256_file(self.incident_board_package_path), self.external_reports["incident"].get("zip_sha256"), "Incident package ZIP sha256")
            self._add_exact_check("external", "tohc_incident_package_zip_size_bytes", os.stat(_fs_path(self.incident_board_package_path)).st_size, self.external_reports["incident"].get("zip_size_bytes"), "Incident package ZIP size")
            self._add_exact_check("external", "tohc_incident_package_manifest_hash", self.external_incident_manifest.get("integrity_hash"), self.external_reports["incident"].get("manifest_hash"), "Incident package manifest hash")
        if self.incident_knowledge_package_path and self.external_reports.get("knowledge"):
            self._add_exact_check("external", "tohc_knowledge_package_zip_sha256", _sha256_file(self.incident_knowledge_package_path), self.external_reports["knowledge"].get("zip_sha256"), "Knowledge package ZIP sha256")
            self._add_exact_check("external", "tohc_knowledge_package_zip_size_bytes", os.stat(_fs_path(self.incident_knowledge_package_path)).st_size, self.external_reports["knowledge"].get("zip_size_bytes"), "Knowledge package ZIP size")
            self._add_exact_check("external", "tohc_knowledge_package_manifest_hash", self.external_knowledge_manifest.get("integrity_hash"), self.external_reports["knowledge"].get("manifest_hash"), "Knowledge package manifest hash")

    def _verify_external_knowledge_semantics(self) -> None:
        if not self.external_knowledge_entries_doc or not self.external_incidents_doc:
            return
        facts = self._external_incident_facts()
        external_entries = {str(entry.get("integrity_hash") or ""): entry for entry in self.external_knowledge_entries_doc.get("entries", []) if isinstance(entry, dict)}
        external_guards = self.external_knowledge_guards_doc.get("guards") if isinstance(self.external_knowledge_guards_doc.get("guards"), list) else []
        guard_by_entry_hash = {str(guard.get("source", {}).get("knowledge_entry_hash") or ""): guard for guard in external_guards if isinstance(guard, dict) and guard.get("status") not in {"archived", "manual_required"}}
        mismatches: list[str] = []
        missing_controls: list[str] = []
        for control in self.catalog.get("controls", []) if isinstance(self.catalog.get("controls"), list) else []:
            if not isinstance(control, dict) or control.get("source", {}).get("source_type") != "knowledge_entry":
                continue
            source = control.get("source") if isinstance(control.get("source"), dict) else {}
            entry_hash = str(source.get("knowledge_entry_hash") or "")
            entry = external_entries.get(entry_hash)
            fact = facts.get(str(source.get("incident_hash") or ""))
            if not entry or not fact:
                missing_controls.append(str(control.get("control_id") or entry_hash))
                continue
            if not _control_matches_external_entry(control, entry, fact, guard_by_entry_hash.get(entry_hash), self.external_reports.get("knowledge", {}), self.external_reports.get("incident", {})):
                mismatches.append(str(control.get("control_id") or entry_hash))
        self._add_check("external", "tohc_knowledge_derived_controls_backed_by_entries", "failed" if missing_controls else "passed", "blocking", "Derived controls missing external Knowledge entries: " + ", ".join(missing_controls[:5]) if missing_controls else "Derived controls are backed by external Knowledge entries.")
        self._add_check("external", "tohc_knowledge_derived_control_fact_binding", "failed" if mismatches else "passed", "blocking", "Derived controls do not match external Knowledge facts: " + ", ".join(mismatches[:5]) if mismatches else "Derived controls match external Knowledge and Incident facts.")
        high_missing: list[str] = []
        control_by_entry_hash = {str(control.get("source", {}).get("knowledge_entry_hash") or ""): control for control in self.catalog.get("controls", []) if isinstance(control, dict) and control.get("source", {}).get("source_type") == "knowledge_entry"}
        for entry_hash, entry in external_entries.items():
            if entry.get("status") == "hidden" or entry.get("severity") not in {"critical", "high"}:
                continue
            if entry_hash not in control_by_entry_hash:
                high_missing.append(str(entry.get("entry_id") or entry_hash))
        self._add_check("external", "tohc_external_high_knowledge_control_coverage", "failed" if high_missing else "passed", "blocking", "External high Knowledge entries missing controls: " + ", ".join(high_missing[:5]) if high_missing else "External high Knowledge entries have derived controls.")

    def _external_incident_facts(self) -> dict[str, dict[str, Any]]:
        incidents = self.external_incidents_doc.get("incidents") if isinstance(self.external_incidents_doc.get("incidents"), list) else []
        closeouts = self.external_closeouts_doc.get("closeouts") if isinstance(self.external_closeouts_doc.get("closeouts"), list) else []
        closeout_by_id = {str(closeout.get("incident_id") or ""): closeout for closeout in closeouts if isinstance(closeout, dict)}
        facts: dict[str, dict[str, Any]] = {}
        for incident in incidents:
            if not isinstance(incident, dict) or incident.get("status") != "closed" or incident.get("stale"):
                continue
            incident_integrity = str(incident.get("integrity_hash") or "")
            if not incident_integrity or incident_integrity != incident_hash(incident):
                continue
            incident_id = str(incident.get("incident_id") or "")
            closeout = closeout_by_id.get(incident_id) or {}
            closeout_hash = str(closeout.get("integrity_hash") or "")
            if closeout.get("status") != "passed" or closeout_hash != incident_hash(closeout):
                continue
            detected = incident.get("detected_from") if isinstance(incident.get("detected_from"), dict) else {}
            classification = _classify_incident(incident)
            facts[incident_integrity] = {
                "incident_id": incident_id,
                "severity": incident.get("severity"),
                "category": incident.get("category"),
                "component_type": detected.get("component_type"),
                "component_id": detected.get("component_id"),
                "source_fingerprint": detected.get("source_fingerprint"),
                "closeout_hash": closeout_hash,
                "failure_mode": classification["failure_mode"],
                "root_cause": classification["root_cause"],
                "recommended_guard": {"guard_type": classification["guard_type"], "title": classification["guard_title"], "reason": classification["guard_reason"]},
            }
        return facts

    def _verify_requirements(self) -> None:
        required_failed = int((self.results_doc.get("summary") if isinstance(self.results_doc.get("summary"), dict) else {}).get("required_failed_count") or 0)
        assessment_passed = self.assessment.get("status") == "passed"
        self._add_check("requirements", "tohc_require_policy_passed", "passed" if (not self.require_policy_passed or (required_failed == 0 and assessment_passed)) else "failed", "blocking", "Control policy assessment passed." if required_failed == 0 and assessment_passed else "Required controls failed.")

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
            "catalog": self.catalog,
            "policy": self.policy,
            "assessment": self.assessment,
            "results": self.results_doc,
            "bindings": self.bindings_doc,
            "blockers": self.blockers_doc,
            "actions": self.actions_doc,
        }.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "tohc_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Control package." if findings else "No sensitive values found in Control package.")

    def _build_report(self) -> dict[str, Any]:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        source = self.assessment.get("source") if isinstance(self.assessment.get("source"), dict) else {}
        summary = {
            "hub_id": self.assessment.get("hub_id"),
            "assessment_id": self.assessment.get("assessment_id"),
            "policy_id": self.assessment.get("policy_id"),
            "control_count": int((self.catalog.get("summary") if isinstance(self.catalog.get("summary"), dict) else {}).get("control_count") or 0),
            "required_failed_count": int((self.results_doc.get("summary") if isinstance(self.results_doc.get("summary"), dict) else {}).get("required_failed_count") or 0),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": self.assessment.get("integrity_hash"),
                "hub_verification_report_hash": source.get("hub_verification_report_hash"),
                "hub_zip_sha256": source.get("hub_zip_sha256"),
                "hub_zip_size_bytes": source.get("hub_zip_size_bytes"),
                "hub_manifest_hash": source.get("hub_manifest_hash"),
                "incident_verification_report_hash": source.get("incident_verification_report_hash"),
                "incident_zip_sha256": source.get("incident_zip_sha256"),
                "incident_zip_size_bytes": source.get("incident_zip_size_bytes"),
                "incident_manifest_hash": source.get("incident_manifest_hash"),
                "knowledge_verification_report_hash": source.get("knowledge_verification_report_hash"),
                "knowledge_zip_sha256": source.get("knowledge_zip_sha256"),
                "knowledge_zip_size_bytes": source.get("knowledge_zip_size_bytes"),
                "knowledge_manifest_hash": source.get("knowledge_manifest_hash"),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": summary,
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
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

    def _read_external_json_entry(self, archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
        try:
            value = json.loads(archive.read(name).decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _control_matches_external_entry(control: dict[str, Any], entry: dict[str, Any], fact: dict[str, Any], guard: dict[str, Any] | None, knowledge_report: dict[str, Any], incident_report: dict[str, Any]) -> bool:
    source = control.get("source") if isinstance(control.get("source"), dict) else {}
    scope = control.get("scope") if isinstance(control.get("scope"), dict) else {}
    recommended = entry.get("recommended_guard") if isinstance(entry.get("recommended_guard"), dict) else {}
    guard = guard or {}
    expected_source = {
        "source_type": "knowledge_entry",
        "knowledge_entry_id": entry.get("entry_id"),
        "knowledge_entry_hash": entry.get("integrity_hash"),
        "incident_id": entry.get("incident_id"),
        "incident_hash": entry.get("source", {}).get("incident_hash"),
        "closeout_hash": entry.get("source", {}).get("closeout_hash"),
        "source_fingerprint": entry.get("source", {}).get("source_fingerprint"),
        "knowledge_verification_report_hash": verification_hash(knowledge_report) if knowledge_report else source.get("knowledge_verification_report_hash"),
        "incident_verification_report_hash": verification_hash(incident_report) if incident_report else source.get("incident_verification_report_hash"),
        "guard_id": guard.get("guard_id"),
        "guard_hash": guard.get("integrity_hash"),
        "recommended_guard_type": recommended.get("guard_type"),
    }
    return (
        control.get("severity") == fact.get("severity")
        and control.get("category") == fact.get("category")
        and scope.get("component_type") == fact.get("component_type")
        and scope.get("component_id") == fact.get("component_id")
        and scope.get("failure_mode") == fact.get("failure_mode")
        and source == expected_source
        and control.get("source_hash") == stable_hash(expected_source)
        and control.get("evaluation", {}).get("method") == "knowledge_guard_coverage"
        and control.get("integrity_hash") == control_hash(control)
    )


def _result_projection(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"control_id": row.get("control_id"), "control_hash": row.get("control_hash"), "required": row.get("required"), "severity": row.get("severity"), "status": row.get("status"), "evaluation_method": row.get("evaluation_method")})
    return sorted(out, key=lambda item: str(item.get("control_id") or ""))


def _blocker_projection(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"control_id": row.get("control_id"), "severity": row.get("severity"), "source_result_hash": row.get("source_result_hash")})
    return sorted(out, key=lambda item: str(item.get("control_id") or ""))


def _action_projection(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"control_id": row.get("control_id"), "status": row.get("status"), "allowed_automation": row.get("allowed_automation")})
    return sorted(out, key=lambda item: str(item.get("control_id") or ""))


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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


def _raw_zip_entry_names(zip_path: Path) -> list[str]:
    try:
        data = Path(_fs_path(zip_path)).read_bytes()
    except OSError:
        return []
    names: list[str] = []
    offset = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, offset)
        if index < 0 or index + 46 > len(data):
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        names.append(data[start:end].decode("utf-8", errors="replace"))
        offset = end + extra_len + comment_len
    return names


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
    return any(marker in lowered for marker in ("github" + "key", "x-access" + "-token", "github" + "_pat_"))


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
