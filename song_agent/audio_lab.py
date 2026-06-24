from __future__ import annotations

import hashlib
import math
import re
import struct
import threading
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from song_agent.agent.pipeline import SongAgent
from song_agent.audio_health import analyze_wav_health, audio_health_summary
from song_agent.audio_profiles import AudioProfileNotFoundError, AudioProfileStore, renderer_profile_hash
from song_agent.music_acceptance import default_acceptance_song_cases
from song_agent.music_health import analyze_music_health, music_health_summary
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.renderers.audio import RendererError, load_renderer_config, renderer_configured, render_audio
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongPlan, SongRequest


AUDIO_LAB_ROOT = Path(".musicforge") / "audio-lab"
AUDIO_LAB_SCHEMA_VERSION = 1
REVIEW_RESULTS = {"accepted", "needs_fix", "rejected"}
MARKER_CATEGORIES = {
    "audio_silent",
    "audio_clipping",
    "mix_balance",
    "unbalanced_mix",
    "harshness",
    "timing",
    "arrangement",
    "mastering",
    "other",
}
MARKER_SEVERITIES = {"low", "medium", "high", "critical"}


class AudioLabError(ValueError):
    pass


class AudioLabNotFoundError(AudioLabError):
    pass


class AudioLabStateError(AudioLabError):
    pass


class AudioLabValidationError(AudioLabError):
    pass


WavWriter = Callable[[Path, Path], Path]


class AudioLabStore:
    def __init__(
        self,
        root: Path | str = AUDIO_LAB_ROOT,
        *,
        audio_profile_store: AudioProfileStore | None = None,
        wav_writer: WavWriter | None = None,
    ) -> None:
        self.root = Path(root)
        self.audio_profile_store = audio_profile_store or AudioProfileStore(self.root.parent / "audio-profiles")
        self.wav_writer = wav_writer
        self.lock = threading.RLock()

    @property
    def environment_dir(self) -> Path:
        return self.root / "environment"

    @property
    def smoke_runs_dir(self) -> Path:
        return self.root / "smoke-runs"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "listening-sessions"

    @property
    def comparisons_dir(self) -> Path:
        return self.root / "comparisons"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "drafts"

    def environment_status(self) -> dict[str, Any]:
        config, sources = load_renderer_config()
        legacy = _renderer_public_summary(config, sources)
        profiles = []
        for profile in self.audio_profile_store.list_profiles(include_hidden=True):
            profiles.append(profile.public_summary())
        default_profile = None
        try:
            default_profile = self.audio_profile_store.get_profile().public_summary()
        except AudioProfileNotFoundError:
            default_profile = None
        configured = bool(default_profile and default_profile.get("soundfont_exists")) or renderer_configured(config)
        status = "configured" if configured else "missing"
        warnings: list[str] = []
        if not configured:
            warnings.append("renderer_not_configured")
        if self.wav_writer is not None:
            warnings.append("test_wav_writer_active")
        result = {
            "schema_version": AUDIO_LAB_SCHEMA_VERSION,
            "generated_at": now_iso(),
            "status": status,
            "renderer": legacy,
            "profiles": profiles,
            "default_profile": default_profile,
            "summary": {
                "renderer_status": status,
                "profile_count": len(profiles),
                "default_profile_id": (default_profile or {}).get("profile_id"),
                "real_audio_ready": configured and self.wav_writer is None,
                "test_audio_runner": self.wav_writer is not None,
            },
            "warnings": warnings,
        }
        return sanitize_metadata(result)

    def detect_environment(self) -> dict[str, Any]:
        status = self.environment_status()
        report = {
            **status,
            "detect_id": self._next_id(self.environment_dir, "ald"),
            "detected_at": now_iso(),
            "checks": [
                _check("audio_lab_renderer_profile", status.get("status") == "configured", "Renderer or audio profile is configured."),
                _check("audio_lab_paths_redacted", True, "Environment summaries redact local renderer paths."),
            ],
        }
        write_json(self.environment_dir / "last-detect.json", report)
        return report

    def test_profile(self, profile_id: str | None = None) -> dict[str, Any]:
        target = _default_profile_id(profile_id)
        try:
            result = self.audio_profile_store.test_profile(target)
        except AudioProfileNotFoundError:
            result = {"status": "failed", "message": "Audio profile is not configured.", "profile": None}
        result = sanitize_metadata({**result, "tested_at": now_iso(), "profile_id": target or "default"})
        write_json(self.environment_dir / "last-profile-test.json", result)
        return result

    def setup_report(self) -> dict[str, Any]:
        env = self.environment_status()
        last_test = _read_optional_json(self.environment_dir / "last-profile-test.json")
        report = sanitize_metadata(
            {
                "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                "report_id": "audio-lab-setup",
                "generated_at": now_iso(),
                "status": "passed" if env.get("status") == "configured" else "warning",
                "environment": env,
                "last_profile_test": last_test,
                "summary": {
                    "renderer_status": env.get("status"),
                    "profile_test_status": last_test.get("status") if last_test else "missing",
                    "real_audio_ready": (env.get("summary") or {}).get("real_audio_ready", False),
                },
            }
        )
        report["source_hash"] = stable_hash({"environment": env, "last_profile_test": last_test})
        report["integrity_hash"] = _integrity_hash(report)
        write_json(self.environment_dir / "audio-lab-setup-report.json", report)
        return report

    def run_smoke(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        cases = max(1, min(12, int(payload.get("cases") or 1)))
        render_mode = str(payload.get("render_audio") or payload.get("render_audio_mode") or "auto")
        if render_mode == "required":
            render_mode = "require"
        if render_mode not in {"auto", "never", "require"}:
            raise AudioLabValidationError("render_audio must be auto, never, or required.")
        profile_id = _default_profile_id(payload.get("profile") or payload.get("profile_id"))
        with self.lock:
            smoke_id = self._next_id(self.smoke_runs_dir, "alsm")
            run_dir = self.smoke_run_dir(smoke_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            items: list[dict[str, Any]] = []
            for index, song in enumerate(default_acceptance_song_cases(cases), start=1):
                item_id = f"item-{index:03d}"
                item = self._generate_smoke_item(run_dir, smoke_id, item_id, song, render_mode=render_mode, profile_id=profile_id)
                items.append(item)
            status = "failed" if any(item.get("status") == "failed" for item in items) else "warning" if any(item.get("audio_status") != "rendered" for item in items) else "passed"
            report = sanitize_metadata(
                {
                    "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                    "smoke_run_id": smoke_id,
                    "created_at": now_iso(),
                    "status": status,
                    "render_audio": render_mode,
                    "profile_id": profile_id or "default",
                    "items": items,
                    "summary": _smoke_summary(items, status),
                    "warnings": _smoke_warnings(items),
                }
            )
            report["source_hash"] = stable_hash({"items": [_item_source(item) for item in items], "render_audio": render_mode, "profile_id": profile_id or "default"})
            report["integrity_hash"] = _integrity_hash(report)
            write_json(run_dir / "smoke-run-report.json", report)
            write_json(run_dir / "smoke-run.json", {"smoke_run_id": smoke_id, "status": status, "created_at": report["created_at"], "summary": report["summary"]})
            return report

    def list_smoke_runs(self) -> list[dict[str, Any]]:
        rows = []
        for path in self.smoke_runs_dir.glob("alsm-*/smoke-run-report.json"):
            try:
                report = read_json(path)
                rows.append({"smoke_run_id": report.get("smoke_run_id"), "status": report.get("status"), "summary": report.get("summary", {}), "created_at": report.get("created_at")})
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("smoke_run_id") or ""))

    def smoke_run_dir(self, smoke_run_id: str) -> Path:
        return self.smoke_runs_dir / _validate_id(smoke_run_id, "alsm")

    def read_smoke_report(self, smoke_run_id: str) -> dict[str, Any]:
        path = self.smoke_run_dir(smoke_run_id) / "smoke-run-report.json"
        if not path.exists():
            raise AudioLabNotFoundError(f"Smoke run not found: {smoke_run_id}.")
        return sanitize_metadata(read_json(path))

    def create_session(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        smoke_run_id = str(payload.get("from_smoke") or payload.get("smoke_run_id") or "").strip()
        if not smoke_run_id:
            raise AudioLabValidationError("from_smoke is required.")
        smoke_report = self.read_smoke_report(smoke_run_id)
        with self.lock:
            session_id = self._next_id(self.sessions_dir, "als")
            items = []
            for smoke_item in smoke_report.get("items", []):
                if not isinstance(smoke_item, dict):
                    continue
                item = {
                    "item_id": str(smoke_item.get("item_id") or f"item-{len(items)+1:03d}"),
                    "song_id": smoke_item.get("song_id"),
                    "title": smoke_item.get("title"),
                    "source_smoke_run_id": smoke_run_id,
                    "artifact_relpaths": dict(smoke_item.get("artifact_relpaths") or {}),
                    "artifact_hashes": dict(smoke_item.get("artifact_hashes") or {}),
                    "audio_status": smoke_item.get("audio_status"),
                    "audio_health_summary": smoke_item.get("audio_health_summary") or {},
                    "music_health_summary": smoke_item.get("music_health_summary") or {},
                    "source_hash": smoke_item.get("source_hash"),
                    "review": {},
                    "markers": [],
                    "stale": self._item_is_stale(smoke_item),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
                items.append(item)
            session = sanitize_metadata(
                {
                    "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                    "session_id": session_id,
                    "status": "needs_review",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "source": {"source_type": "audio_lab_smoke", "smoke_run_id": smoke_run_id, "smoke_source_hash": smoke_report.get("source_hash")},
                    "items": items,
                    "summary": _session_summary(items, "needs_review"),
                }
            )
            session["source_hash"] = stable_hash({"source": session["source"], "items": [_item_source(item) for item in items]})
            session["integrity_hash"] = _integrity_hash(session)
            self._write_session(session)
            return session

    def list_sessions(self) -> list[dict[str, Any]]:
        rows = []
        for path in self.sessions_dir.glob("als-*/session.json"):
            try:
                session = self._with_session_stale(read_json(path))
                rows.append({"session_id": session.get("session_id"), "status": session.get("status"), "summary": session.get("summary", {}), "created_at": session.get("created_at")})
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("session_id") or ""))

    def read_session(self, session_id: str) -> dict[str, Any]:
        path = self.session_path(session_id)
        if not path.exists():
            raise AudioLabNotFoundError(f"Listening session not found: {session_id}.")
        return self._with_session_stale(read_json(path))

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / _validate_id(session_id, "als")

    def session_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"

    def write_item_review(self, session_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            session = self.read_session(session_id)
            item = self._find_item(session, item_id)
            if item.get("stale"):
                raise AudioLabStateError("Listening session item is stale. Refresh the smoke run before reviewing.")
            review = _review_payload(payload)
            if item.get("audio_status") != "rendered" or not item.get("artifact_hashes", {}).get("wav_sha256"):
                raise AudioLabStateError("Manual Audio Lab review requires a rendered current WAV artifact.")
            review["audio_evidence"] = {
                "wav_sha256": item.get("artifact_hashes", {}).get("wav_sha256"),
                "audio_health_hash": item.get("artifact_hashes", {}).get("audio_health_hash"),
                "source_hash": item.get("source_hash"),
            }
            review["source_hash"] = stable_hash({"item_source_hash": item.get("source_hash"), "audio_evidence": review["audio_evidence"], "review": _review_core(review)})
            review["integrity_hash"] = _integrity_hash(review)
            item["review"] = review
            item["updated_at"] = now_iso()
            session["items"] = [item if row.get("item_id") == item_id else row for row in session.get("items", [])]
            session["status"] = _session_status(session["items"])
            session["updated_at"] = now_iso()
            session["summary"] = _session_summary(session["items"], session["status"])
            session["integrity_hash"] = _integrity_hash(session)
            self._write_session(session)
            return {"session": session, "item": item, "review": review, "summary": session["summary"]}

    def add_marker(self, session_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            session = self.read_session(session_id)
            item = self._find_item(session, item_id)
            if item.get("stale"):
                raise AudioLabStateError("Listening session item is stale. Refresh before adding markers.")
            marker_id = f"alm-{len(item.get('markers') or []) + 1:03d}"
            marker = _marker_payload(marker_id, item, payload)
            item.setdefault("markers", []).append(marker)
            item["updated_at"] = now_iso()
            session["items"] = [item if row.get("item_id") == item_id else row for row in session.get("items", [])]
            session["status"] = _session_status(session["items"])
            session["summary"] = _session_summary(session["items"], session["status"])
            session["updated_at"] = now_iso()
            session["integrity_hash"] = _integrity_hash(session)
            self._write_session(session)
            return {"session": session, "item": item, "marker": marker, "summary": session["summary"]}

    def create_marker_draft(self, session_id: str, marker_id: str, draft_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        if draft_type not in {"review_task", "audio_revision", "mix_patch"}:
            raise AudioLabValidationError("Unsupported marker draft type.")
        with self.lock:
            session = self.read_session(session_id)
            item, marker = self._find_marker(session, marker_id)
            if item.get("stale"):
                raise AudioLabStateError("Marker source is stale. Refresh before creating fix drafts.")
            draft_prefix = {"review_task": "alrt", "audio_revision": "alar", "mix_patch": "almp"}[draft_type]
            draft_id = self._next_id(self.drafts_dir / f"{draft_type}s", draft_prefix)
            draft = sanitize_metadata(
                {
                    "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                    "draft_id": draft_id,
                    "draft_type": draft_type,
                    "status": "draft",
                    "created_at": now_iso(),
                    "session_id": session_id,
                    "item_id": item.get("item_id"),
                    "marker_id": marker_id,
                    "title": _bounded(payload.get("title"), 160) or f"Audio Lab fix: {marker.get('category')}",
                    "instruction": _bounded(payload.get("instruction"), 1000) or marker.get("message") or marker.get("category"),
                    "provenance": {
                        "source_type": "audio_lab_marker",
                        "session_source_hash": session.get("source_hash"),
                        "item_source_hash": item.get("source_hash"),
                        "marker_source_hash": marker.get("source_hash"),
                        "wav_sha256": item.get("artifact_hashes", {}).get("wav_sha256"),
                    },
                    "auto_apply": False,
                }
            )
            draft["integrity_hash"] = _integrity_hash(draft)
            path = self.drafts_dir / f"{draft_type}s" / draft_id / "draft.json"
            write_json(path, draft)
            marker[f"{draft_type}_draft_id"] = draft_id
            self._write_session(session)
            return {"draft": draft, "marker": marker}

    def session_report(self, session_id: str) -> dict[str, Any]:
        session = self.read_session(session_id)
        items = session.get("items", [])
        report = sanitize_metadata(
            {
                "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                "report_id": f"alr-{session_id}",
                "session_id": session_id,
                "generated_at": now_iso(),
                "status": "failed" if any(row.get("stale") for row in items) else session.get("status"),
                "source": session.get("source", {}),
                "summary": _session_summary(items, str(session.get("status") or "needs_review")),
                "items": [_session_item_public(row) for row in items],
            }
        )
        report["source_hash"] = stable_hash({"session_source_hash": session.get("source_hash"), "items": [_item_source(item) for item in items]})
        report["integrity_hash"] = _integrity_hash(report)
        write_json(self.session_dir(session_id) / "audio-lab-session-report.json", report)
        return report

    def close_session(self, session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            session = self.read_session(session_id)
            summary = _session_summary(session.get("items", []), str(session.get("status") or "needs_review"))
            if summary["stale_count"]:
                raise AudioLabStateError("Cannot close a stale Audio Lab session.")
            if summary["manual_review_count"] < len(session.get("items", [])):
                raise AudioLabStateError("All Audio Lab session items require manual review before close.")
            session["status"] = "closed" if summary["rejected_count"] == 0 else "closed_with_rejections"
            session["closed_at"] = now_iso()
            session["closeout"] = sanitize_metadata({"status": session["status"], "closed_by": _bounded(payload.get("closed_by"), 120) or "audio-lab", "summary": summary})
            session["summary"] = _session_summary(session.get("items", []), session["status"])
            session["integrity_hash"] = _integrity_hash(session)
            self._write_session(session)
            return {"session": session, "summary": session["summary"]}

    def create_comparison(self, payload: dict[str, Any]) -> dict[str, Any]:
        left = _artifact_from_payload(payload.get("left") or payload.get("left_artifact") or payload.get("left_path"))
        right = _artifact_from_payload(payload.get("right") or payload.get("right_artifact") or payload.get("right_path"))
        with self.lock:
            comparison_id = self._next_id(self.comparisons_dir, "abc")
            comparison = {
                "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                "comparison_id": comparison_id,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "left": left,
                "right": right,
                "review": {},
            }
            comparison["source_hash"] = stable_hash({"left": _artifact_source(left), "right": _artifact_source(right)})
            comparison["integrity_hash"] = _integrity_hash(comparison)
            self._write_comparison(comparison)
            return self._with_comparison_stale(comparison)

    def list_comparisons(self) -> list[dict[str, Any]]:
        rows = []
        for path in self.comparisons_dir.glob("abc-*/comparison.json"):
            try:
                comparison = self._with_comparison_stale(read_json(path))
                rows.append({"comparison_id": comparison.get("comparison_id"), "stale": comparison.get("stale"), "review": comparison.get("review", {}), "created_at": comparison.get("created_at")})
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("comparison_id") or ""))

    def read_comparison(self, comparison_id: str) -> dict[str, Any]:
        path = self.comparison_path(comparison_id)
        if not path.exists():
            raise AudioLabNotFoundError(f"Comparison not found: {comparison_id}.")
        return self._with_comparison_stale(read_json(path))

    def _read_comparison_raw(self, comparison_id: str) -> dict[str, Any]:
        path = self.comparison_path(comparison_id)
        if not path.exists():
            raise AudioLabNotFoundError(f"Comparison not found: {comparison_id}.")
        return read_json(path)

    def comparison_dir(self, comparison_id: str) -> Path:
        return self.comparisons_dir / _validate_id(comparison_id, "abc")

    def comparison_path(self, comparison_id: str) -> Path:
        return self.comparison_dir(comparison_id) / "comparison.json"

    def review_comparison(self, comparison_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            raw = self._read_comparison_raw(comparison_id)
            checked = self._with_comparison_stale(raw)
            if checked.get("stale"):
                raise AudioLabStateError("A/B comparison artifacts are stale.")
            review = _comparison_review_payload(payload)
            review["source_hash"] = stable_hash({"comparison_source_hash": raw.get("source_hash"), "review": _review_core(review)})
            review["integrity_hash"] = _integrity_hash(review)
            raw["review"] = review
            raw["updated_at"] = now_iso()
            raw["integrity_hash"] = _integrity_hash(raw)
            self._write_comparison(raw)
            return self._with_comparison_stale(raw)

    def comparison_report(self, comparison_id: str) -> dict[str, Any]:
        raw = self._read_comparison_raw(comparison_id)
        comparison = self._with_comparison_stale(raw)
        report = sanitize_metadata(
            {
                "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                "report_id": f"abcr-{comparison_id}",
                "comparison_id": comparison_id,
                "generated_at": now_iso(),
                "status": "failed" if comparison.get("stale") else "passed" if comparison.get("review") else "needs_review",
                "left": comparison.get("left"),
                "right": comparison.get("right"),
                "review": comparison.get("review", {}),
                "stale": comparison.get("stale", False),
                "stale_reasons": comparison.get("stale_reasons", []),
            }
        )
        report["source_hash"] = stable_hash({"comparison_source_hash": comparison.get("source_hash"), "review": comparison.get("review", {})})
        report["integrity_hash"] = _integrity_hash(report)
        write_json(self.comparison_dir(comparison_id) / "comparison-report.json", report)
        return report

    def _generate_smoke_item(self, run_dir: Path, smoke_id: str, item_id: str, song: dict[str, Any], *, render_mode: str, profile_id: str | None) -> dict[str, Any]:
        item_dir = run_dir / "items" / item_id
        item_dir.mkdir(parents=True, exist_ok=True)
        request = SongRequest.from_dict(song.get("request") or {})
        plan = SongAgent().generate(request)
        plan_path = item_dir / "song-plan.json"
        midi_path = item_dir / "song.mid"
        wav_path = item_dir / "song.wav"
        write_json(plan_path, plan.to_dict())
        write_json(item_dir / "request.json", request.to_dict())
        render_midi(plan, midi_path)
        audio_status, audio_error, renderer_summary = self._render_smoke_audio(midi_path, wav_path, render_mode=render_mode, profile_id=profile_id)
        audio_health_report: dict[str, Any] = {}
        if wav_path.exists():
            audio_health_report = analyze_wav_health(
                wav_path,
                source={"smoke_run_id": smoke_id, "item_id": item_id, "runner_kind": renderer_summary.get("runner_kind")},
                expected_duration_seconds=float((song.get("request") or {}).get("duration_seconds") or 90),
                report_id=f"alahr-{smoke_id}-{item_id}",
                now=now_iso(),
            )
            write_json(item_dir / "audio-health.json", audio_health_report)
        music_health = analyze_music_health(
            plan,
            case_id=item_id,
            midi_path=midi_path,
            wav_path=wav_path,
            validator_report={"status": "passed"},
            quality_report={},
            renderer_configured=audio_status == "rendered" or render_mode == "require",
            audio_not_required_status=audio_status,
            now=now_iso(),
        )
        write_json(item_dir / "music-health.json", music_health)
        artifact_relpaths = {
            "song_plan": _rel(self.root, plan_path),
            "midi": _rel(self.root, midi_path),
            "music_health": _rel(self.root, item_dir / "music-health.json"),
        }
        if wav_path.exists():
            artifact_relpaths["wav"] = _rel(self.root, wav_path)
            artifact_relpaths["audio_health"] = _rel(self.root, item_dir / "audio-health.json")
        artifact_hashes = {
            "song_plan_hash": _json_file_hash(plan_path),
            "midi_sha256": _sha256_path(midi_path),
            "wav_sha256": _sha256_path(wav_path) if wav_path.exists() else None,
            "music_health_hash": stable_hash(music_health),
            "audio_health_hash": stable_hash(audio_health_report) if audio_health_report else None,
            "renderer_profile_hash": renderer_summary.get("profile_hash"),
        }
        source_hash = stable_hash({"artifact_hashes": artifact_hashes, "renderer": renderer_summary, "song_id": song.get("song_id")})
        item_status = "failed" if render_mode == "require" and audio_status != "rendered" else "passed" if music_health.get("status") in {"passed", "warning"} else "failed"
        return sanitize_metadata(
            {
                "item_id": item_id,
                "song_id": song.get("song_id"),
                "title": song.get("title") or request.title,
                "status": item_status,
                "audio_status": audio_status,
                "audio_error": sanitize_sensitive_text(audio_error or ""),
                "artifact_relpaths": artifact_relpaths,
                "artifact_hashes": artifact_hashes,
                "renderer": renderer_summary,
                "audio_health_summary": audio_health_summary(audio_health_report) if audio_health_report else {"status": audio_status},
                "music_health_summary": music_health_summary(music_health),
                "source_hash": source_hash,
            }
        )

    def _render_smoke_audio(self, midi_path: Path, wav_path: Path, *, render_mode: str, profile_id: str | None) -> tuple[str, str | None, dict[str, Any]]:
        if render_mode == "never":
            return "skipped_by_request", None, {"runner_kind": "none", "profile_id": profile_id or "default"}
        if self.wav_writer is not None:
            self.wav_writer(midi_path, wav_path)
            return "rendered", None, {"runner_kind": "test_fake", "profile_id": profile_id or "test", "release_ready": False}
        try:
            profile = self.audio_profile_store.get_profile(profile_id)
            summary = profile.public_summary()
            if not summary.get("soundfont_exists"):
                if render_mode == "require":
                    return "failed", "SoundFont file does not exist.", {**summary, "runner_kind": "real"}
                return "skipped_renderer_not_configured", None, {**summary, "runner_kind": "real"}
            render_audio(midi_path, wav_path, profile.to_renderer_config(), timeout_seconds=profile.timeout_seconds)
            return "rendered", None, {**summary, "runner_kind": "real", "release_ready": True}
        except (AudioProfileNotFoundError, RendererError) as exc:
            if render_mode == "require":
                return "failed", sanitize_sensitive_text(str(exc)), {"runner_kind": "real", "profile_id": profile_id or "default"}
            return "render_failed" if isinstance(exc, RendererError) else "skipped_renderer_not_configured", sanitize_sensitive_text(str(exc)), {"runner_kind": "real", "profile_id": profile_id or "default"}

    def _write_session(self, session: dict[str, Any]) -> None:
        write_json(self.session_path(str(session["session_id"])), sanitize_metadata(session))

    def _write_comparison(self, comparison: dict[str, Any]) -> None:
        write_json(self.comparison_path(str(comparison["comparison_id"])), comparison)

    def _find_item(self, session: dict[str, Any], item_id: str) -> dict[str, Any]:
        for item in session.get("items", []):
            if isinstance(item, dict) and item.get("item_id") == item_id:
                return item
        raise AudioLabNotFoundError(f"Audio Lab session item not found: {item_id}.")

    def _find_marker(self, session: dict[str, Any], marker_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for item in session.get("items", []):
            if not isinstance(item, dict):
                continue
            for marker in item.get("markers", []):
                if isinstance(marker, dict) and marker.get("marker_id") == marker_id:
                    return item, marker
        raise AudioLabNotFoundError(f"Audio Lab marker not found: {marker_id}.")

    def _with_session_stale(self, session: dict[str, Any]) -> dict[str, Any]:
        items = []
        for item in session.get("items", []):
            if isinstance(item, dict):
                updated = dict(item)
                updated["stale"] = self._item_is_stale(updated)
                updated["stale_reasons"] = self._item_stale_reasons(updated)
                items.append(updated)
        session = dict(session)
        session["items"] = items
        session["summary"] = _session_summary(items, str(session.get("status") or "needs_review"))
        return sanitize_metadata(session)

    def _item_is_stale(self, item: dict[str, Any]) -> bool:
        return bool(self._item_stale_reasons(item))

    def _item_stale_reasons(self, item: dict[str, Any]) -> list[str]:
        reasons = []
        relpaths = item.get("artifact_relpaths") if isinstance(item.get("artifact_relpaths"), dict) else {}
        hashes = item.get("artifact_hashes") if isinstance(item.get("artifact_hashes"), dict) else {}
        for key, hash_key in (("song_plan", "song_plan_hash"), ("midi", "midi_sha256"), ("wav", "wav_sha256")):
            relpath = str(relpaths.get(key) or "")
            expected = hashes.get(hash_key)
            if not relpath or not expected:
                continue
            path = _resolve_rel(self.root, relpath)
            if not path.exists():
                reasons.append(f"{key}_missing")
            elif (stable_hash(read_json(path)) if key == "song_plan" else _sha256_path(path)) != expected:
                reasons.append(f"{key}_changed")
        if relpaths.get("audio_health") and hashes.get("audio_health_hash"):
            path = _resolve_rel(self.root, str(relpaths["audio_health"]))
            if not path.exists():
                reasons.append("audio_health_missing")
            elif stable_hash(read_json(path)) != hashes.get("audio_health_hash"):
                reasons.append("audio_health_changed")
        return reasons

    def _with_comparison_stale(self, comparison: dict[str, Any]) -> dict[str, Any]:
        reasons = []
        for side in ("left", "right"):
            artifact = comparison.get(side) if isinstance(comparison.get(side), dict) else {}
            path_text = str(artifact.get("source_abspath") or "")
            expected = str(artifact.get("artifact_hash") or "")
            if not path_text or not expected:
                reasons.append(f"{side}_missing")
                continue
            path = Path(path_text)
            if not path.exists():
                reasons.append(f"{side}_missing")
            elif _sha256_path(path) != expected:
                reasons.append(f"{side}_changed")
        comparison = dict(comparison)
        comparison["stale"] = bool(reasons)
        comparison["stale_reasons"] = reasons
        public = sanitize_metadata(comparison)
        for side in ("left", "right"):
            if isinstance(public.get(side), dict):
                public[side].pop("source_abspath", None)
        return public

    def _next_id(self, root: Path, prefix: str) -> str:
        root.mkdir(parents=True, exist_ok=True)
        max_index = 0
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d{{6}}|\d{{3}})$")
        for path in root.glob(f"{prefix}-*"):
            match = pattern.match(path.name)
            if match:
                max_index = max(max_index, int(match.group(1)))
        return f"{prefix}-{max_index + 1:06d}"


def write_lab_test_wav(_midi_path: Path, wav_path: Path, *, duration_seconds: float = 9.0, sample_rate: int = 44100, amplitude: float = 0.2) -> Path:
    """Test-only WAV writer used by release-check and unit tests, never by public config."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frame_count):
            value = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * (index / sample_rate)))
            wav.writeframesraw(struct.pack("<hh", value, value))
    return wav_path


def _renderer_public_summary(config: Any, sources: dict[str, str]) -> dict[str, Any]:
    soundfont = Path(config.soundfont_path) if getattr(config, "soundfont_path", "") else None
    return sanitize_metadata(
        {
            "renderer_type": config.renderer_type,
            "fluidsynth_configured": bool(config.fluidsynth_path),
            "soundfont_configured": bool(config.soundfont_path),
            "soundfont_exists": bool(soundfont and soundfont.exists()),
            "sample_rate": config.sample_rate,
            "output_format": config.output_format,
            "gain": config.gain,
            "sources": {key: value for key, value in sources.items() if key not in {"fluidsynth_path", "soundfont_path"}},
            "paths_redacted": True,
        }
    )


def _default_profile_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return None if text in {"", "default", "None", "null"} else text


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.match(rf"^{re.escape(prefix)}-\d{{3,6}}$", text):
        raise AudioLabValidationError(f"Invalid {prefix} id.")
    return text


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _review_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = str(payload.get("result") or payload.get("status") or "").strip()
    if result not in REVIEW_RESULTS:
        raise AudioLabValidationError("review result must be accepted, needs_fix, or rejected.")
    if not bool(payload.get("playback_confirmed", False)):
        raise AudioLabValidationError("playback_confirmed=true is required for manual Audio Lab review.")
    if str(payload.get("review_mode") or "manual") != "manual":
        raise AudioLabValidationError("Audio Lab session review must use review_mode=manual.")
    reviewer_payload = payload.get("reviewer") if isinstance(payload.get("reviewer"), dict) else {}
    reviewer_name = payload.get("reviewer_name") or reviewer_payload.get("name") or (payload.get("reviewer") if isinstance(payload.get("reviewer"), str) else "")
    reviewer_role = payload.get("reviewer_role") or reviewer_payload.get("role") or payload.get("role")
    reviewer = {"name": _bounded(reviewer_name, 120), "role": _bounded(reviewer_role, 120)}
    if not reviewer["name"] or not reviewer["role"]:
        raise AudioLabValidationError("reviewer name and role are required.")
    rating = max(1, min(5, int(payload.get("rating") or 0)))
    if rating <= 0:
        raise AudioLabValidationError("rating must be 1..5.")
    review = {
        "status": result,
        "result": result,
        "rating": rating,
        "review_mode": "manual",
        "playback_confirmed": True,
        "reviewer": reviewer,
        "notes": _bounded(payload.get("notes"), 2000),
        "reviewed_at": now_iso(),
    }
    return sanitize_metadata(review)


def _comparison_review_payload(payload: dict[str, Any]) -> dict[str, Any]:
    preferred = str(payload.get("preferred") or "").strip()
    if preferred not in {"left", "right", "same"}:
        raise AudioLabValidationError("preferred must be left, right, or same.")
    base = _review_payload({**payload, "result": payload.get("result") or "accepted", "rating": payload.get("rating") or 4})
    base["preferred"] = preferred
    base["rating_delta"] = int(payload.get("rating_delta") or 0)
    return base


def _marker_payload(marker_id: str, item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    category = str(payload.get("category") or "other").strip()
    if category not in MARKER_CATEGORIES:
        category = "other"
    severity = str(payload.get("severity") or "medium").strip()
    if severity not in MARKER_SEVERITIES:
        severity = "medium"
    marker = sanitize_metadata(
        {
            "marker_id": marker_id,
            "created_at": now_iso(),
            "time_seconds": max(0.0, float(payload.get("time_seconds") or 0.0)),
            "category": category,
            "severity": severity,
            "message": _bounded(payload.get("message") or payload.get("notes"), 1000),
            "source": {"item_source_hash": item.get("source_hash"), "wav_sha256": item.get("artifact_hashes", {}).get("wav_sha256")},
            "auto_apply": False,
        }
    )
    marker["source_hash"] = stable_hash(marker["source"])
    marker["integrity_hash"] = _integrity_hash(marker)
    return marker


def _artifact_from_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        raw_path = value.get("path") or value.get("artifact_path") or value.get("source_abspath")
        label = str(value.get("label") or "").strip()
        artifact_type = str(value.get("artifact_type") or "").strip()
    else:
        raw_path = value
        label = ""
        artifact_type = ""
    path = Path(str(raw_path or "")).resolve()
    if not path.exists() or not path.is_file():
        raise AudioLabValidationError("Comparison artifact file does not exist.")
    suffix = path.suffix.lower().lstrip(".") or "artifact"
    artifact = {
        "label": _bounded(label, 80) or path.stem,
        "artifact_type": artifact_type or suffix,
        "artifact_hash": _sha256_path(path),
        "size_bytes": path.stat().st_size,
        "filename": path.name,
        "source_abspath": str(path),
        "summary_hash": stable_hash({"filename": path.name, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size}),
    }
    return artifact


def _artifact_source(artifact: dict[str, Any]) -> dict[str, Any]:
    return {"artifact_hash": artifact.get("artifact_hash"), "size_bytes": artifact.get("size_bytes"), "summary_hash": artifact.get("summary_hash")}


def _item_source(item: dict[str, Any]) -> dict[str, Any]:
    return {"source_hash": item.get("source_hash"), "artifact_hashes": item.get("artifact_hashes"), "audio_status": item.get("audio_status")}


def _review_core(review: dict[str, Any]) -> dict[str, Any]:
    return {key: review.get(key) for key in ("status", "rating", "review_mode", "playback_confirmed", "reviewer", "preferred", "rating_delta")}


def _session_item_public(item: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "item_id": item.get("item_id"),
            "song_id": item.get("song_id"),
            "title": item.get("title"),
            "audio_status": item.get("audio_status"),
            "audio_health_summary": item.get("audio_health_summary", {}),
            "music_health_summary": item.get("music_health_summary", {}),
            "review": item.get("review", {}),
            "markers": item.get("markers", []),
            "stale": item.get("stale", False),
            "stale_reasons": item.get("stale_reasons", []),
        }
    )


def _session_status(items: list[dict[str, Any]]) -> str:
    if any(item.get("stale") for item in items):
        return "stale"
    reviews = [item.get("review") for item in items if isinstance(item.get("review"), dict) and item.get("review")]
    if len(reviews) < len(items):
        return "needs_review"
    if any(review.get("status") == "rejected" for review in reviews):
        return "failed"
    if any(review.get("status") == "needs_fix" for review in reviews):
        return "needs_fix"
    return "passed"


def _session_summary(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    reviews = [item.get("review") for item in items if isinstance(item.get("review"), dict) and item.get("review")]
    return {
        "status": status,
        "item_count": len(items),
        "manual_review_count": sum(1 for review in reviews if review.get("review_mode") == "manual"),
        "accepted_count": sum(1 for review in reviews if review.get("status") == "accepted"),
        "needs_fix_count": sum(1 for review in reviews if review.get("status") == "needs_fix"),
        "rejected_count": sum(1 for review in reviews if review.get("status") == "rejected"),
        "marker_count": sum(len(item.get("markers") or []) for item in items),
        "stale_count": sum(1 for item in items if item.get("stale")),
        "rendered_wav_count": sum(1 for item in items if item.get("audio_status") == "rendered"),
    }


def _smoke_summary(items: list[dict[str, Any]], status: str) -> dict[str, Any]:
    return {
        "status": status,
        "item_count": len(items),
        "midi_count": sum(1 for item in items if item.get("artifact_hashes", {}).get("midi_sha256")),
        "wav_count": sum(1 for item in items if item.get("artifact_hashes", {}).get("wav_sha256")),
        "rendered_count": sum(1 for item in items if item.get("audio_status") == "rendered"),
        "skipped_count": sum(1 for item in items if str(item.get("audio_status") or "").startswith("skipped")),
        "failed_count": sum(1 for item in items if item.get("status") == "failed"),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake"),
    }


def _smoke_warnings(items: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if any(item.get("audio_status") == "skipped_renderer_not_configured" for item in items):
        warnings.append("renderer_not_configured")
    if any(item.get("renderer", {}).get("runner_kind") == "test_fake" for item in items):
        warnings.append("test_fake_audio_not_release_ready")
    return warnings


def _check(check_id: str, passed: bool, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "warning", "message": message}


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return sanitize_metadata(read_json(path))
    except (OSError, ValueError):
        return {}


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return stable_hash(read_json(path))


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _resolve_rel(root: Path, relpath: str) -> Path:
    base = root.resolve()
    target = (base / relpath).resolve()
    if base != target and base not in target.parents:
        raise AudioLabValidationError("Unsafe Audio Lab artifact path.")
    return target
