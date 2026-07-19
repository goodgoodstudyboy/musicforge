# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_text as _as_text
import hashlib as hashlib
import math as math
import re as re
import struct as struct
import threading as threading
import wave as wave
from collections.abc import Callable as Callable
from pathlib import Path as Path
from song_agent.domains.creation.agent.pipeline import SongAgent as SongAgent
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_summary as audio_health_summary
from song_agent.domains.quality.audio_profiles import AudioProfileNotFoundError as AudioProfileNotFoundError, AudioProfileStore as AudioProfileStore, renderer_profile_hash as renderer_profile_hash
from song_agent.domains.quality.music_acceptance import default_acceptance_song_cases as default_acceptance_song_cases
from song_agent.domains.creation.music_health import analyze_music_health as analyze_music_health, music_health_summary as music_health_summary
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.creation.renderers.audio import RendererError as RendererError, load_renderer_config as load_renderer_config, renderer_configured as renderer_configured, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongRequest as SongRequest

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

AudioLabNotFoundError = _make_deferred_global('AudioLabNotFoundError')
AudioLabStateError = _make_deferred_global('AudioLabStateError')
_comparison_review_payload = _make_deferred_global('_comparison_review_payload')
_integrity_hash = _make_deferred_global('_integrity_hash')
_json_file_hash = _make_deferred_global('_json_file_hash')
_rel = _make_deferred_global('_rel')
_resolve_rel = _make_deferred_global('_resolve_rel')
_review_core = _make_deferred_global('_review_core')
_session_summary = _make_deferred_global('_session_summary')
_sha256_path = _make_deferred_global('_sha256_path')
_validate_id = _make_deferred_global('_validate_id')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioLabNotFoundError, AudioLabStateError, _comparison_review_payload, _integrity_hash, _json_file_hash, _rel, _resolve_rel
    global _review_core, _session_summary, _sha256_path, _validate_id, row
    AudioLabNotFoundError = namespace.get('AudioLabNotFoundError', AudioLabNotFoundError)
    AudioLabStateError = namespace.get('AudioLabStateError', AudioLabStateError)
    _comparison_review_payload = namespace.get('_comparison_review_payload', _comparison_review_payload)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _json_file_hash = namespace.get('_json_file_hash', _json_file_hash)
    _rel = namespace.get('_rel', _rel)
    _resolve_rel = namespace.get('_resolve_rel', _resolve_rel)
    _review_core = namespace.get('_review_core', _review_core)
    _session_summary = namespace.get('_session_summary', _session_summary)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _validate_id = namespace.get('_validate_id', _validate_id)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


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




class AudioLabStoreEvidenceMixin:
    def list_comparisons(self) -> list[DomainDocument]:
        rows = []
        for path in self.comparisons_dir.glob("abc-*/comparison.json"):
            try:
                comparison = self._with_comparison_stale(read_json(path))
                rows.append({"comparison_id": comparison.get("comparison_id"), "stale": comparison.get("stale"), "review": comparison.get("review", {}), "created_at": comparison.get("created_at")})
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("comparison_id") or ""))

    def read_comparison(self, comparison_id: str) -> DomainDocument:
        path = self.comparison_path(comparison_id)
        if not path.exists():
            raise AudioLabNotFoundError(f"Comparison not found: {comparison_id}.")
        return self._with_comparison_stale(read_json(path))

    def _read_comparison_raw(self, comparison_id: str) -> DomainDocument:
        path = self.comparison_path(comparison_id)
        if not path.exists():
            raise AudioLabNotFoundError(f"Comparison not found: {comparison_id}.")
        return read_json(path)

    def comparison_dir(self, comparison_id: str) -> Path:
        return self.comparisons_dir / _validate_id(comparison_id, "abc")

    def comparison_path(self, comparison_id: str) -> Path:
        return self.comparison_dir(comparison_id) / "comparison.json"

    def review_comparison(self, comparison_id: str, payload: DomainDocument) -> DomainDocument:
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

    def comparison_report(self, comparison_id: str) -> DomainDocument:
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

    def _generate_smoke_item(self, run_dir: Path, smoke_id: str, item_id: str, song: DomainDocument, *, render_mode: str, profile_id: str | None) -> DomainDocument:
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
        audio_health_report: DomainDocument = {}
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

    def _render_smoke_audio(self, midi_path: Path, wav_path: Path, *, render_mode: str, profile_id: str | None) -> tuple[str, str | None, DomainDocument]:
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

    def _write_session(self, session: DomainDocument) -> None:
        write_json(self.session_path(str(session["session_id"])), sanitize_metadata(session))

    def _write_comparison(self, comparison: DomainDocument) -> None:
        write_json(self.comparison_path(str(comparison["comparison_id"])), comparison)

    def _find_item(self, session: DomainDocument, item_id: str) -> DomainDocument:
        for item in session.get("items", []):
            if isinstance(item, dict) and item.get("item_id") == item_id:
                return item
        raise AudioLabNotFoundError(f"Audio Lab session item not found: {item_id}.")

    def _find_marker(self, session: DomainDocument, marker_id: str) -> tuple[DomainDocument, DomainDocument]:
        for item in session.get("items", []):
            if not isinstance(item, dict):
                continue
            for marker in item.get("markers", []):
                if isinstance(marker, dict) and marker.get("marker_id") == marker_id:
                    return item, marker
        raise AudioLabNotFoundError(f"Audio Lab marker not found: {marker_id}.")

    def _with_session_stale(self, session: DomainDocument) -> DomainDocument:
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

    def _item_is_stale(self, item: DomainDocument) -> bool:
        return bool(self._item_stale_reasons(item))

    def _item_stale_reasons(self, item: DomainDocument) -> list[str]:
        reasons = []
        relpaths = _as_document(item.get("artifact_relpaths"))
        hashes = _as_document(item.get("artifact_hashes"))
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

    def _with_comparison_stale(self, comparison: DomainDocument) -> DomainDocument:
        reasons = []
        for side in ("left", "right"):
            artifact = _as_document(comparison.get(side))
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
