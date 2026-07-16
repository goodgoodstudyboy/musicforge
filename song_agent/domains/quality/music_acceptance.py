from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

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


ACCEPTANCE_ROOT = Path(".musicforge") / "acceptance"
ACCEPTANCE_SUITE_SCHEMA_VERSION = 1
ACCEPTANCE_CASE_SCHEMA_VERSION = 1
LISTENING_REVIEW_SCHEMA_VERSION = 1
ACCEPTANCE_REPORT_SCHEMA_VERSION = 1
ACCEPTANCE_SIGNOFF_SCHEMA_VERSION = 1
SUITE_STATUSES = {"draft", "generated", "needs_review", "passed", "failed", "signed", "archived"}
CASE_STATUSES = {"pending", "generated", "health_failed", "needs_review", "accepted", "waived", "rejected"}
SIGNED_ACCEPTANCE_STATUSES = {"signed", "force_signed"}


class AcceptanceError(ValueError):
    pass


class AcceptanceNotFoundError(AcceptanceError):
    pass


class AcceptanceValidationError(AcceptanceError):
    pass


class AcceptanceStateError(AcceptanceError):
    pass


@dataclass
class AcceptanceCase:
    schema_version: int
    case_id: str
    suite_id: str
    name: str
    source_type: str
    status: str
    song_id: str | None = None
    songbook_id: str | None = None
    songbook_version: str | None = None
    expectations: dict[str, Any] = field(default_factory=dict)
    request_summary: dict[str, Any] = field(default_factory=dict)
    job_id: str | None = None
    project_id: str | None = None
    version_id: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    health_summary: dict[str, Any] = field(default_factory=dict)
    review_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "case_id": self.case_id,
                "suite_id": self.suite_id,
                "name": self.name,
                "source_type": self.source_type,
                "status": self.status,
                "song_id": self.song_id,
                "songbook_id": self.songbook_id,
                "songbook_version": self.songbook_version,
                "expectations": self.expectations,
                "request_summary": self.request_summary,
                "job_id": self.job_id,
                "project_id": self.project_id,
                "version_id": self.version_id,
                "artifacts": self.artifacts,
                "health_summary": self.health_summary,
                "review_summary": self.review_summary,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AcceptanceCase":
        created_at = str(data.get("created_at") or now_iso())
        status = str(data.get("status") or "pending")
        if status not in CASE_STATUSES:
            status = "pending"
        return cls(
            schema_version=int(data.get("schema_version") or ACCEPTANCE_CASE_SCHEMA_VERSION),
            case_id=_validate_case_id(str(data.get("case_id") or "case-000001")),
            suite_id=_validate_suite_id(str(data.get("suite_id") or "suite-000001")),
            name=_safe_text(data.get("name"), 120) or "Acceptance Case",
            source_type=_safe_text(data.get("source_type"), 80) or "generated_request",
            status=status,
            song_id=_optional_text(data.get("song_id"), 120),
            songbook_id=_optional_text(data.get("songbook_id"), 120),
            songbook_version=_optional_text(data.get("songbook_version"), 80),
            expectations=_safe_dict(data.get("expectations")),
            request_summary=_safe_dict(data.get("request_summary")),
            job_id=_optional_text(data.get("job_id"), 120),
            project_id=_optional_text(data.get("project_id"), 120),
            version_id=_optional_text(data.get("version_id"), 40),
            artifacts=_safe_dict(data.get("artifacts")),
            health_summary=_safe_dict(data.get("health_summary")),
            review_summary=_safe_dict(data.get("review_summary")),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )


@dataclass
class AcceptanceSuite:
    schema_version: int
    suite_id: str
    name: str
    status: str
    mode: str
    profile_id: str = "developer_manual"
    profile: dict[str, Any] = field(default_factory=dict)
    songbook_id: str = BUILTIN_SONGBOOK_ID
    songbook_version: str = BUILTIN_SONGBOOK_VERSION
    require_manual_review: bool = False
    allow_synthetic_review: bool = True
    release_ready_profile: bool = False
    min_rating: int = 3
    require_audio_if_renderer_configured: bool = True
    case_count: int = 0
    accepted_count: int = 0
    failed_count: int = 0
    renderer_snapshot: dict[str, Any] = field(default_factory=dict)
    latest_report_summary: dict[str, Any] = field(default_factory=dict)
    latest_signoff_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "suite_id": self.suite_id,
                "name": self.name,
                "status": self.status,
                "mode": self.mode,
                "profile_id": self.profile_id,
                "profile": self.profile,
                "songbook_id": self.songbook_id,
                "songbook_version": self.songbook_version,
                "require_manual_review": self.require_manual_review,
                "allow_synthetic_review": self.allow_synthetic_review,
                "release_ready_profile": self.release_ready_profile,
                "min_rating": self.min_rating,
                "require_audio_if_renderer_configured": self.require_audio_if_renderer_configured,
                "case_count": self.case_count,
                "accepted_count": self.accepted_count,
                "failed_count": self.failed_count,
                "renderer_snapshot": self.renderer_snapshot,
                "latest_report_summary": self.latest_report_summary,
                "latest_signoff_summary": self.latest_signoff_summary,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AcceptanceSuite":
        created_at = str(data.get("created_at") or now_iso())
        status = str(data.get("status") or "draft")
        if status not in SUITE_STATUSES:
            status = "draft"
        return cls(
            schema_version=int(data.get("schema_version") or ACCEPTANCE_SUITE_SCHEMA_VERSION),
            suite_id=_validate_suite_id(str(data.get("suite_id") or "suite-000001")),
            name=_safe_text(data.get("name"), 120) or "Music Acceptance Suite",
            status=status,
            mode=_safe_text(data.get("mode"), 80) or "developer_self_test",
            profile_id=_safe_text(data.get("profile_id"), 80) or "developer_manual",
            profile=_safe_dict(data.get("profile")),
            songbook_id=_safe_text(data.get("songbook_id"), 120) or BUILTIN_SONGBOOK_ID,
            songbook_version=_safe_text(data.get("songbook_version"), 80) or BUILTIN_SONGBOOK_VERSION,
            require_manual_review=bool(data.get("require_manual_review", False)),
            allow_synthetic_review=bool(data.get("allow_synthetic_review", True)),
            release_ready_profile=bool(data.get("release_ready_profile", False)),
            min_rating=max(1, min(5, int(data.get("min_rating", 3) or 3))),
            require_audio_if_renderer_configured=bool(data.get("require_audio_if_renderer_configured", True)),
            case_count=int(data.get("case_count", 0) or 0),
            accepted_count=int(data.get("accepted_count", 0) or 0),
            failed_count=int(data.get("failed_count", 0) or 0),
            renderer_snapshot=_safe_dict(data.get("renderer_snapshot")),
            latest_report_summary=_safe_dict(data.get("latest_report_summary")),
            latest_signoff_summary=_safe_dict(data.get("latest_signoff_summary")),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )


class AcceptanceStore:
    def __init__(self, root: Path | str = ACCEPTANCE_ROOT, *, project_store: ProjectStore | None = None) -> None:
        self.root = Path(root).resolve()
        self.project_store = project_store or ProjectStore()
        self.lock = threading.RLock()

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

    def create_suite(self, payload: dict[str, Any] | None = None) -> AcceptanceSuite:
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

    def add_case(self, suite_id: str, payload: dict[str, Any]) -> AcceptanceCase:
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

    def render_audio(self, suite_id: str, case_id: str, *, mode: str = "auto", persist: bool = True, config: Any | None = None) -> dict[str, Any]:
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
            sources = {}
            if config is None:
                config, sources = load_renderer_config()
            configured = renderer_configured(config)
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

    def run_health(self, suite_id: str, case_id: str) -> dict[str, Any]:
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
                artifacts = report.get("artifacts") if isinstance(report.get("artifacts"), dict) else {}
                artifacts["audio_health"] = f"cases/{case_id}/audio-health.json"
                report["artifacts"] = artifacts
            write_json(self.health_path(suite_id, case_id), report)
            case.health_summary = music_health_summary(report)
            case.status = "needs_review" if music_health_allows_review(report) else "health_failed"
            self.save_case(case)
            self.append_event(suite_id, "case_health_ran", {"case_id": case_id, "status": report.get("status")})
            return report

    def write_review(self, suite_id: str, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            case = self.get_case(suite_id, case_id)
            health = self.read_health(suite_id, case_id, default={})
            if not music_health_allows_review(health) and str(payload.get("status") or "") != "waived":
                raise AcceptanceStateError("Case health has blocking failures. Use waived with a waiver reason or fix the case.")
            review = _review_payload(case_id, payload, min_rating=suite.min_rating)
            if str(review.get("audio_mode") or "").lower() == "wav":
                audio_health = health.get("audio_health") if isinstance(health.get("audio_health"), dict) else {}
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

    def read_health(self, suite_id: str, case_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.health_path(suite_id, case_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("music-health.json does not exist.")
        return sanitize_metadata(read_json(path))

    def read_review(self, suite_id: str, case_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.review_path(suite_id, case_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("listening-review.json does not exist.")
        return sanitize_metadata(read_json(path))

    def build_report(self, suite_id: str) -> dict[str, Any]:
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

    def read_report(self, suite_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(suite_id)
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceNotFoundError("music-acceptance-report.json does not exist.")
        return self.verify_report(suite_id, read_json(path))

    def signoff(self, suite_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            suite = self.get_suite(suite_id)
            self.ensure_mutable(suite)
            report = self.read_report(suite_id, default={})
            if not report:
                report = self.build_report(suite_id)
            if report.get("status") != "passed":
                raise AcceptanceStateError("Acceptance report must pass before signoff.")
            verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
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

    def reset_signoff(self, suite_id: str, reason: str) -> dict[str, Any]:
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

    def read_signoff(self, suite_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_report(self, suite_id: str, report: dict[str, Any] | None = None) -> dict[str, Any]:
        report_data = sanitize_metadata(report if isinstance(report, dict) else read_json(self.report_path(suite_id)))
        current = build_acceptance_report(self, self.get_suite(suite_id))
        verification = _report_verification(
            str(report_data.get("source_hash") or ""),
            stable_hash(acceptance_source_state(self, self.get_suite(suite_id))),
            stable_hash(_report_integrity_core(report_data)),
            stable_hash(_report_integrity_core(current)),
        )
        report_data["verification"] = verification
        if verification["status"] != "passed":
            report_data["status"] = "failed"
            blockers = list(report_data.get("blockers", []) if isinstance(report_data.get("blockers"), list) else [])
            if verification["source_status"] != "passed" and "acceptance report source hash mismatch" not in blockers:
                blockers.append("acceptance report source hash mismatch")
            if verification["content_status"] != "passed" and "acceptance report content hash mismatch" not in blockers:
                blockers.append("acceptance report content hash mismatch")
            report_data["blockers"] = blockers
            summary = dict(report_data.get("summary") if isinstance(report_data.get("summary"), dict) else {})
            summary["blocking_count"] = int(summary.get("blocking_count", 0) or 0) + 1
            report_data["summary"] = summary
        return sanitize_metadata(report_data)

    def read_events(self, suite_id: str) -> list[dict[str, Any]]:
        path = self.events_path(suite_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return sanitize_metadata(rows)

    def ensure_mutable(self, suite: AcceptanceSuite) -> None:
        if suite.status == "archived":
            raise AcceptanceStateError("Archived acceptance suites are read-only.")
        if suite.status == "signed" or suite.latest_signoff_summary.get("status") in SIGNED_ACCEPTANCE_STATUSES or self.read_signoff(suite.suite_id, default={}).get("status") in SIGNED_ACCEPTANCE_STATUSES:
            raise AcceptanceStateError("Signed acceptance suites cannot be modified. Reset signoff before changing this suite.")

    def append_event(self, suite_id: str, event_type: str, payload: dict[str, Any]) -> None:
        path = self.events_path(suite_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload})
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _copy_project_version_artifacts(self, case: AcceptanceCase) -> None:
        if not case.project_id or not case.version_id:
            raise AcceptanceValidationError("project_id and version_id are required for project_version cases.")
        document = self.project_store.get_project(case.project_id)
        version = next((item for item in document.versions if item.version_id == case.version_id), None)
        if version is None:
            raise AcceptanceNotFoundError(case.version_id)
        run_dir = Path(version.output_dir)
        case_dir = self.case_dir(case.suite_id, case.case_id)
        required = {
            run_dir / "data" / "song-plan.json": case_dir / "song-plan.json",
            run_dir / "renders" / "song.mid": case_dir / "song.mid",
        }
        for source, target in required.items():
            if not source.exists():
                raise AcceptanceStateError(f"Project version artifact is missing: {source.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for name in ("validator-report.json", "quality.json", "quality-report.json", "run-summary.json"):
            source = run_dir / "data" / name
            if source.exists():
                shutil.copy2(source, case_dir / name)
        audio_source = run_dir / "renders" / "song.wav"
        if audio_source.exists():
            shutil.copy2(audio_source, case_dir / "song.wav")
        case.job_id = version.job_id
        case.request_summary = _request_summary(version.request)

    def _reserve_suite_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            suite_id = f"suite-{index:06d}"
            try:
                (self.root / suite_id).mkdir(parents=True, exist_ok=False)
                return suite_id
            except FileExistsError:
                continue
        raise AcceptanceValidationError("Unable to allocate acceptance suite id.")

    def _next_case_id(self, suite_id: str) -> str:
        used = {case.case_id for case in self.list_cases(suite_id)}
        self.cases_dir(suite_id).mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            case_id = f"case-{index:06d}"
            if case_id not in used:
                return case_id
        raise AcceptanceValidationError("Unable to allocate acceptance case id.")

    def _recalculate_suite(self, suite: AcceptanceSuite) -> None:
        try:
            cases = self._read_cases(suite.suite_id) if self.cases_dir(suite.suite_id).exists() else []
        except AcceptanceNotFoundError:
            cases = []
        suite.case_count = len(cases)
        suite.accepted_count = sum(1 for case in cases if case.status in {"accepted", "waived"})
        suite.failed_count = sum(1 for case in cases if case.status in {"health_failed", "rejected"})


def build_acceptance_report(store: AcceptanceStore, suite: AcceptanceSuite) -> dict[str, Any]:
    cases = store.list_cases(suite.suite_id)
    case_rows = []
    blockers: list[str] = []
    ratings: list[int] = []
    for case in cases:
        health = store.read_health(suite.suite_id, case.case_id, default={})
        review = store.read_review(suite.suite_id, case.case_id, default={})
        health_summary = music_health_summary(health)
        review_summary = listening_review_summary(review)
        rating = review_summary.get("rating")
        review_mode = str(review_summary.get("review_mode") or "manual")
        if isinstance(rating, int):
            ratings.append(rating)
        if not health:
            blockers.append(f"{case.case_id}: missing health report")
        if health_summary.get("blocking_failed", 0):
            blockers.append(f"{case.case_id}: health blocking failures")
        if not review:
            blockers.append(f"{case.case_id}: missing listening review")
        if review and not review_summary.get("playback_confirmed"):
            blockers.append(f"{case.case_id}: playback not confirmed")
        if review and review_summary.get("status") not in {"accepted", "waived"}:
            blockers.append(f"{case.case_id}: review status is {review_summary.get('status')}")
        if review and isinstance(rating, int) and rating < suite.min_rating and review_summary.get("status") != "waived":
            blockers.append(f"{case.case_id}: rating below {suite.min_rating}")
        if review and suite.require_manual_review and review_mode != "manual":
            blockers.append(f"{case.case_id}: manual review required")
        expectation_blockers = _expectation_blockers(case, health_summary)
        blockers.extend(expectation_blockers)
        audio_summary = audio_health_summary(health.get("audio_health") if isinstance(health.get("audio_health"), dict) else {})
        case_rows.append(
            {
                "case_id": case.case_id,
                "song_id": case.song_id,
                "songbook_id": case.songbook_id,
                "songbook_version": case.songbook_version,
                "name": case.name,
                "status": case.status,
                "health_status": health_summary.get("status"),
                "review_status": review_summary.get("status"),
                "rating": rating,
                "playback_confirmed": review_summary.get("playback_confirmed", False),
                "audio_status": health_summary.get("audio_status"),
                "audio_mode": review_summary.get("audio_mode"),
                "audio_health_status": audio_summary.get("status"),
                "audio_health_hash": audio_summary.get("integrity_hash"),
                "audio_evidence_status": _audio_evidence_status(review, health),
                "review_mode": review_mode,
                "review_source_type": (review.get("source") or {}).get("source_type") if isinstance(review.get("source"), dict) else None,
                "review_pack_id": (review.get("source") or {}).get("pack_id") if isinstance(review.get("source"), dict) else None,
                "review_import_id": (review.get("source") or {}).get("import_id") if isinstance(review.get("source"), dict) else None,
                "review_tag_count": len(review.get("tags", [])) if isinstance(review.get("tags"), list) else 0,
                "review_marker_count": len(review.get("markers", [])) if isinstance(review.get("markers"), list) else 0,
                "note_count": health_summary.get("note_count", 0),
                "track_count": health_summary.get("track_count", 0),
                "section_count": health_summary.get("section_count", 0),
                "quality_overall": health_summary.get("quality_overall"),
                "health_blockers": [item.get("check_id") for item in health.get("blockers", []) if isinstance(item, dict)],
                "expectation_blockers": expectation_blockers,
            }
        )
    if not cases:
        blockers.append("suite has no cases")
    sensitive = _redaction_findings({"suite": suite.to_dict(), "cases": case_rows})
    if sensitive:
        blockers.append(f"redaction scan found {len(sensitive)} issue(s)")
    manual_accepted = sum(1 for row in case_rows if row.get("review_status") == "accepted" and row.get("review_mode") == "manual")
    synthetic_accepted = sum(1 for row in case_rows if row.get("review_status") == "accepted" and row.get("review_mode") == "synthetic")
    audio_required = _suite_requires_audio(suite)
    audio_passed = sum(1 for row in case_rows if row.get("audio_health_status") in {"passed", "warning"})
    manual_audio_accepted = sum(1 for row in case_rows if row.get("review_status") == "accepted" and row.get("review_mode") == "manual" and row.get("audio_mode") == "wav" and row.get("audio_evidence_status") == "current")
    if audio_required:
        for row in case_rows:
            if row.get("audio_health_status") not in {"passed", "warning"}:
                blockers.append(f"{row.get('case_id')}: passing WAV audio health required")
            if row.get("review_status") == "accepted" and row.get("audio_mode") != "wav":
                blockers.append(f"{row.get('case_id')}: accepted review must bind WAV audio")
            if row.get("review_status") == "accepted" and row.get("review_mode") == "manual" and row.get("audio_evidence_status") != "current":
                blockers.append(f"{row.get('case_id')}: manual WAV review evidence is stale or missing")
    coverage = _songbook_coverage(case_rows, suite)
    coverage_blockers = _songbook_coverage_blockers(coverage, suite)
    blockers.extend(coverage_blockers)
    acceptance_status = _acceptance_status(
        blockers=blockers,
        case_count=len(cases),
        manual_accepted=manual_accepted,
        synthetic_accepted=synthetic_accepted,
        suite=suite,
        songbook_coverage_status=coverage["songbook_coverage_status"],
    )
    status = "passed" if not blockers else "failed"
    source_hash = stable_hash(acceptance_source_state(store, suite))
    human_review_pack = _human_review_evidence_summary(store, suite.suite_id)
    report = {
        "schema_version": ACCEPTANCE_REPORT_SCHEMA_VERSION,
        "suite_id": suite.suite_id,
        "status": status,
        "generated_at": now_iso(),
        "source_hash": source_hash,
        "profile": suite.profile,
        "profile_id": suite.profile_id,
        "songbook_id": suite.songbook_id,
        "songbook_version": suite.songbook_version,
        "summary": {
            "case_count": len(cases),
            "accepted_count": sum(1 for row in case_rows if row.get("review_status") == "accepted"),
            "waived_count": sum(1 for row in case_rows if row.get("review_status") == "waived"),
            "health_failed_count": sum(1 for row in case_rows if row.get("health_status") == "failed"),
            "manual_accepted_count": manual_accepted,
            "synthetic_accepted_count": synthetic_accepted,
            "audio_required": audio_required,
            "audio_passed_count": audio_passed,
            "manual_audio_accepted_count": manual_audio_accepted,
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "renderer_status": "configured" if suite.renderer_snapshot.get("configured") else "not_configured",
            "blocking_count": len(blockers),
            "acceptance_status": acceptance_status,
            "release_ready": acceptance_status == "release_ready_passed",
            "manual_required": suite.require_manual_review,
            "expected_case_count": coverage["expected_case_count"],
            "missing_song_ids": coverage["missing_song_ids"],
            "duplicate_song_ids": coverage["duplicate_song_ids"],
            "songbook_coverage_status": coverage["songbook_coverage_status"],
            "human_review_pack": human_review_pack,
        },
        "cases": case_rows,
        "blockers": blockers,
        "signoff": {"status": "not_signed"},
        "redaction_summary": {"status": "failed" if sensitive else "passed", "findings": sensitive[:20]},
    }
    report["verification"] = _report_verification(source_hash, source_hash, stable_hash(_report_integrity_core(report)), stable_hash(_report_integrity_core(report)))
    return sanitize_metadata(report)


def acceptance_source_state(store: AcceptanceStore, suite: AcceptanceSuite) -> dict[str, Any]:
    cases = []
    for case in store.list_cases(suite.suite_id):
        cases.append(
            {
                "case_id": case.case_id,
                "name": case.name,
                "source_type": case.source_type,
                "status": case.status,
                "song_id": case.song_id,
                "songbook_id": case.songbook_id,
                "songbook_version": case.songbook_version,
                "expectations": case.expectations,
                "request_summary": case.request_summary,
                "artifacts": case.artifacts,
                "health": store.read_health(suite.suite_id, case.case_id, default={}),
                "review": store.read_review(suite.suite_id, case.case_id, default={}),
            }
        )
    return sanitize_metadata(
        {
            "suite_id": suite.suite_id,
            "name": suite.name,
            "mode": suite.mode,
            "profile_id": suite.profile_id,
            "songbook_id": suite.songbook_id,
            "songbook_version": suite.songbook_version,
            "min_rating": suite.min_rating,
            "require_audio_if_renderer_configured": suite.require_audio_if_renderer_configured,
            "require_manual_review": suite.require_manual_review,
            "allow_synthetic_review": suite.allow_synthetic_review,
            "release_ready_profile": suite.release_ready_profile,
            "cases": cases,
        }
    )


def _report_integrity_core(report: ImplementationDocument) -> ImplementationDocument:
    data = dict(report)
    data.pop("verification", None)
    data.pop("generated_at", None)
    return sanitize_metadata(data)


def _report_verification(stored_source_hash: str, current_source_hash: str, stored_content_hash: str, current_content_hash: str) -> ImplementationDocument:
    source_ok = bool(stored_source_hash) and stored_source_hash == current_source_hash
    content_ok = bool(stored_content_hash) and stored_content_hash == current_content_hash
    return sanitize_metadata(
        {
            "status": "passed" if source_ok and content_ok else "failed",
            "source_status": "passed" if source_ok else "failed",
            "content_status": "passed" if content_ok else "failed",
            "stored_source_hash": stored_source_hash,
            "current_source_hash": current_source_hash,
            "stored_content_hash": stored_content_hash,
            "current_content_hash": current_content_hash,
        }
    )


def acceptance_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "suite_id": data.get("suite_id"),
            "case_count": summary.get("case_count", 0),
            "accepted_count": summary.get("accepted_count", 0),
            "waived_count": summary.get("waived_count", 0),
            "health_failed_count": summary.get("health_failed_count", 0),
            "manual_accepted_count": summary.get("manual_accepted_count", 0),
            "synthetic_accepted_count": summary.get("synthetic_accepted_count", 0),
            "audio_required": bool(summary.get("audio_required", False)),
            "audio_passed_count": summary.get("audio_passed_count", 0),
            "manual_audio_accepted_count": summary.get("manual_audio_accepted_count", 0),
            "average_rating": summary.get("average_rating"),
            "renderer_status": summary.get("renderer_status"),
            "blocking_count": summary.get("blocking_count", 0),
            "acceptance_status": summary.get("acceptance_status") or data.get("status") or "missing",
            "release_ready": bool(summary.get("release_ready", False)),
            "expected_case_count": summary.get("expected_case_count", 0),
            "missing_song_ids": summary.get("missing_song_ids", []),
            "duplicate_song_ids": summary.get("duplicate_song_ids", []),
            "songbook_coverage_status": summary.get("songbook_coverage_status") or "not_applicable",
            "human_review_pack": summary.get("human_review_pack") if isinstance(summary.get("human_review_pack"), dict) else {"status": "missing", "pack_count": 0, "import_count": 0},
            "profile_id": data.get("profile_id"),
            "songbook_id": data.get("songbook_id"),
            "songbook_version": data.get("songbook_version"),
        }
    )


def listening_review_summary(review: dict[str, Any] | None) -> dict[str, Any]:
    data = review if isinstance(review, dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "rating": data.get("rating"),
            "playback_confirmed": bool(data.get("playback_confirmed", False)),
            "listened_by": data.get("listened_by"),
            "listened_at": data.get("listened_at"),
            "audio_mode": data.get("audio_mode"),
            "audio_evidence": data.get("audio_evidence") if isinstance(data.get("audio_evidence"), dict) else {},
            "review_mode": data.get("review_mode") or "manual",
            "review_source_type": (data.get("source") or {}).get("source_type") if isinstance(data.get("source"), dict) else None,
            "review_pack_id": (data.get("source") or {}).get("pack_id") if isinstance(data.get("source"), dict) else None,
            "review_import_id": (data.get("source") or {}).get("import_id") if isinstance(data.get("source"), dict) else None,
            "tag_count": len(data.get("tags", [])) if isinstance(data.get("tags"), list) else 0,
            "marker_count": len(data.get("markers", [])) if isinstance(data.get("markers"), list) else 0,
        }
    )


def acceptance_signoff_summary(signoff: dict[str, Any] | None) -> dict[str, Any]:
    data = signoff if isinstance(signoff, dict) else {}
    return sanitize_metadata({"status": data.get("status") or "not_signed", "signed_by": data.get("signed_by"), "signed_at": data.get("signed_at"), "report_hash": data.get("report_hash")})


def acceptance_suite_summary(suite: AcceptanceSuite | dict[str, Any] | None) -> dict[str, Any]:
    data = suite.to_dict() if isinstance(suite, AcceptanceSuite) else suite if isinstance(suite, dict) else {}
    return sanitize_metadata(
        {
            "suite_id": data.get("suite_id"),
            "name": data.get("name"),
            "status": data.get("status") or "missing",
            "profile_id": data.get("profile_id"),
            "songbook_id": data.get("songbook_id"),
            "songbook_version": data.get("songbook_version"),
            "case_count": data.get("case_count", 0),
            "accepted_count": data.get("accepted_count", 0),
            "failed_count": data.get("failed_count", 0),
            "report_status": (data.get("latest_report_summary") or {}).get("status") if isinstance(data.get("latest_report_summary"), dict) else None,
            "signoff_status": (data.get("latest_signoff_summary") or {}).get("status") if isinstance(data.get("latest_signoff_summary"), dict) else None,
            "updated_at": data.get("updated_at"),
        }
    )


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def acceptance_profile_payload(profile_id: str | None) -> dict[str, Any]:
    return profile_payload(get_acceptance_profile(profile_id))


def default_acceptance_requests(count: int) -> list[dict[str, Any]]:
    return [song["request"] for song in default_acceptance_song_cases(count)]


def default_acceptance_song_cases(count: int) -> list[dict[str, Any]]:
    songs = list_regression_songs()
    rows = []
    for index in range(max(1, count)):
        song = dict(songs[index % len(songs)])
        if index >= len(songs):
            song["song_id"] = f"{song['song_id']}_{index + 1}"
            song["title"] = f"{song['title']} {index + 1}"
            song["request"] = {**song["request"], "title": song["title"]}
        rows.append(song)
    return rows


def _request_from_payload(payload: ImplementationDocument) -> ImplementationDocument:
    request = payload.get("request")
    if isinstance(request, dict):
        return sanitize_metadata(dict(request))
    if payload.get("title") or payload.get("style") or payload.get("theme"):
        return sanitize_metadata(
            {
                "title": payload.get("title") or payload.get("name") or "Acceptance Song",
                "language": payload.get("language") or "English",
                "style": payload.get("style") or "pop",
                "theme": payload.get("theme") or "acceptance test",
                "duration_seconds": int(payload.get("duration_seconds", 90) or 90),
            }
        )
    return {}


def _request_summary(request: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "title": request.get("title"),
            "style": request.get("style"),
            "theme": request.get("theme"),
            "duration_seconds": request.get("duration_seconds"),
        }
    )


def _default_request(name: str) -> ImplementationDocument:
    return {"title": name or "Acceptance Song", "language": "English", "style": "pop", "theme": "acceptance test", "duration_seconds": 90}


def _quality_payload(plan: SongPlan) -> ImplementationDocument:
    if plan.quality and plan.quality.scores:
        return {"status": "passed", "overall": plan.quality.scores.overall, "summary": {"overall": plan.quality.scores.overall}}
    return {"status": "passed", "overall": 80, "summary": {"overall": 80}}


def _case_artifacts(case_id: str, *, audio_exists: bool, audio_status: str) -> ImplementationDocument:
    base = f"cases/{case_id}"
    artifacts = {"song_plan": f"{base}/song-plan.json", "midi": f"{base}/song.mid", "audio_status": audio_status}
    if audio_exists:
        artifacts["audio"] = f"{base}/song.wav"
    return artifacts


def _review_payload(case_id: str, payload: ImplementationDocument, *, min_rating: int) -> ImplementationDocument:
    status = str(payload.get("status") or "accepted")
    if status not in {"accepted", "needs_fix", "rejected", "waived"}:
        raise AcceptanceValidationError("review status must be accepted, needs_fix, rejected, or waived.")
    rating = int(payload.get("rating", 0) or 0)
    if rating < 1 or rating > 5:
        raise AcceptanceValidationError("rating must be between 1 and 5.")
    playback_confirmed = bool(payload.get("playback_confirmed", False))
    if status == "accepted" and not playback_confirmed:
        raise AcceptanceValidationError("accepted review requires playback_confirmed=true.")
    notes = _safe_text(payload.get("notes"), 2000)
    if len(notes.strip()) < 10:
        raise AcceptanceValidationError("review notes must be at least 10 characters.")
    waivers = payload.get("waivers") if isinstance(payload.get("waivers"), list) else []
    if status == "waived" and not waivers and not _safe_text(payload.get("waiver_reason"), 500):
        raise AcceptanceValidationError("waived review requires a waiver reason.")
    if status == "accepted" and rating < min_rating:
        raise AcceptanceValidationError(f"accepted review requires rating >= {min_rating}.")
    review = {
            "schema_version": LISTENING_REVIEW_SCHEMA_VERSION,
            "case_id": case_id,
            "status": status,
            "rating": rating,
            "playback_confirmed": playback_confirmed,
            "listened_by": _safe_text(payload.get("listened_by"), 120) or "developer",
            "listened_at": str(payload.get("listened_at") or now_iso()),
            "audio_mode": _safe_text(payload.get("audio_mode"), 40) or "midi",
            "notes": notes,
            "issues": [_safe_text(item, 300) for item in payload.get("issues", []) if str(item).strip()] if isinstance(payload.get("issues"), list) else [],
            "waivers": [_safe_text(item, 500) for item in waivers if str(item).strip()] or ([_safe_text(payload.get("waiver_reason"), 500)] if payload.get("waiver_reason") else []),
            "review_mode": _safe_text(payload.get("review_mode"), 40) or "manual",
    }
    if isinstance(payload.get("source"), dict):
        review["source"] = sanitize_metadata(
            {
                "source_type": _safe_text(payload["source"].get("source_type"), 80),
                "pack_id": _safe_text(payload["source"].get("pack_id"), 80),
                "import_id": _safe_text(payload["source"].get("import_id"), 80),
                "reviewer_id": _safe_text(payload["source"].get("reviewer_id"), 80),
                "organization": _safe_text(payload["source"].get("organization"), 120),
            }
        )
    if isinstance(payload.get("tags"), list):
        review["tags"] = [_safe_text(item, 80) for item in payload.get("tags", []) if str(item).strip()][:40]
    if isinstance(payload.get("markers"), list):
        markers = []
        for marker in payload.get("markers", [])[:100]:
            if not isinstance(marker, dict):
                continue
            markers.append(
                sanitize_metadata(
                    {
                        "beat": marker.get("beat"),
                        "time_seconds": marker.get("time_seconds"),
                        "severity": _safe_text(marker.get("severity"), 40) or "note",
                        "label": _safe_text(marker.get("label"), 120),
                        "note": _safe_text(marker.get("note"), 500),
                    }
                )
            )
        review["markers"] = markers
    return sanitize_metadata(review)


def _case_status_from_review(review: ImplementationDocument) -> str:
    status = str(review.get("status") or "")
    return {"accepted": "accepted", "waived": "waived", "rejected": "rejected", "needs_fix": "rejected"}.get(status, "rejected")


def _suite_requires_audio(suite: AcceptanceSuite) -> bool:
    profile = suite.profile if isinstance(suite.profile, dict) else {}
    return suite.profile_id == "audio_required" or str(profile.get("profile_id") or "") == "audio_required" or str(profile.get("render_audio") or "") in {"always", "require"}


def _request_duration_seconds(request: ImplementationDocument) -> float | None:
    try:
        value = float((request or {}).get("duration_seconds") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _audio_evidence_status(review: ImplementationDocument, health: ImplementationDocument) -> str:
    if not review:
        return "missing"
    if str(review.get("audio_mode") or "").lower() != "wav":
        return "not_wav"
    evidence = review.get("audio_evidence") if isinstance(review.get("audio_evidence"), dict) else {}
    summary = audio_health_summary(health.get("audio_health") if isinstance(health.get("audio_health"), dict) else {})
    if not evidence or not summary:
        return "missing"
    if evidence.get("audio_health_hash") != summary.get("integrity_hash") or evidence.get("wav_sha256") != summary.get("wav_sha256"):
        return "stale"
    return "current"


def _profile_from_payload(payload: ImplementationDocument) -> AcceptanceProfile:
    if isinstance(payload.get("profile"), dict) and payload["profile"].get("profile_id"):
        return get_acceptance_profile(str(payload["profile"].get("profile_id")))
    profile_id = str(payload.get("profile_id") or "").strip()
    if profile_id:
        return get_acceptance_profile(profile_id)
    mode = str(payload.get("mode") or "").strip()
    legacy_modes = {"", "developer_self_test", "release_review"}
    return get_acceptance_profile("developer_manual" if mode in legacy_modes else mode)


def _expectation_blockers(case: AcceptanceCase, health_summary: ImplementationDocument) -> list[str]:
    expectations = case.expectations if isinstance(case.expectations, dict) else {}
    blockers: list[str] = []
    minimums = (
        ("note_count_min", "note_count", "note count"),
        ("tracks_min", "track_count", "track count"),
        ("sections_min", "section_count", "section count"),
        ("quality_min", "quality_overall", "quality"),
    )
    for expectation_key, summary_key, label in minimums:
        expected = expectations.get(expectation_key)
        actual = health_summary.get(summary_key)
        if isinstance(expected, (int, float)) and (not isinstance(actual, (int, float)) or actual < expected):
            blockers.append(f"{case.case_id}: {label} below expected {expected}")
    return blockers


def _songbook_coverage(case_rows: list[ImplementationDocument], suite: AcceptanceSuite) -> ImplementationDocument:
    if not suite.release_ready_profile:
        return {
            "expected_case_count": 0,
            "missing_song_ids": [],
            "duplicate_song_ids": [],
            "songbook_coverage_status": "not_applicable",
        }
    profile = get_acceptance_profile(suite.profile_id)
    expected_song_ids = [str(song.get("song_id") or "") for song in list_regression_songs(profile.case_count)]
    expected_song_ids = [song_id for song_id in expected_song_ids if song_id]
    seen: dict[str, int] = {}
    manual_accepted_song_ids: set[str] = set()
    for row in case_rows:
        song_id = str(row.get("song_id") or "").strip()
        if not song_id:
            continue
        seen[song_id] = seen.get(song_id, 0) + 1
        if row.get("review_status") == "accepted" and row.get("review_mode") == "manual":
            manual_accepted_song_ids.add(song_id)
    duplicate_song_ids = sorted(song_id for song_id, count in seen.items() if count > 1)
    missing_song_ids = [song_id for song_id in expected_song_ids if song_id not in manual_accepted_song_ids]
    expected_set = set(expected_song_ids)
    complete = (
        len(case_rows) >= profile.case_count
        and not missing_song_ids
        and not duplicate_song_ids
        and all(song_id in expected_set for song_id in seen)
    )
    return sanitize_metadata(
        {
            "expected_case_count": profile.case_count,
            "case_count": len(case_rows),
            "missing_song_ids": missing_song_ids,
            "duplicate_song_ids": duplicate_song_ids,
            "songbook_coverage_status": "complete" if complete else "incomplete",
        }
    )


def _songbook_coverage_blockers(coverage: ImplementationDocument, suite: AcceptanceSuite) -> list[str]:
    if not suite.release_ready_profile or coverage.get("songbook_coverage_status") == "complete":
        return []
    blockers = ["release-ready profile requires complete regression songbook coverage"]
    missing = coverage.get("missing_song_ids") if isinstance(coverage.get("missing_song_ids"), list) else []
    duplicates = coverage.get("duplicate_song_ids") if isinstance(coverage.get("duplicate_song_ids"), list) else []
    expected = int(coverage.get("expected_case_count", 0) or 0)
    if expected and int(coverage.get("case_count", 0) or 0) < expected:
        blockers.append(f"case count below expected {expected}")
    if missing:
        blockers.append("missing song ids: " + ", ".join(str(item) for item in missing[:12]))
    if duplicates:
        blockers.append("duplicate song ids: " + ", ".join(str(item) for item in duplicates[:12]))
    return blockers


def _acceptance_status(
    *,
    blockers: list[str],
    case_count: int,
    manual_accepted: int,
    synthetic_accepted: int,
    suite: AcceptanceSuite,
    songbook_coverage_status: str = "not_applicable",
) -> str:
    if blockers:
        return "failed"
    if suite.release_ready_profile:
        complete = songbook_coverage_status == "complete"
        return "release_ready_passed" if complete and manual_accepted == case_count and case_count > 0 else "manual_required"
    if manual_accepted == case_count and case_count > 0:
        return "manual_passed"
    if synthetic_accepted == case_count and case_count > 0:
        return "synthetic_passed"
    return "passed"


def _renderer_snapshot(config: Any, sources: dict[str, str]) -> ImplementationDocument:
    public = config.to_public_dict(sources)
    return sanitize_metadata(
        {
            "configured": renderer_configured(config),
            "renderer_type": public.get("renderer_type"),
            "soundfont_exists": public.get("soundfont_exists"),
            "soundfont_warning": public.get("soundfont_warning"),
            "sources": public.get("sources"),
        }
    )


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _report_markdown(report: ImplementationDocument) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Music Acceptance Report",
        "",
        f"- Suite: {report.get('suite_id')}",
        f"- Status: {report.get('status')}",
        f"- Cases: {summary.get('case_count', 0)}",
        f"- Accepted: {summary.get('accepted_count', 0)}",
        f"- Average rating: {summary.get('average_rating')}",
        "",
        "| Case | Health | Review | Rating | Audio |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in report.get("cases", []):
        if isinstance(case, dict):
            lines.append(f"| {case.get('case_id')} | {case.get('health_status')} | {case.get('review_status')} | {case.get('rating')} | {case.get('audio_status')} |")
    lines.append("")
    return "\n".join(lines)


def _redaction_findings(payload: Any) -> list[ImplementationDocument]:
    raw = json.dumps(payload, ensure_ascii=False)
    patterns = ("sk-", "api_key", "access_token", "Authorization:", "Bearer ", "C:\\Users", "\\\\", "/Users/", "/home/")
    findings = []
    for pattern in patterns:
        if pattern in raw:
            findings.append({"pattern": pattern, "message": "Sensitive value pattern found."})
    return findings


def _human_review_evidence_summary(store: AcceptanceStore, suite_id: str) -> ImplementationDocument:
    try:
        suite_dir = store.suite_dir(suite_id)
        packs = [
            read_json(path)
            for path in (suite_dir / "human-review-packs").glob("hrpack-*/pack.json")
        ]
        imports = [
            read_json(path)
            for path in (suite_dir / "review-imports").glob("review-import-*/review-import.json")
        ]
        packs = sorted(packs, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
        imports = sorted(imports, key=lambda row: str(row.get("imported_at") or row.get("created_at") or ""), reverse=True)
        latest_pack = packs[0] if packs else {}
        latest_import = imports[0] if imports else {}
        summary = latest_import.get("summary") if isinstance(latest_import.get("summary"), dict) else {}
        return sanitize_metadata(
            {
                "status": "imported" if latest_import else "packaged" if latest_pack else "missing",
                "pack_count": len(packs),
                "import_count": len(imports),
                "latest_pack_id": latest_pack.get("pack_id"),
                "latest_pack_status": latest_pack.get("status"),
                "latest_import_id": latest_import.get("import_id"),
                "accepted_count": summary.get("accepted_count", 0),
                "needs_fix_count": summary.get("needs_fix_count", 0),
                "rejected_count": summary.get("rejected_count", 0),
                "created_review_task_count": summary.get("created_review_task_count", 0),
            }
        )
    except Exception:
        return {"status": "missing", "pack_count": 0, "import_count": 0}


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]


def _optional_text(value: Any, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None


def _safe_dict(value: Any) -> ImplementationDocument:
    return sanitize_metadata(dict(value)) if isinstance(value, dict) else {}


def _validate_suite_id(value: str) -> str:
    value = str(value or "").strip()
    if not value.startswith("suite-") or not value.removeprefix("suite-").isdigit():
        raise AcceptanceValidationError("Invalid suite_id.")
    return value


def _validate_case_id(value: str) -> str:
    value = str(value or "").strip()
    if not value.startswith("case-") or not value.removeprefix("case-").isdigit():
        raise AcceptanceValidationError("Invalid case_id.")
    return value
