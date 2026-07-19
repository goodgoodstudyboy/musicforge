# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Callable as Callable
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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

HEX_SHA256 = _make_deferred_global('HEX_SHA256')
INLINE_EVENT_RE = _make_deferred_global('INLINE_EVENT_RE')
_contains_local_path = _make_deferred_global('_contains_local_path')
_counts = _make_deferred_global('_counts')
_delivery_payloads_from_data_docs = _make_deferred_global('_delivery_payloads_from_data_docs')
_delivery_payloads_from_fingerprint_sidecars = _make_deferred_global('_delivery_payloads_from_fingerprint_sidecars')
_delivery_readiness = _make_deferred_global('_delivery_readiness')
_delivery_risk_register = _make_deferred_global('_delivery_risk_register')
_delivery_verification_index_from_independent_sidecars = _make_deferred_global('_delivery_verification_index_from_independent_sidecars')
_is_forbidden_public_entry = _make_deferred_global('_is_forbidden_public_entry')
_normalize_newlines = _make_deferred_global('_normalize_newlines')
_package_index = _make_deferred_global('_package_index')
_package_verification_index_from_independent_sidecars = _make_deferred_global('_package_verification_index_from_independent_sidecars')
_packages_from_sidecars = _make_deferred_global('_packages_from_sidecars')
_portfolio_readiness = _make_deferred_global('_portfolio_readiness')
_release_readiness = _make_deferred_global('_release_readiness')
_sha256_entry = _make_deferred_global('_sha256_entry')
_sha256_file = _make_deferred_global('_sha256_file')
_sha256_text = _make_deferred_global('_sha256_text')
_summary_from_source = _make_deferred_global('_summary_from_source')
_verification_index = _make_deferred_global('_verification_index')
_verifications_from_sidecars = _make_deferred_global('_verifications_from_sidecars')
count = _make_deferred_global('count')

def bind_globals(namespace: dict[str, object]) -> None:
    global HEX_SHA256, INLINE_EVENT_RE, _contains_local_path, _counts, _delivery_payloads_from_data_docs, _delivery_payloads_from_fingerprint_sidecars, _delivery_readiness, _delivery_risk_register
    global _delivery_verification_index_from_independent_sidecars, _is_forbidden_public_entry, _normalize_newlines, _package_index, _package_verification_index_from_independent_sidecars, _packages_from_sidecars, _portfolio_readiness
    global _release_readiness, _sha256_entry, _sha256_file, _sha256_text, _summary_from_source, _verification_index, _verifications_from_sidecars, count
    HEX_SHA256 = namespace.get('HEX_SHA256', HEX_SHA256)
    INLINE_EVENT_RE = namespace.get('INLINE_EVENT_RE', INLINE_EVENT_RE)
    _contains_local_path = namespace.get('_contains_local_path', _contains_local_path)
    _counts = namespace.get('_counts', _counts)
    _delivery_payloads_from_data_docs = namespace.get('_delivery_payloads_from_data_docs', _delivery_payloads_from_data_docs)
    _delivery_payloads_from_fingerprint_sidecars = namespace.get('_delivery_payloads_from_fingerprint_sidecars', _delivery_payloads_from_fingerprint_sidecars)
    _delivery_readiness = namespace.get('_delivery_readiness', _delivery_readiness)
    _delivery_risk_register = namespace.get('_delivery_risk_register', _delivery_risk_register)
    _delivery_verification_index_from_independent_sidecars = namespace.get('_delivery_verification_index_from_independent_sidecars', _delivery_verification_index_from_independent_sidecars)
    _is_forbidden_public_entry = namespace.get('_is_forbidden_public_entry', _is_forbidden_public_entry)
    _normalize_newlines = namespace.get('_normalize_newlines', _normalize_newlines)
    _package_index = namespace.get('_package_index', _package_index)
    _package_verification_index_from_independent_sidecars = namespace.get('_package_verification_index_from_independent_sidecars', _package_verification_index_from_independent_sidecars)
    _packages_from_sidecars = namespace.get('_packages_from_sidecars', _packages_from_sidecars)
    _portfolio_readiness = namespace.get('_portfolio_readiness', _portfolio_readiness)
    _release_readiness = namespace.get('_release_readiness', _release_readiness)
    _sha256_entry = namespace.get('_sha256_entry', _sha256_entry)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _sha256_text = namespace.get('_sha256_text', _sha256_text)
    _summary_from_source = namespace.get('_summary_from_source', _summary_from_source)
    _verification_index = namespace.get('_verification_index', _verification_index)
    _verifications_from_sidecars = namespace.get('_verifications_from_sidecars', _verifications_from_sidecars)
    count = namespace.get('count', count)
    _bind_deferred_defaults(namespace)


PTC_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 250
REQUIRED_ENTRIES = {
    "trust-center-manifest.json",
    "trust-center-report.json",
    "data/trust-center-data.json",
    "data/release-index.json",
    "data/portfolio-index.json",
    "data/package-index.json",
    "data/verification-index.json",
    "data/public-package-verification-index.json",
    "data/risk-register.json",
    "data/transparency-index.json",
    "data/acknowledgement-index.json",
    "data/delivery-index.json",
    "data/distribution-index.json",
    "data/submission-index.json",
    "data/submission-evidence-index.json",
    "data/operations-index.json",
    "data/operations-package-index.json",
    "data/readiness-matrix.json",
    "data/delivery-risk-register.json",
    "data/delivery-verification-index.json",
    "index.html",
    "releases.html",
    "portfolios.html",
    "delivery.html",
    "distribution.html",
    "submissions.html",
    "operations.html",
    "evidence.html",
    "risk.html",
    "verify.html",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"trust-center-manifest.json"}




class _PublicTrustCenterVerifierReadinessMixin:
    def run(self) -> DomainDocument:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "trust-center-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "trust-center-manifest.json", "manifest", "ptc_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_html(archive)
                self._verify_requirements()
                self._verify_delivery_anchor()
                self._verify_anchor_registry()
                self._verify_anchor_transparency()
                self._verify_acceptance_board_signoff()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptc_zip_open", "failed", "blocking", "Public Trust Center ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptc_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptc_zip_open", "failed", "blocking", f"Public Trust Center ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptc_zip_open", "passed", "blocking", "Public Trust Center ZIP can be opened.")
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
        self._add_check("zip", "ptc_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptc_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptc_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptc_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "ptc_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Public Trust Center entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "ptc_zip_no_nested_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden nested/internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptc_manifest_exists", "failed", "blocking", "trust-center-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptc_manifest_integrity", self.manifest.get("integrity_hash"), public_trust_center_manifest_hash(self.manifest), "Trust Center manifest integrity")
        package_type_ok = self.manifest.get("package_type") == PTC_PACKAGE_TYPE
        self._add_check("manifest", "ptc_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is valid." if package_type_ok else "Manifest package_type is invalid.")
        rows = _as_list(self.manifest.get("files"))
        valid: list[DomainDocument] = []
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
        self._add_check("manifest", "ptc_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "ptc_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "ptc_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", "ptc_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "trust-center-report.json", "report", "ptc_report_parse")
        for name in (
            "trust-center-data.json",
            "release-index.json",
            "portfolio-index.json",
            "package-index.json",
            "verification-index.json",
            "public-package-verification-index.json",
            "risk-register.json",
            "transparency-index.json",
            "acknowledgement-index.json",
            "delivery-index.json",
            "distribution-index.json",
            "submission-index.json",
            "submission-evidence-index.json",
            "operations-index.json",
            "operations-package-index.json",
            "readiness-matrix.json",
            "delivery-risk-register.json",
            "delivery-verification-index.json",
        ):
            self.data_docs[name] = self._read_json_entry(archive, f"data/{name}", "data", f"ptc_data_{name.replace('-', '_').replace('.', '_')}_parse")
        sidecar_index = self.data_docs.get("public-package-verification-index.json", {})
        for row in sidecar_index.get("sidecars", []) if isinstance(sidecar_index.get("sidecars"), list) else []:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if not path:
                continue
            entry = f"data/{path}"
            self.data_docs[path] = self._read_json_entry(archive, entry, "data", f"ptc_data_{path.replace('/', '_').replace('-', '_').replace('.', '_')}_parse")
        delivery_sidecar_index = self.data_docs.get("delivery-verification-index.json", {})
        for row in delivery_sidecar_index.get("sidecars", []) if isinstance(delivery_sidecar_index.get("sidecars"), list) else []:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if not path:
                continue
            entry = f"data/{path}"
            self.data_docs[path] = self._read_json_entry(archive, entry, "data", f"ptc_data_{path.replace('/', '_').replace('-', '_').replace('.', '_')}_parse")
        for row in delivery_sidecar_index.get("fingerprint_sidecars", []) if isinstance(delivery_sidecar_index.get("fingerprint_sidecars"), list) else []:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if not path:
                continue
            entry = f"data/{path}"
            self.data_docs[path] = self._read_json_entry(archive, entry, "data", f"ptc_data_{path.replace('/', '_').replace('-', '_').replace('.', '_')}_parse")

    def _verify_documents(self) -> None:
        if self.report_doc:
            self._add_hash_check("report", "ptc_report_integrity", self.report_doc.get("integrity_hash"), public_trust_center_report_hash(self.report_doc), "Trust Center Report integrity")
            self._add_hash_check("report", "ptc_manifest_report_hash", self.manifest.get("trust_center_report", {}).get("integrity_hash") if isinstance(self.manifest.get("trust_center_report"), dict) else None, self.report_doc.get("integrity_hash"), "Manifest report hash")
            self._add_hash_check("report", "ptc_manifest_report_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest report source hash")
            source = _as_document(self.report_doc.get("source"))
            self._add_hash_check("report", "ptc_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Trust Center Report source hash")
            self._verify_report_semantics()
            self._verify_data_documents()
            self._verify_manifest_bindings()
        else:
            self._add_check("report", "ptc_report_document_exists", "failed", "blocking", "trust-center-report.json must contain a JSON object.")

    def _verify_report_semantics(self) -> None:
        source = _as_document(self.report_doc.get("source"))
        blockers = _as_list(self.report_doc.get("blockers"))
        warnings = _as_list(self.report_doc.get("warnings"))
        expected_summary = _summary_from_source(source, blockers, warnings)
        for key in ("release_count", "portfolio_count", "public_package_count", "verification_count", "passed_verification_count", "blocker_count", "warning_count", "status", "readiness"):
            self._add_exact_check("report", f"ptc_report_summary_{key}", self.report_doc.get("summary", {}).get(key) if isinstance(self.report_doc.get("summary"), dict) else None, expected_summary.get(key), f"Report summary {key}")
        self._add_exact_check("report", "ptc_report_release_readiness_semantics", self.report_doc.get("release_readiness"), _release_readiness(source), "Release readiness")
        self._add_exact_check("report", "ptc_report_portfolio_readiness_semantics", self.report_doc.get("portfolio_readiness"), _portfolio_readiness(source), "Portfolio readiness")
        self._add_exact_check("report", "ptc_report_package_index_semantics", self.report_doc.get("package_index"), _package_index(source), "Package index")
        self._add_exact_check("report", "ptc_report_verification_index_semantics", self.report_doc.get("verification_index"), _verification_index(source), "Verification index")
        self._add_exact_check("report", "ptc_report_delivery_readiness_semantics", self.report_doc.get("delivery_readiness"), _delivery_readiness(source), "Delivery readiness")
        self._add_exact_check("report", "ptc_report_delivery_risk_register_semantics", self.report_doc.get("delivery_risk_register"), _delivery_risk_register(source), "Delivery risk register")

    def _verify_data_documents(self) -> None:
        sidecar_docs = {name: doc for name, doc in self.data_docs.items() if name.startswith("package-verification-summaries/")}
        delivery_sidecar_docs = {name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-verification-summaries/") or name.startswith("delivery-fingerprint-summaries/")}
        expected_docs, _expected_pages = expected_public_trust_center_documents(self.report_doc, sidecar_docs, delivery_sidecar_docs)
        for name, doc in self.data_docs.items():
            if name.startswith("package-verification-summaries/") or name.startswith("delivery-verification-summaries/") or name.startswith("delivery-fingerprint-summaries/"):
                continue
            self._add_exact_check("data", f"ptc_data_{name.replace('-', '_').replace('.', '_')}_source_hash", doc.get("source_hash"), self.report_doc.get("source_hash"), f"{name} source_hash")
            self._add_exact_check("data", f"ptc_data_{name.replace('-', '_').replace('.', '_')}_semantics", doc, expected_docs.get(name), f"{name} semantic payload")
        data_doc = self.data_docs.get("trust-center-data.json", {})
        for name, key in (
            ("release-index.json", "releases"),
            ("portfolio-index.json", "portfolios"),
            ("package-index.json", "packages"),
            ("verification-index.json", "verifications"),
            ("risk-register.json", "risks"),
            ("transparency-index.json", "transparency"),
            ("acknowledgement-index.json", "acknowledgements"),
        ):
            self._add_exact_check("data", f"ptc_data_{name.replace('-', '_').replace('.', '_')}_trust_center_binding", self.data_docs.get(name, {}).get(key), data_doc.get(key), f"{name} binds trust-center-data.{key}")
        for name, doc_key, data_key in (
            ("delivery-index.json", "releases", "delivery"),
            ("distribution-index.json", "targets", "distribution"),
            ("submission-index.json", "submissions", "submissions"),
            ("submission-evidence-index.json", "evidence", "submission_evidence"),
            ("operations-index.json", "operations", "operations"),
            ("operations-package-index.json", "packages", "operations_packages"),
            ("readiness-matrix.json", "rows", "readiness_matrix"),
            ("delivery-risk-register.json", "risks", "delivery_risks"),
        ):
            self._add_exact_check("data", f"ptc_data_{name.replace('-', '_').replace('.', '_')}_trust_center_binding", self.data_docs.get(name, {}).get(doc_key), data_doc.get(data_key), f"{name} binds trust-center-data.{data_key}")
        sidecar_doc = self.data_docs.get("public-package-verification-index.json", {})
        self._add_exact_check("data", "ptc_data_public_package_verification_index_json_trust_center_binding", sidecar_doc.get("packages"), data_doc.get("package_verification_summaries"), "public-package-verification-index.json binds trust-center-data.package_verification_summaries")
        delivery_sidecar_doc = self.data_docs.get("delivery-verification-index.json", {})
        self._add_exact_check("data", "ptc_data_delivery_verification_index_json_trust_center_binding", delivery_sidecar_doc.get("summaries"), data_doc.get("delivery_verification_summaries"), "delivery-verification-index.json binds trust-center-data.delivery_verification_summaries")
        self._verify_package_verification_sidecar()
        self._verify_delivery_verification_sidecar()

    def _verify_manifest_bindings(self) -> None:
        data = _as_document(self.manifest.get("data"))
        self._add_exact_check("manifest", "ptc_manifest_data_trust_center_hash", data.get("trust_center_data_hash"), stable_hash(self.data_docs.get("trust-center-data.json", {})), "Manifest trust-center-data hash")
        self._add_exact_check("manifest", "ptc_manifest_data_package_index_hash", data.get("package_index_hash"), stable_hash(self.data_docs.get("package-index.json", {})), "Manifest package-index hash")
        self._add_exact_check("manifest", "ptc_manifest_data_verification_index_hash", data.get("verification_index_hash"), stable_hash(self.data_docs.get("verification-index.json", {})), "Manifest verification-index hash")
        self._add_exact_check("manifest", "ptc_manifest_data_public_package_verification_index_hash", data.get("public_package_verification_index_hash"), stable_hash(self.data_docs.get("public-package-verification-index.json", {})), "Manifest public-package-verification-index hash")
        self._add_exact_check("manifest", "ptc_manifest_data_risk_register_hash", data.get("risk_register_hash"), stable_hash(self.data_docs.get("risk-register.json", {})), "Manifest risk-register hash")
        for name, key in (
            ("delivery-index.json", "delivery_index_hash"),
            ("distribution-index.json", "distribution_index_hash"),
            ("submission-index.json", "submission_index_hash"),
            ("submission-evidence-index.json", "submission_evidence_index_hash"),
            ("operations-index.json", "operations_index_hash"),
            ("operations-package-index.json", "operations_package_index_hash"),
            ("readiness-matrix.json", "readiness_matrix_hash"),
            ("delivery-risk-register.json", "delivery_risk_register_hash"),
            ("delivery-verification-index.json", "delivery_verification_index_hash"),
        ):
            self._add_exact_check("manifest", f"ptc_manifest_data_{key}", data.get(key), stable_hash(self.data_docs.get(name, {})), f"Manifest {name} hash")
        summary = _as_document(self.report_doc.get("summary"))
        for key in ("release_count", "portfolio_count", "public_package_count", "verification_count"):
            self._add_exact_check("manifest", f"ptc_manifest_{key}", self.manifest.get(key), summary.get(key), f"Manifest {key}")

    def _verify_html(self, archive: zipfile.ZipFile) -> None:
        sidecar_docs = {name: doc for name, doc in self.data_docs.items() if name.startswith("package-verification-summaries/")}
        delivery_sidecar_docs = {name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-verification-summaries/") or name.startswith("delivery-fingerprint-summaries/")}
        _expected_docs, expected_pages = expected_public_trust_center_documents(self.report_doc, sidecar_docs, delivery_sidecar_docs)
        pages = _as_list(self.manifest.get("pages"))
        page_rows = {str(item.get("path") or ""): item for item in pages if isinstance(item, dict)}
        source_hash = str(self.report_doc.get("source_hash") or "")
        for page in PTC_HTML_PAGES:
            info = self.entry_map.get(page)
            if info is None:
                self._add_check("html", f"ptc_html_{page}_exists", "failed", "blocking", f"{page} is missing.")
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                self._add_check("html", f"ptc_html_{page}_utf8", "failed", "blocking", f"{page} is not valid UTF-8: {exc}")
                continue
            self._add_check("html", f"ptc_html_{page}_utf8", "passed", "blocking", f"{page} parses as UTF-8.")
            row = page_rows.get(page, {})
            self._add_hash_check("html", f"ptc_html_{page}_manifest_hash", row.get("content_hash"), _sha256_text(text), f"{page} manifest content hash")
            self._add_exact_check("html", f"ptc_html_{page}_source_hash", row.get("source_hash"), source_hash, f"{page} manifest source hash")
            self._add_check("html", f"ptc_html_{page}_source_marker", "passed" if f'data-source-hash="{source_hash}"' in text else "failed", "blocking", f"{page} binds source hash." if f'data-source-hash="{source_hash}"' in text else f"{page} does not bind source hash.")
            self._add_exact_check("html", f"ptc_html_{page}_semantics", _normalize_newlines(text), _normalize_newlines(expected_pages.get(page) or ""), f"{page} deterministic HTML")
            lower = text.lower()
            bad = []
            for needle in ("<script", "<iframe", "<object", "<embed", "http://", "https://", "url(", "data:"):
                if needle in lower:
                    bad.append(needle)
            if INLINE_EVENT_RE.search(text):
                bad.append("inline_event")
            if _contains_local_path(text) or ".musicforge/" in lower:
                bad.append("local_path")
            self._add_check("html", f"ptc_html_{page}_safe", "failed" if bad else "passed", "blocking", f"{page} contains forbidden HTML content: " + ", ".join(bad) if bad else f"{page} contains no forbidden HTML content.")

    def _verify_package_verification_sidecar(self) -> None:
        package_doc = self.data_docs.get("package-index.json", {})
        verification_doc = self.data_docs.get("verification-index.json", {})
        sidecar_doc = self.data_docs.get("public-package-verification-index.json", {})
        packages = _as_list(package_doc.get("packages"))
        verifications = _as_list(verification_doc.get("verifications"))
        sidecar_packages = _as_list(sidecar_doc.get("packages"))
        sidecar_verifications = _as_list(sidecar_doc.get("verifications"))
        independent_sidecars = {name: doc for name, doc in self.data_docs.items() if name.startswith("package-verification-summaries/")}
        expected_index = _package_verification_index_from_independent_sidecars(self.report_doc.get("source_hash"), independent_sidecars)
        self._add_exact_check("data", "ptc_package_fingerprint_verification_summary_binding", sidecar_packages, expected_index.get("packages"), "Public package fingerprints bind independent verification sidecars")
        self._add_exact_check("data", "ptc_verification_index_sidecar_binding", sidecar_verifications, expected_index.get("verifications"), "Verification index binds independent verification sidecars")
        self._add_exact_check("data", "ptc_full_resign_package_fingerprint", packages, _packages_from_sidecars(sidecar_packages), "Package index fingerprints match independent verification sidecar")
        self._add_exact_check("data", "ptc_full_resign_verification_fingerprint", verifications, _verifications_from_sidecars(sidecar_verifications), "Verification index fingerprints match independent verification sidecar")
        self._verify_independent_sidecar_hashes(sidecar_doc, independent_sidecars)

    def _verify_delivery_verification_sidecar(self) -> None:
        delivery_doc = self.data_docs.get("delivery-verification-index.json", {})
        independent_sidecars = {name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-verification-summaries/")}
        fingerprint_sidecars = {name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-fingerprint-summaries/")}
        self._verify_delivery_sidecar_evidence_bindings(independent_sidecars, fingerprint_sidecars)
        expected_index = _delivery_verification_index_from_independent_sidecars(self.report_doc.get("source_hash"), independent_sidecars, fingerprint_sidecars)
        self._add_exact_check("data", "ptc_delivery_verification_sidecar_binding", delivery_doc.get("summaries"), expected_index.get("summaries"), "Delivery verification index binds independent sidecars")
        self._add_exact_check("data", "ptc_delivery_fingerprint_sidecar_binding", delivery_doc.get("fingerprint_sidecars"), expected_index.get("fingerprint_sidecars"), "Delivery verification index binds independent fingerprint sidecars")
        expected_payloads = _delivery_payloads_from_fingerprint_sidecars(fingerprint_sidecars)
        actual_payloads = _delivery_payloads_from_data_docs(self.data_docs)
        self._add_exact_check("data", "ptc_delivery_full_resign_guard", actual_payloads, expected_payloads, "Delivery data payloads match independent sidecars")
        self._verify_independent_delivery_sidecar_hashes(delivery_doc, independent_sidecars)
        self._verify_independent_delivery_fingerprint_hashes(delivery_doc, fingerprint_sidecars)

    def _verify_independent_sidecar_hashes(self, sidecar_doc: DomainDocument, sidecars: dict[str, DomainDocument]) -> None:
        rows = _as_list(sidecar_doc.get("sidecars"))
        declared = {str(row.get("path") or ""): row for row in rows if isinstance(row, dict)}
        actual = {path: stable_hash(doc) for path, doc in sidecars.items()}
        self._add_exact_check("data", "ptc_independent_verification_sidecar_set", sorted(declared), sorted(actual), "Declared independent verification sidecar set")
        for path, row in sorted(declared.items()):
            self._add_exact_check("data", "ptc_independent_verification_sidecar_hash", row.get("hash"), actual.get(path), f"Independent verification sidecar hash {path}")

    def _verify_independent_delivery_sidecar_hashes(self, sidecar_doc: DomainDocument, sidecars: dict[str, DomainDocument]) -> None:
        rows = _as_list(sidecar_doc.get("sidecars"))
        declared = {str(row.get("path") or ""): row for row in rows if isinstance(row, dict)}
        actual = {path: stable_hash(doc) for path, doc in sidecars.items()}
        self._add_exact_check("data", "ptc_independent_delivery_sidecar_set", sorted(declared), sorted(actual), "Declared independent delivery sidecar set")
        for path, row in sorted(declared.items()):
            self._add_exact_check("data", "ptc_independent_delivery_sidecar_hash", row.get("hash"), actual.get(path), f"Independent delivery sidecar hash {path}")

    def _verify_independent_delivery_fingerprint_hashes(self, sidecar_doc: DomainDocument, sidecars: dict[str, DomainDocument]) -> None:
        rows = _as_list(sidecar_doc.get("fingerprint_sidecars"))
        declared = {str(row.get("path") or ""): row for row in rows if isinstance(row, dict)}
        actual = {path: stable_hash(doc) for path, doc in sidecars.items()}
        self._add_exact_check("data", "ptc_independent_delivery_fingerprint_sidecar_set", sorted(declared), sorted(actual), "Declared independent delivery fingerprint sidecar set")
        for path, row in sorted(declared.items()):
            self._add_exact_check("data", "ptc_independent_delivery_fingerprint_sidecar_hash", row.get("hash"), actual.get(path), f"Independent delivery fingerprint sidecar hash {path}")

    def _verify_delivery_sidecar_evidence_bindings(self, sidecars: dict[str, DomainDocument], fingerprint_sidecars: dict[str, DomainDocument]) -> None:
        for path, doc in sorted(sidecars.items()):
            if not isinstance(doc, dict):
                continue
            evidence = _as_document(doc.get("evidence"))
            payload = _as_document(doc.get("payload"))
            summary = _as_document(doc.get("summary"))
            fingerprint_path = str(doc.get("fingerprint_sidecar_path") or summary.get("fingerprint_sidecar_path") or "")
            fingerprint_doc = fingerprint_sidecars.get(fingerprint_path, {}) if fingerprint_path else {}
            fingerprint_payload = _as_document(fingerprint_doc.get("payload"))
            evidence_payload = _as_document(evidence.get("payload"))
            self._add_exact_check("data", "ptc_delivery_sidecar_evidence_binding", payload, evidence_payload, f"Delivery sidecar payload binds independent evidence {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_evidence_payload_hash", evidence.get("payload_hash"), stable_hash(evidence_payload), f"Delivery sidecar evidence payload hash {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_summary_hash", doc.get("summary_hash"), stable_hash({"summary": summary, "payload": payload, "evidence": evidence}), f"Delivery sidecar summary hash {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_fingerprint_reference", doc.get("fingerprint_sidecar_hash"), stable_hash(fingerprint_doc) if fingerprint_doc else None, f"Delivery sidecar fingerprint reference {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_fingerprint_payload_binding", payload, fingerprint_payload, f"Delivery sidecar payload binds fingerprint sidecar {path}")
            self._add_exact_check("data", "ptc_delivery_fingerprint_payload_hash", fingerprint_doc.get("payload_hash") if isinstance(fingerprint_doc, dict) else None, stable_hash(fingerprint_payload), f"Delivery fingerprint payload hash {path}")
            fingerprints = _as_document(fingerprint_doc.get("fingerprints"))
            self._add_exact_check("data", "ptc_delivery_fingerprint_hash", fingerprint_doc.get("fingerprint_hash") if isinstance(fingerprint_doc, dict) else None, stable_hash({"payload_hash": fingerprint_doc.get("payload_hash") if isinstance(fingerprint_doc, dict) else None, "fingerprints": fingerprints}), f"Delivery fingerprint hash {path}")

    def _verify_requirements(self) -> None:
        packages = _as_list(self.report_doc.get("package_index"))
        releases = _as_list(self.report_doc.get("release_readiness"))
        if self.require_release_readiness:
            ok = bool(releases) and all(item.get("readiness") == "ready" for item in releases if isinstance(item, dict))
            self._add_check("requirements", "ptc_require_release_readiness", "passed" if ok else "failed", "blocking", "All releases are ready." if ok else "Release readiness is required.")
        required_types = []
        if self.require_public_attestation:
            required_types.extend(["registry", "portal", "transparency"])
        if self.require_registry_current:
            required_types.append("registry")
        if self.require_portal_current:
            required_types.append("portal")
        if self.require_transparency_current:
            required_types.append("transparency")
        if self.require_acknowledgement_current:
            required_types.append("transparency_acknowledgement")
        for package_type in sorted(set(required_types)):
            matching = [item for item in packages if isinstance(item, dict) and item.get("package_type") == package_type]
            ok = bool(matching) and all(item.get("verification_status") == "passed" for item in matching)
            self._add_check("requirements", f"ptc_require_{package_type}", "passed" if ok else "failed", "blocking", f"{package_type} public evidence is verified." if ok else f"{package_type} public evidence is required.")
        delivery_rows = _as_list(self.report_doc.get("delivery_readiness"))
        if self.require_delivery_readiness:
            ok = bool(delivery_rows) and all(item.get("readiness") == "ready" for item in delivery_rows if isinstance(item, dict))
            self._add_check("requirements", "ptc_require_delivery_readiness", "passed" if ok else "failed", "blocking", "Delivery readiness is complete." if ok else "Delivery readiness is required.")
        requirement_checks = (
            ("distribution_ready", self.require_distribution_ready, "distribution_status", {"ready"}, "Distribution evidence is ready."),
            ("submission_accepted", self.require_submission_accepted, "submission_status", {"accepted"}, "Submission evidence is accepted."),
            ("submission_evidence", self.require_submission_evidence, "submission_evidence_status", {"signed"}, "Submission Evidence is signed."),
            ("operations_signed", self.require_operations_signed, "operations_status", {"signed", "force_signed"}, "Release Operations is signed."),
            ("operations_audit", self.require_operations_audit, "operations_audit_status", {"passed", "warning"}, "Release Operations Audit is verified."),
            ("operations_reviewer_pack", self.require_operations_reviewer_pack, "operations_reviewer_pack_status", {"passed", "warning"}, "Release Operations Reviewer Pack is verified."),
        )
        for name, enabled, key, allowed, passed_message in requirement_checks:
            if not enabled:
                continue
            ok = bool(delivery_rows) and all(item.get(key) in allowed for item in delivery_rows if isinstance(item, dict))
            self._add_check("requirements", f"ptc_require_{name}", "passed" if ok else "failed", "blocking", passed_message if ok else f"{name} is required.")
