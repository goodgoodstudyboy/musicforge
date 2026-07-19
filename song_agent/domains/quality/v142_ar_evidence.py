# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from pathlib import Path as Path
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

AudioRevisionError = _make_deferred_global('AudioRevisionError')
AudioRevisionNotFoundError = _make_deferred_global('AudioRevisionNotFoundError')
AudioRevisionStateError = _make_deferred_global('AudioRevisionStateError')
_ensure_within = _make_deferred_global('_ensure_within')
_object_hash = _make_deferred_global('_object_hash')
_render_revision_audio = _make_deferred_global('_render_revision_audio')
_safe_relative_path = _make_deferred_global('_safe_relative_path')
_severity_rank = _make_deferred_global('_severity_rank')
build_audio_revision_summary = _make_deferred_global('build_audio_revision_summary')
candidate_integrity_ok = _make_deferred_global('candidate_integrity_ok')
closeout_integrity_ok = _make_deferred_global('closeout_integrity_ok')
issue_integrity_ok = _make_deferred_global('issue_integrity_ok')
item = _make_deferred_global('item')
session_integrity_ok = _make_deferred_global('session_integrity_ok')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioRevisionError, AudioRevisionNotFoundError, AudioRevisionStateError, _ensure_within, _object_hash, _render_revision_audio, _safe_relative_path
    global _severity_rank, build_audio_revision_summary, candidate_integrity_ok, closeout_integrity_ok, issue_integrity_ok, item, session_integrity_ok, value
    AudioRevisionError = namespace.get('AudioRevisionError', AudioRevisionError)
    AudioRevisionNotFoundError = namespace.get('AudioRevisionNotFoundError', AudioRevisionNotFoundError)
    AudioRevisionStateError = namespace.get('AudioRevisionStateError', AudioRevisionStateError)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _object_hash = namespace.get('_object_hash', _object_hash)
    _render_revision_audio = namespace.get('_render_revision_audio', _render_revision_audio)
    _safe_relative_path = namespace.get('_safe_relative_path', _safe_relative_path)
    _severity_rank = namespace.get('_severity_rank', _severity_rank)
    build_audio_revision_summary = namespace.get('build_audio_revision_summary', build_audio_revision_summary)
    candidate_integrity_ok = namespace.get('candidate_integrity_ok', candidate_integrity_ok)
    closeout_integrity_ok = namespace.get('closeout_integrity_ok', closeout_integrity_ok)
    issue_integrity_ok = namespace.get('issue_integrity_ok', issue_integrity_ok)
    item = namespace.get('item', item)
    session_integrity_ok = namespace.get('session_integrity_ok', session_integrity_ok)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


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




class AudioRevisionStoreEvidenceMixin:
    def apply_candidate(self, release_id: str, session_id: str, candidate_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        payload = payload or {}
        self._ensure_session_action_allowed(release_id, session_id)
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        if not candidate.get("selected"):
            raise AudioRevisionStateError("Candidate must be selected before apply.")
        review = _as_document(candidate.get("review"))
        if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
            raise AudioRevisionStateError("Candidate must have a manual accepted review before apply.")
        preview = _as_document(candidate.get("preview"))
        health = _as_document(candidate.get("health"))
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

    def replace_release_track_version(self, release_id: str, track_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        current = self._track(release_id, track_id)
        project_id = str(payload.get("project_id") or current.project_id)
        version_id = str(payload.get("version_id") or "").strip()
        if not version_id:
            raise AudioRevisionError("version_id is required.")
        self._replace_release_track_version(release_id, track_id, project_id, version_id, now=now)
        self._refresh_release_audio_qa(release_id, now=now)
        return self.release_store.get_release(release_id).to_dict()

    def refresh_recheck_status(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
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

    def close_session(self, release_id: str, session_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def build_closeout(self, release_id: str, session_id: str, *, now: str | None = None, force: bool = False, override_reason: str = "") -> DomainDocument:
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

    def read_closeout(self, release_id: str, session_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.session_dir(release_id, session_id) / "closeout.json"
        if not path.exists():
            if default is not None:
                return default
            raise AudioRevisionNotFoundError("Audio revision closeout is missing.")
        closeout = read_json(path)
        return sanitize_metadata(_as_document(closeout), blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})

    def archive_session(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
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
        preview = _as_document(candidate.get("preview"))
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

    def write_summary(self, release_id: str, export_dir: Path, *, now: str | None = None) -> DomainDocument:
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

    def gate(self, release_id: str, *, required: bool = False, now: str | None = None) -> DomainDocument:
        summary = build_audio_revision_summary(self, release_id, now=now)
        marker_count = summary.get("source_marker_count", 0)
        if required and not summary.get("session_count") and marker_count:
            return {**summary, "status": "failed", "hard_block": True, "message": "Audio revision closeout is required for release audio review markers."}
        if required and summary.get("status") in {"failed", "missing"}:
            return {**summary, "status": "failed", "hard_block": True, "message": "Audio revision closeout gate failed."}
        if summary.get("status") == "failed":
            return {**summary, "status": "failed" if required else "warning", "message": "Audio revision closeout has unresolved blockers."}
        return {**summary, "status": "passed" if summary.get("status") == "passed" else "warning" if summary.get("session_count") else "missing", "message": "Audio revision closeout gate passed."}

    def _issues_from_audio_markers(self, release_id: str, session_id: str, payload: DomainDocument, *, now: str) -> list[DomainDocument]:
        include_categories = {str(item) for item in payload.get("include_categories", []) if str(item).strip()} if isinstance(payload.get("include_categories"), list) else set(REVISION_CATEGORIES)
        min_severity = str(payload.get("min_severity") or "low")
        track_ids = {str(item) for item in payload.get("track_ids", []) if str(item).strip()} if isinstance(payload.get("track_ids"), list) else set()
        reviews = self.audio_review_store.list_reviews(release_id)
        issues: list[DomainDocument] = []
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
