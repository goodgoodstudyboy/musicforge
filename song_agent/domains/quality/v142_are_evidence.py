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
_artifact_stale_reasons = _make_deferred_global('_artifact_stale_reasons')
_current_audio_qa_track = _make_deferred_global('_current_audio_qa_track')
_payload_redaction_findings = _make_deferred_global('_payload_redaction_findings')
_sha256 = _make_deferred_global('_sha256')
_validate_marker_id = _make_deferred_global('_validate_marker_id')
audio_health_content_hash = _make_deferred_global('audio_health_content_hash')
audio_review_integrity_hash = _make_deferred_global('audio_review_integrity_hash')
audio_review_source_hash = _make_deferred_global('audio_review_source_hash')
key = _make_deferred_global('key')
map_marker_to_song_plan = _make_deferred_global('map_marker_to_song_plan')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioReviewEvidenceError, AudioReviewEvidenceNotFoundError, AudioReviewEvidenceStateError, _artifact_stale_reasons, _current_audio_qa_track, _payload_redaction_findings, _sha256
    global _validate_marker_id, audio_health_content_hash, audio_review_integrity_hash, audio_review_source_hash, key, map_marker_to_song_plan
    AudioReviewEvidenceError = namespace.get('AudioReviewEvidenceError', AudioReviewEvidenceError)
    AudioReviewEvidenceNotFoundError = namespace.get('AudioReviewEvidenceNotFoundError', AudioReviewEvidenceNotFoundError)
    AudioReviewEvidenceStateError = namespace.get('AudioReviewEvidenceStateError', AudioReviewEvidenceStateError)
    _artifact_stale_reasons = namespace.get('_artifact_stale_reasons', _artifact_stale_reasons)
    _current_audio_qa_track = namespace.get('_current_audio_qa_track', _current_audio_qa_track)
    _payload_redaction_findings = namespace.get('_payload_redaction_findings', _payload_redaction_findings)
    _sha256 = namespace.get('_sha256', _sha256)
    _validate_marker_id = namespace.get('_validate_marker_id', _validate_marker_id)
    audio_health_content_hash = namespace.get('audio_health_content_hash', audio_health_content_hash)
    audio_review_integrity_hash = namespace.get('audio_review_integrity_hash', audio_review_integrity_hash)
    audio_review_source_hash = namespace.get('audio_review_source_hash', audio_review_source_hash)
    key = namespace.get('key', key)
    map_marker_to_song_plan = namespace.get('map_marker_to_song_plan', map_marker_to_song_plan)
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




class AudioReviewEvidenceStoreEvidenceMixin:
    def track_audio_context(self, release_id: str, track_id: str, *, require_reviewable: bool = True) -> DomainDocument:
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

    def _build_review(self, release_id: str, review_id: str, payload: DomainDocument, *, now: str, created_at: str | None = None) -> DomainDocument:
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

    def _normalize_markers(self, value: object, *, context: DomainDocument) -> list[DomainDocument]:
        markers = _as_list(value)
        result: list[DomainDocument] = []
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

    def _write_review_with_markers(self, release_id: str, review: DomainDocument, markers: list[DomainDocument], *, now: str) -> DomainDocument:
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

    def _append_event(self, release_id: str, event_type: str, payload: DomainDocument, now: str) -> None:
        root = self.reviews_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=BLOCKED_RELEASE_KEYS)
        with (root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)
