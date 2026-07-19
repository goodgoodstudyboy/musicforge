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
EncodedAudioAcceptanceNotFoundError = _make_deferred_global('EncodedAudioAcceptanceNotFoundError')
_validate_profile_id = _make_deferred_global('_validate_profile_id')
_validate_review_id = _make_deferred_global('_validate_review_id')
_worst_status = _make_deferred_global('_worst_status')
encoded_audio_acceptance_allows_signoff = _make_deferred_global('encoded_audio_acceptance_allows_signoff')
encoded_audio_acceptance_source_hash = _make_deferred_global('encoded_audio_acceptance_source_hash')
encoded_audio_acceptance_summary_hash = _make_deferred_global('encoded_audio_acceptance_summary_hash')
encoded_audio_acceptance_summary_public = _make_deferred_global('encoded_audio_acceptance_summary_public')
encoded_audio_health_hash = _make_deferred_global('encoded_audio_health_hash')
encoded_audio_health_integrity_ok = _make_deferred_global('encoded_audio_health_integrity_ok')
encoded_audio_health_source = _make_deferred_global('encoded_audio_health_source')
encoded_audio_review_integrity_hash = _make_deferred_global('encoded_audio_review_integrity_hash')
encoded_audio_review_integrity_ok = _make_deferred_global('encoded_audio_review_integrity_ok')
encoded_audio_review_redaction_findings = _make_deferred_global('encoded_audio_review_redaction_findings')
encoded_audio_review_source_hash = _make_deferred_global('encoded_audio_review_source_hash')
failure = _make_deferred_global('failure')
item = _make_deferred_global('item')
reason = _make_deferred_global('reason')
warning = _make_deferred_global('warning')

def bind_globals(namespace: dict[str, object]) -> None:
    global ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS, EncodedAudioAcceptanceNotFoundError, _validate_profile_id, _validate_review_id, _worst_status, encoded_audio_acceptance_allows_signoff, encoded_audio_acceptance_source_hash
    global encoded_audio_acceptance_summary_hash, encoded_audio_acceptance_summary_public, encoded_audio_health_hash, encoded_audio_health_integrity_ok, encoded_audio_health_source, encoded_audio_review_integrity_hash, encoded_audio_review_integrity_ok, encoded_audio_review_redaction_findings
    global encoded_audio_review_source_hash, failure, item, reason, warning
    ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS = namespace.get('ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS', ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
    EncodedAudioAcceptanceNotFoundError = namespace.get('EncodedAudioAcceptanceNotFoundError', EncodedAudioAcceptanceNotFoundError)
    _validate_profile_id = namespace.get('_validate_profile_id', _validate_profile_id)
    _validate_review_id = namespace.get('_validate_review_id', _validate_review_id)
    _worst_status = namespace.get('_worst_status', _worst_status)
    encoded_audio_acceptance_allows_signoff = namespace.get('encoded_audio_acceptance_allows_signoff', encoded_audio_acceptance_allows_signoff)
    encoded_audio_acceptance_source_hash = namespace.get('encoded_audio_acceptance_source_hash', encoded_audio_acceptance_source_hash)
    encoded_audio_acceptance_summary_hash = namespace.get('encoded_audio_acceptance_summary_hash', encoded_audio_acceptance_summary_hash)
    encoded_audio_acceptance_summary_public = namespace.get('encoded_audio_acceptance_summary_public', encoded_audio_acceptance_summary_public)
    encoded_audio_health_hash = namespace.get('encoded_audio_health_hash', encoded_audio_health_hash)
    encoded_audio_health_integrity_ok = namespace.get('encoded_audio_health_integrity_ok', encoded_audio_health_integrity_ok)
    encoded_audio_health_source = namespace.get('encoded_audio_health_source', encoded_audio_health_source)
    encoded_audio_review_integrity_hash = namespace.get('encoded_audio_review_integrity_hash', encoded_audio_review_integrity_hash)
    encoded_audio_review_integrity_ok = namespace.get('encoded_audio_review_integrity_ok', encoded_audio_review_integrity_ok)
    encoded_audio_review_redaction_findings = namespace.get('encoded_audio_review_redaction_findings', encoded_audio_review_redaction_findings)
    encoded_audio_review_source_hash = namespace.get('encoded_audio_review_source_hash', encoded_audio_review_source_hash)
    failure = namespace.get('failure', failure)
    item = namespace.get('item', item)
    reason = namespace.get('reason', reason)
    warning = namespace.get('warning', warning)
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




class EncodedAudioAcceptanceStoreReadinessMixin:
    def root_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "encoded-audio" / "acceptance"

    def health_dir(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "health"

    def reviews_dir(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "reviews"

    def summary_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "summary.json"

    def health_path(self, release_id: str, profile_id: str) -> Path:
        return self.health_dir(release_id) / f"{_validate_profile_id(profile_id)}.json"

    def review_path(self, release_id: str, review_id: str) -> Path:
        return self.reviews_dir(release_id) / f"{_validate_review_id(review_id)}.json"

    def list_health(self, release_id: str) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        rows: list[DomainDocument] = []
        if not self.health_dir(release_id).exists():
            return rows
        for path in sorted(self.health_dir(release_id).glob("*.json")):
            try:
                report = read_json(path)
                if isinstance(report, dict):
                    rows.append(self.with_current_health_state(report))
            except Exception:
                continue
        return rows

    def read_health(self, release_id: str, profile_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.health_path(release_id, profile_id)
        if not path.exists():
            if default is not None:
                return default
            raise EncodedAudioAcceptanceNotFoundError(f"Encoded audio health report not found: {profile_id}.")
        data = read_json(path)
        return self.with_current_health_state(_as_document(data))

    def refresh_health(self, release_id: str, profile_ids: list[str] | None = None, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        profile_ids = self._required_profiles(release_id, profile_ids)
        reports = []
        with self.lock:
            for profile_id in profile_ids:
                report = self.build_health(release_id, profile_id, now=now)
                path = self.health_path(release_id, profile_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                write_json(path, report)
                reports.append(self.with_current_health_state(report))
            self._append_event(release_id, "encoded_audio_health_refreshed", {"profiles": profile_ids, "status": _worst_status(reports)}, now)
        return {"release_id": release_id, "profiles": reports, "summary": {"status": _worst_status(reports), "profile_count": len(reports)}}

    def build_health(self, release_id: str, profile_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        profile_id = _validate_profile_id(profile_id)
        manifest = self.audio_encoding_store.read_manifest(release_id, profile_id, default={})
        profile = self.audio_encoding_store.profile_store.get_profile(profile_id)
        if not manifest:
            report = {
                "schema_version": ENCODED_AUDIO_HEALTH_SCHEMA_VERSION,
                "release_id": release_id,
                "profile_id": profile_id,
                "generated_at": now,
                "source_hash": "",
                "source": {"status": "missing", "profile_hash": audio_encoding_profile_hash(profile)},
                "summary": {"status": "failed", "track_count": 0, "passed_count": 0, "failed_count": 1, "warning_count": 0},
                "tracks": [],
                "failures": ["manifest_missing"],
                "warnings": [],
            }
            report["integrity_hash"] = encoded_audio_health_hash(report)
            return sanitize_metadata(report, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
        tracks = []
        for row in manifest.get("tracks", []) if isinstance(manifest.get("tracks"), list) else []:
            if isinstance(row, dict):
                tracks.append(self._health_track(release_id, manifest, row))
        failures = []
        warnings: list[object] = []
        if manifest.get("stale") or not encoded_manifest_integrity_ok(manifest):
            failures.append("manifest_stale_or_tampered")
        if encoded_manifest_uses_fake(manifest):
            failures.append("fake_encoder_evidence")
        failures.extend(f"{row.get('track_id')}:{failure}" for row in tracks for failure in row.get("failures", []) if isinstance(row, dict))
        warnings.extend(f"{row.get('track_id')}:{warning}" for row in tracks for warning in row.get("warnings", []) if isinstance(row, dict))
        failed_count = len([row for row in tracks if row.get("status") == "failed"])
        warning_count = len([row for row in tracks if row.get("status") == "warning"])
        status = "failed" if failures or failed_count else "warning" if warnings or warning_count else "passed"
        source = encoded_audio_health_source(manifest)
        report = {
            "schema_version": ENCODED_AUDIO_HEALTH_SCHEMA_VERSION,
            "release_id": release_id,
            "profile_id": profile_id,
            "generated_at": now,
            "source_hash": stable_hash(source),
            "source": source,
            "summary": {
                "status": status,
                "track_count": len(tracks),
                "passed_count": len([row for row in tracks if row.get("status") == "passed"]),
                "failed_count": failed_count,
                "warning_count": warning_count,
            },
            "tracks": tracks,
            "failures": sorted(set(failures)),
            "warnings": sorted(set(warnings)),
        }
        report["integrity_hash"] = encoded_audio_health_hash(report)
        return sanitize_metadata(report, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def with_current_health_state(self, report: DomainDocument) -> DomainDocument:
        clean = sanitize_metadata(_as_document(report), blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
        reasons: list[str] = []
        current_source_hash = ""
        try:
            manifest = self.audio_encoding_store.read_manifest(str(clean.get("release_id") or ""), str(clean.get("profile_id") or ""), default={})
            if manifest:
                current_source_hash = stable_hash(encoded_audio_health_source(manifest))
        except Exception as exc:
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "encoded_manifest_unavailable")
        if current_source_hash and str(clean.get("source_hash") or "") != current_source_hash:
            reasons.append("source_changed")
        if not encoded_audio_health_integrity_ok(clean):
            reasons.append("health_integrity")
        clean["current_source_hash"] = current_source_hash or None
        clean["stale_reasons"] = sorted(set(reason for reason in reasons if reason))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def list_reviews(self, release_id: str, *, include_deleted: bool = False) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        rows: list[DomainDocument] = []
        if not self.reviews_dir(release_id).exists():
            return rows
        for path in sorted(self.reviews_dir(release_id).glob("ear-*.json")):
            try:
                review = self.with_current_review_state(read_json(path))
            except Exception:
                continue
            if review.get("status") == "deleted" and not include_deleted:
                continue
            rows.append(review)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def read_review(self, release_id: str, review_id: str) -> DomainDocument:
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise EncodedAudioAcceptanceNotFoundError(review_id)
        return self.with_current_review_state(read_json(path))

    def create_review(self, release_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        with self.lock:
            review_id = self._reserve_review_id(release_id)
            review = self._build_review(release_id, review_id, payload, now=now)
            write_json(self.review_path(release_id, review_id), review)
            self._append_event(release_id, "encoded_audio_review_created", {"review_id": review_id, "profile_id": review.get("profile_id"), "track_id": review.get("track_id")}, now)
            return self.with_current_review_state(review)

    def update_review(self, release_id: str, review_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        existing = self.read_review(release_id, review_id)
        merged = {
            **existing,
            "status": payload.get("status", existing.get("status")),
            "review_mode": payload.get("review_mode", existing.get("review_mode")),
            "reviewer": payload.get("reviewer", existing.get("reviewer")),
            "rating": payload.get("rating", existing.get("rating")),
            "listened_at": payload.get("listened_at", existing.get("listened_at")),
            "playback_confirmed": payload.get("playback_confirmed", existing.get("playback_confirmed")),
            "listening_device": payload.get("listening_device", existing.get("listening_device")),
            "notes": payload.get("notes", existing.get("notes")),
            "tags": payload.get("tags", existing.get("tags")),
            "markers": payload.get("markers", existing.get("markers")),
            "updated_at": now,
        }
        rebuilt = self._build_review(release_id, review_id, merged, now=now, created_at=str(existing.get("created_at") or now))
        write_json(self.review_path(release_id, review_id), rebuilt)
        self._append_event(release_id, "encoded_audio_review_updated", {"review_id": review_id, "profile_id": rebuilt.get("profile_id"), "track_id": rebuilt.get("track_id")}, now)
        return self.with_current_review_state(rebuilt)

    def delete_review(self, release_id: str, review_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise EncodedAudioAcceptanceNotFoundError(review_id)
        path.unlink()
        self._append_event(release_id, "encoded_audio_review_deleted", {"review_id": review_id}, now)
        return {"review_id": review_id, "deleted": True}

    def write_summary(self, release_id: str, *, required_profiles: list[str] | None = None, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        summary = self.build_summary(release_id, required_profiles=required_profiles, now=now)
        self.summary_path(release_id).parent.mkdir(parents=True, exist_ok=True)
        write_json(self.summary_path(release_id), summary)
        self._append_event(release_id, "encoded_audio_acceptance_refreshed", {"status": summary.get("status"), "required_profiles": summary.get("required_profiles")}, now)
        return summary

    def read_summary(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.summary_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise EncodedAudioAcceptanceNotFoundError("Encoded audio acceptance summary does not exist.")
        data = read_json(path)
        return sanitize_metadata(_as_document(data), blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def build_summary(self, release_id: str, *, required_profiles: list[str] | None = None, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        profiles = self._required_profiles(release_id, required_profiles)
        release = self.release_store.get_release(release_id)
        reviews = self.list_reviews(release_id)
        profile_rows: list[DomainDocument] = []
        track_rows: list[DomainDocument] = []
        blockers: list[str] = []
        warnings: list[str] = []
        for profile_id in profiles:
            manifest = self.audio_encoding_store.read_manifest(release_id, profile_id, default={})
            health = self.read_health(release_id, profile_id, default={})
            health_status = (health.get("summary") or {}).get("status") if isinstance(health.get("summary"), dict) else health.get("status")
            profile_blockers: list[str] = []
            if not manifest:
                profile_blockers.append("manifest_missing")
            elif manifest.get("stale") or not encoded_manifest_integrity_ok(manifest):
                profile_blockers.append("manifest_stale_or_tampered")
            elif encoded_manifest_uses_fake(manifest):
                profile_blockers.append("fake_encoder_evidence")
            if not health:
                profile_blockers.append("health_missing")
            elif health.get("stale") or not encoded_audio_health_integrity_ok(health):
                profile_blockers.append("health_stale_or_tampered")
            elif health_status == "failed":
                profile_blockers.append("health_failed")
            elif health_status == "warning":
                warnings.append(f"{profile_id}:health_warning")
            tracks = _as_list(manifest.get("tracks"))
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                track_id = str(track.get("track_id") or "")
                review_rows = [review for review in reviews if review.get("profile_id") == profile_id and review.get("track_id") == track_id]
                current_reviews = [
                    review
                    for review in review_rows
                    if not review.get("stale")
                    and encoded_audio_review_integrity_ok(review)
                    and not encoded_audio_review_redaction_findings(review)
                ]
                accepted_manual = [
                    review
                    for review in current_reviews
                    if review.get("status") == "accepted"
                    and review.get("review_mode") in {"manual", "external_import"}
                    and bool(review.get("playback_confirmed", False))
                ]
                synthetic_accepted = [review for review in current_reviews if review.get("status") == "accepted" and review.get("review_mode") == "synthetic"]
                needs_fix = [review for review in current_reviews if review.get("status") == "needs_fix"]
                rejected = [review for review in current_reviews if review.get("status") == "rejected"]
                stale_count = len([review for review in review_rows if review.get("stale")])
                tampered_count = len([review for review in review_rows if not encoded_audio_review_integrity_ok(review)])
                redaction_count = len([review for review in review_rows if encoded_audio_review_redaction_findings(review)])
                status = "accepted" if accepted_manual else "missing"
                if len(accepted_manual) > 1:
                    status = "duplicate_manual"
                if synthetic_accepted and not accepted_manual:
                    status = "synthetic_only"
                if needs_fix:
                    status = "needs_fix"
                if rejected:
                    status = "rejected"
                if stale_count:
                    status = "stale"
                if tampered_count:
                    status = "tampered"
                if redaction_count:
                    status = "redaction_failed"
                if not accepted_manual:
                    blockers.append(f"{profile_id}/{track_id}: manual encoded audio review is missing")
                if synthetic_accepted and not accepted_manual:
                    blockers.append(f"{profile_id}/{track_id}: synthetic encoded audio review cannot satisfy gate")
                if len(accepted_manual) > 1:
                    blockers.append(f"{profile_id}/{track_id}: multiple current manual encoded audio reviews")
                if needs_fix:
                    blockers.append(f"{profile_id}/{track_id}: encoded audio review needs work")
                if rejected:
                    blockers.append(f"{profile_id}/{track_id}: encoded audio review rejected")
                if stale_count:
                    blockers.append(f"{profile_id}/{track_id}: encoded audio review is stale")
                if tampered_count:
                    blockers.append(f"{profile_id}/{track_id}: encoded audio review integrity failed")
                if redaction_count:
                    blockers.append(f"{profile_id}/{track_id}: encoded audio review contains sensitive values")
                track_rows.append(
                    {
                        "profile_id": profile_id,
                        "track_id": track_id,
                        "status": status,
                        "format": manifest.get("format"),
                        "extension": manifest.get("extension"),
                        "manifest_hash": manifest.get("integrity_hash"),
                        "health_hash": health.get("integrity_hash"),
                        "encoded_track_hash": track.get("output_sha256"),
                        "review_count": len(review_rows),
                        "manual_accepted_count": len(accepted_manual),
                        "synthetic_accepted_count": len(synthetic_accepted),
                        "needs_fix_count": len(needs_fix),
                        "rejected_count": len(rejected),
                        "stale_count": stale_count,
                        "tampered_count": tampered_count,
                        "redaction_issue_count": redaction_count,
                        "accepted_review_id": accepted_manual[0].get("review_id") if accepted_manual else None,
                    }
                )
            if profile_blockers:
                blockers.extend(f"{profile_id}: {item}" for item in profile_blockers)
            profile_rows.append(
                {
                    "profile_id": profile_id,
                    "status": "failed" if profile_blockers else "warning" if health_status == "warning" else "passed",
                    "format": manifest.get("format") if manifest else None,
                    "extension": manifest.get("extension") if manifest else None,
                    "manifest_hash": manifest.get("integrity_hash") if manifest else None,
                    "source_hash": manifest.get("source_hash") if manifest else None,
                    "health_hash": health.get("integrity_hash") if health else None,
                    "track_count": len(tracks),
                    "blockers": profile_blockers,
                }
            )
        status = "failed" if blockers else "warning" if warnings else "passed"
        source_hash = encoded_audio_acceptance_source_hash(release.to_dict(), profiles, profile_rows, track_rows, reviews)
        summary = {
            "schema_version": ENCODED_AUDIO_ACCEPTANCE_SUMMARY_SCHEMA_VERSION,
            "release_id": release_id,
            "generated_at": now,
            "status": status,
            "source_hash": source_hash,
            "required_profiles": profiles,
            "profile_count": len(profiles),
            "track_count": len(track_rows),
            "covered_track_count": len([row for row in track_rows if int(row.get("review_count") or 0) > 0]),
            "manual_accepted_track_count": len([row for row in track_rows if int(row.get("manual_accepted_count") or 0) > 0]),
            "synthetic_only_track_count": len([row for row in track_rows if row.get("status") == "synthetic_only"]),
            "needs_fix_track_count": len([row for row in track_rows if int(row.get("needs_fix_count") or 0) > 0]),
            "rejected_track_count": len([row for row in track_rows if int(row.get("rejected_count") or 0) > 0]),
            "stale_review_count": sum(int(row.get("stale_count") or 0) for row in track_rows),
            "tampered_review_count": sum(int(row.get("tampered_count") or 0) for row in track_rows),
            "redaction_issue_count": sum(int(row.get("redaction_issue_count") or 0) for row in track_rows),
            "profiles": profile_rows,
            "tracks": track_rows,
            "review_hashes": [
                {
                    "profile_id": review.get("profile_id"),
                    "track_id": review.get("track_id"),
                    "review_id": review.get("review_id"),
                    "payload_hash": encoded_audio_review_integrity_hash(review),
                }
                for review in sorted(reviews, key=lambda item: str(item.get("review_id") or ""))
            ],
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
        }
        summary["integrity_hash"] = encoded_audio_acceptance_summary_hash(summary)
        return sanitize_metadata(summary, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def gate(self, release_id: str, *, required_profiles: list[str] | None = None, required: bool = False, now: str | None = None) -> DomainDocument:
        profiles = self._required_profiles(release_id, required_profiles)
        summary = self.build_summary(release_id, required_profiles=profiles, now=now)
        if not required:
            return {**encoded_audio_acceptance_summary_public(summary), "require_encoded_audio_review": False, "required_profiles": profiles, "hard_block": False}
        allowed = encoded_audio_acceptance_allows_signoff(summary)
        return {
            **encoded_audio_acceptance_summary_public(summary),
            "require_encoded_audio_review": True,
            "required_profiles": profiles,
            "summary_hash": encoded_audio_acceptance_summary_hash(summary),
            "source_hash": summary.get("source_hash"),
            "hard_block": not allowed,
            "message": "Encoded audio acceptance gate passed." if allowed else "Encoded audio acceptance gate failed.",
        }

    def with_current_review_state(self, review: DomainDocument) -> DomainDocument:
        clean = sanitize_metadata(_as_document(review), blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
        reasons: list[str] = []
        current_source_hash = ""
        try:
            context = self.encoded_track_context(
                str(clean.get("release_id") or ""),
                str(clean.get("profile_id") or ""),
                str(clean.get("track_id") or ""),
                require_reviewable=False,
            )
            current_source_hash = encoded_audio_review_source_hash(context)
            if str(clean.get("project_id") or "") != str((context.get("track") or {}).get("project_id") or "") or str(clean.get("version_id") or "") != str((context.get("track") or {}).get("version_id") or ""):
                reasons.append("track_identity_changed")
            if str(clean.get("source_hash") or "") != current_source_hash:
                reasons.append("source_changed")
            evidence = _as_document(clean.get("encoded_audio_evidence"))
            current_evidence = _as_document(context.get("encoded_audio_evidence"))
            for field in ("manifest_hash", "encoded_track_hash", "health_hash", "profile_hash"):
                if str(evidence.get(field) or "") != str(current_evidence.get(field) or ""):
                    reasons.append(field.replace("_hash", "_changed"))
            if current_evidence.get("health_status") not in {"passed", "warning"}:
                reasons.append("encoded_health_failed")
        except Exception as exc:
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "encoded_context_unavailable")
        if not encoded_audio_review_integrity_ok(clean):
            reasons.append("review_integrity")
        if encoded_audio_review_redaction_findings(clean):
            reasons.append("redaction_failed")
        clean["current_source_hash"] = current_source_hash or None
        clean["stale_reasons"] = sorted(set(reason for reason in reasons if reason))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
