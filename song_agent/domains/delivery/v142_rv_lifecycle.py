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

MAX_TEXT_SCAN_BYTES = _make_deferred_global('MAX_TEXT_SCAN_BYTES')
VERIFIER_REPORT_BLOCKED_KEYS = _make_deferred_global('VERIFIER_REPORT_BLOCKED_KEYS')
_blocked_key_findings = _make_deferred_global('_blocked_key_findings')
_redaction_findings = _make_deferred_global('_redaction_findings')
key = _make_deferred_global('key')
profile = _make_deferred_global('profile')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_TEXT_SCAN_BYTES, VERIFIER_REPORT_BLOCKED_KEYS, _blocked_key_findings, _redaction_findings, key, profile
    MAX_TEXT_SCAN_BYTES = namespace.get('MAX_TEXT_SCAN_BYTES', MAX_TEXT_SCAN_BYTES)
    VERIFIER_REPORT_BLOCKED_KEYS = namespace.get('VERIFIER_REPORT_BLOCKED_KEYS', VERIFIER_REPORT_BLOCKED_KEYS)
    _blocked_key_findings = namespace.get('_blocked_key_findings', _blocked_key_findings)
    _redaction_findings = namespace.get('_redaction_findings', _redaction_findings)
    key = namespace.get('key', key)
    profile = namespace.get('profile', profile)
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




class _ReleaseZipVerifierLifecycleMixin:
    def _verify_encoded_audio_acceptance(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_encoded_audio_review()
        manifest_summary = _as_document(self.manifest.get("encoded_audio_acceptance"))
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
        exported_reviews = _as_list(manifest_summary.get("review_hashes"))
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
        manifest_summary = _as_document(self.manifest.get("format_decision"))
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
        decision = _as_document(report.get("decision"))
        selected = set(decision.get("selected_profiles", []) if isinstance(decision.get("selected_profiles"), list) else [])
        archive_profiles = set(decision.get("archive_profiles", []) if isinstance(decision.get("archive_profiles"), list) else [])
        rejected = set(decision.get("rejected_profiles", []) if isinstance(decision.get("rejected_profiles"), list) else [])
        if selected & rejected:
            failures.append("selected_rejected_overlap")
        if archive_profiles & rejected:
            failures.append("archive_rejected_overlap")
        required_profiles = set(self.required_audio_format_profiles or [])
        failures.extend(f"{profile}:not_selected" for profile in sorted(required_profiles - selected))
        encoded_summary = _as_document(self.manifest.get("encoded_audio"))
        encoded_profiles = {str(row.get("profile_id") or "") for row in encoded_summary.get("profiles", []) if isinstance(row, dict)}
        failures.extend(f"{profile}:encoded_summary_missing" for profile in sorted((selected | archive_profiles) - encoded_profiles))
        if self._requires_encoded_audio_review():
            acceptance = _as_document(self.manifest.get("encoded_audio_acceptance"))
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
        gate = _as_document(self.signoff.get("acceptance_gate"))
        rights_gate = _as_document(gate.get("rights_clearance"))
        return bool(self.require_rights_clearance or rights_gate.get("require_rights_clearance"))

    def _verify_rights_clearance(self, archive: zipfile.ZipFile) -> None:
        required = self._requires_rights_clearance()
        manifest_summary = _as_document(self.manifest.get("rights_clearance"))
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
        tracks: dict[str, DomainDocument] = {}
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
        manifest_summary = _as_document(self.manifest.get("audio_revisions"))
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
        file_rows = _as_list(manifest_summary.get("files"))
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
        stems = _as_list(manifest.get("stems"))
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

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str, *, track_id: str | None = None) -> DomainDocument:
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
        item: DomainDocument = {
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
        item: DomainDocument = {
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
