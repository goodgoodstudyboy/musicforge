# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_encoding import AudioEncodingStateError as AudioEncodingStateError, AudioEncodingStore as AudioEncodingStore, detect_audio_header as detect_audio_header, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_manifest_uses_fake as encoded_manifest_uses_fake, normalize_required_profiles as normalize_required_profiles, validate_relative_path as validate_relative_path
from song_agent.domains.quality.audio_encoding_profiles import audio_encoding_profile_hash as audio_encoding_profile_hash
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, DistributionTarget as DistributionTarget
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.creation.v142_eaa_readiness import EncodedAudioAcceptanceStoreReadinessMixin
from song_agent.domains.creation import v142_eaa_readiness as _v142_eaa_readiness
from song_agent.domains.creation.v142_eaa_evidence import EncodedAudioAcceptanceStoreEvidenceMixin
from song_agent.domains.creation import v142_eaa_evidence as _v142_eaa_evidence



ENCODED_AUDIO_ACCEPTANCE_SCHEMA_VERSION = 1
ENCODED_AUDIO_HEALTH_SCHEMA_VERSION = 1
ENCODED_AUDIO_REVIEW_SCHEMA_VERSION = 1
ENCODED_AUDIO_ACCEPTANCE_SUMMARY_SCHEMA_VERSION = 1
ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
ENCODED_REVIEW_STATUSES = {"accepted", "needs_fix", "rejected", "waived"}
ENCODED_REVIEW_MODES = {"manual", "external_import", "synthetic"}
ENCODED_REVIEW_MARKER_CATEGORIES = {"format_artifact", "codec", "loudness", "noise", "gap", "metadata", "other"}
ENCODED_REVIEW_MARKER_SEVERITIES = {"low", "medium", "high", "critical"}
ENCODED_HEALTH_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
ENCODED_REVIEW_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
ENCODED_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
MIN_ENCODED_AUDIO_BYTES = {"mp3": 16 * 1024, "flac": 16 * 1024, "aac": 16 * 1024, "wav": 44}


class EncodedAudioAcceptanceError(ValueError):
    pass


class EncodedAudioAcceptanceNotFoundError(EncodedAudioAcceptanceError):
    pass


class EncodedAudioAcceptanceStateError(EncodedAudioAcceptanceError):
    pass


class EncodedAudioAcceptanceStore(EncodedAudioAcceptanceStoreReadinessMixin, EncodedAudioAcceptanceStoreEvidenceMixin):
    def __init__(
        self,
        release_store: ReleaseStore,
        project_store: ProjectStore | None = None,
        audio_encoding_store: AudioEncodingStore | None = None,
    ) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.audio_encoding_store = audio_encoding_store or AudioEncodingStore(release_store, project_store=self.project_store)
        self.lock = threading.RLock()






























def encoded_audio_health_source(manifest: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "release_id": manifest.get("release_id"),
            "profile_id": manifest.get("profile_id"),
            "profile_hash": manifest.get("profile_hash"),
            "format": manifest.get("format"),
            "extension": manifest.get("extension"),
            "manifest_hash": manifest.get("integrity_hash"),
            "manifest_source_hash": manifest.get("source_hash"),
            "manifest_current": not bool(manifest.get("stale", False)),
            "fake_evidence": encoded_manifest_uses_fake(manifest),
            "tracks": [
                {
                    "track_id": row.get("track_id"),
                    "output_rel": row.get("output_rel"),
                    "output_sha256": row.get("output_sha256"),
                    "source_wav_sha256": row.get("source_wav_sha256"),
                    "status": row.get("status"),
                }
                for row in manifest.get("tracks", [])
                if isinstance(row, dict)
            ],
        },
        blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS,
    )


def encoded_audio_health_hash(report: DomainDocument) -> str:
    payload = {key: value for key, value in report.items() if key not in ENCODED_HEALTH_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS))


def encoded_audio_health_integrity_ok(report: DomainDocument) -> bool:
    expected = str((report or {}).get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_health_hash(report)


def encoded_audio_review_source_hash(context: DomainDocument) -> str:
    track = _as_document(context.get("track"))
    profile = _as_document(context.get("profile"))
    evidence = _as_document(context.get("encoded_audio_evidence"))
    health = _as_document(context.get("health"))
    return stable_hash(
        sanitize_metadata(
            {
                "release_id": (context.get("release") or {}).get("release_id") if isinstance(context.get("release"), dict) else None,
                "track": {
                    "track_id": track.get("track_id"),
                    "project_id": track.get("project_id"),
                    "version_id": track.get("version_id"),
                    "disc_number": track.get("disc_number"),
                    "track_number": track.get("track_number"),
                },
                "profile": {
                    "profile_id": profile.get("profile_id"),
                    "profile_hash": evidence.get("profile_hash") or profile.get("integrity_hash"),
                    "format": profile.get("format"),
                    "extension": profile.get("extension"),
                },
                "encoded_audio_evidence": {
                    "manifest_hash": evidence.get("manifest_hash"),
                    "manifest_source_hash": evidence.get("manifest_source_hash"),
                    "encoded_track_hash": evidence.get("encoded_track_hash"),
                    "source_wav_sha256": evidence.get("source_wav_sha256"),
                    "health_hash": evidence.get("health_hash"),
                    "health_status": evidence.get("health_status"),
                },
                "health_source_hash": health.get("source_hash"),
            },
            blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS,
        )
    )


def encoded_audio_review_integrity_hash(review: DomainDocument) -> str:
    payload = {key: value for key, value in review.items() if key not in ENCODED_REVIEW_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS))


def encoded_audio_review_integrity_ok(review: DomainDocument) -> bool:
    expected = str((review or {}).get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_review_integrity_hash(review)


def encoded_audio_acceptance_source_hash(
    release: DomainDocument,
    profiles: list[str],
    profile_rows: list[DomainDocument],
    track_rows: list[DomainDocument],
    reviews: list[DomainDocument],
) -> str:
    return stable_hash(
        {
            "release": {
                "release_id": release.get("release_id"),
                "tracks": [
                    {
                        "track_id": item.get("track_id"),
                        "project_id": item.get("project_id"),
                        "version_id": item.get("version_id"),
                        "disc_number": item.get("disc_number"),
                        "track_number": item.get("track_number"),
                    }
                    for item in release.get("tracks", [])
                    if isinstance(item, dict)
                ],
            },
            "required_profiles": profiles,
            "profiles": [
                {
                    "profile_id": row.get("profile_id"),
                    "manifest_hash": row.get("manifest_hash"),
                    "source_hash": row.get("source_hash"),
                    "health_hash": row.get("health_hash"),
                    "status": row.get("status"),
                }
                for row in profile_rows
            ],
            "tracks": [
                {
                    "profile_id": row.get("profile_id"),
                    "track_id": row.get("track_id"),
                    "encoded_track_hash": row.get("encoded_track_hash"),
                    "health_hash": row.get("health_hash"),
                    "status": row.get("status"),
                }
                for row in track_rows
            ],
            "reviews": [
                {
                    "review_id": review.get("review_id"),
                    "profile_id": review.get("profile_id"),
                    "track_id": review.get("track_id"),
                    "status": review.get("status"),
                    "review_mode": review.get("review_mode"),
                    "playback_confirmed": review.get("playback_confirmed"),
                    "source_hash": review.get("source_hash"),
                    "integrity_hash": review.get("integrity_hash"),
                    "stale": bool(review.get("stale", False)),
                    "redaction_issue_count": len(encoded_audio_review_redaction_findings(review)),
                }
                for review in sorted(reviews, key=lambda item: str(item.get("review_id") or ""))
            ],
        }
    )


def encoded_audio_acceptance_summary_hash(summary: DomainDocument) -> str:
    payload = {key: value for key, value in summary.items() if key not in ENCODED_SUMMARY_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS))


def encoded_audio_acceptance_summary_integrity_ok(summary: DomainDocument) -> bool:
    expected = str((summary or {}).get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_acceptance_summary_hash(summary)


def encoded_audio_acceptance_allows_signoff(summary: DomainDocument) -> bool:
    return (
        bool(summary)
        and encoded_audio_acceptance_summary_integrity_ok(summary)
        and summary.get("status") == "passed"
        and not summary.get("blockers")
        and int(summary.get("track_count") or 0) > 0
        and int(summary.get("manual_accepted_track_count") or 0) == int(summary.get("track_count") or -1)
    )


def encoded_audio_acceptance_summary_public(summary: DomainDocument | None) -> DomainDocument:
    data = _as_document(summary)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_id": data.get("release_id"),
            "profile_count": data.get("profile_count", 0),
            "track_count": data.get("track_count", 0),
            "covered_track_count": data.get("covered_track_count", 0),
            "manual_accepted_track_count": data.get("manual_accepted_track_count", 0),
            "synthetic_only_track_count": data.get("synthetic_only_track_count", 0),
            "needs_fix_track_count": data.get("needs_fix_track_count", 0),
            "rejected_track_count": data.get("rejected_track_count", 0),
            "stale_review_count": data.get("stale_review_count", 0),
            "tampered_review_count": data.get("tampered_review_count", 0),
            "redaction_issue_count": data.get("redaction_issue_count", 0),
            "required_profiles": data.get("required_profiles", []),
            "source_hash": data.get("source_hash"),
            "summary_hash": encoded_audio_acceptance_summary_hash(data) if data else None,
            "integrity_hash": data.get("integrity_hash"),
            "blockers": data.get("blockers", []),
            "warnings": data.get("warnings", []),
        },
        blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS,
    )


def encoded_audio_payload_redaction_findings(payload: DomainDocument) -> list[DomainDocument]:
    findings: list[ImplementationDocument] = []

    def walk(value: Any, field: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{field}.{key}" if field else str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{field}[{index}]")
        elif isinstance(value, str):
            sanitized = sanitize_sensitive_text(value)
            if sanitized != value:
                findings.append({"field": field, "kind": "sensitive_value", "message": f"{field} contained a sensitive value."})

    walk({key: payload.get(key) for key in ("reviewer", "notes", "tags", "markers", "imported_from", "listening_device")}, "")
    return sanitize_metadata(findings, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)


def encoded_audio_review_redaction_findings(review: DomainDocument) -> list[DomainDocument]:
    findings = list(review.get("redaction_findings") or []) if isinstance(review.get("redaction_findings"), list) else []
    for field in ("reviewer", "notes", "tags", "markers", "imported_from", "listening_device"):
        value = review.get(field)
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
        for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append({"field": field, "kind": "sensitive_value", "message": f"{field} contains sensitive value pattern: {replacement}."})
    return sanitize_metadata(findings, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)


def export_encoded_audio_acceptance(
    release_store: ReleaseStore,
    release_id: str,
    export_dir: Path,
    *,
    project_store: ProjectStore | None = None,
    required_profiles: list[str] | None = None,
    now: str | None = None,
) -> DomainDocument:
    store = EncodedAudioAcceptanceStore(release_store, project_store=project_store)
    profiles = store._required_profiles(release_id, required_profiles)
    if not profiles:
        return {"status": "not_required", "required_profiles": [], "summary_path": None}
    summary = store.build_summary(release_id, required_profiles=profiles, now=now)
    health_root = export_dir / "encoded-audio-health"
    reviews_root = export_dir / "encoded-audio-reviews"
    health_root.mkdir(parents=True, exist_ok=True)
    reviews_root.mkdir(parents=True, exist_ok=True)
    write_json(export_dir / "encoded-audio-acceptance-summary.json", summary)
    health_files = []
    for profile_id in profiles:
        health = store.read_health(release_id, profile_id, default={})
        if not health:
            continue
        path = health_root / f"{profile_id}.json"
        write_json(path, health)
        health_files.append({"profile_id": profile_id, "path": f"encoded-audio-health/{profile_id}.json", "payload_hash": encoded_audio_health_hash(health)})
    review_files = []
    for review in sorted(store.list_reviews(release_id), key=lambda item: (str(item.get("profile_id") or ""), str(item.get("track_id") or ""), str(item.get("review_id") or ""))):
        if str(review.get("profile_id") or "") not in profiles:
            continue
        filename = f"{review.get('review_id')}.json"
        path = reviews_root / filename
        write_json(path, review)
        review_files.append({"profile_id": review.get("profile_id"), "track_id": review.get("track_id"), "review_id": review.get("review_id"), "path": f"encoded-audio-reviews/{filename}", "payload_hash": encoded_audio_review_integrity_hash(review)})
    return {
        **encoded_audio_acceptance_summary_public(summary),
        "summary_hash": encoded_audio_acceptance_summary_hash(summary),
        "summary_path": "encoded-audio-acceptance-summary.json",
        "health_files": health_files,
        "review_hashes": review_files,
        "health_count": len(health_files),
        "review_count": len(review_files),
    }


def export_distribution_encoded_audio_acceptance(
    *,
    store: DistributionStore,
    release_id: str,
    target: DistributionTarget,
    export_dir: Path,
    required_profiles: list[str],
    records: list[DomainDocument],
) -> DomainDocument:
    acceptance_store = EncodedAudioAcceptanceStore(store.release_store, project_store=store.release_store.project_store)
    profiles = [profile_id for profile_id in normalize_required_profiles(required_profiles) if profile_id != "wav_master"]
    if not profiles:
        return {"status": "not_required", "required_profiles": []}
    summary = acceptance_store.build_summary(release_id, required_profiles=profiles)
    root = export_dir / "encoded-audio-acceptance"
    health_dir = root / "health"
    review_dir = root / "reviews"
    health_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    write_json(root / "summary.json", summary)
    records.append(_file_record(export_dir, root / "summary.json"))
    health_files = []
    for profile_id in profiles:
        health = acceptance_store.read_health(release_id, profile_id, default={})
        if not health:
            continue
        path = health_dir / f"{profile_id}.json"
        write_json(path, health)
        records.append(_file_record(export_dir, path))
        health_files.append({"profile_id": profile_id, "path": f"encoded-audio-acceptance/health/{profile_id}.json", "payload_hash": encoded_audio_health_hash(health)})
    review_files = []
    for review in sorted(acceptance_store.list_reviews(release_id), key=lambda item: (str(item.get("profile_id") or ""), str(item.get("track_id") or ""), str(item.get("review_id") or ""))):
        if str(review.get("profile_id") or "") not in profiles:
            continue
        filename = f"{review.get('review_id')}.json"
        path = review_dir / filename
        write_json(path, review)
        records.append(_file_record(export_dir, path))
        review_files.append({"profile_id": review.get("profile_id"), "track_id": review.get("track_id"), "review_id": review.get("review_id"), "path": f"encoded-audio-acceptance/reviews/{filename}", "payload_hash": encoded_audio_review_integrity_hash(review)})
    return sanitize_metadata(
        {
            **encoded_audio_acceptance_summary_public(summary),
            "target_id": target.target_id,
            "summary_hash": encoded_audio_acceptance_summary_hash(summary),
            "summary_path": "encoded-audio-acceptance/summary.json",
            "health_files": health_files,
            "review_hashes": review_files,
            "health_count": len(health_files),
            "review_count": len(review_files),
        },
        blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS,
    )


def _normalize_markers(value: Any) -> list[ImplementationDocument]:
    markers = _as_list(value)
    result = []
    for index, item in enumerate(markers, start=1):
        if not isinstance(item, dict):
            continue
        seconds = _float(item.get("time_seconds"))
        if seconds < 0:
            raise EncodedAudioAcceptanceError("marker time_seconds cannot be negative.")
        category = str(item.get("category") or "other").strip()
        if category not in ENCODED_REVIEW_MARKER_CATEGORIES:
            category = "other"
        severity = str(item.get("severity") or "medium").strip()
        if severity not in ENCODED_REVIEW_MARKER_SEVERITIES:
            severity = "medium"
        result.append(
            {
                "marker_id": _validate_marker_id(str(item.get("marker_id") or f"m-{index:06d}")),
                "time_seconds": round(seconds, 3),
                "severity": severity,
                "category": category,
                "message": sanitize_sensitive_text(str(item.get("message") or ""))[:800],
            }
        )
    return result


def _worst_status(reports: list[ImplementationDocument]) -> str:
    statuses = [
        (report.get("summary") or {}).get("status") if isinstance(report.get("summary"), dict) else report.get("status")
        for report in reports
        if isinstance(report, dict)
    ]
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "warning" for status in statuses):
        return "warning"
    if any(status == "passed" for status in statuses):
        return "passed"
    return "missing"


def _validate_profile_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise EncodedAudioAcceptanceError("Invalid encoded audio profile id.")
    return text


def _validate_track_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise EncodedAudioAcceptanceError("Invalid encoded audio track id.")
    return text


def _validate_review_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("ear-") or not text[4:].isdigit():
        raise EncodedAudioAcceptanceError("Invalid encoded audio review id.")
    return text


def _validate_marker_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("m-") or not text[2:].isdigit():
        raise EncodedAudioAcceptanceError("Invalid encoded audio review marker id.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise EncodedAudioAcceptanceStateError("Path is outside the allowed encoded audio directory.") from exc


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    rel = validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0

_v142_eaa_readiness.bind_globals(globals())
_v142_eaa_evidence.bind_globals(globals())
