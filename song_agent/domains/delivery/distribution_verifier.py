from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import csv as csv
import hashlib as hashlib
import io as io
import json as json
import re as re
import struct as struct
import sys as sys
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution_export import DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS as DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS
from song_agent.domains.delivery.distribution_layout import RESERVED_LAYOUT_PATHS as RESERVED_LAYOUT_PATHS, effective_file_naming as effective_file_naming, layout_payload_hash as layout_payload_hash, validate_layout_path as validate_layout_path
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_checklist import checklist_payload_hash as checklist_payload_hash, checklist_summary as checklist_summary
from song_agent.domains.delivery.distribution_templates import DistributionTemplateError as DistributionTemplateError, template_content_hash as template_content_hash, template_summary as template_summary, validate_template_pack as validate_template_pack
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.quality.audio_encoding import detect_audio_format_bytes as detect_audio_format_bytes, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_audio_summary_integrity_ok as encoded_audio_summary_integrity_ok, encoded_audio_summary_uses_fake as encoded_audio_summary_uses_fake, encoded_manifest_uses_fake as encoded_manifest_uses_fake
from song_agent.domains.creation.encoded_audio_acceptance import encoded_audio_acceptance_summary_hash as encoded_audio_acceptance_summary_hash, encoded_audio_acceptance_summary_integrity_ok as encoded_audio_acceptance_summary_integrity_ok, encoded_audio_review_integrity_hash as encoded_audio_review_integrity_hash, encoded_audio_review_integrity_ok as encoded_audio_review_integrity_ok
from song_agent.domains.delivery.format_decisions import distribution_target_format_decision_coverage as distribution_target_format_decision_coverage, format_distribution_decision_summary_integrity_ok as format_distribution_decision_summary_integrity_ok
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.rights_clearance import verify_rights_summary_evidence as verify_rights_summary_evidence


DISTRIBUTION_VERIFICATION_SCHEMA_VERSION = 1
DISTRIBUTION_VERIFICATION_PACKAGE_TYPE = "musicforge_distribution_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json", "package.json", "release.json", "tracklist.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def verify_distribution_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_audio: bool = False,
    require_artwork: bool = False,
    require_encoded_audio: bool = False,
    require_encoded_audio_review: bool = False,
    require_format_decision: bool = False,
    require_rights_clearance: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _DistributionPackageVerifier(
        Path(zip_path),
        strict=strict,
        require_audio=require_audio,
        require_artwork=require_artwork,
        require_encoded_audio=require_encoded_audio,
        require_encoded_audio_review=require_encoded_audio_review,
        require_format_decision=require_format_decision,
        require_rights_clearance=require_rights_clearance,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def distribution_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "package_id": summary.get("package_id"),
            "release_id": summary.get("release_id"),
            "target_id": summary.get("target_id"),
            "profile_id": summary.get("profile_id"),
            "entry_count": summary.get("entry_count", 0),
            "checked_file_count": summary.get("checked_file_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def write_distribution_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))


def print_distribution_verification_report(report: dict[str, Any]) -> None:
    summary = distribution_verification_summary(report)
    print("MusicForge distribution package verification")
    print(f"status: {summary.get('status')}")
    print(f"package: {summary.get('package_id') or 'unknown'}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"target: {summary.get('target_id') or 'unknown'}")
    print(f"profile: {summary.get('profile_id') or 'unknown'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"checked files: {summary.get('checked_file_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = _as_list(report.get(key))
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            check_id = item.get("check_id", "unknown") if isinstance(item, dict) else "unknown"
            message = item.get("message", str(item)) if isinstance(item, dict) else str(item)
            print(f"  [{check_id}] {message}")
        if len(items) > 10:
            print(f"  ... {len(items) - 10} more")


def distribution_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _DistributionPackageVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_audio: bool,
        require_artwork: bool,
        require_encoded_audio: bool,
        require_encoded_audio_review: bool,
        require_format_decision: bool,
        require_rights_clearance: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_audio = require_audio
        self.require_artwork = require_artwork
        self.require_encoded_audio = require_encoded_audio
        self.require_encoded_audio_review = require_encoded_audio_review
        self.require_format_decision = require_format_decision
        self.require_rights_clearance = require_rights_clearance
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.package: dict[str, Any] = {}
        self.release: dict[str, Any] = {}
        self.tracklist: dict[str, Any] = {}
        self.template: dict[str, Any] = {}
        self.template_summary_doc: dict[str, Any] = {}
        self.checklist: dict[str, Any] = {}
        self.layout: dict[str, Any] = {}
        self.encoded_audio_summary: dict[str, Any] = {}
        self.encoded_audio_manifests: dict[str, dict[str, Any]] = {}
        self.encoded_audio_acceptance_summary: dict[str, Any] = {}
        self.encoded_audio_acceptance_reviews: dict[str, dict[str, Any]] = {}
        self.format_decision_summary: dict[str, Any] = {}
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
                if "distribution-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "distribution-manifest.json", "manifest", "distribution_manifest_parse")
                self._verify_manifest(archive)
                self._read_json_documents(archive)
                self._verify_package_release()
                self._verify_signoff()
                self._verify_template_and_checklist()
                self._verify_layout(archive)
                self._verify_metadata_and_artwork(archive)
                self._verify_encoded_audio(archive)
                self._verify_encoded_audio_acceptance(archive)
                self._verify_format_decision(archive)
                self._verify_rights_clearance(archive)
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "zip_open", "failed", "blocking", "Distribution ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.", count=self.zip_size_bytes)
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "zip_open", "failed", "blocking", f"Distribution ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "zip_open", "passed", "blocking", "Distribution ZIP can be opened.")
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
        self._add_check("zip", "zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.", count=self.total_uncompressed_size)
        self._add_check("zip", "zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.", count=len(self.entry_infos))
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.", count=len(unsafe))
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.", count=len(duplicates))
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required distribution entries exist.", count=len(missing))

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "distribution_manifest_exists", "failed", "blocking", "distribution-manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "distribution_manifest_exists", "passed", "blocking", "distribution-manifest.json exists.")
        missing_fields = [field for field in ("schema_version", "package_id", "release_id", "target_id", "profile_id", "source_hash", "qa_source_hash") if self.manifest.get(field) in (None, "")]
        if not isinstance(self.manifest.get("files"), list):
            missing_fields.append("files")
        if not isinstance(self.manifest.get("summary"), dict):
            missing_fields.append("summary")
        self._add_check("manifest", "distribution_manifest_schema", "failed" if missing_fields else "passed", "blocking", "Missing manifest fields: " + ", ".join(missing_fields) if missing_fields else "Distribution manifest schema has required fields.", count=len(missing_fields))
        rows = _as_list(self.manifest.get("files"))
        valid_rows: list[dict[str, Any]] = []
        shape_errors: list[str] = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                shape_errors.append(f"files[{index}] is not an object")
                continue
            path = str(item.get("path") or "")
            size = item.get("size_bytes")
            sha = str(item.get("sha256") or "")
            if not _is_safe_zip_entry(path):
                shape_errors.append(f"{path or f'files[{index}]'} has unsafe path")
            if not isinstance(size, int) or size < 0:
                shape_errors.append(f"{path or f'files[{index}]'} has invalid size")
            if not HEX_SHA256.fullmatch(sha):
                shape_errors.append(f"{path or f'files[{index}]'} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(size, int) and size >= 0 and HEX_SHA256.fullmatch(sha):
                valid_rows.append(item)
        self._add_check("manifest", "distribution_manifest_files_shape", "failed" if shape_errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(shape_errors[:5]) if shape_errors else "Manifest file rows are valid.", count=len(shape_errors))
        mismatches: list[str] = []
        for item in valid_rows:
            path = str(item["path"])
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(f"{path} missing from ZIP")
                continue
            actual_size = int(info.file_size or 0)
            actual_sha = _sha256_entry(archive, info)
            expected_size = int(item["size_bytes"])
            expected_sha = str(item["sha256"])
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_size == expected_size and actual_sha == expected_sha else "failed"})
            if actual_size != expected_size:
                mismatches.append(f"{path} size mismatch")
            if actual_sha != expected_sha:
                mismatches.append(f"{path} hash mismatch")
        self._add_check("manifest", "distribution_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Distribution file mismatches: " + "; ".join(mismatches[:5]) if mismatches else "Distribution manifest files match ZIP bytes.", count=len(mismatches))
        allowed = {str(item.get("path")) for item in valid_rows}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "distribution_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.", count=len(extra))
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "distribution_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.", count=len(spoofed))

    def _read_json_documents(self, archive: zipfile.ZipFile) -> None:
        if "distribution-signoff.json" in self.entry_map:
            self.signoff = self._read_json_entry(archive, "distribution-signoff.json", "signoff", "distribution_signoff_parse")
        if "package.json" in self.entry_map:
            self.package = self._read_json_entry(archive, "package.json", "package", "distribution_package_parse")
        if "release.json" in self.entry_map:
            self.release = self._read_json_entry(archive, "release.json", "release", "distribution_release_parse")
        if "tracklist.json" in self.entry_map:
            self.tracklist = self._read_json_entry(archive, "tracklist.json", "tracklist", "distribution_tracklist_parse")
        if "template-pack.json" in self.entry_map:
            self.template = self._read_json_entry(archive, "template-pack.json", "template", "distribution_template_pack_parse")
        if "template-summary.json" in self.entry_map:
            self.template_summary_doc = self._read_json_entry(archive, "template-summary.json", "template", "distribution_template_summary_parse")
        if "docs/checklist.json" in self.entry_map:
            self.checklist = self._read_json_entry(archive, "docs/checklist.json", "checklist", "distribution_checklist_parse")
        if "layout/manifest-layout.json" in self.entry_map:
            self.layout = self._read_json_entry(archive, "layout/manifest-layout.json", "layout", "distribution_layout_sidecar_parse")
        if "encoded-audio/summary.json" in self.entry_map:
            self.encoded_audio_summary = self._read_json_entry(archive, "encoded-audio/summary.json", "encoded_audio", "distribution_encoded_audio_summary_parse")
        if "encoded-audio-acceptance/summary.json" in self.entry_map:
            self.encoded_audio_acceptance_summary = self._read_json_entry(archive, "encoded-audio-acceptance/summary.json", "encoded_audio_acceptance", "distribution_encoded_audio_acceptance_summary_parse")
        if "format-decision/target-decision-summary.json" in self.entry_map:
            self.format_decision_summary = self._read_json_entry(archive, "format-decision/target-decision-summary.json", "format_decision", "distribution_format_decision_summary_parse")
        encoded = _as_document(self.manifest.get("encoded_audio"))
        for row in encoded.get("profiles", []) if isinstance(encoded.get("profiles"), list) else []:
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("profile_id") or "")
            path = str(row.get("manifest_path") or f"encoded-audio/manifests/{profile_id}.json")
            if path in self.entry_map:
                self.encoded_audio_manifests[profile_id] = self._read_json_entry(archive, path, "encoded_audio", "distribution_encoded_audio_manifest_parse")
        acceptance = _as_document(self.manifest.get("encoded_audio_acceptance"))
        for row in acceptance.get("review_hashes", []) if isinstance(acceptance.get("review_hashes"), list) else []:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if path in self.entry_map:
                self.encoded_audio_acceptance_reviews[path] = self._read_json_entry(archive, path, "encoded_audio_acceptance", "distribution_encoded_audio_review_parse")

    def _verify_package_release(self) -> None:
        errors: list[str] = []
        for field in ("package_id", "release_id", "target_id", "profile_id"):
            if self.package.get(field) != self.manifest.get(field):
                errors.append(f"package.{field} does not match manifest")
        if self.release.get("release_id") != self.manifest.get("release_id"):
            errors.append("release.json release_id does not match manifest")
        tracks = _as_list(self.tracklist.get("tracks"))
        if not tracks:
            errors.append("tracklist has no tracks")
        self._add_check("package", "distribution_package_consistency", "failed" if errors else "passed", "blocking", "; ".join(errors) if errors else "Package, release, and tracklist are consistent.", count=len(errors))

    def _verify_signoff(self) -> None:
        if not self.signoff:
            self._add_check("signoff", "distribution_signoff_exists", "failed", "blocking", "distribution-signoff.json is missing or invalid.")
            return
        self._add_check("signoff", "distribution_signoff_exists", "passed", "blocking", "distribution-signoff.json exists.")
        signoff_status = self.signoff.get("status")
        self._add_check("signoff", "distribution_signoff_status", "passed" if signoff_status in {"signed", "force_signed"} else "failed", "blocking", f"Distribution signoff status is {signoff_status!r}.")
        manifest_hash = stable_hash({key: value for key, value in self.manifest.items() if key != "zip"})
        signoff_hash = self.signoff.get("export_manifest_hash")
        self._add_check("signoff", "distribution_signoff_manifest_hash", "passed" if signoff_hash == manifest_hash else "failed", "blocking", "Distribution signoff export_manifest_hash matches manifest without zip." if signoff_hash == manifest_hash else "Distribution signoff export_manifest_hash does not match manifest without zip.")
        sidecars = _as_document(self.manifest.get("sidecars"))
        signoff_sidecar = _as_document(sidecars.get("distribution_signoff"))
        expected_payload_hash = signoff_sidecar.get("payload_hash")
        payload_hash = stable_hash(_distribution_signoff_hash_payload(self.signoff))
        self._add_check("signoff", "distribution_signoff_sidecar_payload_hash", "passed" if expected_payload_hash == payload_hash else "failed", "blocking", "distribution-signoff.json payload hash matches manifest sidecar record." if expected_payload_hash == payload_hash else "distribution-signoff.json payload hash does not match manifest sidecar record.")
        qa_source = self.signoff.get("qa_source_hash")
        manifest_qa_source = self.manifest.get("qa_source_hash")
        self._add_check("signoff", "distribution_signoff_qa_source", "passed" if qa_source and qa_source == manifest_qa_source else "failed", "blocking", "Distribution signoff qa_source_hash matches manifest." if qa_source and qa_source == manifest_qa_source else "Distribution signoff qa_source_hash is missing or does not match manifest.")

    def _verify_template_and_checklist(self) -> None:
        manifest_template = _as_document(self.manifest.get("template"))
        if not manifest_template:
            self._add_check("template", "distribution_template_optional", "passed", "blocking", "No distribution template is declared.")
            return
        self._add_check("template", "distribution_template_pack_exists", "passed" if self.template else "failed", "blocking", "template-pack.json exists." if self.template else "template-pack.json is missing.")
        self._add_check("template", "distribution_template_summary_exists", "passed" if self.template_summary_doc else "failed", "blocking", "template-summary.json exists." if self.template_summary_doc else "template-summary.json is missing.")
        expected_hash = manifest_template.get("template_hash")
        actual_hash = template_content_hash(self.template) if self.template else None
        self._add_check("template", "distribution_template_hash_match", "passed" if expected_hash and actual_hash == expected_hash else "failed", "blocking", "template-pack.json hash matches manifest template hash." if expected_hash and actual_hash == expected_hash else "template-pack.json hash does not match manifest template hash.")
        expected_summary_hash = manifest_template.get("payload_hash")
        actual_summary_hash = template_summary(self.template).get("payload_hash") if self.template else None
        doc_summary_hash = self.template_summary_doc.get("payload_hash") if self.template_summary_doc else None
        self._add_check("template", "distribution_template_summary_hash_match", "passed" if expected_summary_hash and actual_summary_hash == expected_summary_hash and doc_summary_hash == expected_summary_hash else "failed", "blocking", "template summary hash matches manifest and template-pack.json." if expected_summary_hash and actual_summary_hash == expected_summary_hash and doc_summary_hash == expected_summary_hash else "template summary hash does not match manifest/template.")
        validation = validate_template_pack(self.template) if self.template else {"status": "failed"}
        self._add_check("template", "distribution_template_valid", "passed" if validation.get("status") == "passed" else "failed", "blocking", "template-pack.json is valid." if validation.get("status") == "passed" else "template-pack.json failed validation.")

        manifest_checklist = _as_document(self.manifest.get("checklist"))
        self._add_check("checklist", "distribution_checklist_exists", "passed" if self.checklist else "failed", "blocking", "docs/checklist.json exists." if self.checklist else "docs/checklist.json is missing.")
        expected_payload_hash = manifest_checklist.get("payload_hash")
        actual_payload_hash = checklist_payload_hash(self.checklist) if self.checklist else None
        summary_hash = checklist_summary(self.checklist).get("payload_hash") if self.checklist else None
        self._add_check("checklist", "distribution_checklist_payload_hash", "passed" if expected_payload_hash and actual_payload_hash == expected_payload_hash and summary_hash == expected_payload_hash else "failed", "blocking", "Checklist payload hash matches manifest." if expected_payload_hash and actual_payload_hash == expected_payload_hash and summary_hash == expected_payload_hash else "Checklist payload hash does not match manifest.")
        checklist_status = checklist_summary(self.checklist).get("status") if self.checklist else "missing"
        self._add_check("checklist", "distribution_checklist_status", "passed" if checklist_status in {"passed", "warning"} else "failed", "blocking", f"Checklist status is {checklist_status}.")

    def _verify_layout(self, archive: zipfile.ZipFile) -> None:
        manifest_layout = _as_document(self.manifest.get("layout"))
        generated_version = str((self.manifest.get("tool") or {}).get("version") or self.manifest.get("generated_by_version") or "").strip()
        legacy = not manifest_layout
        if legacy:
            status = "failed" if self.strict or (generated_version and _version_at_least(generated_version, "4.2.0")) else "warning"
            self._add_check("layout", "distribution_layout_legacy_missing", status, "blocking" if status == "failed" else "warning", "Distribution layout contract is missing.")
            return
        self._add_check("layout", "distribution_layout_exists", "passed", "blocking", "Distribution manifest includes layout contract.")
        self._add_check("layout", "distribution_layout_sidecar_exists", "passed" if self.layout else "failed", "blocking", "layout/manifest-layout.json exists." if self.layout else "layout/manifest-layout.json is missing.")
        if not self.layout:
            return
        manifest_hash = layout_payload_hash(manifest_layout)
        sidecar_hash = layout_payload_hash(self.layout)
        manifest_payload_hash = manifest_layout.get("payload_hash")
        sidecar_payload_hash = self.layout.get("payload_hash")
        hash_ok = bool(manifest_payload_hash and manifest_payload_hash == manifest_hash == sidecar_payload_hash == sidecar_hash)
        self._add_check("layout", "distribution_layout_hash_match", "passed" if hash_ok else "failed", "blocking", "Layout sidecar hash matches manifest." if hash_ok else "Layout sidecar hash does not match manifest.")
        manifest_entries = _as_list(manifest_layout.get("entries"))
        sidecar_entries = _as_list(self.layout.get("entries"))
        entries_match = layout_payload_hash({"entries": manifest_entries}) == layout_payload_hash({"entries": sidecar_entries})
        self._add_check("layout", "distribution_layout_entries_declared", "passed" if entries_match else "failed", "blocking", "Layout entries match sidecar." if entries_match else "Layout entries differ between manifest and sidecar.")
        manifest_files = {str(item.get("path") or ""): item for item in self.manifest.get("files", []) if isinstance(item, dict)}
        missing_manifest: list[str] = []
        missing_zip: list[str] = []
        mismatches: list[str] = []
        reserved: list[str] = []
        unsafe: list[str] = []
        for entry in manifest_entries:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "")
            try:
                validate_layout_path(path)
            except ValueError:
                unsafe.append(path)
            if path in RESERVED_LAYOUT_PATHS:
                reserved.append(path)
            if path not in manifest_files:
                missing_manifest.append(path)
            info = self.entry_map.get(path)
            if info is None:
                missing_zip.append(path)
                continue
            actual_size = int(info.file_size or 0)
            actual_sha = _sha256_entry(archive, info)
            if entry.get("size_bytes") != actual_size or entry.get("sha256") != actual_sha:
                mismatches.append(path)
        self._add_check("layout", "distribution_layout_entries_declared_in_files", "failed" if missing_manifest else "passed", "blocking", "Layout entries missing from manifest.files: " + ", ".join(missing_manifest[:5]) if missing_manifest else "Layout entries are declared in manifest.files.", count=len(missing_manifest))
        self._add_check("layout", "distribution_layout_entries_exist", "failed" if missing_zip else "passed", "blocking", "Layout entries missing from ZIP: " + ", ".join(missing_zip[:5]) if missing_zip else "Layout entries exist in ZIP.", count=len(missing_zip))
        self._add_check("layout", "distribution_layout_file_hash_match", "failed" if mismatches else "passed", "blocking", "Layout entry bytes mismatch: " + ", ".join(mismatches[:5]) if mismatches else "Layout entry hashes and sizes match ZIP.", count=len(mismatches))
        self._add_check("layout", "distribution_layout_reserved_collision", "failed" if reserved else "passed", "blocking", "Layout entries target fixed sidecars: " + ", ".join(reserved[:5]) if reserved else "Layout entries do not target fixed sidecars.", count=len(reserved))
        self._add_check("layout", "distribution_layout_path_safe", "failed" if unsafe else "passed", "blocking", "Layout entries contain unsafe paths: " + ", ".join(unsafe[:5]) if unsafe else "Layout entry paths are safe.", count=len(unsafe))
        try:
            expected_naming = effective_file_naming(self.template) if self.template else {"audio": "audio/{track_number:02d}-{slug_title}.{ext}", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt", "artwork": "artwork/cover.{ext}"}
            template_pattern_ok = True
        except (DistributionTemplateError, ValueError) as exc:
            expected_naming = {}
            template_pattern_ok = False
            self._add_check("layout", "distribution_layout_template_pattern_parse", "failed", "blocking", f"Template file_naming could not be parsed: {exc}")
        naming = _as_document(manifest_layout.get("naming"))
        self._add_check("layout", "distribution_layout_template_patterns_match", "passed" if template_pattern_ok and naming == expected_naming else "failed", "blocking", "Layout naming patterns match template-pack.json." if template_pattern_ok and naming == expected_naming else "Layout naming patterns do not match template-pack.json.")
        artwork = _as_document(self.manifest.get("artwork"))
        artwork_path = str(artwork.get("package_path") or "")
        artwork_entries = {str(entry.get("path") or "") for entry in manifest_entries if isinstance(entry, dict) and entry.get("kind") == "artwork"}
        self._add_check("layout", "distribution_artwork_package_path_match", "passed" if not artwork or artwork_path in artwork_entries and artwork_path in self.entry_map else "failed", "blocking", "Artwork package_path points to layout artwork entry." if not artwork or artwork_path in artwork_entries and artwork_path in self.entry_map else "Artwork package_path does not point to a real layout artwork entry.")

    def _verify_metadata_and_artwork(self, archive: zipfile.ZipFile) -> None:
        metadata_required = {"release-metadata.json", "platform-metadata.csv", "credits.csv"}
        missing_metadata = sorted(metadata_required - set(self.entry_names))
        self._add_check("metadata", "distribution_metadata_files_present", "failed" if missing_metadata else "passed", "blocking", "Missing metadata files: " + ", ".join(missing_metadata) if missing_metadata else "Metadata export files exist.", count=len(missing_metadata))
        csv_failures: list[str] = []
        for name in ("platform-metadata.csv", "credits.csv"):
            if name not in self.entry_map:
                continue
            try:
                text = archive.read(self.entry_map[name]).decode("utf-8")
                rows = list(csv.reader(io.StringIO(text)))
            except (OSError, UnicodeDecodeError, csv.Error, RuntimeError):
                csv_failures.append(f"{name} parse failed")
                continue
            for row_index, row in enumerate(rows, start=1):
                for col_index, cell in enumerate(row, start=1):
                    if _formula_cell(cell):
                        csv_failures.append(f"{name}:{row_index}:{col_index}")
        self._add_check("metadata", "distribution_csv_formula_safe", "failed" if csv_failures else "passed", "blocking", "CSV formula issues: " + ", ".join(csv_failures[:5]) if csv_failures else "CSV cells are formula-safe.", count=len(csv_failures))
        artwork_entries = [name for name in self.entry_names if name.startswith("artwork/") and Path(name).suffix.lower() in {".png", ".jpg", ".jpeg"}]
        missing_artwork = self.require_artwork and not artwork_entries
        self._add_check("artwork", "distribution_artwork_present", "failed" if missing_artwork else "passed", "blocking", "Artwork is required but missing." if missing_artwork else "Artwork presence is acceptable.", count=0 if artwork_entries else 1)
        header_failures: list[str] = []
        for name in artwork_entries:
            info = self.entry_map[name]
            data = archive.read(info)[:32]
            suffix = Path(name).suffix.lower()
            if suffix == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
                header_failures.append(name)
            if suffix in {".jpg", ".jpeg"} and not data.startswith(b"\xff\xd8"):
                header_failures.append(name)
        self._add_check("artwork", "distribution_artwork_header", "failed" if header_failures else "passed", "blocking", "Artwork header failures: " + ", ".join(header_failures[:5]) if header_failures else "Artwork headers are valid.", count=len(header_failures))
        if self.require_audio:
            layout_entries = self.manifest.get("layout", {}).get("entries") if isinstance(self.manifest.get("layout"), dict) else []
            audio_entries = [str(entry.get("path") or "") for entry in layout_entries if isinstance(entry, dict) and entry.get("kind") == "audio"]
            if not audio_entries:
                audio_entries = [name for name in self.entry_names if name.startswith("audio/") and name.endswith((".wav", ".mid", ".midi"))]
            missing_audio = [name for name in audio_entries if name not in self.entry_map]
            bad_audio = []
            for name in audio_entries:
                audio_info = self.entry_map.get(name)
                if audio_info is None:
                    continue
                suffix = Path(name).suffix.lower()
                data = archive.read(audio_info)[:14]
                if suffix == ".wav" and (len(data) < 12 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE"):
                    bad_audio.append(name)
                elif suffix in {".mid", ".midi"} and (len(data) < 14 or not data.startswith(b"MThd")):
                    bad_audio.append(name)
            failed = not audio_entries or missing_audio or bad_audio
            self._add_check("audio", "distribution_audio_file_valid", "failed" if failed else "passed", "blocking", "Audio files are missing or invalid." if failed else "Audio layout files are present and valid.", count=len(missing_audio) + len(bad_audio) if audio_entries else 1)

    def _verify_encoded_audio(self, archive: zipfile.ZipFile) -> None:
        layout_entries = self.manifest.get("layout", {}).get("entries") if isinstance(self.manifest.get("layout"), dict) else []
        encoded_entries = [entry for entry in layout_entries if isinstance(entry, dict) and entry.get("kind") == "audio" and entry.get("source_kind") == "encoded_audio"]
        required = self.require_encoded_audio or bool(encoded_entries)
        if not required:
            self._add_check("encoded_audio", "distribution_encoded_audio_optional", "passed", "warning", "Encoded audio is not required.")
            return
        failures: list[str] = []
        if not self.encoded_audio_summary:
            failures.append("summary_missing")
        elif not encoded_audio_summary_integrity_ok(self.encoded_audio_summary):
            failures.append("summary_integrity")
        elif encoded_audio_summary_uses_fake(self.encoded_audio_summary):
            failures.append("fake_encoder_evidence")
        if self.require_encoded_audio and not encoded_entries:
            failures.append("encoded_layout_entries_missing")
        required_profiles = self._required_encoded_profile_ids(encoded_entries)
        entries_by_profile_track: set[tuple[str, str]] = set()
        for entry in encoded_entries:
            audio_format = _as_document(entry.get("audio_format"))
            profile_id = str(audio_format.get("profile_id") or "")
            track_id = str(entry.get("track_id") or "")
            if profile_id and track_id:
                entries_by_profile_track.add((profile_id, track_id))
            manifest = self.encoded_audio_manifests.get(profile_id)
            if not manifest:
                failures.append(f"{profile_id}:manifest_missing")
                continue
            if not encoded_manifest_integrity_ok(manifest):
                failures.append(f"{profile_id}:manifest_integrity")
            if encoded_manifest_uses_fake(manifest):
                failures.append(f"{profile_id}:fake_encoder_evidence")
            row = next((item for item in manifest.get("tracks", []) if isinstance(item, dict) and item.get("track_id") == track_id), None)
            path = str(entry.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                failures.append(f"{path}:missing")
                continue
            data = archive.read(info)
            detected = detect_audio_format_bytes(data[:32])
            expected_format = str(manifest.get("format") or audio_format.get("format") or "")
            if detected != expected_format and not (expected_format == "aac" and detected == "aac"):
                failures.append(f"{path}:header")
            if row:
                actual_sha = hashlib.sha256(data).hexdigest()
                if actual_sha != row.get("output_sha256"):
                    failures.append(f"{path}:hash")
            else:
                failures.append(f"{profile_id}:{track_id}:track_missing")
        expected_track_ids = self._track_ids()
        for profile_id in required_profiles:
            manifest = self.encoded_audio_manifests.get(profile_id)
            if not manifest:
                failures.append(f"{profile_id}:manifest_missing")
                continue
            for track_id in expected_track_ids:
                if (profile_id, track_id) not in entries_by_profile_track:
                    failures.append(f"{profile_id}:{track_id}:layout_entry_missing")
        self._add_check(
            "encoded_audio",
            "distribution_encoded_audio_evidence",
            "failed" if failures else "passed",
            "blocking",
            "Distribution encoded audio evidence matches package files." if not failures else "Distribution encoded audio failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_encoded_audio_acceptance(self, archive: zipfile.ZipFile) -> None:
        encoded_acceptance = _as_document(self.manifest.get("encoded_audio_acceptance"))
        target = _as_document(self.manifest.get("target"))
        options = _as_document(target.get("options"))
        required = self.require_encoded_audio_review or bool(options.get("require_encoded_audio_review")) or bool(encoded_acceptance.get("review_count"))
        if not required and str(encoded_acceptance.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("encoded_audio_acceptance", "distribution_encoded_audio_acceptance_optional", "passed", "warning", "Encoded audio acceptance is not required.")
            return
        if not required:
            self._add_check("encoded_audio_acceptance", "distribution_encoded_audio_acceptance_optional", "passed", "warning", "Encoded audio acceptance is not required.")
            return
        failures: list[str] = []
        if not self.encoded_audio_acceptance_summary:
            failures.append("summary_missing")
        else:
            if encoded_audio_acceptance_summary_hash(self.encoded_audio_acceptance_summary) != encoded_acceptance.get("summary_hash"):
                failures.append("summary_hash")
            if not encoded_audio_acceptance_summary_integrity_ok(self.encoded_audio_acceptance_summary):
                failures.append("summary_integrity")
            if self.encoded_audio_acceptance_summary.get("status") != "passed":
                failures.append(f"summary_status:{self.encoded_audio_acceptance_summary.get('status')}")
        layout_entries = self.manifest.get("layout", {}).get("entries") if isinstance(self.manifest.get("layout"), dict) else []
        encoded_entries = [entry for entry in layout_entries if isinstance(entry, dict) and entry.get("kind") == "audio" and entry.get("source_kind") == "encoded_audio"]
        review_rows = _as_list(encoded_acceptance.get("review_hashes"))
        summary_tracks = _as_list(self.encoded_audio_acceptance_summary.get("tracks"))
        accepted_review_ids = {str(row.get("accepted_review_id") or "") for row in summary_tracks if isinstance(row, dict) and str(row.get("accepted_review_id") or "")}
        reviews_by_profile_track: dict[tuple[str, str], dict[str, Any]] = {}
        for row in review_rows:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            review = self.encoded_audio_acceptance_reviews.get(path)
            if not review:
                failures.append(f"{path}:missing")
                continue
            if encoded_audio_review_integrity_hash(review) != row.get("payload_hash") or not encoded_audio_review_integrity_ok(review):
                failures.append(f"{path}:integrity")
            if str(review.get("review_id") or "") not in accepted_review_ids:
                continue
            if review.get("status") != "accepted":
                failures.append(f"{path}:status")
            if review.get("review_mode") == "synthetic":
                failures.append(f"{path}:synthetic")
            if not bool(review.get("playback_confirmed", False)):
                failures.append(f"{path}:playback")
            if review.get("stale"):
                failures.append(f"{path}:stale")
            reviews_by_profile_track[(str(review.get("profile_id") or ""), str(review.get("track_id") or ""))] = review
        for entry in encoded_entries:
            audio_format = _as_document(entry.get("audio_format"))
            profile_id = str(audio_format.get("profile_id") or "")
            track_id = str(entry.get("track_id") or "")
            review = reviews_by_profile_track.get((profile_id, track_id))
            if not review:
                failures.append(f"{profile_id}:{track_id}:review_missing")
                continue
            evidence = _as_document(review.get("encoded_audio_evidence"))
            path = str(entry.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                failures.append(f"{path}:missing")
                continue
            actual_hash = hashlib.sha256(archive.read(info)).hexdigest()
            if actual_hash != evidence.get("encoded_track_hash"):
                failures.append(f"{path}:review_hash")
        if required and not encoded_entries:
            failures.append("encoded_layout_entries_missing")
        self._add_check(
            "encoded_audio_acceptance",
            "distribution_encoded_audio_acceptance_evidence",
            "failed" if failures else "passed",
            "blocking",
            "Distribution encoded audio acceptance evidence matches package audio." if not failures else "Distribution encoded audio acceptance failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_format_decision(self, archive: zipfile.ZipFile) -> None:
        manifest_decision = _as_document(self.manifest.get("format_decision"))
        target = _as_document(self.manifest.get("target"))
        options = _as_document(target.get("options"))
        required = self.require_format_decision or bool(options.get("require_format_decision")) or bool(manifest_decision.get("report_hash"))
        if not required and str(manifest_decision.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("format_decision", "distribution_format_decision_optional", "passed", "warning", "Format decision evidence is not required.")
            return
        failures: list[str] = []
        if not self.format_decision_summary:
            failures.append("target_summary_missing")
        else:
            expected_hash = str(manifest_decision.get("integrity_hash") or "")
            actual_hash = str(self.format_decision_summary.get("integrity_hash") or "")
            if expected_hash and expected_hash != actual_hash:
                failures.append("target_summary_hash")
            if not format_distribution_decision_summary_integrity_ok(self.format_decision_summary):
                failures.append("target_summary_integrity")
            if str(self.format_decision_summary.get("report_hash") or "") != str(manifest_decision.get("report_hash") or ""):
                failures.append("report_hash")
            required_profiles = set(self.format_decision_summary.get("required_profiles", []) if isinstance(self.format_decision_summary.get("required_profiles"), list) else [])
            covered = set(self.format_decision_summary.get("covered_profiles", []) if isinstance(self.format_decision_summary.get("covered_profiles"), list) else [])
            rejected = set(self.format_decision_summary.get("rejected_profiles", []) if isinstance(self.format_decision_summary.get("rejected_profiles"), list) else [])
            failures.extend(f"{profile}:missing" for profile in sorted(required_profiles - covered))
            failures.extend(f"{profile}:rejected" for profile in sorted(required_profiles & rejected))
            decision = {
                "selected_profiles": self.format_decision_summary.get("selected_profiles", []),
                "archive_profiles": self.format_decision_summary.get("archive_profiles", []),
            }
            coverage = distribution_target_format_decision_coverage(target, sorted(required_profiles), decision)
            failures.extend(f"{profile}:role_incompatible" for profile in coverage.get("role_incompatible_profiles", []))
            failures.extend(f"{profile}:missing_by_role" for profile in coverage.get("missing_profiles", []))
            if sorted(covered) != list(coverage.get("covered_profiles", [])):
                failures.append("covered_profiles_role_policy")
            if self.format_decision_summary.get("allowed_roles") and list(self.format_decision_summary.get("allowed_roles") or []) != list(coverage.get("allowed_roles", [])):
                failures.append("allowed_roles")
        signoff_decision = _as_document(self.signoff.get("format_decision"))
        if signoff_decision and str(signoff_decision.get("report_hash") or "") != str(manifest_decision.get("report_hash") or ""):
            failures.append("signoff_report_hash")
        self._add_check(
            "format_decision",
            "distribution_format_decision_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Distribution format decision evidence covers target requirements." if not failures else "Distribution format decision failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_rights_clearance(self, archive: zipfile.ZipFile) -> None:
        manifest_rights = _as_document(self.manifest.get("rights_clearance"))
        signoff_rights = _as_document(self.signoff.get("rights_clearance"))
        required = bool(self.require_rights_clearance or signoff_rights.get("require_rights_clearance") or manifest_rights.get("report_hash"))
        if not required and str(manifest_rights.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("rights_clearance", "distribution_rights_clearance_optional", "passed", "warning", "Rights clearance evidence is not required.")
            return
        summary_path = str(manifest_rights.get("summary_path") or "rights/summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("rights_clearance", "distribution_rights_clearance_summary_exists", status, "blocking" if status == "failed" else "warning", "rights/summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "rights_clearance", "distribution_rights_summary_parse")
        failures = verify_rights_summary_evidence(manifest_summary=manifest_rights, summary=summary, required=required)
        if signoff_rights and str(signoff_rights.get("report_hash") or "") != str(manifest_rights.get("report_hash") or ""):
            failures.append("signoff_report_hash")
        self._add_check(
            "rights_clearance",
            "distribution_rights_clearance_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Distribution rights clearance evidence is present." if not failures else "Distribution rights clearance failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _required_encoded_profile_ids(self, encoded_entries: list[ImplementationDocument]) -> list[str]:
        target = _as_document(self.manifest.get("target"))
        options = _as_document(target.get("options"))
        raw = options.get("audio_format_profiles")
        if isinstance(raw, str):
            profiles = [item.strip() for item in raw.split(",")]
        elif isinstance(raw, list):
            profiles = [str(item).strip() for item in raw]
        else:
            profiles = []
        if not profiles and self.require_encoded_audio:
            profiles = [
                str(audio_format.get("profile_id") or "")
                for entry in encoded_entries
                for audio_format in [entry.get("audio_format")]
                if isinstance(audio_format, dict)
            ]
        result: list[str] = []
        for profile_id in profiles:
            if profile_id and profile_id != "wav_master" and profile_id not in result:
                result.append(profile_id)
        encoded = _as_document(self.manifest.get("encoded_audio"))
        for row in encoded.get("profiles", []) if isinstance(encoded.get("profiles"), list) else []:
            profile_id = str(row.get("profile_id") or "")
            if profile_id and profile_id != "wav_master" and profile_id not in result and self.require_encoded_audio:
                result.append(profile_id)
        return result

    def _track_ids(self) -> list[str]:
        tracks = _as_list(self.tracklist.get("tracks"))
        result: list[str] = []
        for row in tracks:
            if not isinstance(row, dict):
                continue
            track_id = str(row.get("track_id") or "")
            if track_id and track_id not in result:
                result.append(track_id)
        if result:
            return result
        layout_entries = self.manifest.get("layout", {}).get("entries") if isinstance(self.manifest.get("layout"), dict) else []
        for entry in layout_entries:
            if isinstance(entry, dict) and entry.get("kind") == "audio":
                track_id = str(entry.get("track_id") or "")
                if track_id and track_id not in result:
                    result.append(track_id)
        return result

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        layout_entries = self.manifest.get("layout", {}).get("entries") if isinstance(self.manifest.get("layout"), dict) else []
        layout_lyrics = {str(entry.get("path") or "") for entry in layout_entries if isinstance(entry, dict) and entry.get("kind") == "lyrics"}
        scan_names = [
            name
            for name in self.entry_names
            if name in {"distribution-manifest.json", "distribution-signoff.json", "package.json", "release.json", "tracklist.json", "release-metadata.json", "platform-metadata.csv", "credits.csv", "README.txt"}
            or name.startswith("lyrics/")
            or name in layout_lyrics
            or name.startswith("docs/")
        ]
        for name in scan_names:
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
        self._add_check("redaction", "distribution_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.", count=len(self.redaction_findings))

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not valid UTF-8 JSON: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} is valid JSON.")
        return value

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str, *, count: int | None = None) -> None:
        item: dict[str, Any] = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if count is not None:
            item["count"] = count
        self.checks.append(sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": DISTRIBUTION_VERIFICATION_SCHEMA_VERSION,
            "package_type": DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Distribution Package Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "require_audio": self.require_audio,
            "require_artwork": self.require_artwork,
            "require_encoded_audio": self.require_encoded_audio,
            "require_encoded_audio_review": self.require_encoded_audio_review,
            "require_format_decision": self.require_format_decision,
            "summary": {
                "package_id": self.manifest.get("package_id"),
                "release_id": self.manifest.get("release_id"),
                "target_id": self.manifest.get("target_id"),
                "profile_id": self.manifest.get("profile_id"),
                "entry_count": len(self.entry_infos),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "total_uncompressed_size_bytes": self.total_uncompressed_size,
            },
            "checks": self.checks,
            "files": self.files,
            "redaction_findings": self.redaction_findings,
            "warnings": warnings,
            "blockers": blockers,
        }
        return sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _distribution_signoff_hash_payload(signoff: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in signoff.items() if key not in DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}


def _formula_cell(cell: str) -> bool:
    text = str(cell or "")
    return bool(text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"))


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def _version_at_least(version: str, minimum: str) -> bool:
    def parts(value: str) -> tuple[int, int, int]:
        raw = str(value or "0.0.0").split("-", 1)[0].lstrip("v")
        nums = []
        for item in raw.split(".")[:3]:
            try:
                nums.append(int(item))
            except ValueError:
                nums.append(0)
        while len(nums) < 3:
            nums.append(0)
        return nums[0], nums[1], nums[2]

    return parts(version) >= parts(minimum)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_findings(path: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": kind, "message": f"{path} contains a local path-like value."})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "message": f"{path} contains a sensitive value pattern: {replacement}."})
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in DISTRIBUTION_BLOCKED_KEYS:
                findings.append({"path": path, "field": child_path, "kind": "blocked_key", "message": f"{path} contains blocked key {child_path}."})
            findings.extend(_blocked_key_findings(path, item, prefix=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(path, item, prefix=f"{prefix}[{index}]"))
    return findings


def _main() -> None:
    report = verify_distribution_package(Path(sys.argv[1]))
    print_distribution_verification_report(report)
    raise SystemExit(distribution_verification_exit_code(report))


if __name__ == "__main__":
    _main()
