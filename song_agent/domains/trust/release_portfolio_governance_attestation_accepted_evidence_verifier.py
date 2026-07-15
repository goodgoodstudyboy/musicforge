from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_contracts import ACCEPTED_EVIDENCE_BLOCKED_KEYS, ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_STATUSES, accepted_evidence_hash, accepted_evidence_manifest_hash, accepted_evidence_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash


ACCEPTED_EVIDENCE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "accepted-evidence-manifest.json",
    "accepted-evidence-report.json",
    "accepted-evidence-summary.json",
    "data/response-verification-summary.json",
    "data/review-pack-source-summary.json",
    "data/portal-binding-summary.json",
    "data/registry-binding-summary.json",
    "data/attestation-binding-summary.json",
    "data/external-review-public-summary.json",
    "README.txt",
}
LEGAL_SIDECARS = {"accepted-evidence-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ACCEPTED_EVIDENCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_attestation_accepted_evidence(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AcceptedEvidenceVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_attestation_accepted_evidence_verification_report(report: dict[str, Any]) -> None:
    print("MusicForge release portfolio governance attestation accepted evidence verification")
    print(f"status: {report.get('status')}")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"accepted evidence: {summary.get('accepted_evidence_id') or 'none'}")
    print(f"external review: {summary.get('external_review_status') or 'missing'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")


def release_portfolio_governance_attestation_accepted_evidence_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AcceptedEvidenceVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
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
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.summary_doc: dict[str, Any] = {}
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
                if "accepted-evidence-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "accepted-evidence-manifest.json", "manifest", "accepted_evidence_manifest_parse")
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
            self._add_check("zip", "accepted_evidence_zip_open", "failed", "blocking", "Accepted Evidence ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "accepted_evidence_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "accepted_evidence_zip_open", "failed", "blocking", f"Accepted Evidence ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "accepted_evidence_zip_open", "passed", "blocking", "Accepted Evidence ZIP can be opened.")
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
        self._add_check("zip", "accepted_evidence_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "accepted_evidence_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "accepted_evidence_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "accepted_evidence_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "accepted_evidence_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Accepted Evidence entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "accepted_evidence_zip_no_nested_or_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "accepted_evidence_manifest_exists", "failed", "blocking", "accepted-evidence-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "accepted_evidence_manifest_integrity", self.manifest.get("integrity_hash"), accepted_evidence_manifest_hash(self.manifest), "Accepted Evidence manifest integrity")
        self._add_check("manifest", "accepted_evidence_manifest_package_type", "passed" if self.manifest.get("package_type") == ACCEPTED_EVIDENCE_PACKAGE_TYPE else "failed", "blocking", "Manifest package_type is valid." if self.manifest.get("package_type") == ACCEPTED_EVIDENCE_PACKAGE_TYPE else "Manifest package_type is invalid.")
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
        self._add_check("manifest", "accepted_evidence_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "accepted_evidence_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECARS)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "accepted_evidence_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", "accepted_evidence_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "accepted-evidence-report.json", "report", "accepted_evidence_report_parse")
        self.summary_doc = self._read_json_entry(archive, "accepted-evidence-summary.json", "summary", "accepted_evidence_summary_parse")
        for name in (
            "response-verification-summary.json",
            "review-pack-source-summary.json",
            "portal-binding-summary.json",
            "registry-binding-summary.json",
            "attestation-binding-summary.json",
            "external-review-public-summary.json",
        ):
            self.data_docs[name] = self._read_json_entry(archive, f"data/{name}", "data", f"accepted_evidence_data_{name.replace('-', '_').replace('.', '_')}_parse")

    def _verify_documents(self) -> None:
        if not self.report_doc:
            self._add_check("report", "accepted_evidence_report_exists", "failed", "blocking", "accepted-evidence-report.json must contain a JSON object.")
            return
        self._add_hash_check("report", "accepted_evidence_report_integrity", self.report_doc.get("integrity_hash"), accepted_evidence_hash(self.report_doc), "Accepted Evidence report integrity")
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        self._add_hash_check("report", "accepted_evidence_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Accepted Evidence source hash")
        row = self.manifest.get("accepted_evidence") if isinstance(self.manifest.get("accepted_evidence"), dict) else {}
        for label, expected, actual in (
            ("id", row.get("accepted_evidence_id"), self.report_doc.get("accepted_evidence_id")),
            ("integrity_hash", row.get("integrity_hash"), self.report_doc.get("integrity_hash")),
            ("source_hash", row.get("source_hash"), self.report_doc.get("source_hash")),
            ("status", row.get("status"), self.report_doc.get("status")),
            ("manifest_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash")),
        ):
            self._add_exact_check("manifest", f"accepted_evidence_manifest_{label}", expected, actual, f"Manifest {label}")
        public = self.report_doc.get("public_summary") if isinstance(self.report_doc.get("public_summary"), dict) else {}
        summary = self.summary_doc.get("summary") if isinstance(self.summary_doc.get("summary"), dict) else {}
        expected_summary = accepted_evidence_summary(self.report_doc)
        for key, expected in expected_summary.items():
            self._add_exact_check("summary", f"accepted_evidence_summary_{key}", summary.get(key), expected, f"Accepted Evidence summary {key}")
        self._add_exact_check("summary", "accepted_evidence_summary_public_status", self.summary_doc.get("public_summary", {}).get("external_review_status") if isinstance(self.summary_doc.get("public_summary"), dict) else None, public.get("external_review_status"), "Public summary external review status")
        for name, doc in self.data_docs.items():
            self._add_exact_check("data", f"accepted_evidence_data_{name.replace('-', '_').replace('.', '_')}_source_hash", doc.get("source_hash"), self.report_doc.get("source_hash"), f"{name} source_hash")
        self._verify_data_bindings(source, public)

    def _verify_data_bindings(self, source: dict[str, Any], public: dict[str, Any]) -> None:
        response = self.data_docs.get("response-verification-summary.json", {})
        pack = self.data_docs.get("review-pack-source-summary.json", {})
        portal = self.data_docs.get("portal-binding-summary.json", {})
        registry = self.data_docs.get("registry-binding-summary.json", {})
        attestation = self.data_docs.get("attestation-binding-summary.json", {})
        external = self.data_docs.get("external-review-public-summary.json", {})
        for key, source_key in (
            ("response_id", "response_id"),
            ("decision", "response_decision"),
            ("response_status", "response_status"),
            ("verification_status", "response_verification_status"),
            ("verification_hash", "response_verification_hash"),
            ("payload_hash", "response_payload_hash"),
            ("integrity_hash", "response_integrity_hash"),
        ):
            self._add_exact_check("data", f"accepted_evidence_data_response_{key}", response.get(key), source.get(source_key), f"Response verification {key}")
        for key, source_key in (
            ("review_pack_id", "review_pack_id"),
            ("review_pack_source_hash", "review_pack_source_hash"),
            ("response_review_pack_id", "response_review_pack_id"),
            ("response_review_pack_source_hash", "response_review_pack_source_hash"),
            ("review_pack_stale", "review_pack_stale"),
        ):
            self._add_exact_check("data", f"accepted_evidence_data_pack_{key}", pack.get(key), source.get(source_key), f"Review Pack source {key}")
        for key in ("portal_zip_sha256", "portal_zip_size_bytes", "portal_manifest_hash", "portal_verification_hash", "portal_verification_status", "portal_source_hash"):
            self._add_exact_check("data", f"accepted_evidence_data_portal_{key}", portal.get(key), source.get(key), f"Portal binding {key}")
        for key, source_key in (
            ("registry_zip_sha256", "registry_zip_sha256"),
            ("registry_manifest_hash", "registry_manifest_hash"),
            ("registry_verification_hash", "registry_verification_hash"),
            ("registry_verification_status", "registry_verification_status"),
            ("current_entry_id", "registry_current_entry_id"),
            ("current_entry_hash", "registry_current_entry_hash"),
        ):
            self._add_exact_check("data", f"accepted_evidence_data_registry_{key}", registry.get(key), source.get(source_key), f"Registry binding {key}")
        for key, source_key in (
            ("current_certificate_id", "current_certificate_id"),
            ("attestation_zip_sha256", "current_attestation_zip_sha256"),
            ("attestation_manifest_hash", "current_attestation_manifest_hash"),
            ("attestation_verification_hash", "current_attestation_verification_hash"),
            ("attestation_verification_status", "current_attestation_verification_status"),
            ("evidence_vault_zip_sha256", "evidence_vault_zip_sha256"),
            ("evidence_vault_manifest_hash", "evidence_vault_manifest_hash"),
            ("evidence_vault_verification_hash", "evidence_vault_verification_hash"),
            ("evidence_vault_deep_verification_status", "evidence_vault_deep_verification_status"),
            ("final_board_signoff_hash", "final_board_signoff_hash"),
        ):
            self._add_exact_check("data", f"accepted_evidence_data_attestation_{key}", attestation.get(key), source.get(source_key), f"Attestation binding {key}")
        for key in ("external_review_status", "accepted_at", "reviewed_at", "reviewer_label", "response_id", "current_certificate_id", "registry_current_entry_id", "verification_status"):
            self._add_exact_check("data", f"accepted_evidence_data_external_{key}", external.get(key), public.get(key), f"External review public summary {key}")

    def _verify_requirements(self) -> None:
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        public = self.report_doc.get("public_summary") if isinstance(self.report_doc.get("public_summary"), dict) else {}
        self._add_check("requirements", "accepted_evidence_decision_accepted", "passed" if source.get("response_decision") == "accepted" else "failed", "blocking", "Response decision is accepted." if source.get("response_decision") == "accepted" else "Response decision must be accepted.")
        self._add_check("requirements", "accepted_evidence_response_verified", "passed" if source.get("response_verification_status") == "passed" else "failed", "blocking", "Response verification is passed." if source.get("response_verification_status") == "passed" else "Passed response verification is required.")
        self._add_check("requirements", "accepted_evidence_external_status", "passed" if public.get("external_review_status") == "accepted" else "failed", "blocking", "External review status is accepted." if public.get("external_review_status") == "accepted" else "External review status must be accepted.")
        self._add_check("requirements", "accepted_evidence_status_valid", "passed" if self.report_doc.get("status") in ACCEPTED_EVIDENCE_STATUSES else "failed", "blocking", "Accepted Evidence status is valid." if self.report_doc.get("status") in ACCEPTED_EVIDENCE_STATUSES else "Accepted Evidence status is invalid.")
        if self.require_current:
            self._add_check("requirements", "accepted_evidence_require_current", "passed" if self.report_doc.get("status") == "current" and public.get("external_review_status") == "accepted" else "failed", "blocking", "Current accepted evidence is present." if self.report_doc.get("status") == "current" and public.get("external_review_status") == "accepted" else "Current accepted evidence is required.")

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
        self._add_check("redaction", "accepted_evidence_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned entries.")

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
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = accepted_evidence_summary(self.report_doc)
        summary.update({"portfolio_id": self.manifest.get("portfolio_id") or self.report_doc.get("portfolio_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        return sanitize_metadata(
            {
                "schema_version": ACCEPTED_EVIDENCE_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "attestation_accepted_evidence",
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


def _is_forbidden_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")


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


def _redaction_findings(path: str, text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": kind, "excerpt": match.group(0)[:120]})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": "sensitive_value", "pattern": replacement, "excerpt": match.group(0)[:120]})
    return rows


def _blocked_key_findings(path: str, value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(current: Any, trail: str) -> None:
        if isinstance(current, dict):
            for key, item in current.items():
                lowered = str(key).lower()
                if any(marker in lowered for marker in ("api_key", "access_token", "token", "secret", "password", "provider-snapshot", "renderer.json", "source_path", "local_path", "file_path")):
                    rows.append({"path": path, "type": "blocked_key", "key": f"{trail}.{key}" if trail else str(key)})
                walk(item, f"{trail}.{key}" if trail else str(key))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                walk(item, f"{trail}[{index}]")

    walk(value, "")
    return rows
