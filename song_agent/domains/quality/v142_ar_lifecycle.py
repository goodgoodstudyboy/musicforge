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
_safe_relative_path = _make_deferred_global('_safe_relative_path')
_stale_summary = _make_deferred_global('_stale_summary')
_validate_issue_id = _make_deferred_global('_validate_issue_id')
candidate_integrity_ok = _make_deferred_global('candidate_integrity_ok')
ch = _make_deferred_global('ch')
issue_integrity_ok = _make_deferred_global('issue_integrity_ok')
item = _make_deferred_global('item')
session_integrity_ok = _make_deferred_global('session_integrity_ok')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioRevisionError, AudioRevisionNotFoundError, AudioRevisionStateError, _ensure_within, _object_hash, _safe_relative_path, _stale_summary
    global _validate_issue_id, candidate_integrity_ok, ch, issue_integrity_ok, item, session_integrity_ok, value
    AudioRevisionError = namespace.get('AudioRevisionError', AudioRevisionError)
    AudioRevisionNotFoundError = namespace.get('AudioRevisionNotFoundError', AudioRevisionNotFoundError)
    AudioRevisionStateError = namespace.get('AudioRevisionStateError', AudioRevisionStateError)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _object_hash = namespace.get('_object_hash', _object_hash)
    _safe_relative_path = namespace.get('_safe_relative_path', _safe_relative_path)
    _stale_summary = namespace.get('_stale_summary', _stale_summary)
    _validate_issue_id = namespace.get('_validate_issue_id', _validate_issue_id)
    candidate_integrity_ok = namespace.get('candidate_integrity_ok', candidate_integrity_ok)
    ch = namespace.get('ch', ch)
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




class AudioRevisionStoreLifecycleMixin:
    def _build_issue(self, release_id: str, session_id: str, issue_id: str, *, track: object, review: DomainDocument, marker: DomainDocument, now: str) -> DomainDocument:
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

    def _with_session_current_state(self, session: DomainDocument) -> DomainDocument:
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

    def _with_issue_current_state(self, issue: DomainDocument) -> DomainDocument:
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

    def _with_candidate_current_state(self, candidate: DomainDocument) -> DomainDocument:
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

    def _candidate_stale_reasons(self, candidate: DomainDocument, *, context: DomainDocument) -> list[str]:
        reasons: list[str] = []
        patch_payload = _as_document(candidate.get("patch"))
        try:
            patch = MixPatch.from_dict(patch_payload)
            if not mix_patch_integrity_ok(patch):
                reasons.append("patch_integrity")
        except Exception:
            reasons.append("patch_invalid")
        source = _as_document(candidate.get("source"))
        current_state = MixControlStore(self.project_store.project_dir(str(candidate.get("project_id") or ""))).read_state(str(candidate.get("version_id") or ""))
        if source.get("parent_song_plan_hash") != song_plan_hash(context["plan"]):
            reasons.append("parent_song_plan_hash")
        if source.get("parent_midi_hash") != file_sha256(context["midi_path"]):
            reasons.append("parent_midi_hash")
        if source.get("mix_state_hash") != mix_state_hash(current_state):
            reasons.append("mix_state_hash")
        if candidate.get("source_hash") != stable_hash(source):
            reasons.append("source_hash")
        preview = _as_document(candidate.get("preview"))
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

    def _candidate_source(self, release_id: str, issue: DomainDocument, mix_state: DomainDocument, context: DomainDocument, *, review_id: str, marker_id: str) -> DomainDocument:
        audio_context = self.audio_review_store.track_audio_context(release_id, str(issue.get("track_id") or ""), require_reviewable=False)
        evidence = _as_document(audio_context.get("audio_evidence"))
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

    def _session_source(self, release_id: str) -> DomainDocument:
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

    def _version_context(self, project_id: str, version_id: str) -> DomainDocument:
        document, version, job, plan, midi_path = _project_version_context(self.project_store, self.job_store, project_id, version_id)
        state = MixControlStore(self.project_store.project_dir(project_id)).get_or_create_state(project_id=project_id, version_id=version_id, plan=plan, midi_path=midi_path, now=now_iso())
        stale = mix_state_stale_reasons(state, plan=plan, midi_path=midi_path)
        if stale:
            raise AudioRevisionStateError("Mix state is stale: " + ", ".join(stale))
        return {"document": document, "version": version, "job": job, "plan": plan, "midi_path": midi_path, "mix_state": state}

    def _track(self, release_id: str, track_id: str) -> object:
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

    def _refresh_release_audio_qa(self, release_id: str, *, now: str) -> DomainDocument:
        release = self.release_store.get_release(release_id)
        report = build_release_audio_qa_report(
            release=release,
            release_store=self.release_store,
            project_store=self.project_store,
            require_audio=True,
            now=now,
        )
        return write_release_audio_qa(self.release_store, release_id, report)

    def _refresh_project_delivery_qa(self, project_id: str, *, now: str) -> DomainDocument:
        project_dir = self.project_store.project_dir(project_id)
        manifest = read_json(final_export_dir(project_dir) / "manifest.json")
        report = build_delivery_qa_report(
            project_id=project_id,
            project_document=self.project_store.get_project(project_id),
            project_dir=project_dir,
            project_export=self.project_store.project_export_snapshot(project_id),
            final_export_manifest=_as_document(manifest),
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
    ) -> object:
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

    def _refresh_session_counts(self, release_id: str, session_id: str, *, status: str | None = None, now: str | None = None) -> DomainDocument:
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

    def _refresh_session_source(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
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

    def _append_event(self, release_id: str, session_id: str, event_type: str, payload: DomainDocument, now: str) -> None:
        root = self.session_dir(release_id, session_id)
        root.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=BLOCKED_RELEASE_KEYS - {"path"})
        with (root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)
