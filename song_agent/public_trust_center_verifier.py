from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.projectio import write_json
from song_agent.public_trust_center import (
    PTC_BLOCKED_KEYS,
    PTC_HTML_PAGES,
    PTC_PACKAGE_TYPE,
    expected_public_trust_center_documents,
    public_trust_center_manifest_hash,
    public_trust_center_report_hash,
)
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash


PTC_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 250
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
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
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
INLINE_EVENT_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
VERIFIER_BLOCKED_KEYS = PTC_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_public_trust_center_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_release_readiness: bool = False,
    require_public_attestation: bool = False,
    require_registry_current: bool = False,
    require_portal_current: bool = False,
    require_transparency_current: bool = False,
    require_acknowledgement_current: bool = False,
    require_delivery_readiness: bool = False,
    require_distribution_ready: bool = False,
    require_submission_accepted: bool = False,
    require_submission_evidence: bool = False,
    require_operations_signed: bool = False,
    require_operations_audit: bool = False,
    require_operations_reviewer_pack: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
    delivery_anchor_path: Path | str | None = None,
) -> dict[str, Any]:
    verifier = _PublicTrustCenterVerifier(
        Path(zip_path),
        strict=strict,
        require_release_readiness=require_release_readiness,
        require_public_attestation=require_public_attestation,
        require_registry_current=require_registry_current,
        require_portal_current=require_portal_current,
        require_transparency_current=require_transparency_current,
        require_acknowledgement_current=require_acknowledgement_current,
        require_delivery_readiness=require_delivery_readiness,
        require_distribution_ready=require_distribution_ready,
        require_submission_accepted=require_submission_accepted,
        require_submission_evidence=require_submission_evidence,
        require_operations_signed=require_operations_signed,
        require_operations_audit=require_operations_audit,
        require_operations_reviewer_pack=require_operations_reviewer_pack,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
        delivery_anchor_path=Path(delivery_anchor_path) if delivery_anchor_path is not None else None,
    )
    return verifier.run()


def write_public_trust_center_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Public Trust Center verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"readiness: {summary.get('readiness') or 'unknown'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def public_trust_center_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PublicTrustCenterVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_release_readiness: bool,
        require_public_attestation: bool,
        require_registry_current: bool,
        require_portal_current: bool,
        require_transparency_current: bool,
        require_acknowledgement_current: bool,
        require_delivery_readiness: bool,
        require_distribution_ready: bool,
        require_submission_accepted: bool,
        require_submission_evidence: bool,
        require_operations_signed: bool,
        require_operations_audit: bool,
        require_operations_reviewer_pack: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
        delivery_anchor_path: Path | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_release_readiness = require_release_readiness
        self.require_public_attestation = require_public_attestation
        self.require_registry_current = require_registry_current
        self.require_portal_current = require_portal_current
        self.require_transparency_current = require_transparency_current
        self.require_acknowledgement_current = require_acknowledgement_current
        self.require_delivery_readiness = require_delivery_readiness
        self.require_distribution_ready = require_distribution_ready
        self.require_submission_accepted = require_submission_accepted
        self.require_submission_evidence = require_submission_evidence
        self.require_operations_signed = require_operations_signed
        self.require_operations_audit = require_operations_audit
        self.require_operations_reviewer_pack = require_operations_reviewer_pack
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.delivery_anchor_path = delivery_anchor_path
        self.delivery_anchor_doc: dict[str, Any] = {}
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.data_docs: dict[str, dict[str, Any]] = {}
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
                if "trust-center-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "trust-center-manifest.json", "manifest", "ptc_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_html(archive)
                self._verify_requirements()
                self._verify_delivery_anchor()
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
            source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
            self._add_hash_check("report", "ptc_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Trust Center Report source hash")
            self._verify_report_semantics()
            self._verify_data_documents()
            self._verify_manifest_bindings()
        else:
            self._add_check("report", "ptc_report_document_exists", "failed", "blocking", "trust-center-report.json must contain a JSON object.")

    def _verify_report_semantics(self) -> None:
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        blockers = self.report_doc.get("blockers") if isinstance(self.report_doc.get("blockers"), list) else []
        warnings = self.report_doc.get("warnings") if isinstance(self.report_doc.get("warnings"), list) else []
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
        data = self.manifest.get("data") if isinstance(self.manifest.get("data"), dict) else {}
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
        summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
        for key in ("release_count", "portfolio_count", "public_package_count", "verification_count"):
            self._add_exact_check("manifest", f"ptc_manifest_{key}", self.manifest.get(key), summary.get(key), f"Manifest {key}")

    def _verify_html(self, archive: zipfile.ZipFile) -> None:
        sidecar_docs = {name: doc for name, doc in self.data_docs.items() if name.startswith("package-verification-summaries/")}
        delivery_sidecar_docs = {name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-verification-summaries/") or name.startswith("delivery-fingerprint-summaries/")}
        _expected_docs, expected_pages = expected_public_trust_center_documents(self.report_doc, sidecar_docs, delivery_sidecar_docs)
        pages = self.manifest.get("pages") if isinstance(self.manifest.get("pages"), list) else []
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
        packages = package_doc.get("packages") if isinstance(package_doc.get("packages"), list) else []
        verifications = verification_doc.get("verifications") if isinstance(verification_doc.get("verifications"), list) else []
        sidecar_packages = sidecar_doc.get("packages") if isinstance(sidecar_doc.get("packages"), list) else []
        sidecar_verifications = sidecar_doc.get("verifications") if isinstance(sidecar_doc.get("verifications"), list) else []
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

    def _verify_independent_sidecar_hashes(self, sidecar_doc: dict[str, Any], sidecars: dict[str, dict[str, Any]]) -> None:
        rows = sidecar_doc.get("sidecars") if isinstance(sidecar_doc.get("sidecars"), list) else []
        declared = {str(row.get("path") or ""): row for row in rows if isinstance(row, dict)}
        actual = {path: stable_hash(doc) for path, doc in sidecars.items()}
        self._add_exact_check("data", "ptc_independent_verification_sidecar_set", sorted(declared), sorted(actual), "Declared independent verification sidecar set")
        for path, row in sorted(declared.items()):
            self._add_exact_check("data", "ptc_independent_verification_sidecar_hash", row.get("hash"), actual.get(path), f"Independent verification sidecar hash {path}")

    def _verify_independent_delivery_sidecar_hashes(self, sidecar_doc: dict[str, Any], sidecars: dict[str, dict[str, Any]]) -> None:
        rows = sidecar_doc.get("sidecars") if isinstance(sidecar_doc.get("sidecars"), list) else []
        declared = {str(row.get("path") or ""): row for row in rows if isinstance(row, dict)}
        actual = {path: stable_hash(doc) for path, doc in sidecars.items()}
        self._add_exact_check("data", "ptc_independent_delivery_sidecar_set", sorted(declared), sorted(actual), "Declared independent delivery sidecar set")
        for path, row in sorted(declared.items()):
            self._add_exact_check("data", "ptc_independent_delivery_sidecar_hash", row.get("hash"), actual.get(path), f"Independent delivery sidecar hash {path}")

    def _verify_independent_delivery_fingerprint_hashes(self, sidecar_doc: dict[str, Any], sidecars: dict[str, dict[str, Any]]) -> None:
        rows = sidecar_doc.get("fingerprint_sidecars") if isinstance(sidecar_doc.get("fingerprint_sidecars"), list) else []
        declared = {str(row.get("path") or ""): row for row in rows if isinstance(row, dict)}
        actual = {path: stable_hash(doc) for path, doc in sidecars.items()}
        self._add_exact_check("data", "ptc_independent_delivery_fingerprint_sidecar_set", sorted(declared), sorted(actual), "Declared independent delivery fingerprint sidecar set")
        for path, row in sorted(declared.items()):
            self._add_exact_check("data", "ptc_independent_delivery_fingerprint_sidecar_hash", row.get("hash"), actual.get(path), f"Independent delivery fingerprint sidecar hash {path}")

    def _verify_delivery_sidecar_evidence_bindings(self, sidecars: dict[str, dict[str, Any]], fingerprint_sidecars: dict[str, dict[str, Any]]) -> None:
        for path, doc in sorted(sidecars.items()):
            if not isinstance(doc, dict):
                continue
            evidence = doc.get("evidence") if isinstance(doc.get("evidence"), dict) else {}
            payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
            summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
            fingerprint_path = str(doc.get("fingerprint_sidecar_path") or summary.get("fingerprint_sidecar_path") or "")
            fingerprint_doc = fingerprint_sidecars.get(fingerprint_path, {}) if fingerprint_path else {}
            fingerprint_payload = fingerprint_doc.get("payload") if isinstance(fingerprint_doc.get("payload"), dict) else {}
            evidence_payload = evidence.get("payload") if isinstance(evidence.get("payload"), dict) else {}
            self._add_exact_check("data", "ptc_delivery_sidecar_evidence_binding", payload, evidence_payload, f"Delivery sidecar payload binds independent evidence {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_evidence_payload_hash", evidence.get("payload_hash"), stable_hash(evidence_payload), f"Delivery sidecar evidence payload hash {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_summary_hash", doc.get("summary_hash"), stable_hash({"summary": summary, "payload": payload, "evidence": evidence}), f"Delivery sidecar summary hash {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_fingerprint_reference", doc.get("fingerprint_sidecar_hash"), stable_hash(fingerprint_doc) if fingerprint_doc else None, f"Delivery sidecar fingerprint reference {path}")
            self._add_exact_check("data", "ptc_delivery_sidecar_fingerprint_payload_binding", payload, fingerprint_payload, f"Delivery sidecar payload binds fingerprint sidecar {path}")
            self._add_exact_check("data", "ptc_delivery_fingerprint_payload_hash", fingerprint_doc.get("payload_hash") if isinstance(fingerprint_doc, dict) else None, stable_hash(fingerprint_payload), f"Delivery fingerprint payload hash {path}")
            fingerprints = fingerprint_doc.get("fingerprints") if isinstance(fingerprint_doc.get("fingerprints"), dict) else {}
            self._add_exact_check("data", "ptc_delivery_fingerprint_hash", fingerprint_doc.get("fingerprint_hash") if isinstance(fingerprint_doc, dict) else None, stable_hash({"payload_hash": fingerprint_doc.get("payload_hash") if isinstance(fingerprint_doc, dict) else None, "fingerprints": fingerprints}), f"Delivery fingerprint hash {path}")

    def _verify_requirements(self) -> None:
        packages = self.report_doc.get("package_index") if isinstance(self.report_doc.get("package_index"), list) else []
        releases = self.report_doc.get("release_readiness") if isinstance(self.report_doc.get("release_readiness"), list) else []
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
        delivery_rows = self.report_doc.get("delivery_readiness") if isinstance(self.report_doc.get("delivery_readiness"), list) else []
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

    def _verify_delivery_anchor(self) -> None:
        required = any(
            (
                self.require_delivery_readiness,
                self.require_distribution_ready,
                self.require_submission_accepted,
                self.require_submission_evidence,
                self.require_operations_signed,
                self.require_operations_audit,
                self.require_operations_reviewer_pack,
            )
        )
        if not required:
            return
        anchor_path = self.delivery_anchor_path or self.zip_path.with_name(self.zip_path.stem + ".delivery-anchor.json")
        if not anchor_path.exists() or not anchor_path.is_file() or anchor_path.is_symlink():
            self._add_check("requirements", "ptc_delivery_external_anchor", "failed", "blocking", "Delivery verification requires an external Public Trust Center delivery anchor.")
            return
        try:
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._add_check("requirements", "ptc_delivery_external_anchor", "failed", "blocking", f"Delivery anchor cannot be read: {exc}")
            return
        self.delivery_anchor_doc = anchor if isinstance(anchor, dict) else {}
        self._add_exact_check("requirements", "ptc_delivery_anchor_package_type", self.delivery_anchor_doc.get("package_type"), "musicforge_public_trust_center_delivery_anchor", "Delivery anchor package type")
        self._add_exact_check("requirements", "ptc_delivery_anchor_hash", self.delivery_anchor_doc.get("anchor_hash"), stable_hash({key: value for key, value in self.delivery_anchor_doc.items() if key != "anchor_hash"}), "Delivery anchor integrity")
        self._add_exact_check("requirements", "ptc_delivery_anchor_zip_sha256", self.delivery_anchor_doc.get("zip_sha256"), self.zip_sha256, "Delivery anchor ZIP sha256")
        self._add_exact_check("requirements", "ptc_delivery_anchor_zip_size", self.delivery_anchor_doc.get("zip_size_bytes"), self.zip_size_bytes, "Delivery anchor ZIP size")
        self._add_exact_check("requirements", "ptc_delivery_anchor_manifest_hash", self.delivery_anchor_doc.get("manifest_hash"), self.manifest.get("integrity_hash"), "Delivery anchor manifest hash")
        self._add_exact_check("requirements", "ptc_delivery_anchor_source_hash", self.delivery_anchor_doc.get("source_hash"), self.report_doc.get("source_hash"), "Delivery anchor source hash")
        expected = _delivery_anchor_rows_from_fingerprint_sidecars({name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-fingerprint-summaries/")})
        actual = self.delivery_anchor_doc.get("fingerprint_sidecars") if isinstance(self.delivery_anchor_doc.get("fingerprint_sidecars"), list) else []
        self._add_exact_check("requirements", "ptc_delivery_anchor_fingerprint_sidecars", actual, expected, "Delivery anchor binds fingerprint sidecars")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".md", ".html")):
                continue
            info = self.entry_map.get(name)
            if info is None or info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
            if name.endswith(".json"):
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    continue
                self.redaction_findings.extend(_blocked_key_findings(name, value))
        self._add_check("redaction", "ptc_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
        info = self.entry_map.get(name)
        if not name or info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name or 'entry'} is missing.")
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
        summary.update({"center_id": self.manifest.get("center_id") or self.report_doc.get("center_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": PTC_VERIFICATION_SCHEMA_VERSION,
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


def _summary_from_source(source: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    package_count = len(source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else [])
    verification_count = len(source.get("verification_fingerprints", []) if isinstance(source.get("verification_fingerprints"), list) else [])
    passed_verifications = sum(1 for item in source.get("verification_fingerprints", []) if isinstance(item, dict) and item.get("verification_status") == "passed")
    delivery_rows = source.get("release_delivery_summaries", []) if isinstance(source.get("release_delivery_summaries"), list) else []
    distribution_rows = source.get("distribution_summaries", []) if isinstance(source.get("distribution_summaries"), list) else []
    submission_rows = source.get("submission_summaries", []) if isinstance(source.get("submission_summaries"), list) else []
    operations_rows = source.get("operations_summaries", []) if isinstance(source.get("operations_summaries"), list) else []
    return {
        "center_id": source.get("center_id"),
        "profile": source.get("profile"),
        "release_count": int(source.get("release_count") or 0),
        "portfolio_count": int(source.get("portfolio_count") or 0),
        "public_package_count": package_count,
        "verification_count": verification_count,
        "passed_verification_count": passed_verifications,
        "delivery_release_count": len(delivery_rows),
        "delivery_ready_count": sum(1 for item in delivery_rows if isinstance(item, dict) and item.get("readiness") == "ready"),
        "distribution_ready_count": sum(1 for item in distribution_rows if isinstance(item, dict) and item.get("readiness") == "ready"),
        "submission_accepted_count": sum(1 for item in submission_rows if isinstance(item, dict) and item.get("accepted_count", 0)),
        "operations_signed_count": sum(1 for item in operations_rows if isinstance(item, dict) and item.get("operations_signoff_status") in {"signed", "force_signed"}),
        "delivery_risk_count": len(source.get("delivery_risk_register", []) if isinstance(source.get("delivery_risk_register"), list) else []),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "readiness": "blocked" if blockers else "review_needed" if warnings else "public_trust_ready",
    }


def _release_readiness(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in source.get("releases", []) if isinstance(source.get("releases"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "release_id": item.get("release_id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "signoff_status": item.get("signoff_status"),
                "track_count": item.get("track_count", 0),
                "readiness": "ready" if item.get("signoff_status") in {"signed", "force_signed"} else "review_needed",
                "zip_sha256": item.get("zip_sha256"),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("release_id") or ""))


def _delivery_readiness(source: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in source.get("delivery_readiness_matrix", []) if isinstance(item, dict)], key=lambda item: str(item.get("release_id") or ""))


def _delivery_risk_register(source: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in source.get("delivery_risk_register", []) if isinstance(item, dict)], key=lambda item: str(item.get("risk_id") or ""))


def _portfolio_readiness(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in source.get("portfolios", []) if isinstance(source.get("portfolios"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append({"portfolio_id": item.get("portfolio_id"), "status": item.get("status"), "profile": item.get("profile"), "public_package_status": item.get("public_package_status")})
    return sorted(rows, key=lambda item: str(item.get("portfolio_id") or ""))


def _package_index(source: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in source.get("public_package_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _verification_index(source: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in source.get("verification_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_sidecars(source: dict[str, Any]) -> list[dict[str, Any]]:
    packages = _package_index(source)
    verifications = {
        _fingerprint_key(item): dict(item)
        for item in source.get("verification_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for package in packages:
        verification = verifications.get(_fingerprint_key(package), {})
        rows.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "zip_sha256": package.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash"),
                "verification_hash": package.get("verification_hash"),
                "verification_status": package.get("verification_status"),
                "verification_report_hash": verification.get("verification_hash") or package.get("verification_hash"),
                "verification_report_status": verification.get("verification_status") or package.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_index_from_independent_sidecars(source_hash: Any, sidecars: dict[str, dict[str, Any]]) -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    verifications: list[dict[str, Any]] = []
    rows = []
    for path, doc in sorted(sidecars.items()):
        if not isinstance(doc, dict):
            continue
        package = dict(doc.get("package") if isinstance(doc.get("package"), dict) else {})
        package["sidecar_path"] = path
        package["sidecar_hash"] = stable_hash(doc)
        packages.append(package)
        verification = doc.get("verification") if isinstance(doc.get("verification"), dict) else {}
        verifications.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "verification_hash": verification.get("verification_report_hash"),
                "verification_status": verification.get("verification_report_status"),
                "verification_report_hash": verification.get("verification_report_hash"),
                "verification_report_status": verification.get("verification_report_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": verification.get("zip_sha256"),
                "zip_size_bytes": verification.get("zip_size_bytes"),
                "manifest_hash": verification.get("manifest_hash"),
                "sidecar_path": path,
                "sidecar_hash": stable_hash(doc),
            }
        )
        rows.append({"path": path, "hash": stable_hash(doc)})
    return {
        "source_hash": source_hash,
        "packages": sorted(packages, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")), str(item.get("profile")))),
        "verifications": sorted(verifications, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")), str(item.get("profile")))),
        "sidecars": rows,
    }


def _delivery_verification_index_from_independent_sidecars(source_hash: Any, sidecars: dict[str, dict[str, Any]], fingerprint_sidecars: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    fingerprint_rows: list[dict[str, Any]] = []
    for path, doc in sorted(sidecars.items()):
        if not isinstance(doc, dict):
            continue
        summary = dict(doc.get("summary") if isinstance(doc.get("summary"), dict) else {})
        summary["sidecar_path"] = path
        summary["sidecar_hash"] = stable_hash(doc)
        if doc.get("fingerprint_sidecar_path"):
            summary["fingerprint_sidecar_path"] = doc.get("fingerprint_sidecar_path")
            summary["fingerprint_sidecar_hash"] = doc.get("fingerprint_sidecar_hash")
        summaries.append(summary)
        rows.append({"path": path, "hash": stable_hash(doc)})
    for path, doc in sorted((fingerprint_sidecars or {}).items()):
        if isinstance(doc, dict):
            fingerprint_rows.append({"path": path, "hash": stable_hash(doc)})
    return {"source_hash": source_hash, "summaries": sorted(summaries, key=_delivery_summary_key), "sidecars": rows, "fingerprint_sidecars": fingerprint_rows}


def _verification_sidecars(source: dict[str, Any]) -> list[dict[str, Any]]:
    packages = {
        _fingerprint_key(item): dict(item)
        for item in source.get("public_package_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for verification in _verification_index(source):
        package = packages.get(_fingerprint_key(verification), {})
        rows.append(
            {
                "portfolio_id": verification.get("portfolio_id"),
                "profile": verification.get("profile"),
                "package_type": verification.get("package_type"),
                "verification_hash": verification.get("verification_hash"),
                "verification_status": verification.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": package.get("zip_sha256") or verification.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes") or verification.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash") or verification.get("manifest_hash"),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _packages_from_sidecars(sidecars: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sidecars:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "portfolio_id": item.get("portfolio_id"),
                "profile": item.get("profile"),
                "package_type": item.get("package_type"),
                "zip_sha256": item.get("zip_sha256"),
                "zip_size_bytes": item.get("zip_size_bytes"),
                "manifest_hash": item.get("manifest_hash"),
                "verification_hash": item.get("verification_hash"),
                "verification_status": item.get("verification_status"),
                "verification_report_hash": item.get("verification_report_hash"),
                "verification_report_status": item.get("verification_report_status"),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _verifications_from_sidecars(sidecars: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sidecars:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "portfolio_id": item.get("portfolio_id"),
                "profile": item.get("profile"),
                "package_type": item.get("package_type"),
                "zip_sha256": item.get("zip_sha256"),
                "zip_size_bytes": item.get("zip_size_bytes"),
                "manifest_hash": item.get("manifest_hash"),
                "verification_hash": item.get("verification_hash"),
                "verification_status": item.get("verification_status"),
                "verification_report_hash": item.get("verification_report_hash"),
                "verification_report_status": item.get("verification_report_status"),
                "blocker_count": item.get("blocker_count", 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _delivery_payloads_from_sidecars(sidecars: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, doc in sorted(sidecars.items()):
        del path
        if not isinstance(doc, dict):
            continue
        payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
        row = dict(payload)
        rows.append(row)
    return sorted(rows, key=_delivery_payload_key)


def _delivery_payloads_from_fingerprint_sidecars(sidecars: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, doc in sorted(sidecars.items()):
        del path
        if not isinstance(doc, dict):
            continue
        payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
        rows.append(dict(payload))
    return sorted(rows, key=_delivery_payload_key)


def _delivery_anchor_rows_from_fingerprint_sidecars(sidecars: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, doc in sorted(sidecars.items()):
        if not isinstance(doc, dict):
            continue
        rows.append(
            {
                "path": path,
                "fingerprint_hash": doc.get("fingerprint_hash"),
                "payload_hash": doc.get("payload_hash"),
                "fingerprints_hash": stable_hash(doc.get("fingerprints") if isinstance(doc.get("fingerprints"), dict) else {}),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("path") or ""))


def _delivery_payloads_from_data_docs(data_docs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for domain, doc_name, row_key in (
        ("release", "delivery-index.json", "releases"),
        ("distribution", "distribution-index.json", "targets"),
        ("submission", "submission-index.json", "submissions"),
        ("submission_evidence", "submission-evidence-index.json", "evidence"),
        ("operations", "operations-index.json", "operations"),
    ):
        doc = data_docs.get(doc_name, {})
        values = doc.get(row_key) if isinstance(doc.get(row_key), list) else []
        for item in values:
            if isinstance(item, dict):
                rows.append(_delivery_public_payload(domain, item))
    return sorted(rows, key=_delivery_payload_key)


def _delivery_public_payload(domain: str, item: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "status",
        "name",
        "readiness",
        "release_signoff_status",
        "release_zip_status",
        "distribution_status",
        "submission_status",
        "submission_evidence_status",
        "operations_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "portfolio_public_proof_status",
        "risk_count",
        "signoff_status",
        "profile_id",
        "platform",
        "target_name",
        "target_status",
        "track_count",
        "ready_count",
        "submitted_count",
        "accepted_count",
        "latest_feedback_status",
        "report_status",
        "report_hash",
        "signoff_hash",
        "redaction_status",
        "accepted_evidence_count",
        "attachment_count",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "package_zip_status",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "runbook_status",
        "change_request_count",
        "fingerprint_hash",
    }
    return {"domain": domain, **{key: item.get(key) for key in sorted(allowed) if key in item}}


def _delivery_summary_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("release_id") or ""), str(item.get("domain") or ""), str(item.get("entity_id") or item.get("target_id") or item.get("submission_id") or ""))


def _delivery_payload_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (str(item.get("release_id") or ""), str(item.get("domain") or ""), str(item.get("target_id") or ""), str(item.get("submission_id") or item.get("entity_id") or ""))


def _fingerprint_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("portfolio_id") or ""), str(item.get("package_type") or ""), str(item.get("profile") or ""))


def _is_safe_zip_entry(name: str) -> bool:
    text = str(name or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        return False
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    if ":" in path.parts[0]:
        return False
    return True


def _is_forbidden_public_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/") or "/.musicforge/" in lowered


def _raw_zip_entry_names(path: Path) -> list[str]:
    data = path.read_bytes() if path.exists() else b""
    names: list[str] = []
    index = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, index)
        if index < 0 or index + 46 > len(data):
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        try:
            names.append(data[start:end].decode("utf-8"))
        except UnicodeDecodeError:
            names.append(data[start:end].decode("cp437", errors="replace"))
        index = end + extra_len + comment_len
    return names


def _counts(values: list[str]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for value in values:
        rows[value] = rows.get(value, 0) + 1
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contains_local_path(text: str) -> bool:
    return any(pattern.search(text) for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS)


def _normalize_newlines(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def _redaction_findings(name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            excerpt = match.group(0)[:120]
            if _allowed_public_false_positive(excerpt):
                continue
            findings.append({"path": name, "pattern": replacement, "excerpt": excerpt})
    if _contains_local_path(text):
        findings.append({"path": name, "pattern": "local_path", "excerpt": "local path"})
    lowered = text.lower()
    github_key_marker = "github" + "key"
    access_token_marker = "x-access" + "-token"
    secret_marker = "sk-" + "secret"
    if github_key_marker in lowered or access_token_marker in lowered or secret_marker in lowered:
        findings.append({"path": name, "pattern": "secret_marker", "excerpt": "secret marker"})
    return findings[:20]


def _allowed_public_false_positive(value: str) -> bool:
    lowered = str(value or "").lower()
    return lowered in {"sk-register", "sk-register.json"}


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": path, "pattern": "blocked_metadata_key"})
            findings.extend(_blocked_key_findings(name, child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value[:200]):
            findings.extend(_blocked_key_findings(name, child, f"{prefix}[{index}]"))
    return findings[:20]
