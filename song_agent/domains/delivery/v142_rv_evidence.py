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

_audio_review_integrity_ok = _make_deferred_global('_audio_review_integrity_ok')
_audio_review_summary_hash = _make_deferred_global('_audio_review_summary_hash')
_audio_review_value_findings = _make_deferred_global('_audio_review_value_findings')
_manifest_review_hash = _make_deferred_global('_manifest_review_hash')
_release_signoff_hash_payload = _make_deferred_global('_release_signoff_hash_payload')
_review_payload_hash = _make_deferred_global('_review_payload_hash')
_sha256_entry = _make_deferred_global('_sha256_entry')
_wav_duration = _make_deferred_global('_wav_duration')
key = _make_deferred_global('key')
name = _make_deferred_global('name')

def bind_globals(namespace: dict[str, object]) -> None:
    global _audio_review_integrity_ok, _audio_review_summary_hash, _audio_review_value_findings, _manifest_review_hash, _release_signoff_hash_payload, _review_payload_hash, _sha256_entry
    global _wav_duration, key, name
    _audio_review_integrity_ok = namespace.get('_audio_review_integrity_ok', _audio_review_integrity_ok)
    _audio_review_summary_hash = namespace.get('_audio_review_summary_hash', _audio_review_summary_hash)
    _audio_review_value_findings = namespace.get('_audio_review_value_findings', _audio_review_value_findings)
    _manifest_review_hash = namespace.get('_manifest_review_hash', _manifest_review_hash)
    _release_signoff_hash_payload = namespace.get('_release_signoff_hash_payload', _release_signoff_hash_payload)
    _review_payload_hash = namespace.get('_review_payload_hash', _review_payload_hash)
    _sha256_entry = namespace.get('_sha256_entry', _sha256_entry)
    _wav_duration = namespace.get('_wav_duration', _wav_duration)
    key = namespace.get('key', key)
    name = namespace.get('name', name)
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




class _ReleaseZipVerifierEvidenceMixin:
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
        sidecars = _as_document(self.manifest.get("sidecars"))
        release_signoff = _as_document(sidecars.get("release_signoff"))
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
            gate = _as_document(self.signoff.get("acceptance_gate"))
            audio_gate = _as_document(gate.get("audio"))
            per_track = _as_document(audio_gate.get("per_track_review"))
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
        manifest_summary = _as_document(self.manifest.get("audio_reviews"))
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
        tracklist_tracks = _as_list(self.tracklist.get("tracks"))
        accepted_by_track: dict[str, DomainDocument] = {}
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
        redaction_errors: list[DomainDocument] = []
        for item in tracklist_tracks:
            if not isinstance(item, dict):
                continue
            track_id = str(item.get("track_id") or "")
            directory = str(item.get("directory") or "").strip("/")
            review = _as_document(accepted_by_track.get(track_id))
            if not review:
                missing_track_ids.append(track_id)
                continue
            wav_entry = f"{directory}/song.wav"
            info = self.entry_map.get(wav_entry)
            if info is None:
                mismatches.append(f"{track_id}: song.wav missing")
                continue
            actual_wav_sha = _sha256_entry(archive, info)
            evidence = _as_document(review.get("audio_evidence"))
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
        metadata_summary = _as_document(self.manifest.get("metadata"))
        if not metadata_summary:
            self._add_check("metadata", "metadata_manifest_summary", "warning", "warning", "Release metadata summary is not present; treating this as a pre-v3.9 ZIP.")
            return
        self._add_check("metadata", "metadata_manifest_summary", "passed", "warning", "Release metadata summary exists.")
        declared = [str(item) for item in metadata_summary.get("files", []) if str(item).strip()] if isinstance(metadata_summary.get("files"), list) else []
        required = {"release-metadata.json", "platform-metadata.csv", "credits.csv"}
        missing_declared = sorted(required - set(declared))
        missing_entries = sorted(path for path in declared if path not in self.entry_map)
        file_rows = _as_list(self.manifest.get("files"))
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
            meta_tracks = _as_list(self.release_metadata.get("tracks"))
            tracklist_tracks = _as_list(self.tracklist.get("tracks"))
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

    def _read_audio_review_files(self, archive: zipfile.ZipFile, manifest_summary: DomainDocument, *, enforce_per_track: bool) -> list[tuple[str, DomainDocument]]:
        declared = _as_list(manifest_summary.get("review_hashes"))
        paths = [str(item.get("path") or "") for item in declared if isinstance(item, dict) and str(item.get("path") or "").strip()]
        if not paths:
            paths = sorted(name for name in self.entry_names if name.startswith("audio-reviews/reviews/") and name.endswith(".json"))
        reviews: list[tuple[str, DomainDocument]] = []
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
        gate = _as_document(self.signoff.get("acceptance_gate"))
        audio_gate = _as_document(gate.get("audio"))
        per_track = _as_document(audio_gate.get("per_track_review"))
        return bool(audio_gate.get("require_per_track_audio_review") or per_track.get("require_per_track_audio_review"))

    def _requires_stem_audio_health(self) -> bool:
        gate = _as_document(self.signoff.get("acceptance_gate"))
        audio_gate = _as_document(gate.get("audio"))
        mix_gate = _as_document(audio_gate.get("mix"))
        return bool(audio_gate.get("require_stem_audio_health") or mix_gate.get("require_stem_audio_health"))

    def _requires_current_mix_state(self) -> bool:
        gate = _as_document(self.signoff.get("acceptance_gate"))
        audio_gate = _as_document(gate.get("audio"))
        mix_gate = _as_document(audio_gate.get("mix"))
        return bool(audio_gate.get("require_current_mix_state") or mix_gate.get("require_current_mix_state"))

    def _requires_audio_revisions(self) -> bool:
        gate = _as_document(self.signoff.get("acceptance_gate"))
        audio_gate = _as_document(gate.get("audio"))
        revision_gate = _as_document(audio_gate.get("audio_revision"))
        return bool(self.require_audio_revisions or audio_gate.get("require_audio_revision_closeout") or revision_gate.get("session_count"))

    def _requires_mastering(self) -> bool:
        gate = _as_document(self.signoff.get("acceptance_gate"))
        mastering_gate = _as_document(gate.get("mastering"))
        return bool(self.require_mastering or mastering_gate.get("require_mastering_qa"))

    def _verify_mastering(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_mastering()
        manifest_summary = _as_document(self.manifest.get("mastering"))
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
            review = _as_document(selected.get("review"))
            if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
                failures.append("manual_review_missing")
            tracks = _as_list(selected.get("tracks"))
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
        gate = _as_document(self.signoff.get("acceptance_gate"))
        encoded_gate = _as_document(gate.get("encoded_audio"))
        return bool(self.require_encoded_audio or encoded_gate.get("require_encoded_audio"))

    def _encoded_audio_required_profiles(self) -> list[str]:
        result = list(self.required_audio_format_profiles)
        gate = _as_document(self.signoff.get("acceptance_gate"))
        encoded_gate = _as_document(gate.get("encoded_audio"))
        for value in encoded_gate.get("required_audio_format_profiles", []) if isinstance(encoded_gate.get("required_audio_format_profiles"), list) else []:
            text = str(value or "")
            if text and text not in result:
                result.append(text)
        return result

    def _requires_encoded_audio_review(self) -> bool:
        gate = _as_document(self.signoff.get("acceptance_gate"))
        review_gate = _as_document(gate.get("encoded_audio_acceptance"))
        return bool(self.require_encoded_audio_review or review_gate.get("require_encoded_audio_review"))

    def _encoded_audio_review_required_profiles(self) -> list[str]:
        result = self._encoded_audio_required_profiles()
        gate = _as_document(self.signoff.get("acceptance_gate"))
        review_gate = _as_document(gate.get("encoded_audio_acceptance"))
        manifest_summary = _as_document(self.manifest.get("encoded_audio_acceptance"))
        sources = (review_gate,) if result else (review_gate, manifest_summary)
        for source in sources:
            for value in source.get("required_profiles", []) if isinstance(source.get("required_profiles"), list) else []:
                text = str(value or "")
                if text and text not in result:
                    result.append(text)
        return result

    def _requires_format_decision(self) -> bool:
        gate = _as_document(self.signoff.get("acceptance_gate"))
        decision_gate = _as_document(gate.get("format_decision"))
        return bool(self.require_format_decision or decision_gate.get("require_format_decision"))

    def _verify_encoded_audio(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_encoded_audio()
        manifest_summary = _as_document(self.manifest.get("encoded_audio"))
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
        profiles = _as_list(summary.get("profiles"))
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
