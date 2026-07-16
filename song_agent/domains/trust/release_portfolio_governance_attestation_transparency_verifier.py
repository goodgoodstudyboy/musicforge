from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument
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
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_contracts import TRANSPARENCY_BLOCKED_KEYS as TRANSPARENCY_BLOCKED_KEYS, TRANSPARENCY_PACKAGE_TYPE as TRANSPARENCY_PACKAGE_TYPE, TRANSPARENCY_FEED_PACKAGE_TYPE as TRANSPARENCY_FEED_PACKAGE_TYPE, TRANSPARENCY_REPORT_PACKAGE_TYPE as TRANSPARENCY_REPORT_PACKAGE_TYPE, _build_events as _build_events, _build_notices as _build_notices, transparency_event_hash as transparency_event_hash, transparency_feed_hash as transparency_feed_hash, transparency_manifest_hash as transparency_manifest_hash, transparency_notice_hash as transparency_notice_hash, transparency_summary as transparency_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash


TRANSPARENCY_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 300
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "transparency-manifest.json",
    "transparency-feed.json",
    "transparency-report.json",
    "README.txt",
    "data/current-public-state.json",
    "data/package-fingerprints.json",
    "data/registry-binding-summary.json",
    "data/portal-binding-summary.json",
    "data/attestation-binding-summary.json",
    "data/accepted-evidence-binding-summary.json",
}
LEGAL_SIDECAR_ENTRIES = {"transparency-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = TRANSPARENCY_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_attestation_transparency(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_accepted_evidence: bool = False,
    require_no_revoked_current: bool = False,
    require_contiguous_chain: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _TransparencyVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        require_accepted_evidence=require_accepted_evidence,
        require_no_revoked_current=require_no_revoked_current,
        require_contiguous_chain=require_contiguous_chain,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_release_portfolio_governance_attestation_transparency_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_attestation_transparency_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge release portfolio governance attestation transparency verification")
    print(f"status: {report.get('status')}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"current entry: {summary.get('current_entry_id') or 'none'}")
    print(f"events: {summary.get('event_count', 0)}")
    print(f"notices: {summary.get('notice_count', 0)}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")


def release_portfolio_governance_attestation_transparency_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _TransparencyVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        require_accepted_evidence: bool,
        require_no_revoked_current: bool,
        require_contiguous_chain: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.require_accepted_evidence = require_accepted_evidence
        self.require_no_revoked_current = require_no_revoked_current
        self.require_contiguous_chain = require_contiguous_chain
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
        self.feed_doc: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.data_docs: dict[str, dict[str, Any]] = {}
        self.notice_docs: dict[str, dict[str, Any]] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "transparency-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "transparency-manifest.json", "manifest", "transparency_manifest_parse")
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
            self._add_check("zip", "transparency_zip_open", "failed", "blocking", "Attestation Transparency ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "transparency_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "transparency_zip_open", "failed", "blocking", f"Attestation Transparency ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "transparency_zip_open", "passed", "blocking", "Attestation Transparency ZIP can be opened.")
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
        self._add_check("zip", "transparency_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "transparency_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "transparency_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "transparency_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "transparency_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Attestation Transparency entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "transparency_zip_no_nested_or_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden package entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "transparency_manifest_exists", "failed", "blocking", "transparency-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "transparency_manifest_integrity", self.manifest.get("integrity_hash"), transparency_manifest_hash(self.manifest), "Attestation Transparency manifest integrity")
        self._add_check("manifest", "transparency_manifest_package_type", "passed" if self.manifest.get("package_type") == TRANSPARENCY_PACKAGE_TYPE else "failed", "blocking", "Manifest package_type is valid." if self.manifest.get("package_type") == TRANSPARENCY_PACKAGE_TYPE else "Manifest package_type is invalid.")
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
        self._add_check("manifest", "transparency_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "transparency_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "transparency_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", "transparency_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.feed_doc = self._read_json_entry(archive, "transparency-feed.json", "feed", "transparency_feed_parse")
        self.report_doc = self._read_json_entry(archive, "transparency-report.json", "report", "transparency_report_parse")
        for name in (
            "current-public-state.json",
            "package-fingerprints.json",
            "registry-binding-summary.json",
            "portal-binding-summary.json",
            "attestation-binding-summary.json",
            "accepted-evidence-binding-summary.json",
        ):
            self.data_docs[name] = self._read_json_entry(archive, f"data/{name}", "data", f"transparency_data_{name.replace('-', '_').replace('.', '_')}_parse")
        for name in self.entry_names:
            if name.startswith("notices/") and name.endswith(".json"):
                self.notice_docs[name] = self._read_json_entry(archive, name, "notice", f"transparency_notice_{Path(name).stem}_parse")

    def _verify_documents(self) -> None:
        if not self.feed_doc:
            self._add_check("feed", "transparency_feed_exists", "failed", "blocking", "transparency-feed.json must contain a JSON object.")
            return
        if not self.report_doc:
            self._add_check("report", "transparency_report_exists", "failed", "blocking", "transparency-report.json must contain a JSON object.")
            return
        self._add_hash_check("feed", "transparency_feed_integrity", self.feed_doc.get("integrity_hash"), transparency_feed_hash(self.feed_doc), "Attestation Transparency Feed integrity")
        source = self.feed_doc.get("source") if isinstance(self.feed_doc.get("source"), dict) else {}
        current_state = self.feed_doc.get("current_public_state") if isinstance(self.feed_doc.get("current_public_state"), dict) else {}
        self._add_hash_check("feed", "transparency_feed_source_hash", self.feed_doc.get("source_hash"), stable_hash(source), "Feed source hash")
        self._add_hash_check("feed", "transparency_feed_public_state_hash", source.get("public_state_hash"), stable_hash(current_state), "Feed public state hash")
        self._add_check("feed", "transparency_feed_package_type", "passed" if self.feed_doc.get("package_type") == TRANSPARENCY_FEED_PACKAGE_TYPE else "failed", "blocking", "Feed package_type is valid." if self.feed_doc.get("package_type") == TRANSPARENCY_FEED_PACKAGE_TYPE else "Feed package_type is invalid.")
        self._verify_event_chain()
        self._verify_notices()
        self._verify_event_semantics(source, current_state)
        self._verify_notice_semantics(source, current_state)

        self._add_hash_check("report", "transparency_report_integrity", self.report_doc.get("integrity_hash"), _transparency_report_hash(self.report_doc), "Attestation Transparency Report integrity")
        report_source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        self._add_hash_check("report", "transparency_report_source_hash", self.report_doc.get("source_hash"), stable_hash(report_source), "Report source hash")
        self._add_check("report", "transparency_report_package_type", "passed" if self.report_doc.get("package_type") == TRANSPARENCY_REPORT_PACKAGE_TYPE else "failed", "blocking", "Report package_type is valid." if self.report_doc.get("package_type") == TRANSPARENCY_REPORT_PACKAGE_TYPE else "Report package_type is invalid.")
        self._add_exact_check("report", "transparency_report_feed_hash", report_source.get("feed_hash"), self.feed_doc.get("integrity_hash"), "Report feed_hash")
        self._add_exact_check("report", "transparency_report_feed_source_hash", report_source.get("feed_source_hash"), self.feed_doc.get("source_hash"), "Report feed_source_hash")
        self._add_exact_check("report", "transparency_report_public_state_hash", report_source.get("public_state_hash"), source.get("public_state_hash"), "Report public_state_hash")

        feed_row = self.manifest.get("feed") if isinstance(self.manifest.get("feed"), dict) else {}
        report_row = self.manifest.get("report") if isinstance(self.manifest.get("report"), dict) else {}
        self._add_exact_check("manifest", "transparency_manifest_source_hash", self.manifest.get("source_hash"), self.feed_doc.get("source_hash"), "Manifest source_hash")
        self._add_exact_check("manifest", "transparency_manifest_feed_integrity", feed_row.get("integrity_hash"), self.feed_doc.get("integrity_hash"), "Manifest feed integrity hash")
        self._add_exact_check("manifest", "transparency_manifest_feed_source_hash", feed_row.get("source_hash"), self.feed_doc.get("source_hash"), "Manifest feed source hash")
        self._add_exact_check("manifest", "transparency_manifest_report_integrity", report_row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report integrity hash")
        self._add_exact_check("manifest", "transparency_manifest_report_source_hash", report_row.get("source_hash"), self.report_doc.get("source_hash"), "Manifest report source hash")
        self._verify_data_bindings(source, current_state)

    def _verify_event_chain(self) -> None:
        events = self.feed_doc.get("events") if isinstance(self.feed_doc.get("events"), list) else []
        previous = ""
        ids: set[str] = set()
        problems: list[str] = []
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                problems.append(f"events[{index}] is not an object")
                continue
            event_id = str(event.get("event_id") or "")
            if not event_id or event_id in ids:
                problems.append(f"{event_id or index} duplicate/missing id")
            ids.add(event_id)
            if event.get("previous_event_hash") != previous:
                problems.append(f"{event_id or index} previous hash mismatch")
            if event.get("event_hash") != transparency_event_hash(event):
                problems.append(f"{event_id or index} hash mismatch")
            previous = str(event.get("event_hash") or "")
        severity = "blocking" if self.require_contiguous_chain or problems else "blocking"
        self._add_check("feed", "transparency_event_chain_contiguous", "failed" if problems else "passed", severity, "Event chain problems: " + "; ".join(problems[:5]) if problems else "Transparency event chain is contiguous.")

    def _verify_notices(self) -> None:
        events = self.feed_doc.get("events") if isinstance(self.feed_doc.get("events"), list) else []
        event_ids = {str(event.get("event_id") or "") for event in events if isinstance(event, dict)}
        feed_notices = self.feed_doc.get("notices") if isinstance(self.feed_doc.get("notices"), list) else []
        by_id = {str(item.get("notice_id") or ""): item for item in feed_notices if isinstance(item, dict)}
        problems: list[str] = []
        for notice_id, notice in by_id.items():
            if notice.get("integrity_hash") != transparency_notice_hash(notice):
                problems.append(f"{notice_id} hash mismatch")
            if not set(str(item) for item in notice.get("source_event_ids", []) if item).issubset(event_ids):
                problems.append(f"{notice_id} references unknown events")
            path = f"notices/{notice_id}.json"
            disk_notice = self.notice_docs.get(path)
            if disk_notice != notice:
                problems.append(f"{notice_id} file mismatch")
        missing = [f"notices/{notice_id}.json" for notice_id in by_id if f"notices/{notice_id}.json" not in self.entry_names]
        problems.extend(missing)
        self._add_check("feed", "transparency_notices_integrity", "failed" if problems else "passed", "blocking", "Notice problems: " + "; ".join(problems[:5]) if problems else "Transparency notices are bound to feed events.")

    def _verify_event_semantics(self, source: ImplementationDocument, current_state: ImplementationDocument) -> None:
        actual_events = self.feed_doc.get("events") if isinstance(self.feed_doc.get("events"), list) else []
        expected_events = _build_events(
            str(self.feed_doc.get("portfolio_id") or ""),
            str(self.feed_doc.get("attestation_profile") or "public_summary"),
            current_state,
            source,
            now=str(self.feed_doc.get("generated_at") or self.generated_at),
        )
        expected_semantics = [_event_semantics(event) for event in expected_events if isinstance(event, dict)]
        actual_semantics = [_event_semantics(event) for event in actual_events if isinstance(event, dict)]
        problems = _semantic_mismatches("event", expected_semantics, actual_semantics)
        self._add_check(
            "feed",
            "transparency_event_semantics_match",
            "failed" if problems else "passed",
            "blocking",
            "Transparency event semantics mismatch: " + "; ".join(problems[:5]) if problems else "Transparency events match the package public state.",
        )

    def _verify_notice_semantics(self, source: ImplementationDocument, current_state: ImplementationDocument) -> None:
        actual_notices = self.feed_doc.get("notices") if isinstance(self.feed_doc.get("notices"), list) else []
        expected_events = _build_events(
            str(self.feed_doc.get("portfolio_id") or ""),
            str(self.feed_doc.get("attestation_profile") or "public_summary"),
            current_state,
            source,
            now=str(self.feed_doc.get("generated_at") or self.generated_at),
        )
        expected_notices = _build_notices(
            str(self.feed_doc.get("portfolio_id") or ""),
            str(self.feed_doc.get("attestation_profile") or "public_summary"),
            current_state,
            source,
            expected_events,
            {},
            now=str(self.feed_doc.get("generated_at") or self.generated_at),
        )
        expected_semantics = [_notice_semantics(notice) for notice in expected_notices if isinstance(notice, dict)]
        actual_semantics = [_notice_semantics(notice) for notice in actual_notices if isinstance(notice, dict)]
        problems = _semantic_mismatches("notice", expected_semantics, actual_semantics)
        self._add_check(
            "feed",
            "transparency_notice_semantics_match",
            "failed" if problems else "passed",
            "blocking",
            "Transparency notice semantics mismatch: " + "; ".join(problems[:5]) if problems else "Transparency notices match the package public state and events.",
        )

    def _verify_data_bindings(self, source: ImplementationDocument, current_state: ImplementationDocument) -> None:
        current = self.data_docs.get("current-public-state.json", {})
        package = self.data_docs.get("package-fingerprints.json", {})
        registry = self.data_docs.get("registry-binding-summary.json", {})
        portal = self.data_docs.get("portal-binding-summary.json", {})
        attestation = self.data_docs.get("attestation-binding-summary.json", {})
        accepted = self.data_docs.get("accepted-evidence-binding-summary.json", {})
        for name, doc in self.data_docs.items():
            source_key = "feed_source_hash" if name == "accepted-evidence-binding-summary.json" else "source_hash"
            self._add_exact_check("data", f"transparency_data_{name.replace('-', '_').replace('.', '_')}_source_hash", doc.get(source_key), self.feed_doc.get("source_hash"), f"{name} {source_key}")
        self._add_hash_check("data", "transparency_data_current_public_state_hash", current.get("public_state_hash"), stable_hash(current.get("current_public_state") if isinstance(current.get("current_public_state"), dict) else {}), "Current public state data hash")
        self._add_exact_check("data", "transparency_data_current_public_state_value", current.get("current_public_state"), current_state, "Current public state data")
        for key, value in source.items():
            self._add_exact_check("data", f"transparency_data_package_{key}", package.get(key), value, f"Package fingerprint {key}")
        registry_state = current_state.get("registry") if isinstance(current_state.get("registry"), dict) else {}
        portal_state = current_state.get("portal") if isinstance(current_state.get("portal"), dict) else {}
        attestation_state = current_state.get("public_attestation") if isinstance(current_state.get("public_attestation"), dict) else {}
        accepted_state = current_state.get("accepted_evidence") if isinstance(current_state.get("accepted_evidence"), dict) else {}
        for key, value in registry_state.items():
            self._add_exact_check("data", f"transparency_data_registry_{key}", registry.get(key), value, f"Registry binding {key}")
        for key, value in portal_state.items():
            self._add_exact_check("data", f"transparency_data_portal_{key}", portal.get(key), value, f"Portal binding {key}")
        for key, value in attestation_state.items():
            self._add_exact_check("data", f"transparency_data_attestation_{key}", attestation.get(key), value, f"Attestation binding {key}")
        if accepted_state:
            for key, value in accepted_state.items():
                self._add_exact_check("data", f"transparency_data_accepted_evidence_{key}", accepted.get(key), value, f"Accepted Evidence binding {key}")
            for key, source_key in (
                ("status", "accepted_evidence_status"),
                ("external_review_status", "accepted_evidence_external_review_status"),
                ("accepted_evidence_id", "accepted_evidence_id"),
                ("source_hash", "accepted_evidence_source_hash"),
                ("accepted_evidence_zip_sha256", "accepted_evidence_zip_sha256"),
                ("accepted_evidence_manifest_hash", "accepted_evidence_manifest_hash"),
                ("accepted_evidence_verification_status", "accepted_evidence_verification_status"),
                ("accepted_evidence_verification_report_hash", "accepted_evidence_verification_report_hash"),
            ):
                self._add_exact_check("data", f"transparency_data_accepted_source_{key}", accepted.get(key), source.get(source_key), f"Accepted Evidence source binding {key}")

    def _verify_requirements(self) -> None:
        source = self.feed_doc.get("source") if isinstance(self.feed_doc.get("source"), dict) else {}
        self._add_check("requirements", "transparency_registry_verification_passed", "passed" if source.get("registry_verification_status") == "passed" else "failed", "blocking", "Registry verification is passed." if source.get("registry_verification_status") == "passed" else "Registry verification must be passed.")
        self._add_check("requirements", "transparency_attestation_verification_passed", "passed" if source.get("attestation_verification_status") == "passed" else "failed", "blocking", "Public Attestation verification is passed." if source.get("attestation_verification_status") == "passed" else "Public Attestation verification must be passed.")
        self._add_check("requirements", "transparency_portal_verification_passed", "passed" if source.get("portal_verification_status") == "passed" else "failed", "blocking", "Portal verification is passed." if source.get("portal_verification_status") == "passed" else "Portal verification must be passed.")
        if self.require_current:
            current_ok = bool(source.get("registry_current_entry_id")) and source.get("registry_current_entry_status") == "published"
            self._add_check("requirements", "transparency_require_current", "passed" if current_ok else "failed", "blocking", "Current published registry entry exists." if current_ok else "A current published Registry entry is required.")
        if self.require_no_revoked_current:
            not_revoked = source.get("registry_current_entry_status") != "revoked"
            self._add_check("requirements", "transparency_require_no_revoked_current", "passed" if not_revoked else "failed", "blocking", "Current entry is not revoked." if not_revoked else "Current entry must not be revoked.")
        if self.require_accepted_evidence:
            accepted_ok = (
                source.get("accepted_evidence_status") == "current"
                and source.get("accepted_evidence_external_review_status") == "accepted"
                and source.get("accepted_evidence_verification_status") == "passed"
                and bool(source.get("accepted_evidence_zip_sha256"))
                and bool(source.get("accepted_evidence_manifest_hash"))
                and bool(source.get("accepted_evidence_verification_report_hash"))
            )
            self._add_check("requirements", "transparency_require_accepted_evidence", "passed" if accepted_ok else "failed", "blocking", "Current accepted external review evidence is verified." if accepted_ok else "Current accepted external review evidence is required.")

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
        self._add_check("redaction", "transparency_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned entries.")

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
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = transparency_summary(self.feed_doc)
        summary.update({"portfolio_id": self.manifest.get("portfolio_id") or self.feed_doc.get("portfolio_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        return sanitize_metadata(
            {
                "schema_version": TRANSPARENCY_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "attestation_transparency",
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


def _transparency_report_hash(report: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in {"integrity_hash", "generated_at", "updated_at"}})


def _event_semantics(event: ImplementationDocument) -> ImplementationDocument:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "severity": event.get("severity"),
        "portfolio_id": event.get("portfolio_id"),
        "attestation_profile": event.get("attestation_profile"),
        "source": {
            "public_state_hash": source.get("public_state_hash"),
            "registry_current_entry_id": source.get("registry_current_entry_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "portal_manifest_hash": source.get("portal_manifest_hash"),
            "accepted_evidence_id": source.get("accepted_evidence_id"),
        },
        "public_references": summary.get("public_references") if isinstance(summary.get("public_references"), dict) else {},
    }


def _notice_semantics(notice: ImplementationDocument) -> ImplementationDocument:
    return {
        "notice_id": notice.get("notice_id"),
        "notice_type": notice.get("notice_type"),
        "severity": notice.get("severity"),
        "portfolio_id": notice.get("portfolio_id"),
        "attestation_profile": notice.get("attestation_profile"),
        "source_event_ids": list(notice.get("source_event_ids") or []) if isinstance(notice.get("source_event_ids"), list) else [],
        "public_references": notice.get("public_references") if isinstance(notice.get("public_references"), dict) else {},
    }


def _semantic_mismatches(kind: str, expected: list[ImplementationDocument], actual: list[ImplementationDocument]) -> list[str]:
    problems: list[str] = []
    if len(actual) != len(expected):
        problems.append(f"{kind} count {len(actual)} != expected {len(expected)}")
    for index, expected_item in enumerate(expected):
        if index >= len(actual):
            problems.append(f"{kind}[{index}] missing")
            continue
        actual_item = actual[index]
        for key, expected_value in expected_item.items():
            actual_value = actual_item.get(key)
            if key == "public_references" and kind == "notice":
                if not _reference_subset_matches(expected_value, actual_value, notice_type=str(expected_item.get("notice_type") or "")):
                    problems.append(f"{kind}[{index}].{key} mismatch")
                continue
            if actual_value != expected_value:
                problems.append(f"{kind}[{index}].{key} mismatch")
    return problems


def _reference_subset_matches(expected: Any, actual: Any, *, notice_type: str) -> bool:
    expected_refs = expected if isinstance(expected, dict) else {}
    actual_refs = actual if isinstance(actual, dict) else {}
    for key, value in expected_refs.items():
        if actual_refs.get(key) != value:
            return False
    extra_keys = set(actual_refs) - set(expected_refs)
    return not extra_keys or (notice_type == "public_state_refreshed" and extra_keys <= {"previous_state_hash"})


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


def _redaction_findings(path: str, text: str) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": kind, "excerpt": match.group(0)[:120]})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": "sensitive_value", "pattern": replacement, "excerpt": match.group(0)[:120]})
    return rows


def _blocked_key_findings(path: str, value: Any) -> list[ImplementationDocument]:
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
