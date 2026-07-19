# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.quality.audio_campaign_verifier import verify_audio_campaign_package as verify_audio_campaign_package, write_audio_campaign_verification_report as write_audio_campaign_verification_report
from song_agent.domains.quality.audio_fix_sprints import AudioFixSprintNotFoundError as AudioFixSprintNotFoundError, AudioFixSprintStateError as AudioFixSprintStateError, AudioFixSprintStore as AudioFixSprintStore
from song_agent.domains.quality.audio_lab import AudioLabStore as AudioLabStore
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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

ch = _make_deferred_global('ch')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, key
    ch = namespace.get('ch', ch)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


AUDIO_CAMPAIGN_SCHEMA_VERSION = 1
HIGH_SEVERITIES = {"high", "critical"}




class AudioCampaignError(ValueError):
    pass

class AudioCampaignNotFoundError(AudioCampaignError):
    pass

class AudioCampaignStateError(AudioCampaignError):
    pass

class AudioCampaignValidationError(AudioCampaignError):
    pass

def _build_campaign_report(campaign: DomainDocument, fix_store: AudioFixSprintStore) -> DomainDocument:
    settings = _as_document(campaign.get("settings"))
    blockers: list[DomainDocument] = []
    warnings: list[DomainDocument] = []
    case_reports: list[DomainDocument] = []
    summary = {
        "case_count": len(campaign.get("cases", [])),
        "accepted_count": 0,
        "needs_fix_count": 0,
        "rejected_count": 0,
        "manual_review_count": 0,
        "synthetic_review_count": 0,
        "real_audio_count": 0,
        "test_fake_count": 0,
        "missing_wav_count": 0,
        "open_high_marker_count": 0,
        "open_critical_marker_count": 0,
        "fix_sprint_count": 0,
        "open_fix_sprint_count": 0,
        "failed_fix_sprint_count": 0,
        "stale_case_count": 0,
    }
    for case in campaign.get("cases", []):
        case_blockers: list[str] = []
        renderer = _as_document(case.get("renderer"))
        review = _as_document(case.get("review"))
        markers = [marker for marker in case.get("markers", []) if isinstance(marker, dict)]
        wav_sha = case.get("artifact_hashes", {}).get("wav_sha256") if isinstance(case.get("artifact_hashes"), dict) else None
        if case.get("stale"):
            summary["stale_case_count"] += 1
            case_blockers.append("audio_campaign_case_stale")
        if not wav_sha:
            summary["missing_wav_count"] += 1
            case_blockers.append("audio_campaign_wav_missing")
        if renderer.get("runner_kind") == "real" and renderer.get("release_ready") is True:
            summary["real_audio_count"] += 1
        elif renderer.get("runner_kind") == "test_fake":
            summary["test_fake_count"] += 1
            if not settings.get("allow_test_fake_audio"):
                case_blockers.append("test_fake_audio_not_release_ready")
        elif settings.get("require_real_renderer"):
            case_blockers.append("real_audio_required")
        if review.get("review_mode") == "manual" and review.get("playback_confirmed") is True:
            summary["manual_review_count"] += 1
        elif review:
            summary["synthetic_review_count"] += 1
            if not settings.get("allow_synthetic_review"):
                case_blockers.append("synthetic_review_not_allowed")
        else:
            case_blockers.append("manual_review_missing")
        fix_sprint_id = case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None
        fix_required = _case_requires_fix(case, settings)
        fix_passed = False
        if fix_required:
            if not fix_sprint_id:
                case_blockers.append("fix_sprint_missing")
            else:
                summary["fix_sprint_count"] += 1
                try:
                    sprint = fix_store.read_sprint(str(fix_sprint_id))
                    closeout = fix_store.closeout_report(str(fix_sprint_id))
                    if sprint.get("status") != "closed":
                        summary["open_fix_sprint_count"] += 1
                        case_blockers.append("fix_sprint_not_closed")
                    if closeout.get("status") != "passed":
                        summary["failed_fix_sprint_count"] += 1
                        case_blockers.append("fix_sprint_closeout_failed")
                    fix_passed = sprint.get("status") == "closed" and closeout.get("status") == "passed"
                except Exception:
                    summary["failed_fix_sprint_count"] += 1
                    case_blockers.append("fix_sprint_missing")
        status = str(review.get("status") or "")
        if status == "accepted":
            summary["accepted_count"] += 1
        elif status == "needs_fix":
            summary["needs_fix_count"] += 1
            if not fix_passed:
                case_blockers.append("case_needs_fix")
        elif status == "rejected":
            summary["rejected_count"] += 1
            if not fix_passed:
                case_blockers.append("case_rejected")
        if review and int(review.get("rating") or 0) < int(settings.get("minimum_rating") or 4) and not fix_passed:
            case_blockers.append("minimum_rating_not_met")
        high_or_critical = []
        for marker in markers:
            severity = str(marker.get("severity") or "")
            if severity in HIGH_SEVERITIES:
                high_or_critical.append(marker)
                if not fix_passed:
                    if severity == "high":
                        summary["open_high_marker_count"] += 1
                    if severity == "critical":
                        summary["open_critical_marker_count"] += 1
        if high_or_critical and settings.get("block_high_or_critical_markers") and not fix_passed:
            case_blockers.append("open_high_or_critical_marker")
        for blocker in sorted(set(case_blockers)):
            blockers.append({"check_id": blocker, "case_id": case.get("case_id"), "message": _blocker_message(blocker)})
        case_reports.append(
            {
                "case_id": case.get("case_id"),
                "session_id": case.get("session_id"),
                "item_id": case.get("item_id"),
                "song_id": case.get("song_id"),
                "title": case.get("title"),
                "status": "blocked" if case_blockers else "passed",
                "blockers": sorted(set(case_blockers)),
                "renderer": renderer,
                "review": _review_public(review),
                "marker_count": len(markers),
                "fix_sprint_id": fix_sprint_id,
                "source_hash": case.get("source_hash"),
            }
        )
    checks = _checks_from_summary(summary, blockers, settings)
    status = "passed" if not blockers else "failed"
    report = sanitize_metadata(
        {
            "schema_version": AUDIO_CAMPAIGN_SCHEMA_VERSION,
            "report_id": f"acr-{campaign.get('campaign_id')}",
            "campaign_id": campaign.get("campaign_id"),
            "generated_at": now_iso(),
            "status": status,
            "profile": campaign.get("profile"),
            "settings": settings,
            "source": {"campaign_source_hash": campaign.get("source_hash"), "session_ids": campaign.get("source", {}).get("session_ids", [])},
            "summary": summary,
            "checks": checks,
            "blockers": blockers,
            "warnings": warnings,
            "cases": case_reports,
        }
    )
    report["source_hash"] = stable_hash(report["source"])
    report["integrity_hash"] = _integrity_hash(report)
    return report

def _checks_from_summary(summary: DomainDocument, blockers: list[DomainDocument], settings: DomainDocument) -> list[DomainDocument]:
    return [
        _check("audio_campaign_has_cases", int(summary.get("case_count") or 0) > 0, "Campaign contains at least one case."),
        _check("audio_campaign_real_audio", not settings.get("require_real_renderer") or int(summary.get("real_audio_count") or 0) == int(summary.get("case_count") or 0), "All cases use release-ready real audio."),
        _check("audio_campaign_manual_review", int(summary.get("manual_review_count") or 0) == int(summary.get("case_count") or 0), "All cases have manual review."),
        _check("audio_campaign_no_test_fake", settings.get("allow_test_fake_audio") or int(summary.get("test_fake_count") or 0) == 0, "No test fake WAV is counted as release-ready."),
        _check("audio_campaign_no_open_markers", not settings.get("block_high_or_critical_markers") or (int(summary.get("open_high_marker_count") or 0) + int(summary.get("open_critical_marker_count") or 0)) == 0, "No high or critical markers remain open."),
        _check("audio_campaign_fix_sprints_closed", int(summary.get("open_fix_sprint_count") or 0) == 0 and int(summary.get("failed_fix_sprint_count") or 0) == 0, "Required fix sprints are closed and passed."),
        _check("audio_campaign_no_blockers", not blockers, "Campaign has no blocking issues."),
    ]

def _cases_from_sessions(sessions: list[DomainDocument]) -> list[DomainDocument]:
    cases: list[DomainDocument] = []
    counter = 0
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for item in session.get("items", []):
            if not isinstance(item, dict):
                continue
            counter += 1
            case = sanitize_metadata(
                {
                    "case_id": f"acc-{counter:06d}",
                    "source_key": stable_hash({"session_id": session_id, "item_id": item.get("item_id")}),
                    "session_id": session_id,
                    "item_id": item.get("item_id"),
                    "song_id": item.get("song_id"),
                    "title": item.get("title"),
                    "project_id": item.get("project_id"),
                    "version_id": item.get("version_id"),
                    "final_export_hash": item.get("final_export_hash"),
                    "status": "reviewed" if item.get("review") else "needs_review",
                    "artifact_relpaths": dict(item.get("artifact_relpaths") or {}),
                    "artifact_hashes": dict(item.get("artifact_hashes") or {}),
                    "audio_status": item.get("audio_status"),
                    "renderer": dict(item.get("renderer") or {}),
                    "audio_health_summary": item.get("audio_health_summary") or {},
                    "music_health_summary": item.get("music_health_summary") or {},
                    "review": dict(item.get("review") or {}),
                    "markers": [dict(marker) for marker in item.get("markers", []) if isinstance(marker, dict)],
                    "stale": bool(item.get("stale") or session.get("stale")),
                    "source_hash": item.get("source_hash"),
                    "fix": {},
                }
            )
            cases.append(case)
    return cases

def _source_from_sessions(session_ids: list[str], sessions: list[DomainDocument]) -> DomainDocument:
    source = {
        "source_type": "audio_lab_sessions",
        "session_ids": session_ids,
        "session_hashes": {str(session.get("session_id")): session.get("source_hash") for session in sessions},
        "session_integrity_hashes": {str(session.get("session_id")): session.get("integrity_hash") for session in sessions},
    }
    source["source_hash"] = stable_hash(source)
    return source

def _settings_from_payload(payload: DomainDocument) -> DomainDocument:
    allow_test = bool(payload.get("allow_test_audio") or payload.get("allow_test_fake_audio"))
    return {
        "require_real_renderer": not allow_test and bool(payload.get("require_real_renderer", True)),
        "allow_test_fake_audio": allow_test,
        "allow_synthetic_review": bool(payload.get("allow_synthetic_review", False)),
        "minimum_rating": max(1, min(5, int(payload.get("minimum_rating") or 4))),
        "block_high_or_critical_markers": bool(payload.get("block_high_or_critical_markers", True)),
    }

def _session_ids_from_payload(payload: DomainDocument) -> list[str]:
    raw = payload.get("session_ids") or payload.get("from_sessions") or payload.get("from_session") or payload.get("session_id")
    if isinstance(raw, list):
        values = raw
    else:
        values = [raw]
    session_ids = [_validate_id(str(item), "als") for item in values if str(item or "").strip()]
    if not session_ids:
        raise AudioCampaignValidationError("At least one Audio Lab session is required.")
    return list(dict.fromkeys(session_ids))

def _sessions_requiring_fix(campaign: DomainDocument) -> list[str]:
    sessions = []
    settings = _as_document(campaign.get("settings"))
    for case in campaign.get("cases", []):
        if _case_requires_fix(case, settings):
            session_id = str(case.get("session_id") or "")
            if session_id and session_id not in sessions:
                sessions.append(session_id)
    return sessions

def _case_requires_fix(case: DomainDocument, settings: DomainDocument) -> bool:
    review = _as_document(case.get("review"))
    if review.get("status") in {"needs_fix", "rejected"}:
        return True
    if not settings.get("block_high_or_critical_markers", True):
        return False
    return any(str(marker.get("severity") or "") in HIGH_SEVERITIES for marker in case.get("markers", []) if isinstance(marker, dict))

def _campaign_fix_sprint_for_session(campaign: DomainDocument, session_id: str) -> str | None:
    for case in campaign.get("cases", []):
        if case.get("session_id") == session_id:
            sprint_id = case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None
            if sprint_id:
                return str(sprint_id)
    return None

def _case_source(case: DomainDocument) -> DomainDocument:
    return {
        "case_id": case.get("case_id"),
        "session_id": case.get("session_id"),
        "item_id": case.get("item_id"),
        "source_hash": case.get("source_hash"),
        "artifact_hashes": case.get("artifact_hashes"),
        "renderer": case.get("renderer"),
        "review": _review_public(_as_document(case.get("review"))),
        "markers": [
            {"marker_id": marker.get("marker_id"), "severity": marker.get("severity"), "category": marker.get("category"), "source_hash": marker.get("source_hash")}
            for marker in case.get("markers", [])
            if isinstance(marker, dict)
        ],
        "fix_sprint_id": case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None,
    }

def _review_public(review: DomainDocument) -> DomainDocument:
    return {
        "status": review.get("status"),
        "rating": review.get("rating"),
        "review_mode": review.get("review_mode"),
        "playback_confirmed": review.get("playback_confirmed"),
        "reviewer": review.get("reviewer"),
        "source_hash": review.get("source_hash"),
        "integrity_hash": review.get("integrity_hash"),
    }

def _check(check_id: str, passed: bool, message: str) -> DomainDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}

def _blocker_message(blocker: str) -> str:
    return {
        "audio_campaign_case_stale": "Campaign case source is stale.",
        "audio_campaign_wav_missing": "Campaign case is missing WAV evidence.",
        "test_fake_audio_not_release_ready": "Test fake WAV cannot count as release-ready audio.",
        "real_audio_required": "Release candidate campaign requires real renderer audio.",
        "synthetic_review_not_allowed": "Synthetic review cannot satisfy release candidate audio review.",
        "manual_review_missing": "Manual playback-confirmed review is missing.",
        "case_needs_fix": "Listening review needs fix.",
        "case_rejected": "Listening review rejected the track.",
        "minimum_rating_not_met": "Listening rating is below campaign threshold.",
        "open_high_or_critical_marker": "High or critical marker remains open.",
        "fix_sprint_missing": "Required Audio Fix Sprint is missing.",
        "fix_sprint_not_closed": "Required Audio Fix Sprint is not closed.",
        "fix_sprint_closeout_failed": "Required Audio Fix Sprint closeout failed.",
    }.get(blocker, blocker)

def _readme(campaign: DomainDocument, report: DomainDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(
        [
            "# MusicForge Audio Campaign",
            "",
            f"Campaign: {campaign.get('campaign_id')}",
            f"Status: {report.get('status')}",
            f"Cases: {summary.get('case_count')}",
            f"Manual reviews: {summary.get('manual_review_count')}",
            f"Real audio: {summary.get('real_audio_count')}",
            "",
            "This package contains campaign evidence summaries only. It does not embed local .musicforge paths or audio files.",
            "",
        ]
    )

def _file_record(path: Path, root: Path, rel: str) -> DomainDocument:
    return {"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size}

def _append_event(path: Path, event_type: str, payload: DomainDocument) -> None:
    event = sanitize_metadata({"event_type": event_type, "created_at": now_iso(), "payload": payload})
    event["event_hash"] = stable_hash(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _validate_id(value: str, prefix: str) -> str:
    value = str(value or "").strip()
    if not value.startswith(prefix + "-"):
        raise AudioCampaignValidationError(f"Invalid {prefix} id.")
    safe = "".join(ch for ch in value if ch.isalnum() or ch in "-_")
    if safe != value:
        raise AudioCampaignValidationError(f"Invalid {prefix} id.")
    return value

def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
