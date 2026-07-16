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
import sys as sys
import zipfile as zipfile
import csv as csv
import io as io
import wave as wave
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

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


REPORT_SCHEMA_VERSION = 1
RELEASE_VERIFICATION_PACKAGE_TYPE = "musicforge_release_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
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
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS = {"export_manifest_hash"}
LOCAL_PATH_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b[A-Z]:[\\/][^\"'\s,;]*"), "windows_path"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/][^\"'\s,;]*"), "unc_path"),
    (re.compile(r"(?<!\S)/(?:Users|home)/[^\"'\s,;]+"), "posix_user_path"),
)
VERIFIER_REPORT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}
REDACTION_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


class ReleaseVerificationError(ValueError):
    pass


class ReleaseZipOpenError(ReleaseVerificationError):
    pass


class ReleaseZipSafetyError(ReleaseVerificationError):
    pass


class ReleaseManifestError(ReleaseVerificationError):
    pass


def verify_release_zip(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_audio: bool = False,
    require_human_review: bool = False,
    require_audio_revisions: bool = False,
    require_stems: bool = False,
    require_mastering: bool = False,
    require_encoded_audio: bool = False,
    require_encoded_audio_review: bool = False,
    require_format_decision: bool = False,
    require_rights_clearance: bool = False,
    required_audio_format_profiles: list[str] | None = None,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _ReleaseZipVerifier(
        Path(zip_path),
        strict=strict,
        require_audio=require_audio,
        require_human_review=require_human_review,
        require_audio_revisions=require_audio_revisions,
        require_stems=require_stems,
        require_mastering=require_mastering,
        require_encoded_audio=require_encoded_audio,
        require_encoded_audio_review=require_encoded_audio_review,
        require_format_decision=require_format_decision,
        require_rights_clearance=require_rights_clearance,
        required_audio_format_profiles=required_audio_format_profiles or [],
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "release_id": summary.get("release_id"),
            "release_name": summary.get("release_name"),
            "track_count": summary.get("track_count", 0),
            "entry_count": summary.get("entry_count", 0),
            "checked_file_count": summary.get("checked_file_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS,
    )


def write_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    target = Path(path)
    return write_json(target, sanitize_metadata(report, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))


def print_verification_report(report: dict[str, Any]) -> None:
    summary = verification_summary(report)
    print("MusicForge release verification")
    print(f"status: {summary.get('status')}")
    release_id = summary.get("release_id") or "unknown"
    release_name = summary.get("release_name") or "unknown"
    print(f"release: {release_id} - {release_name}")
    print(f"tracks: {summary.get('track_count', 0)}")
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


def release_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _ReleaseZipVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_audio: bool,
        require_human_review: bool,
        require_audio_revisions: bool,
        require_stems: bool,
        require_mastering: bool,
        require_encoded_audio: bool,
        require_encoded_audio_review: bool,
        require_format_decision: bool,
        require_rights_clearance: bool,
        required_audio_format_profiles: list[str],
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_audio = require_audio
        self.require_human_review = require_human_review
        self.require_audio_revisions = require_audio_revisions
        self.require_stems = require_stems
        self.require_mastering = require_mastering
        self.require_encoded_audio = require_encoded_audio
        self.require_encoded_audio_review = require_encoded_audio_review
        self.require_format_decision = require_format_decision
        self.require_rights_clearance = require_rights_clearance
        self.required_audio_format_profiles = [str(item) for item in required_audio_format_profiles if str(item)]
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.track_checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.release: dict[str, Any] = {}
        self.tracklist: dict[str, Any] = {}
        self.release_qa: dict[str, Any] = {}
        self.signoff: dict[str, Any] = {}
        self.release_metadata: dict[str, Any] = {}
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes: int = 0
        self.total_uncompressed_size: int = 0

    def run(self) -> dict[str, Any]:
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
        manifest_files = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        valid_file_rows: list[dict[str, Any]] = []
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

        tracks = self.tracklist.get("tracks") if isinstance(self.tracklist.get("tracks"), list) else []
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

        manifest_tracks = self.manifest.get("tracks") if isinstance(self.manifest.get("tracks"), list) else []
        summary = self.manifest.get("summary") if isinstance(self.manifest.get("summary"), dict) else {}
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
        tracks = self.tracklist.get("tracks") if isinstance(self.tracklist.get("tracks"), list) else []
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

    def _verify_track_mix_state(self, archive: zipfile.ZipFile, *, track_id: str, directory: str, plan_payload: ImplementationDocument, midi_path: str) -> None:
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
        source = mix_state.get("source") if isinstance(mix_state.get("source"), dict) else {}
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

    def _verify_signoff(self) -> None:
        if not self.signoff:
            self._add_check("signoff", "release_signoff_exists", "failed", "blocking", "release-signoff.json is missing or invalid.")
            return
        self._add_check("signoff", "release_signoff_exists", "passed", "blocking", "release-signoff.json exists.")
        signoff_status = self.signoff.get("status")
        self._add_check(
            "signoff",
            "signoff_status",
            "passed" if signoff_status in {"signed", "force_signed"} else "failed",
            "blocking",
            f"Release signoff status is {signoff_status!r}.",
        )
        manifest_hash = stable_hash({key: value for key, value in self.manifest.items() if key != "zip"})
        signoff_hash = self.signoff.get("export_manifest_hash")
        self._add_check(
            "signoff",
            "signoff_manifest_hash",
            "passed" if signoff_hash == manifest_hash else "failed",
            "blocking",
            "Signoff export_manifest_hash matches manifest without zip." if signoff_hash == manifest_hash else "Signoff export_manifest_hash does not match manifest without zip.",
        )
        sidecars = self.manifest.get("sidecars") if isinstance(self.manifest.get("sidecars"), dict) else {}
        release_signoff = sidecars.get("release_signoff") if isinstance(sidecars.get("release_signoff"), dict) else {}
        expected_payload_hash = release_signoff.get("payload_hash")
        payload_hash = stable_hash(_release_signoff_hash_payload(self.signoff))
        self._add_check(
            "signoff",
            "signoff_sidecar_payload_hash",
            "passed" if expected_payload_hash == payload_hash else "failed",
            "blocking",
            "release-signoff.json payload hash matches manifest sidecar record." if expected_payload_hash == payload_hash else "release-signoff.json payload hash does not match manifest sidecar record.",
        )
        qa_source = self.signoff.get("qa_source_hash")
        manifest_qa_source = self.manifest.get("qa_source_hash")
        self._add_check(
            "signoff",
            "signoff_qa_source",
            "passed" if qa_source and qa_source == manifest_qa_source else "failed",
            "blocking",
            "Signoff qa_source_hash matches manifest." if qa_source and qa_source == manifest_qa_source else "Signoff qa_source_hash is missing or does not match manifest.",
        )
        if self.require_human_review:
            gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
            audio_gate = gate.get("audio") if isinstance(gate.get("audio"), dict) else {}
            per_track = audio_gate.get("per_track_review") if isinstance(audio_gate.get("per_track_review"), dict) else {}
            manual_audio_count = int(per_track.get("manual_accepted_track_count", audio_gate.get("manual_audio_accepted_count", 0)) or 0)
            require_per_track = bool(audio_gate.get("require_per_track_audio_review") or per_track.get("require_per_track_audio_review"))
            message = "Release signoff contains manual WAV review evidence."
            if require_per_track:
                message = "Release signoff contains manual per-track WAV review evidence."
            status = "passed" if audio_gate.get("status") == "passed" and manual_audio_count > 0 else "failed"
            self._add_check(
                "signoff",
                "human_audio_review_evidence",
                status,
                "blocking",
                message if status == "passed" else "Manual WAV review evidence is required but missing.",
                count=manual_audio_count,
            )

    def _verify_audio_reviews(self, archive: zipfile.ZipFile) -> None:
        enforce_per_track = self._requires_per_track_audio_review()
        manifest_summary = self.manifest.get("audio_reviews") if isinstance(self.manifest.get("audio_reviews"), dict) else {}
        summary_path = str(manifest_summary.get("summary_path") or "audio-reviews/summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if enforce_per_track else "warning"
            self._add_check("audio_reviews", "audio_review_summary_exists", status, "blocking" if status == "failed" else "warning", "audio-reviews/summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "audio_reviews", "audio_review_summary_parse")
        expected_summary_hash = manifest_summary.get("summary_hash")
        actual_summary_hash = _audio_review_summary_hash(summary)
        self._add_check(
            "audio_reviews",
            "audio_review_summary_hash",
            "passed" if expected_summary_hash == actual_summary_hash else "failed",
            "blocking",
            "Audio review summary hash matches manifest." if expected_summary_hash == actual_summary_hash else "Audio review summary hash does not match manifest.",
        )
        reviews = self._read_audio_review_files(archive, manifest_summary, enforce_per_track=enforce_per_track)
        if not enforce_per_track and not reviews:
            self._add_check("audio_reviews", "audio_review_files_present", "passed", "warning", "No per-track audio review files are required for this release.")
            return
        tracklist_tracks = self.tracklist.get("tracks") if isinstance(self.tracklist.get("tracks"), list) else []
        accepted_by_track: dict[str, dict[str, Any]] = {}
        duplicate_tracks: list[str] = []
        for path, review in reviews:
            track_id = str(review.get("track_id") or "")
            expected_review_hash = _manifest_review_hash(manifest_summary, path, review.get("review_id"))
            if expected_review_hash and _review_payload_hash(review) != str(expected_review_hash):
                self._add_check("audio_reviews", "audio_review_payload_hash", "failed", "blocking", f"Audio review payload hash mismatch for {path}.")
            if not _audio_review_integrity_ok(review):
                self._add_check("audio_reviews", "audio_review_integrity", "failed", "blocking", f"Audio review integrity failed for {path}.")
            if review.get("status") == "accepted" and review.get("review_mode") == "manual" and bool(review.get("playback_confirmed", False)) and not review.get("stale"):
                if track_id in accepted_by_track:
                    duplicate_tracks.append(track_id)
                accepted_by_track[track_id] = review
        if duplicate_tracks:
            self._add_check("audio_reviews", "audio_review_duplicate_track", "failed", "blocking", "Duplicate accepted manual audio reviews for tracks: " + ", ".join(sorted(set(duplicate_tracks))[:5]), count=len(set(duplicate_tracks)))
        missing_track_ids: list[str] = []
        mismatches: list[str] = []
        marker_errors: list[str] = []
        redaction_errors: list[str] = []
        for item in tracklist_tracks:
            if not isinstance(item, dict):
                continue
            track_id = str(item.get("track_id") or "")
            directory = str(item.get("directory") or "").strip("/")
            review = accepted_by_track.get(track_id)
            if not review:
                missing_track_ids.append(track_id)
                continue
            wav_entry = f"{directory}/song.wav"
            info = self.entry_map.get(wav_entry)
            if info is None:
                mismatches.append(f"{track_id}: song.wav missing")
                continue
            actual_wav_sha = _sha256_entry(archive, info)
            evidence = review.get("audio_evidence") if isinstance(review.get("audio_evidence"), dict) else {}
            if evidence.get("wav_sha256") != actual_wav_sha:
                mismatches.append(f"{track_id}: wav sha mismatch")
            duration = _wav_duration(archive, info)
            for marker in review.get("markers", []) if isinstance(review.get("markers"), list) else []:
                if not isinstance(marker, dict):
                    continue
                seconds = float(marker.get("time_seconds") or 0.0)
                if seconds < 0 or (duration > 0 and seconds > duration + 1.0):
                    marker_errors.append(f"{track_id}: marker {marker.get('marker_id')} out of range")
            redaction_errors.extend(_audio_review_value_findings(f"audio review {track_id}", review))
        failures = [*mismatches, *marker_errors, *[item.get("message", "") for item in redaction_errors]]
        if enforce_per_track:
            failures = [*missing_track_ids, *failures]
        status = "failed" if failures else "warning" if missing_track_ids else "passed"
        self._add_check(
            "audio_reviews",
            "per_track_audio_review_evidence",
            status,
            "blocking" if status == "failed" else "warning",
            "Per-track manual audio review evidence covers every track." if status == "passed" else "Per-track audio review evidence failed: " + "; ".join([*missing_track_ids[:3], *mismatches[:3], *marker_errors[:3], *[item.get("message", "") for item in redaction_errors[:3]]]),
            count=len(missing_track_ids) + len(mismatches) + len(marker_errors) + len(redaction_errors),
        )

    def _verify_metadata(self, archive: zipfile.ZipFile) -> None:
        metadata_summary = self.manifest.get("metadata") if isinstance(self.manifest.get("metadata"), dict) else {}
        if not metadata_summary:
            self._add_check("metadata", "metadata_manifest_summary", "warning", "warning", "Release metadata summary is not present; treating this as a pre-v3.9 ZIP.")
            return
        self._add_check("metadata", "metadata_manifest_summary", "passed", "warning", "Release metadata summary exists.")
        declared = [str(item) for item in metadata_summary.get("files", []) if str(item).strip()] if isinstance(metadata_summary.get("files"), list) else []
        required = {"release-metadata.json", "platform-metadata.csv", "credits.csv"}
        missing_declared = sorted(required - set(declared))
        missing_entries = sorted(path for path in declared if path not in self.entry_map)
        file_rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        manifest_paths = {str(item.get("path")) for item in file_rows if isinstance(item, dict)}
        unprotected = sorted(path for path in declared if path not in manifest_paths)
        failures = [*missing_declared, *missing_entries, *[f"{path} not protected by manifest.files" for path in unprotected]]
        self._add_check(
            "metadata",
            "metadata_files_present",
            "failed" if failures else "passed",
            "blocking",
            "Metadata file problems: " + "; ".join(failures[:5]) if failures else "Metadata files exist and are declared in manifest.files.",
            count=len(failures),
        )
        if "release-metadata.json" in self.entry_map:
            self.release_metadata = self._read_json_entry(archive, "release-metadata.json", "metadata", "metadata_json_parse")
        platform_ok = self._read_csv_entry(archive, "platform-metadata.csv", "metadata_platform_csv")
        credits_ok = self._read_csv_entry(archive, "credits.csv", "metadata_credits_csv")
        self._add_check("metadata", "metadata_csv_utf8", "passed" if platform_ok and credits_ok else "failed", "blocking", "Metadata CSV files are UTF-8 readable." if platform_ok and credits_ok else "Metadata CSV files must be valid UTF-8 CSV.")
        if self.release_metadata:
            meta_tracks = self.release_metadata.get("tracks") if isinstance(self.release_metadata.get("tracks"), list) else []
            tracklist_tracks = self.tracklist.get("tracks") if isinstance(self.tracklist.get("tracks"), list) else []
            meta_ids = {str(item.get("track_id")) for item in meta_tracks if isinstance(item, dict)}
            tracklist_ids = {str(item.get("track_id")) for item in tracklist_tracks if isinstance(item, dict)}
            count_match = len(meta_tracks) == len(tracklist_tracks)
            id_match = meta_ids == tracklist_ids
            self._add_check(
                "metadata",
                "metadata_tracklist_consistency",
                "passed" if count_match and id_match else "failed",
                "blocking",
                "Metadata tracks match tracklist." if count_match and id_match else "Metadata tracks do not match tracklist.",
            )
            expected_hash = metadata_summary.get("payload_hash")
            if expected_hash:
                actual_hash = stable_hash(self.release_metadata)
                self._add_check(
                    "metadata",
                    "metadata_payload_hash",
                    "passed" if expected_hash == actual_hash else "failed",
                    "blocking",
                    "Metadata payload hash matches manifest summary." if expected_hash == actual_hash else "Metadata payload hash does not match manifest summary.",
                )

    def _read_audio_review_files(self, archive: zipfile.ZipFile, manifest_summary: ImplementationDocument, *, enforce_per_track: bool) -> list[tuple[str, ImplementationDocument]]:
        declared = manifest_summary.get("review_hashes") if isinstance(manifest_summary.get("review_hashes"), list) else []
        paths = [str(item.get("path") or "") for item in declared if isinstance(item, dict) and str(item.get("path") or "").strip()]
        if not paths:
            paths = sorted(name for name in self.entry_names if name.startswith("audio-reviews/reviews/") and name.endswith(".json"))
        reviews: list[tuple[str, dict[str, Any]]] = []
        missing: list[str] = []
        for path in paths:
            if path not in self.entry_map:
                missing.append(path)
                continue
            reviews.append((path, self._read_json_entry(archive, path, "audio_reviews", "audio_review_parse")))
        self._add_check(
            "audio_reviews",
            "audio_review_files_present",
            "failed" if missing or (enforce_per_track and not reviews) else "passed",
            "blocking" if missing or enforce_per_track else "warning",
            "Missing audio review files: " + ", ".join(missing[:5]) if missing else f"{len(reviews)} audio review file(s) present.",
            count=len(missing),
        )
        return [(path, review) for path, review in reviews if review]

    def _requires_per_track_audio_review(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        audio_gate = gate.get("audio") if isinstance(gate.get("audio"), dict) else {}
        per_track = audio_gate.get("per_track_review") if isinstance(audio_gate.get("per_track_review"), dict) else {}
        return bool(audio_gate.get("require_per_track_audio_review") or per_track.get("require_per_track_audio_review"))

    def _requires_stem_audio_health(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        audio_gate = gate.get("audio") if isinstance(gate.get("audio"), dict) else {}
        mix_gate = audio_gate.get("mix") if isinstance(audio_gate.get("mix"), dict) else {}
        return bool(audio_gate.get("require_stem_audio_health") or mix_gate.get("require_stem_audio_health"))

    def _requires_current_mix_state(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        audio_gate = gate.get("audio") if isinstance(gate.get("audio"), dict) else {}
        mix_gate = audio_gate.get("mix") if isinstance(audio_gate.get("mix"), dict) else {}
        return bool(audio_gate.get("require_current_mix_state") or mix_gate.get("require_current_mix_state"))

    def _requires_audio_revisions(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        audio_gate = gate.get("audio") if isinstance(gate.get("audio"), dict) else {}
        revision_gate = audio_gate.get("audio_revision") if isinstance(audio_gate.get("audio_revision"), dict) else {}
        return bool(self.require_audio_revisions or audio_gate.get("require_audio_revision_closeout") or revision_gate.get("session_count"))

    def _requires_mastering(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        mastering_gate = gate.get("mastering") if isinstance(gate.get("mastering"), dict) else {}
        return bool(self.require_mastering or mastering_gate.get("require_mastering_qa"))

    def _verify_mastering(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_mastering()
        manifest_summary = self.manifest.get("mastering") if isinstance(self.manifest.get("mastering"), dict) else {}
        summary_path = str(manifest_summary.get("summary_path") or "mastering/summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("mastering", "mastering_summary_exists", status, "blocking" if status == "failed" else "warning", "mastering/summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "mastering", "mastering_summary_parse")
        expected_summary_hash = manifest_summary.get("summary_hash")
        actual_summary_hash = mastering_summary_hash(summary)
        self._add_check(
            "mastering",
            "mastering_summary_hash",
            "passed" if expected_summary_hash == actual_summary_hash else "failed",
            "blocking",
            "Mastering summary hash matches manifest." if expected_summary_hash == actual_summary_hash else "Mastering summary hash does not match manifest.",
        )
        analysis = self._read_json_entry(archive, "mastering/analysis.json", "mastering", "mastering_analysis_parse") if "mastering/analysis.json" in self.entry_map else {}
        plan = self._read_json_entry(archive, "mastering/plan.json", "mastering", "mastering_plan_parse") if "mastering/plan.json" in self.entry_map else {}
        selected = self._read_json_entry(archive, "mastering/selected-candidate.json", "mastering", "mastering_selected_candidate_parse") if "mastering/selected-candidate.json" in self.entry_map else {}
        failures: list[str] = []
        if required and not analysis:
            failures.append("analysis_missing")
        if analysis and not mastering_analysis_integrity_ok(analysis):
            failures.append("analysis_integrity")
        if plan and not mastering_plan_integrity_ok(plan):
            failures.append("plan_integrity")
        if required and not selected:
            failures.append("selected_candidate_missing")
        if selected:
            if not mastering_candidate_integrity_ok(selected):
                failures.append("selected_candidate_integrity")
            review = selected.get("review") if isinstance(selected.get("review"), dict) else {}
            if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
                failures.append("manual_review_missing")
            tracks = selected.get("tracks") if isinstance(selected.get("tracks"), list) else []
            by_track = {str(item.get("track_id") or ""): item for item in tracks if isinstance(item, dict)}
            for item in self.tracklist.get("tracks", []) if isinstance(self.tracklist.get("tracks"), list) else []:
                if not isinstance(item, dict):
                    continue
                track_id = str(item.get("track_id") or "")
                directory = str(item.get("directory") or "").strip("/")
                row = by_track.get(track_id)
                if not row:
                    failures.append(f"{track_id}:candidate_track_missing")
                    continue
                mastered_path = f"mastering/tracks/{track_id}/song.wav"
                package_path = f"{directory}/song.wav"
                for path, expected_sha in ((mastered_path, row.get("candidate_wav_sha256")), (package_path, row.get("candidate_wav_sha256"))):
                    info = self.entry_map.get(path)
                    if info is None:
                        failures.append(f"{path}:missing")
                        continue
                    actual_sha = _sha256_entry(archive, info)
                    if actual_sha != expected_sha:
                        failures.append(f"{path}:hash_mismatch")
        if required and summary.get("status") not in {"passed", "warning"}:
            failures.append(f"summary_status:{summary.get('status')}")
        self._add_check(
            "mastering",
            "mastering_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Mastering evidence is present, intact, and matches track audio." if not failures else "Mastering evidence failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _requires_encoded_audio(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        encoded_gate = gate.get("encoded_audio") if isinstance(gate.get("encoded_audio"), dict) else {}
        return bool(self.require_encoded_audio or encoded_gate.get("require_encoded_audio"))

    def _encoded_audio_required_profiles(self) -> list[str]:
        result = list(self.required_audio_format_profiles)
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        encoded_gate = gate.get("encoded_audio") if isinstance(gate.get("encoded_audio"), dict) else {}
        for value in encoded_gate.get("required_audio_format_profiles", []) if isinstance(encoded_gate.get("required_audio_format_profiles"), list) else []:
            text = str(value or "")
            if text and text not in result:
                result.append(text)
        return result

    def _requires_encoded_audio_review(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        review_gate = gate.get("encoded_audio_acceptance") if isinstance(gate.get("encoded_audio_acceptance"), dict) else {}
        return bool(self.require_encoded_audio_review or review_gate.get("require_encoded_audio_review"))

    def _encoded_audio_review_required_profiles(self) -> list[str]:
        result = self._encoded_audio_required_profiles()
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        review_gate = gate.get("encoded_audio_acceptance") if isinstance(gate.get("encoded_audio_acceptance"), dict) else {}
        manifest_summary = self.manifest.get("encoded_audio_acceptance") if isinstance(self.manifest.get("encoded_audio_acceptance"), dict) else {}
        sources = (review_gate,) if result else (review_gate, manifest_summary)
        for source in sources:
            for value in source.get("required_profiles", []) if isinstance(source.get("required_profiles"), list) else []:
                text = str(value or "")
                if text and text not in result:
                    result.append(text)
        return result

    def _requires_format_decision(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        decision_gate = gate.get("format_decision") if isinstance(gate.get("format_decision"), dict) else {}
        return bool(self.require_format_decision or decision_gate.get("require_format_decision"))

    def _verify_encoded_audio(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_encoded_audio()
        manifest_summary = self.manifest.get("encoded_audio") if isinstance(self.manifest.get("encoded_audio"), dict) else {}
        summary_path = str(manifest_summary.get("summary_path") or "encoded-audio-summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("encoded_audio", "encoded_audio_summary_exists", status, "blocking" if status == "failed" else "warning", "encoded-audio-summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "encoded_audio", "encoded_audio_summary_parse")
        expected_hash = manifest_summary.get("summary_hash")
        actual_hash = encoded_audio_summary_hash(summary)
        self._add_check(
            "encoded_audio",
            "encoded_audio_summary_hash",
            "passed" if expected_hash == actual_hash else "failed",
            "blocking",
            "Encoded audio summary hash matches manifest." if expected_hash == actual_hash else "Encoded audio summary hash does not match manifest.",
        )
        failures: list[str] = []
        if summary and not encoded_audio_summary_integrity_ok(summary):
            failures.append("summary_integrity")
        if summary and encoded_audio_summary_uses_fake(summary):
            failures.append("fake_encoder_evidence")
        profiles = summary.get("profiles") if isinstance(summary.get("profiles"), list) else []
        by_profile = {str(row.get("profile_id") or ""): row for row in profiles if isinstance(row, dict)}
        for profile_id in self._encoded_audio_required_profiles():
            row = by_profile.get(profile_id)
            if not row:
                failures.append(f"{profile_id}:missing")
                continue
            if row.get("status") != "completed":
                failures.append(f"{profile_id}:status:{row.get('status')}")
            if not row.get("manifest_hash") or not row.get("source_hash"):
                failures.append(f"{profile_id}:hash_missing")
        if required and not profiles:
            failures.append("profiles_missing")
        self._add_check(
            "encoded_audio",
            "encoded_audio_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Encoded audio summary evidence is present." if not failures else "Encoded audio evidence failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_encoded_audio_acceptance(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_encoded_audio_review()
        manifest_summary = self.manifest.get("encoded_audio_acceptance") if isinstance(self.manifest.get("encoded_audio_acceptance"), dict) else {}
        if not required and str(manifest_summary.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("encoded_audio_acceptance", "encoded_audio_acceptance_optional", "passed", "warning", "Encoded audio acceptance is not required.")
            return
        summary_path = str(manifest_summary.get("summary_path") or "encoded-audio-acceptance-summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("encoded_audio_acceptance", "encoded_audio_acceptance_summary_exists", status, "blocking" if status == "failed" else "warning", "encoded-audio-acceptance-summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "encoded_audio_acceptance", "encoded_audio_acceptance_summary_parse")
        expected_hash = manifest_summary.get("summary_hash")
        actual_hash = encoded_audio_acceptance_summary_hash(summary)
        self._add_check(
            "encoded_audio_acceptance",
            "encoded_audio_acceptance_summary_hash",
            "passed" if expected_hash == actual_hash else "failed",
            "blocking",
            "Encoded audio acceptance summary hash matches manifest." if expected_hash == actual_hash else "Encoded audio acceptance summary hash does not match manifest.",
        )
        failures: list[str] = []
        if not encoded_audio_acceptance_summary_integrity_ok(summary):
            failures.append("summary_integrity")
        by_profile_track = {
            (str(row.get("profile_id") or ""), str(row.get("track_id") or "")): row
            for row in summary.get("tracks", [])
            if isinstance(row, dict)
        }
        accepted_review_ids = {str(row.get("accepted_review_id") or "") for row in by_profile_track.values() if str(row.get("accepted_review_id") or "")}
        if required:
            for profile_id in self._encoded_audio_review_required_profiles():
                profile_rows = [row for key, row in by_profile_track.items() if key[0] == profile_id]
                if not profile_rows:
                    failures.append(f"{profile_id}:tracks_missing")
                    continue
                for row in profile_rows:
                    if row.get("status") != "accepted":
                        failures.append(f"{profile_id}/{row.get('track_id')}:status:{row.get('status')}")
        exported_reviews = manifest_summary.get("review_hashes") if isinstance(manifest_summary.get("review_hashes"), list) else []
        for row in exported_reviews:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if path not in self.entry_map:
                failures.append(f"{path}:missing")
                continue
            review = self._read_json_entry(archive, path, "encoded_audio_acceptance", "encoded_audio_review_parse")
            payload_hash = encoded_audio_review_integrity_hash(review)
            if payload_hash != row.get("payload_hash") or not encoded_audio_review_integrity_ok(review):
                failures.append(f"{path}:integrity")
            if str(review.get("review_id") or "") not in accepted_review_ids:
                continue
            if not required:
                continue
            if review.get("status") != "accepted":
                failures.append(f"{path}:status")
            if review.get("review_mode") == "synthetic":
                failures.append(f"{path}:synthetic")
            if not bool(review.get("playback_confirmed", False)):
                failures.append(f"{path}:playback")
            if review.get("stale"):
                failures.append(f"{path}:stale")
        if required and not exported_reviews:
            failures.append("reviews_missing")
        self._add_check(
            "encoded_audio_acceptance",
            "encoded_audio_acceptance_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Encoded audio acceptance evidence is present and manual." if not failures else "Encoded audio acceptance failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_format_decision(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_format_decision()
        manifest_summary = self.manifest.get("format_decision") if isinstance(self.manifest.get("format_decision"), dict) else {}
        if not required and str(manifest_summary.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("format_decision", "format_decision_optional", "passed", "warning", "Format decision evidence is not required.")
            return
        report_path = str(manifest_summary.get("report_path") or "format-decision/decision-report.json")
        if report_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("format_decision", "format_decision_report_exists", status, "blocking" if status == "failed" else "warning", "Format decision report is missing.")
            return
        report = self._read_json_entry(archive, report_path, "format_decision", "format_decision_report_parse")
        matrix_path = str(manifest_summary.get("matrix_path") or "format-decision/matrix.json")
        recommendation_path = str(manifest_summary.get("recommendation_path") or "format-decision/recommendation.json")
        matrix = self._read_json_entry(archive, matrix_path, "format_decision", "format_decision_matrix_parse") if matrix_path in self.entry_map else {}
        recommendation = self._read_json_entry(archive, recommendation_path, "format_decision", "format_decision_recommendation_parse") if recommendation_path in self.entry_map else {}
        failures: list[str] = []
        expected_report_hash = str(manifest_summary.get("report_hash") or "")
        actual_report_hash = format_report_hash(report)
        if not expected_report_hash or expected_report_hash != actual_report_hash or not format_report_integrity_ok(report):
            failures.append("report_hash")
        if matrix:
            expected_matrix_hash = str(report.get("matrix_hash") or manifest_summary.get("matrix_hash") or "")
            if expected_matrix_hash != str(matrix.get("integrity_hash") or "") or not format_matrix_integrity_ok(matrix):
                failures.append("matrix_hash")
        elif required:
            failures.append("matrix_missing")
        if recommendation:
            expected_recommendation_hash = str(report.get("recommendation_hash") or manifest_summary.get("recommendation_hash") or "")
            if expected_recommendation_hash != str(recommendation.get("integrity_hash") or "") or not format_recommendation_integrity_ok(recommendation):
                failures.append("recommendation_hash")
        decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
        selected = set(decision.get("selected_profiles", []) if isinstance(decision.get("selected_profiles"), list) else [])
        archive_profiles = set(decision.get("archive_profiles", []) if isinstance(decision.get("archive_profiles"), list) else [])
        rejected = set(decision.get("rejected_profiles", []) if isinstance(decision.get("rejected_profiles"), list) else [])
        if selected & rejected:
            failures.append("selected_rejected_overlap")
        if archive_profiles & rejected:
            failures.append("archive_rejected_overlap")
        required_profiles = set(self.required_audio_format_profiles or [])
        failures.extend(f"{profile}:not_selected" for profile in sorted(required_profiles - selected))
        encoded_summary = self.manifest.get("encoded_audio") if isinstance(self.manifest.get("encoded_audio"), dict) else {}
        encoded_profiles = {str(row.get("profile_id") or "") for row in encoded_summary.get("profiles", []) if isinstance(row, dict)}
        failures.extend(f"{profile}:encoded_summary_missing" for profile in sorted((selected | archive_profiles) - encoded_profiles))
        if self._requires_encoded_audio_review():
            acceptance = self.manifest.get("encoded_audio_acceptance") if isinstance(self.manifest.get("encoded_audio_acceptance"), dict) else {}
            accepted_profiles = set(acceptance.get("required_profiles", []) if isinstance(acceptance.get("required_profiles"), list) else [])
            failures.extend(f"{profile}:acceptance_missing" for profile in sorted(selected - accepted_profiles))
        if report.get("status") == "failed":
            failures.append("report_failed")
        self._add_check(
            "format_decision",
            "format_decision_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Format decision evidence is present and current." if not failures else "Format decision evidence failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _requires_rights_clearance(self) -> bool:
        gate = self.signoff.get("acceptance_gate") if isinstance(self.signoff.get("acceptance_gate"), dict) else {}
        rights_gate = gate.get("rights_clearance") if isinstance(gate.get("rights_clearance"), dict) else {}
        return bool(self.require_rights_clearance or rights_gate.get("require_rights_clearance"))

    def _verify_rights_clearance(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_rights_clearance()
        manifest_summary = self.manifest.get("rights_clearance") if isinstance(self.manifest.get("rights_clearance"), dict) else {}
        if not required and str(manifest_summary.get("status") or "") in {"", "missing", "not_required"}:
            self._add_check("rights_clearance", "rights_clearance_optional", "passed", "warning", "Rights clearance evidence is not required.")
            return
        summary_path = str(manifest_summary.get("summary_path") or "rights/summary.json")
        report_path = str(manifest_summary.get("report_path") or "rights/report.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("rights_clearance", "rights_clearance_summary_exists", status, "blocking" if status == "failed" else "warning", "rights/summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "rights_clearance", "rights_summary_parse")
        report = self._read_json_entry(archive, report_path, "rights_clearance", "rights_report_parse") if report_path in self.entry_map else {}
        tracks: dict[str, dict[str, Any]] = {}
        for row in summary.get("tracks", []) if isinstance(summary.get("tracks"), list) else []:
            if not isinstance(row, dict):
                continue
            track_id = str(row.get("track_id") or "")
            path = str(row.get("path") or "")
            if track_id and path in self.entry_map:
                tracks[track_id] = self._read_json_entry(archive, path, "rights_clearance", "rights_track_parse")
        failures = verify_release_rights_package_evidence(
            manifest_summary=manifest_summary,
            summary=summary,
            report=report,
            tracks=tracks,
            required=required,
        )
        self._add_check(
            "rights_clearance",
            "rights_clearance_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Rights clearance evidence is present and intact." if not failures else "Rights clearance evidence failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_audio_revisions(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_audio_revisions()
        manifest_summary = self.manifest.get("audio_revisions") if isinstance(self.manifest.get("audio_revisions"), dict) else {}
        summary_path = str(manifest_summary.get("summary_path") or "audio-revisions/summary.json")
        if summary_path not in self.entry_map:
            status = "failed" if required else "warning"
            self._add_check("audio_revisions", "audio_revision_summary_exists", status, "blocking" if status == "failed" else "warning", "audio-revisions/summary.json is missing.")
            return
        summary = self._read_json_entry(archive, summary_path, "audio_revisions", "audio_revision_summary_parse")
        expected_hash = manifest_summary.get("summary_hash")
        actual_hash = summary.get("integrity_hash")
        self._add_check(
            "audio_revisions",
            "audio_revision_summary_hash",
            "passed" if expected_hash == actual_hash and audio_revision_summary_integrity_ok(summary) else "failed",
            "blocking",
            "Audio revision summary hash and integrity match manifest." if expected_hash == actual_hash and audio_revision_summary_integrity_ok(summary) else "Audio revision summary hash or integrity failed.",
        )
        file_rows = manifest_summary.get("files") if isinstance(manifest_summary.get("files"), list) else []
        paths = [str(item.get("path") or "") for item in file_rows if isinstance(item, dict) and str(item.get("path") or "").startswith("audio-revisions/") and str(item.get("path") or "").endswith(".json")]
        if not paths:
            paths = sorted(name for name in self.entry_names if name.startswith("audio-revisions/") and name.endswith(".json"))
        missing = [path for path in paths if path not in self.entry_map]
        tampered: list[str] = []
        applied_mismatches: list[str] = []
        applied_versions_by_track: dict[str, set[str]] = {}
        candidate_track_by_issue: dict[str, str] = {}
        track_versions = {str(item.get("track_id") or ""): str(item.get("version_id") or "") for item in self.tracklist.get("tracks", []) if isinstance(item, dict)}
        for path in paths:
            if path in missing or path == summary_path:
                continue
            payload = self._read_json_entry(archive, path, "audio_revisions", "audio_revision_payload_parse")
            if not payload:
                tampered.append(path)
                continue
            track_id = str(payload.get("track_id") or "")
            applied_version = str(payload.get("applied_version_id") or "")
            if applied_version:
                if track_id:
                    applied_versions_by_track.setdefault(track_id, set()).add(applied_version)
            if path.startswith("audio-revisions/sessions/") and path.endswith("-closeout.json"):
                if not audio_revision_closeout_integrity_ok(payload):
                    tampered.append(path)
            elif path.startswith("audio-revisions/sessions/"):
                if not audio_revision_session_integrity_ok(payload):
                    tampered.append(path)
            elif path.startswith("audio-revisions/issues/"):
                if not audio_revision_issue_integrity_ok(payload):
                    tampered.append(path)
            elif path.startswith("audio-revisions/selected-candidates/"):
                if not audio_revision_candidate_integrity_ok(payload):
                    tampered.append(path)
                track_id = str(payload.get("track_id") or "")
                applied_version = str(payload.get("applied_version_id") or "")
                issue_id = str(payload.get("issue_id") or "")
                if track_id and issue_id:
                    candidate_track_by_issue[issue_id] = track_id
                if applied_version:
                    applied_versions_by_track.setdefault(track_id, set()).add(applied_version)
        for path in paths:
            if path in missing or not path.startswith("audio-revisions/issues/"):
                continue
            payload = self._read_json_entry(archive, path, "audio_revisions", "audio_revision_payload_parse")
            issue_id = str(payload.get("issue_id") or "")
            applied_version = str(payload.get("applied_version_id") or "")
            track_id = str(payload.get("track_id") or "") or candidate_track_by_issue.get(issue_id, "")
            if track_id and applied_version:
                applied_versions_by_track.setdefault(track_id, set()).add(applied_version)
        for track_id, version_id in track_versions.items():
            versions = applied_versions_by_track.get(track_id, set())
            if versions and version_id not in versions:
                applied_mismatches.append(f"{track_id}:{sorted(versions)[-1] if versions else ''}")
        failures = [*missing, *tampered, *applied_mismatches]
        if required and summary.get("status") not in {"passed", "warning"}:
            failures.append(f"summary_status:{summary.get('status')}")
        self._add_check(
            "audio_revisions",
            "audio_revision_evidence",
            "failed" if failures else "passed",
            "blocking" if required or failures else "warning",
            "Audio revision evidence is present, intact, and matches tracklist." if not failures else "Audio revision evidence failed: " + "; ".join(failures[:5]),
            count=len(failures),
        )

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        scan_names = [
            name
            for name in self.entry_names
            if name in {"manifest.json", "release.json", "tracklist.json", "release-qa.json", "release-signoff.json", "acceptance-analytics-summary.json", "README.txt"}
            or name.endswith(("/project-export.json", "/song-plan.json", "/manifest.json", "/README.txt"))
            or name in {"release-metadata.json", "platform-metadata.csv", "credits.csv"}
            or name.startswith("lyrics/")
            or name.startswith("audio-reviews/")
            or name.startswith("audio-revisions/")
            or name.startswith("mastering/")
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
        self._add_check(
            "redaction",
            "redaction_scan",
            "failed" if self.redaction_findings else "passed",
            "blocking",
            f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.",
            count=len(self.redaction_findings),
        )

    def _verify_stems_manifest(self, archive: zipfile.ZipFile, track_id: str, path: str, directory: str) -> None:
        manifest = self._read_json_entry(archive, path, "track", "track_stems_manifest_parse", track_id=track_id)
        stems = manifest.get("stems") if isinstance(manifest.get("stems"), list) else []
        missing: list[str] = []
        for stem in stems:
            if not isinstance(stem, dict):
                continue
            rel = stem.get("midi") or stem.get("midi_path") or stem.get("path")
            if not rel:
                continue
            stem_path = str(rel).replace("\\", "/").lstrip("/")
            full = stem_path if stem_path.startswith(f"{directory}/") else f"{directory}/{stem_path}"
            if full not in self.entry_map:
                missing.append(full)
        self._add_track_check(track_id, "track_optional_stems", "failed" if missing else "passed", "blocking", "Missing stem files: " + ", ".join(missing[:5]) if missing else "Stem manifest files exist.", path=path, count=len(missing))

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str, *, track_id: str | None = None) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if info is None:
            if track_id:
                self._add_track_check(track_id, check_id, "failed", "blocking", f"{name} is missing.", path=name)
            else:
                self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return {}
        try:
            data = archive.read(info).decode("utf-8")
            value = json.loads(data)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
            if track_id:
                self._add_track_check(track_id, check_id, "failed", "blocking", f"{name} is not valid UTF-8 JSON: {exc}", path=name)
            else:
                self._add_check(scope, check_id, "failed", "blocking", f"{name} is not valid UTF-8 JSON: {exc}")
            return {}
        if not isinstance(value, dict):
            if track_id:
                self._add_track_check(track_id, check_id, "failed", "blocking", f"{name} is not a JSON object.", path=name)
            else:
                self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        if track_id:
            self._add_track_check(track_id, check_id, "passed", "blocking", f"{name} is valid JSON.", path=name)
        else:
            self._add_check(scope, check_id, "passed", "blocking", f"{name} is valid JSON.")
        return value

    def _read_csv_entry(self, archive: zipfile.ZipFile, name: str, check_id: str) -> bool:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check("metadata", check_id, "failed", "blocking", f"{name} is missing.")
            return False
        try:
            text = archive.read(info).decode("utf-8")
            list(csv.reader(io.StringIO(text)))
        except (OSError, UnicodeDecodeError, csv.Error, RuntimeError) as exc:
            self._add_check("metadata", check_id, "failed", "blocking", f"{name} is not valid UTF-8 CSV: {exc}")
            return False
        self._add_check("metadata", check_id, "passed", "blocking", f"{name} is valid UTF-8 CSV.")
        return True

    def _check_midi_header(self, archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[bool, str]:
        data = archive.read(info)[:14]
        if len(data) < 14 or not data.startswith(b"MThd"):
            return False, "MIDI file does not start with a valid MThd header."
        header_len = int.from_bytes(data[4:8], "big")
        track_count = int.from_bytes(data[10:12], "big")
        ppq = int.from_bytes(data[12:14], "big")
        if header_len < 6 or track_count <= 0 or ppq <= 0:
            return False, "MIDI header has invalid length, track count, or PPQ."
        return True, "MIDI header is valid."

    def _check_wav_header(self, archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[bool, str]:
        data = archive.read(info)[:12]
        if len(data) < 12 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
            return False, "WAV file does not start with RIFF/WAVE."
        return True, "WAV header is valid."

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str, *, count: int | None = None) -> None:
        item: dict[str, Any] = {
            "scope": scope,
            "check_id": check_id,
            "status": status,
            "severity": severity,
            "message": message,
        }
        if count is not None:
            item["count"] = count
        self.checks.append(sanitize_metadata(item, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))

    def _add_track_check(self, track_id: str, check_id: str, status: str, severity: str, message: str, *, path: str | None = None, count: int | None = None) -> None:
        item: dict[str, Any] = {
            "scope": "track",
            "track_id": track_id,
            "check_id": check_id,
            "status": status,
            "severity": severity,
            "message": message,
        }
        if path is not None:
            item["path"] = path
        if count is not None:
            item["count"] = count
        self.track_checks.append(sanitize_metadata(item, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in [*self.checks, *self.track_checks] if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in [*self.checks, *self.track_checks] if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        tracks = self.tracklist.get("tracks") if isinstance(self.tracklist.get("tracks"), list) else []
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "package_type": RELEASE_VERIFICATION_PACKAGE_TYPE,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Release Verifier", "version": __version__},
            "input": {
                "filename": self.zip_path.name,
                "size_bytes": self.zip_size_bytes,
                "sha256": self.zip_sha256,
            },
            "status": status,
            "strict": self.strict,
            "require_audio": self.require_audio,
            "require_human_review": self.require_human_review,
            "require_audio_revisions": self.require_audio_revisions,
            "require_stems": self.require_stems,
            "require_mastering": self.require_mastering,
            "require_encoded_audio": self.require_encoded_audio,
            "require_encoded_audio_review": self.require_encoded_audio_review,
            "require_format_decision": self.require_format_decision,
            "required_audio_format_profiles": self.required_audio_format_profiles,
            "summary": {
                "release_id": self.manifest.get("release_id"),
                "release_name": self.manifest.get("release_name"),
                "track_count": len(tracks),
                "entry_count": len(self.entry_infos),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "total_uncompressed_size_bytes": self.total_uncompressed_size,
            },
            "checks": self.checks,
            "track_checks": self.track_checks,
            "files": self.files,
            "redaction_findings": self.redaction_findings,
            "warnings": warnings,
            "blockers": blockers,
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS)


def _release_signoff_hash_payload(signoff: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in signoff.items() if key not in SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}


def _review_payload_hash(review: ImplementationDocument) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in review.items() if key not in {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}}, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))


def _audio_review_summary_hash(summary: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in summary.items() if key not in {"integrity_hash", "generated_at"}})


def _audio_review_integrity_ok(review: ImplementationDocument) -> bool:
    expected = str(review.get("integrity_hash") or "")
    return bool(expected) and expected == _review_payload_hash(review)


def _mix_source_state_for_zip(*, plan: SongPlan, midi_sha: str, project_id: str, version_id: str) -> ImplementationDocument:
    return {
        "project_id": project_id,
        "version_id": version_id,
        "song_plan_hash": song_plan_hash(plan),
        "midi_sha256": midi_sha,
        "track_count": len(plan.tracks),
        "tracks": [{"track_id": track_id_for_index(index), "name": track.name, "role": track_role(track.name), "note_count": len(track.notes)} for index, track in enumerate(plan.tracks)],
        "sections": [{"section_id": section_id_for_index(index), "name": section.name, "start_bar": section.start_bar, "bars": section.bars} for index, section in enumerate(plan.sections)],
    }


def _manifest_review_hash(manifest_summary: ImplementationDocument, path: str, review_id: Any) -> str | None:
    rows = manifest_summary.get("review_hashes") if isinstance(manifest_summary.get("review_hashes"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("path") == path or (review_id and row.get("review_id") == review_id):
            return str(row.get("payload_hash") or "")
    return None


def _wav_duration(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> float:
    try:
        data = archive.read(info)
        with wave.open(io.BytesIO(data), "rb") as wav:
            rate = wav.getframerate()
            return wav.getnframes() / rate if rate else 0.0
    except (OSError, RuntimeError, wave.Error, EOFError):
        return 0.0


def _audio_review_value_findings(path: str, review: ImplementationDocument) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    text = json.dumps(
        {
            "reviewer": review.get("reviewer"),
            "notes": review.get("notes"),
            "tags": review.get("tags"),
            "markers": review.get("markers"),
            "imported_from": review.get("imported_from"),
            "redaction_findings": review.get("redaction_findings"),
        },
        ensure_ascii=False,
    )
    findings.extend(_redaction_findings(path, text))
    findings.extend(_blocked_key_findings(path, review))
    return findings


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


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
            if str(key).lower() in REDACTION_BLOCKED_KEYS:
                findings.append({"path": path, "field": child_path, "kind": "blocked_key", "message": f"{path} contains blocked key {child_path}."})
            findings.extend(_blocked_key_findings(path, item, prefix=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(path, item, prefix=f"{prefix}[{index}]"))
    return findings


def _main() -> None:
    report = verify_release_zip(Path(sys.argv[1]))
    print_verification_report(report)
    raise SystemExit(release_verification_exit_code(report))


if __name__ == "__main__":
    _main()
