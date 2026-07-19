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

from song_agent.domains.quality.audio_artifacts import build_audio_artifact_manifest as build_audio_artifact_manifest, write_audio_artifact_manifest as write_audio_artifact_manifest
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_allows_release as audio_health_allows_release, audio_health_integrity_ok as audio_health_integrity_ok, audio_health_summary as audio_health_summary
from song_agent.domains.delivery.delivery_qa import build_delivery_qa_report as build_delivery_qa_report
from song_agent.domains.quality.audio_review_evidence import AudioReviewEvidenceStore as AudioReviewEvidenceStore, review_integrity_ok as review_integrity_ok, review_payload_hash as review_payload_hash
from song_agent.domains.creation.final_export import FinalExportOptions as FinalExportOptions, build_final_export_bundle as build_final_export_bundle, build_final_export_zip as build_final_export_zip, final_export_dir as final_export_dir
from song_agent.domains.quality.mix_controls import MixControlError as MixControlError, MixControlStateError as MixControlStateError, MixControlStore as MixControlStore, MixPatch as MixPatch, apply_patch_and_render_plan as apply_patch_and_render_plan, build_mix_patch as build_mix_patch, default_mix_state as default_mix_state, file_sha256 as file_sha256, marker_to_mix_patch_operations as marker_to_mix_patch_operations, mix_patch_hash as mix_patch_hash, mix_patch_integrity_ok as mix_patch_integrity_ok, mix_state_hash as mix_state_hash, mix_state_integrity_ok as mix_state_integrity_ok, mix_state_stale_reasons as mix_state_stale_reasons, song_plan_hash as song_plan_hash, stable_hash as stable_hash
from song_agent.domains.quality.mix_render import _job_state as _job_state, _project_version_context as _project_version_context, _run_summary as _run_summary, _validator_report as _validator_report
from song_agent.domains.studio.projectio import ProjectPaths as ProjectPaths, append_event as append_event, read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_quality import evaluate_quality_gate as evaluate_quality_gate, load_quality_gate_config as load_quality_gate_config
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio import build_release_audio_qa_report as build_release_audio_qa_report, write_release_audio_qa as write_release_audio_qa
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseNotFoundError as ReleaseNotFoundError, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, build_release_track_snapshot as build_release_track_snapshot
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, load_renderer_config as load_renderer_config, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stem_health import build_stem_health_report as build_stem_health_report, stem_health_summary as stem_health_summary, write_stem_health_report as write_stem_health_report
from song_agent.domains.quality.v142_ar_readiness import AudioRevisionStoreReadinessMixin
from song_agent.domains.quality import v142_ar_readiness as _v142_ar_readiness
from song_agent.domains.quality.v142_ar_evidence import AudioRevisionStoreEvidenceMixin
from song_agent.domains.quality import v142_ar_evidence as _v142_ar_evidence
from song_agent.domains.quality.v142_ar_lifecycle import AudioRevisionStoreLifecycleMixin
from song_agent.domains.quality import v142_ar_lifecycle as _v142_ar_lifecycle



AUDIO_REVISION_SCHEMA_VERSION = 1
AUDIO_REVISION_STATUSES = {"open", "candidate_generation", "reviewing_candidates", "partially_applied", "closed", "archived"}
ISSUE_STATUSES = {"open", "candidates_ready", "candidate_selected", "applied", "needs_recheck", "rechecked", "waived", "stale"}
CANDIDATE_STATUSES = {"draft", "rendered", "ready_for_review", "reviewed", "selected", "applied", "rejected", "stale"}
REVISION_CATEGORIES = {"mix_balance", "sound_quality", "arrangement"}
REVISION_SEVERITIES = {"low": 1, "medium": 2, "high": 3, "critical": 4}
SESSION_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash"}
ISSUE_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash"}
CANDIDATE_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash"}
CLOSEOUT_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}


class AudioRevisionError(ValueError):
    pass


class AudioRevisionNotFoundError(AudioRevisionError):
    pass


class AudioRevisionStateError(AudioRevisionError):
    pass


class AudioRevisionStore(AudioRevisionStoreReadinessMixin, AudioRevisionStoreEvidenceMixin, AudioRevisionStoreLifecycleMixin):
    def __init__(self, release_store: ReleaseStore, project_store: ProjectStore | None = None, job_store: Any | None = None, audio_review_store: AudioReviewEvidenceStore | None = None) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.job_store = job_store
        self.audio_review_store = audio_review_store or AudioReviewEvidenceStore(release_store, project_store=self.project_store)
        self.lock = threading.RLock()






















































def build_audio_revision_summary(store: AudioRevisionStore, release_id: str, *, now: str | None = None) -> DomainDocument:
    now = now or now_iso()
    sessions = store.list_sessions(release_id, include_archived=False)
    source_marker_count = _revision_marker_count(store, release_id)
    blockers: list[str] = []
    warnings: list[str] = []
    session_rows = []
    latest_session_id = sessions[0].get("session_id") if sessions else None
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        closeout = store.read_closeout(release_id, session_id, default={})
        issues = store.list_issues(release_id, session_id)
        candidates = store.list_candidates(release_id, session_id)
        closeout_ok = bool(closeout) and closeout_integrity_ok(closeout) and closeout.get("status") in {"passed", "warning", "force_closed"}
        if session.get("stale") or not session_integrity_ok(session):
            blockers.append(f"{session_id}: session_stale_or_tampered")
        if not closeout_ok and session.get("status") != "archived":
            blockers.append(f"{session_id}: closeout_missing_or_failed")
        for issue in issues:
            if issue.get("status") in {"open", "candidates_ready", "candidate_selected", "applied", "needs_recheck"} and _severity_rank(issue.get("severity")) >= _severity_rank("high"):
                blockers.append(f"{issue.get('issue_id')}: high_issue_unresolved")
        session_rows.append(
            {
                "session_id": session_id,
                "status": session.get("status"),
                "stale": bool(session.get("stale")),
                "issue_count": len(issues),
                "open_issue_count": len([issue for issue in issues if issue.get("status") in {"open", "candidates_ready", "candidate_selected", "applied", "needs_recheck"}]),
                "applied_candidate_count": len([candidate for candidate in candidates if candidate.get("applied_version_id")]),
                "rechecked_issue_count": len([issue for issue in issues if issue.get("status") == "rechecked"]),
                "closeout_status": closeout.get("status") if closeout else "missing",
                "closeout_hash": closeout.get("integrity_hash") if closeout else None,
            }
        )
    active_markers = _active_revision_markers(store.audio_review_store, release_id)
    active_marker_ids = {str(item.get("marker_key") or "") for item in active_markers if str(item.get("marker_key") or "")}
    covered_marker_ids: set[str] = set()
    for session in sessions:
        covered_marker_ids.update(_covered_marker_ids(store._list_raw_issues(release_id, str(session.get("session_id") or ""))))
    uncovered_marker_ids = sorted(active_marker_ids - covered_marker_ids)
    if uncovered_marker_ids:
        blockers.append("active_markers_uncovered")
    status = "failed" if blockers else "warning" if warnings else "passed" if sessions else "missing"
    summary = {
        "schema_version": AUDIO_REVISION_SCHEMA_VERSION,
        "release_id": release_id,
        "status": status,
        "generated_at": now,
        "session_count": len(sessions),
        "source_marker_count": source_marker_count,
        "active_marker_count": len(active_markers),
        "covered_active_marker_count": len(active_marker_ids) - len(uncovered_marker_ids),
        "uncovered_marker_ids": uncovered_marker_ids,
        "active_marker_hash": stable_hash(active_markers),
        "latest_session_id": latest_session_id,
        "open_issue_count": sum(int(item.get("open_issue_count") or 0) for item in session_rows),
        "applied_candidate_count": sum(int(item.get("applied_candidate_count") or 0) for item in session_rows),
        "rechecked_issue_count": sum(int(item.get("rechecked_issue_count") or 0) for item in session_rows),
        "sessions": session_rows,
        "blockers": blockers,
        "warnings": warnings,
    }
    summary["integrity_hash"] = _object_hash(summary, SUMMARY_INTEGRITY_EXCLUDE)
    return sanitize_metadata(summary, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})


def audio_revision_summary_integrity_ok(summary: DomainDocument) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(summary, SUMMARY_INTEGRITY_EXCLUDE)


def session_integrity_ok(session: DomainDocument) -> bool:
    expected = str(session.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(session, SESSION_INTEGRITY_EXCLUDE)


def issue_integrity_ok(issue: DomainDocument) -> bool:
    expected = str(issue.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(issue, ISSUE_INTEGRITY_EXCLUDE)


def candidate_integrity_ok(candidate: DomainDocument) -> bool:
    expected = str(candidate.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(candidate, CANDIDATE_INTEGRITY_EXCLUDE)


def closeout_integrity_ok(closeout: DomainDocument) -> bool:
    expected = str(closeout.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(closeout, CLOSEOUT_INTEGRITY_EXCLUDE)


def export_audio_revisions(release_store: ReleaseStore, release_id: str, export_dir: Path, *, project_store: ProjectStore | None = None, now: str | None = None) -> DomainDocument:
    summary = AudioRevisionStore(release_store, project_store=project_store).write_summary(release_id, export_dir, now=now)
    root = export_dir / "audio-revisions"
    files = []
    for path in sorted(root.rglob("*.json")):
        rel = path.resolve().relative_to(export_dir.resolve()).as_posix()
        files.append({"path": rel, "sha256": file_sha256(path), "payload_hash": stable_hash(read_json(path))})
    return {
        **summary,
        "summary_path": "audio-revisions/summary.json",
        "summary_hash": summary.get("integrity_hash"),
        "files": files,
        "exported_file_count": len(files),
    }


def read_audio_revision_summary_from_export(export_dir: Path) -> DomainDocument:
    path = export_dir / "audio-revisions" / "summary.json"
    if not path.exists():
        return {}
    data = read_json(path)
    return _as_document(data)


def _revision_marker_count(store: AudioRevisionStore, release_id: str) -> int:
    count = 0
    for review in store.audio_review_store.list_reviews(release_id):
        if review.get("stale") or not review_integrity_ok(review):
            continue
        for marker in review.get("markers", []) if isinstance(review.get("markers"), list) else []:
            if isinstance(marker, dict) and str(marker.get("category") or "") in REVISION_CATEGORIES:
                count += 1
    return count


def _candidate_strategies(issue: ImplementationDocument, plan: SongPlan, *, max_count: int) -> list[ImplementationDocument]:
    base_marker = {
        "category": issue.get("category"),
        "severity": issue.get("severity"),
        "message": issue.get("summary"),
        "mapped": {"section_id": issue.get("section_id")} if issue.get("section_id") else {},
    }
    strategies: list[ImplementationDocument] = []
    primary = marker_to_mix_patch_operations(base_marker, {"track_id": issue.get("track_id")}, plan, {})
    strategies.append({"strategy": "marker_default_balance", "operations": primary})
    category = str(issue.get("category") or "")
    section_id = str(issue.get("section_id") or "")
    severity = str(issue.get("severity") or "medium")
    amount = {"low": 1.0, "medium": 1.5, "high": 2.5, "critical": 3.0}.get(severity, 1.5)
    if category == "mix_balance":
        strategies.extend(
            [
                {"strategy": "lift_melody", "operations": [{"op": "set_track_volume", "track_id": _track_by_role(plan, "melody"), "volume_db": amount}]},
                {"strategy": "reduce_drums", "operations": [{"op": "set_track_velocity_scale", "track_id": _track_by_role(plan, "drums"), "velocity_scale": max(0.75, 1.0 - amount / 20)}]},
            ]
        )
    elif category == "sound_quality":
        strategies.extend(
            [
                {"strategy": "reduce_clipping_risk", "operations": [{"op": "set_track_velocity_scale", "track_id": _track_by_role(plan, "melody"), "velocity_scale": 0.9}]},
                {"strategy": "de_muddy_low_end", "operations": [{"op": "set_track_volume", "track_id": _track_by_role(plan, "bass"), "volume_db": -amount}]},
            ]
        )
    else:
        op = "set_section_track_volume_delta" if section_id else "set_track_volume"
        operation = {"op": op, "track_id": _track_by_role(plan, "melody"), "volume_db": amount}
        if section_id:
            operation = {"op": op, "track_id": _track_by_role(plan, "melody"), "section_id": section_id, "volume_db_delta": min(6.0, amount)}
        strategies.extend([{"strategy": "section_energy_lift", "operations": [operation]}, {"strategy": "focus_hook", "operations": [{"op": "set_track_volume", "track_id": _track_by_role(plan, "chords"), "volume_db": -1.0}]}])
    seen: set[str] = set()
    unique = []
    for strategy in strategies:
        key = stable_hash(strategy.get("operations", []))
        if key in seen:
            continue
        seen.add(key)
        unique.append(strategy)
    return unique[: max(1, min(max_count, 5))]


def _track_by_role(plan: SongPlan, role: str) -> str:
    role = role.lower()
    for index, track in enumerate(plan.tracks, start=1):
        name = track.name.lower()
        if role in name:
            return f"track-{index:03d}"
    return "track-001"


def _candidate_score(strategy: ImplementationDocument, audio_health: ImplementationDocument, stem_health: ImplementationDocument) -> ImplementationDocument:
    operations = _as_list(strategy.get("operations"))
    score = 65
    if audio_health.get("status") == "passed":
        score += 15
    elif audio_health.get("status") == "warning":
        score += 5
    else:
        score -= 30
    if stem_health.get("status") in {"passed", "warning"}:
        score += 10
    score -= max(0, len(operations) - 1) * 3
    score = max(0, min(100, score))
    risk = max(0, min(100, 20 + len(operations) * 4 - (10 if audio_health.get("status") == "passed" else 0)))
    return {"deterministic_score": score, "risk_score": risk, "expected_improvement": max(0, score - risk)}


def _candidate_stem_health(*, project_id: str, version_id: str, plan: SongPlan, midi_path: Path, mix_state: ImplementationDocument, candidate_dir: Path, now: str) -> ImplementationDocument:
    run_dir = candidate_dir / "stem-run"
    paths = ProjectPaths.create(run_dir)
    write_json(paths.data / "song-plan.json", plan.to_dict())
    shutil.copy2(midi_path, paths.renders / "song.mid")
    from song_agent.domains.creation.stems import build_stem_manifest, write_stem_manifest
    manifest = build_stem_manifest(plan, run_dir, f"{project_id}-{version_id}", now=now)
    write_stem_manifest(run_dir, manifest)
    for stem in manifest.stems:
        stem_path = run_dir / stem.midi_path
        stem_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(midi_path, stem_path)
    try:
        report = build_stem_health_report(run_dir=run_dir, project_id=project_id, version_id=version_id, mix_state=mix_state, require_wav=False, now=now)
        return write_stem_health_report(run_dir, report)
    except Exception as exc:
        return {"status": "failed", "warnings": [sanitize_sensitive_text(str(exc))[:160]], "integrity_hash": stable_hash(str(exc))}


def _active_revision_markers(audio_review_store: AudioReviewEvidenceStore, release_id: str) -> list[ImplementationDocument]:
    markers: list[ImplementationDocument] = []
    for review in audio_review_store.list_reviews(release_id):
        if review.get("stale") or not review_integrity_ok(review):
            continue
        if review.get("status") not in {"needs_fix", "rejected"}:
            continue
        for marker in review.get("markers", []) if isinstance(review.get("markers"), list) else []:
            if not isinstance(marker, dict):
                continue
            category = str(marker.get("category") or "")
            if category not in REVISION_CATEGORIES:
                continue
            marker_id = str(marker.get("marker_id") or "")
            marker_key = _marker_key(str(review.get("review_id") or ""), marker_id)
            markers.append(
                {
                    "marker_key": marker_key,
                    "review_id": review.get("review_id"),
                    "marker_id": marker_id,
                    "track_id": review.get("track_id"),
                    "project_id": review.get("project_id"),
                    "version_id": review.get("version_id"),
                    "status": review.get("status"),
                    "category": category,
                    "severity": str(marker.get("severity") or "medium"),
                    "review_hash": review_payload_hash(review),
                    "marker_hash": stable_hash(marker),
                }
            )
    return sorted(markers, key=lambda item: str(item.get("marker_key") or ""))


def _covered_marker_ids(issues: list[ImplementationDocument]) -> set[str]:
    covered: set[str] = set()
    for issue in issues:
        review_id = str(issue.get("source_review_id") or "")
        marker_id = str(issue.get("source_marker_id") or "")
        if review_id and marker_id and issue.get("status") != "stale":
            covered.add(_marker_key(review_id, marker_id))
    return covered


def _marker_key(review_id: str, marker_id: str) -> str:
    return f"{review_id}:{marker_id}"


def _render_revision_audio(midi_path: Path, wav_path: Path) -> tuple[str, str | None, RendererConfig]:
    try:
        config, _sources = load_renderer_config()
        render_audio(midi_path, wav_path, config)
        return "completed", None, config
    except RendererError as exc:
        return "failed", sanitize_sensitive_text(str(exc))[:500], RendererConfig()


def _renderer_summary(config: RendererConfig) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "renderer_type": config.renderer_type,
            "sample_rate": config.sample_rate,
            "output_format": config.output_format,
            "gain": config.gain,
            "configured": bool(config.soundfont_path),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _object_hash(value: ImplementationDocument, exclude: set[str]) -> str:
    return stable_hash(sanitize_metadata({key: item for key, item in value.items() if key not in exclude}, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))


def _severity_rank(value: Any) -> int:
    return REVISION_SEVERITIES.get(str(value or "medium"), 2)


def _safe_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise AudioRevisionStateError("Unsafe artifact path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise AudioRevisionStateError("Unsafe artifact path.")
    return "/".join(parts)


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise AudioRevisionStateError("Refusing to access audio revision artifact outside candidate directory.") from exc


def _validate_session_id(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("ars-") or not value.removeprefix("ars-").isdigit():
        raise AudioRevisionError("Invalid audio revision session id.")
    return value


def _validate_issue_id(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("ari-") or not value.removeprefix("ari-").isdigit():
        raise AudioRevisionError("Invalid audio revision issue id.")
    return value


def _validate_candidate_id(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("arc-") or not value.removeprefix("arc-").isdigit():
        raise AudioRevisionError("Invalid audio revision candidate id.")
    return value


def _stale_summary(summary: ImplementationDocument) -> ImplementationDocument:
    data = dict(summary) if isinstance(summary, dict) else {}
    if data:
        data["status"] = "stale"
        data["stale"] = True
    return data

_v142_ar_readiness.bind_globals(globals())
_v142_ar_evidence.bind_globals(globals())
_v142_ar_lifecycle.bind_globals(globals())
