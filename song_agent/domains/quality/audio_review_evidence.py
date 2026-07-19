from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import os as os
import threading as threading
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_artifacts import audio_artifact_summary as audio_artifact_summary, audio_artifact_stale_reasons_for_profile as audio_artifact_stale_reasons_for_profile
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_allows_release as audio_health_allows_release, audio_health_integrity_ok as audio_health_integrity_ok, audio_health_summary as audio_health_summary
from song_agent.domains.quality.audio_profiles import AudioProfileStore as AudioProfileStore
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio import read_release_audio_qa as read_release_audio_qa, release_audio_report_integrity_ok as release_audio_report_integrity_ok, release_audio_source_hash as release_audio_source_hash
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.review_tasks import REVIEW_TASK_SCHEMA_VERSION as REVIEW_TASK_SCHEMA_VERSION, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore


AUDIO_REVIEW_SCHEMA_VERSION = 1
AUDIO_REVIEW_SUMMARY_SCHEMA_VERSION = 1
REVIEW_STATUSES = {"accepted", "needs_fix", "rejected", "waived"}
REVIEW_MODES = {"manual", "synthetic"}
MARKER_CATEGORIES = {"arrangement", "melody", "harmony", "rhythm", "mix_balance", "sound_quality", "structure", "hook", "other"}
MARKER_SEVERITIES = {"low", "medium", "high", "critical"}
_SUMMARY_FILENAME = "release-audio-review-summary.json"
_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
_SUMMARY_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "generated_at"}


class AudioReviewEvidenceError(ValueError):
    pass


class AudioReviewEvidenceNotFoundError(AudioReviewEvidenceError):
    pass


class AudioReviewEvidenceStateError(AudioReviewEvidenceError):
    pass


class AudioReviewEvidenceStore:
    def __init__(self, release_store: ReleaseStore, project_store: ProjectStore | None = None) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.lock = threading.RLock()

    def reviews_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-reviews"

    def summary_path(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / _SUMMARY_FILENAME

    def review_path(self, release_id: str, review_id: str) -> Path:
        return self.reviews_dir(release_id) / f"{_validate_review_id(review_id)}.json"

    def list_reviews(self, release_id: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        root = self.reviews_dir(release_id)
        if not root.exists():
            return []
        reviews: list[dict[str, Any]] = []
        for path in root.glob("arv-*.json"):
            try:
                review = read_json(path)
                review = self.with_current_state(review)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if review.get("status") == "deleted" and not include_deleted:
                continue
            reviews.append(review)
        return sorted(reviews, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def read_review(self, release_id: str, review_id: str) -> dict[str, Any]:
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise AudioReviewEvidenceNotFoundError(review_id)
        return self.with_current_state(read_json(path))

    def create_review(self, release_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        with self.lock:
            review_id = self._reserve_review_id(release_id)
            review = self._build_review(release_id, review_id, payload, now=now)
            write_json(self.review_path(release_id, review_id), review)
            self._append_event(release_id, "release_audio_review_created", {"review_id": review_id, "track_id": review.get("track_id")}, now)
            return self.with_current_state(review)

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
            "notes": payload.get("notes", existing.get("notes")),
            "tags": payload.get("tags", existing.get("tags")),
            "markers": payload.get("markers", existing.get("markers")),
            "updated_at": now,
        }
        rebuilt = self._build_review(release_id, review_id, merged, now=now, created_at=str(existing.get("created_at") or now))
        write_json(self.review_path(release_id, review_id), rebuilt)
        self._append_event(release_id, "release_audio_review_updated", {"review_id": review_id, "track_id": rebuilt.get("track_id")}, now)
        return self.with_current_state(rebuilt)

    def delete_review(self, release_id: str, review_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise AudioReviewEvidenceNotFoundError(review_id)
        path.unlink()
        self._append_event(release_id, "release_audio_review_deleted", {"review_id": review_id}, now)
        return {"review_id": review_id, "deleted": True}

    def refresh_review(self, release_id: str, review_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        existing = self.read_review(release_id, review_id)
        rebuilt = self._build_review(release_id, review_id, existing, now=now, created_at=str(existing.get("created_at") or now))
        write_json(self.review_path(release_id, review_id), rebuilt)
        self._append_event(release_id, "release_audio_review_refreshed", {"review_id": review_id, "track_id": rebuilt.get("track_id")}, now)
        return self.with_current_state(rebuilt)

    def build_summary(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        release = self.release_store.get_release(release_id)
        reviews = self.list_reviews(release_id)
        by_track: dict[str, list[dict[str, Any]]] = {}
        for review in reviews:
            by_track.setdefault(str(review.get("track_id") or ""), []).append(review)
        track_summaries: list[dict[str, Any]] = []
        blockers: list[str] = []
        warnings: list[str] = []
        for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
            track_reviews = by_track.get(track.track_id, [])
            current_track_reviews = [
                review
                for review in track_reviews
                if str(review.get("project_id") or "") == str(track.project_id)
                and str(review.get("version_id") or "") == str(track.version_id)
            ]
            accepted_manual = [
                review
                for review in current_track_reviews
                if review.get("status") == "accepted"
                and review.get("review_mode") == "manual"
                and bool(review.get("playback_confirmed", False))
                and not review.get("stale")
                and review_integrity_ok(review)
                and not _review_redaction_findings(review)
            ]
            duplicate_manual_count = max(0, len(accepted_manual) - 1)
            synthetic_count = len([review for review in current_track_reviews if review.get("status") == "accepted" and review.get("review_mode") == "synthetic"])
            needs_fix_count = len([review for review in current_track_reviews if review.get("status") == "needs_fix"])
            rejected_count = len([review for review in current_track_reviews if review.get("status") == "rejected"])
            stale_count = len([review for review in current_track_reviews if review.get("stale")])
            tampered_count = len([review for review in current_track_reviews if not review_integrity_ok(review)])
            sensitive_count = len([review for review in current_track_reviews if _review_redaction_findings(review)])
            historical_review_count = max(0, len(track_reviews) - len(current_track_reviews))
            status = "accepted" if accepted_manual else "missing"
            if duplicate_manual_count:
                status = "duplicate_manual"
            if needs_fix_count:
                status = "needs_fix"
            if rejected_count:
                status = "rejected"
            if stale_count:
                status = "stale"
            if tampered_count:
                status = "tampered"
            if sensitive_count:
                status = "redaction_failed"
            if not accepted_manual:
                blockers.append(f"{track.track_id}: current manual accepted audio review is missing")
            if synthetic_count and not accepted_manual:
                blockers.append(f"{track.track_id}: synthetic audio review cannot satisfy per-track gate")
            if duplicate_manual_count:
                blockers.append(f"{track.track_id}: multiple current manual accepted audio reviews")
            if needs_fix_count:
                blockers.append(f"{track.track_id}: audio review needs work")
            if rejected_count:
                blockers.append(f"{track.track_id}: audio review rejected")
            if stale_count:
                blockers.append(f"{track.track_id}: audio review is stale")
            if tampered_count:
                blockers.append(f"{track.track_id}: audio review integrity failed")
            if sensitive_count:
                blockers.append(f"{track.track_id}: audio review contains sensitive values")
            track_summaries.append(
                {
                    "track_id": track.track_id,
                    "disc_number": track.disc_number,
                    "track_number": track.track_number,
                    "title": track.title,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "status": status,
                    "review_count": len(track_reviews),
                    "current_review_count": len(current_track_reviews),
                    "historical_review_count": historical_review_count,
                    "manual_accepted_count": len(accepted_manual),
                    "duplicate_manual_accepted_count": duplicate_manual_count,
                    "synthetic_accepted_count": synthetic_count,
                    "needs_fix_count": needs_fix_count,
                    "rejected_count": rejected_count,
                    "stale_count": stale_count,
                    "tampered_count": tampered_count,
                    "redaction_issue_count": sensitive_count,
                    "accepted_review_id": accepted_manual[0].get("review_id") if accepted_manual else None,
                }
            )
        status = "failed" if blockers else "warning" if warnings else "passed"
        source_hash = audio_review_summary_source_hash(release.to_dict(), reviews)
        summary = {
            "schema_version": AUDIO_REVIEW_SUMMARY_SCHEMA_VERSION,
            "release_id": release_id,
            "status": status,
            "generated_at": now,
            "source_hash": source_hash,
            "track_count": len(release.tracks),
            "covered_track_count": len([item for item in track_summaries if int(item.get("review_count") or 0) > 0]),
            "manual_accepted_track_count": len([item for item in track_summaries if int(item.get("manual_accepted_count") or 0) > 0]),
            "synthetic_only_track_count": len([item for item in track_summaries if int(item.get("synthetic_accepted_count") or 0) > 0 and int(item.get("manual_accepted_count") or 0) == 0]),
            "duplicate_manual_review_count": sum(int(item.get("duplicate_manual_accepted_count") or 0) for item in track_summaries),
            "needs_fix_track_count": len([item for item in track_summaries if int(item.get("needs_fix_count") or 0) > 0]),
            "rejected_track_count": len([item for item in track_summaries if int(item.get("rejected_count") or 0) > 0]),
            "stale_review_count": sum(int(item.get("stale_count") or 0) for item in track_summaries),
            "tampered_review_count": sum(int(item.get("tampered_count") or 0) for item in track_summaries),
            "redaction_issue_count": sum(int(item.get("redaction_issue_count") or 0) for item in track_summaries),
            "missing_track_ids": [item["track_id"] for item in track_summaries if int(item.get("manual_accepted_count") or 0) <= 0],
            "blocking_track_ids": sorted({str(item).split(":", 1)[0] for item in blockers if ":" in str(item)}),
            "tracks": track_summaries,
            "review_hashes": [
                {"track_id": review.get("track_id"), "review_id": review.get("review_id"), "payload_hash": review_payload_hash(review)}
                for review in sorted(reviews, key=lambda item: str(item.get("review_id") or ""))
            ],
            "blockers": blockers,
            "warnings": warnings,
        }
        summary["integrity_hash"] = audio_review_summary_hash(summary)
        return sanitize_metadata(summary, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def write_summary(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        summary = self.build_summary(release_id, now=now)
        write_json(self.summary_path(release_id), summary)
        self._append_event(release_id, "release_audio_review_summary_refreshed", {"status": summary.get("status")}, now or now_iso())
        return summary

    def read_summary(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.summary_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioReviewEvidenceNotFoundError("Release audio review summary does not exist.")
        data = read_json(path)
        return sanitize_metadata(_as_document(data), blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def create_review_task_from_marker(self, release_id: str, review_id: str, marker_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        payload = payload or {}
        review = self.read_review(release_id, review_id)
        if review.get("stale") or not review_integrity_ok(review):
            raise AudioReviewEvidenceStateError("Audio review is stale or tampered. Refresh review before creating ReviewTasks.")
        markers = _as_list(review.get("markers"))
        marker = next((item for item in markers if isinstance(item, dict) and item.get("marker_id") == marker_id), None)
        if not marker:
            raise AudioReviewEvidenceNotFoundError(marker_id)
        project_id = str(review.get("project_id") or "")
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.ensure_project_dir_is_safe(project_dir)
        document = self.project_store.get_project(project_id)
        existing_task_id = str(marker.get("review_task_id") or "")
        if existing_task_id:
            try:
                existing_task = ReviewTaskStore(project_dir).read_task(existing_task_id)
                if existing_task.status in {"open", "candidate_ready", "needs_more_work"}:
                    return {"status": "existing", "project_id": project_id, "task_id": existing_task.task_id, "marker": marker}
            except Exception:
                pass
        match = _matching_open_marker_task(project_dir, release_id, review_id, marker_id)
        if match:
            marker["review_task_id"] = match.task_id
            self._write_review_with_markers(release_id, review, markers, now=now)
            return {"status": "existing", "project_id": project_id, "task_id": match.task_id, "marker": marker}
        title = sanitize_sensitive_text(str(payload.get("title") or _marker_task_title(marker, review)))[:160]
        instruction = sanitize_sensitive_text(str(payload.get("instruction") or _marker_task_instruction(marker)))[:800]
        priority = _priority(payload.get("priority"), marker.get("severity"))
        task_store = ReviewTaskStore(project_dir)
        with task_store.lock:
            task_id, task_dir = task_store._reserve_task_dir()
            task = ReviewTask.from_dict(
                {
                    "schema_version": REVIEW_TASK_SCHEMA_VERSION,
                    "task_id": task_id,
                    "project_id": project_id,
                    "parent_version_id": str(review.get("version_id") or document.state.final_version_id or document.state.selected_version_id or document.state.latest_version_id or ""),
                    "preview_id": f"audio-review-{review_id}",
                    "audition_id": f"audio-marker-{marker_id}",
                    "status": "open",
                    "priority": priority,
                    "title": title,
                    "summary": instruction,
                    "source": {
                        "source_type": "release_audio_review_marker",
                        "release_id": release_id,
                        "track_id": review.get("track_id"),
                        "review_id": review_id,
                        "marker_id": marker_id,
                        "time_seconds": marker.get("time_seconds"),
                        "mapped": _as_document(marker.get("mapped")),
                        "audio_evidence": {
                            "wav_sha256": (review.get("audio_evidence") or {}).get("wav_sha256") if isinstance(review.get("audio_evidence"), dict) else None,
                            "audio_health_hash": (review.get("audio_evidence") or {}).get("audio_health_hash") if isinstance(review.get("audio_evidence"), dict) else None,
                        },
                    },
                    "review_snapshot": {"audio_review": review_public_summary(review), "marker": marker},
                    "target": {
                        "scope": "project_version",
                        "project_id": project_id,
                        "version_id": review.get("version_id"),
                        "time_seconds": marker.get("time_seconds"),
                        "section_id": (marker.get("mapped") or {}).get("section_id") if isinstance(marker.get("mapped"), dict) else None,
                        "category": marker.get("category"),
                        "target_track": sanitize_sensitive_text(str(payload.get("target_track") or ""))[:120],
                    },
                    "hashes": {"audio_review_source_hash": str(review.get("source_hash") or ""), "audio_review_integrity_hash": str(review.get("integrity_hash") or "")},
                    "counts": {"candidate_count": 0, "ready_candidate_count": 0, "failed_candidate_count": 0},
                    "created_at": now,
                    "updated_at": now,
                }
            )
            write_json(task_dir / "task.json", task.to_dict())
            _append_task_event(task_dir, "review_task_created_from_release_audio_review", {"release_id": release_id, "review_id": review_id, "marker_id": marker_id}, now)
        marker["review_task_id"] = task.task_id
        self._write_review_with_markers(release_id, review, markers, now=now)
        self._append_event(release_id, "release_audio_review_marker_task_created", {"review_id": review_id, "marker_id": marker_id, "task_id": task.task_id}, now)
        return {"status": "created", "project_id": project_id, "task_id": task.task_id, "review_task": task.to_dict(), "marker": marker}

    def import_human_review_pack(self, release_id: str, payload: dict[str, Any], *, acceptance_store: Any, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        if not isinstance(payload, dict):
            raise AudioReviewEvidenceError("Import payload must be an object.")
        suite_id = str(payload.get("suite_id") or "").strip()
        mapping = _as_list(payload.get("mapping"))
        if not suite_id:
            raise AudioReviewEvidenceError("suite_id is required.")
        if not mapping:
            raise AudioReviewEvidenceError("mapping is required.")
        imported: list[dict[str, Any]] = []
        for row in mapping:
            if not isinstance(row, dict):
                continue
            track_id = str(row.get("track_id") or "").strip()
            case_id = str(row.get("case_id") or "").strip()
            if not track_id or not case_id:
                raise AudioReviewEvidenceError("Each mapping item requires track_id and case_id.")
            context = self.track_audio_context(release_id, track_id, require_reviewable=True)
            case = acceptance_store.get_case(suite_id, case_id)
            review = acceptance_store.read_review(suite_id, case_id, default={})
            health = acceptance_store.read_health(suite_id, case_id, default={})
            health_summary = audio_health_summary(health)
            if not review:
                raise AudioReviewEvidenceStateError(f"{case_id} has no listening review.")
            if str(review.get("review_mode") or "") != "manual":
                raise AudioReviewEvidenceStateError(f"{case_id} review is not manual.")
            if str(review.get("status") or "") != "accepted":
                raise AudioReviewEvidenceStateError(f"{case_id} review is not accepted.")
            if not bool(review.get("playback_confirmed", False)):
                raise AudioReviewEvidenceStateError(f"{case_id} review playback is not confirmed.")
            if str(review.get("audio_mode") or "") != "wav":
                raise AudioReviewEvidenceStateError(f"{case_id} review is not WAV evidence.")
            case_wav_hash = str((review.get("audio_evidence") or {}).get("wav_sha256") or health_summary.get("wav_sha256") or "")
            track_wav_hash = str((context.get("audio_evidence") or {}).get("wav_sha256") or "")
            if not case_wav_hash or case_wav_hash != track_wav_hash:
                raise AudioReviewEvidenceStateError(f"{case_id} WAV hash does not match release track {track_id}.")
            created = self.create_review(
                release_id,
                {
                    "track_id": track_id,
                    "status": "accepted",
                    "review_mode": "manual",
                    "reviewer": {"name": review.get("listened_by") or "human-reviewer"},
                    "rating": review.get("rating", 0),
                    "listened_at": review.get("listened_at") or now,
                    "playback_confirmed": True,
                    "notes": review.get("notes") or f"Imported from Human Review Pack case {case_id}.",
                    "tags": [*([str(item) for item in review.get("tags", []) if str(item).strip()] if isinstance(review.get("tags"), list) else []), "human-review-pack"],
                    "markers": _markers_from_human_review(review),
                    "imported_from": {
                        "suite_id": suite_id,
                        "case_id": case_id,
                        "song_id": getattr(case, "song_id", None),
                        "pack_id": payload.get("pack_id"),
                        "import_id": payload.get("import_id"),
                    },
                },
                now=now,
            )
            imported.append({"track_id": track_id, "case_id": case_id, "review_id": created.get("review_id"), "status": created.get("status")})
        summary = self.write_summary(release_id, now=now)
        self._append_event(release_id, "release_audio_reviews_imported_from_human_review_pack", {"suite_id": suite_id, "imported_count": len(imported)}, now)
        return {"status": "imported", "release_id": release_id, "suite_id": suite_id, "imported_count": len(imported), "imported": imported, "summary": audio_review_summary_public(summary)}

    def with_current_state(self, review: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(review, dict):
            raise AudioReviewEvidenceError("Audio review must be an object.")
        reasons: list[str] = []
        current_source_hash = ""
        try:
            context = self.track_audio_context(str(review.get("release_id") or ""), str(review.get("track_id") or ""), require_reviewable=False)
            current_source_hash = audio_review_source_hash(
                release_id=str(review.get("release_id") or ""),
                track=context["track"],
                audio_evidence=context["audio_evidence"],
                song_plan=context["song_plan"],
            )
            if str(review.get("project_id") or "") != str(context["track"].get("project_id") or "") or str(review.get("version_id") or "") != str(context["track"].get("version_id") or ""):
                reasons.append("track_identity_changed")
            if str(review.get("source_hash") or "") != current_source_hash:
                reasons.append("source_changed")
            evidence = _as_document(review.get("audio_evidence"))
            current_evidence = context["audio_evidence"]
            if evidence.get("wav_sha256") != current_evidence.get("wav_sha256"):
                reasons.append("wav_changed")
            if current_evidence.get("audio_health_status") not in {"passed", "warning"}:
                reasons.append("audio_health_failed")
            if current_evidence.get("artifact_current") is not True:
                reasons.append("audio_artifact_stale")
        except Exception as exc:
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "audio_context_unavailable")
        if not review_integrity_ok(review):
            reasons.append("review_integrity")
        if _review_redaction_findings(review):
            reasons.append("redaction_failed")
        clean = dict(review)
        clean["current_source_hash"] = current_source_hash
        clean["stale_reasons"] = sorted(set(reason for reason in reasons if reason))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def track_audio_context(self, release_id: str, track_id: str, *, require_reviewable: bool = True) -> dict[str, Any]:
        release = self.release_store.get_release(release_id)
        track = next((item for item in release.tracks if item.track_id == track_id), None)
        if track is None:
            raise AudioReviewEvidenceNotFoundError(f"Release track not found: {track_id}.")
        export_dir = final_export_dir(self.project_store.project_dir(track.project_id)).resolve()
        project_root = self.project_store.project_dir(track.project_id).resolve()
        try:
            export_dir.relative_to(project_root)
        except ValueError as exc:
            raise AudioReviewEvidenceStateError("Project Final Export path is outside project root.") from exc
        wav_path = export_dir / "song.wav"
        artifact_path = export_dir / "audio-artifact.json"
        song_plan_path = export_dir / "song-plan.json"
        if not wav_path.exists() or not wav_path.is_file() or wav_path.is_symlink():
            raise AudioReviewEvidenceStateError("Track song.wav is missing.")
        artifact = read_json(artifact_path) if artifact_path.exists() and artifact_path.is_file() and not artifact_path.is_symlink() else {}
        artifact_stale = _artifact_stale_reasons(artifact, wav_path=wav_path, midi_path=export_dir / "song.mid", song_plan_path=song_plan_path, project_store=self.project_store)
        if require_reviewable and artifact_stale:
            raise AudioReviewEvidenceStateError("Track audio artifact is stale or missing.")
        song_plan = read_json(song_plan_path) if song_plan_path.exists() else {}
        qa_track = _current_audio_qa_track(self.release_store, self.project_store, release, release_id, track.track_id)
        health_report = _as_document(qa_track.get("health_report"))
        health_summary = _as_document(qa_track.get("health"))
        if not health_summary:
            if require_reviewable:
                health_report = analyze_wav_health(wav_path, source={"release_id": release_id, "track_id": track.track_id, "project_id": track.project_id, "version_id": track.version_id}, report_id=f"ahr-{release_id}-{track.track_id}", now=now_iso())
                health_summary = audio_health_summary(health_report)
            else:
                health_summary = {"status": "unknown", "wav_sha256": _sha256(wav_path), "duration_seconds": None, "integrity_hash": None}
        health_ok = bool(health_report) and audio_health_integrity_ok(health_report) and audio_health_allows_release(health_report)
        if not health_report and health_summary.get("status") in {"passed", "warning"} and health_summary.get("wav_sha256"):
            health_ok = True
        if require_reviewable and not health_ok:
            raise AudioReviewEvidenceStateError("Track audio health does not allow review evidence.")
        artifact_summary = audio_artifact_summary(artifact, wav_path=wav_path, midi_path=export_dir / "song.mid", song_plan_path=song_plan_path)
        health_hash = audio_health_content_hash(health_report) if health_report else health_summary.get("integrity_hash")
        audio_evidence = {
            "audio_artifact_id": artifact_summary.get("artifact_id"),
            "wav_sha256": health_summary.get("wav_sha256"),
            "audio_health_hash": health_hash,
            "audio_health_status": health_summary.get("status"),
            "audio_health_report_id": health_summary.get("report_id"),
            "duration_seconds": health_summary.get("duration_seconds"),
            "renderer_profile_id": artifact_summary.get("renderer_profile_id"),
            "renderer_profile_hash": artifact_summary.get("renderer_profile_hash"),
            "soundfont_sha256": artifact_summary.get("soundfont_sha256"),
            "source_hash": artifact_summary.get("source_hash"),
            "artifact_integrity_hash": artifact_summary.get("integrity_hash"),
            "artifact_current": not artifact_stale,
        }
        return {
            "release": release.to_dict(),
            "track": track.to_dict(),
            "export_dir": export_dir,
            "song_plan": _as_document(song_plan),
            "audio_evidence": audio_evidence,
            "health_report": health_report,
            "artifact": artifact,
        }

    def _build_review(self, release_id: str, review_id: str, payload: ImplementationDocument, *, now: str, created_at: str | None = None) -> ImplementationDocument:
        track_id = str(payload.get("track_id") or "").strip()
        if not track_id:
            raise AudioReviewEvidenceError("track_id is required.")
        context = self.track_audio_context(release_id, track_id, require_reviewable=True)
        track = context["track"]
        reviewer = _as_document(payload.get("reviewer"))
        status = str(payload.get("status") or "accepted").strip()
        if status not in REVIEW_STATUSES:
            raise AudioReviewEvidenceError(f"status must be one of: {', '.join(sorted(REVIEW_STATUSES))}.")
        review_mode = str(payload.get("review_mode") or "manual").strip()
        if review_mode not in REVIEW_MODES:
            raise AudioReviewEvidenceError(f"review_mode must be one of: {', '.join(sorted(REVIEW_MODES))}.")
        rating = max(0, min(5, int(payload.get("rating") or 0)))
        markers = self._normalize_markers(payload.get("markers"), context=context)
        review = {
            "schema_version": AUDIO_REVIEW_SCHEMA_VERSION,
            "review_id": review_id,
            "release_id": release_id,
            "track_id": track_id,
            "project_id": track.get("project_id"),
            "version_id": track.get("version_id"),
            "status": status,
            "review_mode": review_mode,
            "reviewer": {
                "name": sanitize_sensitive_text(str(reviewer.get("name") or payload.get("reviewer_name") or "reviewer"))[:120],
                "role": sanitize_sensitive_text(str(reviewer.get("role") or ""))[:80],
            },
            "rating": rating,
            "listened_at": str(payload.get("listened_at") or now),
            "playback_confirmed": bool(payload.get("playback_confirmed", False)),
            "audio_evidence": context["audio_evidence"],
            "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:4000],
            "tags": [sanitize_sensitive_text(str(item))[:80] for item in payload.get("tags", []) if str(item).strip()][:24] if isinstance(payload.get("tags"), list) else [],
            "markers": markers,
            "imported_from": sanitize_metadata(payload.get("imported_from"), blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}) if isinstance(payload.get("imported_from"), dict) else {},
            "redaction_findings": _payload_redaction_findings(payload),
            "source_hash": audio_review_source_hash(release_id=release_id, track=track, audio_evidence=context["audio_evidence"], song_plan=context["song_plan"]),
            "created_at": created_at or now,
            "updated_at": now,
        }
        review["integrity_hash"] = audio_review_integrity_hash(review)
        review["current_source_hash"] = review["source_hash"]
        review["stale"] = False
        review["current"] = True
        review["stale_reasons"] = []
        return sanitize_metadata(review, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def _normalize_markers(self, value: Any, *, context: ImplementationDocument) -> list[ImplementationDocument]:
        markers = _as_list(value)
        result: list[dict[str, Any]] = []
        duration = float((context.get("audio_evidence") or {}).get("duration_seconds") or 0.0)
        for index, item in enumerate(markers, start=1):
            if not isinstance(item, dict):
                continue
            seconds = float(item.get("time_seconds") or 0.0)
            if seconds < 0:
                raise AudioReviewEvidenceError("marker time_seconds cannot be negative.")
            if duration > 0 and seconds > duration + 1.0:
                raise AudioReviewEvidenceError("marker time_seconds exceeds WAV duration.")
            category = str(item.get("category") or "other").strip()
            if category not in MARKER_CATEGORIES:
                category = "other"
            severity = str(item.get("severity") or "medium").strip()
            if severity not in MARKER_SEVERITIES:
                severity = "medium"
            marker_id = str(item.get("marker_id") or f"m-{index:06d}")
            result.append(
                {
                    "marker_id": _validate_marker_id(marker_id),
                    "time_seconds": round(seconds, 3),
                    "severity": severity,
                    "category": category,
                    "message": sanitize_sensitive_text(str(item.get("message") or ""))[:800],
                    "mapped": map_marker_to_song_plan(seconds, _as_document(context.get("song_plan"))),
                    "review_task_id": str(item.get("review_task_id") or "") or None,
                    "mix_patch_id": str(item.get("mix_patch_id") or "") or None,
                }
            )
        return result

    def _write_review_with_markers(self, release_id: str, review: ImplementationDocument, markers: list[ImplementationDocument], *, now: str) -> ImplementationDocument:
        updated = {key: value for key, value in review.items() if key not in {"integrity_hash", "stale", "stale_reasons", "current", "current_source_hash"}}
        updated["markers"] = markers
        updated["updated_at"] = now
        updated["integrity_hash"] = audio_review_integrity_hash(updated)
        write_json(self.review_path(release_id, str(review.get("review_id") or "")), sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        return updated

    def _reserve_review_id(self, release_id: str) -> str:
        root = self.reviews_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            review_id = f"arv-{index:06d}"
            path = root / f"{review_id}.json"
            if not path.exists():
                return review_id
        raise AudioReviewEvidenceError("Unable to allocate audio review id.")

    def _ensure_release_mutable(self, release_id: str) -> None:
        document = self.release_store.get_release(release_id)
        if document.status == "archived":
            raise AudioReviewEvidenceStateError("Archived releases are read-only.")
        if document.status == "signed" or self.release_store.read_signoff(release_id, default={}):
            raise AudioReviewEvidenceStateError("Signed releases cannot change audio reviews. Reset signoff first.")

    def _append_event(self, release_id: str, event_type: str, payload: ImplementationDocument, now: str) -> None:
        root = self.reviews_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=BLOCKED_RELEASE_KEYS)
        with (root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)


def audio_review_source_hash(*, release_id: str, track: dict[str, Any], audio_evidence: dict[str, Any], song_plan: dict[str, Any]) -> str:
    return stable_hash(
        {
            "release_id": release_id,
            "track": {
                "track_id": track.get("track_id"),
                "project_id": track.get("project_id"),
                "version_id": track.get("version_id"),
                "disc_number": track.get("disc_number"),
                "track_number": track.get("track_number"),
            },
            "audio_evidence": {
                "audio_artifact_id": audio_evidence.get("audio_artifact_id"),
                "wav_sha256": audio_evidence.get("wav_sha256"),
                "audio_health_status": audio_evidence.get("audio_health_status"),
                "renderer_profile_id": audio_evidence.get("renderer_profile_id"),
                "renderer_profile_hash": audio_evidence.get("renderer_profile_hash"),
                "source_hash": audio_evidence.get("source_hash"),
                "artifact_integrity_hash": audio_evidence.get("artifact_integrity_hash"),
            },
            "song_plan": _song_plan_identity(song_plan),
        }
    )


def audio_health_content_hash(report: dict[str, Any]) -> str:
    return stable_hash(
        {
            "status": report.get("status"),
            "wav_sha256": report.get("wav_sha256"),
            "format": _as_document(report.get("format")),
            "metrics": _as_document(report.get("metrics")),
            "checks": _as_list(report.get("checks")),
            "warnings": _as_list(report.get("warnings")),
            "failures": _as_list(report.get("failures")),
        }
    )


def audio_review_integrity_hash(review: dict[str, Any]) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in review.items() if key not in _INTEGRITY_EXCLUDE_KEYS}, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))


def review_integrity_ok(review: dict[str, Any]) -> bool:
    expected = str(review.get("integrity_hash") or "")
    return bool(expected) and expected == audio_review_integrity_hash(review)


def review_payload_hash(review: dict[str, Any]) -> str:
    return audio_review_integrity_hash(review)


def audio_review_summary_source_hash(release: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
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
            "reviews": [
                {
                    "review_id": review.get("review_id"),
                    "track_id": review.get("track_id"),
                    "status": review.get("status"),
                    "review_mode": review.get("review_mode"),
                    "playback_confirmed": review.get("playback_confirmed"),
                    "source_hash": review.get("source_hash"),
                    "integrity_hash": review.get("integrity_hash"),
                    "stale": bool(review.get("stale", False)),
                    "redaction_issue_count": len(_review_redaction_findings(review)),
                }
                for review in sorted(reviews, key=lambda item: str(item.get("review_id") or ""))
            ],
        }
    )


def audio_review_summary_hash(summary: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in summary.items() if key not in _SUMMARY_INTEGRITY_EXCLUDE_KEYS})


def audio_review_summary_integrity_ok(summary: dict[str, Any]) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == audio_review_summary_hash(summary)


def audio_review_summary_allows_signoff(summary: dict[str, Any]) -> bool:
    return bool(summary) and audio_review_summary_integrity_ok(summary) and summary.get("status") == "passed" and not summary.get("missing_track_ids") and int(summary.get("manual_accepted_track_count") or 0) == int(summary.get("track_count") or -1)


def audio_review_summary_public(summary: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(summary)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_id": data.get("release_id"),
            "track_count": data.get("track_count", 0),
            "covered_track_count": data.get("covered_track_count", 0),
            "manual_accepted_track_count": data.get("manual_accepted_track_count", 0),
            "synthetic_only_track_count": data.get("synthetic_only_track_count", 0),
            "needs_fix_track_count": data.get("needs_fix_track_count", 0),
            "rejected_track_count": data.get("rejected_track_count", 0),
            "stale_review_count": data.get("stale_review_count", 0),
            "tampered_review_count": data.get("tampered_review_count", 0),
            "duplicate_manual_review_count": data.get("duplicate_manual_review_count", 0),
            "redaction_issue_count": data.get("redaction_issue_count", 0),
            "missing_track_ids": data.get("missing_track_ids", []),
            "blocking_track_ids": data.get("blocking_track_ids", []),
            "source_hash": data.get("source_hash"),
            "integrity_hash": data.get("integrity_hash"),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS - {"path"},
    )


def review_public_summary(review: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "review_id": review.get("review_id"),
            "track_id": review.get("track_id"),
            "project_id": review.get("project_id"),
            "version_id": review.get("version_id"),
            "status": review.get("status"),
            "review_mode": review.get("review_mode"),
            "rating": review.get("rating"),
            "playback_confirmed": bool(review.get("playback_confirmed", False)),
            "marker_count": len(review.get("markers", [])) if isinstance(review.get("markers"), list) else 0,
            "current": not bool(review.get("stale", False)),
            "stale": bool(review.get("stale", False)),
            "stale_reasons": review.get("stale_reasons", []),
            "integrity_ok": review_integrity_ok(review),
            "audio_evidence": _as_document(review.get("audio_evidence")),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS - {"path"},
    )


def export_audio_reviews(release_store: ReleaseStore, release_id: str, export_dir: Path, *, project_store: ProjectStore | None = None, now: str | None = None) -> dict[str, Any]:
    store = AudioReviewEvidenceStore(release_store, project_store=project_store)
    summary = store.build_summary(release_id, now=now)
    target_root = export_dir / "audio-reviews"
    reviews_dir = target_root / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    write_json(target_root / "summary.json", summary)
    exported: list[dict[str, Any]] = []
    for review in sorted(store.list_reviews(release_id), key=lambda item: (str(item.get("track_id") or ""), str(item.get("review_id") or ""))):
        filename = f"{review.get('track_id')}-{review.get('review_id')}.json"
        write_json(reviews_dir / filename, review)
        exported.append({"track_id": review.get("track_id"), "review_id": review.get("review_id"), "path": f"audio-reviews/reviews/{filename}", "payload_hash": review_payload_hash(review)})
    return {
        **audio_review_summary_public(summary),
        "summary_hash": audio_review_summary_hash(summary),
        "summary_path": "audio-reviews/summary.json",
        "review_hashes": exported,
        "review_count": len(exported),
    }


def read_release_audio_review_summary(release_store: ReleaseStore, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    return AudioReviewEvidenceStore(release_store).read_summary(release_id, default=default)


def write_release_audio_review_summary(release_store: ReleaseStore, release_id: str, *, project_store: ProjectStore | None = None, now: str | None = None) -> dict[str, Any]:
    return AudioReviewEvidenceStore(release_store, project_store=project_store).write_summary(release_id, now=now)


def map_marker_to_song_plan(time_seconds: float, song_plan: dict[str, Any]) -> dict[str, Any]:
    bpm = _tempo(song_plan)
    if bpm <= 0:
        return {"status": "no_bpm"}
    beat = round(float(time_seconds) * bpm / 60.0, 3)
    sections = _section_ranges(song_plan)
    for section in sections:
        start = float(section.get("start_beat") or 0.0)
        duration = float(section.get("duration_beats") or 0.0)
        if duration > 0 and start <= beat < start + duration:
            return {
                "status": "mapped",
                "beat": beat,
                "section_id": section.get("section_id"),
                "section_role": section.get("role") or section.get("name") or section.get("section_role"),
                "local_beat": round(beat - start, 3),
            }
    return {"status": "unmapped", "beat": beat}


def release_audio_review_gate(release_store: ReleaseStore, project_store: ProjectStore, release_id: str, *, now: str | None = None) -> dict[str, Any]:
    store = AudioReviewEvidenceStore(release_store, project_store=project_store)
    summary = store.build_summary(release_id, now=now)
    public = audio_review_summary_public(summary)
    if not audio_review_summary_allows_signoff(summary):
        return {**public, "status": "failed", "hard_block": True, "message": "Per-track audio review gate failed."}
    return {**public, "status": "passed", "message": "Per-track audio review gate passed."}


def _current_audio_qa_track(release_store: ReleaseStore, project_store: ProjectStore, release: Any, release_id: str, track_id: str) -> ImplementationDocument:
    try:
        report = read_release_audio_qa(release_store, release_id, default={})
        current_hash = release_audio_source_hash(release, project_store=project_store, release_store=release_store)
        if not report or report.get("source_hash") != current_hash or not release_audio_report_integrity_ok(report):
            return {}
        for item in report.get("tracks", []) if isinstance(report.get("tracks"), list) else []:
            if isinstance(item, dict) and item.get("track_id") == track_id:
                return item
    except Exception:
        return {}
    return {}


def _song_plan_identity(song_plan: ImplementationDocument) -> ImplementationDocument:
    return {
        "payload_hash": stable_hash(_as_document(song_plan)),
        "tempo_bpm": _tempo(song_plan),
        "duration_seconds": song_plan.get("duration_seconds") if isinstance(song_plan, dict) else None,
        "sections": _section_ranges(song_plan),
    }


def _tempo(song_plan: ImplementationDocument) -> float:
    if not isinstance(song_plan, dict):
        return 0.0
    for key in ("tempo_bpm", "bpm", "tempo"):
        value = song_plan.get(key)
        if isinstance(value, (int, float, str)) and str(value).strip():
            try:
                return float(value)
            except ValueError:
                pass
    request = _as_document(song_plan.get("request"))
    value = request.get("tempo_bpm")
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _section_ranges(song_plan: ImplementationDocument) -> list[ImplementationDocument]:
    sections = _as_list(song_plan.get("sections"))
    result: list[dict[str, Any]] = []
    cursor = 0.0
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        duration = _float(section.get("duration_beats") or section.get("bars") or 0.0)
        if "bars" in section and not section.get("duration_beats"):
            duration *= 4.0
        start = _float(section.get("start_beat")) if section.get("start_beat") is not None else cursor
        result.append(
            {
                "section_id": str(section.get("section_id") or section.get("id") or f"section-{index:03d}"),
                "role": str(section.get("role") or section.get("name") or section.get("section_role") or ""),
                "start_beat": round(start, 3),
                "duration_beats": round(duration, 3),
            }
        )
        cursor = start + max(0.0, duration)
    return result


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _artifact_stale_reasons(artifact: ImplementationDocument, *, wav_path: Path, midi_path: Path, song_plan_path: Path, project_store: ProjectStore) -> list[str]:
    renderer = _as_document(artifact.get("renderer"))
    profile_id = str(renderer.get("profile_id") or "")
    profile = None
    if profile_id.startswith("arp-"):
        try:
            profile = AudioProfileStore(project_store.root.parent / "audio-profiles").get_profile(profile_id)
        except Exception:
            profile = None
    return audio_artifact_stale_reasons_for_profile(artifact, wav_path=wav_path, midi_path=midi_path, song_plan_path=song_plan_path, profile=profile)


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = __import__("hashlib").sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_redaction_findings(payload: ImplementationDocument) -> list[ImplementationDocument]:
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

    walk({key: payload.get(key) for key in ("reviewer", "notes", "tags", "markers", "imported_from")}, "")
    return sanitize_metadata(findings, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})


def _review_redaction_findings(review: ImplementationDocument) -> list[ImplementationDocument]:
    findings = list(review.get("redaction_findings") or []) if isinstance(review.get("redaction_findings"), list) else []
    for field in ("reviewer", "notes", "tags", "markers", "imported_from"):
        value = review.get(field)
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
        for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append({"field": field, "kind": "sensitive_value", "message": f"{field} contains sensitive value pattern: {replacement}."})
    return sanitize_metadata(findings, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})


def _markers_from_human_review(review: ImplementationDocument) -> list[ImplementationDocument]:
    source = _as_list(review.get("markers"))
    result: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        seconds_value = item.get("time_seconds")
        if seconds_value is None:
            continue
        result.append(
            {
                "time_seconds": seconds_value,
                "category": item.get("category") or item.get("label") or "other",
                "severity": item.get("severity") or "medium",
                "message": item.get("message") or item.get("note") or "",
            }
        )
    return result


def _matching_open_marker_task(project_dir: Path, release_id: str, review_id: str, marker_id: str) -> ReviewTask | None:
    store = ReviewTaskStore(project_dir)
    for task in store.list_tasks(include_archived=False):
        source = _as_document(task.source)
        if (
            source.get("source_type") == "release_audio_review_marker"
            and source.get("release_id") == release_id
            and source.get("review_id") == review_id
            and source.get("marker_id") == marker_id
            and task.status in {"open", "candidate_ready", "needs_more_work"}
        ):
            return task
    return None


def _marker_task_title(marker: ImplementationDocument, review: ImplementationDocument) -> str:
    mapped = _as_document(marker.get("mapped"))
    section = mapped.get("section_role") or mapped.get("section_id") or f"{marker.get('time_seconds')}s"
    return f"Fix audio review marker: {marker.get('category') or 'issue'} at {section}"


def _marker_task_instruction(marker: ImplementationDocument) -> str:
    category = str(marker.get("category") or "other")
    message = str(marker.get("message") or "").strip()
    mapped = _as_document(marker.get("mapped"))
    section = mapped.get("section_role") or mapped.get("section_id") or "the marked section"
    base = {
        "mix_balance": "Adjust arrangement density, velocities, or register balance around the marked section.",
        "melody": "Revise the melody around the marked section.",
        "harmony": "Review chord movement around the marked section.",
        "rhythm": "Adjust rhythm pattern or density around the marked section.",
        "arrangement": "Refine arrangement around the marked section.",
        "sound_quality": "Review audio quality around the marked section.",
        "structure": "Review structure around the marked section.",
        "hook": "Strengthen the hook around the marked section.",
    }.get(category, "Review the marked audio issue.")
    return sanitize_sensitive_text(f"{base} Section: {section}. Marker note: {message}")[:800]


def _priority(value: Any, severity: Any) -> int:
    text = str(value or "").lower()
    if text in {"critical", "high"}:
        return 90
    if text == "medium":
        return 72
    if text == "low":
        return 55
    severity_text = str(severity or "").lower()
    return {"critical": 94, "high": 86, "medium": 72, "low": 55}.get(severity_text, 70)


def _validate_review_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("arv-") or not text[4:].isdigit():
        raise AudioReviewEvidenceError("Invalid audio review id.")
    return text


def _validate_marker_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("m-") or not text[2:].isdigit():
        raise AudioReviewEvidenceError("Invalid marker id.")
    return text


def _append_task_event(task_dir: Path, event: str, payload: ImplementationDocument, now: str) -> None:
    path = task_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = sanitize_metadata({"timestamp": now, "event": event, "payload": payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(data, ensure_ascii=False) + "\n")
