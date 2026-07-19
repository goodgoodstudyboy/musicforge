# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from pathlib import Path as Path
from song_agent.domains.quality.audio_encoding import AudioEncodingStateError as AudioEncodingStateError, AudioEncodingStore as AudioEncodingStore, detect_audio_header as detect_audio_header, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_manifest_uses_fake as encoded_manifest_uses_fake, normalize_required_profiles as normalize_required_profiles, validate_relative_path as validate_relative_path
from song_agent.domains.quality.audio_encoding_profiles import audio_encoding_profile_hash as audio_encoding_profile_hash
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, DistributionTarget as DistributionTarget
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS = _make_deferred_global('ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS')
EncodedAudioAcceptanceError = _make_deferred_global('EncodedAudioAcceptanceError')
EncodedAudioAcceptanceNotFoundError = _make_deferred_global('EncodedAudioAcceptanceNotFoundError')
EncodedAudioAcceptanceStateError = _make_deferred_global('EncodedAudioAcceptanceStateError')
_ensure_within = _make_deferred_global('_ensure_within')
_normalize_markers = _make_deferred_global('_normalize_markers')
_sha256_file = _make_deferred_global('_sha256_file')
_validate_profile_id = _make_deferred_global('_validate_profile_id')
_validate_track_id = _make_deferred_global('_validate_track_id')
encoded_audio_health_integrity_ok = _make_deferred_global('encoded_audio_health_integrity_ok')
encoded_audio_payload_redaction_findings = _make_deferred_global('encoded_audio_payload_redaction_findings')
encoded_audio_review_integrity_hash = _make_deferred_global('encoded_audio_review_integrity_hash')
encoded_audio_review_source_hash = _make_deferred_global('encoded_audio_review_source_hash')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS, EncodedAudioAcceptanceError, EncodedAudioAcceptanceNotFoundError, EncodedAudioAcceptanceStateError, _ensure_within, _normalize_markers, _sha256_file
    global _validate_profile_id, _validate_track_id, encoded_audio_health_integrity_ok, encoded_audio_payload_redaction_findings, encoded_audio_review_integrity_hash, encoded_audio_review_source_hash, item
    ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS = namespace.get('ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS', ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
    EncodedAudioAcceptanceError = namespace.get('EncodedAudioAcceptanceError', EncodedAudioAcceptanceError)
    EncodedAudioAcceptanceNotFoundError = namespace.get('EncodedAudioAcceptanceNotFoundError', EncodedAudioAcceptanceNotFoundError)
    EncodedAudioAcceptanceStateError = namespace.get('EncodedAudioAcceptanceStateError', EncodedAudioAcceptanceStateError)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _normalize_markers = namespace.get('_normalize_markers', _normalize_markers)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _validate_profile_id = namespace.get('_validate_profile_id', _validate_profile_id)
    _validate_track_id = namespace.get('_validate_track_id', _validate_track_id)
    encoded_audio_health_integrity_ok = namespace.get('encoded_audio_health_integrity_ok', encoded_audio_health_integrity_ok)
    encoded_audio_payload_redaction_findings = namespace.get('encoded_audio_payload_redaction_findings', encoded_audio_payload_redaction_findings)
    encoded_audio_review_integrity_hash = namespace.get('encoded_audio_review_integrity_hash', encoded_audio_review_integrity_hash)
    encoded_audio_review_source_hash = namespace.get('encoded_audio_review_source_hash', encoded_audio_review_source_hash)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


ENCODED_AUDIO_ACCEPTANCE_SCHEMA_VERSION = 1
ENCODED_AUDIO_HEALTH_SCHEMA_VERSION = 1
ENCODED_AUDIO_REVIEW_SCHEMA_VERSION = 1
ENCODED_AUDIO_ACCEPTANCE_SUMMARY_SCHEMA_VERSION = 1
ENCODED_REVIEW_STATUSES = {"accepted", "needs_fix", "rejected", "waived"}
ENCODED_REVIEW_MODES = {"manual", "external_import", "synthetic"}
ENCODED_REVIEW_MARKER_CATEGORIES = {"format_artifact", "codec", "loudness", "noise", "gap", "metadata", "other"}
ENCODED_REVIEW_MARKER_SEVERITIES = {"low", "medium", "high", "critical"}
ENCODED_HEALTH_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
ENCODED_REVIEW_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
ENCODED_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
MIN_ENCODED_AUDIO_BYTES = {"mp3": 16 * 1024, "flac": 16 * 1024, "aac": 16 * 1024, "wav": 44}




class EncodedAudioAcceptanceStoreEvidenceMixin:
    def encoded_track_context(self, release_id: str, profile_id: str, track_id: str, *, require_reviewable: bool = True) -> DomainDocument:
        release = self.release_store.get_release(release_id)
        track = next((item for item in release.tracks if item.track_id == track_id), None)
        if track is None:
            raise EncodedAudioAcceptanceNotFoundError(f"Release track not found: {track_id}.")
        profile = self.audio_encoding_store.profile_store.get_profile(profile_id)
        manifest = self.audio_encoding_store.read_manifest(release_id, profile_id, default={})
        if not manifest:
            raise EncodedAudioAcceptanceStateError(f"Encoded audio manifest not found: {profile_id}.")
        if require_reviewable and (manifest.get("stale") or not encoded_manifest_integrity_ok(manifest)):
            raise EncodedAudioAcceptanceStateError("Encoded audio manifest is stale or tampered.")
        if require_reviewable and encoded_manifest_uses_fake(manifest):
            raise EncodedAudioAcceptanceStateError("Fake encoded audio evidence cannot be reviewed for release acceptance.")
        row = next((item for item in manifest.get("tracks", []) if isinstance(item, dict) and item.get("track_id") == track_id), None)
        if not row:
            raise EncodedAudioAcceptanceNotFoundError(f"Encoded track audio not found: {profile_id}/{track_id}.")
        output_rel = validate_relative_path(str(row.get("output_rel") or ""))
        output_path = (self.audio_encoding_store.root_dir(release_id) / output_rel).resolve()
        _ensure_within(self.audio_encoding_store.root_dir(release_id).resolve(), output_path)
        if not output_path.exists() or not output_path.is_file() or output_path.is_symlink():
            raise EncodedAudioAcceptanceStateError("Encoded track audio file is missing.")
        output_sha = _sha256_file(output_path)
        if output_sha != row.get("output_sha256"):
            raise EncodedAudioAcceptanceStateError("Encoded track audio hash does not match manifest.")
        health = self.read_health(release_id, profile_id, default={})
        if not health and require_reviewable:
            health = self.build_health(release_id, profile_id)
            if self.release_store.get_release(release_id).status not in {"signed", "archived"} and not self.release_store.read_signoff(release_id, default={}):
                self.health_path(release_id, profile_id).parent.mkdir(parents=True, exist_ok=True)
                write_json(self.health_path(release_id, profile_id), health)
                health = self.with_current_health_state(health)
        if require_reviewable and (not health or health.get("stale") or not encoded_audio_health_integrity_ok(health)):
            raise EncodedAudioAcceptanceStateError("Encoded audio health is missing, stale, or tampered.")
        health_status = (health.get("summary") or {}).get("status") if isinstance(health.get("summary"), dict) else ""
        if require_reviewable and health_status not in {"passed", "warning"}:
            raise EncodedAudioAcceptanceStateError("Encoded audio health does not allow review evidence.")
        return {
            "release": release.to_dict(),
            "track": track.to_dict(),
            "profile": profile.to_dict(),
            "manifest": manifest,
            "manifest_track": row,
            "health": health,
            "encoded_audio_evidence": {
                "profile_id": profile_id,
                "profile_hash": audio_encoding_profile_hash(profile),
                "format": profile.format,
                "extension": profile.extension,
                "manifest_hash": manifest.get("integrity_hash"),
                "manifest_source_hash": manifest.get("source_hash"),
                "encoded_track_hash": output_sha,
                "encoded_track_size_bytes": output_path.stat().st_size,
                "output_rel": output_rel,
                "source_wav_sha256": row.get("source_wav_sha256"),
                "health_hash": health.get("integrity_hash") if isinstance(health, dict) else None,
                "health_status": health_status or None,
            },
        }

    def _build_review(self, release_id: str, review_id: str, payload: DomainDocument, *, now: str, created_at: str | None = None) -> DomainDocument:
        profile_id = _validate_profile_id(str(payload.get("profile_id") or ""))
        track_id = _validate_track_id(str(payload.get("track_id") or ""))
        status = str(payload.get("status") or "accepted").strip()
        if status not in ENCODED_REVIEW_STATUSES:
            raise EncodedAudioAcceptanceError(f"status must be one of: {', '.join(sorted(ENCODED_REVIEW_STATUSES))}.")
        review_mode = str(payload.get("review_mode") or "manual").strip()
        if review_mode not in ENCODED_REVIEW_MODES:
            raise EncodedAudioAcceptanceError(f"review_mode must be one of: {', '.join(sorted(ENCODED_REVIEW_MODES))}.")
        playback_confirmed = bool(payload.get("playback_confirmed", False))
        rating = max(0, min(5, int(payload.get("rating") or 0)))
        if status == "accepted":
            if not playback_confirmed:
                raise EncodedAudioAcceptanceError("playback_confirmed=true is required for accepted encoded audio reviews.")
            if rating < 1:
                raise EncodedAudioAcceptanceError("rating is required for accepted encoded audio reviews.")
        context = self.encoded_track_context(release_id, profile_id, track_id, require_reviewable=True)
        reviewer = _as_document(payload.get("reviewer"))
        if review_mode in {"manual", "external_import"} and not str(reviewer.get("name") or payload.get("reviewer_name") or "").strip():
            raise EncodedAudioAcceptanceError("reviewer.name is required for manual encoded audio reviews.")
        review = {
            "schema_version": ENCODED_AUDIO_REVIEW_SCHEMA_VERSION,
            "review_id": review_id,
            "release_id": release_id,
            "profile_id": profile_id,
            "track_id": track_id,
            "project_id": (context["track"] or {}).get("project_id"),
            "version_id": (context["track"] or {}).get("version_id"),
            "status": status,
            "review_mode": review_mode,
            "reviewer": {
                "name": sanitize_sensitive_text(str(reviewer.get("name") or payload.get("reviewer_name") or "reviewer"))[:120],
                "role": sanitize_sensitive_text(str(reviewer.get("role") or ""))[:80],
            },
            "rating": rating,
            "listened_at": str(payload.get("listened_at") or now),
            "listening_device": sanitize_sensitive_text(str(payload.get("listening_device") or ""))[:160],
            "playback_confirmed": playback_confirmed,
            "encoded_audio_evidence": context["encoded_audio_evidence"],
            "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:4000],
            "tags": [sanitize_sensitive_text(str(item))[:80] for item in payload.get("tags", []) if str(item).strip()][:24] if isinstance(payload.get("tags"), list) else [],
            "markers": _normalize_markers(payload.get("markers")),
            "imported_from": sanitize_metadata(payload.get("imported_from"), blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS) if isinstance(payload.get("imported_from"), dict) else {},
            "redaction_findings": encoded_audio_payload_redaction_findings(payload),
            "source_hash": encoded_audio_review_source_hash(context),
            "created_at": created_at or now,
            "updated_at": now,
        }
        review["integrity_hash"] = encoded_audio_review_integrity_hash(review)
        review["current_source_hash"] = review["source_hash"]
        review["stale"] = False
        review["current"] = True
        review["stale_reasons"] = []
        return sanitize_metadata(review, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def _health_track(self, release_id: str, manifest: DomainDocument, row: DomainDocument) -> DomainDocument:
        failures: list[str] = []
        warnings: list[str] = []
        profile_id = str(manifest.get("profile_id") or "")
        fmt = str(manifest.get("format") or "")
        output_rel = str(row.get("output_rel") or "")
        try:
            output_rel = validate_relative_path(output_rel)
            output_path = (self.audio_encoding_store.root_dir(release_id) / output_rel).resolve()
            _ensure_within(self.audio_encoding_store.root_dir(release_id).resolve(), output_path)
        except Exception:
            failures.append("unsafe_output_path")
            output_path = self.audio_encoding_store.root_dir(release_id) / "_missing"
        size = 0
        actual_sha = None
        header = {"valid": False, "detected_format": "missing", "expected_format": fmt}
        if not failures:
            if not output_path.exists() or not output_path.is_file() or output_path.is_symlink():
                failures.append("output_missing")
            else:
                size = output_path.stat().st_size
                actual_sha = _sha256_file(output_path)
                if actual_sha != row.get("output_sha256"):
                    failures.append("output_hash_mismatch")
                header = detect_audio_header(output_path, expected_format=fmt)
                if not header.get("valid"):
                    failures.append("header_mismatch")
                minimum = MIN_ENCODED_AUDIO_BYTES.get(fmt, 8)
                if size < minimum:
                    failures.append("size_too_small")
        status = "failed" if failures else "warning" if warnings else "passed"
        payload = {
            "track_id": row.get("track_id"),
            "profile_id": profile_id,
            "status": status,
            "format": fmt,
            "extension": manifest.get("extension"),
            "output_rel": output_rel,
            "size_bytes": size,
            "min_size_bytes": MIN_ENCODED_AUDIO_BYTES.get(fmt, 8),
            "encoded_sha256": actual_sha,
            "manifest_sha256": row.get("output_sha256"),
            "source_wav_sha256": row.get("source_wav_sha256"),
            "duration_seconds": row.get("duration_seconds"),
            "header": header,
            "failures": failures,
            "warnings": warnings,
        }
        payload["track_health_hash"] = stable_hash(payload)
        return sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def _reserve_review_id(self, release_id: str) -> str:
        root = self.reviews_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            review_id = f"ear-{index:06d}"
            if not (root / f"{review_id}.json").exists():
                return review_id
        raise EncodedAudioAcceptanceError("Unable to allocate encoded audio review id.")

    def _required_profiles(self, release_id: str, profiles: list[str] | None) -> list[str]:
        values = normalize_required_profiles(profiles or [])
        if not values:
            values = [
                str(manifest.get("profile_id") or "")
                for manifest in self.audio_encoding_store.list_manifests(release_id)
                if str(manifest.get("profile_id") or "") and str(manifest.get("profile_id") or "") != "wav_master"
            ]
        return [item for item in values if item and item != "wav_master"]

    def _ensure_release_mutable(self, release_id: str) -> None:
        document = self.release_store.get_release(release_id)
        if document.status == "archived":
            raise EncodedAudioAcceptanceStateError("Archived releases are read-only.")
        if document.status == "signed" or self.release_store.read_signoff(release_id, default={}):
            raise EncodedAudioAcceptanceStateError("Signed releases cannot change encoded audio acceptance evidence. Reset signoff first.")

    def _append_event(self, release_id: str, event_type: str, payload: DomainDocument, now: str) -> None:
        root = self.root_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
        with (root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)
