# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_controls_contracts import BASELINE_CONTROLS as BASELINE_CONTROLS, CONTROL_EXPORT_ENTRIES as CONTROL_EXPORT_ENTRIES, TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION as TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION, _blocker_summary as _blocker_summary, _blockers_from_results as _blockers_from_results, _catalog_summary as _catalog_summary, _evaluate_control as _evaluate_control, _manual_actions_from_blockers as _manual_actions_from_blockers, _results_summary as _results_summary, control_hash as control_hash, control_manifest_hash as control_manifest_hash
from song_agent.domains.trust.trust_operations_hub_contracts import hub_manifest_hash as hub_manifest_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash
from song_agent.domains.trust.trust_operations_incident_knowledge_contracts import _classify_incident as _classify_incident, knowledge_hash as knowledge_hash, knowledge_manifest_hash as knowledge_manifest_hash


TRUST_OPERATIONS_CONTROL_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_control_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


from song_agent.domains.trust import v142_tocv_readiness as _v142_tocv_readiness
from song_agent.domains.trust.v142_tocv_readiness import verify_trust_operations_control_package as verify_trust_operations_control_package, write_trust_operations_control_verification_report as write_trust_operations_control_verification_report, print_trust_operations_control_verification_report as print_trust_operations_control_verification_report, trust_operations_control_verification_exit_code as trust_operations_control_verification_exit_code, _control_matches_external_entry as _control_matches_external_entry, _result_projection as _result_projection, _blocker_projection as _blocker_projection, _action_projection as _action_projection, _read_json_file as _read_json_file, _sha256_entry as _sha256_entry, _sha256_file as _sha256_file, _counts as _counts, _is_safe_entry as _is_safe_entry, _is_forbidden_entry as _is_forbidden_entry, _is_text_scan_entry as _is_text_scan_entry, _contains_sensitive_text as _contains_sensitive_text, _walk_json_values as _walk_json_values, _fs_path as _fs_path









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
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.manifest: ImplementationDocument = {}
        self.catalog: ImplementationDocument = {}
        self.policy: ImplementationDocument = {}
        self.assessment: ImplementationDocument = {}
        self.results_doc: ImplementationDocument = {}
        self.bindings_doc: ImplementationDocument = {}
        self.blockers_doc: ImplementationDocument = {}
        self.actions_doc: ImplementationDocument = {}
        self.external_reports: dict[str, ImplementationDocument] = {}
        self.external_hub_manifest: ImplementationDocument = {}
        self.external_incident_manifest: ImplementationDocument = {}
        self.external_knowledge_manifest: ImplementationDocument = {}
        self.external_incidents_doc: ImplementationDocument = {}
        self.external_closeouts_doc: ImplementationDocument = {}
        self.external_knowledge_entries_doc: ImplementationDocument = {}
        self.external_knowledge_guards_doc: ImplementationDocument = {}
        self.external_knowledge_runs_doc: ImplementationDocument = {}
        self.redaction_findings: list[ImplementationDocument] = []

    def run(self) -> DomainDocument:
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
        rows = _as_list(self.manifest.get("files"))
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
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
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
        source = _as_document(self.manifest.get("source"))
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
        report_source = _as_document(self.assessment.get("source"))
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
        actual_results = _as_list(self.results_doc.get("results"))
        self._add_exact_check("results", "tohc_control_results_semantics_match", _result_projection(actual_results), _result_projection(expected_results), "Control results match external evidence semantics")
        self._add_exact_check("results", "tohc_results_summary_matches_rows", self.results_doc.get("summary"), _results_summary(actual_results), "Control results summary")
        expected_blockers = _blockers_from_results(actual_results, required)
        actual_blockers = _as_list(self.blockers_doc.get("blockers"))
        self._add_exact_check("blockers", "tohc_blocker_summary_semantics_match", _blocker_projection(actual_blockers), _blocker_projection(expected_blockers), "Blocker summary matches required failed controls")
        self._add_exact_check("blockers", "tohc_blocker_summary_counts", self.blockers_doc.get("summary"), _blocker_summary(actual_blockers), "Blocker summary counts")
        expected_actions = _manual_actions_from_blockers(actual_blockers)
        actual_actions = _as_list(self.actions_doc.get("actions"))
        self._add_exact_check("actions", "tohc_manual_actions_match_blockers", _action_projection(actual_actions), _action_projection(expected_actions), "Manual actions match blockers")
        expected_status = "passed" if not actual_blockers else "failed"
        self._add_exact_check("assessment", "tohc_assessment_status_matches_blockers", self.assessment.get("status"), expected_status, "Assessment status")
        self._add_exact_check("assessment", "tohc_assessment_summary_matches_results", {key: self.assessment.get("summary", {}).get(key) for key in ("result_count", "passed_count", "failed_count", "required_failed_count", "blocker_count", "manual_action_count")}, {**_results_summary(actual_results), "blocker_count": len(actual_blockers), "manual_action_count": len(actual_actions)}, "Assessment summary")

    def _assessment_external_source(self) -> ImplementationDocument:
        source = dict(_as_document(self.assessment.get("source")))
        for kind, report in self.external_reports.items():
            if report:
                source[f"{kind}_verification_status"] = report.get("status")
                source[f"{kind}_verification_report_hash"] = verification_hash(report)
                source[f"{kind}_zip_sha256"] = report.get("zip_sha256")
                source[f"{kind}_zip_size_bytes"] = report.get("zip_size_bytes")
                source[f"{kind}_manifest_hash"] = report.get("manifest_hash")
                source[f"{kind}_source_hash"] = report.get("source_hash")
                source[f"{kind}_summary"] = _as_document(report.get("summary"))
        return source

    def _verify_external_bindings(self) -> None:
        source = _as_document(self.assessment.get("source"))
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
        external_guards = _as_list(self.external_knowledge_guards_doc.get("guards"))
        guard_by_entry_hash = {str(guard.get("source", {}).get("knowledge_entry_hash") or ""): guard for guard in external_guards if isinstance(guard, dict) and guard.get("status") not in {"archived", "manual_required"}}
        mismatches: list[str] = []
        missing_controls: list[str] = []
        for control in self.catalog.get("controls", []) if isinstance(self.catalog.get("controls"), list) else []:
            if not isinstance(control, dict) or control.get("source", {}).get("source_type") != "knowledge_entry":
                continue
            source = _as_document(control.get("source"))
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

    def _external_incident_facts(self) -> dict[str, ImplementationDocument]:
        incidents = _as_list(self.external_incidents_doc.get("incidents"))
        closeouts = _as_list(self.external_closeouts_doc.get("closeouts"))
        closeout_by_id = {str(closeout.get("incident_id") or ""): closeout for closeout in closeouts if isinstance(closeout, dict)}
        facts: dict[str, ImplementationDocument] = {}
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
            detected = _as_document(incident.get("detected_from"))
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
        required_failed = int((_as_document(self.results_doc.get("summary"))).get("required_failed_count") or 0)
        assessment_passed = self.assessment.get("status") == "passed"
        self._add_check("requirements", "tohc_require_policy_passed", "passed" if (not self.require_policy_passed or (required_failed == 0 and assessment_passed)) else "failed", "blocking", "Control policy assessment passed." if required_failed == 0 and assessment_passed else "Required controls failed.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[ImplementationDocument] = []
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

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        source = _as_document(self.assessment.get("source"))
        summary = {
            "hub_id": self.assessment.get("hub_id"),
            "assessment_id": self.assessment.get("assessment_id"),
            "policy_id": self.assessment.get("policy_id"),
            "control_count": int((_as_document(self.catalog.get("summary"))).get("control_count") or 0),
            "required_failed_count": int((_as_document(self.results_doc.get("summary"))).get("required_failed_count") or 0),
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

    def _read_external_json_entry(self, archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
        try:
            value = json.loads(archive.read(name).decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return _as_document(value)

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})

_v142_tocv_readiness.bind_globals(globals())
