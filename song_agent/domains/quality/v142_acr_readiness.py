# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.quality.audio_campaign_planner import AudioCampaignPlannerStore as AudioCampaignPlannerStore
from song_agent.domains.quality.audio_campaigns import AudioCampaignStore as AudioCampaignStore
from song_agent.domains.quality.audio_fix_sprints import AudioFixSprintStore as AudioFixSprintStore
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.audio_campaign_remediation_contracts import AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE as AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE, AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION as AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION

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

action = _make_deferred_global('action')
key = _make_deferred_global('key')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global action, key, row
    action = namespace.get('action', action)
    key = namespace.get('key', key)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


HIGH_SEVERITIES = {"high", "critical"}




class AudioCampaignRemediationError(ValueError):
    pass

class AudioCampaignRemediationNotFoundError(AudioCampaignRemediationError):
    pass

class AudioCampaignRemediationStateError(AudioCampaignRemediationError):
    pass

class AudioCampaignRemediationValidationError(AudioCampaignRemediationError):
    pass

def _issues_from_campaign(campaign: DomainDocument, report: DomainDocument, case_index: DomainDocument) -> list[DomainDocument]:
    case_rows = {str(row.get("case_id")): row for row in case_index.get("cases", []) if isinstance(row, dict)}
    report_rows = {str(row.get("case_id")): row for row in report.get("cases", []) if isinstance(row, dict)}
    issues = []
    for case in campaign.get("cases", []):
        if not isinstance(case, dict):
            continue
        report_row = report_rows.get(str(case.get("case_id")), {})
        blockers = set(str(item) for item in report_row.get("blockers", []) if str(item))
        review = _as_document(case.get("review"))
        markers = [marker for marker in case.get("markers", []) if isinstance(marker, dict)]
        requires_fix = review.get("status") in {"needs_fix", "rejected"} or any(str(marker.get("severity") or "") in HIGH_SEVERITIES for marker in markers) or bool(blockers & {"case_needs_fix", "case_rejected", "open_high_or_critical_marker", "fix_sprint_missing", "fix_sprint_not_closed", "fix_sprint_closeout_failed"})
        if not requires_fix:
            continue
        case_index_row = case_rows.get(str(case.get("case_id")), {})
        issue = sanitize_metadata(
            {
                "issue_id": f"racr-{case.get('case_id')}",
                "case_id": case.get("case_id"),
                "session_id": case.get("session_id"),
                "item_id": case.get("item_id"),
                "song_id": case.get("song_id"),
                "title": case.get("title"),
                "project_id": case.get("project_id"),
                "version_id": case.get("version_id"),
                "final_export_hash": case.get("final_export_hash"),
                "review_status": review.get("status"),
                "severity": _issue_severity(review, markers),
                "category": _issue_category(markers),
                "markers": [_marker_public(marker) for marker in markers],
                "blockers": sorted(blockers),
                "fix_sprint_id": case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else case_index_row.get("fix_sprint_id"),
                "source_hash": stable_hash({"case_source_hash": case.get("source_hash"), "report_blockers": sorted(blockers), "case_index_row": case_index_row}),
            }
        )
        issues.append(issue)
    return sorted(issues, key=lambda row: ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(row.get("severity") or ""), 9), str(row.get("case_id") or "")))

def _issue_closeout(issue: DomainDocument, fix_store: AudioFixSprintStore) -> DomainDocument:
    blockers: list[str] = []
    warnings: list[str] = []
    sprint_id = str(issue.get("fix_sprint_id") or "")
    sprint: DomainDocument = {}
    closeout: DomainDocument = {}
    if not sprint_id:
        blockers.append("fix_sprint_missing")
    else:
        try:
            sprint = fix_store.read_sprint(sprint_id)
            closeout = fix_store.closeout_report(sprint_id)
        except Exception:
            blockers.append("fix_sprint_missing")
        if sprint:
            state = _sprint_state(sprint, fix_store, sprint_id)
            if not state.get("manual_ab_reviewed"):
                blockers.append("manual_ab_review_missing")
            if not state.get("selected_candidate"):
                blockers.append("selected_candidate_missing")
            if not state.get("manual_recheck_accepted"):
                blockers.append("manual_recheck_missing")
            if state.get("test_fake_count", 0) > 0:
                blockers.append("test_fake_audio_not_release_ready")
            if state.get("release_ready_audio_count", 0) <= 0:
                blockers.append("release_ready_recheck_audio_missing")
            if closeout.get("status") != "passed":
                blockers.append("fix_sprint_closeout_failed")
            if sprint.get("status") != "closed":
                blockers.append("fix_sprint_not_closed")
    return {
        "issue_id": issue.get("issue_id"),
        "case_id": issue.get("case_id"),
        "fix_sprint_id": sprint_id or None,
        "status": "passed" if not blockers else "failed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "sprint_status": sprint.get("status"),
        "closeout_status": closeout.get("status"),
        "closeout_hash": closeout.get("integrity_hash"),
    }

def _sprint_state(sprint: DomainDocument, fix_store: AudioFixSprintStore, sprint_id: str) -> DomainDocument:
    selected = False
    manual_ab = False
    candidate_count = 0
    for item in sprint.get("items", []):
        if not isinstance(item, dict):
            continue
        candidates = [row for row in item.get("candidates", []) if isinstance(row, dict)]
        candidate_count += len(candidates)
        selected = selected or bool(item.get("selected_candidate_id"))
        for candidate in candidates:
            review = _as_document(candidate.get("review"))
            if review.get("review_mode") == "manual" and review.get("playback_confirmed") is True:
                manual_ab = True
    recheck = fix_store._read_recheck_session(sprint_id, missing_ok=True)
    manual_recheck = False
    release_ready_audio_count = 0
    test_fake_count = 0
    if recheck:
        for item in recheck.get("items", []):
            if not isinstance(item, dict):
                continue
            review = _as_document(item.get("review"))
            renderer = _as_document(item.get("renderer"))
            if review.get("review_mode") == "manual" and review.get("status") == "accepted" and review.get("playback_confirmed") is True:
                manual_recheck = True
            if renderer.get("runner_kind") == "real" and renderer.get("release_ready") is True:
                release_ready_audio_count += 1
            if renderer.get("runner_kind") == "test_fake" or renderer.get("release_ready") is not True:
                test_fake_count += 1
    try:
        closeout = fix_store.closeout_report(sprint_id)
    except Exception:
        closeout = {}
    return {
        "sprint_status": sprint.get("status"),
        "candidate_count": candidate_count,
        "manual_ab_reviewed": manual_ab,
        "selected_candidate": selected,
        "recheck_created": bool(recheck),
        "manual_recheck_accepted": manual_recheck,
        "release_ready_audio_count": release_ready_audio_count,
        "test_fake_count": test_fake_count,
        "closeout_status": closeout.get("status"),
        "closeout_hash": closeout.get("integrity_hash"),
    }

def _action(index: int, issue: DomainDocument, action_type: str, kind: str, status: str, *, sprint_id: str | None = None) -> DomainDocument:
    return {
        "action_id": f"racra-{index:06d}",
        "issue_id": issue.get("issue_id"),
        "case_id": issue.get("case_id"),
        "fix_sprint_id": sprint_id,
        "action_type": action_type,
        "kind": kind,
        "status": status,
        "created_at": now_iso(),
    }

def _release_track_current_row(project_store: ProjectStore, track: object) -> DomainDocument:
    project_id = str(getattr(track, "project_id", "") or "")
    manifest_path = final_export_dir(project_store.project_dir(project_id)) / "manifest.json"
    current_hash = _sha256_path(manifest_path) if manifest_path.exists() else None
    expected_hash = str(getattr(track, "final_export_hash", "") or "")
    return {
        "track_id": getattr(track, "track_id", None),
        "project_id": project_id,
        "version_id": getattr(track, "version_id", None),
        "expected_hash": expected_hash,
        "current_hash": current_hash,
        "status": "passed" if expected_hash and current_hash and expected_hash == current_hash else "failed",
    }

def _track_identity(track: object) -> DomainDocument:
    return {"track_id": getattr(track, "track_id", None), "project_id": getattr(track, "project_id", None), "version_id": getattr(track, "version_id", None), "final_export_hash": getattr(track, "final_export_hash", None)}

def _issue_severity(review: DomainDocument, markers: list[DomainDocument]) -> str:
    values = [str(marker.get("severity") or "") for marker in markers]
    if review.get("status") == "rejected":
        values.append("critical")
    if review.get("status") == "needs_fix":
        values.append("high")
    for severity in ("critical", "high", "medium", "low"):
        if severity in values:
            return severity
    return "medium"

def _issue_category(markers: list[DomainDocument]) -> str:
    for marker in markers:
        category = str(marker.get("category") or "").strip()
        if category:
            return category
    return "other"

def _marker_public(marker: DomainDocument) -> DomainDocument:
    return sanitize_metadata({key: marker.get(key) for key in ("marker_id", "time_seconds", "category", "severity", "message", "source_hash")})

def _plan_summary(issues: list[DomainDocument], blockers: list[DomainDocument]) -> DomainDocument:
    return {
        "issue_count": len(issues),
        "critical_count": sum(1 for issue in issues if issue.get("severity") == "critical"),
        "high_count": sum(1 for issue in issues if issue.get("severity") == "high"),
        "linked_fix_sprint_count": len({issue.get("fix_sprint_id") for issue in issues if issue.get("fix_sprint_id")}),
        "blocker_count": len(blockers),
    }

def _queue_summary(actions: list[DomainDocument]) -> DomainDocument:
    return {
        "action_count": len(actions),
        "safe_count": sum(1 for action in actions if action.get("kind") == "safe"),
        "manual_required_count": sum(1 for action in actions if action.get("kind") == "manual_required"),
        "pending_count": sum(1 for action in actions if action.get("status") == "pending"),
    }

def _linked_fix_sprints(plan: DomainDocument, fix_store: AudioFixSprintStore) -> list[DomainDocument]:
    rows = []
    for sprint_id in sorted({str(issue.get("fix_sprint_id") or "") for issue in plan.get("issues", []) if issue.get("fix_sprint_id")}):
        try:
            sprint = fix_store.read_sprint(sprint_id)
            closeout = fix_store.closeout_report(sprint_id)
            rows.append({"fix_sprint_id": sprint_id, "status": sprint.get("status"), "source_hash": sprint.get("source_hash"), "closeout_status": closeout.get("status"), "closeout_hash": closeout.get("integrity_hash")})
        except Exception as exc:
            rows.append({"fix_sprint_id": sprint_id, "status": "missing", "error": str(exc)})
    return rows

def _readme(plan: DomainDocument, closeout: DomainDocument) -> str:
    return "\n".join(
        [
            "MusicForge Audio Campaign Remediation",
            f"release_id: {plan.get('release_id')}",
            f"campaign_id: {plan.get('campaign_id')}",
            f"status: {closeout.get('status')}",
            "This package records safe remediation orchestration only. Manual A/B review, candidate selection, campaign signoff, and release signoff remain explicit manual steps.",
            "",
        ]
    )

def _file_record(path: Path, root: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _bounded(value: object, limit: int) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())
    return text[:limit]

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _append_event(path: Path, event_type: str, payload: DomainDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"event_type": event_type, "created_at": now_iso(), **payload})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
