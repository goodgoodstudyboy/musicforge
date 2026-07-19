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
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_contracts import ENTRY_STATUSES as ENTRY_STATUSES, REGISTRY_BLOCKED_KEYS as REGISTRY_BLOCKED_KEYS, REGISTRY_PACKAGE_TYPE as REGISTRY_PACKAGE_TYPE, registry_entry_hash as registry_entry_hash, registry_hash as registry_hash, registry_manifest_hash as registry_manifest_hash, registry_report_hash as registry_report_hash, registry_summary as registry_summary, registry_verification_summary as registry_verification_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS


REGISTRY_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"manifest.json", "registry.json", "registry-report.json", "package-index.json", "chain-of-custody.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = REGISTRY_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_attestation_registry(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_published: bool = False,
    require_no_revoked_current: bool = False,
    require_accepted_evidence: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _RegistryVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        require_published=require_published,
        require_no_revoked_current=require_no_revoked_current,
        require_accepted_evidence=require_accepted_evidence,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_release_portfolio_governance_attestation_registry_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_attestation_registry_verification_report(report: DomainDocument) -> None:
    summary = registry_verification_summary(report)
    print("MusicForge release portfolio governance attestation registry verification")
    print(f"status: {summary.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"current entry: {summary.get('current_entry_id') or 'none'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = _as_list(report.get(key))
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_attestation_registry_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _RegistryVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        require_published: bool,
        require_no_revoked_current: bool,
        require_accepted_evidence: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.require_published = require_published
        self.require_no_revoked_current = require_no_revoked_current
        self.require_accepted_evidence = require_accepted_evidence
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.manifest: ImplementationDocument = {}
        self.registry: ImplementationDocument = {}
        self.report_doc: ImplementationDocument = {}
        self.package_index: ImplementationDocument = {}
        self.chain: ImplementationDocument = {}
        self.accepted_evidence: ImplementationDocument = {}
        self.accepted_evidence_verification: ImplementationDocument = {}
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
                if "manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "registry_manifest_parse")
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
            self._add_check("zip", "registry_zip_open", "failed", "blocking", "Attestation Registry ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "registry_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "registry_zip_open", "failed", "blocking", f"Attestation Registry ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "registry_zip_open", "passed", "blocking", "Attestation Registry ZIP can be opened.")
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
        self._add_check("zip", "registry_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "registry_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "registry_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "registry_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        required = set(REQUIRED_ENTRIES)
        if "data/accepted-evidence-summary.json" in self.entry_names or "data/accepted-evidence-verification-summary.json" in self.entry_names:
            required.add("data/accepted-evidence-summary.json")
            required.add("data/accepted-evidence-verification-summary.json")
        missing = sorted(required - set(self.entry_names))
        self._add_check("zip", "registry_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required registry entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "registry_zip_no_nested_packages", "failed" if forbidden else "passed", "blocking", "Forbidden nested package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "registry_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        actual_manifest_hash = registry_manifest_hash(self.manifest)
        self._add_check("manifest", "registry_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Registry manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Registry manifest integrity hash does not match.")
        package_type_ok = self.manifest.get("package_type") == REGISTRY_PACKAGE_TYPE
        self._add_check("manifest", "registry_manifest_package_type", "passed" if package_type_ok else "failed", "blocking", "Manifest package_type is valid." if package_type_ok else "Manifest package_type is invalid.")
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
        self._add_check("manifest", "registry_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "registry_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Registry file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Registry manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "registry_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "registry_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.registry = self._read_json_entry(archive, "registry.json", "registry", "registry_parse")
        self.report_doc = self._read_json_entry(archive, "registry-report.json", "report", "registry_report_parse")
        self.package_index = self._read_json_entry(archive, "package-index.json", "package_index", "registry_package_index_parse")
        self.chain = self._read_json_entry(archive, "chain-of-custody.json", "chain", "registry_chain_parse")
        if "data/accepted-evidence-summary.json" in self.entry_map:
            self.accepted_evidence = self._read_json_entry(archive, "data/accepted-evidence-summary.json", "data", "registry_data_accepted_evidence_summary_parse")
        else:
            self.accepted_evidence = {}
        if "data/accepted-evidence-verification-summary.json" in self.entry_map:
            self.accepted_evidence_verification = self._read_json_entry(archive, "data/accepted-evidence-verification-summary.json", "data", "registry_data_accepted_evidence_verification_summary_parse")
        else:
            self.accepted_evidence_verification = {}

    def _verify_documents(self) -> None:
        if self.registry:
            self._add_hash_check("registry", "registry_integrity", self.registry.get("integrity_hash"), registry_hash(self.registry), "Registry integrity")
            row = _as_document(self.manifest.get("registry"))
            self._add_hash_check("registry", "registry_manifest_registry_hash", row.get("integrity_hash"), self.registry.get("integrity_hash"), "Manifest registry hash")
            entries = _as_list(self.registry.get("entries"))
            ids = [str(item.get("entry_id") or "") for item in entries if isinstance(item, dict)]
            self._add_check("registry", "registry_entry_ids_unique", "passed" if len(ids) == len(set(ids)) else "failed", "blocking", "Registry entry IDs are unique." if len(ids) == len(set(ids)) else "Registry entry IDs are duplicated.")
            certificate_map: dict[str, set[str]] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    self._add_check("registry", "registry_entry_shape", "failed", "blocking", "Registry entry is not an object.")
                    continue
                entry_id = str(entry.get("entry_id") or "")
                self._add_hash_check("registry", f"{entry_id}_integrity", entry.get("integrity_hash"), registry_entry_hash(entry), f"Entry {entry_id} integrity")
                self._add_check("registry", f"{entry_id}_status", "passed" if entry.get("status") in ENTRY_STATUSES else "failed", "blocking", f"Entry {entry_id} status is valid." if entry.get("status") in ENTRY_STATUSES else f"Entry {entry_id} status is invalid.")
                cert_id = str(entry.get("certificate_id") or "")
                zip_sha = str((_as_document(entry.get("source"))).get("attestation_zip_sha256") or "")
                if cert_id:
                    certificate_map.setdefault(cert_id, set()).add(zip_sha)
                if entry.get("status") == "superseded":
                    target = str(entry.get("superseded_by_entry_id") or "")
                    self._add_check("registry", f"{entry_id}_superseded_target", "passed" if target and target in ids else "failed", "blocking", f"Entry {entry_id} superseded target exists." if target and target in ids else f"Entry {entry_id} superseded target is missing.")
            ambiguous = [cert for cert, hashes in certificate_map.items() if len(hashes) > 1]
            self._add_check("registry", "registry_certificate_ids_not_ambiguous", "failed" if ambiguous else "passed", "blocking", "Certificate IDs map to multiple attestation ZIP hashes: " + ", ".join(ambiguous[:5]) if ambiguous else "Certificate IDs are not ambiguous.")
            current_id = str(self.registry.get("current_entry_id") or "")
            current = _find_entry(self.registry, current_id) if current_id else {}
            self._add_check("registry", "registry_current_entry_exists", "passed" if not current_id or current else "failed", "blocking", "Current entry exists when set." if not current_id or current else "Current entry is missing.")
            self._add_check("registry", "registry_current_entry_published", "passed" if not current_id or current.get("status") == "published" else "failed", "blocking", "Current entry is published." if not current_id or current.get("status") == "published" else "Current entry is not published.")
            self._add_check("registry", "registry_current_not_revoked", "passed" if not current_id or current.get("status") != "revoked" else "failed", "blocking", "Current entry is not revoked." if not current_id or current.get("status") != "revoked" else "Current entry is revoked.")
        else:
            self._add_check("registry", "registry_document_exists", "failed", "blocking", "registry.json must contain a JSON object.")
        if self.report_doc:
            self._add_hash_check("report", "registry_report_integrity", self.report_doc.get("integrity_hash"), registry_report_hash(self.report_doc), "Registry Report integrity")
            row = _as_document(self.manifest.get("registry_report"))
            self._add_hash_check("report", "registry_manifest_report_hash", row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
            self._add_hash_check("report", "registry_manifest_report_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest report source hash")
            source = _as_document(self.report_doc.get("source"))
            self._add_hash_check("report", "registry_report_source_registry_hash", source.get("registry_hash"), self.registry.get("integrity_hash"), "Report registry source hash")
            expected_source = _report_source_from_registry(self.registry)
            for key in (
                "current_entry_id",
                "current_entry_hash",
                "current_attestation_zip_sha256",
                "current_attestation_manifest_hash",
                "current_attestation_verification_hash",
                "evidence_vault_zip_sha256",
                "final_board_signoff_hash",
            ):
                self._add_exact_check("report", f"registry_report_source_{key}", source.get(key), expected_source.get(key), f"Report source {key}")
            expected = registry_summary(self.registry)
            summary = _as_document(self.report_doc.get("summary"))
            for key in ("entry_count", "published_count", "revoked_count", "superseded_count", "current_entry_id"):
                self._add_value_check("report", f"registry_report_summary_{key}", summary.get(key), expected.get(key), f"Report summary {key}")
        else:
            self._add_check("report", "registry_report_document_exists", "failed", "blocking", "registry-report.json must contain a JSON object.")
        if self.package_index:
            self._add_hash_check("package_index", "registry_package_index_integrity", self.package_index.get("integrity_hash"), stable_hash({key: value for key, value in self.package_index.items() if key != "integrity_hash"}), "Package index integrity")
            self._add_hash_check("package_index", "registry_package_index_source_hash", self.package_index.get("source_hash"), self.report_doc.get("source_hash"), "Package index source hash")
            self._add_exact_check("package_index", "registry_package_index_portfolio_id", self.package_index.get("portfolio_id"), self.registry.get("portfolio_id"), "Package index portfolio_id")
            expected_items = _package_index_items_from_registry(self.registry)
            actual_items = _as_list(self.package_index.get("items"))
            self._add_hash_check("package_index", "registry_package_index_items_match_registry", stable_hash(expected_items), stable_hash(actual_items), "Package index items derived from registry")
            summary = _as_document(self.package_index.get("summary"))
            self._add_exact_check("package_index", "registry_package_index_summary_entry_count", summary.get("entry_count"), len(expected_items), "Package index entry_count")
        else:
            self._add_check("package_index", "registry_package_index_document_exists", "failed", "blocking", "package-index.json must contain a JSON object.")
        if self.chain:
            self._add_hash_check("chain", "registry_chain_integrity", self.chain.get("integrity_hash"), stable_hash({key: value for key, value in self.chain.items() if key != "integrity_hash"}), "Chain of custody integrity")
            self._add_hash_check("chain", "registry_chain_source_hash", self.chain.get("source_hash"), self.report_doc.get("source_hash"), "Chain of custody source hash")
            self._add_exact_check("chain", "registry_chain_portfolio_id", self.chain.get("portfolio_id"), self.registry.get("portfolio_id"), "Chain portfolio_id")
            chain_summary = _as_document(self.chain.get("summary"))
            events = _as_list(self.chain.get("events"))
            latest_event_type = events[-1].get("type") if events and isinstance(events[-1], dict) else None
            self._add_exact_check("chain", "registry_chain_summary_current_entry_id", chain_summary.get("current_entry_id"), self.registry.get("current_entry_id"), "Chain current_entry_id")
            self._add_exact_check("chain", "registry_chain_summary_event_count", chain_summary.get("event_count"), len(events), "Chain event_count")
            self._add_exact_check("chain", "registry_chain_summary_latest_event_type", chain_summary.get("latest_event_type"), latest_event_type, "Chain latest_event_type")
        else:
            self._add_check("chain", "registry_chain_document_exists", "failed", "blocking", "chain-of-custody.json must contain a JSON object.")
        if self.accepted_evidence:
            external = _as_document(self.manifest.get("external_review"))
            evidence_external = _as_document(self.accepted_evidence.get("external_review"))
            self._add_exact_check("accepted_evidence", "registry_accepted_evidence_source_hash", self.accepted_evidence.get("source_hash"), self.report_doc.get("source_hash"), "Accepted Evidence summary source_hash")
            for key in ("status", "external_review_status", "accepted_evidence_id", "response_id", "reviewer_label", "reviewed_at", "verification_status", "source_hash", "current_entry_id", "current_certificate_id", "accepted_evidence_verification_status", "accepted_evidence_zip_sha256", "accepted_evidence_zip_size_bytes", "accepted_evidence_manifest_hash", "accepted_evidence_verification_report_hash"):
                self._add_exact_check("accepted_evidence", f"registry_accepted_evidence_{key}", evidence_external.get(key), external.get(key), f"Accepted Evidence summary {key}")
        if self.accepted_evidence_verification:
            external = _as_document(self.manifest.get("external_review"))
            manifest_verification = _as_document(self.manifest.get("external_review_verification"))
            evidence_external = _as_document(self.accepted_evidence.get("external_review"))
            verification = _as_document(self.accepted_evidence_verification.get("accepted_evidence_verification"))
            self._add_exact_check("accepted_evidence", "registry_accepted_evidence_verification_source_hash", self.accepted_evidence_verification.get("source_hash"), self.report_doc.get("source_hash"), "Accepted Evidence verification summary source_hash")
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
                self._add_exact_check("accepted_evidence", f"registry_accepted_evidence_verification_{key}", verification.get(key), manifest_verification.get(key), f"Accepted Evidence verification {key}")
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
                self._add_exact_check("accepted_evidence", f"registry_accepted_evidence_summary_verification_{verification_key}", evidence_external.get(summary_key), verification.get(verification_key), f"Accepted Evidence summary binding {verification_key}")
            for verification_key, summary_key in summary_bindings.items():
                self._add_exact_check("accepted_evidence", f"registry_accepted_evidence_manifest_verification_{verification_key}", external.get(summary_key), verification.get(verification_key), f"Accepted Evidence manifest binding {verification_key}")

    def _verify_requirements(self) -> None:
        current_id = str(self.registry.get("current_entry_id") or "")
        current = _find_entry(self.registry, current_id) if current_id else {}
        if self.require_current:
            self._add_check("requirements", "registry_require_current", "passed" if current_id and current else "failed", "blocking", "Current Registry entry is present." if current_id and current else "Current Registry entry is required.")
        if self.require_published:
            self._add_check("requirements", "registry_require_published", "passed" if current and current.get("status") == "published" else "failed", "blocking", "Current Registry entry is published." if current and current.get("status") == "published" else "Published current Registry entry is required.")
        if self.require_no_revoked_current:
            self._add_check("requirements", "registry_require_no_revoked_current", "passed" if not current or current.get("status") != "revoked" else "failed", "blocking", "Current Registry entry is not revoked." if not current or current.get("status") != "revoked" else "Current Registry entry is revoked.")
        if self.require_accepted_evidence:
            external = _as_document(self.manifest.get("external_review"))
            verification = _as_document(self.accepted_evidence_verification.get("accepted_evidence_verification"))
            ok = (
                bool(self.accepted_evidence)
                and bool(self.accepted_evidence_verification)
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
            self._add_check("requirements", "registry_require_accepted_evidence", "passed" if ok else "failed", "blocking", "Current accepted external review evidence is present." if ok else "Current accepted external review evidence is required.")

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
        self._add_check("redaction", "registry_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

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
        summary = registry_summary(self.registry)
        summary.update({"portfolio_id": self.manifest.get("portfolio_id") or self.registry.get("portfolio_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": REGISTRY_VERIFICATION_SCHEMA_VERSION,
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

    def _add_value_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected is not None and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _report_source_from_registry(registry: ImplementationDocument) -> ImplementationDocument:
    current = _find_entry(registry, str(registry.get("current_entry_id") or "")) if registry.get("current_entry_id") else {}
    source = current.get("source") if current and isinstance(current.get("source"), dict) else {}
    return {
        "registry_hash": registry.get("integrity_hash"),
        "current_entry_id": registry.get("current_entry_id"),
        "current_entry_hash": current.get("integrity_hash") if current else None,
        "current_attestation_zip_sha256": _as_document(source).get("attestation_zip_sha256") if current else None,
        "current_attestation_manifest_hash": _as_document(source).get("attestation_manifest_hash") if current else None,
        "current_attestation_verification_hash": _as_document(source).get("attestation_verification_hash") if current else None,
        "evidence_vault_zip_sha256": _as_document(source).get("evidence_vault_zip_sha256") if current else None,
        "final_board_signoff_hash": _as_document(source).get("final_board_signoff_hash") if current else None,
    }


def _package_index_items_from_registry(registry: ImplementationDocument) -> list[ImplementationDocument]:
    entries = _as_list(registry.get("entries"))
    items: list[ImplementationDocument] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item = {"entry_id": entry.get("entry_id"), "certificate_id": entry.get("certificate_id"), "status": entry.get("status")}
        source = _as_document(entry.get("source"))
        item.update(source)
        items.append(item)
    return sanitize_metadata(items, blocked_keys=VERIFIER_BLOCKED_KEYS)


def _find_entry(registry: ImplementationDocument, entry_id: str) -> ImplementationDocument:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}


def _is_forbidden_public_entry(name: str) -> bool:
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


def _redaction_findings(path: str, text: str) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": kind, "excerpt": match.group(0)[:120]})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": "sensitive_value", "pattern": replacement, "excerpt": match.group(0)[:120]})
    return rows


def _blocked_key_findings(path: str, value: Any) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []

    def walk(current: Any, trail: str) -> None:
        if isinstance(current, dict):
            for key, item in current.items():
                lowered = str(key).lower()
                if any(marker in lowered for marker in ("api_key", "access_token", "token", "secret", "password", "provider-snapshot", "renderer.json")):
                    rows.append({"path": path, "type": "blocked_key", "key": f"{trail}.{key}" if trail else str(key)})
                walk(item, f"{trail}.{key}" if trail else str(key))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                walk(item, f"{trail}[{index}]")

    walk(value, "")
    return rows
