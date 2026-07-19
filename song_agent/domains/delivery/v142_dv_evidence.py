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

MAX_TEXT_SCAN_BYTES = _make_deferred_global('MAX_TEXT_SCAN_BYTES')
_blocked_key_findings = _make_deferred_global('_blocked_key_findings')
_redaction_findings = _make_deferred_global('_redaction_findings')
profile = _make_deferred_global('profile')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_TEXT_SCAN_BYTES, _blocked_key_findings, _redaction_findings, profile
    MAX_TEXT_SCAN_BYTES = namespace.get('MAX_TEXT_SCAN_BYTES', MAX_TEXT_SCAN_BYTES)
    _blocked_key_findings = namespace.get('_blocked_key_findings', _blocked_key_findings)
    _redaction_findings = namespace.get('_redaction_findings', _redaction_findings)
    profile = namespace.get('profile', profile)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_VERIFICATION_SCHEMA_VERSION = 1
DISTRIBUTION_VERIFICATION_PACKAGE_TYPE = "musicforge_distribution_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
REQUIRED_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json", "package.json", "release.json", "tracklist.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")




class _DistributionPackageVerifierEvidenceMixin:
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
        reviews_by_profile_track: dict[tuple[str, str], DomainDocument] = {}
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

    def _required_encoded_profile_ids(self, encoded_entries: list[DomainDocument]) -> list[str]:
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

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> DomainDocument:
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
        item: DomainDocument = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if count is not None:
            item["count"] = count
        self.checks.append(sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _build_report(self) -> DomainDocument:
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
