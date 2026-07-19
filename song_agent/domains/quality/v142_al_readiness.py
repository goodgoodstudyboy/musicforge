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
AudioLabValidationError = _make_deferred_global('AudioLabValidationError')
_artifact_from_payload = _make_deferred_global('_artifact_from_payload')
_artifact_source = _make_deferred_global('_artifact_source')
_bounded = _make_deferred_global('_bounded')
_check = _make_deferred_global('_check')
_default_profile_id = _make_deferred_global('_default_profile_id')
_integrity_hash = _make_deferred_global('_integrity_hash')
_item_source = _make_deferred_global('_item_source')
_marker_payload = _make_deferred_global('_marker_payload')
_read_optional_json = _make_deferred_global('_read_optional_json')
_rel = _make_deferred_global('_rel')
_renderer_public_summary = _make_deferred_global('_renderer_public_summary')
_review_core = _make_deferred_global('_review_core')
_review_payload = _make_deferred_global('_review_payload')
_session_item_public = _make_deferred_global('_session_item_public')
_session_status = _make_deferred_global('_session_status')
_session_summary = _make_deferred_global('_session_summary')
_sha256_path = _make_deferred_global('_sha256_path')
_smoke_summary = _make_deferred_global('_smoke_summary')
_smoke_warnings = _make_deferred_global('_smoke_warnings')
_validate_id = _make_deferred_global('_validate_id')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global AudioLabNotFoundError, AudioLabStateError, AudioLabValidationError, _artifact_from_payload, _artifact_source, _bounded, _check, _default_profile_id
    global _integrity_hash, _item_source, _marker_payload, _read_optional_json, _rel, _renderer_public_summary, _review_core
    global _review_payload, _session_item_public, _session_status, _session_summary, _sha256_path, _smoke_summary, _smoke_warnings, _validate_id
    global row
    AudioLabNotFoundError = namespace.get('AudioLabNotFoundError', AudioLabNotFoundError)
    AudioLabStateError = namespace.get('AudioLabStateError', AudioLabStateError)
    AudioLabValidationError = namespace.get('AudioLabValidationError', AudioLabValidationError)
    _artifact_from_payload = namespace.get('_artifact_from_payload', _artifact_from_payload)
    _artifact_source = namespace.get('_artifact_source', _artifact_source)
    _bounded = namespace.get('_bounded', _bounded)
    _check = namespace.get('_check', _check)
    _default_profile_id = namespace.get('_default_profile_id', _default_profile_id)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _item_source = namespace.get('_item_source', _item_source)
    _marker_payload = namespace.get('_marker_payload', _marker_payload)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _rel = namespace.get('_rel', _rel)
    _renderer_public_summary = namespace.get('_renderer_public_summary', _renderer_public_summary)
    _review_core = namespace.get('_review_core', _review_core)
    _review_payload = namespace.get('_review_payload', _review_payload)
    _session_item_public = namespace.get('_session_item_public', _session_item_public)
    _session_status = namespace.get('_session_status', _session_status)
    _session_summary = namespace.get('_session_summary', _session_summary)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _smoke_summary = namespace.get('_smoke_summary', _smoke_summary)
    _smoke_warnings = namespace.get('_smoke_warnings', _smoke_warnings)
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




class AudioLabStoreReadinessMixin:
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

    def environment_status(self) -> DomainDocument:
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

    def detect_environment(self) -> DomainDocument:
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

    def test_profile(self, profile_id: str | None = None) -> DomainDocument:
        target = _default_profile_id(profile_id)
        try:
            result = self.audio_profile_store.test_profile(_as_text(target))
        except AudioProfileNotFoundError:
            result = {"status": "failed", "message": "Audio profile is not configured.", "profile": None}
        result = sanitize_metadata({**result, "tested_at": now_iso(), "profile_id": target or "default"})
        write_json(self.environment_dir / "last-profile-test.json", result)
        return result

    def setup_report(self) -> DomainDocument:
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

    def run_smoke(self, payload: DomainDocument | None = None) -> DomainDocument:
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
            items: list[DomainDocument] = []
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

    def list_smoke_runs(self) -> list[DomainDocument]:
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

    def read_smoke_report(self, smoke_run_id: str) -> DomainDocument:
        path = self.smoke_run_dir(smoke_run_id) / "smoke-run-report.json"
        if not path.exists():
            raise AudioLabNotFoundError(f"Smoke run not found: {smoke_run_id}.")
        return sanitize_metadata(read_json(path))

    def create_session(self, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        smoke_run_id = str(payload.get("from_smoke") or payload.get("smoke_run_id") or "").strip()
        if not smoke_run_id:
            raise AudioLabValidationError("from_smoke is required.")
        smoke_report = self.read_smoke_report(smoke_run_id)
        with self.lock:
            session_id = self._next_id(self.sessions_dir, "als")
            items: list[object] = []
            for smoke_item in smoke_report.get("items", []):
                if not isinstance(smoke_item, dict):
                    continue
                item: object = {
                    "item_id": str(smoke_item.get("item_id") or f"item-{len(items)+1:03d}"),
                    "song_id": smoke_item.get("song_id"),
                    "title": smoke_item.get("title"),
                    "source_smoke_run_id": smoke_run_id,
                    "artifact_relpaths": dict(smoke_item.get("artifact_relpaths") or {}),
                    "artifact_hashes": dict(smoke_item.get("artifact_hashes") or {}),
                    "audio_status": smoke_item.get("audio_status"),
                    "renderer": dict(smoke_item.get("renderer") or {}),
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

    def create_session_from_items(self, items: list[DomainDocument], source: DomainDocument, *, status: str = "needs_review") -> DomainDocument:
        if not items:
            raise AudioLabValidationError("Listening session requires at least one item.")
        with self.lock:
            session_id = self._next_id(self.sessions_dir, "als")
            session_dir = self.session_dir(session_id)
            now = now_iso()
            prepared: list[DomainDocument] = []
            for index, raw_item in enumerate(items, start=1):
                item_id = str(raw_item.get("item_id") or f"item-{index:03d}")
                item = sanitize_metadata(
                    {
                        **dict(raw_item),
                        "item_id": item_id,
                        "review": dict(raw_item.get("review") or {}),
                        "markers": [dict(marker) for marker in raw_item.get("markers", []) if isinstance(marker, dict)],
                        "stale": bool(raw_item.get("stale", False)),
                        "created_at": str(raw_item.get("created_at") or now),
                        "updated_at": str(raw_item.get("updated_at") or now),
                    }
                )
                source_abspaths = _as_document(raw_item.get("source_abspaths"))
                wav_source = Path(str(source_abspaths.get("wav") or "")) if source_abspaths.get("wav") else None
                if wav_source and wav_source.exists():
                    target = session_dir / "items" / item_id / "song.wav"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(wav_source.read_bytes())
                    item.setdefault("artifact_relpaths", {})["wav"] = _rel(self.root, target)
                    item.setdefault("artifact_hashes", {})["wav_sha256"] = _sha256_path(target)
                item.pop("source_abspaths", None)
                item["source_hash"] = str(item.get("source_hash") or stable_hash(_item_source(item)))
                prepared.append(item)
            session = sanitize_metadata(
                {
                    "schema_version": AUDIO_LAB_SCHEMA_VERSION,
                    "session_id": session_id,
                    "status": status,
                    "created_at": now,
                    "updated_at": now,
                    "source": dict(source),
                    "items": prepared,
                    "summary": _session_summary(prepared, status),
                }
            )
            session["source_hash"] = stable_hash({"source": session["source"], "items": [_item_source(item) for item in prepared]})
            session["integrity_hash"] = _integrity_hash(session)
            self._write_session(session)
            return session

    def list_sessions(self) -> list[DomainDocument]:
        rows = []
        for path in self.sessions_dir.glob("als-*/session.json"):
            try:
                session = self._with_session_stale(read_json(path))
                rows.append({"session_id": session.get("session_id"), "status": session.get("status"), "summary": session.get("summary", {}), "created_at": session.get("created_at")})
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("session_id") or ""))

    def read_session(self, session_id: str) -> DomainDocument:
        path = self.session_path(session_id)
        if not path.exists():
            raise AudioLabNotFoundError(f"Listening session not found: {session_id}.")
        return self._with_session_stale(read_json(path))

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / _validate_id(session_id, "als")

    def session_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"

    def write_item_review(self, session_id: str, item_id: str, payload: DomainDocument) -> DomainDocument:
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

    def add_marker(self, session_id: str, item_id: str, payload: DomainDocument) -> DomainDocument:
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

    def create_marker_draft(self, session_id: str, marker_id: str, draft_type: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def session_report(self, session_id: str) -> DomainDocument:
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

    def close_session(self, session_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            session = self.read_session(session_id)
            summary = _session_summary(session.get("items", []), str(session.get("status") or "needs_review"))
            if summary["stale_count"]:
                raise AudioLabStateError("Cannot close a stale Audio Lab session.")
            if summary["manual_review_count"] < len(session.get("items", [])):
                raise AudioLabStateError("All Audio Lab session items require manual review before close.")
            if summary["rejected_count"]:
                session["status"] = "closed_with_rejections"
            elif summary["needs_fix_count"]:
                session["status"] = "closed_needs_fix"
            else:
                session["status"] = "closed"
            session["closed_at"] = now_iso()
            session["closeout"] = sanitize_metadata({"status": session["status"], "closed_by": _bounded(payload.get("closed_by"), 120) or "audio-lab", "summary": summary})
            session["summary"] = _session_summary(session.get("items", []), session["status"])
            session["integrity_hash"] = _integrity_hash(session)
            self._write_session(session)
            return {"session": session, "summary": session["summary"]}

    def create_comparison(self, payload: DomainDocument) -> DomainDocument:
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
