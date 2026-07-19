# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_contracts import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES as HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HUB_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION as TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash as hub_hash, hub_manifest_hash as hub_manifest_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

_check_safe_id = _make_deferred_global('_check_safe_id')
_combine_readiness_summaries = _make_deferred_global('_combine_readiness_summaries')
_counts = _make_deferred_global('_counts')
_delivery_evidence_rows = _make_deferred_global('_delivery_evidence_rows')
_evidence_by_type = _make_deferred_global('_evidence_by_type')
_evidence_summary = _make_deferred_global('_evidence_summary')
_expected_blockers = _make_deferred_global('_expected_blockers')
_expected_delivery_matrix_rows = _make_deferred_global('_expected_delivery_matrix_rows')
_expected_matrix_rows = _make_deferred_global('_expected_matrix_rows')
_external_delivery_component_id = _make_deferred_global('_external_delivery_component_id')
_fs_path = _make_deferred_global('_fs_path')
_is_forbidden_entry = _make_deferred_global('_is_forbidden_entry')
_is_safe_entry = _make_deferred_global('_is_safe_entry')
_matrix_projection = _make_deferred_global('_matrix_projection')
_normalize_blockers = _make_deferred_global('_normalize_blockers')
_read_json_file = _make_deferred_global('_read_json_file')
_readiness_summary = _make_deferred_global('_readiness_summary')
_sha256_entry = _make_deferred_global('_sha256_entry')
_sha256_file = _make_deferred_global('_sha256_file')
_source_publication_states = _make_deferred_global('_source_publication_states')
_strip_none = _make_deferred_global('_strip_none')
_verification_from_evidence = _make_deferred_global('_verification_from_evidence')
_verification_summary = _make_deferred_global('_verification_summary')
count = _make_deferred_global('count')
name = _make_deferred_global('name')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global _check_safe_id, _combine_readiness_summaries, _counts, _delivery_evidence_rows, _evidence_by_type, _evidence_summary, _expected_blockers, _expected_delivery_matrix_rows
    global _expected_matrix_rows, _external_delivery_component_id, _fs_path, _is_forbidden_entry, _is_safe_entry, _matrix_projection, _normalize_blockers
    global _read_json_file, _readiness_summary, _sha256_entry, _sha256_file, _source_publication_states, _strip_none, _verification_from_evidence, _verification_summary
    global count, name, row
    _check_safe_id = namespace.get('_check_safe_id', _check_safe_id)
    _combine_readiness_summaries = namespace.get('_combine_readiness_summaries', _combine_readiness_summaries)
    _counts = namespace.get('_counts', _counts)
    _delivery_evidence_rows = namespace.get('_delivery_evidence_rows', _delivery_evidence_rows)
    _evidence_by_type = namespace.get('_evidence_by_type', _evidence_by_type)
    _evidence_summary = namespace.get('_evidence_summary', _evidence_summary)
    _expected_blockers = namespace.get('_expected_blockers', _expected_blockers)
    _expected_delivery_matrix_rows = namespace.get('_expected_delivery_matrix_rows', _expected_delivery_matrix_rows)
    _expected_matrix_rows = namespace.get('_expected_matrix_rows', _expected_matrix_rows)
    _external_delivery_component_id = namespace.get('_external_delivery_component_id', _external_delivery_component_id)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _is_forbidden_entry = namespace.get('_is_forbidden_entry', _is_forbidden_entry)
    _is_safe_entry = namespace.get('_is_safe_entry', _is_safe_entry)
    _matrix_projection = namespace.get('_matrix_projection', _matrix_projection)
    _normalize_blockers = namespace.get('_normalize_blockers', _normalize_blockers)
    _read_json_file = namespace.get('_read_json_file', _read_json_file)
    _readiness_summary = namespace.get('_readiness_summary', _readiness_summary)
    _sha256_entry = namespace.get('_sha256_entry', _sha256_entry)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _source_publication_states = namespace.get('_source_publication_states', _source_publication_states)
    _strip_none = namespace.get('_strip_none', _strip_none)
    _verification_from_evidence = namespace.get('_verification_from_evidence', _verification_from_evidence)
    _verification_summary = namespace.get('_verification_summary', _verification_summary)
    count = namespace.get('count', count)
    name = namespace.get('name', name)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_HUB_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_hub_verification"
TRUST_OPERATIONS_HUB_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 64




class _HubVerifierReadinessMixin:
    def run(self) -> DomainDocument:
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
        rows = _as_list(self.manifest.get("files"))
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
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
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
        source = _as_document(self.report.get("source"))
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
        manifest_source = _as_document(self.manifest.get("source"))
        manifest_expected = {"hub_report_hash": self.report.get("integrity_hash"), **expected_source, "signoff_summary_hash": self.signoff_summary.get("integrity_hash")}
        for key, value in manifest_expected.items():
            self._add_exact_check("manifest", "toh_manifest_source_" + key, manifest_source.get(key), value, f"Manifest source {key}")

    def _verify_checksums(self, archive: zipfile.ZipFile) -> None:
        rows = _as_list(self.checksum_json.get("files"))
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
        actual_blockers = _normalize_blockers(_as_list(self.blockers_doc.get("blockers")))
        self._add_exact_check("blockers", "toh_blocker_register_matches_readiness", actual_blockers, expected_blockers, "Blocker register matches blocking readiness rows")
        actions = _as_list(self.actions.get("actions"))
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
        delivery_actual_blockers = _normalize_blockers(_as_list(self.delivery_blockers.get("blockers")))
        self._add_exact_check("delivery", "toh_delivery_blockers_match_readiness", delivery_actual_blockers, delivery_expected_blockers, "Delivery blocker register matches delivery readiness")
        delivery_actions = _as_list(self.delivery_actions.get("actions"))
        delivery_action_ids = sorted(str(item.get("action_id") or "") for item in delivery_actions if isinstance(item, dict))
        delivery_expected_action_ids = sorted(str(item.get("manual_action_id") or "") for item in self.delivery_blockers.get("blockers", []) if isinstance(item, dict))
        self._add_exact_check("delivery", "toh_delivery_actions_match_blockers", delivery_action_ids, delivery_expected_action_ids, "Delivery manual actions match delivery blockers")
        combined_summary = _combine_readiness_summaries(expected_summary, delivery_expected_summary)
        expected_status = "ready" if combined_summary.get("blocked_count") == 0 and combined_summary.get("stale_count") == 0 and combined_summary.get("missing_count") == 0 and len(expected_blockers) == 0 and len(delivery_expected_blockers) == 0 else "blocked"
        self._add_exact_check("hub_report", "toh_report_status_matches_readiness", self.report.get("status"), expected_status, "Hub report status matches readiness")
        report_readiness = _as_document(self.report.get("readiness"))
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
            current = _as_document(self.external_channel_state.get("current_publication"))
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

    def _verify_external_report(self, component_type: str, report: DomainDocument, check_prefix: str) -> None:
        expected = _evidence_by_type(self.evidence, component_type)
        report_hash = verification_hash(report)
        status = "passed" if report and report_hash == expected.get("verification_report_hash") else "failed"
        self._add_check("external", check_prefix + "_hash", status, "blocking", f"External {component_type} report matches Hub evidence." if status == "passed" else f"External {component_type} report does not match Hub evidence.")
        self._add_exact_check("external", check_prefix + "_status", report.get("status"), expected.get("status"), f"External {component_type} status")
        if component_type == "publication_monitoring_verification":
            summary = _as_document(report.get("summary"))
            critical = int(summary.get("critical_incidents") or summary.get("open_critical_incidents") or 0)
            self._add_check("external", "toh_external_monitoring_no_open_critical_incidents", "passed" if critical == 0 else "failed", "blocking", "External monitoring report has no open critical incidents." if critical == 0 else "External monitoring report has open critical incidents.")

    def _verify_external_delivery_reports(self, component_type: str, expected_rows: list[DomainDocument], reports: list[DomainDocument], check_prefix: str) -> None:
        expected_by_id = {str(row.get("component_id") or ""): row for row in expected_rows if str(row.get("component_id") or "")}
        report_by_id: dict[str, DomainDocument] = {}
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

    def _verify_external_signoff(self, signoff: DomainDocument) -> None:
        self._add_exact_check("external", "toh_hub_signoff_package_type", signoff.get("package_type"), TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, "Hub signoff package_type")
        self._add_exact_check("external", "toh_hub_signoff_status", signoff.get("status"), "signed", "Hub signoff status")
        self._add_hash_check("external", "toh_hub_signoff_integrity", signoff.get("integrity_hash"), hub_hash(signoff), "Hub signoff integrity")
        source = _as_document(signoff.get("source"))
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
            summary = _as_document(report.get("summary"))
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
        summary = _as_document(knowledge_report.get("summary"))
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
        summary = _as_document(report.get("summary"))
        self._add_check("external", "toh_trust_control_required_controls_passed", "passed" if int(summary.get("required_failed_count") or 0) == 0 else "failed", "blocking", "Trust control policy passed." if int(summary.get("required_failed_count") or 0) == 0 else "Trust control policy has failed required controls.")
