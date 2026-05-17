from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import struct
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent import __version__
from song_agent.distribution_export import DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS
from song_agent.distribution_layout import RESERVED_LAYOUT_PATHS, effective_file_naming, layout_payload_hash, validate_layout_path
from song_agent.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS
from song_agent.distribution_checklist import checklist_payload_hash, checklist_summary
from song_agent.distribution_templates import template_content_hash, template_summary, validate_template_pack
from song_agent.projectio import write_json
from song_agent.redaction import SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash


DISTRIBUTION_VERIFICATION_SCHEMA_VERSION = 1
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
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def distribution_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
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
        items = report.get(key) if isinstance(report.get(key), list) else []
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
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_audio = require_audio
        self.require_artwork = require_artwork
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
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
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

    def _verify_package_release(self) -> None:
        errors: list[str] = []
        for field in ("package_id", "release_id", "target_id", "profile_id"):
            if self.package.get(field) != self.manifest.get(field):
                errors.append(f"package.{field} does not match manifest")
        if self.release.get("release_id") != self.manifest.get("release_id"):
            errors.append("release.json release_id does not match manifest")
        tracks = self.tracklist.get("tracks") if isinstance(self.tracklist.get("tracks"), list) else []
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
        sidecars = self.manifest.get("sidecars") if isinstance(self.manifest.get("sidecars"), dict) else {}
        signoff_sidecar = sidecars.get("distribution_signoff") if isinstance(sidecars.get("distribution_signoff"), dict) else {}
        expected_payload_hash = signoff_sidecar.get("payload_hash")
        payload_hash = stable_hash(_distribution_signoff_hash_payload(self.signoff))
        self._add_check("signoff", "distribution_signoff_sidecar_payload_hash", "passed" if expected_payload_hash == payload_hash else "failed", "blocking", "distribution-signoff.json payload hash matches manifest sidecar record." if expected_payload_hash == payload_hash else "distribution-signoff.json payload hash does not match manifest sidecar record.")
        qa_source = self.signoff.get("qa_source_hash")
        manifest_qa_source = self.manifest.get("qa_source_hash")
        self._add_check("signoff", "distribution_signoff_qa_source", "passed" if qa_source and qa_source == manifest_qa_source else "failed", "blocking", "Distribution signoff qa_source_hash matches manifest." if qa_source and qa_source == manifest_qa_source else "Distribution signoff qa_source_hash is missing or does not match manifest.")

    def _verify_template_and_checklist(self) -> None:
        manifest_template = self.manifest.get("template") if isinstance(self.manifest.get("template"), dict) else {}
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

        manifest_checklist = self.manifest.get("checklist") if isinstance(self.manifest.get("checklist"), dict) else {}
        self._add_check("checklist", "distribution_checklist_exists", "passed" if self.checklist else "failed", "blocking", "docs/checklist.json exists." if self.checklist else "docs/checklist.json is missing.")
        expected_payload_hash = manifest_checklist.get("payload_hash")
        actual_payload_hash = checklist_payload_hash(self.checklist) if self.checklist else None
        summary_hash = checklist_summary(self.checklist).get("payload_hash") if self.checklist else None
        self._add_check("checklist", "distribution_checklist_payload_hash", "passed" if expected_payload_hash and actual_payload_hash == expected_payload_hash and summary_hash == expected_payload_hash else "failed", "blocking", "Checklist payload hash matches manifest." if expected_payload_hash and actual_payload_hash == expected_payload_hash and summary_hash == expected_payload_hash else "Checklist payload hash does not match manifest.")
        checklist_status = checklist_summary(self.checklist).get("status") if self.checklist else "missing"
        self._add_check("checklist", "distribution_checklist_status", "passed" if checklist_status in {"passed", "warning"} else "failed", "blocking", f"Checklist status is {checklist_status}.")

    def _verify_layout(self, archive: zipfile.ZipFile) -> None:
        manifest_layout = self.manifest.get("layout") if isinstance(self.manifest.get("layout"), dict) else {}
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
        manifest_entries = manifest_layout.get("entries") if isinstance(manifest_layout.get("entries"), list) else []
        sidecar_entries = self.layout.get("entries") if isinstance(self.layout.get("entries"), list) else []
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
        expected_naming = effective_file_naming(self.template) if self.template else {"audio": "audio/{track_number:02d}-{slug_title}.{ext}", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt", "artwork": "artwork/cover.{ext}"}
        naming = manifest_layout.get("naming") if isinstance(manifest_layout.get("naming"), dict) else {}
        self._add_check("layout", "distribution_layout_template_patterns_match", "passed" if naming == expected_naming else "failed", "blocking", "Layout naming patterns match template-pack.json." if naming == expected_naming else "Layout naming patterns do not match template-pack.json.")
        artwork = self.manifest.get("artwork") if isinstance(self.manifest.get("artwork"), dict) else {}
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
                info = self.entry_map.get(name)
                if info is None:
                    continue
                suffix = Path(name).suffix.lower()
                data = archive.read(info)[:14]
                if suffix == ".wav" and (len(data) < 12 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE"):
                    bad_audio.append(name)
                elif suffix in {".mid", ".midi"} and (len(data) < 14 or not data.startswith(b"MThd")):
                    bad_audio.append(name)
            failed = not audio_entries or missing_audio or bad_audio
            self._add_check("audio", "distribution_audio_file_valid", "failed" if failed else "passed", "blocking", "Audio files are missing or invalid." if failed else "Audio layout files are present and valid.", count=len(missing_audio) + len(bad_audio) if audio_entries else 1)

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

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
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

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": DISTRIBUTION_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Distribution Package Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "require_audio": self.require_audio,
            "require_artwork": self.require_artwork,
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


def _is_safe_zip_entry(name: str) -> bool:
    raw = str(name or "")
    if "\\" in raw:
        return False
    if not raw or raw.endswith("/") or raw.startswith("/") or raw.startswith("//"):
        return False
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return PurePosixPath(*parts).as_posix() == raw


def _raw_zip_entry_names(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    names: list[str] = []
    offset = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, offset)
        if index < 0 or index + 46 > len(data):
            break
        flags = struct.unpack_from("<H", data, index + 8)[0]
        name_len = struct.unpack_from("<H", data, index + 28)[0]
        extra_len = struct.unpack_from("<H", data, index + 30)[0]
        comment_len = struct.unpack_from("<H", data, index + 32)[0]
        name_start = index + 46
        name_end = name_start + name_len
        if name_end > len(data):
            break
        raw = data[name_start:name_end]
        encoding = "utf-8" if flags & 0x800 else "cp437"
        try:
            names.append(raw.decode(encoding))
        except UnicodeDecodeError:
            names.append(raw.decode("utf-8", errors="replace"))
        offset = name_end + extra_len + comment_len
    return names


def _distribution_signoff_hash_payload(signoff: dict[str, Any]) -> dict[str, Any]:
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


def _redaction_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": kind, "message": f"{path} contains a local path-like value."})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "message": f"{path} contains a sensitive value pattern: {replacement}."})
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[dict[str, Any]]:
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
