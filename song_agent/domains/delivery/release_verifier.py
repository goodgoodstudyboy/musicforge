# ruff: noqa: E402,F401
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
from song_agent.domains.delivery.v142_rv_readiness import _ReleaseZipVerifierReadinessMixin
from song_agent.domains.delivery import v142_rv_readiness as _v142_rv_readiness
from song_agent.domains.delivery.v142_rv_evidence import _ReleaseZipVerifierEvidenceMixin
from song_agent.domains.delivery import v142_rv_evidence as _v142_rv_evidence
from song_agent.domains.delivery.v142_rv_lifecycle import _ReleaseZipVerifierLifecycleMixin
from song_agent.domains.delivery import v142_rv_lifecycle as _v142_rv_lifecycle
from song_agent.domains.delivery.v142_rv_archive import _ReleaseZipVerifierArchiveMixin
from song_agent.domains.delivery import v142_rv_archive as _v142_rv_archive



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
) -> DomainDocument:
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


def verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
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


def write_verification_report(report: DomainDocument, path: Path | str) -> Path:
    target = Path(path)
    return write_json(target, sanitize_metadata(report, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))


def print_verification_report(report: DomainDocument) -> None:
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


def release_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _ReleaseZipVerifier(_ReleaseZipVerifierReadinessMixin, _ReleaseZipVerifierEvidenceMixin, _ReleaseZipVerifierLifecycleMixin, _ReleaseZipVerifierArchiveMixin):
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
        self.checks: list[ImplementationDocument] = []
        self.track_checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.manifest: ImplementationDocument = {}
        self.release: ImplementationDocument = {}
        self.tracklist: ImplementationDocument = {}
        self.release_qa: ImplementationDocument = {}
        self.signoff: ImplementationDocument = {}
        self.release_metadata: ImplementationDocument = {}
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes: int = 0
        self.total_uncompressed_size: int = 0








































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
    rows = _as_list(manifest_summary.get("review_hashes"))
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
    findings: list[ImplementationDocument] = []
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
    findings: list[ImplementationDocument] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": kind, "message": f"{path} contains a local path-like value."})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "message": f"{path} contains a sensitive value pattern: {replacement}."})
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[ImplementationDocument] = []
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

_v142_rv_readiness.bind_globals(globals())
_v142_rv_evidence.bind_globals(globals())
_v142_rv_lifecycle.bind_globals(globals())
_v142_rv_archive.bind_globals(globals())
