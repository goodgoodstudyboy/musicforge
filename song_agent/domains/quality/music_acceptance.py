# ruff: noqa: E402,F401
from __future__ import annotations


from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

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
from song_agent.domains.quality.v142_ma_readiness import AcceptanceStoreReadinessMixin
from song_agent.domains.quality import v142_ma_readiness as _v142_ma_readiness
from song_agent.domains.quality.v142_ma_evidence import AcceptanceStoreEvidenceMixin
from song_agent.domains.quality import v142_ma_evidence as _v142_ma_evidence



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
    expectations: ImplementationDocument = field(default_factory=dict)
    request_summary: ImplementationDocument = field(default_factory=dict)
    job_id: str | None = None
    project_id: str | None = None
    version_id: str | None = None
    artifacts: ImplementationDocument = field(default_factory=dict)
    health_summary: ImplementationDocument = field(default_factory=dict)
    review_summary: ImplementationDocument = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "AcceptanceCase":
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
    profile: ImplementationDocument = field(default_factory=dict)
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
    renderer_snapshot: ImplementationDocument = field(default_factory=dict)
    latest_report_summary: ImplementationDocument = field(default_factory=dict)
    latest_signoff_summary: ImplementationDocument = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "AcceptanceSuite":
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


class AcceptanceStore(AcceptanceStoreReadinessMixin, AcceptanceStoreEvidenceMixin):
    def __init__(self, root: Path | str = ACCEPTANCE_ROOT, *, project_store: ProjectStore | None = None) -> None:
        self.root = Path(root).resolve()
        self.project_store = project_store or ProjectStore()
        self.lock = threading.RLock()













































def build_acceptance_report(store: AcceptanceStore, suite: AcceptanceSuite) -> DomainDocument:
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
        audio_summary = audio_health_summary(_as_document(health.get("audio_health")))
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


def acceptance_source_state(store: AcceptanceStore, suite: AcceptanceSuite) -> DomainDocument:
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


from song_agent.domains.quality import v142_ma_readiness_2 as _v142_ma_readiness_2
from song_agent.domains.quality.v142_ma_readiness_2 import acceptance_report_summary as acceptance_report_summary, listening_review_summary as listening_review_summary, acceptance_signoff_summary as acceptance_signoff_summary, acceptance_suite_summary as acceptance_suite_summary, stable_hash as stable_hash, acceptance_profile_payload as acceptance_profile_payload, default_acceptance_requests as default_acceptance_requests, default_acceptance_song_cases as default_acceptance_song_cases, _request_from_payload as _request_from_payload, _request_summary as _request_summary, _default_request as _default_request, _quality_payload as _quality_payload, _case_artifacts as _case_artifacts, _review_payload as _review_payload, _case_status_from_review as _case_status_from_review, _suite_requires_audio as _suite_requires_audio, _request_duration_seconds as _request_duration_seconds, _audio_evidence_status as _audio_evidence_status, _profile_from_payload as _profile_from_payload, _expectation_blockers as _expectation_blockers, _songbook_coverage as _songbook_coverage, _songbook_coverage_blockers as _songbook_coverage_blockers, _acceptance_status as _acceptance_status, _renderer_snapshot as _renderer_snapshot, _read_optional_json as _read_optional_json, _report_markdown as _report_markdown, _redaction_findings as _redaction_findings, _human_review_evidence_summary as _human_review_evidence_summary, _safe_text as _safe_text, _optional_text as _optional_text, _safe_dict as _safe_dict, _validate_suite_id as _validate_suite_id
from song_agent.domains.quality import v142_ma_evidence_2 as _v142_ma_evidence_2
from song_agent.domains.quality.v142_ma_evidence_2 import _validate_case_id as _validate_case_id


































































_v142_ma_readiness.bind_globals(globals())
_v142_ma_evidence.bind_globals(globals())

_v142_ma_readiness_2.bind_globals(globals())
_v142_ma_evidence_2.bind_globals(globals())
