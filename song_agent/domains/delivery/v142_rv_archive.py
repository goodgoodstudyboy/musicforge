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

VERIFIER_REPORT_BLOCKED_KEYS = _make_deferred_global('VERIFIER_REPORT_BLOCKED_KEYS')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_REPORT_BLOCKED_KEYS, item
    VERIFIER_REPORT_BLOCKED_KEYS = namespace.get('VERIFIER_REPORT_BLOCKED_KEYS', VERIFIER_REPORT_BLOCKED_KEYS)
    item = namespace.get('item', item)
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




class _ReleaseZipVerifierArchiveMixin:
    def _build_report(self) -> DomainDocument:
        blockers = [item for item in [*self.checks, *self.track_checks] if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in [*self.checks, *self.track_checks] if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        tracks = _as_list(self.tracklist.get("tracks"))
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
