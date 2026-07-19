# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_profiles import AcceptanceProfile as AcceptanceProfile, get_acceptance_profile as get_acceptance_profile, profile_payload as profile_payload
from song_agent.domains.creation.agent.pipeline import SongAgent as SongAgent
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_summary as audio_health_summary
from song_agent.domains.creation.music_health import analyze_music_health as analyze_music_health, music_health_allows_review as music_health_allows_review, music_health_summary as music_health_summary
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.regression_songbook import BUILTIN_SONGBOOK_ID as BUILTIN_SONGBOOK_ID, BUILTIN_SONGBOOK_VERSION as BUILTIN_SONGBOOK_VERSION, list_regression_songs as list_regression_songs
from song_agent.domains.creation.renderers.audio import RendererError as RendererError, load_renderer_config as load_renderer_config, render_audio as render_audio, renderer_configured as renderer_configured
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

AcceptanceCase = _make_deferred_global('AcceptanceCase')
AcceptanceNotFoundError = _make_deferred_global('AcceptanceNotFoundError')
AcceptanceStateError = _make_deferred_global('AcceptanceStateError')
AcceptanceSuite = _make_deferred_global('AcceptanceSuite')
AcceptanceValidationError = _make_deferred_global('AcceptanceValidationError')
_case_artifacts = _make_deferred_global('_case_artifacts')
_case_status_from_review = _make_deferred_global('_case_status_from_review')
_default_request = _make_deferred_global('_default_request')
_optional_text = _make_deferred_global('_optional_text')
_profile_from_payload = _make_deferred_global('_profile_from_payload')
_quality_payload = _make_deferred_global('_quality_payload')
_read_optional_json = _make_deferred_global('_read_optional_json')
_renderer_snapshot = _make_deferred_global('_renderer_snapshot')
_report_markdown = _make_deferred_global('_report_markdown')
_request_duration_seconds = _make_deferred_global('_request_duration_seconds')
_request_from_payload = _make_deferred_global('_request_from_payload')
_request_summary = _make_deferred_global('_request_summary')
_review_payload = _make_deferred_global('_review_payload')
_safe_dict = _make_deferred_global('_safe_dict')
_safe_text = _make_deferred_global('_safe_text')
_suite_requires_audio = _make_deferred_global('_suite_requires_audio')
_validate_case_id = _make_deferred_global('_validate_case_id')
_validate_suite_id = _make_deferred_global('_validate_suite_id')
acceptance_report_summary = _make_deferred_global('acceptance_report_summary')
acceptance_signoff_summary = _make_deferred_global('acceptance_signoff_summary')
build_acceptance_report = _make_deferred_global('build_acceptance_report')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
listening_review_summary = _make_deferred_global('listening_review_summary')
stable_hash = _make_deferred_global('stable_hash')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceCase, AcceptanceNotFoundError, AcceptanceStateError, AcceptanceSuite, AcceptanceValidationError, _case_artifacts, _case_status_from_review, _default_request
    global _optional_text, _profile_from_payload, _quality_payload, _read_optional_json, _renderer_snapshot, _report_markdown, _request_duration_seconds
    global _request_from_payload, _request_summary, _review_payload, _safe_dict, _safe_text, _suite_requires_audio, _validate_case_id, _validate_suite_id
    global acceptance_report_summary, acceptance_signoff_summary, build_acceptance_report, item, key, listening_review_summary, stable_hash, value
    AcceptanceCase = namespace.get('AcceptanceCase', AcceptanceCase)
    AcceptanceNotFoundError = namespace.get('AcceptanceNotFoundError', AcceptanceNotFoundError)
    AcceptanceStateError = namespace.get('AcceptanceStateError', AcceptanceStateError)
    AcceptanceSuite = namespace.get('AcceptanceSuite', AcceptanceSuite)
    AcceptanceValidationError = namespace.get('AcceptanceValidationError', AcceptanceValidationError)
    _case_artifacts = namespace.get('_case_artifacts', _case_artifacts)
    _case_status_from_review = namespace.get('_case_status_from_review', _case_status_from_review)
    _default_request = namespace.get('_default_request', _default_request)
    _optional_text = namespace.get('_optional_text', _optional_text)
    _profile_from_payload = namespace.get('_profile_from_payload', _profile_from_payload)
    _quality_payload = namespace.get('_quality_payload', _quality_payload)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _renderer_snapshot = namespace.get('_renderer_snapshot', _renderer_snapshot)
    _report_markdown = namespace.get('_report_markdown', _report_markdown)
    _request_duration_seconds = namespace.get('_request_duration_seconds', _request_duration_seconds)
    _request_from_payload = namespace.get('_request_from_payload', _request_from_payload)
    _request_summary = namespace.get('_request_summary', _request_summary)
    _review_payload = namespace.get('_review_payload', _review_payload)
    _safe_dict = namespace.get('_safe_dict', _safe_dict)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _suite_requires_audio = namespace.get('_suite_requires_audio', _suite_requires_audio)
    _validate_case_id = namespace.get('_validate_case_id', _validate_case_id)
    _validate_suite_id = namespace.get('_validate_suite_id', _validate_suite_id)
    acceptance_report_summary = namespace.get('acceptance_report_summary', acceptance_report_summary)
    acceptance_signoff_summary = namespace.get('acceptance_signoff_summary', acceptance_signoff_summary)
    build_acceptance_report = namespace.get('build_acceptance_report', build_acceptance_report)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    listening_review_summary = namespace.get('listening_review_summary', listening_review_summary)
    stable_hash = namespace.get('stable_hash', stable_hash)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_SUITE_SCHEMA_VERSION = 1
ACCEPTANCE_CASE_SCHEMA_VERSION = 1
LISTENING_REVIEW_SCHEMA_VERSION = 1
ACCEPTANCE_REPORT_SCHEMA_VERSION = 1
ACCEPTANCE_SIGNOFF_SCHEMA_VERSION = 1
SUITE_STATUSES = {"draft", "generated", "needs_review", "passed", "failed", "signed", "archived"}
CASE_STATUSES = {"pending", "generated", "health_failed", "needs_review", "accepted", "waived", "rejected"}
SIGNED_ACCEPTANCE_STATUSES = {"signed", "force_signed"}




class AcceptanceStoreReadinessMixin:
    def suites_dir(self) -> Path:
        return self.root

    def suite_dir(self, suite_id: str) -> Path:
        return self.root / _validate_suite_id(suite_id)

    def suite_path(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "suite.json"

    def cases_dir(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "cases"

    def case_dir(self, suite_id: str, case_id: str) -> Path:
        return self.cases_dir(suite_id) / _validate_case_id(case_id)

    def case_path(self, suite_id: str, case_id: str) -> Path:
        return self.case_dir(suite_id, case_id) / "case.json"

    def health_path(self, suite_id: str, case_id: str) -> Path:
        return self.case_dir(suite_id, case_id) / "music-health.json"

    def review_path(self, suite_id: str, case_id: str) -> Path:
        return self.case_dir(suite_id, case_id) / "listening-review.json"

    def result_path(self, suite_id: str, case_id: str) -> Path:
        return self.case_dir(suite_id, case_id) / "acceptance-result.json"

    def report_path(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "music-acceptance-report.json"

    def report_markdown_path(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "music-acceptance-report.md"

    def signoff_path(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "acceptance-signoff.json"

    def signoff_history_path(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "signoff-history.jsonl"

    def events_path(self, suite_id: str) -> Path:
        return self.suite_dir(suite_id) / "events.jsonl"

    def list_suites(self, *, include_archived: bool = False) -> list[AcceptanceSuite]:
        rows: list[AcceptanceSuite] = []
        for path in self.root.glob("suite-*/suite.json"):
            try:
                suite = AcceptanceSuite.from_dict(read_json(path))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if suite.status == "archived" and not include_archived:
                continue
            self._recalculate_suite(suite)
            rows.append(suite)
        return sorted(rows, key=lambda item: item.updated_at, reverse=True)

    def get_suite(self, suite_id: str) -> AcceptanceSuite:
        path = self.suite_path(suite_id)
        if not path.exists():
            raise AcceptanceNotFoundError(suite_id)
        suite = AcceptanceSuite.from_dict(read_json(path))
        self._recalculate_suite(suite)
        return suite

    def create_suite(self, payload: DomainDocument | None = None) -> AcceptanceSuite:
        payload = payload or {}
        with self.lock:
            profile = _profile_from_payload(payload)
            suite_id = self._reserve_suite_id()
            now = now_iso()
            config, sources = load_renderer_config()
            require_audio = profile.require_audio_if_renderer_configured
            if payload.get("require_audio_if_renderer_configured") is not None:
                require_audio = bool(payload.get("require_audio_if_renderer_configured"))
            suite = AcceptanceSuite(
                schema_version=ACCEPTANCE_SUITE_SCHEMA_VERSION,
                suite_id=suite_id,
                name=_safe_text(payload.get("name"), 120) or "Music Acceptance Suite",
                status="draft",
                mode=_safe_text(payload.get("mode"), 80) or profile.profile_id,
                profile_id=profile.profile_id,
                profile=profile_payload(profile),
                songbook_id=_safe_text(payload.get("songbook_id"), 120) or profile.songbook_id,
                songbook_version=_safe_text(payload.get("songbook_version"), 80) or BUILTIN_SONGBOOK_VERSION,
                require_manual_review=bool(payload.get("require_manual_review", profile.require_manual_review)),
                allow_synthetic_review=bool(payload.get("allow_synthetic_review", profile.allow_synthetic_review)),
                release_ready_profile=bool(payload.get("release_ready_profile", profile.release_ready)),
                min_rating=max(1, min(5, int(payload.get("min_rating", profile.min_rating) or profile.min_rating))),
                require_audio_if_renderer_configured=require_audio,
                renderer_snapshot=_renderer_snapshot(config, sources),
                created_at=now,
                updated_at=now,
            )
            self.save_suite(suite)
            self.append_event(suite.suite_id, "suite_created", {"name": suite.name})
            return suite

    def save_suite(self, suite: AcceptanceSuite, *, touch: bool = True) -> AcceptanceSuite:
        if suite.status not in SUITE_STATUSES:
            raise AcceptanceValidationError(f"Unsupported suite status: {suite.status}.")
        self._recalculate_suite(suite)
        if touch:
            suite.updated_at = now_iso()
        write_json(self.suite_path(suite.suite_id), suite.to_dict())
        return suite

    def list_cases(self, suite_id: str) -> list[AcceptanceCase]:
        if not self.suite_path(suite_id).exists():
            raise AcceptanceNotFoundError(suite_id)
        return self._read_cases(suite_id)

    def _read_cases(self, suite_id: str) -> list[AcceptanceCase]:
        rows: list[AcceptanceCase] = []
        for path in self.cases_dir(suite_id).glob("case-*/case.json"):
            try:
                rows.append(AcceptanceCase.from_dict(read_json(path)))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(rows, key=lambda item: item.case_id)

    def get_case(self, suite_id: str, case_id: str) -> AcceptanceCase:
        path = self.case_path(suite_id, case_id)
        if not path.exists():
            raise AcceptanceNotFoundError(case_id)
        return AcceptanceCase.from_dict(read_json(path))

    def add_case(self, suite_id: str, payload: DomainDocument) -> AcceptanceCase:
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            case_id = self._next_case_id(suite_id)
            now = now_iso()
            request = _request_from_payload(payload)
            source_type = _safe_text(payload.get("source_type"), 80) or ("project_version" if payload.get("project_id") else "generated_request")
            case = AcceptanceCase(
                schema_version=ACCEPTANCE_CASE_SCHEMA_VERSION,
                case_id=case_id,
                suite_id=suite_id,
                name=_safe_text(payload.get("name"), 120) or request.get("title") or f"Acceptance Case {case_id}",
                source_type=source_type,
                status="pending",
                song_id=_optional_text(payload.get("song_id"), 120),
                songbook_id=_optional_text(payload.get("songbook_id"), 120) or suite.songbook_id,
                songbook_version=_optional_text(payload.get("songbook_version"), 80) or suite.songbook_version,
                expectations=_safe_dict(payload.get("expectations")),
                request_summary=_request_summary(request),
                project_id=_optional_text(payload.get("project_id"), 120),
                version_id=_optional_text(payload.get("version_id"), 40),
                created_at=now,
                updated_at=now,
            )
            case_dir = self.case_dir(suite_id, case_id)
            case_dir.mkdir(parents=True, exist_ok=True)
            if request:
                write_json(case_dir / "request.json", request)
            self.save_case(case)
            self.save_suite(suite)
            self.append_event(suite_id, "case_added", {"case_id": case_id, "source_type": source_type})
            return case

    def save_case(self, case: AcceptanceCase, *, touch: bool = True) -> AcceptanceCase:
        if case.status not in CASE_STATUSES:
            raise AcceptanceValidationError(f"Unsupported case status: {case.status}.")
        if touch:
            case.updated_at = now_iso()
        write_json(self.case_path(case.suite_id, case.case_id), case.to_dict())
        return case

    def generate_case(self, suite_id: str, case_id: str, *, render_audio_mode: str = "auto") -> AcceptanceCase:
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            case = self.get_case(suite_id, case_id)
            case_dir = self.case_dir(suite_id, case_id)
            if case.source_type == "project_version":
                self._copy_project_version_artifacts(case)
            else:
                request_path = case_dir / "request.json"
                request_data = read_json(request_path) if request_path.exists() else _default_request(case.name)
                request = SongRequest.from_dict(request_data)
                plan = SongAgent().generate(request)
                render_midi(plan, case_dir / "song.mid")
                write_json(case_dir / "song-plan.json", plan.to_dict())
                write_json(case_dir / "validator-report.json", {"status": "passed", "generated_at": now_iso()})
                write_json(case_dir / "quality.json", _quality_payload(plan))
                case.request_summary = _request_summary(request.to_dict())
                case.job_id = f"acceptance-{suite_id}-{case_id}"
            audio_status = self.render_audio(suite_id, case_id, mode=render_audio_mode, persist=False)["summary"]["audio_status"]
            case.artifacts = _case_artifacts(case_id, audio_exists=(case_dir / "song.wav").exists(), audio_status=audio_status)
            case.status = "generated"
            self.save_case(case)
            self.append_event(suite_id, "case_generated", {"case_id": case_id, "audio_status": audio_status})
            return case

    def render_audio(self, suite_id: str, case_id: str, *, mode: str = "auto", persist: bool = True, config: object | None = None) -> DomainDocument:
        with self.lock:
            mode = str(mode or "auto")
            if mode not in {"auto", "always", "never"}:
                raise AcceptanceValidationError("render_audio mode must be auto, always, or never.")
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            case = self.get_case(suite_id, case_id)
            case_dir = self.case_dir(suite_id, case_id)
            midi_path = case_dir / "song.mid"
            wav_path = case_dir / "song.wav"
            sources: DomainDocument = {}
            if config is None:
                config, sources = load_renderer_config()
            configured = renderer_configured(config)
            result: DomainDocument
            if mode == "never":
                status = "skipped_renderer_not_configured" if not configured else "skipped_by_request"
                result = {"status": "skipped", "summary": {"audio_status": status, "renderer": _renderer_snapshot(config, sources)}}
            elif not configured:
                if mode == "always":
                    raise AcceptanceStateError("Audio renderer is not configured.")
                result = {"status": "skipped", "summary": {"audio_status": "skipped_renderer_not_configured", "renderer": _renderer_snapshot(config, sources)}}
            else:
                try:
                    render_audio(midi_path, wav_path, config)
                    result = {"status": "rendered", "summary": {"audio_status": "rendered", "renderer": _renderer_snapshot(config, sources), "size_bytes": wav_path.stat().st_size}}
                except RendererError as exc:
                    if mode == "always":
                        raise
                    result = {"status": "skipped", "summary": {"audio_status": "render_failed", "error": sanitize_sensitive_text(str(exc)), "renderer": _renderer_snapshot(config, sources)}}
            if persist:
                case.artifacts = _case_artifacts(case_id, audio_exists=wav_path.exists(), audio_status=result["summary"]["audio_status"])
                self.save_case(case)
                self.append_event(suite_id, "case_audio_rendered", {"case_id": case_id, "audio_status": result["summary"]["audio_status"]})
            return sanitize_metadata(result)

    def run_health(self, suite_id: str, case_id: str) -> DomainDocument:
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            case = self.get_case(suite_id, case_id)
            case_dir = self.case_dir(suite_id, case_id)
            plan_path = case_dir / "song-plan.json"
            if not plan_path.exists():
                raise AcceptanceStateError("song-plan.json is missing. Generate the case first.")
            plan = SongPlan.from_dict(read_json(plan_path))
            config, _sources = load_renderer_config()
            audio_required = _suite_requires_audio(suite) or (renderer_configured(config) and suite.require_audio_if_renderer_configured)
            report = analyze_music_health(
                plan,
                case_id=case_id,
                midi_path=case_dir / "song.mid",
                wav_path=case_dir / "song.wav",
                validator_report=_read_optional_json(case_dir / "validator-report.json"),
                quality_report=_read_optional_json(case_dir / "quality.json"),
                renderer_configured=audio_required,
                audio_not_required_status=str(case.artifacts.get("audio_status") or "skipped_renderer_not_configured"),
                now=now_iso(),
            )
            wav_path = case_dir / "song.wav"
            if wav_path.exists() and wav_path.is_file():
                expected_duration = _request_duration_seconds(_read_optional_json(case_dir / "request.json") or case.request_summary)
                audio_report = analyze_wav_health(
                    wav_path,
                    source={"suite_id": suite_id, "case_id": case_id, "song_id": case.song_id, "profile_id": suite.profile_id},
                    expected_duration_seconds=expected_duration,
                    report_id=f"ahr-{case_id}",
                    now=now_iso(),
                )
                write_json(case_dir / "audio-health.json", audio_report)
                report["audio_health"] = audio_health_summary(audio_report)
                artifacts = _as_document(report.get("artifacts"))
                artifacts["audio_health"] = f"cases/{case_id}/audio-health.json"
                report["artifacts"] = artifacts
            write_json(self.health_path(suite_id, case_id), report)
            case.health_summary = music_health_summary(report)
            case.status = "needs_review" if music_health_allows_review(report) else "health_failed"
            self.save_case(case)
            self.append_event(suite_id, "case_health_ran", {"case_id": case_id, "status": report.get("status")})
            return report

    def write_review(self, suite_id: str, case_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            case = self.get_case(suite_id, case_id)
            health = self.read_health(suite_id, case_id, default={})
            if not music_health_allows_review(health) and str(payload.get("status") or "") != "waived":
                raise AcceptanceStateError("Case health has blocking failures. Use waived with a waiver reason or fix the case.")
            review = _review_payload(case_id, payload, min_rating=suite.min_rating)
            if str(review.get("audio_mode") or "").lower() == "wav":
                audio_health = _as_document(health.get("audio_health"))
                if not audio_health or audio_health.get("status") not in {"passed", "warning"}:
                    raise AcceptanceStateError("WAV review requires a passing audio health report.")
                review["audio_evidence"] = sanitize_metadata(
                    {
                        "audio_health_report_id": audio_health.get("report_id"),
                        "audio_health_hash": audio_health.get("integrity_hash"),
                        "wav_sha256": audio_health.get("wav_sha256"),
                    }
                )
            write_json(self.review_path(suite_id, case_id), review)
            case.review_summary = listening_review_summary(review)
            case.status = _case_status_from_review(review)
            self.save_case(case)
            self.append_event(suite_id, "case_review_written", {"case_id": case_id, "status": review.get("status"), "review_mode": review.get("review_mode")})
            return review

    def read_health(self, suite_id: str, case_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.health_path(suite_id, case_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("music-health.json does not exist.")
        return sanitize_metadata(read_json(path))

    def read_review(self, suite_id: str, case_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.review_path(suite_id, case_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("listening-review.json does not exist.")
        return sanitize_metadata(read_json(path))

    def build_report(self, suite_id: str) -> DomainDocument:
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            report = build_acceptance_report(self, suite)
            write_json(self.report_path(suite_id), report)
            self.report_markdown_path(suite_id).write_text(_report_markdown(report), encoding="utf-8")
            suite.latest_report_summary = acceptance_report_summary(report)
            suite.status = "passed" if report.get("status") == "passed" else "failed"
            self.save_suite(suite)
            self.append_event(suite_id, "acceptance_report_built", {"status": report.get("status")})
            return report

    def read_report(self, suite_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.report_path(suite_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("music-acceptance-report.json does not exist.")
        return self.verify_report(suite_id, read_json(path))

    def signoff(self, suite_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            report = self.read_report(suite_id, default={})
            if not report:
                report = self.build_report(suite_id)
            if report.get("status") != "passed":
                raise AcceptanceStateError("Acceptance report must pass before signoff.")
            verification = _as_document(report.get("verification"))
            if verification.get("status") != "passed":
                raise AcceptanceStateError("Acceptance report integrity check must pass before signoff.")
            report_hash = stable_hash(report)
            signoff = sanitize_metadata(
                {
                    "schema_version": ACCEPTANCE_SIGNOFF_SCHEMA_VERSION,
                    "suite_id": suite_id,
                    "status": "signed",
                    "signed_by": _safe_text(payload.get("signed_by"), 120) or "developer",
                    "signed_at": str(payload.get("signed_at") or now_iso()),
                    "notes": _safe_text(payload.get("notes"), 1000),
                    "report_hash": report_hash,
                    "report_summary": acceptance_report_summary(report),
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "payload_hash"})
            write_json(self.signoff_path(suite_id), signoff)
            suite.latest_signoff_summary = acceptance_signoff_summary(signoff)
            suite.status = "signed"
            self.save_suite(suite)
            self.append_event(suite_id, "acceptance_signed", {"status": "signed"})
            return signoff

    def reset_signoff(self, suite_id: str, reason: str) -> DomainDocument:
        with self.lock:
            suite = self.get_suite(suite_id)
            existing = self.read_signoff(suite_id, default={})
            event = sanitize_metadata({"timestamp": now_iso(), "event": "acceptance_signoff_reset", "reason": _safe_text(reason, 500), "previous_summary": acceptance_signoff_summary(existing)})
            if existing:
                path = self.signoff_history_path(suite_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event, ensure_ascii=False) + "\n")
            signoff_path = self.signoff_path(suite_id)
            if signoff_path.exists():
                signoff_path.unlink()
            suite.latest_signoff_summary = {"status": "not_signed"}
            if suite.status == "signed":
                suite.status = suite.latest_report_summary.get("status") or "draft"
            self.save_suite(suite)
            self.append_event(suite_id, "acceptance_signoff_reset", {"reason": event.get("reason")})
            return event

    def read_signoff(self, suite_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.signoff_path(suite_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("acceptance-signoff.json does not exist.")
        signoff = sanitize_metadata(read_json(path))
        report = self.read_report(suite_id, default={})
        expected = str(signoff.get("report_hash") or "")
        actual = stable_hash(report) if report else ""
        signoff["report_integrity"] = {
            "status": "passed" if expected and expected == actual else "failed",
            "expected_report_hash": expected,
            "actual_report_hash": actual,
            "report_verification_status": (report.get("verification") or {}).get("status") if isinstance(report, dict) else "missing",
        }
        return sanitize_metadata(signoff)

    def archive_suite(self, suite_id: str) -> AcceptanceSuite:
        suite = self.get_suite(suite_id)
        self.ensure_mutable(suite)
        suite.status = "archived"
        self.save_suite(suite)
        self.append_event(suite_id, "suite_archived", {})
        return suite
