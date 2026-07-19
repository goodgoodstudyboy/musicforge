# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_float as _as_float, as_list as _as_list

import hashlib as hashlib
import io as io
import math as math
import shutil as shutil
import threading as threading
import wave as wave
from pathlib import Path as Path
from typing import Any as Any, Protocol as Protocol

from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_integrity_ok as audio_health_integrity_ok, audio_health_summary as audio_health_summary
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.quality.mastering_profiles import MasteringProfile as MasteringProfile, MasteringProfileError as MasteringProfileError, MasteringProfileStore as MasteringProfileStore, mastering_profile_hash as mastering_profile_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseDocument as ReleaseDocument, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash


MASTERING_SCHEMA_VERSION = 1
MASTERING_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash"}
MASTERING_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
MASTERING_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


class MasteringQAError(ValueError):
    pass


class MasteringNotFoundError(MasteringQAError):
    pass


class MasteringStateError(MasteringQAError):
    pass


class MasteringStore:
    def __init__(self, release_store: ReleaseStore, project_store: ProjectStore | None = None, profile_store: MasteringProfileStore | None = None) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.profile_store = profile_store or MasteringProfileStore(self.release_store.root.parent / "mastering-profiles")
        self.lock = threading.RLock()

    def root_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "mastering"

    def analysis_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "analysis.json"

    def plan_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "plan.json"

    def summary_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "summary.json"

    def candidate_dir(self, release_id: str, candidate_id: str) -> Path:
        return self.root_dir(release_id) / "candidates" / _validate_candidate_id(candidate_id)

    def selected_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "selected-candidate.json"

    def get_summary(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        self.release_store.get_release(release_id)
        analysis = self.read_analysis(release_id, default={})
        plan = self.read_plan(release_id, default={})
        candidates = self.list_candidates(release_id)
        selected = self.read_selected_candidate(release_id, default={})
        summary = self._build_summary(release_id, analysis=analysis, plan=plan, candidates=candidates, selected=selected, now=now)
        write_json(self.summary_path(release_id), summary)
        return summary

    def analyze(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        profile = self.profile_store.get_profile(str(payload.get("profile_id") or "streaming_balanced"))
        release = self.release_store.get_release(release_id)
        with self.lock:
            analysis = build_mastering_analysis(release=release, release_store=self.release_store, project_store=self.project_store, profile=profile, now=now)
            self.root_dir(release_id).mkdir(parents=True, exist_ok=True)
            write_json(self.analysis_path(release_id), analysis)
            self.get_summary(release_id, now=now)
            return analysis

    def read_analysis(self, release_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.analysis_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError("Mastering analysis does not exist.")
        data = read_json(path)
        return self._with_analysis_current_state(_as_document(data))

    def build_plan(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        analysis = self.read_analysis(release_id)
        if analysis.get("stale") or not mastering_analysis_integrity_ok(analysis):
            raise MasteringStateError("Mastering analysis is stale or tampered. Refresh analysis before planning.")
        with self.lock:
            plan = build_mastering_plan(analysis, payload, now=now)
            write_json(self.plan_path(release_id), plan)
            self.get_summary(release_id, now=now)
            return plan

    def read_plan(self, release_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.plan_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError("Mastering plan does not exist.")
        data = read_json(path)
        return self._with_plan_current_state(release_id, _as_document(data))

    def render_candidate(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        analysis = self.read_analysis(release_id)
        plan = self.read_plan(release_id)
        if analysis.get("stale") or not mastering_analysis_integrity_ok(analysis):
            raise MasteringStateError("Mastering analysis is stale or tampered.")
        if plan.get("stale") or not mastering_plan_integrity_ok(plan):
            raise MasteringStateError("Mastering plan is stale or tampered.")
        profile = self.profile_store.get_profile(str(analysis.get("profile_id") or "streaming_balanced"))
        with self.lock:
            candidate_id = self._reserve_candidate_id(release_id)
            candidate_dir = self.candidate_dir(release_id, candidate_id)
            candidate_dir.mkdir(parents=True, exist_ok=False)
            candidate = build_mastered_candidate(
                candidate_id=candidate_id,
                release_id=release_id,
                analysis=analysis,
                plan=plan,
                profile=profile,
                source_wavs={
                    track.track_id: final_export_dir(self.project_store.project_dir(track.project_id)) / "song.wav"
                    for track in self.release_store.get_release(release_id).tracks
                },
                candidate_dir=candidate_dir,
                payload=payload,
                now=now,
            )
            write_json(candidate_dir / "candidate.json", candidate)
            self.get_summary(release_id, now=now)
            return self.read_candidate(release_id, candidate_id)

    def list_candidates(self, release_id: str) -> list[DomainDocument]:
        root = self.root_dir(release_id) / "candidates"
        if not root.exists():
            return []
        candidates: list[ImplementationDocument] = []
        for path in sorted(root.glob("mcand-*/candidate.json")):
            try:
                candidates.append(self.read_candidate(release_id, path.parent.name))
            except Exception:
                continue
        return sorted(candidates, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def read_candidate(self, release_id: str, candidate_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.candidate_dir(release_id, candidate_id) / "candidate.json"
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError(candidate_id)
        data = read_json(path)
        return self._with_candidate_current_state(release_id, _as_document(data))

    def read_selected_candidate(self, release_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.selected_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError("Selected mastered candidate does not exist.")
        data = read_json(path)
        candidate_id = str(data.get("candidate_id") or "")
        if candidate_id:
            return self.read_candidate(release_id, candidate_id)
        return self._with_candidate_current_state(release_id, _as_document(data))

    def candidate_audio_path(self, release_id: str, candidate_id: str, track_id: str) -> Path:
        candidate = self.read_candidate(release_id, candidate_id)
        if candidate.get("stale") or not mastering_candidate_integrity_ok(candidate):
            raise MasteringStateError("Mastered candidate is stale or tampered.")
        root = self.candidate_dir(release_id, candidate_id).resolve()
        path = (root / "tracks" / _validate_track_id(track_id) / "song.wav").resolve()
        _ensure_within(root, path)
        if not path.exists() or not path.is_file() or path.is_symlink():
            raise MasteringNotFoundError("Mastered candidate WAV is missing.")
        return path

    def review_candidate(self, release_id: str, candidate_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        candidate = self.read_candidate(release_id, candidate_id)
        if candidate.get("stale") or not mastering_candidate_integrity_ok(candidate):
            raise MasteringStateError("Mastered candidate is stale or tampered.")
        review_mode = str(payload.get("review_mode") or "manual")
        status = str(payload.get("status") or "accepted")
        playback_confirmed = bool(payload.get("playback_confirmed", False))
        rating = int(payload.get("rating", 0) or 0)
        if review_mode != "manual":
            raise MasteringStateError("Mastered candidate selection requires a manual review.")
        if status == "accepted" and (not playback_confirmed or rating < 3):
            raise MasteringStateError("Accepted mastering review requires playback_confirmed=true and rating >= 3.")
        updated = {key: value for key, value in candidate.items() if key not in MASTERING_INTEGRITY_EXCLUDE}
        updated["status"] = "reviewed" if status != "rejected" else "rejected"
        updated["review"] = {
            "status": status,
            "review_mode": review_mode,
            "rating": rating,
            "playback_confirmed": playback_confirmed,
            "reviewed_by": sanitize_sensitive_text(str(payload.get("reviewed_by") or payload.get("reviewer") or "reviewer"))[:120],
            "reviewed_at": now,
            "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:2000],
        }
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, MASTERING_INTEGRITY_EXCLUDE)
        write_json(self.candidate_dir(release_id, candidate_id) / "candidate.json", sanitize_metadata(updated, blocked_keys=MASTERING_BLOCKED_KEYS))
        self.get_summary(release_id, now=now)
        return self.read_candidate(release_id, candidate_id)

    def select_candidate(self, release_id: str, candidate_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        candidate = self.read_candidate(release_id, candidate_id)
        if candidate.get("stale") or not mastering_candidate_integrity_ok(candidate):
            raise MasteringStateError("Mastered candidate is stale or tampered.")
        review = _as_document(candidate.get("review"))
        after = _as_document(candidate.get("after_analysis"))
        if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
            raise MasteringStateError("Mastered candidate must have an accepted manual review before selection.")
        if after.get("status") not in {"passed", "warning"}:
            raise MasteringStateError("Mastered candidate audio analysis does not allow selection.")
        for other in self.list_candidates(release_id):
            if other.get("candidate_id") == candidate_id:
                continue
            other_path = self.candidate_dir(release_id, str(other.get("candidate_id") or "")) / "candidate.json"
            if not other_path.exists():
                continue
            raw = read_json(other_path)
            if not isinstance(raw, dict):
                continue
            raw["selected"] = False
            raw["updated_at"] = now
            raw["integrity_hash"] = _object_hash(raw, MASTERING_INTEGRITY_EXCLUDE)
            write_json(other_path, sanitize_metadata(raw, blocked_keys=MASTERING_BLOCKED_KEYS))
        updated = {key: value for key, value in candidate.items() if key not in MASTERING_INTEGRITY_EXCLUDE}
        updated["status"] = "selected"
        updated["selected"] = True
        updated["selected_at"] = now
        updated["selected_by"] = sanitize_sensitive_text(str(payload.get("selected_by") or "reviewer"))[:120]
        updated["updated_at"] = now
        updated["integrity_hash"] = _object_hash(updated, MASTERING_INTEGRITY_EXCLUDE)
        write_json(self.candidate_dir(release_id, candidate_id) / "candidate.json", sanitize_metadata(updated, blocked_keys=MASTERING_BLOCKED_KEYS))
        write_json(self.selected_path(release_id), sanitize_metadata(updated, blocked_keys=MASTERING_BLOCKED_KEYS))
        self.get_summary(release_id, now=now)
        return self.read_candidate(release_id, candidate_id)

    def refresh(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        profile_id = str(payload.get("profile_id") or "")
        if not profile_id:
            existing = self.read_analysis(release_id, default={})
            profile_id = str(existing.get("profile_id") or "streaming_balanced")
        analysis = self.analyze(release_id, {"profile_id": profile_id}, now=now)
        plan = self.build_plan(release_id, payload, now=now)
        return {"analysis": analysis, "plan": plan, "summary": self.get_summary(release_id, now=now)}

    def reset(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        self._ensure_release_mutable(release_id)
        root = self.root_dir(release_id)
        if root.exists():
            shutil.rmtree(root)
        self.release_store.append_event(release_id, "release_mastering_reset", {"reason": sanitize_sensitive_text(str(payload.get("reason") or ""))[:240]})
        return {"status": "reset", "release_id": release_id}

    def gate(self, release_id: str, *, required: bool, profile_id: str | None = None, force: bool = False) -> DomainDocument:
        if not required:
            summary = self.get_summary(release_id)
            return {**summary, "require_mastering_qa": False, "status": "passed" if summary.get("status") in {"passed", "missing"} else summary.get("status")}
        try:
            analysis = self.read_analysis(release_id)
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": f"Mastering analysis is missing: {sanitize_sensitive_text(str(exc))}"}
        if profile_id and str(analysis.get("profile_id") or "") != profile_id:
            return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": "Mastering analysis profile does not match the required profile.", "profile_id": analysis.get("profile_id"), "required_profile_id": profile_id}
        if analysis.get("stale") or not mastering_analysis_integrity_ok(analysis):
            return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": "Mastering analysis is stale or tampered.", "stale_reasons": analysis.get("stale_reasons", [])}
        selected = self.read_selected_candidate(release_id, default={})
        if not selected:
            return {**mastering_analysis_summary(analysis), "require_mastering_qa": True, "status": "failed", "hard_block": True, "message": "Selected mastered candidate is required before signoff."}
        if selected.get("stale") or not mastering_candidate_integrity_ok(selected):
            return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": "Selected mastered candidate is stale or tampered.", "candidate_id": selected.get("candidate_id"), "stale_reasons": selected.get("stale_reasons", [])}
        review = _as_document(selected.get("review"))
        after = _as_document(selected.get("after_analysis"))
        status = str(after.get("status") or "")
        if review.get("status") != "accepted" or review.get("review_mode") != "manual" or not review.get("playback_confirmed"):
            return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": "Selected mastered candidate is missing accepted manual review.", "candidate_id": selected.get("candidate_id")}
        if status == "failed":
            return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": "Selected mastered candidate failed Mastering QA.", "candidate_id": selected.get("candidate_id")}
        if status == "warning":
            profile = self.profile_store.get_profile(str(selected.get("profile_id") or analysis.get("profile_id") or "streaming_balanced"))
            if not (profile.allow_warning_signoff or force):
                return {"status": "failed", "hard_block": True, "require_mastering_qa": True, "message": "Selected mastered candidate has Mastering QA warnings.", "candidate_id": selected.get("candidate_id")}
        summary = self.get_summary(release_id)
        return {**summary, "require_mastering_qa": True, "status": "passed", "message": "Mastering QA gate passed."}

    def _build_summary(
        self,
        release_id: str,
        *,
        analysis: ImplementationDocument,
        plan: ImplementationDocument,
        candidates: list[ImplementationDocument],
        selected: ImplementationDocument,
        now: str | None = None,
    ) -> ImplementationDocument:
        now = now or now_iso()
        status = "missing"
        blockers: list[str] = []
        warnings: list[str] = []
        if analysis:
            status = str(analysis.get("status") or "failed")
            if analysis.get("stale"):
                status = "stale"
                blockers.append("analysis_stale")
            if not mastering_analysis_integrity_ok(analysis):
                status = "failed"
                blockers.append("analysis_integrity")
        if selected:
            if selected.get("stale"):
                status = "stale"
                blockers.append("selected_candidate_stale")
            elif not mastering_candidate_integrity_ok(selected):
                status = "failed"
                blockers.append("selected_candidate_integrity")
            else:
                after = _as_document(selected.get("after_analysis"))
                status = str(after.get("status") or status or "failed")
        elif analysis:
            warnings.append("selected_candidate_missing")
        summary = {
            "schema_version": MASTERING_SCHEMA_VERSION,
            "release_id": release_id,
            "generated_at": now,
            "status": status,
            "profile_id": analysis.get("profile_id") if analysis else None,
            "analysis_hash": analysis.get("integrity_hash") if analysis else None,
            "analysis_source_hash": analysis.get("source_hash") if analysis else None,
            "plan_hash": plan.get("integrity_hash") if plan else None,
            "selected_candidate_id": selected.get("candidate_id") if selected else None,
            "selected_candidate_hash": selected.get("integrity_hash") if selected else None,
            "candidate_count": len(candidates),
            "track_count": int((analysis.get("summary") or {}).get("track_count") or 0) if analysis else 0,
            "average_loudness_proxy_db": (selected.get("after_analysis") or analysis).get("summary", {}).get("average_loudness_proxy_db") if (selected or analysis) else None,
            "max_track_loudness_delta_db": (selected.get("after_analysis") or analysis).get("summary", {}).get("max_track_loudness_delta_db") if (selected or analysis) else None,
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set([*warnings, *[str(item) for item in (analysis.get("warnings", []) if analysis else [])]])),
        }
        summary["integrity_hash"] = mastering_summary_hash(summary)
        return sanitize_metadata(summary, blocked_keys=MASTERING_BLOCKED_KEYS)

    def _with_analysis_current_state(self, analysis: ImplementationDocument) -> ImplementationDocument:
        clean = sanitize_metadata(analysis, blocked_keys=MASTERING_BLOCKED_KEYS)
        try:
            profile = self.profile_store.get_profile(str(clean.get("profile_id") or "streaming_balanced"))
            release = self.release_store.get_release(str(clean.get("release_id") or ""))
            current_source = mastering_source_state(release=release, release_store=self.release_store, project_store=self.project_store, profile=profile)
            current_hash = stable_hash(current_source)
        except Exception:
            current_hash = ""
        reasons: list[str] = []
        if current_hash and clean.get("source_hash") != current_hash:
            reasons.append("source_hash")
        if not mastering_analysis_integrity_ok(clean):
            reasons.append("integrity")
        clean["current_source_hash"] = current_hash
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = any(reason != "integrity" for reason in reasons)
        return clean

    def _with_plan_current_state(self, release_id: str, plan: ImplementationDocument) -> ImplementationDocument:
        clean = sanitize_metadata(plan, blocked_keys=MASTERING_BLOCKED_KEYS)
        reasons: list[str] = []
        analysis = self.read_analysis(release_id, default={})
        if analysis and clean.get("analysis_hash") != analysis.get("integrity_hash"):
            reasons.append("analysis_hash")
        if not mastering_plan_integrity_ok(clean):
            reasons.append("integrity")
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = any(reason != "integrity" for reason in reasons)
        return clean

    def _with_candidate_current_state(self, release_id: str, candidate: ImplementationDocument) -> ImplementationDocument:
        clean = sanitize_metadata(candidate, blocked_keys=MASTERING_BLOCKED_KEYS)
        reasons: list[str] = []
        analysis = self.read_analysis(release_id, default={})
        plan = self.read_plan(release_id, default={})
        if analysis and clean.get("analysis_hash") != analysis.get("integrity_hash"):
            reasons.append("analysis_hash")
        if analysis and analysis.get("stale"):
            reasons.append("analysis_stale")
        if plan and clean.get("plan_hash") != plan.get("integrity_hash"):
            reasons.append("plan_hash")
        if plan and plan.get("stale"):
            reasons.append("plan_stale")
        for row in clean.get("tracks", []) if isinstance(clean.get("tracks"), list) else []:
            if not isinstance(row, dict):
                continue
            rel = str(row.get("candidate_wav") or "")
            path = self.candidate_dir(release_id, str(clean.get("candidate_id") or "")) / rel
            if not path.exists() or row.get("candidate_wav_sha256") != file_sha256(path):
                reasons.append(f"candidate_wav:{row.get('track_id')}")
        if not mastering_candidate_integrity_ok(clean):
            reasons.append("integrity")
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = any(reason != "integrity" for reason in reasons)
        return clean

    def _ensure_release_mutable(self, release_id: str) -> None:
        document = self.release_store.get_release(release_id)
        if document.status == "archived":
            raise ReleaseStateError("Archived releases are read-only.")
        if document.status == "signed" or self.release_store.read_signoff(release_id, default={}):
            raise ReleaseStateError("Signed releases cannot mutate Mastering QA. Reset signoff before changing mastering evidence.")

    def _reserve_candidate_id(self, release_id: str) -> str:
        root = self.root_dir(release_id) / "candidates"
        root.mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            candidate = f"mcand-{index:06d}"
            path = root / candidate
            try:
                path.mkdir(parents=True, exist_ok=False)
                path.rmdir()
                return candidate
            except FileExistsError:
                index += 1


class _ProjectPathStore(Protocol):
    def project_dir(self, project_id: str) -> Path: ...


from song_agent.domains.quality import v142_mq_readiness as _v142_mq_readiness
from song_agent.domains.quality.v142_mq_readiness import build_mastering_analysis as build_mastering_analysis, mastering_source_state as mastering_source_state, build_mastering_plan as build_mastering_plan, build_mastered_candidate as build_mastered_candidate, apply_mastering_actions as apply_mastering_actions, mastering_analysis_summary as mastering_analysis_summary, selected_mastering_track_sources as selected_mastering_track_sources, export_mastering as export_mastering, mastering_summary_hash as mastering_summary_hash, mastering_analysis_integrity_ok as mastering_analysis_integrity_ok, mastering_plan_integrity_ok as mastering_plan_integrity_ok, mastering_candidate_integrity_ok as mastering_candidate_integrity_ok, file_sha256 as file_sha256
from song_agent.domains.quality import v142_mq_evidence as _v142_mq_evidence
from song_agent.domains.quality.v142_mq_evidence import _analyze_mastering_track as _analyze_mastering_track, _profile_limits as _profile_limits, _release_stub_from_analysis as _release_stub_from_analysis, _NullReleaseStore as _NullReleaseStore, _NullProjectStore as _NullProjectStore, _object_hash as _object_hash, _file_state as _file_state, _json_file_state as _json_file_state, _file_record as _file_record, _validate_candidate_id as _validate_candidate_id, _validate_track_id as _validate_track_id, _ensure_within as _ensure_within, _check as _check, _amplitude_db as _amplitude_db, _short_hash as _short_hash

_v142_mq_readiness.bind_globals(globals())
_v142_mq_evidence.bind_globals(globals())
