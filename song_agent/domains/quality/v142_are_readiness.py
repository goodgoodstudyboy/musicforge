# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import os as os
import threading as threading
from pathlib import Path as Path
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

AudioReviewEvidenceError = _make_deferred_global('AudioReviewEvidenceError')
AudioReviewEvidenceNotFoundError = _make_deferred_global('AudioReviewEvidenceNotFoundError')
AudioReviewEvidenceStateError = _make_deferred_global('AudioReviewEvidenceStateError')
_append_task_event = _make_deferred_global('_append_task_event')
_marker_task_instruction = _make_deferred_global('_marker_task_instruction')
_marker_task_title = _make_deferred_global('_marker_task_title')
_markers_from_human_review = _make_deferred_global('_markers_from_human_review')
_matching_open_marker_task = _make_deferred_global('_matching_open_marker_task')
_priority = _make_deferred_global('_priority')
_review_redaction_findings = _make_deferred_global('_review_redaction_findings')
_validate_review_id = _make_deferred_global('_validate_review_id')
audio_review_source_hash = _make_deferred_global('audio_review_source_hash')
audio_review_summary_hash = _make_deferred_global('audio_review_summary_hash')
audio_review_summary_public = _make_deferred_global('audio_review_summary_public')
audio_review_summary_source_hash = _make_deferred_global('audio_review_summary_source_hash')
item = _make_deferred_global('item')
reason = _make_deferred_global('reason')
review_integrity_ok = _make_deferred_global('review_integrity_ok')
review_payload_hash = _make_deferred_global('review_payload_hash')
review_public_summary = _make_deferred_global('review_public_summary')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioReviewEvidenceError, AudioReviewEvidenceNotFoundError, AudioReviewEvidenceStateError, _append_task_event, _marker_task_instruction, _marker_task_title, _markers_from_human_review
    global _matching_open_marker_task, _priority, _review_redaction_findings, _validate_review_id, audio_review_source_hash, audio_review_summary_hash, audio_review_summary_public, audio_review_summary_source_hash
    global item, reason, review_integrity_ok, review_payload_hash, review_public_summary
    AudioReviewEvidenceError = namespace.get('AudioReviewEvidenceError', AudioReviewEvidenceError)
    AudioReviewEvidenceNotFoundError = namespace.get('AudioReviewEvidenceNotFoundError', AudioReviewEvidenceNotFoundError)
    AudioReviewEvidenceStateError = namespace.get('AudioReviewEvidenceStateError', AudioReviewEvidenceStateError)
    _append_task_event = namespace.get('_append_task_event', _append_task_event)
    _marker_task_instruction = namespace.get('_marker_task_instruction', _marker_task_instruction)
    _marker_task_title = namespace.get('_marker_task_title', _marker_task_title)
    _markers_from_human_review = namespace.get('_markers_from_human_review', _markers_from_human_review)
    _matching_open_marker_task = namespace.get('_matching_open_marker_task', _matching_open_marker_task)
    _priority = namespace.get('_priority', _priority)
    _review_redaction_findings = namespace.get('_review_redaction_findings', _review_redaction_findings)
    _validate_review_id = namespace.get('_validate_review_id', _validate_review_id)
    audio_review_source_hash = namespace.get('audio_review_source_hash', audio_review_source_hash)
    audio_review_summary_hash = namespace.get('audio_review_summary_hash', audio_review_summary_hash)
    audio_review_summary_public = namespace.get('audio_review_summary_public', audio_review_summary_public)
    audio_review_summary_source_hash = namespace.get('audio_review_summary_source_hash', audio_review_summary_source_hash)
    item = namespace.get('item', item)
    reason = namespace.get('reason', reason)
    review_integrity_ok = namespace.get('review_integrity_ok', review_integrity_ok)
    review_payload_hash = namespace.get('review_payload_hash', review_payload_hash)
    review_public_summary = namespace.get('review_public_summary', review_public_summary)
    _bind_deferred_defaults(namespace)


AUDIO_REVIEW_SCHEMA_VERSION = 1
AUDIO_REVIEW_SUMMARY_SCHEMA_VERSION = 1
REVIEW_STATUSES = {"accepted", "needs_fix", "rejected", "waived"}
REVIEW_MODES = {"manual", "synthetic"}
MARKER_CATEGORIES = {"arrangement", "melody", "harmony", "rhythm", "mix_balance", "sound_quality", "structure", "hook", "other"}
MARKER_SEVERITIES = {"low", "medium", "high", "critical"}
_SUMMARY_FILENAME = "release-audio-review-summary.json"
_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
_SUMMARY_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "generated_at"}




class AudioReviewEvidenceStoreReadinessMixin:
    def reviews_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-reviews"

    def summary_path(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / _SUMMARY_FILENAME

    def review_path(self, release_id: str, review_id: str) -> Path:
        return self.reviews_dir(release_id) / f"{_validate_review_id(review_id)}.json"

    def list_reviews(self, release_id: str, *, include_deleted: bool = False) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        root = self.reviews_dir(release_id)
        if not root.exists():
            return []
        reviews: list[DomainDocument] = []
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

    def read_review(self, release_id: str, review_id: str) -> DomainDocument:
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise AudioReviewEvidenceNotFoundError(review_id)
        return self.with_current_state(read_json(path))

    def create_review(self, release_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        with self.lock:
            review_id = self._reserve_review_id(release_id)
            review = self._build_review(release_id, review_id, payload, now=now)
            write_json(self.review_path(release_id, review_id), review)
            self._append_event(release_id, "release_audio_review_created", {"review_id": review_id, "track_id": review.get("track_id")}, now)
            return self.with_current_state(review)

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
            "notes": payload.get("notes", existing.get("notes")),
            "tags": payload.get("tags", existing.get("tags")),
            "markers": payload.get("markers", existing.get("markers")),
            "updated_at": now,
        }
        rebuilt = self._build_review(release_id, review_id, merged, now=now, created_at=str(existing.get("created_at") or now))
        write_json(self.review_path(release_id, review_id), rebuilt)
        self._append_event(release_id, "release_audio_review_updated", {"review_id": review_id, "track_id": rebuilt.get("track_id")}, now)
        return self.with_current_state(rebuilt)

    def delete_review(self, release_id: str, review_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        path = self.review_path(release_id, review_id)
        if not path.exists():
            raise AudioReviewEvidenceNotFoundError(review_id)
        path.unlink()
        self._append_event(release_id, "release_audio_review_deleted", {"review_id": review_id}, now)
        return {"review_id": review_id, "deleted": True}

    def refresh_review(self, release_id: str, review_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        existing = self.read_review(release_id, review_id)
        rebuilt = self._build_review(release_id, review_id, existing, now=now, created_at=str(existing.get("created_at") or now))
        write_json(self.review_path(release_id, review_id), rebuilt)
        self._append_event(release_id, "release_audio_review_refreshed", {"review_id": review_id, "track_id": rebuilt.get("track_id")}, now)
        return self.with_current_state(rebuilt)

    def build_summary(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        release = self.release_store.get_release(release_id)
        reviews = self.list_reviews(release_id)
        by_track: dict[str, list[DomainDocument]] = {}
        for review in reviews:
            by_track.setdefault(str(review.get("track_id") or ""), []).append(review)
        track_summaries: list[DomainDocument] = []
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

    def write_summary(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        summary = self.build_summary(release_id, now=now)
        write_json(self.summary_path(release_id), summary)
        self._append_event(release_id, "release_audio_review_summary_refreshed", {"status": summary.get("status")}, now or now_iso())
        return summary

    def read_summary(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.summary_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioReviewEvidenceNotFoundError("Release audio review summary does not exist.")
        data = read_json(path)
        return sanitize_metadata(_as_document(data), blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def create_review_task_from_marker(self, release_id: str, review_id: str, marker_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def import_human_review_pack(self, release_id: str, payload: DomainDocument, *, acceptance_store: object, now: str | None = None) -> DomainDocument:
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
        imported: list[DomainDocument] = []
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

    def with_current_state(self, review: DomainDocument) -> DomainDocument:
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
