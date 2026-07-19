# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
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
_counts = _make_deferred_global('_counts')
_distribution_signoff_hash_payload = _make_deferred_global('_distribution_signoff_hash_payload')
_formula_cell = _make_deferred_global('_formula_cell')
_sha256_entry = _make_deferred_global('_sha256_entry')
_sha256_file = _make_deferred_global('_sha256_file')
_version_at_least = _make_deferred_global('_version_at_least')
count = _make_deferred_global('count')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global HEX_SHA256, _counts, _distribution_signoff_hash_payload, _formula_cell, _sha256_entry, _sha256_file, _version_at_least
    global count, key, value
    HEX_SHA256 = namespace.get('HEX_SHA256', HEX_SHA256)
    _counts = namespace.get('_counts', _counts)
    _distribution_signoff_hash_payload = namespace.get('_distribution_signoff_hash_payload', _distribution_signoff_hash_payload)
    _formula_cell = namespace.get('_formula_cell', _formula_cell)
    _sha256_entry = namespace.get('_sha256_entry', _sha256_entry)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _version_at_least = namespace.get('_version_at_least', _version_at_least)
    count = namespace.get('count', count)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_VERIFICATION_SCHEMA_VERSION = 1
DISTRIBUTION_VERIFICATION_PACKAGE_TYPE = "musicforge_distribution_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
REQUIRED_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json", "package.json", "release.json", "tracklist.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")




class _DistributionPackageVerifierReadinessMixin:
    def run(self) -> DomainDocument:
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
        valid_rows: list[DomainDocument] = []
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
