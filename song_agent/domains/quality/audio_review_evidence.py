# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

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
from song_agent.domains.quality.v142_are_readiness import AudioReviewEvidenceStoreReadinessMixin
from song_agent.domains.quality import v142_are_readiness as _v142_are_readiness
from song_agent.domains.quality.v142_are_evidence import AudioReviewEvidenceStoreEvidenceMixin
from song_agent.domains.quality import v142_are_evidence as _v142_are_evidence



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


class AudioReviewEvidenceStore(AudioReviewEvidenceStoreReadinessMixin, AudioReviewEvidenceStoreEvidenceMixin):
    def __init__(self, release_store: ReleaseStore, project_store: ProjectStore | None = None) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.lock = threading.RLock()
























def audio_review_source_hash(*, release_id: str, track: DomainDocument, audio_evidence: DomainDocument, song_plan: DomainDocument) -> str:
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


def audio_health_content_hash(report: DomainDocument) -> str:
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


def audio_review_integrity_hash(review: DomainDocument) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in review.items() if key not in _INTEGRITY_EXCLUDE_KEYS}, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))


def review_integrity_ok(review: DomainDocument) -> bool:
    expected = str(review.get("integrity_hash") or "")
    return bool(expected) and expected == audio_review_integrity_hash(review)


def review_payload_hash(review: DomainDocument) -> str:
    return audio_review_integrity_hash(review)


def audio_review_summary_source_hash(release: DomainDocument, reviews: list[DomainDocument]) -> str:
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


def audio_review_summary_hash(summary: DomainDocument) -> str:
    return stable_hash({key: value for key, value in summary.items() if key not in _SUMMARY_INTEGRITY_EXCLUDE_KEYS})


def audio_review_summary_integrity_ok(summary: DomainDocument) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == audio_review_summary_hash(summary)


def audio_review_summary_allows_signoff(summary: DomainDocument) -> bool:
    return bool(summary) and audio_review_summary_integrity_ok(summary) and summary.get("status") == "passed" and not summary.get("missing_track_ids") and int(summary.get("manual_accepted_track_count") or 0) == int(summary.get("track_count") or -1)


def audio_review_summary_public(summary: DomainDocument | None) -> DomainDocument:
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


def review_public_summary(review: DomainDocument) -> DomainDocument:
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


def export_audio_reviews(release_store: ReleaseStore, release_id: str, export_dir: Path, *, project_store: ProjectStore | None = None, now: str | None = None) -> DomainDocument:
    store = AudioReviewEvidenceStore(release_store, project_store=project_store)
    summary = store.build_summary(release_id, now=now)
    target_root = export_dir / "audio-reviews"
    reviews_dir = target_root / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    write_json(target_root / "summary.json", summary)
    exported: list[ImplementationDocument] = []
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


def read_release_audio_review_summary(release_store: ReleaseStore, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
    return AudioReviewEvidenceStore(release_store).read_summary(release_id, default=default)


def write_release_audio_review_summary(release_store: ReleaseStore, release_id: str, *, project_store: ProjectStore | None = None, now: str | None = None) -> DomainDocument:
    return AudioReviewEvidenceStore(release_store, project_store=project_store).write_summary(release_id, now=now)


def map_marker_to_song_plan(time_seconds: float, song_plan: DomainDocument) -> DomainDocument:
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


def release_audio_review_gate(release_store: ReleaseStore, project_store: ProjectStore, release_id: str, *, now: str | None = None) -> DomainDocument:
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
    result: list[ImplementationDocument] = []
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
    result: list[ImplementationDocument] = []
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

_v142_are_readiness.bind_globals(globals())
_v142_are_evidence.bind_globals(globals())
