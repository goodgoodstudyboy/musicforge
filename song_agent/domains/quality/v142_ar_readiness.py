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
_candidate_score = _make_deferred_global('_candidate_score')
_candidate_stem_health = _make_deferred_global('_candidate_stem_health')
_candidate_strategies = _make_deferred_global('_candidate_strategies')
_object_hash = _make_deferred_global('_object_hash')
_render_revision_audio = _make_deferred_global('_render_revision_audio')
_renderer_summary = _make_deferred_global('_renderer_summary')
_severity_rank = _make_deferred_global('_severity_rank')
_validate_candidate_id = _make_deferred_global('_validate_candidate_id')
_validate_issue_id = _make_deferred_global('_validate_issue_id')
_validate_session_id = _make_deferred_global('_validate_session_id')
candidate_integrity_ok = _make_deferred_global('candidate_integrity_ok')
issue_integrity_ok = _make_deferred_global('issue_integrity_ok')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioRevisionError, AudioRevisionNotFoundError, AudioRevisionStateError, _candidate_score, _candidate_stem_health, _candidate_strategies, _object_hash
    global _render_revision_audio, _renderer_summary, _severity_rank, _validate_candidate_id, _validate_issue_id, _validate_session_id, candidate_integrity_ok, issue_integrity_ok
    global item, key, value
    AudioRevisionError = namespace.get('AudioRevisionError', AudioRevisionError)
    AudioRevisionNotFoundError = namespace.get('AudioRevisionNotFoundError', AudioRevisionNotFoundError)
    AudioRevisionStateError = namespace.get('AudioRevisionStateError', AudioRevisionStateError)
    _candidate_score = namespace.get('_candidate_score', _candidate_score)
    _candidate_stem_health = namespace.get('_candidate_stem_health', _candidate_stem_health)
    _candidate_strategies = namespace.get('_candidate_strategies', _candidate_strategies)
    _object_hash = namespace.get('_object_hash', _object_hash)
    _render_revision_audio = namespace.get('_render_revision_audio', _render_revision_audio)
    _renderer_summary = namespace.get('_renderer_summary', _renderer_summary)
    _severity_rank = namespace.get('_severity_rank', _severity_rank)
    _validate_candidate_id = namespace.get('_validate_candidate_id', _validate_candidate_id)
    _validate_issue_id = namespace.get('_validate_issue_id', _validate_issue_id)
    _validate_session_id = namespace.get('_validate_session_id', _validate_session_id)
    candidate_integrity_ok = namespace.get('candidate_integrity_ok', candidate_integrity_ok)
    issue_integrity_ok = namespace.get('issue_integrity_ok', issue_integrity_ok)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
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




class AudioRevisionStoreReadinessMixin:
    def root_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-revisions"

    def session_dir(self, release_id: str, session_id: str) -> Path:
        return self.root_dir(release_id) / _validate_session_id(session_id)

    def issue_path(self, release_id: str, session_id: str, issue_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "issues" / f"{_validate_issue_id(issue_id)}.json"

    def candidate_dir(self, release_id: str, session_id: str, candidate_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "candidates" / _validate_candidate_id(candidate_id)

    def list_sessions(self, release_id: str, *, include_archived: bool = False) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        root = self.root_dir(release_id)
        if not root.exists():
            return []
        sessions: list[DomainDocument] = []
        for path in sorted(root.glob("ars-*/session.json")):
            try:
                session = self.read_session(release_id, path.parent.name)
            except Exception:
                continue
            if session.get("status") == "archived" and not include_archived:
                continue
            sessions.append(session)
        return sorted(sessions, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def create_session(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def read_session(self, release_id: str, session_id: str) -> DomainDocument:
        path = self.session_dir(release_id, session_id) / "session.json"
        if not path.exists():
            raise AudioRevisionNotFoundError(session_id)
        session = read_json(path)
        return self._with_session_current_state(_as_document(session))

    def list_issues(self, release_id: str, session_id: str) -> list[DomainDocument]:
        self.read_session(release_id, session_id)
        issues = []
        for issue in self._list_raw_issues(release_id, session_id):
            try:
                issues.append(self._with_issue_current_state(issue))
            except Exception:
                continue
        return issues

    def _list_raw_issues(self, release_id: str, session_id: str) -> list[DomainDocument]:
        issues_dir = self.session_dir(release_id, session_id) / "issues"
        issues: list[object] = []
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

    def read_issue(self, release_id: str, session_id: str, issue_id: str) -> DomainDocument:
        path = self.issue_path(release_id, session_id, issue_id)
        if not path.exists():
            raise AudioRevisionNotFoundError(issue_id)
        issue = read_json(path)
        return self._with_issue_current_state(_as_document(issue))

    def create_issue(self, release_id: str, session_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
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
                "mapped": _as_document(payload.get("mapped")),
                "time_seconds": payload.get("time_seconds"),
            },
            now=now,
        )
        write_json(self.issue_path(release_id, session_id, issue_id), issue)
        self._refresh_session_counts(release_id, session_id, now=now)
        self._write_issue_index(release_id, session_id)
        self._append_event(release_id, session_id, "audio_revision_issue_created", {"issue_id": issue_id}, now)
        return self.read_issue(release_id, session_id, issue_id)

    def waive_issue(self, release_id: str, session_id: str, issue_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
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

    def reopen_issue(self, release_id: str, session_id: str, issue_id: str, *, now: str | None = None) -> DomainDocument:
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

    def generate_candidates(self, release_id: str, session_id: str, issue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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
            review: object = {"status": "pending", "review_mode": None, "reviewer": None, "rating": None, "notes": "", "markers": []}
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

    def list_candidates(self, release_id: str, session_id: str, *, issue_id: str | None = None) -> list[DomainDocument]:
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

    def read_candidate(self, release_id: str, session_id: str, candidate_id: str) -> DomainDocument:
        path = self.candidate_dir(release_id, session_id, candidate_id) / "candidate.json"
        if not path.exists():
            raise AudioRevisionNotFoundError(candidate_id)
        candidate = read_json(path)
        return self._with_candidate_current_state(_as_document(candidate))

    def review_candidate(self, release_id: str, session_id: str, candidate_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        preview = _as_document(candidate.get("preview"))
        health = _as_document(candidate.get("health"))
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
            "markers": sanitize_metadata(_as_list(payload.get("markers")), blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})[:64],
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

    def select_candidate(self, release_id: str, session_id: str, candidate_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_session_action_allowed(release_id, session_id)
        candidate = self.read_candidate(release_id, session_id, candidate_id)
        if candidate.get("stale") or not candidate_integrity_ok(candidate):
            raise AudioRevisionStateError("Audio revision candidate is stale or tampered.")
        review = _as_document(candidate.get("review"))
        if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
            raise AudioRevisionStateError("Only manually accepted and playback-confirmed candidates can be selected.")
        preview = _as_document(candidate.get("preview"))
        health = _as_document(candidate.get("health"))
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
