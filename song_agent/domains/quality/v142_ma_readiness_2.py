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
from song_agent.domains.quality.v142_ma_readiness import AcceptanceStoreReadinessMixin
from song_agent.domains.quality import v142_ma_readiness as _v142_ma_readiness
from song_agent.domains.quality.v142_ma_evidence import AcceptanceStoreEvidenceMixin
from song_agent.domains.quality import v142_ma_evidence as _v142_ma_evidence

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
AcceptanceStore = _make_deferred_global('AcceptanceStore')
AcceptanceSuite = _make_deferred_global('AcceptanceSuite')
AcceptanceValidationError = _make_deferred_global('AcceptanceValidationError')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceCase, AcceptanceStore, AcceptanceSuite, AcceptanceValidationError, item
    AcceptanceCase = namespace.get('AcceptanceCase', AcceptanceCase)
    AcceptanceStore = namespace.get('AcceptanceStore', AcceptanceStore)
    AcceptanceSuite = namespace.get('AcceptanceSuite', AcceptanceSuite)
    AcceptanceValidationError = namespace.get('AcceptanceValidationError', AcceptanceValidationError)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_SUITE_SCHEMA_VERSION = 1
ACCEPTANCE_CASE_SCHEMA_VERSION = 1
LISTENING_REVIEW_SCHEMA_VERSION = 1
ACCEPTANCE_REPORT_SCHEMA_VERSION = 1
ACCEPTANCE_SIGNOFF_SCHEMA_VERSION = 1
SUITE_STATUSES = {"draft", "generated", "needs_review", "passed", "failed", "signed", "archived"}
CASE_STATUSES = {"pending", "generated", "health_failed", "needs_review", "accepted", "waived", "rejected"}
SIGNED_ACCEPTANCE_STATUSES = {"signed", "force_signed"}




def acceptance_report_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
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
            "human_review_pack": _document_or(summary.get("human_review_pack"), {"status": "missing", "pack_count": 0, "import_count": 0}),
            "profile_id": data.get("profile_id"),
            "songbook_id": data.get("songbook_id"),
            "songbook_version": data.get("songbook_version"),
        }
    )

def listening_review_summary(review: DomainDocument | None) -> DomainDocument:
    data = _as_document(review)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "rating": data.get("rating"),
            "playback_confirmed": bool(data.get("playback_confirmed", False)),
            "listened_by": data.get("listened_by"),
            "listened_at": data.get("listened_at"),
            "audio_mode": data.get("audio_mode"),
            "audio_evidence": _as_document(data.get("audio_evidence")),
            "review_mode": data.get("review_mode") or "manual",
            "review_source_type": (data.get("source") or {}).get("source_type") if isinstance(data.get("source"), dict) else None,
            "review_pack_id": (data.get("source") or {}).get("pack_id") if isinstance(data.get("source"), dict) else None,
            "review_import_id": (data.get("source") or {}).get("import_id") if isinstance(data.get("source"), dict) else None,
            "tag_count": len(data.get("tags", [])) if isinstance(data.get("tags"), list) else 0,
            "marker_count": len(data.get("markers", [])) if isinstance(data.get("markers"), list) else 0,
        }
    )

def acceptance_signoff_summary(signoff: DomainDocument | None) -> DomainDocument:
    data = _as_document(signoff)
    return sanitize_metadata({"status": data.get("status") or "not_signed", "signed_by": data.get("signed_by"), "signed_at": data.get("signed_at"), "report_hash": data.get("report_hash")})

def acceptance_suite_summary(suite: AcceptanceSuite | DomainDocument | None) -> DomainDocument:
    data = suite.to_dict() if isinstance(suite, AcceptanceSuite) else _as_document(suite)
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

def stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def acceptance_profile_payload(profile_id: str | None) -> DomainDocument:
    return profile_payload(get_acceptance_profile(profile_id))

def default_acceptance_requests(count: int) -> list[DomainDocument]:
    return [song["request"] for song in default_acceptance_song_cases(count)]

def default_acceptance_song_cases(count: int) -> list[DomainDocument]:
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

def _request_from_payload(payload: DomainDocument) -> DomainDocument:
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

def _request_summary(request: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "title": request.get("title"),
            "style": request.get("style"),
            "theme": request.get("theme"),
            "duration_seconds": request.get("duration_seconds"),
        }
    )

def _default_request(name: str) -> DomainDocument:
    return {"title": name or "Acceptance Song", "language": "English", "style": "pop", "theme": "acceptance test", "duration_seconds": 90}

def _quality_payload(plan: SongPlan) -> DomainDocument:
    if plan.quality and plan.quality.scores:
        return {"status": "passed", "overall": plan.quality.scores.overall, "summary": {"overall": plan.quality.scores.overall}}
    return {"status": "passed", "overall": 80, "summary": {"overall": 80}}

def _case_artifacts(case_id: str, *, audio_exists: bool, audio_status: str) -> DomainDocument:
    base = f"cases/{case_id}"
    artifacts = {"song_plan": f"{base}/song-plan.json", "midi": f"{base}/song.mid", "audio_status": audio_status}
    if audio_exists:
        artifacts["audio"] = f"{base}/song.wav"
    return artifacts

def _review_payload(case_id: str, payload: DomainDocument, *, min_rating: int) -> DomainDocument:
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
    waivers = _as_list(payload.get("waivers"))
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

def _case_status_from_review(review: DomainDocument) -> str:
    status = str(review.get("status") or "")
    return {"accepted": "accepted", "waived": "waived", "rejected": "rejected", "needs_fix": "rejected"}.get(status, "rejected")

def _suite_requires_audio(suite: AcceptanceSuite) -> bool:
    profile = _as_document(suite.profile)
    return suite.profile_id == "audio_required" or str(profile.get("profile_id") or "") == "audio_required" or str(profile.get("render_audio") or "") in {"always", "require"}

def _request_duration_seconds(request: DomainDocument) -> float | None:
    try:
        value = float((request or {}).get("duration_seconds") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None

def _audio_evidence_status(review: DomainDocument, health: DomainDocument) -> str:
    if not review:
        return "missing"
    if str(review.get("audio_mode") or "").lower() != "wav":
        return "not_wav"
    evidence = _as_document(review.get("audio_evidence"))
    summary = audio_health_summary(_as_document(health.get("audio_health")))
    if not evidence or not summary:
        return "missing"
    if evidence.get("audio_health_hash") != summary.get("integrity_hash") or evidence.get("wav_sha256") != summary.get("wav_sha256"):
        return "stale"
    return "current"

def _profile_from_payload(payload: DomainDocument) -> AcceptanceProfile:
    if isinstance(payload.get("profile"), dict) and payload["profile"].get("profile_id"):
        return get_acceptance_profile(str(payload["profile"].get("profile_id")))
    profile_id = str(payload.get("profile_id") or "").strip()
    if profile_id:
        return get_acceptance_profile(profile_id)
    mode = str(payload.get("mode") or "").strip()
    legacy_modes = {"", "developer_self_test", "release_review"}
    return get_acceptance_profile("developer_manual" if mode in legacy_modes else mode)

def _expectation_blockers(case: AcceptanceCase, health_summary: DomainDocument) -> list[str]:
    expectations = _as_document(case.expectations)
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

def _songbook_coverage(case_rows: list[DomainDocument], suite: AcceptanceSuite) -> DomainDocument:
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

def _songbook_coverage_blockers(coverage: DomainDocument, suite: AcceptanceSuite) -> list[str]:
    if not suite.release_ready_profile or coverage.get("songbook_coverage_status") == "complete":
        return []
    blockers = ["release-ready profile requires complete regression songbook coverage"]
    missing = _as_list(coverage.get("missing_song_ids"))
    duplicates = _as_list(coverage.get("duplicate_song_ids"))
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

def _renderer_snapshot(config: object, sources: dict[str, str]) -> DomainDocument:
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

def _read_optional_json(path: Path) -> DomainDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return _as_document(value)

def _report_markdown(report: DomainDocument) -> str:
    summary = _as_document(report.get("summary"))
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

def _redaction_findings(payload: object) -> list[DomainDocument]:
    raw = json.dumps(payload, ensure_ascii=False)
    patterns = ("sk-", "api_key", "access_token", "Authorization:", "Bearer ", "C:\\Users", "\\\\", "/Users/", "/home/")
    findings = []
    for pattern in patterns:
        if pattern in raw:
            findings.append({"pattern": pattern, "message": "Sensitive value pattern found."})
    return findings

def _human_review_evidence_summary(store: AcceptanceStore, suite_id: str) -> DomainDocument:
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
        summary = _as_document(latest_import.get("summary"))
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

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]

def _optional_text(value: object, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(dict(value)) if isinstance(value, dict) else {}

def _validate_suite_id(value: str) -> str:
    value = str(value or "").strip()
    if not value.startswith("suite-") or not value.removeprefix("suite-").isdigit():
        raise AcceptanceValidationError("Invalid suite_id.")
    return value
