from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from typing import Any

from song_agent.application.legacy_dependencies.audio_encoding import AudioEncodingStateError, AudioEncodingStore, detect_audio_header, encoded_manifest_integrity_ok, encoded_manifest_uses_fake, normalize_required_profiles, validate_relative_path
from song_agent.application.legacy_dependencies.audio_encoding_profiles import audio_encoding_profile_hash
from song_agent.application.legacy_dependencies.distribution import DistributionStore, DistributionTarget
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import ProjectStore, now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.application.legacy_dependencies.releases import BLOCKED_RELEASE_KEYS, ReleaseStore, stable_hash


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


class EncodedAudioAcceptanceStore:
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

    def list_health(self, release_id: str) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        rows: list[dict[str, Any]] = []
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

    def read_health(self, release_id: str, profile_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.health_path(release_id, profile_id)
        if not path.exists():
            if default is not None:
                return default
            raise EncodedAudioAcceptanceNotFoundError(f"Encoded audio health report not found: {profile_id}.")
        data = read_json(path)
        return self.with_current_health_state(data if isinstance(data, dict) else {})

    def refresh_health(self, release_id: str, profile_ids: list[str] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def build_health(self, release_id: str, profile_id: str, *, now: str | None = None) -> dict[str, Any]:
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
        warnings = []
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

    def with_current_health_state(self, report: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(report if isinstance(report, dict) else {}, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
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

    def list_reviews(self, release_id: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        rows: list[dict[str, Any]] = []
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

    def read_review(self, release_id: str, review_id: str) -> dict[str, Any]:
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise EncodedAudioAcceptanceNotFoundError(review_id)
        return self.with_current_review_state(read_json(path))

    def create_review(self, release_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        with self.lock:
            review_id = self._reserve_review_id(release_id)
            review = self._build_review(release_id, review_id, payload, now=now)
            write_json(self.review_path(release_id, review_id), review)
            self._append_event(release_id, "encoded_audio_review_created", {"review_id": review_id, "profile_id": review.get("profile_id"), "track_id": review.get("track_id")}, now)
            return self.with_current_review_state(review)

    def update_review(self, release_id: str, review_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
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

    def delete_review(self, release_id: str, review_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise EncodedAudioAcceptanceNotFoundError(review_id)
        path.unlink()
        self._append_event(release_id, "encoded_audio_review_deleted", {"review_id": review_id}, now)
        return {"review_id": review_id, "deleted": True}

    def write_summary(self, release_id: str, *, required_profiles: list[str] | None = None, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        summary = self.build_summary(release_id, required_profiles=required_profiles, now=now)
        self.summary_path(release_id).parent.mkdir(parents=True, exist_ok=True)
        write_json(self.summary_path(release_id), summary)
        self._append_event(release_id, "encoded_audio_acceptance_refreshed", {"status": summary.get("status"), "required_profiles": summary.get("required_profiles")}, now)
        return summary

    def read_summary(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.summary_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise EncodedAudioAcceptanceNotFoundError("Encoded audio acceptance summary does not exist.")
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {}, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)

    def build_summary(self, release_id: str, *, required_profiles: list[str] | None = None, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        profiles = self._required_profiles(release_id, required_profiles)
        release = self.release_store.get_release(release_id)
        reviews = self.list_reviews(release_id)
        profile_rows: list[dict[str, Any]] = []
        track_rows: list[dict[str, Any]] = []
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
            tracks = manifest.get("tracks") if isinstance(manifest.get("tracks"), list) else []
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

    def gate(self, release_id: str, *, required_profiles: list[str] | None = None, required: bool = False, now: str | None = None) -> dict[str, Any]:
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

    def with_current_review_state(self, review: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(review if isinstance(review, dict) else {}, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
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
            evidence = clean.get("encoded_audio_evidence") if isinstance(clean.get("encoded_audio_evidence"), dict) else {}
            current_evidence = context.get("encoded_audio_evidence") if isinstance(context.get("encoded_audio_evidence"), dict) else {}
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

    def encoded_track_context(self, release_id: str, profile_id: str, track_id: str, *, require_reviewable: bool = True) -> dict[str, Any]:
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

    def _build_review(self, release_id: str, review_id: str, payload: dict[str, Any], *, now: str, created_at: str | None = None) -> dict[str, Any]:
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
        reviewer = payload.get("reviewer") if isinstance(payload.get("reviewer"), dict) else {}
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

    def _health_track(self, release_id: str, manifest: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
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

    def _append_event(self, release_id: str, event_type: str, payload: dict[str, Any], now: str) -> None:
        root = self.root_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS)
        with (root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)


def encoded_audio_health_source(manifest: dict[str, Any]) -> dict[str, Any]:
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


def encoded_audio_health_hash(report: dict[str, Any]) -> str:
    payload = {key: value for key, value in report.items() if key not in ENCODED_HEALTH_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS))


def encoded_audio_health_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str((report or {}).get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_health_hash(report)


def encoded_audio_review_source_hash(context: dict[str, Any]) -> str:
    track = context.get("track") if isinstance(context.get("track"), dict) else {}
    profile = context.get("profile") if isinstance(context.get("profile"), dict) else {}
    evidence = context.get("encoded_audio_evidence") if isinstance(context.get("encoded_audio_evidence"), dict) else {}
    health = context.get("health") if isinstance(context.get("health"), dict) else {}
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


def encoded_audio_review_integrity_hash(review: dict[str, Any]) -> str:
    payload = {key: value for key, value in review.items() if key not in ENCODED_REVIEW_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS))


def encoded_audio_review_integrity_ok(review: dict[str, Any]) -> bool:
    expected = str((review or {}).get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_review_integrity_hash(review)


def encoded_audio_acceptance_source_hash(
    release: dict[str, Any],
    profiles: list[str],
    profile_rows: list[dict[str, Any]],
    track_rows: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
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


def encoded_audio_acceptance_summary_hash(summary: dict[str, Any]) -> str:
    payload = {key: value for key, value in summary.items() if key not in ENCODED_SUMMARY_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=ENCODED_AUDIO_ACCEPTANCE_BLOCKED_KEYS))


def encoded_audio_acceptance_summary_integrity_ok(summary: dict[str, Any]) -> bool:
    expected = str((summary or {}).get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_acceptance_summary_hash(summary)


def encoded_audio_acceptance_allows_signoff(summary: dict[str, Any]) -> bool:
    return (
        bool(summary)
        and encoded_audio_acceptance_summary_integrity_ok(summary)
        and summary.get("status") == "passed"
        and not summary.get("blockers")
        and int(summary.get("track_count") or 0) > 0
        and int(summary.get("manual_accepted_track_count") or 0) == int(summary.get("track_count") or -1)
    )


def encoded_audio_acceptance_summary_public(summary: dict[str, Any] | None) -> dict[str, Any]:
    data = summary if isinstance(summary, dict) else {}
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


def encoded_audio_payload_redaction_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

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


def encoded_audio_review_redaction_findings(review: dict[str, Any]) -> list[dict[str, Any]]:
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
) -> dict[str, Any]:
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
    records: list[dict[str, Any]],
) -> dict[str, Any]:
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


def _normalize_markers(value: Any) -> list[dict[str, Any]]:
    markers = value if isinstance(value, list) else []
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


def _worst_status(reports: list[dict[str, Any]]) -> str:
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


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    rel = validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
