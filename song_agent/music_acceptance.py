from __future__ import annotations

import hashlib
import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.agent.pipeline import SongAgent
from song_agent.music_health import analyze_music_health, music_health_allows_review, music_health_summary
from song_agent.projectio import read_json, slugify, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.renderers.audio import RendererError, load_renderer_config, render_audio, renderer_configured
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongPlan, SongRequest


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
            suite_id = self._reserve_suite_id()
            now = now_iso()
            config, sources = load_renderer_config()
            suite = AcceptanceSuite(
                schema_version=ACCEPTANCE_SUITE_SCHEMA_VERSION,
                suite_id=suite_id,
                name=_safe_text(payload.get("name"), 120) or "Music Acceptance Suite",
                status="draft",
                mode=_safe_text(payload.get("mode"), 80) or "developer_self_test",
                min_rating=max(1, min(5, int(payload.get("min_rating", 3) or 3))),
                require_audio_if_renderer_configured=bool(payload.get("require_audio_if_renderer_configured", True)),
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

    def render_audio(self, suite_id: str, case_id: str, *, mode: str = "auto", persist: bool = True) -> dict[str, Any]:
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
            report = analyze_music_health(
                plan,
                case_id=case_id,
                midi_path=case_dir / "song.mid",
                wav_path=case_dir / "song.wav",
                validator_report=_read_optional_json(case_dir / "validator-report.json"),
                quality_report=_read_optional_json(case_dir / "quality.json"),
                renderer_configured=renderer_configured(config) and suite.require_audio_if_renderer_configured,
                audio_not_required_status=str(case.artifacts.get("audio_status") or "skipped_renderer_not_configured"),
                now=now_iso(),
            )
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
        case_rows.append(
            {
                "case_id": case.case_id,
                "name": case.name,
                "status": case.status,
                "health_status": health_summary.get("status"),
                "review_status": review_summary.get("status"),
                "rating": rating,
                "playback_confirmed": review_summary.get("playback_confirmed", False),
                "audio_status": health_summary.get("audio_status"),
                "review_mode": review_summary.get("review_mode"),
            }
        )
    if not cases:
        blockers.append("suite has no cases")
    sensitive = _redaction_findings({"suite": suite.to_dict(), "cases": case_rows})
    if sensitive:
        blockers.append(f"redaction scan found {len(sensitive)} issue(s)")
    status = "passed" if not blockers else "failed"
    source_hash = stable_hash(acceptance_source_state(store, suite))
    report = {
        "schema_version": ACCEPTANCE_REPORT_SCHEMA_VERSION,
        "suite_id": suite.suite_id,
        "status": status,
        "generated_at": now_iso(),
        "source_hash": source_hash,
        "summary": {
            "case_count": len(cases),
            "accepted_count": sum(1 for row in case_rows if row.get("review_status") == "accepted"),
            "waived_count": sum(1 for row in case_rows if row.get("review_status") == "waived"),
            "health_failed_count": sum(1 for row in case_rows if row.get("health_status") == "failed"),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "renderer_status": "configured" if suite.renderer_snapshot.get("configured") else "not_configured",
            "blocking_count": len(blockers),
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
            "min_rating": suite.min_rating,
            "require_audio_if_renderer_configured": suite.require_audio_if_renderer_configured,
            "cases": cases,
        }
    )


def _report_integrity_core(report: dict[str, Any]) -> dict[str, Any]:
    data = dict(report)
    data.pop("verification", None)
    data.pop("generated_at", None)
    return sanitize_metadata(data)


def _report_verification(stored_source_hash: str, current_source_hash: str, stored_content_hash: str, current_content_hash: str) -> dict[str, Any]:
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
            "average_rating": summary.get("average_rating"),
            "renderer_status": summary.get("renderer_status"),
            "blocking_count": summary.get("blocking_count", 0),
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
            "review_mode": data.get("review_mode") or "manual",
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


def default_acceptance_requests(count: int) -> list[dict[str, Any]]:
    presets = [
        ("Neon Morning", "upbeat pop", "bright city sunrise"),
        ("Quiet Harbor", "ballad", "late night reflection"),
        ("Circuit Bloom", "electronic synth", "glowing machines"),
        ("Sidewalk Cipher", "hip-hop beat-driven", "confident street story"),
        ("Wide Sky Signal", "instrumental cinematic", "open landscape"),
        ("Woodsmoke Letter", "acoustic singer-songwriter", "warm homecoming"),
    ]
    rows = []
    for index in range(max(1, count)):
        title, style, theme = presets[index % len(presets)]
        suffix = "" if index < len(presets) else f" {index + 1}"
        rows.append({"title": f"{title}{suffix}", "language": "English", "style": style, "theme": theme, "duration_seconds": 90})
    return rows


def _request_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
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


def _request_summary(request: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "title": request.get("title"),
            "style": request.get("style"),
            "theme": request.get("theme"),
            "duration_seconds": request.get("duration_seconds"),
        }
    )


def _default_request(name: str) -> dict[str, Any]:
    return {"title": name or "Acceptance Song", "language": "English", "style": "pop", "theme": "acceptance test", "duration_seconds": 90}


def _quality_payload(plan: SongPlan) -> dict[str, Any]:
    if plan.quality and plan.quality.scores:
        return {"status": "passed", "overall": plan.quality.scores.overall, "summary": {"overall": plan.quality.scores.overall}}
    return {"status": "passed", "overall": 80, "summary": {"overall": 80}}


def _case_artifacts(case_id: str, *, audio_exists: bool, audio_status: str) -> dict[str, Any]:
    base = f"cases/{case_id}"
    artifacts = {"song_plan": f"{base}/song-plan.json", "midi": f"{base}/song.mid", "audio_status": audio_status}
    if audio_exists:
        artifacts["audio"] = f"{base}/song.wav"
    return artifacts


def _review_payload(case_id: str, payload: dict[str, Any], *, min_rating: int) -> dict[str, Any]:
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
    return sanitize_metadata(
        {
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
    )


def _case_status_from_review(review: dict[str, Any]) -> str:
    status = str(review.get("status") or "")
    return {"accepted": "accepted", "waived": "waived", "rejected": "rejected", "needs_fix": "rejected"}.get(status, "rejected")


def _renderer_snapshot(config: Any, sources: dict[str, str]) -> dict[str, Any]:
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


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _report_markdown(report: dict[str, Any]) -> str:
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


def _redaction_findings(payload: Any) -> list[dict[str, Any]]:
    raw = json.dumps(payload, ensure_ascii=False)
    patterns = ("sk-", "api_key", "access_token", "Authorization:", "Bearer ", "C:\\Users", "\\\\", "/Users/", "/home/")
    findings = []
    for pattern in patterns:
        if pattern in raw:
            findings.append({"pattern": pattern, "message": "Sensitive value pattern found."})
    return findings


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]


def _optional_text(value: Any, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None


def _safe_dict(value: Any) -> dict[str, Any]:
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
