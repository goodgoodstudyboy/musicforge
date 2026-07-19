# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
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
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_contracts import PORTAL_BLOCKED_KEYS as PORTAL_BLOCKED_KEYS, PORTAL_PACKAGE_TYPE as PORTAL_PACKAGE_TYPE, PORTAL_PAGES as PORTAL_PAGES, portal_manifest_hash as portal_manifest_hash, portal_report_hash as portal_report_hash, portal_verification_summary as portal_verification_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


PORTAL_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "portal-manifest.json",
    "portal-report.json",
    "index.html",
    "current.html",
    "registry.html",
    "revocations.html",
    "verify.html",
    "data/portal-summary.json",
    "data/registry-summary.json",
    "data/current-attestation-summary.json",
    "data/registry-verification-summary.json",
    "data/attestation-verification-summary.json",
    "data/verification-commands.json",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"portal-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
INLINE_EVENT_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
VERIFIER_BLOCKED_KEYS = PORTAL_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


from song_agent.domains.trust import v142_rpgapv_readiness as _v142_rpgapv_readiness
from song_agent.domains.trust.v142_rpgapv_readiness import (
    verify_release_portfolio_governance_attestation_portal,
    write_release_portfolio_governance_attestation_portal_verification_report,
    print_release_portfolio_governance_attestation_portal_verification_report,
    release_portfolio_governance_attestation_portal_verification_exit_code,
    _is_forbidden_public_entry,
    _counts,
    _sha256_file,
    _sha256_entry,
    _sha256_text,
    _contains_local_path,
    _redaction_findings,
    _blocked_key_findings,
)









class _PortalVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        require_registry: bool,
        require_attestation: bool,
        require_accepted_evidence: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.require_registry = require_registry
        self.require_attestation = require_attestation
        self.require_accepted_evidence = require_accepted_evidence
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.manifest: ImplementationDocument = {}
        self.report_doc: ImplementationDocument = {}
        self.data_docs: dict[str, ImplementationDocument] = {}
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> DomainDocument:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "portal-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "portal-manifest.json", "manifest", "portal_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_html(archive)
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "portal_zip_open", "failed", "blocking", "Attestation Portal ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "portal_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "portal_zip_open", "failed", "blocking", f"Attestation Portal ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "portal_zip_open", "passed", "blocking", "Attestation Portal ZIP can be opened.")
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
        self._add_check("zip", "portal_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "portal_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "portal_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "portal_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        required = set(REQUIRED_ENTRIES)
        if "data/accepted-evidence-summary.json" in self.entry_names or "data/accepted-evidence-verification-summary.json" in self.entry_names:
            required.add("data/accepted-evidence-summary.json")
            required.add("data/accepted-evidence-verification-summary.json")
        missing = sorted(required - set(self.entry_names))
        self._add_check("zip", "portal_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required portal entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "portal_zip_no_nested_packages", "failed" if forbidden else "passed", "blocking", "Forbidden nested package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "portal_manifest_exists", "failed", "blocking", "portal-manifest.json is missing or invalid.")
            return
        actual_manifest_hash = portal_manifest_hash(self.manifest)
        self._add_hash_check("manifest", "portal_manifest_integrity", self.manifest.get("integrity_hash"), actual_manifest_hash, "Portal manifest integrity")
        package_type_ok = self.manifest.get("package_type") == PORTAL_PACKAGE_TYPE
        self._add_check("manifest", "portal_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is valid." if package_type_ok else "Manifest package_type is invalid.")
        rows = _as_list(self.manifest.get("files"))
        valid: list[ImplementationDocument] = []
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
        self._add_check("manifest", "portal_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "portal_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Portal file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Portal manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "portal_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", "portal_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "portal-report.json", "report", "portal_report_parse")
        for name in (
            "portal-summary.json",
            "registry-summary.json",
            "current-attestation-summary.json",
            "registry-verification-summary.json",
            "attestation-verification-summary.json",
            "verification-commands.json",
        ):
            self.data_docs[name] = self._read_json_entry(archive, f"data/{name}", "data", f"portal_data_{name.replace('-', '_').replace('.', '_')}_parse")
        if "data/accepted-evidence-summary.json" in self.entry_map:
            self.data_docs["accepted-evidence-summary.json"] = self._read_json_entry(archive, "data/accepted-evidence-summary.json", "data", "portal_data_accepted_evidence_summary_json_parse")
        else:
            self.data_docs["accepted-evidence-summary.json"] = {}
        if "data/accepted-evidence-verification-summary.json" in self.entry_map:
            self.data_docs["accepted-evidence-verification-summary.json"] = self._read_json_entry(archive, "data/accepted-evidence-verification-summary.json", "data", "portal_data_accepted_evidence_verification_summary_json_parse")
        else:
            self.data_docs["accepted-evidence-verification-summary.json"] = {}

    def _verify_documents(self) -> None:
        if self.report_doc:
            self._add_hash_check("report", "portal_report_integrity", self.report_doc.get("integrity_hash"), portal_report_hash(self.report_doc), "Portal Report integrity")
            row = _as_document(self.manifest.get("portal_report"))
            self._add_hash_check("report", "portal_manifest_report_hash", row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
            self._add_hash_check("report", "portal_manifest_report_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest report source hash")
            source = _as_document(self.report_doc.get("source"))
            self._add_hash_check("report", "portal_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Portal Report source hash")
            self._verify_source_bindings(source)
            self._verify_summary_bindings()
        else:
            self._add_check("report", "portal_report_document_exists", "failed", "blocking", "portal-report.json must contain a JSON object.")
        self._verify_data_documents()

    def _verify_source_bindings(self, source: ImplementationDocument) -> None:
        registry_row = _as_document(self.manifest.get("registry"))
        current_row = _as_document(self.manifest.get("current_attestation"))
        for label, expected, actual in (
            ("zip_sha256", registry_row.get("zip_sha256"), source.get("registry_zip_sha256")),
            ("manifest_hash", registry_row.get("manifest_hash"), source.get("registry_manifest_hash")),
            ("verification_hash", registry_row.get("verification_hash"), source.get("registry_verification_hash")),
            ("current_entry_id", registry_row.get("current_entry_id"), source.get("registry_current_entry_id")),
            ("current_entry_hash", registry_row.get("current_entry_hash"), source.get("registry_current_entry_hash")),
        ):
            self._add_exact_check("manifest", f"portal_manifest_registry_{label}", expected, actual, f"Manifest registry {label}")
        for label, expected, actual in (
            ("certificate_id", current_row.get("certificate_id"), source.get("current_certificate_id")),
            ("zip_sha256", current_row.get("zip_sha256"), source.get("current_attestation_zip_sha256")),
            ("manifest_hash", current_row.get("manifest_hash"), source.get("current_attestation_manifest_hash")),
            ("verification_hash", current_row.get("verification_hash"), source.get("current_attestation_verification_hash")),
        ):
            self._add_exact_check("manifest", f"portal_manifest_current_attestation_{label}", expected, actual, f"Manifest current attestation {label}")

    def _verify_summary_bindings(self) -> None:
        report_summary = _as_document(self.report_doc.get("summary"))
        portal_summary = _as_document(self.data_docs.get("portal-summary.json", {}).get("summary"))
        for key in ("current_entry_id", "current_certificate_id", "published_count", "revoked_count", "superseded_count"):
            self._add_exact_check("data", f"portal_data_portal_summary_{key}", portal_summary.get(key), report_summary.get(key), f"Portal summary {key}")

    def _verify_data_documents(self) -> None:
        source = _as_document(self.report_doc.get("source"))
        registry_summary = self.data_docs.get("registry-summary.json", {})
        current_summary = self.data_docs.get("current-attestation-summary.json", {})
        registry_verification = self.data_docs.get("registry-verification-summary.json", {})
        attestation_verification = self.data_docs.get("attestation-verification-summary.json", {})
        commands = self.data_docs.get("verification-commands.json", {})
        accepted = self.data_docs.get("accepted-evidence-summary.json", {})
        accepted_verification = self.data_docs.get("accepted-evidence-verification-summary.json", {})
        for name, doc in self.data_docs.items():
            if not doc and name in {"accepted-evidence-summary.json", "accepted-evidence-verification-summary.json"}:
                continue
            self._add_exact_check("data", f"portal_data_{name.replace('-', '_').replace('.', '_')}_source_hash", doc.get("source_hash"), self.report_doc.get("source_hash"), f"{name} source_hash")
        for key, source_key in (
            ("status", "registry_verification_status"),
            ("zip_sha256", "registry_zip_sha256"),
            ("zip_size_bytes", "registry_zip_size_bytes"),
            ("manifest_hash", "registry_manifest_hash"),
            ("verification_hash", "registry_verification_hash"),
            ("current_entry_id", "registry_current_entry_id"),
            ("current_entry_hash", "registry_current_entry_hash"),
            ("current_entry_status", "registry_current_entry_status"),
            ("current_certificate_id", "current_certificate_id"),
            ("published_count", "published_count"),
            ("revoked_count", "revoked_count"),
            ("superseded_count", "superseded_count"),
        ):
            self._add_exact_check("data", f"portal_data_registry_verification_{key}", registry_verification.get(key), source.get(source_key), f"Registry verification summary {key}")
        for key, source_key in (
            ("status", "attestation_verification_status"),
            ("zip_sha256", "current_attestation_zip_sha256"),
            ("zip_size_bytes", "current_attestation_zip_size_bytes"),
            ("manifest_hash", "current_attestation_manifest_hash"),
            ("verification_hash", "current_attestation_verification_hash"),
            ("live_zip_sha256", "attestation_zip_sha256"),
            ("live_manifest_hash", "attestation_manifest_hash"),
            ("live_verification_hash", "attestation_verification_hash"),
            ("live_verification_status", "attestation_verification_status"),
            ("certificate_id", "current_certificate_id"),
            ("entry_id", "registry_current_entry_id"),
            ("evidence_vault_zip_sha256", "evidence_vault_zip_sha256"),
            ("evidence_vault_manifest_hash", "evidence_vault_manifest_hash"),
            ("evidence_vault_verification_hash", "evidence_vault_verification_hash"),
            ("evidence_vault_deep_verification_status", "evidence_vault_deep_verification_status"),
            ("final_board_signoff_hash", "final_board_signoff_hash"),
        ):
            self._add_exact_check("data", f"portal_data_attestation_verification_{key}", attestation_verification.get(key), source.get(source_key), f"Attestation verification summary {key}")
        for key, source_key in (
            ("current_entry_id", "registry_current_entry_id"),
            ("current_certificate_id", "current_certificate_id"),
            ("published_count", "published_count"),
            ("revoked_count", "revoked_count"),
            ("superseded_count", "superseded_count"),
            ("registry_verification_status", "registry_verification_status"),
            ("registry_zip_sha256", "registry_zip_sha256"),
            ("registry_manifest_hash", "registry_manifest_hash"),
            ("registry_verification_hash", "registry_verification_hash"),
            ("current_entry_hash", "registry_current_entry_hash"),
        ):
            self._add_exact_check("data", f"portal_data_registry_summary_{key}", registry_summary.get(key), source.get(source_key), f"Registry summary {key}")
        for key, verification_key in (
            ("current_entry_id", "current_entry_id"),
            ("current_certificate_id", "current_certificate_id"),
            ("published_count", "published_count"),
            ("revoked_count", "revoked_count"),
            ("superseded_count", "superseded_count"),
            ("registry_verification_status", "status"),
            ("registry_zip_sha256", "zip_sha256"),
            ("registry_manifest_hash", "manifest_hash"),
            ("registry_verification_hash", "verification_hash"),
            ("current_entry_hash", "current_entry_hash"),
        ):
            self._add_exact_check("data", f"portal_data_registry_summary_verification_{key}", registry_summary.get(key), registry_verification.get(verification_key), f"Registry summary {key} verification binding")
        for key, source_key in (
            ("certificate_id", "current_certificate_id"),
            ("entry_id", "registry_current_entry_id"),
            ("attestation_zip_sha256", "current_attestation_zip_sha256"),
            ("attestation_manifest_hash", "current_attestation_manifest_hash"),
            ("attestation_verification_hash", "current_attestation_verification_hash"),
            ("attestation_verification_status", "attestation_verification_status"),
            ("evidence_vault_zip_sha256", "evidence_vault_zip_sha256"),
            ("evidence_vault_manifest_hash", "evidence_vault_manifest_hash"),
            ("evidence_vault_verification_hash", "evidence_vault_verification_hash"),
            ("evidence_vault_deep_verification_status", "evidence_vault_deep_verification_status"),
            ("final_board_signoff_hash", "final_board_signoff_hash"),
        ):
            self._add_exact_check("data", f"portal_data_current_attestation_{key}", current_summary.get(key), source.get(source_key), f"Current attestation summary {key}")
        for key, verification_key in (
            ("certificate_id", "certificate_id"),
            ("entry_id", "entry_id"),
            ("attestation_zip_sha256", "zip_sha256"),
            ("attestation_manifest_hash", "manifest_hash"),
            ("attestation_verification_hash", "verification_hash"),
            ("attestation_verification_status", "status"),
            ("evidence_vault_zip_sha256", "evidence_vault_zip_sha256"),
            ("evidence_vault_manifest_hash", "evidence_vault_manifest_hash"),
            ("evidence_vault_verification_hash", "evidence_vault_verification_hash"),
            ("evidence_vault_deep_verification_status", "evidence_vault_deep_verification_status"),
            ("final_board_signoff_hash", "final_board_signoff_hash"),
        ):
            self._add_exact_check("data", f"portal_data_current_attestation_verification_{key}", current_summary.get(key), attestation_verification.get(verification_key), f"Current attestation summary {key} verification binding")
        external = _as_document(self.manifest.get("external_review"))
        accepted_external = _as_document(accepted.get("external_review"))
        if accepted:
            self._add_exact_check("data", "portal_data_accepted_evidence_source_hash", accepted.get("source_hash"), self.report_doc.get("source_hash"), "Accepted Evidence summary source_hash")
            for key in ("status", "external_review_status", "accepted_evidence_id", "response_id", "reviewer_label", "reviewed_at", "verification_status", "source_hash", "current_entry_id", "current_certificate_id", "accepted_evidence_verification_status", "accepted_evidence_zip_sha256", "accepted_evidence_zip_size_bytes", "accepted_evidence_manifest_hash", "accepted_evidence_verification_report_hash"):
                self._add_exact_check("data", f"portal_data_accepted_evidence_{key}", accepted_external.get(key), external.get(key), f"Accepted Evidence summary {key}")
        if accepted_verification:
            manifest_verification = _as_document(self.manifest.get("external_review_verification"))
            verification = _as_document(accepted_verification.get("accepted_evidence_verification"))
            self._add_exact_check("data", "portal_data_accepted_evidence_verification_source_hash", accepted_verification.get("source_hash"), self.report_doc.get("source_hash"), "Accepted Evidence verification summary source_hash")
            for key in (
                "accepted_evidence_id",
                "accepted_evidence_source_hash",
                "accepted_evidence_status",
                "external_review_status",
                "response_id",
                "current_entry_id",
                "current_certificate_id",
                "accepted_evidence_verification_status",
                "accepted_evidence_zip_sha256",
                "accepted_evidence_zip_size_bytes",
                "accepted_evidence_manifest_hash",
                "accepted_evidence_verification_report_hash",
            ):
                self._add_exact_check("data", f"portal_data_accepted_evidence_verification_{key}", verification.get(key), manifest_verification.get(key), f"Accepted Evidence verification {key}")
            summary_bindings = {
                "accepted_evidence_id": "accepted_evidence_id",
                "accepted_evidence_source_hash": "source_hash",
                "accepted_evidence_status": "status",
                "external_review_status": "external_review_status",
                "response_id": "response_id",
                "current_entry_id": "current_entry_id",
                "current_certificate_id": "current_certificate_id",
                "accepted_evidence_verification_status": "accepted_evidence_verification_status",
                "accepted_evidence_zip_sha256": "accepted_evidence_zip_sha256",
                "accepted_evidence_zip_size_bytes": "accepted_evidence_zip_size_bytes",
                "accepted_evidence_manifest_hash": "accepted_evidence_manifest_hash",
                "accepted_evidence_verification_report_hash": "accepted_evidence_verification_report_hash",
            }
            for verification_key, summary_key in summary_bindings.items():
                self._add_exact_check("data", f"portal_data_accepted_evidence_summary_verification_{verification_key}", accepted_external.get(summary_key), verification.get(verification_key), f"Accepted Evidence summary binding {verification_key}")
            for verification_key, summary_key in summary_bindings.items():
                self._add_exact_check("data", f"portal_data_accepted_evidence_manifest_verification_{verification_key}", external.get(summary_key), verification.get(verification_key), f"Accepted Evidence manifest binding {verification_key}")
        commands_text = json.dumps(commands, ensure_ascii=False, sort_keys=True)
        unsafe_commands = _contains_local_path(commands_text) or "http://" in commands_text.lower() or "https://" in commands_text.lower()
        self._add_check("data", "portal_data_verification_commands_safe", "failed" if unsafe_commands else "passed", "blocking", "verification-commands contains unsafe paths or remote URLs." if unsafe_commands else "verification-commands contains no local paths or remote URLs.")

    def _verify_html(self, archive: zipfile.ZipFile) -> None:
        pages = _as_list(self.manifest.get("pages"))
        page_rows = {str(item.get("path") or ""): item for item in pages if isinstance(item, dict)}
        source_hash = str(self.report_doc.get("source_hash") or "")
        for page in PORTAL_PAGES:
            info = self.entry_map.get(page)
            if info is None:
                self._add_check("html", f"portal_html_{page}_exists", "failed", "blocking", f"{page} is missing.")
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                self._add_check("html", f"portal_html_{page}_utf8", "failed", "blocking", f"{page} is not valid UTF-8: {exc}")
                continue
            self._add_check("html", f"portal_html_{page}_utf8", "passed", "blocking", f"{page} parses as UTF-8.")
            row = page_rows.get(page, {})
            self._add_hash_check("html", f"portal_html_{page}_manifest_hash", row.get("content_hash"), _sha256_text(text), f"{page} manifest content hash")
            self._add_exact_check("html", f"portal_html_{page}_source_hash", row.get("source_hash"), source_hash, f"{page} manifest source hash")
            self._add_check("html", f"portal_html_{page}_source_marker", "passed" if f'data-source-hash="{source_hash}"' in text else "failed", "blocking", f"{page} binds the portal source hash." if f'data-source-hash="{source_hash}"' in text else f"{page} does not bind the portal source hash.")
            lower = text.lower()
            bad = []
            for needle in ("<script", "<iframe", "<object", "<embed", "http://", "https://", "url(", "data:"):
                if needle in lower:
                    bad.append(needle)
            if INLINE_EVENT_RE.search(text):
                bad.append("inline_event")
            if _contains_local_path(text) or ".musicforge/" in lower:
                bad.append("local_path")
            self._add_check("html", f"portal_html_{page}_safe", "failed" if bad else "passed", "blocking", f"{page} contains forbidden HTML content: " + ", ".join(bad) if bad else f"{page} contains no forbidden HTML content.")

    def _verify_requirements(self) -> None:
        source = _as_document(self.report_doc.get("source"))
        if self.require_current:
            self._add_check("requirements", "portal_require_current", "passed" if source.get("registry_current_entry_id") and source.get("current_certificate_id") else "failed", "blocking", "Current published Portal entry is present." if source.get("registry_current_entry_id") and source.get("current_certificate_id") else "Current published Portal entry is required.")
        if self.require_registry:
            self._add_check("requirements", "portal_require_registry", "passed" if source.get("registry_verification_status") == "passed" and source.get("registry_zip_sha256") else "failed", "blocking", "Registry verification evidence is present." if source.get("registry_verification_status") == "passed" and source.get("registry_zip_sha256") else "Passed Registry verification evidence is required.")
        if self.require_attestation:
            self._add_check("requirements", "portal_require_attestation", "passed" if source.get("attestation_verification_status") == "passed" and source.get("current_attestation_zip_sha256") else "failed", "blocking", "Public Attestation verification evidence is present." if source.get("attestation_verification_status") == "passed" and source.get("current_attestation_zip_sha256") else "Passed Public Attestation verification evidence is required.")
        if self.require_accepted_evidence:
            external = _as_document(self.manifest.get("external_review"))
            accepted_verification = self.data_docs.get("accepted-evidence-verification-summary.json", {})
            verification = _as_document(accepted_verification.get("accepted_evidence_verification"))
            ok = (
                bool(self.data_docs.get("accepted-evidence-summary.json"))
                and bool(accepted_verification)
                and external.get("external_review_status") == "accepted"
                and external.get("status") == "current"
                and external.get("verification_status") == "passed"
                and external.get("accepted_evidence_verification_status") == "passed"
                and verification.get("accepted_evidence_verification_status") == "passed"
                and bool(external.get("accepted_evidence_zip_sha256"))
                and bool(external.get("accepted_evidence_manifest_hash"))
                and bool(external.get("accepted_evidence_verification_report_hash"))
                and external.get("accepted_evidence_zip_sha256") == verification.get("accepted_evidence_zip_sha256")
                and external.get("accepted_evidence_manifest_hash") == verification.get("accepted_evidence_manifest_hash")
                and external.get("accepted_evidence_verification_report_hash") == verification.get("accepted_evidence_verification_report_hash")
            )
            self._add_check("requirements", "portal_require_accepted_evidence", "passed" if ok else "failed", "blocking", "Current accepted external review evidence is present." if ok else "Current accepted external review evidence is required.")

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
        self._add_check("redaction", "portal_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
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
        return sanitize_metadata(_as_document(value), blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = _as_document(self.report_doc.get("summary"))
        summary = dict(summary)
        summary.update({"portfolio_id": self.manifest.get("portfolio_id") or self.report_doc.get("portfolio_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": PORTAL_VERIFICATION_SCHEMA_VERSION,
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

_v142_rpgapv_readiness.bind_globals(globals())
