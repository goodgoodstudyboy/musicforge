from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from typing import Any

from song_agent.domains.quality.audio_artifacts import build_audio_artifact_manifest, write_audio_artifact_manifest
from song_agent.domains.quality.audio_health import analyze_wav_health, audio_health_allows_release, audio_health_integrity_ok, audio_health_summary
from song_agent.application.legacy_dependencies.delivery_qa import build_delivery_qa_report
from song_agent.domains.quality.audio_review_evidence import AudioReviewEvidenceStore, review_integrity_ok, review_payload_hash
from song_agent.domains.creation.final_export import FinalExportOptions, build_final_export_bundle, build_final_export_zip, final_export_dir
from song_agent.domains.quality.mix_controls import MixControlError, MixControlStateError, MixControlStore, MixPatch, apply_patch_and_render_plan, build_mix_patch, default_mix_state, file_sha256, marker_to_mix_patch_operations, mix_patch_hash, mix_patch_integrity_ok, mix_state_hash, mix_state_integrity_ok, mix_state_stale_reasons, song_plan_hash, stable_hash
from song_agent.domains.quality.mix_render import _job_state, _project_version_context, _run_summary, _validator_report
from song_agent.domains.studio.projectio import ProjectPaths, append_event, read_json, write_json
from song_agent.domains.studio.project_quality import evaluate_quality_gate, load_quality_gate_config
from song_agent.domains.studio.project_repository import ProjectStore, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.quality.release_audio import build_release_audio_qa_report, write_release_audio_qa
from song_agent.application.legacy_dependencies.releases import BLOCKED_RELEASE_KEYS, ReleaseNotFoundError, ReleaseStateError, ReleaseStore, build_release_track_snapshot
from song_agent.domains.creation.renderers.audio import RendererConfig, RendererError, load_renderer_config, render_audio
from song_agent.domains.creation.renderers.midi import render_midi
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.creation.stem_health import build_stem_health_report, stem_health_summary, write_stem_health_report


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


class AudioRevisionStore:
    def __init__(self, release_store: ReleaseStore, project_store: ProjectStore | None = None, job_store: Any | None = None, audio_review_store: AudioReviewEvidenceStore | None = None) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.job_store = job_store
        self.audio_review_store = audio_review_store or AudioReviewEvidenceStore(release_store, project_store=self.project_store)
        self.lock = threading.RLock()

    def root_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-revisions"

    def session_dir(self, release_id: str, session_id: str) -> Path:
        return self.root_dir(release_id) / _validate_session_id(session_id)

    def issue_path(self, release_id: str, session_id: str, issue_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "issues" / f"{_validate_issue_id(issue_id)}.json"

    def candidate_dir(self, release_id: str, session_id: str, candidate_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "candidates" / _validate_candidate_id(candidate_id)

    def list_sessions(self, release_id: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        root = self.root_dir(release_id)
        if not root.exists():
            return []
        sessions: list[dict[str, Any]] = []
        for path in sorted(root.glob("ars-*/session.json")):
            try:
                session = self.read_session(release_id, path.parent.name)
            except Exception:
                continue
            if session.get("status") == "archived" and not include_archived:
                continue
            sessions.append(session)
        return sorted(sessions, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def create_session(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        payload = payload or {}
        self._ensure_release_mutable(release_id)
        with self.lock:
            session_id = self._reserve_session_id(release_id)
            session_dir = self.session_dir(release_id, session_id)
            session_dir.mkdir(parents=True, exist_ok=False)
            issues = self._issues_from_audio_markers(release_id, session_id, payload, now=now)
            for issue in issues:
                write_json(self.issue_path(release_id, session_id, str(issue["issue_id"])), issue)
            source = self._session_source(release_id)
            session = {
                "schema_version": AUDIO_REVISION_SCHEMA_VERSION,
                "session_id": session_id,
                "release_id": release_id,
                "status": "open",
                "title": sanitize_sensitive_text(str(payload.get("title") or "Audio revision pass"))[:160],
                "created_at": now,
                "updated_at": now,
                "source": source,
                "source_hash": stable_hash(source),
                "issue_count": len(issues),
                "open_issue_count": len([item for item in issues if item.get("status") == "open"]),
                "selected_candidate_count": 0,
                "applied_candidate_count": 0,
                "warnings": [],
            }
            session["integrity_hash"] = _object_hash(session, SESSION_INTEGRITY_EXCLUDE)
            write_json(session_dir / "session.json", sanitize_metadata(session, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
            self._write_issue_index(release_id, session_id)
            self._append_event(release_id, session_id, "audio_revision_session_created", {"issue_count": len(issues)}, now)
            return self.read_session(release_id, session_id)

    def read_session(self, release_id: str, session_id: str) -> dict[str, Any]:
        path = self.session_dir(release_id, session_id) / "session.json"
        if not path.exists():
            raise AudioRevisionNotFoundError(session_id)
        session = read_json(path)
        return self._with_session_current_state(session if isinstance(session, dict) else {})

    def list_issues(self, release_id: str, session_id: str) -> list[dict[str, Any]]:
        self.read_session(release_id, session_id)
        issues = []
        for issue in self._list_raw_issues(release_id, session_id):
            try:
                issues.append(self._with_issue_current_state(issue))
            except Exception:
                continue
        return issues

    def _list_raw_issues(self, release_id: str, session_id: str) -> list[dict[str, Any]]:
        issues_dir = self.session_dir(release_id, session_id) / "issues"
        issues = []
        if not issues_dir.exists():
            return issues
        for path in sorted(issues_dir.glob("ari-*.json")):
            try:
                issue = read_json(path)
                if isinstance(issue, dict):
                    issues.append(issue)
            except Exception:
                continue
        return issues

    def read_issue(self, release_id: str, session_id: str, issue_id: str) -> dict[str, Any]:
        path = self.issue_path(release_id, session_id, issue_id)
        if not path.exists():
            raise AudioRevisionNotFoundError(issue_id)
        issue = read_json(path)
        return self._with_issue_current_state(issue if isinstance(issue, dict) else {})

    def create_issue(self, release_id: str, session_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        track = self._track(release_id, str(payload.get("track_id") or ""))
        issue_id = self._reserve_issue_id(release_id, session_id)
        issue = self._build_issue(
            release_id,
            session_id,
            issue_id,
            track=track,
            review={},
            marker={
                "marker_id": str(payload.get("marker_id") or "manual"),
                "category": payload.get("category") or "other",
                "severity": payload.get("severity") or "medium",
                "message": payload.get("summary") or payload.get("message") or "",
                "mapped": payload.get("mapped") if isinstance(payload.get("mapped"), dict) else {},
                "time_seconds": payload.get("time_seconds"),
            },
            now=now,
        )
        write_json(self.issue_path(release_id, session_id, issue_id), issue)
        self._refresh_session_counts(release_id, session_id, now=now)
        self._write_issue_index(release_id, session_id)
        self._append_event(release_id, session_id, "audio_revision_issue_created", {"issue_id": issue_id}, now)
        return self.read_issue(release_id, session_id, issue_id)

    def waive_issue(self, release_id: str, session_id: str, issue_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        issue = self.read_issue(release_id, session_id, issue_id)
        if issue.get("stale") or not issue_integrity_ok(issue):
            raise AudioRevisionStateError("Audio revision issue is stale or tampered.")
        reason = sanitize_sensitive_text(str(payload.get("reason") or payload.get("waiver_reason") or ""))[:1000]
        if _severity_rank(issue.get("severity")) >= _severity_rank("high") and not reason:
            raise AudioRevisionStateError("High and critical issues require a waiver reason.")
        updated = {key: value for key, value in issue.items() if key not in ISSUE_INTEGRITY_EXCLUDE}
        updated["status"] = "waived"
        updated["waiver"] = {"reason": reason, "waived_by": sanitize_sensitive_text(str(payload.get("waived_by") or "reviewer"))[:120], "waived_at": now}
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, ISSUE_INTEGRITY_EXCLUDE)
        write_json(self.issue_path(release_id, session_id, issue_id), sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._refresh_session_counts(release_id, session_id, now=now)
        return self.read_issue(release_id, session_id, issue_id)

    def reopen_issue(self, release_id: str, session_id: str, issue_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        issue = self.read_issue(release_id, session_id, issue_id)
        updated = {key: value for key, value in issue.items() if key not in ISSUE_INTEGRITY_EXCLUDE}
        updated["status"] = "open"
        updated["waiver"] = None
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, ISSUE_INTEGRITY_EXCLUDE)
        write_json(self.issue_path(release_id, session_id, issue_id), sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._refresh_session_counts(release_id, session_id, now=now)
        return self.read_issue(release_id, session_id, issue_id)

    def generate_candidates(self, release_id: str, session_id: str, issue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        payload = payload or {}
        self._ensure_session_action_allowed(release_id, session_id)
        issue = self.read_issue(release_id, session_id, issue_id)
        if issue.get("stale") or not issue_integrity_ok(issue):
            raise AudioRevisionStateError("Audio revision issue is stale or tampered.")
        if issue.get("status") in {"applied", "needs_recheck", "rechecked", "waived"}:
            raise AudioRevisionStateError("Audio revision issue is not open for candidate generation.")
        context = self._version_context(str(issue["project_id"]), str(issue["version_id"]))
        state = MixControlStore(self.project_store.project_dir(str(issue["project_id"]))).get_or_create_state(
            project_id=str(issue["project_id"]),
            version_id=str(issue["version_id"]),
            plan=context["plan"],
            midi_path=context["midi_path"],
            now=now,
        )
        strategies = _candidate_strategies(issue, context["plan"], max_count=int(payload.get("max_candidates") or 3))
        candidates = []
        for strategy in strategies:
            candidate_id = self._reserve_candidate_id(release_id, session_id)
            candidate_dir = self.candidate_dir(release_id, session_id, candidate_id)
            candidate_dir.mkdir(parents=True, exist_ok=False)
            patch = build_mix_patch(
                patch_id=f"mixpatch-{int(candidate_id.split('-')[-1]):06d}",
                project_id=str(issue["project_id"]),
                version_id=str(issue["version_id"]),
                state=state,
                plan=context["plan"],
                operations=strategy["operations"],
                source={
                    "source_type": "audio_revision_candidate",
                    "release_id": release_id,
                    "session_id": session_id,
                    "issue_id": issue_id,
                    "candidate_id": candidate_id,
                    "strategy": strategy["strategy"],
                },
                label=f"Audio revision {strategy['strategy']}",
                now=now,
            )
            result = apply_patch_and_render_plan(state, patch, context["plan"], now=now)
            preview_dir = candidate_dir / "preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            write_json(candidate_dir / "mix-patch.json", patch.to_dict())
            write_json(preview_dir / "song-plan.json", result.plan.to_dict())
            render_midi(result.plan, preview_dir / "song.mid", track_pans=result.track_pans, track_volumes=result.track_volumes)
            audio_status, audio_error, renderer_config = _render_revision_audio(preview_dir / "song.mid", preview_dir / "song.wav")
            audio_health = analyze_wav_health(preview_dir / "song.wav", source={"release_id": release_id, "session_id": session_id, "issue_id": issue_id, "candidate_id": candidate_id}, report_id=f"arh-{candidate_id}", now=now)
            write_json(preview_dir / "audio-health.json", audio_health)
            stem_health = _candidate_stem_health(project_id=str(issue["project_id"]), version_id=str(issue["version_id"]), plan=result.plan, midi_path=preview_dir / "song.mid", mix_state=result.state.to_dict(), candidate_dir=candidate_dir, now=now)
            candidate_source = self._candidate_source(release_id, issue, state.to_dict(), context, review_id=str(issue.get("source_review_id") or ""), marker_id=str(issue.get("source_marker_id") or ""))
            review = {"status": "pending", "review_mode": None, "reviewer": None, "rating": None, "notes": "", "markers": []}
            candidate = {
                "schema_version": AUDIO_REVISION_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "issue_id": issue_id,
                "session_id": session_id,
                "release_id": release_id,
                "track_id": issue.get("track_id"),
                "project_id": issue.get("project_id"),
                "version_id": issue.get("version_id"),
                "status": "ready_for_review" if audio_status == "completed" and audio_health_allows_release(audio_health) else "rendered",
                "strategy": strategy["strategy"],
                "patch": patch.to_dict(),
                "patch_hash": mix_patch_hash(patch),
                "preview": {
                    "midi_path": "preview/song.mid",
                    "midi_sha256": file_sha256(preview_dir / "song.mid"),
                    "wav_path": "preview/song.wav",
                    "wav_sha256": file_sha256(preview_dir / "song.wav") if (preview_dir / "song.wav").exists() else None,
                    "audio_status": audio_status,
                    "audio_error": audio_error,
                    "renderer": _renderer_summary(renderer_config),
                },
                "health": {
                    "audio_health_status": audio_health.get("status"),
                    "audio_health_hash": audio_health.get("integrity_hash"),
                    "stem_health_status": stem_health.get("status"),
                    "stem_health_hash": stem_health.get("integrity_hash"),
                    "warnings": list(audio_health.get("warnings") or []) + list(stem_health.get("warnings") or []),
                },
                "score": _candidate_score(strategy, audio_health, stem_health),
                "review": review,
                "selected": False,
                "applied_version_id": None,
                "source": candidate_source,
                "source_hash": stable_hash(candidate_source),
                "created_at": now,
                "updated_at": now,
            }
            candidate["integrity_hash"] = _object_hash(candidate, CANDIDATE_INTEGRITY_EXCLUDE)
            write_json(candidate_dir / "candidate.json", sanitize_metadata(candidate, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
            candidates.append(self.read_candidate(release_id, session_id, candidate_id))
        issue_update = {key: value for key, value in issue.items() if key not in ISSUE_INTEGRITY_EXCLUDE}
        issue_update["status"] = "candidates_ready"
        issue_update["candidate_group_id"] = f"{session_id}:{issue_id}"
        issue_update["updated_at"] = now
        issue_update["integrity_hash"] = _object_hash(issue_update, ISSUE_INTEGRITY_EXCLUDE)
        write_json(self.issue_path(release_id, session_id, issue_id), sanitize_metadata(issue_update, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._refresh_session_counts(release_id, session_id, status="reviewing_candidates", now=now)
        self._append_event(release_id, session_id, "audio_revision_candidates_generated", {"issue_id": issue_id, "candidate_count": len(candidates)}, now)
        return {"status": "created", "release_id": release_id, "session_id": session_id, "issue_id": issue_id, "candidates": candidates, "count": len(candidates)}

    def list_candidates(self, release_id: str, session_id: str, *, issue_id: str | None = None) -> list[dict[str, Any]]:
        self.read_session(release_id, session_id)
        root = self.session_dir(release_id, session_id) / "candidates"
        candidates = []
        for path in sorted(root.glob("arc-*/candidate.json")):
            try:
                candidate = self.read_candidate(release_id, session_id, path.parent.name)
            except Exception:
                continue
            if issue_id and candidate.get("issue_id") != issue_id:
                continue
            candidates.append(candidate)
        return candidates

    def read_candidate(self, release_id: str, session_id: str, candidate_id: str) -> dict[str, Any]:
        path = self.candidate_dir(release_id, session_id, candidate_id) / "candidate.json"
        if not path.exists():
            raise AudioRevisionNotFoundError(candidate_id)
        candidate = read_json(path)
        return self._with_candidate_current_state(candidate if isinstance(candidate, dict) else {})

    def review_candidate(self, release_id: str, session_id: str, candidate_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        preview = candidate.get("preview") if isinstance(candidate.get("preview"), dict) else {}
        health = candidate.get("health") if isinstance(candidate.get("health"), dict) else {}
        if preview.get("audio_status") != "completed" or health.get("audio_health_status") not in {"passed", "warning"}:
            raise AudioRevisionStateError("Candidate audio preview must be rendered and pass audio health before manual review.")
        status = str(payload.get("status") or payload.get("review_status") or "accepted")
        if status not in {"accepted", "rejected", "needs_tweak"}:
            raise AudioRevisionError("Candidate review status must be accepted, rejected, or needs_tweak.")
        mode = str(payload.get("review_mode") or "manual")
        if mode not in {"manual", "synthetic"}:
            raise AudioRevisionError("Candidate review_mode must be manual or synthetic.")
        review = {
            "status": status,
            "review_mode": mode,
            "reviewer": sanitize_sensitive_text(str(payload.get("reviewer") or payload.get("reviewed_by") or "reviewer"))[:120],
            "rating": max(0, min(5, int(payload.get("rating") or 0))),
            "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:4000],
            "markers": sanitize_metadata(payload.get("markers") if isinstance(payload.get("markers"), list) else [], blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})[:64],
            "playback_confirmed": bool(payload.get("playback_confirmed", False)),
            "reviewed_at": now,
            "candidate_wav_sha256": (candidate.get("preview") or {}).get("wav_sha256"),
            "parent_wav_sha256": (candidate.get("source") or {}).get("parent_wav_sha256"),
        }
        updated = {key: value for key, value in candidate.items() if key not in CANDIDATE_INTEGRITY_EXCLUDE}
        updated["review"] = review
        updated["status"] = "reviewed" if status == "accepted" else "rejected" if status == "rejected" else "ready_for_review"
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, CANDIDATE_INTEGRITY_EXCLUDE)
        write_json(self.candidate_dir(release_id, session_id, candidate_id) / "candidate.json", sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._append_event(release_id, session_id, "audio_revision_candidate_reviewed", {"candidate_id": candidate_id, "status": status}, now)
        return self.read_candidate(release_id, session_id, candidate_id)

    def select_candidate(self, release_id: str, session_id: str, candidate_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        review = candidate.get("review") if isinstance(candidate.get("review"), dict) else {}
        if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
            raise AudioRevisionStateError("Only manually accepted and playback-confirmed candidates can be selected.")
        preview = candidate.get("preview") if isinstance(candidate.get("preview"), dict) else {}
        health = candidate.get("health") if isinstance(candidate.get("health"), dict) else {}
        if preview.get("audio_status") != "completed" or health.get("audio_health_status") not in {"passed", "warning"}:
            raise AudioRevisionStateError("Only candidates with rendered passing audio can be selected.")
        issue = self.read_issue(release_id, session_id, str(candidate["issue_id"]))
        for other in self.list_candidates(release_id, session_id, issue_id=str(issue["issue_id"])):
            other_data = {key: value for key, value in other.items() if key not in CANDIDATE_INTEGRITY_EXCLUDE}
            other_data["selected"] = other["candidate_id"] == candidate_id
            other_data["status"] = "selected" if other["candidate_id"] == candidate_id else other_data.get("status")
            other_data["updated_at"] = now
            other_data["integrity_hash"] = _object_hash(other_data, CANDIDATE_INTEGRITY_EXCLUDE)
            write_json(self.candidate_dir(release_id, session_id, str(other["candidate_id"])) / "candidate.json", sanitize_metadata(other_data, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        issue_update = {key: value for key, value in issue.items() if key not in ISSUE_INTEGRITY_EXCLUDE}
        issue_update["status"] = "candidate_selected"
        issue_update["selected_candidate_id"] = candidate_id
        issue_update["updated_at"] = now
        issue_update["integrity_hash"] = _object_hash(issue_update, ISSUE_INTEGRITY_EXCLUDE)
        write_json(self.issue_path(release_id, session_id, str(issue["issue_id"])), sanitize_metadata(issue_update, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._refresh_session_counts(release_id, session_id, status="reviewing_candidates", now=now)
        return self.read_candidate(release_id, session_id, candidate_id)

    def apply_candidate(self, release_id: str, session_id: str, candidate_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        payload = payload or {}
        self._ensure_session_action_allowed(release_id, session_id)
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        if not candidate.get("selected"):
            raise AudioRevisionStateError("Candidate must be selected before apply.")
        review = candidate.get("review") if isinstance(candidate.get("review"), dict) else {}
        if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
            raise AudioRevisionStateError("Candidate must have a manual accepted review before apply.")
        preview = candidate.get("preview") if isinstance(candidate.get("preview"), dict) else {}
        health = candidate.get("health") if isinstance(candidate.get("health"), dict) else {}
        if preview.get("audio_status") != "completed" or health.get("audio_health_status") not in {"passed", "warning"}:
            raise AudioRevisionStateError("Candidate audio preview must be rendered and pass audio health before apply.")
        issue = self.read_issue(release_id, session_id, str(candidate["issue_id"]))
        if issue.get("applied_version_id"):
            raise AudioRevisionStateError("This issue already has an applied candidate.")
        context = self._version_context(str(candidate["project_id"]), str(candidate["version_id"]))
        source_reasons = self._candidate_stale_reasons(candidate, context=context)
        if source_reasons:
            raise AudioRevisionStateError("Audio revision candidate is stale: " + ", ".join(source_reasons))
        state = MixControlStore(self.project_store.project_dir(str(candidate["project_id"]))).read_state(str(candidate["version_id"]))
        patch = MixPatch.from_dict(candidate["patch"])
        result = apply_patch_and_render_plan(state, patch, context["plan"], now=now)
        run_title = sanitize_sensitive_text(str(payload.get("version_name") or f"Audio Revision {candidate_id}"))[:160]
        run_dir = self._reserve_run_dir(run_title)
        paths = ProjectPaths.create(run_dir)
        request_payload = {
            **context["version"].request,
            "project_id": candidate["project_id"],
            "parent_version_id": candidate["version_id"],
            "audio_revision_session_id": session_id,
            "audio_revision_issue_id": issue["issue_id"],
            "audio_revision_candidate_id": candidate_id,
            "edit_type": "audio_revision_mix_edit",
        }
        metadata = {
            "schema_version": 1,
            "edit_source": "audio_revision",
            "edit_type": "audio_revision_mix_edit",
            "audio_revision": {
                "release_id": release_id,
                "session_id": session_id,
                "issue_id": issue["issue_id"],
                "candidate_id": candidate_id,
                "source_review_id": issue.get("source_review_id"),
                "source_marker_id": issue.get("source_marker_id"),
            },
            "summary": result.summary,
            "created_at": now,
        }
        write_json(paths.data / "request.json", request_payload)
        write_json(paths.data / "edit-metadata.json", metadata)
        write_json(paths.data / "mix-state.json", result.state.to_dict())
        write_json(paths.data / "mix-patch.json", patch.to_dict())
        write_json(paths.data / "song-plan.json", result.plan.to_dict())
        render_midi(result.plan, paths.renders / "song.mid", track_pans=result.track_pans, track_volumes=result.track_volumes)
        audio_status, audio_error, renderer_config = _render_revision_audio(paths.renders / "song.mid", paths.renders / "song.wav")
        if audio_status != "completed":
            raise AudioRevisionStateError("Audio revision apply could not render real WAV audio: " + str(audio_error or "renderer unavailable"))
        audio_artifact = build_audio_artifact_manifest(
            artifact_id=f"audio-revision-{candidate_id}-{now.replace(':', '').replace('-', '')}",
            scope="project_version",
            wav_path=paths.renders / "song.wav",
            midi_path=paths.renders / "song.mid",
            song_plan_path=paths.data / "song-plan.json",
            renderer_config=renderer_config,
            extra_source={
                "release_id": release_id,
                "session_id": session_id,
                "issue_id": issue["issue_id"],
                "candidate_id": candidate_id,
                "project_id": candidate["project_id"],
                "parent_version_id": candidate["version_id"],
            },
            now=now,
        )
        write_audio_artifact_manifest(paths.renders / "audio-artifact.json", audio_artifact)
        write_json(paths.data / "validator-report.json", _validator_report(paths.data / "song-plan.json", paths.renders / "song.mid"))
        summary = _run_summary(paths.data / "song-plan.json", paths.renders / "song.mid")
        summary["edit"] = metadata["summary"]
        write_json(paths.data / "run-summary.json", summary)
        append_event(paths, {"event": "audio_revision_candidate_applied", "candidate_id": candidate_id, "issue_id": issue["issue_id"]})
        job = _job_state(self.job_store, run_dir.name, run_dir, run_title, now, summary, request_payload, metadata, context["version"].pipeline_mode)
        if self.job_store is not None:
            self.job_store.jobs[job.job_id] = job
            self.job_store._write_job(job)
        document = self.project_store.add_version_from_job(
            str(candidate["project_id"]),
            job,
            name=run_title,
            note=sanitize_sensitive_text(str(payload.get("version_note") or "Audio revision candidate apply"))[:500],
            parent_version_id=str(candidate["version_id"]),
            variant_type="audio_revision_mix_edit",
            change_summary=f"Applied audio revision candidate {candidate_id}",
        )
        version = next(item for item in document.versions if item.job_id == job.job_id)
        child_state = self._child_mix_state(
            project_id=str(candidate["project_id"]),
            version_id=version.version_id,
            parent_version_id=str(candidate["version_id"]),
            plan=result.plan,
            midi_path=paths.renders / "song.mid",
            candidate_id=candidate_id,
            session_id=session_id,
            issue_id=str(issue["issue_id"]),
            now=now,
        )
        write_json(paths.data / "mix-state.json", child_state.to_dict())
        self.project_store.set_final_version(str(candidate["project_id"]), version.version_id)
        project_dir = self.project_store.project_dir(str(candidate["project_id"]))
        gate = evaluate_quality_gate(Path(version.output_dir), load_quality_gate_config(project_dir), now=now)
        project_export = self.project_store.export_project(str(candidate["project_id"]))
        build_final_export_bundle(
            project=self.project_store.get_project(str(candidate["project_id"])).state,
            version=version,
            project_dir=project_dir,
            run_dir=Path(version.output_dir),
            gate=gate,
            options=FinalExportOptions(version_id=version.version_id, include_audio=True, include_stems=False, include_stem_audio=False, force=True),
            now=now,
            project_export=project_export,
        )
        self.project_store.update_version_final_export(str(candidate["project_id"]), version.version_id, final_export_dir(project_dir))
        build_final_export_zip(project_dir, now=now)
        self._refresh_project_delivery_qa(str(candidate["project_id"]), now=now)
        self._replace_release_track_version(release_id, str(candidate["track_id"]), str(candidate["project_id"]), version.version_id, now=now)
        issue_update = {key: value for key, value in issue.items() if key not in ISSUE_INTEGRITY_EXCLUDE}
        issue_update["status"] = "needs_recheck"
        issue_update["applied_version_id"] = version.version_id
        issue_update["selected_candidate_id"] = candidate_id
        issue_update["updated_at"] = now
        issue_update["integrity_hash"] = _object_hash(issue_update, ISSUE_INTEGRITY_EXCLUDE)
        write_json(self.issue_path(release_id, session_id, str(issue["issue_id"])), sanitize_metadata(issue_update, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        candidate_update = {key: value for key, value in candidate.items() if key not in CANDIDATE_INTEGRITY_EXCLUDE}
        candidate_update["status"] = "applied"
        candidate_update["applied_version_id"] = version.version_id
        candidate_update["updated_at"] = now
        candidate_update["integrity_hash"] = _object_hash(candidate_update, CANDIDATE_INTEGRITY_EXCLUDE)
        write_json(self.candidate_dir(release_id, session_id, candidate_id) / "candidate.json", sanitize_metadata(candidate_update, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._refresh_session_source(release_id, session_id, now=now)
        self._refresh_session_counts(release_id, session_id, status="partially_applied", now=now)
        self._append_event(release_id, session_id, "audio_revision_candidate_applied", {"candidate_id": candidate_id, "applied_version_id": version.version_id}, now)
        self._refresh_release_audio_qa(release_id, now=now)
        return {"status": "applied", "release_id": release_id, "session_id": session_id, "issue_id": issue["issue_id"], "candidate_id": candidate_id, "applied_version_id": version.version_id, "release": self.release_store.get_release(release_id).to_dict()}

    def replace_release_track_version(self, release_id: str, track_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        current = self._track(release_id, track_id)
        project_id = str(payload.get("project_id") or current.project_id)
        version_id = str(payload.get("version_id") or "").strip()
        if not version_id:
            raise AudioRevisionError("version_id is required.")
        self._replace_release_track_version(release_id, track_id, project_id, version_id, now=now)
        self._refresh_release_audio_qa(release_id, now=now)
        return self.release_store.get_release(release_id).to_dict()

    def refresh_recheck_status(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._refresh_session_source(release_id, session_id, now=now)
        reviews = self.audio_review_store.list_reviews(release_id)
        changed = 0
        for issue in self.list_issues(release_id, session_id):
            if issue.get("status") != "needs_recheck" or not issue.get("applied_version_id"):
                continue
            current_reviews = [
                review
                for review in reviews
                if review.get("track_id") == issue.get("track_id")
                and review.get("version_id") == issue.get("applied_version_id")
                and review.get("status") == "accepted"
                and review.get("review_mode") == "manual"
                and review.get("playback_confirmed")
                and not review.get("stale")
                and review_integrity_ok(review)
            ]
            if not current_reviews:
                continue
            updated = {key: value for key, value in issue.items() if key not in ISSUE_INTEGRITY_EXCLUDE}
            updated["status"] = "rechecked"
            updated["recheck_review_id"] = current_reviews[0].get("review_id")
            updated["updated_at"] = now
            updated["integrity_hash"] = _object_hash(updated, ISSUE_INTEGRITY_EXCLUDE)
            write_json(self.issue_path(release_id, session_id, str(issue["issue_id"])), sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
            changed += 1
        self._refresh_session_counts(release_id, session_id, now=now)
        self._refresh_session_source(release_id, session_id, now=now)
        return {"status": "refreshed", "release_id": release_id, "session_id": session_id, "rechecked_count": changed, "issues": self.list_issues(release_id, session_id)}

    def close_session(self, release_id: str, session_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        payload = payload or {}
        self._ensure_release_mutable(release_id)
        self._refresh_session_source(release_id, session_id, now=now)
        session = self.read_session(release_id, session_id)
        if session.get("stale") or not session_integrity_ok(session):
            raise AudioRevisionStateError("Audio revision session is stale or tampered.")
        self.refresh_recheck_status(release_id, session_id, now=now)
        force = bool(payload.get("force", False))
        closeout = self.build_closeout(release_id, session_id, now=now, force=force, override_reason=str(payload.get("override_reason") or ""))
        if force and closeout.get("status") != "passed" and closeout.get("force_allowed") is False:
            write_json(self.session_dir(release_id, session_id) / "closeout.json", closeout)
            raise AudioRevisionStateError("Audio revision closeout has blockers that cannot be force closed.")
        if closeout.get("status") == "failed" and not force:
            write_json(self.session_dir(release_id, session_id) / "closeout.json", closeout)
            raise AudioRevisionStateError("Audio revision closeout failed.")
        if closeout.get("stale") or not closeout_integrity_ok(closeout):
            raise AudioRevisionStateError("Audio revision closeout is stale or tampered.")
        write_json(self.session_dir(release_id, session_id) / "closeout.json", closeout)
        self._refresh_session_counts(release_id, session_id, status="closed", now=now)
        self._append_event(release_id, session_id, "audio_revision_session_closed", {"status": closeout.get("status")}, now)
        return {"status": "closed", "release_id": release_id, "session_id": session_id, "closeout": closeout}

    def build_closeout(self, release_id: str, session_id: str, *, now: str | None = None, force: bool = False, override_reason: str = "") -> dict[str, Any]:
        now = now or now_iso()
        session = self.read_session(release_id, session_id)
        issues = self.list_issues(release_id, session_id)
        candidates = self.list_candidates(release_id, session_id)
        blockers: list[str] = []
        warnings: list[str] = []
        force_blockers: list[str] = []
        override = sanitize_sensitive_text(override_reason).strip()[:1000]
        if session.get("stale"):
            blockers.append("session_stale")
            force_blockers.append("session_stale")
        if not session_integrity_ok(session):
            blockers.append("session_integrity")
            force_blockers.append("session_integrity")
        release = self.release_store.get_release(release_id)
        tracks = {track.track_id: track for track in release.tracks}
        reviews = self.audio_review_store.list_reviews(release_id)
        for issue in issues:
            if issue.get("stale") or not issue_integrity_ok(issue):
                blockers.append(f"{issue.get('issue_id')}: issue_stale_or_tampered")
                force_blockers.append(f"{issue.get('issue_id')}: issue_stale_or_tampered")
            severity = _severity_rank(issue.get("severity"))
            status = str(issue.get("status") or "")
            if severity >= _severity_rank("high") and status not in {"rechecked", "waived"}:
                blockers.append(f"{issue.get('issue_id')}: high_issue_unresolved")
                force_blockers.append(f"{issue.get('issue_id')}: high_issue_unresolved")
            if status == "waived" and severity < _severity_rank("high"):
                warnings.append(f"{issue.get('issue_id')}: waived")
            if status == "needs_recheck":
                blockers.append(f"{issue.get('issue_id')}: applied_but_unrechecked")
            applied_version = str(issue.get("applied_version_id") or "")
            if applied_version:
                track = tracks.get(str(issue.get("track_id") or ""))
                if track is None or track.version_id != applied_version:
                    blockers.append(f"{issue.get('issue_id')}: release_track_version_mismatch")
                current_review = any(
                    review.get("track_id") == issue.get("track_id")
                    and review.get("version_id") == applied_version
                    and review.get("status") == "accepted"
                    and review.get("review_mode") == "manual"
                    and review.get("playback_confirmed")
                    and not review.get("stale")
                    and review_integrity_ok(review)
                    for review in reviews
                )
                if not current_review:
                    blockers.append(f"{issue.get('issue_id')}: recheck_review_missing")
        for candidate in candidates:
            if candidate.get("stale") or not candidate_integrity_ok(candidate):
                blockers.append(f"{candidate.get('candidate_id')}: candidate_stale_or_tampered")
                force_blockers.append(f"{candidate.get('candidate_id')}: candidate_stale_or_tampered")
            if candidate.get("selected") and not candidate.get("applied_version_id"):
                blockers.append(f"{candidate.get('candidate_id')}: selected_candidate_not_applied")
        status = "failed" if blockers else "warning" if warnings else "passed"
        if force and status != "passed" and not override:
            blockers.append("force_override_reason_missing")
            force_blockers.append("force_override_reason_missing")
            status = "failed"
        force_allowed = bool(force and status != "passed" and override and not force_blockers)
        closeout = {
            "schema_version": AUDIO_REVISION_SCHEMA_VERSION,
            "release_id": release_id,
            "session_id": session_id,
            "status": "force_closed" if force_allowed else status,
            "generated_at": now,
            "force": bool(force),
            "override_reason": override,
            "force_allowed": (not force) or status == "passed" or force_allowed,
            "force_blockers": sorted(set(force_blockers)),
            "source_hash": session.get("source_hash"),
            "session_hash": session.get("integrity_hash"),
            "issue_count": len(issues),
            "open_issue_count": len([issue for issue in issues if issue.get("status") in {"open", "candidates_ready", "candidate_selected", "applied", "needs_recheck"}]),
            "applied_issue_count": len([issue for issue in issues if issue.get("applied_version_id")]),
            "rechecked_issue_count": len([issue for issue in issues if issue.get("status") == "rechecked"]),
            "waived_issue_count": len([issue for issue in issues if issue.get("status") == "waived"]),
            "selected_candidate_count": len([candidate for candidate in candidates if candidate.get("selected")]),
            "applied_candidate_count": len([candidate for candidate in candidates if candidate.get("applied_version_id")]),
            "blockers": blockers,
            "warnings": warnings,
        }
        closeout["integrity_hash"] = _object_hash(closeout, CLOSEOUT_INTEGRITY_EXCLUDE)
        return sanitize_metadata(closeout, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def read_closeout(self, release_id: str, session_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.session_dir(release_id, session_id) / "closeout.json"
        if not path.exists():
            if default is not None:
                return default
            raise AudioRevisionNotFoundError("Audio revision closeout is missing.")
        closeout = read_json(path)
        return sanitize_metadata(closeout if isinstance(closeout, dict) else {}, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def archive_session(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        session = self.read_session(release_id, session_id)
        updated = {key: value for key, value in session.items() if key not in SESSION_INTEGRITY_EXCLUDE}
        updated["status"] = "archived"
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, SESSION_INTEGRITY_EXCLUDE)
        write_json(self.session_dir(release_id, session_id) / "session.json", sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        return self.read_session(release_id, session_id)

    def download_candidate_artifact(self, release_id: str, session_id: str, candidate_id: str, artifact: str) -> tuple[Path, str, str]:
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        preview = candidate.get("preview") if isinstance(candidate.get("preview"), dict) else {}
        key = "midi_path" if artifact == "midi" else "wav_path"
        rel = _safe_relative_path(str(preview.get(key) or ""))
        root = self.candidate_dir(release_id, session_id, candidate_id).resolve()
        path = (root / rel).resolve()
        _ensure_within(root, path)
        if not path.exists() or not path.is_file() or path.is_symlink():
            raise AudioRevisionNotFoundError(artifact)
        expected = str(preview.get("midi_sha256" if artifact == "midi" else "wav_sha256") or "")
        if expected and file_sha256(path) != expected:
            raise AudioRevisionStateError("Audio revision candidate artifact hash mismatch.")
        media_type = "audio/midi" if artifact == "midi" else "audio/wav"
        filename = f"{candidate_id}.mid" if artifact == "midi" else f"{candidate_id}.wav"
        return path, media_type, filename

    def write_summary(self, release_id: str, export_dir: Path, *, now: str | None = None) -> dict[str, Any]:
        summary = build_audio_revision_summary(self, release_id, now=now)
        target_root = export_dir / "audio-revisions"
        sessions_dir = target_root / "sessions"
        issues_dir = target_root / "issues"
        candidates_dir = target_root / "selected-candidates"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        issues_dir.mkdir(parents=True, exist_ok=True)
        candidates_dir.mkdir(parents=True, exist_ok=True)
        write_json(target_root / "summary.json", summary)
        for session in self.list_sessions(release_id, include_archived=False):
            session_id = str(session.get("session_id") or "")
            write_json(sessions_dir / f"{session_id}.json", session)
            closeout = self.read_closeout(release_id, session_id, default={})
            if closeout:
                write_json(sessions_dir / f"{session_id}-closeout.json", closeout)
            for issue in self.list_issues(release_id, session_id):
                write_json(issues_dir / f"{session_id}-{issue.get('issue_id')}.json", issue)
            for candidate in self.list_candidates(release_id, session_id):
                if candidate.get("selected") or candidate.get("applied_version_id"):
                    write_json(candidates_dir / f"{session_id}-{candidate.get('candidate_id')}.json", candidate)
        return summary

    def gate(self, release_id: str, *, required: bool = False, now: str | None = None) -> dict[str, Any]:
        summary = build_audio_revision_summary(self, release_id, now=now)
        marker_count = summary.get("source_marker_count", 0)
        if required and not summary.get("session_count") and marker_count:
            return {**summary, "status": "failed", "hard_block": True, "message": "Audio revision closeout is required for release audio review markers."}
        if required and summary.get("status") in {"failed", "missing"}:
            return {**summary, "status": "failed", "hard_block": True, "message": "Audio revision closeout gate failed."}
        if summary.get("status") == "failed":
            return {**summary, "status": "failed" if required else "warning", "message": "Audio revision closeout has unresolved blockers."}
        return {**summary, "status": "passed" if summary.get("status") == "passed" else "warning" if summary.get("session_count") else "missing", "message": "Audio revision closeout gate passed."}

    def _issues_from_audio_markers(self, release_id: str, session_id: str, payload: dict[str, Any], *, now: str) -> list[dict[str, Any]]:
        include_categories = {str(item) for item in payload.get("include_categories", []) if str(item).strip()} if isinstance(payload.get("include_categories"), list) else set(REVISION_CATEGORIES)
        min_severity = str(payload.get("min_severity") or "low")
        track_ids = {str(item) for item in payload.get("track_ids", []) if str(item).strip()} if isinstance(payload.get("track_ids"), list) else set()
        reviews = self.audio_review_store.list_reviews(release_id)
        issues: list[dict[str, Any]] = []
        for review in sorted(reviews, key=lambda item: str(item.get("review_id") or "")):
            if review.get("stale") or not review_integrity_ok(review):
                continue
            if review.get("status") not in {"needs_fix", "accepted", "rejected"}:
                continue
            track = self._track(release_id, str(review.get("track_id") or ""))
            if track_ids and track.track_id not in track_ids:
                continue
            for marker in review.get("markers", []) if isinstance(review.get("markers"), list) else []:
                if not isinstance(marker, dict):
                    continue
                category = str(marker.get("category") or "other")
                severity = str(marker.get("severity") or "medium")
                if category not in include_categories or _severity_rank(severity) < _severity_rank(min_severity):
                    continue
                issue_id = f"ari-{len(issues) + 1:06d}"
                issues.append(self._build_issue(release_id, session_id, issue_id, track=track, review=review, marker=marker, now=now))
        return issues

    def _build_issue(self, release_id: str, session_id: str, issue_id: str, *, track: Any, review: dict[str, Any], marker: dict[str, Any], now: str) -> dict[str, Any]:
        source_review_id = str(review.get("review_id") or "")
        source_marker_id = str(marker.get("marker_id") or "")
        source = {
            "release_id": release_id,
            "session_id": session_id,
            "track": {"track_id": track.track_id, "project_id": track.project_id, "version_id": track.version_id},
            "source_review_id": source_review_id,
            "source_marker_id": source_marker_id,
            "review_hash": review_payload_hash(review) if review else None,
            "marker": marker,
        }
        issue = {
            "schema_version": AUDIO_REVISION_SCHEMA_VERSION,
            "issue_id": _validate_issue_id(issue_id),
            "session_id": session_id,
            "release_id": release_id,
            "track_id": track.track_id,
            "project_id": track.project_id,
            "version_id": track.version_id,
            "source_review_id": source_review_id,
            "source_marker_id": source_marker_id,
            "category": str(marker.get("category") or "other"),
            "severity": str(marker.get("severity") or "medium") if str(marker.get("severity") or "medium") in REVISION_SEVERITIES else "medium",
            "section_id": (marker.get("mapped") or {}).get("section_id") if isinstance(marker.get("mapped"), dict) else None,
            "start_beat": (marker.get("mapped") or {}).get("beat") if isinstance(marker.get("mapped"), dict) else None,
            "end_beat": None,
            "time_seconds": marker.get("time_seconds"),
            "summary": sanitize_sensitive_text(str(marker.get("message") or "Audio revision issue"))[:1000],
            "status": "open",
            "candidate_group_id": None,
            "selected_candidate_id": None,
            "applied_version_id": None,
            "waiver": None,
            "source": source,
            "source_hash": stable_hash(source),
            "created_at": now,
            "updated_at": now,
        }
        issue["integrity_hash"] = _object_hash(issue, ISSUE_INTEGRITY_EXCLUDE)
        return sanitize_metadata(issue, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def _with_session_current_state(self, session: dict[str, Any]) -> dict[str, Any]:
        reasons = []
        if not session_integrity_ok(session):
            reasons.append("session_integrity")
        current_source = self._session_source(str(session.get("release_id") or ""))
        current_hash = stable_hash(current_source)
        if session.get("source_hash") != current_hash:
            reasons.append("source_hash")
        clean = dict(session)
        clean["current_source_hash"] = current_hash
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(reasons)
        return sanitize_metadata(clean, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def _with_issue_current_state(self, issue: dict[str, Any]) -> dict[str, Any]:
        reasons = []
        if not issue_integrity_ok(issue):
            reasons.append("issue_integrity")
        try:
            track = self._track(str(issue.get("release_id") or ""), str(issue.get("track_id") or ""))
            applied_version = str(issue.get("applied_version_id") or "")
            expected_version = applied_version or str(issue.get("version_id") or "")
            if track.project_id != issue.get("project_id") or track.version_id != expected_version:
                reasons.append("track_identity_changed")
            review_id = str(issue.get("source_review_id") or "")
            if review_id and not applied_version:
                review = self.audio_review_store.read_review(str(issue.get("release_id") or ""), review_id)
                if review.get("stale") or not review_integrity_ok(review):
                    reasons.append("source_review_stale")
                if (issue.get("source") or {}).get("review_hash") != review_payload_hash(review):
                    reasons.append("source_review_hash")
        except Exception as exc:
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "source_unavailable")
        clean = dict(issue)
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(reasons)
        return sanitize_metadata(clean, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def _with_candidate_current_state(self, candidate: dict[str, Any]) -> dict[str, Any]:
        reasons = []
        if not candidate_integrity_ok(candidate):
            reasons.append("candidate_integrity")
        try:
            context = self._version_context(str(candidate.get("project_id") or ""), str(candidate.get("version_id") or ""))
            reasons.extend(self._candidate_stale_reasons(candidate, context=context))
        except Exception as exc:
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "source_unavailable")
        clean = dict(candidate)
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(reasons)
        if clean["stale"] and clean.get("status") not in {"applied", "rejected"}:
            clean["status"] = "stale"
        return sanitize_metadata(clean, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def _candidate_stale_reasons(self, candidate: dict[str, Any], *, context: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        patch_payload = candidate.get("patch") if isinstance(candidate.get("patch"), dict) else {}
        try:
            patch = MixPatch.from_dict(patch_payload)
            if not mix_patch_integrity_ok(patch):
                reasons.append("patch_integrity")
        except Exception:
            reasons.append("patch_invalid")
        source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
        current_state = MixControlStore(self.project_store.project_dir(str(candidate.get("project_id") or ""))).read_state(str(candidate.get("version_id") or ""))
        if source.get("parent_song_plan_hash") != song_plan_hash(context["plan"]):
            reasons.append("parent_song_plan_hash")
        if source.get("parent_midi_hash") != file_sha256(context["midi_path"]):
            reasons.append("parent_midi_hash")
        if source.get("mix_state_hash") != mix_state_hash(current_state):
            reasons.append("mix_state_hash")
        if candidate.get("source_hash") != stable_hash(source):
            reasons.append("source_hash")
        preview = candidate.get("preview") if isinstance(candidate.get("preview"), dict) else {}
        root = self.candidate_dir(str(candidate.get("release_id") or ""), str(candidate.get("session_id") or ""), str(candidate.get("candidate_id") or ""))
        for key, hash_key, reason in (("midi_path", "midi_sha256", "preview_midi_hash"), ("wav_path", "wav_sha256", "preview_wav_hash")):
            if key == "wav_path" and preview.get("audio_status") != "completed" and not preview.get(hash_key):
                continue
            rel = str(preview.get(key) or "")
            try:
                path = (root / _safe_relative_path(rel)).resolve()
                _ensure_within(root.resolve(), path)
                if preview.get(hash_key) != file_sha256(path):
                    reasons.append(reason)
            except Exception:
                reasons.append(reason)
        return sorted(set(reasons))

    def _candidate_source(self, release_id: str, issue: dict[str, Any], mix_state: dict[str, Any], context: dict[str, Any], *, review_id: str, marker_id: str) -> dict[str, Any]:
        audio_context = self.audio_review_store.track_audio_context(release_id, str(issue.get("track_id") or ""), require_reviewable=False)
        evidence = audio_context.get("audio_evidence") if isinstance(audio_context.get("audio_evidence"), dict) else {}
        return {
            "release_id": release_id,
            "session_id": issue.get("session_id"),
            "issue_id": issue.get("issue_id"),
            "track_id": issue.get("track_id"),
            "project_id": issue.get("project_id"),
            "version_id": issue.get("version_id"),
            "parent_song_plan_hash": song_plan_hash(context["plan"]),
            "parent_midi_hash": file_sha256(context["midi_path"]),
            "parent_wav_sha256": evidence.get("wav_sha256"),
            "mix_state_hash": mix_state_hash(mix_state),
            "source_review_id": review_id,
            "source_marker_id": marker_id,
            "issue_hash": issue.get("integrity_hash"),
        }

    def _session_source(self, release_id: str) -> dict[str, Any]:
        release = self.release_store.get_release(release_id)
        return {
            "release_id": release_id,
            "release_identity": {
                "release_id": release.release_id,
                "name": release.name,
                "release_type": release.release_type,
                "primary_artist": release.primary_artist,
            },
            "track_identities": [{"track_id": track.track_id, "project_id": track.project_id} for track in release.tracks],
        }

    def _version_context(self, project_id: str, version_id: str) -> dict[str, Any]:
        document, version, job, plan, midi_path = _project_version_context(self.project_store, self.job_store, project_id, version_id)
        state = MixControlStore(self.project_store.project_dir(project_id)).get_or_create_state(project_id=project_id, version_id=version_id, plan=plan, midi_path=midi_path, now=now_iso())
        stale = mix_state_stale_reasons(state, plan=plan, midi_path=midi_path)
        if stale:
            raise AudioRevisionStateError("Mix state is stale: " + ", ".join(stale))
        return {"document": document, "version": version, "job": job, "plan": plan, "midi_path": midi_path, "mix_state": state}

    def _track(self, release_id: str, track_id: str) -> Any:
        release = self.release_store.get_release(release_id)
        track = next((item for item in release.tracks if item.track_id == track_id), None)
        if track is None:
            raise AudioRevisionNotFoundError(f"Release track not found: {track_id}.")
        return track

    def _replace_release_track_version(self, release_id: str, track_id: str, project_id: str, version_id: str, *, now: str) -> None:
        release = self.release_store.get_release(release_id)
        self.release_store._ensure_mutable(release)
        found = False
        tracks = []
        for track in release.tracks:
            if track.track_id != track_id:
                tracks.append(track)
                continue
            found = True
            if track.project_id != project_id:
                raise AudioRevisionStateError("Audio revision candidate cannot change release track project.")
            tracks.append(
                build_release_track_snapshot(
                    self.project_store,
                    track_id=track.track_id,
                    project_id=project_id,
                    version_id=version_id,
                    track_number=track.track_number,
                    disc_number=track.disc_number,
                    title=track.title,
                    artist=track.artist,
                    now=now,
                )
            )
        if not found:
            raise AudioRevisionNotFoundError(track_id)
        release.tracks = tracks
        release.latest_qa_summary = _stale_summary(release.latest_qa_summary)
        release.latest_export_summary = _stale_summary(release.latest_export_summary)
        self.release_store.save_release(release)
        self.release_store.append_event(release_id, "release_track_version_replaced", {"track_id": track_id, "project_id": project_id, "version_id": version_id})

    def _refresh_release_audio_qa(self, release_id: str, *, now: str) -> dict[str, Any]:
        release = self.release_store.get_release(release_id)
        report = build_release_audio_qa_report(
            release=release,
            release_store=self.release_store,
            project_store=self.project_store,
            require_audio=True,
            now=now,
        )
        return write_release_audio_qa(self.release_store, release_id, report)

    def _refresh_project_delivery_qa(self, project_id: str, *, now: str) -> dict[str, Any]:
        project_dir = self.project_store.project_dir(project_id)
        manifest = read_json(final_export_dir(project_dir) / "manifest.json")
        report = build_delivery_qa_report(
            project_id=project_id,
            project_document=self.project_store.get_project(project_id),
            project_dir=project_dir,
            project_export=self.project_store.project_export_snapshot(project_id),
            final_export_manifest=manifest if isinstance(manifest, dict) else {},
            now=now,
        )
        return self.project_store.write_delivery_qa(project_id, report, now=now)

    def _child_mix_state(
        self,
        *,
        project_id: str,
        version_id: str,
        parent_version_id: str,
        plan: SongPlan,
        midi_path: Path,
        candidate_id: str,
        session_id: str,
        issue_id: str,
        now: str,
    ) -> Any:
        base = default_mix_state(project_id=project_id, version_id=version_id, plan=plan, midi_path=midi_path, now=now)
        source = {
            **base.source,
            "source_type": "audio_revision_applied_mix_version",
            "parent_version_id": parent_version_id,
            "audio_revision_session_id": session_id,
            "audio_revision_issue_id": issue_id,
            "audio_revision_candidate_id": candidate_id,
        }
        state = type(base).from_dict(
            {
                **base.to_dict(),
                "source": source,
                "source_hash": stable_hash(source),
                "updated_at": now,
            }
        )
        return MixControlStore(self.project_store.project_dir(project_id)).write_state(state)

    def _refresh_session_counts(self, release_id: str, session_id: str, *, status: str | None = None, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        session = self.read_session(release_id, session_id)
        issues = self.list_issues(release_id, session_id)
        candidates = self.list_candidates(release_id, session_id)
        updated = {key: value for key, value in session.items() if key not in SESSION_INTEGRITY_EXCLUDE}
        if status:
            updated["status"] = status
        updated["updated_at"] = now
        updated["issue_count"] = len(issues)
        updated["open_issue_count"] = len([issue for issue in issues if issue.get("status") in {"open", "candidates_ready", "candidate_selected", "applied", "needs_recheck"}])
        updated["selected_candidate_count"] = len([candidate for candidate in candidates if candidate.get("selected")])
        updated["applied_candidate_count"] = len([candidate for candidate in candidates if candidate.get("applied_version_id")])
        updated["integrity_hash"] = _object_hash(updated, SESSION_INTEGRITY_EXCLUDE)
        write_json(self.session_dir(release_id, session_id) / "session.json", sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        self._write_issue_index(release_id, session_id)
        return self.read_session(release_id, session_id)

    def _refresh_session_source(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        path = self.session_dir(release_id, session_id) / "session.json"
        if not path.exists():
            raise AudioRevisionNotFoundError(session_id)
        session = read_json(path)
        if not isinstance(session, dict):
            raise AudioRevisionNotFoundError(session_id)
        updated = {key: value for key, value in session.items() if key not in SESSION_INTEGRITY_EXCLUDE}
        source = self._session_source(release_id)
        updated["source"] = source
        updated["source_hash"] = stable_hash(source)
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, SESSION_INTEGRITY_EXCLUDE)
        write_json(path, sanitize_metadata(updated, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"}))
        return self.read_session(release_id, session_id)

    def _write_issue_index(self, release_id: str, session_id: str) -> None:
        issues = []
        issues_dir = self.session_dir(release_id, session_id) / "issues"
        for path in sorted(issues_dir.glob("ari-*.json")):
            try:
                issue = read_json(path)
            except Exception:
                continue
            issues.append({"issue_id": issue.get("issue_id"), "track_id": issue.get("track_id"), "status": issue.get("status"), "category": issue.get("category"), "severity": issue.get("severity"), "integrity_hash": issue.get("integrity_hash")})
        write_json(self.session_dir(release_id, session_id) / "issue-index.json", {"schema_version": AUDIO_REVISION_SCHEMA_VERSION, "release_id": release_id, "session_id": session_id, "issue_count": len(issues), "issues": issues, "integrity_hash": stable_hash(issues)})

    def _reserve_session_id(self, release_id: str) -> str:
        root = self.root_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            session_id = f"ars-{index:06d}"
            if not (root / session_id).exists():
                return session_id
        raise AudioRevisionError("Unable to allocate audio revision session id.")

    def _reserve_issue_id(self, release_id: str, session_id: str) -> str:
        issues_dir = self.session_dir(release_id, session_id) / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            issue_id = f"ari-{index:06d}"
            if not (issues_dir / f"{issue_id}.json").exists():
                return issue_id
        raise AudioRevisionError("Unable to allocate audio revision issue id.")

    def _reserve_candidate_id(self, release_id: str, session_id: str) -> str:
        root = self.session_dir(release_id, session_id) / "candidates"
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            candidate_id = f"arc-{index:06d}"
            if not (root / candidate_id).exists():
                return candidate_id
        raise AudioRevisionError("Unable to allocate audio revision candidate id.")

    def _reserve_run_dir(self, title: str) -> Path:
        if self.job_store is not None:
            return self.job_store._reserve_run_dir(title)
        root = Path("runs")
        root.mkdir(parents=True, exist_ok=True)
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-") or "audio-revision"
        for index in range(1, 1_000_000):
            target = root / f"{slug}-{index:06d}"
            try:
                target.mkdir(parents=True, exist_ok=False)
                return target
            except FileExistsError:
                continue
        raise AudioRevisionError("Unable to allocate audio revision run directory.")

    def _ensure_release_mutable(self, release_id: str) -> None:
        release = self.release_store.get_release(release_id)
        if release.status == "archived":
            raise AudioRevisionStateError("Archived releases are read-only.")
        if release.status == "signed" or self.release_store.read_signoff(release_id, default={}):
            raise AudioRevisionStateError("Signed releases cannot change audio revision evidence. Reset signoff first.")

    def _ensure_session_action_allowed(self, release_id: str, session_id: str) -> None:
        self._ensure_release_mutable(release_id)
        session = self.read_session(release_id, session_id)
        if session.get("status") in {"closed", "archived"}:
            raise AudioRevisionStateError("Closed or archived audio revision sessions are read-only.")
        if session.get("stale") or not session_integrity_ok(session):
            raise AudioRevisionStateError("Audio revision session is stale or tampered.")

    def _append_event(self, release_id: str, session_id: str, event_type: str, payload: dict[str, Any], now: str) -> None:
        root = self.session_dir(release_id, session_id)
        root.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})
        with (root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)


def build_audio_revision_summary(store: AudioRevisionStore, release_id: str, *, now: str | None = None) -> dict[str, Any]:
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


def audio_revision_summary_integrity_ok(summary: dict[str, Any]) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(summary, SUMMARY_INTEGRITY_EXCLUDE)


def session_integrity_ok(session: dict[str, Any]) -> bool:
    expected = str(session.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(session, SESSION_INTEGRITY_EXCLUDE)


def issue_integrity_ok(issue: dict[str, Any]) -> bool:
    expected = str(issue.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(issue, ISSUE_INTEGRITY_EXCLUDE)


def candidate_integrity_ok(candidate: dict[str, Any]) -> bool:
    expected = str(candidate.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(candidate, CANDIDATE_INTEGRITY_EXCLUDE)


def closeout_integrity_ok(closeout: dict[str, Any]) -> bool:
    expected = str(closeout.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(closeout, CLOSEOUT_INTEGRITY_EXCLUDE)


def export_audio_revisions(release_store: ReleaseStore, release_id: str, export_dir: Path, *, project_store: ProjectStore | None = None, now: str | None = None) -> dict[str, Any]:
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


def read_audio_revision_summary_from_export(export_dir: Path) -> dict[str, Any]:
    path = export_dir / "audio-revisions" / "summary.json"
    if not path.exists():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def _revision_marker_count(store: AudioRevisionStore, release_id: str) -> int:
    count = 0
    for review in store.audio_review_store.list_reviews(release_id):
        if review.get("stale") or not review_integrity_ok(review):
            continue
        for marker in review.get("markers", []) if isinstance(review.get("markers"), list) else []:
            if isinstance(marker, dict) and str(marker.get("category") or "") in REVISION_CATEGORIES:
                count += 1
    return count


def _candidate_strategies(issue: dict[str, Any], plan: SongPlan, *, max_count: int) -> list[dict[str, Any]]:
    base_marker = {
        "category": issue.get("category"),
        "severity": issue.get("severity"),
        "message": issue.get("summary"),
        "mapped": {"section_id": issue.get("section_id")} if issue.get("section_id") else {},
    }
    strategies: list[dict[str, Any]] = []
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


def _candidate_score(strategy: dict[str, Any], audio_health: dict[str, Any], stem_health: dict[str, Any]) -> dict[str, Any]:
    operations = strategy.get("operations") if isinstance(strategy.get("operations"), list) else []
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


def _candidate_stem_health(*, project_id: str, version_id: str, plan: SongPlan, midi_path: Path, mix_state: dict[str, Any], candidate_dir: Path, now: str) -> dict[str, Any]:
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


def _active_revision_markers(audio_review_store: AudioReviewEvidenceStore, release_id: str) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
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


def _covered_marker_ids(issues: list[dict[str, Any]]) -> set[str]:
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


def _renderer_summary(config: RendererConfig) -> dict[str, Any]:
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


def _object_hash(value: dict[str, Any], exclude: set[str]) -> str:
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


def _stale_summary(summary: dict[str, Any]) -> dict[str, Any]:
    data = dict(summary) if isinstance(summary, dict) else {}
    if data:
        data["status"] = "stale"
        data["stale"] = True
    return data
