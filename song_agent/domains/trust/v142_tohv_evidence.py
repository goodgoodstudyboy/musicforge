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

MAX_TEXT_SCAN_BYTES = _make_deferred_global('MAX_TEXT_SCAN_BYTES')
VERIFIER_BLOCKED_KEYS = _make_deferred_global('VERIFIER_BLOCKED_KEYS')
_contains_sensitive_text = _make_deferred_global('_contains_sensitive_text')
_fs_path = _make_deferred_global('_fs_path')
_is_text_scan_entry = _make_deferred_global('_is_text_scan_entry')
_read_json_file = _make_deferred_global('_read_json_file')
_read_zip_json = _make_deferred_global('_read_zip_json')
_sha256_file = _make_deferred_global('_sha256_file')
_walk_json_values = _make_deferred_global('_walk_json_values')
check = _make_deferred_global('check')
item = _make_deferred_global('item')
row = _make_deferred_global('row')
spec = _make_deferred_global('spec')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_TEXT_SCAN_BYTES, VERIFIER_BLOCKED_KEYS, _contains_sensitive_text, _fs_path, _is_text_scan_entry, _read_json_file, _read_zip_json
    global _sha256_file, _walk_json_values, check, item, row, spec
    MAX_TEXT_SCAN_BYTES = namespace.get('MAX_TEXT_SCAN_BYTES', MAX_TEXT_SCAN_BYTES)
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _contains_sensitive_text = namespace.get('_contains_sensitive_text', _contains_sensitive_text)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _is_text_scan_entry = namespace.get('_is_text_scan_entry', _is_text_scan_entry)
    _read_json_file = namespace.get('_read_json_file', _read_json_file)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _walk_json_values = namespace.get('_walk_json_values', _walk_json_values)
    check = namespace.get('check', check)
    item = namespace.get('item', item)
    row = namespace.get('row', row)
    spec = namespace.get('spec', spec)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_HUB_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_hub_verification"
TRUST_OPERATIONS_HUB_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 64




class _HubVerifierEvidenceMixin:
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
        report_readiness = _as_document(self.report.get("readiness"))
        ready = self.report.get("status") == "ready" and report_readiness.get("blocked_count") == 0 and report_readiness.get("stale_count") == 0 and report_readiness.get("missing_count") == 0
        self._add_check("requirements", "toh_require_ready", "passed" if ready or not self.require_ready else "failed", "blocking", "Hub is ready." if ready else "Hub is not ready.")
        signed = self.external_hub_signoff.get("status") == "signed"
        self._add_check("requirements", "toh_require_signed", "passed" if signed or not self.require_signed else "failed", "blocking", "Hub is signed." if signed else "Hub is not signed.")
        critical = int((_as_document(self.blockers_doc.get("summary"))).get("critical_count") or 0)
        self._add_check("requirements", "toh_require_no_critical_blockers", "passed" if critical == 0 or not self.require_no_critical_blockers else "failed", "blocking", "No critical Hub blockers." if critical == 0 else "Hub has critical blockers.")
        monitoring_row = next((row for row in self.matrix.get("rows", []) if isinstance(row, dict) and row.get("requirement") == "publication_monitoring_clean"), {})
        monitoring_ready = monitoring_row.get("status") == "ready"
        self._add_check("requirements", "toh_require_publication_monitoring_clean", "passed" if monitoring_ready or not self.require_publication_monitoring_clean else "failed", "blocking", "Publication monitoring is clean." if monitoring_ready else "Publication monitoring is not clean.")
        delivery_summary = _as_document(self.delivery_matrix.get("summary"))
        delivery_rows = _as_list(self.delivery_matrix.get("rows"))
        present_types = {str(row.get("component_type") or "") for row in delivery_rows if isinstance(row, dict)}
        expected_types = {str(spec["component_type"]) for spec in DELIVERY_VERIFICATION_COMPONENTS}
        delivery_ready = bool(delivery_rows) and expected_types.issubset(present_types) and delivery_summary.get("blocked_count") == 0 and delivery_summary.get("stale_count") == 0 and delivery_summary.get("missing_count") == 0
        self._add_check("requirements", "toh_require_delivery_ready", "passed" if delivery_ready or not self.require_delivery_ready else "failed", "blocking", "Delivery evidence is ready." if delivery_ready else "Delivery evidence is not ready.")
        incident_ready = self.external_incident_verification_report.get("status") == "passed"
        self._add_check("requirements", "toh_require_incident_closeout", "passed" if incident_ready or not self.require_incident_closeout else "failed", "blocking", "Incident closeout evidence is passed." if incident_ready else "Incident closeout evidence is missing or failed.")
        knowledge_summary = _as_document(self.external_incident_knowledge_verification_report.get("summary"))
        knowledge_ready = self.external_incident_knowledge_verification_report.get("status") == "passed" and int(knowledge_summary.get("guards_passed_count") or 0) > 0 and int(knowledge_summary.get("guard_failed_count") or 0) == 0 and int(knowledge_summary.get("recurrence_count") or 0) == 0
        self._add_check("requirements", "toh_require_incident_regression_guards", "passed" if knowledge_ready or not self.require_incident_regression_guards else "failed", "blocking", "Incident regression guards are passed." if knowledge_ready else "Incident regression guard evidence is missing or failed.")
        controls_summary = _as_document(self.external_trust_control_verification_report.get("summary"))
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
        findings: list[DomainDocument] = []
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

    def _build_report(self) -> DomainDocument:
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

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> DomainDocument:
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

    def _add_hash_check(self, scope: str, check_id: str, actual: object, expected: object, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: object, expected: object, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})
