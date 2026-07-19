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
import sys as sys
import zipfile as zipfile
import csv as csv
import io as io
import wave as wave
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.quality.audio_health import analyze_wav_bytes as analyze_wav_bytes, audio_health_allows_release as audio_health_allows_release
from song_agent.domains.quality.audio_revision import audio_revision_summary_integrity_ok as audio_revision_summary_integrity_ok, candidate_integrity_ok as audio_revision_candidate_integrity_ok, closeout_integrity_ok as audio_revision_closeout_integrity_ok, issue_integrity_ok as audio_revision_issue_integrity_ok, session_integrity_ok as audio_revision_session_integrity_ok
from song_agent.domains.quality.mastering_qa import mastering_analysis_integrity_ok as mastering_analysis_integrity_ok, mastering_candidate_integrity_ok as mastering_candidate_integrity_ok, mastering_plan_integrity_ok as mastering_plan_integrity_ok, mastering_summary_hash as mastering_summary_hash
from song_agent.domains.quality.audio_encoding import encoded_audio_summary_hash as encoded_audio_summary_hash, encoded_audio_summary_integrity_ok as encoded_audio_summary_integrity_ok, encoded_audio_summary_uses_fake as encoded_audio_summary_uses_fake
from song_agent.domains.creation.encoded_audio_acceptance import encoded_audio_acceptance_summary_hash as encoded_audio_acceptance_summary_hash, encoded_audio_acceptance_summary_integrity_ok as encoded_audio_acceptance_summary_integrity_ok, encoded_audio_review_integrity_hash as encoded_audio_review_integrity_hash, encoded_audio_review_integrity_ok as encoded_audio_review_integrity_ok
from song_agent.domains.delivery.format_decisions import format_matrix_integrity_ok as format_matrix_integrity_ok, format_recommendation_integrity_ok as format_recommendation_integrity_ok, format_report_hash as format_report_hash, format_report_integrity_ok as format_report_integrity_ok
from song_agent.domains.delivery.rights_clearance import verify_release_rights_package_evidence as verify_release_rights_package_evidence
from song_agent.domains.quality.mix_controls import mix_state_integrity_ok as mix_state_integrity_ok, song_plan_hash as song_plan_hash, stable_hash as mix_control_stable_hash, track_role as track_role
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stem_health import stem_health_integrity_ok as stem_health_integrity_ok
from song_agent.domains.studio.song_editor import section_id_for_index as section_id_for_index, track_id_for_index as track_id_for_index

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
_mix_source_state_for_zip = _make_deferred_global('_mix_source_state_for_zip')
_sha256_entry = _make_deferred_global('_sha256_entry')
_sha256_file = _make_deferred_global('_sha256_file')
count = _make_deferred_global('count')
key = _make_deferred_global('key')
name = _make_deferred_global('name')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global HEX_SHA256, _counts, _mix_source_state_for_zip, _sha256_entry, _sha256_file, count, key
    global name, value
    HEX_SHA256 = namespace.get('HEX_SHA256', HEX_SHA256)
    _counts = namespace.get('_counts', _counts)
    _mix_source_state_for_zip = namespace.get('_mix_source_state_for_zip', _mix_source_state_for_zip)
    _sha256_entry = namespace.get('_sha256_entry', _sha256_entry)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    count = namespace.get('count', count)
    key = namespace.get('key', key)
    name = namespace.get('name', name)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


REPORT_SCHEMA_VERSION = 1
RELEASE_VERIFICATION_PACKAGE_TYPE = "musicforge_release_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
REQUIRED_TOP_LEVEL_ENTRIES = {
    "manifest.json",
    "release.json",
    "tracklist.json",
    "release-qa.json",
    "release-signoff.json",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json", "release-signoff.json"}
TRACK_CORE_FILES = ("manifest.json", "README.txt", "project-export.json", "song-plan.json", "song.mid")
SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS = {"export_manifest_hash"}
LOCAL_PATH_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b[A-Z]:[\\/][^\"'\s,;]*"), "windows_path"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/][^\"'\s,;]*"), "unc_path"),
    (re.compile(r"(?<!\S)/(?:Users|home)/[^\"'\s,;]+"), "posix_user_path"),
)




class _ReleaseZipVerifierReadinessMixin:
    def run(self) -> DomainDocument:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "manifest_parse")
                self._verify_manifest(archive)
                self._read_top_level_json(archive)
                self._verify_release_tracklist()
                self._verify_tracks(archive)
                self._verify_signoff()
                self._verify_audio_reviews(archive)
                self._verify_audio_revisions(archive)
                self._verify_mastering(archive)
                self._verify_encoded_audio(archive)
                self._verify_encoded_audio_acceptance(archive)
                self._verify_format_decision(archive)
                self._verify_rights_clearance(archive)
                self._verify_metadata(archive)
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists():
            self._add_check("zip", "zip_open", "failed", "blocking", "ZIP file does not exist.")
            return None
        if not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "zip_open", "failed", "blocking", "ZIP path is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check(
            "zip",
            "zip_size_limit",
            "passed" if self.zip_size_bytes <= max_size else "failed",
            "blocking",
            f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.",
            count=self.zip_size_bytes,
        )
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
            self._add_check("zip", "zip_open", "passed", "blocking", "ZIP can be opened.")
            return archive
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "zip_open", "failed", "blocking", f"ZIP cannot be opened: {exc}")
            return None

    def _verify_zip_structure(self, archive: zipfile.ZipFile) -> None:
        self.entry_infos = archive.infolist()
        self.entry_names = [info.filename for info in self.entry_infos]
        self.raw_entry_names = _raw_zip_entry_names(self.zip_path)
        self.total_uncompressed_size = sum(max(0, int(info.file_size or 0)) for info in self.entry_infos)
        max_uncompressed = self.max_uncompressed_size_mb * 1024 * 1024
        self._add_check(
            "zip",
            "zip_uncompressed_size_limit",
            "passed" if self.total_uncompressed_size <= max_uncompressed else "failed",
            "blocking",
            f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.",
            count=self.total_uncompressed_size,
        )
        self._add_check(
            "zip",
            "zip_entry_count_limit",
            "passed" if len(self.entry_infos) <= self.max_entry_count else "failed",
            "blocking",
            f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.",
            count=len(self.entry_infos),
        )
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check(
            "zip",
            "zip_entry_path_safe",
            "failed" if unsafe else "passed",
            "blocking",
            "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.",
            count=len(unsafe),
        )
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check(
            "zip",
            "zip_duplicate_entries",
            "failed" if duplicates else "passed",
            "blocking",
            "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.",
            count=len(duplicates),
        )
        self.entry_map = {}
        for info in self.entry_infos:
            self.entry_map[info.filename] = info
        missing = sorted(REQUIRED_TOP_LEVEL_ENTRIES - set(self.entry_names))
        self._add_check(
            "zip",
            "zip_required_entries",
            "failed" if missing else "passed",
            "blocking",
            "Missing required entries: " + ", ".join(missing) if missing else "All required top-level entries exist.",
            count=len(missing),
        )

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "manifest_exists", "passed", "blocking", "manifest.json exists.")
        missing_fields = [
            field
            for field in ("schema_version", "release_id", "release_name", "source_hash", "qa_source_hash")
            if self.manifest.get(field) in (None, "")
        ]
        if not isinstance(self.manifest.get("tracks"), list):
            missing_fields.append("tracks")
        if not isinstance(self.manifest.get("files"), list):
            missing_fields.append("files")
        if not isinstance(self.manifest.get("summary"), dict):
            missing_fields.append("summary")
        self._add_check(
            "manifest",
            "manifest_schema",
            "failed" if missing_fields else "passed",
            "blocking",
            "Invalid or missing manifest fields: " + ", ".join(missing_fields) if missing_fields else "Manifest schema has required fields.",
            count=len(missing_fields),
        )
        manifest_files = _as_list(self.manifest.get("files"))
        valid_file_rows: list[DomainDocument] = []
        shape_errors: list[str] = []
        for index, item in enumerate(manifest_files):
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
                valid_file_rows.append(item)
        self._add_check(
            "manifest",
            "manifest_files_shape",
            "failed" if shape_errors else "passed",
            "blocking",
            "Invalid manifest file rows: " + "; ".join(shape_errors[:5]) if shape_errors else "Manifest file rows are valid.",
            count=len(shape_errors),
        )
        mismatches: list[str] = []
        for item in valid_file_rows:
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
        self._add_check(
            "manifest",
            "manifest_file_hash_match",
            "failed" if mismatches else "passed",
            "blocking",
            "Manifest file mismatches: " + "; ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.",
            count=len(mismatches),
        )
        allowed = {str(item.get("path")) for item in valid_file_rows}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check(
            "manifest",
            "manifest_extra_entries",
            status,
            "blocking" if status == "failed" else "warning",
            "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra ZIP entries outside legal sidecars.",
            count=len(extra),
        )
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check(
                "manifest",
                "manifest_zip_entries_reference_only",
                "warning" if spoofed else "passed",
                "warning",
                "manifest.zip.entries contains entries that are not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.",
                count=len(spoofed),
            )

    def _read_top_level_json(self, archive: zipfile.ZipFile) -> None:
        if "release.json" in self.entry_map:
            self.release = self._read_json_entry(archive, "release.json", "release", "release_json_parse")
        if "tracklist.json" in self.entry_map:
            self.tracklist = self._read_json_entry(archive, "tracklist.json", "tracklist", "tracklist_json_parse")
        if "release-qa.json" in self.entry_map:
            self.release_qa = self._read_json_entry(archive, "release-qa.json", "release", "release_qa_parse")
        if "release-signoff.json" in self.entry_map:
            self.signoff = self._read_json_entry(archive, "release-signoff.json", "signoff", "release_signoff_parse")

    def _verify_release_tracklist(self) -> None:
        release_errors: list[str] = []
        manifest_release_id = self.manifest.get("release_id")
        if not self.release:
            release_errors.append("release.json is missing or invalid")
        else:
            if self.release.get("release_id") != manifest_release_id:
                release_errors.append("release_id does not match manifest")
            if not self.release.get("release_type"):
                release_errors.append("release_type is missing")
        self._add_check("release", "release_json", "failed" if release_errors else "passed", "blocking", "; ".join(release_errors) if release_errors else "release.json is consistent.")

        tracks = _as_list(self.tracklist.get("tracks"))
        tracklist_errors: list[str] = []
        if not self.tracklist:
            tracklist_errors.append("tracklist.json is missing or invalid")
        for index, item in enumerate(tracks):
            if not isinstance(item, dict):
                tracklist_errors.append(f"tracks[{index}] is not an object")
                continue
            for field in ("track_id", "disc_number", "track_number", "title", "project_id", "version_id", "directory", "file_count"):
                if item.get(field) in (None, ""):
                    tracklist_errors.append(f"tracks[{index}].{field} is missing")
        self._add_check("tracklist", "tracklist_json", "failed" if tracklist_errors else "passed", "blocking", "; ".join(tracklist_errors[:5]) if tracklist_errors else "tracklist.json is valid.", count=len(tracklist_errors))

        order_warnings: list[str] = []
        keys = [(item.get("disc_number"), item.get("track_number")) for item in tracks if isinstance(item, dict)]
        if len(keys) != len(set(keys)):
            order_warnings.append("duplicate disc/track numbers")
        directories = [item.get("directory") for item in tracks if isinstance(item, dict)]
        if len(directories) != len(set(directories)):
            order_warnings.append("duplicate track directories")
        ids = [item.get("track_id") for item in tracks if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            order_warnings.append("duplicate track ids")
        status = "failed" if order_warnings and self.strict else "warning" if order_warnings else "passed"
        self._add_check("tracklist", "track_order", status, "blocking" if status == "failed" else "warning", "; ".join(order_warnings) if order_warnings else "Track ordering identifiers are unique.", count=len(order_warnings))

        manifest_tracks = _as_list(self.manifest.get("tracks"))
        summary = _as_document(self.manifest.get("summary"))
        expected_counts = {
            "manifest.summary.track_count": summary.get("track_count"),
            "manifest.tracks": len(manifest_tracks),
            "tracklist.tracks": len(tracks),
            "release.track_count": self.release.get("track_count"),
        }
        values = {value for value in expected_counts.values() if isinstance(value, int)}
        bad_count = len(values) != 1 or any(not isinstance(value, int) for value in expected_counts.values())
        self._add_check("tracklist", "track_count_consistency", "failed" if bad_count else "passed", "blocking", f"Track count values: {expected_counts}.")

    def _verify_tracks(self, archive: zipfile.ZipFile) -> None:
        tracks = _as_list(self.tracklist.get("tracks"))
        for item in tracks:
            if not isinstance(item, dict):
                continue
            directory = str(item.get("directory") or "").strip("/")
            track_id = str(item.get("track_id") or directory or "unknown")
            missing = [f"{directory}/{name}" for name in TRACK_CORE_FILES if f"{directory}/{name}" not in self.entry_map]
            self._add_track_check(track_id, "track_core_files", "failed" if missing else "passed", "blocking", "Missing core files: " + ", ".join(missing) if missing else "Track core files exist.", path=directory, count=len(missing))
            plan_path = f"{directory}/song-plan.json"
            plan = self._read_json_entry(archive, plan_path, "track", "track_song_plan_parse", track_id=track_id) if plan_path in self.entry_map else {}
            if plan:
                shape_warnings = []
                if not isinstance(plan.get("sections"), list):
                    shape_warnings.append("sections is not a list")
                if not isinstance(plan.get("tracks"), list):
                    shape_warnings.append("tracks is not a list")
                self._add_track_check(track_id, "track_song_plan_shape", "warning" if shape_warnings else "passed", "warning", "; ".join(shape_warnings) if shape_warnings else "song-plan.json has expected shape.", path=plan_path, count=len(shape_warnings))
            midi_path = f"{directory}/song.mid"
            if midi_path in self.entry_map:
                ok, message = self._check_midi_header(archive, self.entry_map[midi_path])
                self._add_track_check(track_id, "track_midi_header", "passed" if ok else "failed", "blocking", message, path=midi_path)
            self._verify_track_mix_state(archive, track_id=track_id, directory=directory, plan_payload=plan, midi_path=midi_path)
            if self.require_audio:
                wav_path = f"{directory}/song.wav"
                if wav_path not in self.entry_map:
                    self._add_track_check(track_id, "track_optional_audio", "failed", "blocking", "song.wav is required but missing.", path=wav_path)
                else:
                    ok, message = self._check_wav_header(archive, self.entry_map[wav_path])
                    status = "passed" if ok else "failed"
                    if ok:
                        health = analyze_wav_bytes(archive.read(self.entry_map[wav_path]), filename=wav_path, source={"track_id": track_id, "path": wav_path}, report_id=f"ahr-verify-{track_id}", now=self.generated_at)
                        status = "passed" if audio_health_allows_release(health) else "failed"
                        message = "song.wav exists and passes baseline audio health." if status == "passed" else "song.wav failed baseline audio health."
                    self._add_track_check(track_id, "track_optional_audio", status, "blocking", message, path=wav_path)
            if self.require_stems:
                stems_manifest_path = f"{directory}/stems/manifest.json"
                if stems_manifest_path not in self.entry_map:
                    self._add_track_check(track_id, "track_optional_stems", "failed", "blocking", "stems/manifest.json is required but missing.", path=stems_manifest_path)
                else:
                    self._verify_stems_manifest(archive, track_id, stems_manifest_path, directory)
            stem_health_required = self.require_stems or self._requires_stem_audio_health()
            if stem_health_required:
                stem_health_path = f"{directory}/stems/stem-health.json"
                if stem_health_path not in self.entry_map:
                    self._add_track_check(track_id, "track_stem_audio_health", "failed", "blocking", "stems/stem-health.json is required but missing.", path=stem_health_path)
                else:
                    report = self._read_json_entry(archive, stem_health_path, "track", "track_stem_health_parse", track_id=track_id)
                    status = str(report.get("status") or "")
                    ok = bool(report) and stem_health_integrity_ok(report) and status in {"passed", "warning"}
                    self._add_track_check(
                        track_id,
                        "track_stem_audio_health",
                        "passed" if ok else "failed",
                        "blocking",
                        "Stem audio health report is present and allows release." if ok else "Stem audio health report is missing, tampered, or failed.",
                        path=stem_health_path,
                    )

    def _verify_track_mix_state(self, archive: zipfile.ZipFile, *, track_id: str, directory: str, plan_payload: DomainDocument, midi_path: str) -> None:
        mix_state_required = self._requires_current_mix_state()
        mix_state_path = f"{directory}/mix-state.json"
        if mix_state_path not in self.entry_map:
            if mix_state_required:
                self._add_track_check(track_id, "track_mix_state_current", "failed", "blocking", "mix-state.json is required but missing.", path=mix_state_path)
            return
        mix_state = self._read_json_entry(archive, mix_state_path, "track", "track_mix_state_parse", track_id=track_id)
        if not mix_state:
            self._add_track_check(track_id, "track_mix_state_current", "failed", "blocking", "mix-state.json is missing or invalid.", path=mix_state_path)
            return
        reasons: list[str] = []
        if not mix_state_integrity_ok(mix_state):
            reasons.append("mix_state_integrity")
        try:
            plan = SongPlan.from_dict(plan_payload)
        except Exception:
            plan = None
            reasons.append("song_plan_unavailable")
        midi_info = self.entry_map.get(midi_path)
        if midi_info is None:
            reasons.append("song_midi_missing")
            midi_sha = ""
        else:
            midi_sha = _sha256_entry(archive, midi_info)
        if plan is not None:
            if mix_state.get("base_song_plan_hash") != song_plan_hash(plan):
                reasons.append("base_song_plan_hash")
            if mix_state.get("base_midi_hash") != midi_sha:
                reasons.append("base_midi_hash")
        source = _as_document(mix_state.get("source"))
        if plan is not None:
            expected_source = _mix_source_state_for_zip(plan=plan, midi_sha=midi_sha, project_id=str(mix_state.get("project_id") or ""), version_id=str(mix_state.get("version_id") or ""))
            if any(source.get(key) != value for key, value in expected_source.items()):
                reasons.append("source_state")
        if mix_state.get("source_hash") != mix_control_stable_hash(source):
            reasons.append("source_hash")
        reasons = sorted(set(reasons))
        self._add_track_check(
            track_id,
            "track_mix_state_current",
            "failed" if reasons else "passed",
            "blocking",
            "mix-state.json matches package song-plan.json and song.mid." if not reasons else "mix-state.json is stale or tampered: " + ", ".join(reasons),
            path=mix_state_path,
            count=len(reasons),
        )
