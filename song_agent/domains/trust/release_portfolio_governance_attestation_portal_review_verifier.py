from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_review_contracts import PORTAL_REVIEW_BLOCKED_KEYS as PORTAL_REVIEW_BLOCKED_KEYS, PORTAL_REVIEW_PACK_PACKAGE_TYPE as PORTAL_REVIEW_PACK_PACKAGE_TYPE, PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE as PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE, response_integrity_hash as response_integrity_hash, response_payload_hash as response_payload_hash, response_summary as response_summary, review_manifest_hash as review_manifest_hash, review_pack_hash as review_pack_hash, review_pack_summary as review_pack_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


PORTAL_REVIEW_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
PACK_REQUIRED_ENTRIES = {
    "review-pack-manifest.json",
    "review-pack.json",
    "reviewer-guide.md",
    "portal-review-form.json",
    "portal-review-form.md",
    "data/portal-summary.json",
    "data/registry-verification-summary.json",
    "data/attestation-verification-summary.json",
    "data/portal-verification-summary.json",
    "data/response-schema.json",
    "README.txt",
}
RESPONSE_REQUIRED_ENTRIES = {
    "response-manifest.json",
    "review-response.json",
    "review-response.md",
    "data/review-pack-source.json",
    "data/portal-binding-summary.json",
    "README.txt",
}
LEGAL_PACK_SIDECARS = {"review-pack-manifest.json"}
LEGAL_RESPONSE_SIDECARS = {"response-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PORTAL_REVIEW_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_attestation_portal_review_pack(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _ReviewZipVerifier(
        Path(zip_path),
        package_kind="pack",
        strict=strict,
        require_current=require_current,
        require_pack=False,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def verify_release_portfolio_governance_attestation_portal_response(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_pack: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _ReviewZipVerifier(
        Path(zip_path),
        package_kind="response",
        strict=strict,
        require_current=require_current,
        require_pack=require_pack,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def verify_response_document(response: dict[str, Any], pack: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    verifier = _ResponseDocumentVerifier(response, pack, now=now)
    return verifier.run()


def write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def write_release_portfolio_governance_attestation_portal_response_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_attestation_portal_review_pack_verification_report(report: dict[str, Any]) -> None:
    _print_report("MusicForge release portfolio governance attestation portal review pack verification", report)


def print_release_portfolio_governance_attestation_portal_response_verification_report(report: dict[str, Any]) -> None:
    _print_report("MusicForge release portfolio governance attestation portal response verification", report)


def release_portfolio_governance_attestation_portal_review_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _ReviewZipVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        package_kind: str,
        strict: bool,
        require_current: bool,
        require_pack: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.package_kind = package_kind
        self.strict = strict
        self.require_current = require_current
        self.require_pack = require_pack
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.manifest_name = "review-pack-manifest.json" if package_kind == "pack" else "response-manifest.json"
        self.main_doc_name = "review-pack.json" if package_kind == "pack" else "review-response.json"
        self.expected_package_type = PORTAL_REVIEW_PACK_PACKAGE_TYPE if package_kind == "pack" else PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE
        self.required_entries = PACK_REQUIRED_ENTRIES if package_kind == "pack" else RESPONSE_REQUIRED_ENTRIES
        self.legal_sidecars = LEGAL_PACK_SIDECARS if package_kind == "pack" else LEGAL_RESPONSE_SIDECARS
        self.check_prefix = "portal_review_pack" if package_kind == "pack" else "portal_review_response"
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.manifest: dict[str, Any] = {}
        self.main_doc: dict[str, Any] = {}
        self.data_docs: dict[str, dict[str, Any]] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if self.manifest_name in self.entry_map:
                    self.manifest = self._read_json_entry(archive, self.manifest_name, "manifest", f"{self.check_prefix}_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", f"{self.check_prefix}_zip_open", "failed", "blocking", "ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", f"{self.check_prefix}_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", f"{self.check_prefix}_zip_open", "failed", "blocking", f"ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", f"{self.check_prefix}_zip_open", "passed", "blocking", "ZIP can be opened.")
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
        self._add_check("zip", f"{self.check_prefix}_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", f"{self.check_prefix}_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", f"{self.check_prefix}_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", f"{self.check_prefix}_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(self.required_entries - set(self.entry_names))
        self._add_check("zip", f"{self.check_prefix}_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", f"{self.check_prefix}_zip_no_nested_or_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", f"{self.check_prefix}_manifest_exists", "failed", "blocking", f"{self.manifest_name} is missing or invalid.")
            return
        self._add_hash_check("manifest", f"{self.check_prefix}_manifest_integrity", self.manifest.get("integrity_hash"), review_manifest_hash(self.manifest), "Manifest integrity")
        package_type_ok = self.manifest.get("package_type") == self.expected_package_type
        self._add_check("manifest", f"{self.check_prefix}_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is valid." if package_type_ok else "Manifest package_type is invalid.")
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
            if not isinstance(item.get("size_bytes"), int) or int(item.get("size_bytes") or 0) < 0:
                errors.append(f"{path or index} has invalid size")
            if not HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                errors.append(f"{path or index} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(item.get("size_bytes"), int) and HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                valid.append(item)
        self._add_check("manifest", f"{self.check_prefix}_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", f"{self.check_prefix}_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(self.legal_sidecars)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", f"{self.check_prefix}_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", f"{self.check_prefix}_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.main_doc = self._read_json_entry(archive, self.main_doc_name, "document", f"{self.check_prefix}_document_parse")
        data_names = (
            ("data/portal-summary.json", "portal-summary.json"),
            ("data/registry-verification-summary.json", "registry-verification-summary.json"),
            ("data/attestation-verification-summary.json", "attestation-verification-summary.json"),
            ("data/portal-verification-summary.json", "portal-verification-summary.json"),
            ("data/response-schema.json", "response-schema.json"),
        ) if self.package_kind == "pack" else (
            ("data/review-pack-source.json", "review-pack-source.json"),
            ("data/portal-binding-summary.json", "portal-binding-summary.json"),
        )
        for path, key in data_names:
            self.data_docs[key] = self._read_json_entry(archive, path, "data", f"{self.check_prefix}_data_{key.replace('-', '_').replace('.', '_')}_parse")

    def _verify_documents(self) -> None:
        if self.package_kind == "pack":
            self._verify_pack_documents()
        else:
            self._verify_response_documents()

    def _verify_pack_documents(self) -> None:
        pack = self.main_doc
        if not pack:
            self._add_check("document", "portal_review_pack_document_exists", "failed", "blocking", "review-pack.json must contain a JSON object.")
            return
        self._add_hash_check("document", "portal_review_pack_integrity", pack.get("integrity_hash"), review_pack_hash(pack), "Review Pack integrity")
        source = _as_document(pack.get("source"))
        self._add_hash_check("document", "portal_review_pack_source_hash", pack.get("source_hash"), stable_hash(source), "Review Pack source hash")
        row = _as_document(self.manifest.get("review_pack"))
        for label, expected, actual in (
            ("integrity_hash", row.get("integrity_hash"), pack.get("integrity_hash")),
            ("source_hash", row.get("source_hash"), pack.get("source_hash")),
            ("manifest_source_hash", self.manifest.get("source_hash"), pack.get("source_hash")),
        ):
            self._add_exact_check("manifest", f"portal_review_pack_manifest_{label}", expected, actual, f"Manifest {label}")
        portal_row = _as_document(self.manifest.get("portal"))
        for key in (
            "portal_zip_sha256",
            "portal_zip_size_bytes",
            "portal_manifest_hash",
            "portal_verification_hash",
            "portal_verification_status",
            "portal_source_hash",
            "registry_zip_sha256",
            "registry_manifest_hash",
            "registry_verification_hash",
            "current_attestation_zip_sha256",
            "current_attestation_manifest_hash",
            "current_attestation_verification_hash",
            "evidence_vault_zip_sha256",
            "final_board_signoff_hash",
        ):
            self._add_exact_check("manifest", f"portal_review_pack_manifest_portal_{key}", portal_row.get(key), source.get(key), f"Manifest portal {key}")
        self._verify_pack_data_bindings(source, pack)

    def _verify_pack_data_bindings(self, source: ImplementationDocument, pack: ImplementationDocument) -> None:
        for name, doc in self.data_docs.items():
            self._add_exact_check("data", f"portal_review_pack_data_{name.replace('-', '_').replace('.', '_')}_source_hash", doc.get("source_hash"), pack.get("source_hash"), f"{name} source_hash")
        portal_verification = self.data_docs.get("portal-verification-summary.json", {})
        registry_verification = self.data_docs.get("registry-verification-summary.json", {})
        attestation_verification = self.data_docs.get("attestation-verification-summary.json", {})
        response_schema = self.data_docs.get("response-schema.json", {})
        for key, source_key in (
            ("status", "portal_verification_status"),
            ("zip_sha256", "portal_zip_sha256"),
            ("zip_size_bytes", "portal_zip_size_bytes"),
            ("manifest_hash", "portal_manifest_hash"),
            ("verification_hash", "portal_verification_hash"),
            ("portal_source_hash", "portal_source_hash"),
        ):
            self._add_exact_check("data", f"portal_review_pack_data_portal_verification_{key}", portal_verification.get(key), source.get(source_key), f"Portal verification summary {key}")
        for key, source_key in (
            ("status", "registry_verification_status"),
            ("zip_sha256", "registry_zip_sha256"),
            ("manifest_hash", "registry_manifest_hash"),
            ("verification_hash", "registry_verification_hash"),
            ("current_entry_id", "registry_current_entry_id"),
            ("current_entry_hash", "registry_current_entry_hash"),
        ):
            self._add_exact_check("data", f"portal_review_pack_data_registry_verification_{key}", registry_verification.get(key), source.get(source_key), f"Registry verification summary {key}")
        for key, source_key in (
            ("status", "current_attestation_verification_status"),
            ("zip_sha256", "current_attestation_zip_sha256"),
            ("manifest_hash", "current_attestation_manifest_hash"),
            ("verification_hash", "current_attestation_verification_hash"),
            ("certificate_id", "current_certificate_id"),
            ("evidence_vault_zip_sha256", "evidence_vault_zip_sha256"),
            ("final_board_signoff_hash", "final_board_signoff_hash"),
        ):
            self._add_exact_check("data", f"portal_review_pack_data_attestation_verification_{key}", attestation_verification.get(key), source.get(source_key), f"Attestation verification summary {key}")
        self._add_exact_check("data", "portal_review_pack_response_schema_review_pack_id", response_schema.get("review_pack_id"), pack.get("review_pack_id"), "Response schema review_pack_id")
        self._add_exact_check("data", "portal_review_pack_response_schema_source_hash", response_schema.get("review_pack_source_hash"), pack.get("source_hash"), "Response schema source hash")

    def _verify_response_documents(self) -> None:
        response = self.main_doc
        if not response:
            self._add_check("document", "portal_review_response_document_exists", "failed", "blocking", "review-response.json must contain a JSON object.")
            return
        self._add_hash_check("document", "portal_review_response_payload_hash", response.get("payload_hash"), response_payload_hash(response), "Response payload hash")
        self._add_hash_check("document", "portal_review_response_integrity", response.get("integrity_hash"), response_integrity_hash(response), "Response integrity")
        self._add_exact_check("manifest", "portal_review_response_manifest_payload_hash", self.manifest.get("payload_hash"), response.get("payload_hash"), "Manifest payload hash")
        self._add_exact_check("manifest", "portal_review_response_manifest_source_hash", self.manifest.get("review_pack_source_hash") or self.manifest.get("source_hash"), response.get("review_pack_source_hash"), "Manifest review pack source hash")
        source_doc = self.data_docs.get("review-pack-source.json", {})
        binding = self.data_docs.get("portal-binding-summary.json", {})
        self._add_exact_check("data", "portal_review_response_data_pack_source_hash", source_doc.get("source_hash"), response.get("review_pack_source_hash"), "Response pack source hash")
        source = _as_document(source_doc.get("source"))
        for key in (
            "portal_zip_sha256",
            "portal_zip_size_bytes",
            "portal_manifest_hash",
            "portal_verification_hash",
            "portal_verification_status",
            "portal_source_hash",
            "registry_zip_sha256",
            "registry_manifest_hash",
            "registry_verification_hash",
            "current_attestation_zip_sha256",
            "current_attestation_manifest_hash",
            "current_attestation_verification_hash",
            "evidence_vault_zip_sha256",
            "final_board_signoff_hash",
        ):
            self._add_exact_check("data", f"portal_review_response_data_binding_{key}", binding.get(key), source.get(key), f"Portal binding {key}")
            manifest_portal = _as_document(self.manifest.get("portal"))
            self._add_exact_check("manifest", f"portal_review_response_manifest_portal_{key}", manifest_portal.get(key), binding.get(key), f"Manifest portal binding {key}")
        decision_ok = response.get("decision") in {"accepted", "needs_changes", "rejected"}
        self._add_check("document", "portal_review_response_decision", "passed" if decision_ok else "failed", "blocking", "Response decision is valid." if decision_ok else "Response decision is invalid.")
        reviewer_ok = isinstance(response.get("reviewer"), dict) and bool(response.get("reviewer", {}).get("name"))
        self._add_check("document", "portal_review_response_reviewer", "passed" if reviewer_ok else "failed", "blocking", "Response reviewer is present." if reviewer_ok else "Response reviewer.name is required.")
        if response.get("decision") == "accepted":
            high = _unresolved_high_findings(response)
            self._add_check("document", "portal_review_response_accepted_no_unresolved_high_findings", "failed" if high else "passed", "blocking", f"Accepted response has unresolved high findings: {len(high)}" if high else "Accepted response has no unresolved high or critical findings.")

    def _verify_requirements(self) -> None:
        if self.package_kind == "pack":
            source = _as_document(self.main_doc.get("source"))
            if self.require_current:
                ok = bool(source.get("registry_current_entry_id")) and source.get("portal_verification_status") == "passed"
                self._add_check("requirements", "portal_review_pack_require_current", "passed" if ok else "failed", "blocking", "Current verified Portal Review Pack is present." if ok else "Current verified Portal Review Pack is required.")
        else:
            response = self.main_doc
            if self.require_pack:
                source_doc = self.data_docs.get("review-pack-source.json", {})
                ok = bool(source_doc.get("source_hash")) and source_doc.get("source_hash") == response.get("review_pack_source_hash")
                self._add_check("requirements", "portal_review_response_require_pack", "passed" if ok else "failed", "blocking", "Response is bound to a Review Pack source." if ok else "Response must be bound to a Review Pack source.")
            if self.require_current:
                ok = response.get("status") != "stale" and bool(response.get("review_pack_source_hash"))
                self._add_check("requirements", "portal_review_response_require_current", "passed" if ok else "failed", "blocking", "Response source is current." if ok else "Current Review Pack response source is required.")

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
        self._add_check("redaction", f"{self.check_prefix}_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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
        summary = review_pack_summary(self.main_doc) if self.package_kind == "pack" else response_summary(self.main_doc)
        summary.update({"blocker_count": len(blockers), "warning_count": len(warnings)})
        return sanitize_metadata(
            {
                "schema_version": PORTAL_REVIEW_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": self.package_kind,
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


class _ResponseDocumentVerifier:
    def __init__(self, response: ImplementationDocument, pack: ImplementationDocument, *, now: str | None) -> None:
        self.response = sanitize_metadata(response, blocked_keys=VERIFIER_BLOCKED_KEYS)
        self.pack = sanitize_metadata(pack, blocked_keys=VERIFIER_BLOCKED_KEYS)
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        self._add_hash_check("response", "portal_review_response_payload_hash", self.response.get("payload_hash"), response_payload_hash(self.response), "Response payload hash")
        self._add_hash_check("response", "portal_review_response_integrity", self.response.get("integrity_hash"), response_integrity_hash(self.response), "Response integrity")
        self._add_exact_check("response", "portal_review_response_pack_source_current", self.response.get("review_pack_source_hash"), self.pack.get("source_hash"), "Response source hash")
        self._add_check("response", "portal_review_response_decision", "passed" if self.response.get("decision") in {"accepted", "needs_changes", "rejected"} else "failed", "blocking", "Decision is valid.")
        reviewer_ok = isinstance(self.response.get("reviewer"), dict) and bool(self.response.get("reviewer", {}).get("name"))
        self._add_check("response", "portal_review_response_reviewer", "passed" if reviewer_ok else "failed", "blocking", "Reviewer is present." if reviewer_ok else "reviewer.name is required.")
        if self.response.get("decision") == "accepted":
            high = _unresolved_high_findings(self.response)
            self._add_check("response", "portal_review_response_accepted_no_unresolved_high_findings", "failed" if high else "passed", "blocking", f"Accepted response has unresolved high findings: {len(high)}" if high else "Accepted response has no unresolved high or critical findings.")
        text = json.dumps({"response": self.response}, ensure_ascii=False, sort_keys=True, default=str)
        self.redaction_findings.extend(_redaction_findings("review-response.json", text))
        self.redaction_findings.extend(_blocked_key_findings("review-response.json", self.response))
        self._add_check("redaction", "portal_review_response_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", "Sensitive values found." if self.redaction_findings else "No sensitive values found.")
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        return sanitize_metadata(
            {
                "schema_version": PORTAL_REVIEW_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "response_document",
                "summary": response_summary(self.response),
                "checks": self.checks,
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


def _print_report(title: str, report: ImplementationDocument) -> None:
    print(title)
    print(f"status: {report.get('status')}")
    summary = _as_document(report.get("summary"))
    if summary.get("portfolio_id"):
        print(f"portfolio: {summary.get('portfolio_id')}")
    if summary.get("review_pack_id"):
        print(f"review pack: {summary.get('review_pack_id')}")
    if summary.get("response_id"):
        print(f"response: {summary.get('response_id')}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


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


def _redaction_findings(name: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": "local_path", "excerpt": match.group(0)[:120]})
    return findings


def _blocked_key_findings(name: str, value: Any, path: str = "") -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"entry": name, "pattern": "blocked_key", "excerpt": key_path[:120]})
            findings.extend(_blocked_key_findings(name, item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{path}[{index}]"))
    return findings


def _unresolved_high_findings(response: ImplementationDocument) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for finding in response.get("findings", []) if isinstance(response.get("findings"), list) else []:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").lower()
        status = str(finding.get("status") or "open").lower()
        if severity in {"high", "critical"} and status not in {"resolved", "accepted_risk"}:
            rows.append(finding)
    return rows
