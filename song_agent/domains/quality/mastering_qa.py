from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_float, _as_list

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

    def get_summary(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        self.release_store.get_release(release_id)
        analysis = self.read_analysis(release_id, default={})
        plan = self.read_plan(release_id, default={})
        candidates = self.list_candidates(release_id)
        selected = self.read_selected_candidate(release_id, default={})
        summary = self._build_summary(release_id, analysis=analysis, plan=plan, candidates=candidates, selected=selected, now=now)
        write_json(self.summary_path(release_id), summary)
        return summary

    def analyze(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def read_analysis(self, release_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.analysis_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError("Mastering analysis does not exist.")
        data = read_json(path)
        return self._with_analysis_current_state(_as_document(data))

    def build_plan(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def read_plan(self, release_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.plan_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError("Mastering plan does not exist.")
        data = read_json(path)
        return self._with_plan_current_state(release_id, _as_document(data))

    def render_candidate(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def list_candidates(self, release_id: str) -> list[dict[str, Any]]:
        root = self.root_dir(release_id) / "candidates"
        if not root.exists():
            return []
        candidates: list[dict[str, Any]] = []
        for path in sorted(root.glob("mcand-*/candidate.json")):
            try:
                candidates.append(self.read_candidate(release_id, path.parent.name))
            except Exception:
                continue
        return sorted(candidates, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def read_candidate(self, release_id: str, candidate_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.candidate_dir(release_id, candidate_id) / "candidate.json"
        if not path.exists():
            if default is not None:
                return default
            raise MasteringNotFoundError(candidate_id)
        data = read_json(path)
        return self._with_candidate_current_state(release_id, _as_document(data))

    def read_selected_candidate(self, release_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def review_candidate(self, release_id: str, candidate_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
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

    def select_candidate(self, release_id: str, candidate_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def refresh(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def reset(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        self._ensure_release_mutable(release_id)
        root = self.root_dir(release_id)
        if root.exists():
            shutil.rmtree(root)
        self.release_store.append_event(release_id, "release_mastering_reset", {"reason": sanitize_sensitive_text(str(payload.get("reason") or ""))[:240]})
        return {"status": "reset", "release_id": release_id}

    def gate(self, release_id: str, *, required: bool, profile_id: str | None = None, force: bool = False) -> dict[str, Any]:
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


def build_mastering_analysis(
    *,
    release: ReleaseDocument,
    release_store: object,
    project_store: _ProjectPathStore,
    profile: MasteringProfile,
    now: str | None = None,
    source_override: dict[str, Any] | None = None,
    wav_overrides: dict[str, Path] | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    wav_overrides = wav_overrides or {}
    source = source_override or mastering_source_state(release=release, release_store=release_store, project_store=project_store, profile=profile)
    track_reports: list[dict[str, Any]] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        wav_path = wav_overrides.get(track.track_id) or final_export_dir(project_store.project_dir(track.project_id)) / "song.wav"
        track_reports.append(_analyze_mastering_track(track=track.to_dict(), wav_path=wav_path, profile=profile, now=now))
    loudness_values = [float(item.get("metrics", {}).get("loudness_proxy_db") or -120.0) for item in track_reports if item.get("status") != "missing"]
    max_delta = round(max(loudness_values) - min(loudness_values), 3) if len(loudness_values) >= 2 else 0.0
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    failures: list[str] = []
    if max_delta > profile.max_track_loudness_delta_db:
        checks.append(_check("album_loudness_consistency", "failed", f"Track loudness delta {max_delta:.2f} dB exceeds {profile.max_track_loudness_delta_db:.2f} dB."))
        failures.append("album_loudness_delta")
    else:
        checks.append(_check("album_loudness_consistency", "passed", "Track loudness delta is within profile tolerance."))
    for item in track_reports:
        failures.extend(f"{item.get('track_id')}:{failure}" for failure in item.get("failures", []) if str(failure))
        warnings.extend(f"{item.get('track_id')}:{warning}" for warning in item.get("warnings", []) if str(warning))
    status = "failed" if failures else "warning" if warnings else "passed"
    analysis = {
        "schema_version": MASTERING_SCHEMA_VERSION,
        "analysis_id": f"man-{_short_hash(release.release_id + now)}",
        "release_id": release.release_id,
        "profile_id": profile.profile_id,
        "profile_hash": mastering_profile_hash(profile),
        "profile": _profile_limits(profile),
        "generated_at": now,
        "status": status,
        "source": source,
        "source_hash": stable_hash(source),
        "tracks": track_reports,
        "checks": checks,
        "warnings": sorted(set(warnings)),
        "failures": sorted(set(failures)),
        "summary": {
            "track_count": len(track_reports),
            "average_loudness_proxy_db": round(sum(loudness_values) / len(loudness_values), 3) if loudness_values else None,
            "max_track_loudness_delta_db": max_delta,
            "failed_track_count": len([item for item in track_reports if item.get("status") == "failed"]),
            "warning_track_count": len([item for item in track_reports if item.get("status") == "warning"]),
        },
    }
    analysis["integrity_hash"] = _object_hash(analysis, MASTERING_INTEGRITY_EXCLUDE)
    return sanitize_metadata(analysis, blocked_keys=MASTERING_BLOCKED_KEYS)


def mastering_source_state(*, release: ReleaseDocument, release_store: object, project_store: _ProjectPathStore, profile: MasteringProfile) -> dict[str, Any]:
    tracks: list[dict[str, Any]] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        project_dir = project_store.project_dir(track.project_id)
        export_dir = final_export_dir(project_dir)
        wav_path = export_dir / "song.wav"
        audio_artifact_path = export_dir / "audio-artifact.json"
        tracks.append(
            {
                "track_id": track.track_id,
                "track_number": track.track_number,
                "disc_number": track.disc_number,
                "project_id": track.project_id,
                "version_id": track.version_id,
                "final_export_hash": track.final_export_hash,
                "song_wav": _file_state(wav_path),
                "audio_artifact": _json_file_state(audio_artifact_path),
            }
        )
    return sanitize_metadata(
        {
            "release_id": release.release_id,
            "release_name": release.name,
            "release_type": release.release_type,
            "track_count": len(tracks),
            "tracks": tracks,
            "profile": {"profile_id": profile.profile_id, "profile_hash": mastering_profile_hash(profile)},
        },
        blocked_keys=MASTERING_BLOCKED_KEYS,
    )


def build_mastering_plan(analysis: dict[str, Any], payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
    payload = payload or {}
    now = now or now_iso()
    profile_id = str(analysis.get("profile_id") or "streaming_balanced")
    profile_limits = _as_document(analysis.get("profile"))
    target_loudness = _as_float(profile_limits.get("target_loudness_proxy_db") if profile_limits.get("target_loudness_proxy_db") is not None else payload.get("target_loudness_proxy_db") or -15.0)
    actions: list[dict[str, Any]] = []
    for track in analysis.get("tracks", []) if isinstance(analysis.get("tracks"), list) else []:
        if not isinstance(track, dict):
            continue
        metrics = _as_document(track.get("metrics"))
        fmt = _as_document(track.get("format"))
        loudness = _as_float(metrics.get("loudness_proxy_db") if metrics.get("loudness_proxy_db") is not None else -120.0)
        peak_dbfs = _as_float(metrics.get("peak_dbfs") if metrics.get("peak_dbfs") is not None else -120.0)
        max_peak_dbfs = float(track.get("profile_limits", {}).get("max_peak_dbfs") if isinstance(track.get("profile_limits"), dict) else -0.5)
        desired_gain = target_loudness - loudness
        headroom_gain = max_peak_dbfs - peak_dbfs
        gain_db = max(-12.0, min(12.0, desired_gain, headroom_gain))
        track_actions: list[dict[str, Any]] = []
        if abs(gain_db) >= 0.1:
            track_actions.append({"type": "gain", "gain_db": round(gain_db, 3), "reason": "target_loudness_proxy"})
        leading = float(metrics.get("leading_silence_seconds") or 0.0)
        trailing = float(metrics.get("trailing_silence_seconds") or 0.0)
        max_leading = float(track.get("profile_limits", {}).get("max_leading_silence_seconds") if isinstance(track.get("profile_limits"), dict) else 3.0)
        max_trailing = float(track.get("profile_limits", {}).get("max_trailing_silence_seconds") if isinstance(track.get("profile_limits"), dict) else 4.0)
        duration = float(fmt.get("duration_seconds") or 0.0)
        min_duration = float(track.get("profile_limits", {}).get("min_duration_seconds") if isinstance(track.get("profile_limits"), dict) else 8.0)
        if leading > max_leading and duration - (leading - max_leading) >= min_duration:
            track_actions.append({"type": "trim_leading", "seconds": round(leading - max_leading, 3), "reason": "leading_silence"})
        if trailing > max_trailing and duration - (trailing - max_trailing) >= min_duration:
            track_actions.append({"type": "trim_trailing", "seconds": round(trailing - max_trailing, 3), "reason": "trailing_silence"})
        actions.append({"track_id": track.get("track_id"), "source_wav_sha256": track.get("wav_sha256"), "actions": track_actions})
    plan = {
        "schema_version": MASTERING_SCHEMA_VERSION,
        "plan_id": f"mpln-{_short_hash(str(analysis.get('integrity_hash')) + now)}",
        "release_id": analysis.get("release_id"),
        "profile_id": profile_id,
        "analysis_hash": analysis.get("integrity_hash"),
        "analysis_source_hash": analysis.get("source_hash"),
        "created_at": now,
        "status": "ready",
        "actions": actions,
        "summary": {
            "track_count": len(actions),
            "action_count": sum(len(item.get("actions", [])) for item in actions if isinstance(item, dict)),
        },
        "warnings": [],
    }
    plan["integrity_hash"] = _object_hash(plan, MASTERING_INTEGRITY_EXCLUDE)
    return sanitize_metadata(plan, blocked_keys=MASTERING_BLOCKED_KEYS)


def build_mastered_candidate(
    *,
    candidate_id: str,
    release_id: str,
    analysis: dict[str, Any],
    plan: dict[str, Any],
    profile: MasteringProfile,
    source_wavs: dict[str, Path] | None = None,
    candidate_dir: Path,
    payload: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    source_wavs = source_wavs or {}
    now = now or now_iso()
    actions_by_track = {str(item.get("track_id") or ""): item.get("actions", []) for item in plan.get("actions", []) if isinstance(item, dict)}
    source_tracks = {str(item.get("track_id") or ""): item for item in analysis.get("tracks", []) if isinstance(item, dict)}
    track_rows: list[dict[str, Any]] = []
    after_wavs: dict[str, Path] = {}
    for track_id, track in source_tracks.items():
        source_path = source_wavs.get(track_id) or Path(str(track.get("source_wav_path") or ""))
        if not source_path.exists() or not source_path.is_file() or source_path.is_symlink():
            raise MasteringStateError(f"Source WAV is missing for {track_id}.")
        output_rel = Path("tracks") / _validate_track_id(track_id) / "song.wav"
        output_path = candidate_dir / output_rel
        output_path.parent.mkdir(parents=True, exist_ok=True)
        applied = apply_mastering_actions(source_path, output_path, actions_by_track.get(track_id, []), profile=profile)
        after_wavs[track_id] = output_path
        track_rows.append(
            {
                "track_id": track_id,
                "source_wav_sha256": track.get("wav_sha256"),
                "candidate_wav": output_rel.as_posix(),
                "candidate_wav_sha256": file_sha256(output_path),
                "applied_actions": applied,
            }
        )
    release_stub = _release_stub_from_analysis(analysis)
    after_analysis = build_mastering_analysis(
        release=release_stub,
        release_store=_NullReleaseStore(release_id),
        project_store=_NullProjectStore(after_wavs),
        profile=profile,
        now=now,
        source_override={
            "release_id": release_id,
            "candidate_id": candidate_id,
            "analysis_hash": analysis.get("integrity_hash"),
            "plan_hash": plan.get("integrity_hash"),
            "profile": {"profile_id": profile.profile_id, "profile_hash": mastering_profile_hash(profile)},
            "tracks": [{"track_id": row["track_id"], "candidate_wav_sha256": row["candidate_wav_sha256"]} for row in track_rows],
        },
        wav_overrides=after_wavs,
    )
    source = {
        "release_id": release_id,
        "analysis_hash": analysis.get("integrity_hash"),
        "plan_hash": plan.get("integrity_hash"),
        "profile_hash": mastering_profile_hash(profile),
        "source_track_wav_hashes": {row["track_id"]: row["source_wav_sha256"] for row in track_rows},
    }
    candidate = {
        "schema_version": MASTERING_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "release_id": release_id,
        "profile_id": profile.profile_id,
        "status": "ready_for_review",
        "created_at": now,
        "updated_at": now,
        "analysis_hash": analysis.get("integrity_hash"),
        "plan_hash": plan.get("integrity_hash"),
        "source": source,
        "source_hash": stable_hash(source),
        "tracks": track_rows,
        "after_analysis": after_analysis,
        "after_analysis_hash": after_analysis.get("integrity_hash"),
        "review": {},
        "selected": False,
        "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:1000],
    }
    candidate["integrity_hash"] = _object_hash(candidate, MASTERING_INTEGRITY_EXCLUDE)
    return sanitize_metadata(candidate, blocked_keys=MASTERING_BLOCKED_KEYS)


def apply_mastering_actions(source: Path, target: Path, actions: list[dict[str, Any]], *, profile: MasteringProfile) -> list[dict[str, Any]]:
    with wave.open(str(source), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        compression = wav.getcomptype()
        frames = wav.readframes(wav.getnframes())
    if compression != "NONE" or sample_width != 2:
        shutil.copy2(source, target)
        return [{"type": "copy", "reason": "unsupported_pcm_format"}]
    samples = [int.from_bytes(frames[index : index + 2], byteorder="little", signed=True) for index in range(0, len(frames), 2)]
    frame_count = len(samples) // max(1, channels)
    applied: list[dict[str, Any]] = []
    start_frame = 0
    end_frame = frame_count
    gain_db = 0.0
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type") or "")
        if action_type == "gain":
            gain_db += float(action.get("gain_db") or 0.0)
            applied.append({"type": "gain", "gain_db": round(float(action.get("gain_db") or 0.0), 3)})
        elif action_type == "trim_leading":
            frames_to_trim = int(max(0.0, float(action.get("seconds") or 0.0)) * sample_rate)
            start_frame = min(end_frame, start_frame + frames_to_trim)
            applied.append({"type": "trim_leading", "seconds": round(frames_to_trim / sample_rate, 3) if sample_rate else 0.0})
        elif action_type == "trim_trailing":
            frames_to_trim = int(max(0.0, float(action.get("seconds") or 0.0)) * sample_rate)
            end_frame = max(start_frame, end_frame - frames_to_trim)
            applied.append({"type": "trim_trailing", "seconds": round(frames_to_trim / sample_rate, 3) if sample_rate else 0.0})
    selected = samples[start_frame * channels : end_frame * channels]
    gain = math.pow(10.0, gain_db / 20.0) if gain_db else 1.0
    encoded = bytearray()
    for value in selected:
        adjusted = int(round(value * gain))
        adjusted = max(-32768, min(32767, adjusted))
        encoded.extend(int(adjusted).to_bytes(2, byteorder="little", signed=True))
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(encoded))
    if not applied:
        applied.append({"type": "copy"})
    return applied


def mastering_analysis_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    summary = _as_document(analysis.get("summary"))
    return sanitize_metadata(
        {
            "status": analysis.get("status") or "missing",
            "analysis_id": analysis.get("analysis_id"),
            "profile_id": analysis.get("profile_id"),
            "analysis_hash": analysis.get("integrity_hash"),
            "source_hash": analysis.get("source_hash"),
            "track_count": summary.get("track_count", 0),
            "average_loudness_proxy_db": summary.get("average_loudness_proxy_db"),
            "max_track_loudness_delta_db": summary.get("max_track_loudness_delta_db"),
            "warning_count": len(analysis.get("warnings", [])) if isinstance(analysis.get("warnings"), list) else 0,
            "failure_count": len(analysis.get("failures", [])) if isinstance(analysis.get("failures"), list) else 0,
        },
        blocked_keys=MASTERING_BLOCKED_KEYS,
    )


def selected_mastering_track_sources(release_store: ReleaseStore, release_id: str, project_store: ProjectStore | None = None, profile_store: MasteringProfileStore | None = None) -> dict[str, Path]:
    store = MasteringStore(release_store, project_store=project_store, profile_store=profile_store)
    selected = store.read_selected_candidate(release_id, default={})
    if not selected or selected.get("stale") or not mastering_candidate_integrity_ok(selected):
        return {}
    result: dict[str, Path] = {}
    candidate_id = str(selected.get("candidate_id") or "")
    for row in selected.get("tracks", []) if isinstance(selected.get("tracks"), list) else []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("candidate_wav") or "")
        if not rel:
            continue
        path = (store.candidate_dir(release_id, candidate_id) / rel).resolve()
        try:
            _ensure_within(store.candidate_dir(release_id, candidate_id).resolve(), path)
        except MasteringStateError:
            continue
        if path.exists() and path.is_file() and not path.is_symlink():
            result[str(row.get("track_id") or "")] = path
    return result


def export_mastering(release_store: ReleaseStore, release_id: str, export_dir: Path, project_store: ProjectStore | None = None, profile_store: MasteringProfileStore | None = None) -> dict[str, Any]:
    store = MasteringStore(release_store, project_store=project_store, profile_store=profile_store)
    summary = store.get_summary(release_id)
    target = export_dir / "mastering"
    target.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    write_json(target / "summary.json", summary)
    files.append(_file_record(export_dir, target / "summary.json"))
    for source_name in ("analysis.json", "plan.json", "selected-candidate.json"):
        source = store.root_dir(release_id) / source_name
        if source.exists() and source.is_file() and not source.is_symlink():
            dest = target / source_name
            write_json(dest, read_json(source))
            files.append(_file_record(export_dir, dest))
    selected = store.read_selected_candidate(release_id, default={})
    if selected:
        for row in selected.get("tracks", []) if isinstance(selected.get("tracks"), list) else []:
            if not isinstance(row, dict):
                continue
            track_id = str(row.get("track_id") or "")
            candidate_wav = store.candidate_audio_path(release_id, str(selected.get("candidate_id") or ""), track_id)
            dest = target / "tracks" / _validate_track_id(track_id) / "song.wav"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate_wav, dest)
            files.append(_file_record(export_dir, dest))
    export_summary = {
        **summary,
        "summary_path": "mastering/summary.json",
        "summary_hash": mastering_summary_hash(summary),
        "files": files,
    }
    return sanitize_metadata(export_summary, blocked_keys=MASTERING_BLOCKED_KEYS)


def mastering_summary_hash(summary: dict[str, Any]) -> str:
    return _object_hash(summary, MASTERING_SUMMARY_INTEGRITY_EXCLUDE)


def mastering_analysis_integrity_ok(analysis: dict[str, Any]) -> bool:
    expected = str(analysis.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(analysis, MASTERING_INTEGRITY_EXCLUDE)


def mastering_plan_integrity_ok(plan: dict[str, Any]) -> bool:
    expected = str(plan.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(plan, MASTERING_INTEGRITY_EXCLUDE)


def mastering_candidate_integrity_ok(candidate: dict[str, Any]) -> bool:
    expected = str(candidate.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(candidate, MASTERING_INTEGRITY_EXCLUDE)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _analyze_mastering_track(*, track: ImplementationDocument, wav_path: Path, profile: MasteringProfile, now: str) -> ImplementationDocument:
    source = {"track_id": track.get("track_id"), "project_id": track.get("project_id"), "version_id": track.get("version_id"), "scope": "mastering"}
    if not wav_path.exists() or not wav_path.is_file() or wav_path.is_symlink():
        return {
            "track_id": track.get("track_id"),
            "status": "failed",
            "source_wav_path": str(wav_path),
            "wav_sha256": None,
            "format": {},
            "metrics": {},
            "profile_limits": _profile_limits(profile),
            "checks": [_check("wav_exists", "failed", "Track WAV is missing.")],
            "warnings": [],
            "failures": ["wav_missing"],
        }
    health = analyze_wav_health(
        wav_path,
        source=source,
        expected_sample_rate=profile.sample_rate,
        expected_channels=profile.channels,
        expected_bit_depth=profile.bit_depth,
        report_id=f"mqa-{track.get('track_id')}",
        now=now,
    )
    fmt = _as_document(health.get("format"))
    metrics = dict(_as_document(health.get("metrics")))
    peak = float(metrics.get("peak") or 0.0)
    rms = float(metrics.get("rms") or 0.0)
    peak_dbfs = _amplitude_db(peak)
    loudness = _amplitude_db(rms)
    metrics["peak_dbfs"] = peak_dbfs
    metrics["loudness_proxy_db"] = loudness
    checks = list(_as_list(health.get("checks")))
    warnings = [str(item) for item in health.get("warnings", []) if str(item)]
    failures = [str(item) for item in health.get("failures", []) if str(item)]
    if not audio_health_integrity_ok(health):
        failures.append("audio_health_integrity")
    if float(fmt.get("duration_seconds") or 0.0) < profile.min_duration_seconds:
        failures.append("duration_too_short_profile")
        checks.append(_check("mastering_duration_min", "failed", "Track duration is below mastering profile minimum."))
    if profile.max_duration_seconds and float(fmt.get("duration_seconds") or 0.0) > profile.max_duration_seconds:
        warnings.append("duration_long_profile")
        checks.append(_check("mastering_duration_max", "warning", "Track duration exceeds mastering profile maximum."))
    if peak_dbfs > profile.max_peak_dbfs:
        failures.append("peak_too_high")
        checks.append(_check("mastering_peak", "failed", f"Peak {peak_dbfs:.2f} dBFS exceeds {profile.max_peak_dbfs:.2f} dBFS."))
    else:
        checks.append(_check("mastering_peak", "passed", "Peak is within mastering profile limit."))
    if float(metrics.get("clipping_ratio") or 0.0) > profile.max_clipping_ratio:
        failures.append("clipping_ratio")
        checks.append(_check("mastering_clipping", "failed", "Clipping ratio exceeds mastering profile limit."))
    else:
        checks.append(_check("mastering_clipping", "passed", "Clipping ratio is within mastering profile limit."))
    if abs(loudness - profile.target_loudness_proxy_db) > profile.loudness_tolerance_db:
        warnings.append("target_loudness_proxy_delta")
        checks.append(_check("mastering_loudness_proxy", "warning", "Loudness proxy is outside target tolerance."))
    else:
        checks.append(_check("mastering_loudness_proxy", "passed", "Loudness proxy is within target tolerance."))
    if float(metrics.get("leading_silence_seconds") or 0.0) > profile.max_leading_silence_seconds:
        warnings.append("leading_silence_profile")
        checks.append(_check("mastering_leading_silence", "warning", "Leading silence exceeds mastering profile limit."))
    if float(metrics.get("trailing_silence_seconds") or 0.0) > profile.max_trailing_silence_seconds:
        warnings.append("trailing_silence_profile")
        checks.append(_check("mastering_trailing_silence", "warning", "Trailing silence exceeds mastering profile limit."))
    status = "failed" if failures else "warning" if warnings else "passed"
    return sanitize_metadata(
        {
            "track_id": track.get("track_id"),
            "track_number": track.get("track_number"),
            "disc_number": track.get("disc_number"),
            "title": track.get("title"),
            "project_id": track.get("project_id"),
            "version_id": track.get("version_id"),
            "status": status,
            "source_wav_path": str(wav_path),
            "wav_sha256": health.get("wav_sha256"),
            "format": fmt,
            "metrics": metrics,
            "profile_limits": _profile_limits(profile),
            "checks": checks,
            "warnings": sorted(set(warnings)),
            "failures": sorted(set(failures)),
        },
        blocked_keys=MASTERING_BLOCKED_KEYS,
    )


def _profile_limits(profile: MasteringProfile) -> ImplementationDocument:
    return {
        "target_loudness_proxy_db": profile.target_loudness_proxy_db,
        "loudness_tolerance_db": profile.loudness_tolerance_db,
        "max_peak_dbfs": profile.max_peak_dbfs,
        "max_clipping_ratio": profile.max_clipping_ratio,
        "max_track_loudness_delta_db": profile.max_track_loudness_delta_db,
        "max_leading_silence_seconds": profile.max_leading_silence_seconds,
        "max_trailing_silence_seconds": profile.max_trailing_silence_seconds,
        "min_duration_seconds": profile.min_duration_seconds,
    }


def _release_stub_from_analysis(analysis: ImplementationDocument) -> ReleaseDocument:
    from song_agent.domains.delivery.releases import ReleaseDocument, ReleaseTrack

    tracks = []
    for index, item in enumerate(analysis.get("tracks", []) if isinstance(analysis.get("tracks"), list) else [], start=1):
        if not isinstance(item, dict):
            continue
        tracks.append(
            ReleaseTrack(
                track_id=str(item.get("track_id") or f"track-{index:06d}"),
                track_number=int(item.get("track_number") or index),
                disc_number=int(item.get("disc_number") or 1),
                title=str(item.get("title") or item.get("track_id") or "Track"),
                artist=None,
                project_id=str(item.get("project_id") or ""),
                version_id=str(item.get("version_id") or ""),
            )
        )
    return ReleaseDocument(
        schema_version=MASTERING_SCHEMA_VERSION,
        release_id=str(analysis.get("release_id") or "release-000000"),
        name="Mastered Candidate",
        release_type="demo_pack",
        status="draft",
        primary_artist="",
        label=None,
        language=None,
        notes=None,
        created_at=str(analysis.get("generated_at") or now_iso()),
        updated_at=str(analysis.get("generated_at") or now_iso()),
        tracks=tracks,
    )


class _NullReleaseStore:
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id

    def export_dir(self, release_id: str) -> Path:
        return Path(".")


class _NullProjectStore:
    def __init__(self, wavs: dict[str, Path]) -> None:
        self.wavs = wavs

    def project_dir(self, project_id: str) -> Path:
        return Path(".")


def _object_hash(value: ImplementationDocument, exclude: set[str]) -> str:
    return stable_hash(sanitize_metadata({key: item for key, item in value.items() if key not in exclude}, blocked_keys=MASTERING_BLOCKED_KEYS))


def _file_state(path: Path) -> ImplementationDocument:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {"exists": False, "sha256": None, "size_bytes": 0}
    return {"exists": True, "sha256": file_sha256(path), "size_bytes": path.stat().st_size}


def _json_file_state(path: Path) -> ImplementationDocument:
    state = _file_state(path)
    if state.get("exists"):
        try:
            state["payload_hash"] = stable_hash(read_json(path))
        except Exception:
            state["payload_hash"] = None
    return state


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
    rel = path.resolve().relative_to(export_dir.resolve()).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": file_sha256(path)}


def _validate_candidate_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("mcand-") or any(part in text for part in ("/", "\\", "..", ":")):
        raise MasteringStateError("Invalid mastered candidate id.")
    return text


def _validate_track_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("track-") or any(part in text for part in ("/", "\\", "..", ":")):
        raise MasteringStateError("Invalid release track id.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise MasteringStateError("Refusing to operate outside mastering boundaries.") from exc


def _check(check_id: str, status: str, message: str) -> ImplementationDocument:
    return {"id": check_id, "status": status, "message": message}


def _amplitude_db(value: float) -> float:
    if value <= 0:
        return -120.0
    return round(20.0 * math.log10(min(max(value, 1e-12), 1.0)), 3)


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]
