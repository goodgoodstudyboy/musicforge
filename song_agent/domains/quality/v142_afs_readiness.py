# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_analytics import AcceptanceAnalyticsStore as AcceptanceAnalyticsStore, AnalyticsScope as AnalyticsScope, acceptance_analytics_summary as acceptance_analytics_summary
from song_agent.domains.quality.acceptance_fix_plan_runtime import current_fix_plan_state as current_fix_plan_state
from song_agent.domains.quality.music_acceptance import AcceptanceStore as AcceptanceStore, stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import REVIEW_TASK_SCHEMA_VERSION as REVIEW_TASK_SCHEMA_VERSION, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore

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

AcceptanceFixItem = _make_deferred_global('AcceptanceFixItem')
AcceptanceFixSprint = _make_deferred_global('AcceptanceFixSprint')
AcceptanceFixSprintStore = _make_deferred_global('AcceptanceFixSprintStore')
_LOCKS_GUARD = _make_deferred_global('_LOCKS_GUARD')
check = _make_deferred_global('check')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceFixItem, AcceptanceFixSprint, AcceptanceFixSprintStore, _LOCKS_GUARD, check
    AcceptanceFixItem = namespace.get('AcceptanceFixItem', AcceptanceFixItem)
    AcceptanceFixSprint = namespace.get('AcceptanceFixSprint', AcceptanceFixSprint)
    AcceptanceFixSprintStore = namespace.get('AcceptanceFixSprintStore', AcceptanceFixSprintStore)
    _LOCKS_GUARD = namespace.get('_LOCKS_GUARD', _LOCKS_GUARD)
    check = namespace.get('check', check)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_FIX_SPRINT_SCHEMA_VERSION = "acceptance_fix_sprint.v1"
ACCEPTANCE_FIX_ITEMS_SCHEMA_VERSION = "acceptance_fix_items.v1"
ACCEPTANCE_FIX_DELTA_SCHEMA_VERSION = "acceptance_fix_delta.v1"
ACCEPTANCE_FIX_CLOSEOUT_SCHEMA_VERSION = "acceptance_fix_closeout.v1"
SPRINT_STATUSES = {"draft", "planned", "in_progress", "recheck_ready", "rechecking", "delta_ready", "ready_to_close", "closed", "archived", "stale"}
ITEM_STATUSES = {"open", "linked", "in_progress", "needs_recheck", "fixed", "waived", "blocked", "stale", "closed"}
OPEN_REVIEW_TASK_STATUSES = {"open", "candidate_ready", "applied", "needs_more_work"}
TERMINAL_REVIEW_TASK_STATUSES = {"resolved", "archived"}
_LOCKS: dict[str, threading.RLock] = {}




class AcceptanceFixSprintError(ValueError):
    pass

class AcceptanceFixSprintNotFoundError(AcceptanceFixSprintError):
    pass

class AcceptanceFixSprintStateError(AcceptanceFixSprintError):
    pass

def build_delta_report(sprint: AcceptanceFixSprint, items: list[AcceptanceFixItem], source_report: DomainDocument, recheck_report: DomainDocument, *, now: str | None = None, project_store: ProjectStore | None = None) -> DomainDocument:
    before = acceptance_analytics_summary(source_report)
    after = acceptance_analytics_summary(recheck_report)
    before_summary = _as_document(source_report.get("summary"))
    after_summary = _as_document(recheck_report.get("summary"))
    before_rating = before.get("average_rating")
    after_rating = after.get("average_rating")
    rating_delta = round(float(after_rating or 0) - float(before_rating or 0), 2) if before_rating is not None and after_rating is not None else None
    issue_delta = int(after.get("issue_count") or 0) - int(before.get("issue_count") or 0)
    accepted_delta = int(after_summary.get("accepted_count") or 0) - int(before_summary.get("accepted_count") or 0)
    fixed_count = sum(1 for item in items if item.status in {"fixed", "closed", "waived"})
    status = "incomplete"
    if after.get("readiness_status") == "blocked":
        status = "blocked"
    elif rating_delta is not None and (rating_delta > 0 or issue_delta < 0 or accepted_delta > 0):
        status = "improved"
    elif rating_delta is not None and (rating_delta < 0 or issue_delta > 0):
        status = "regressed"
    elif after.get("readiness_status") != "missing":
        status = "unchanged"
    return sanitize_metadata(
        {
            "schema_version": ACCEPTANCE_FIX_DELTA_SCHEMA_VERSION,
            "fix_sprint_id": sprint.fix_sprint_id,
            "generated_at": now or now_iso(),
            "source": {"analytics_report_id": _source_report_id(sprint), "source_hash": sprint.source.get("source_hash")},
            "recheck": {"suite_id": sprint.recheck.get("suite_id"), "analytics_report_id": recheck_report.get("report_id"), "source_hash": recheck_report.get("source_hash")},
            "summary": {
                "status": status,
                "before_readiness": before.get("readiness_status"),
                "after_readiness": after.get("readiness_status"),
                "rating_delta": rating_delta,
                "issue_count_delta": issue_delta,
                "accepted_delta": accepted_delta,
                "manual_accepted_count": _accepted_count(recheck_report, mode="manual"),
                "synthetic_accepted_count": _accepted_count(recheck_report, mode="synthetic"),
                "manual_review_count": _review_count(recheck_report, mode="manual"),
                "synthetic_review_count": _review_count(recheck_report, mode="synthetic"),
                "needs_fix_delta": int(after_summary.get("needs_fix_count") or 0) - int(before_summary.get("needs_fix_count") or 0),
                "rejected_delta": int(after_summary.get("rejected_count") or 0) - int(before_summary.get("rejected_count") or 0),
                "fixed_item_count": fixed_count,
                "regressed_item_count": 0,
                "review_task_close_rate": _review_task_close_rate(items, project_store),
            },
            "song_deltas": _song_deltas(source_report, recheck_report),
            "issue_deltas": _issue_deltas(source_report, recheck_report),
            "warnings": [],
        }
    )

def build_closeout_report(sprint: AcceptanceFixSprint, items: list[AcceptanceFixItem], delta: DomainDocument, *, force: bool = False, override_reason: str = "", now: str | None = None) -> DomainDocument:
    active = [item for item in items if item.status not in {"waived", "fixed", "closed"}]
    waived_without_reason = [item.item_id for item in items if item.status == "waived" and not str((item.resolution or {}).get("notes") or "").strip()]
    after_readiness = (_as_document(delta.get("summary"))).get("after_readiness")
    checks = [
        _close_check("items_closed", not active, "blocking", "All non-waived fix items are closed or fixed.", [item.item_id for item in active]),
        _close_check("recheck_suite_exists", bool(sprint.recheck.get("suite_id")), "blocking", "Recheck suite exists.", [] if sprint.recheck.get("suite_id") else ["missing_recheck_suite"]),
        _close_check("delta_ready", bool(delta), "blocking", "Delta report exists.", [] if delta else ["missing_delta_report"]),
        _close_check("recheck_not_blocked", after_readiness not in {"blocked", "missing", None}, "blocking", "Recheck analytics is not blocked.", [] if after_readiness not in {"blocked", "missing", None} else [str(after_readiness or "missing")]),
        _close_check("waiver_reason", not waived_without_reason, "blocking", "Waived items have reasons.", waived_without_reason),
    ]
    blockers = [check for check in checks if check["status"] == "failed" and check.get("severity") == "blocking"]
    if force and not override_reason.strip():
        blockers.append(_close_check("override_reason", False, "blocking", "Force close requires override_reason.", ["missing_override_reason"]))
    status = "passed" if not blockers else "force_closed" if force and override_reason.strip() else "failed"
    return sanitize_metadata(
        {
            "schema_version": ACCEPTANCE_FIX_CLOSEOUT_SCHEMA_VERSION,
            "fix_sprint_id": sprint.fix_sprint_id,
            "generated_at": now or now_iso(),
            "status": status,
            "message": "Acceptance Fix Sprint closeout failed." if status == "failed" else "Acceptance Fix Sprint closeout complete.",
            "forced": bool(force),
            "override_reason": _bounded(override_reason, 500),
            "checks": checks,
            "summary": {"status": status, "item_count": len(items), "open_item_count": len(active), "delta_status": (delta.get("summary") or {}).get("status"), "after_readiness": after_readiness},
        }
    )

def fix_sprint_summary(sprint: AcceptanceFixSprint | DomainDocument | None, items: list[AcceptanceFixItem] | None = None) -> DomainDocument:
    data = sprint.to_dict() if isinstance(sprint, AcceptanceFixSprint) else _as_document(sprint)
    counts = _as_document(data.get("counts"))
    recheck = _as_document(data.get("recheck"))
    delta = _as_document(data.get("delta_summary"))
    closeout = _as_document(data.get("closeout_summary"))
    delta_status = delta.get("status")
    if not delta_status and isinstance(delta.get("summary"), dict):
        delta_status = delta["summary"].get("status")
    return sanitize_metadata(
        {
            "fix_sprint_id": data.get("fix_sprint_id"),
            "status": data.get("status") or "missing",
            "source_report_id": (_as_document(data.get("source"))).get("report_id") or (_as_document(data.get("source"))).get("analytics_report_id"),
            "source_hash": (_as_document(data.get("source"))).get("source_hash"),
            "item_count": counts.get("item_count", len(items or [])),
            "open_item_count": counts.get("open_item_count", 0),
            "linked_review_task_count": counts.get("linked_review_task_count", 0),
            "completed_review_task_count": counts.get("completed_review_task_count", 0),
            "recheck_suite_id": recheck.get("suite_id"),
            "recheck_status": recheck.get("status") or "not_started",
            "delta_status": delta_status,
            "closeout_status": closeout.get("status") or "missing",
        }
    )

def acceptance_fix_closeout_summary(closeout: DomainDocument | None) -> DomainDocument:
    data = _as_document(closeout)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata({"status": data.get("status") or "missing", "forced": bool(data.get("forced", False)), "delta_status": summary.get("delta_status"), "after_readiness": summary.get("after_readiness")})

def latest_fix_sprint_summary(store: AcceptanceFixSprintStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    for sprint in store.list_sprints(include_archived=True):
        scope = _as_document(sprint.scope)
        if release_id and scope.get("release_id") != release_id:
            continue
        items = store.read_items(sprint.fix_sprint_id)
        if project_id and scope.get("project_id") != project_id and not any(str(item.target.get("project_id") or "") == project_id for item in items):
            continue
        return fix_sprint_summary(sprint, items)
    return {"status": "missing"}

def write_acceptance_fix_sprints_summary(path: Path, store: AcceptanceFixSprintStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    summary = latest_fix_sprint_summary(store, release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary

def _selected_recommendations(report: DomainDocument, recommendation_ids: object, *, max_items: int) -> list[DomainDocument]:
    rows = [item for item in report.get("recommendations", []) if isinstance(item, dict)]
    selected_ids = [str(item) for item in recommendation_ids if str(item).strip()] if isinstance(recommendation_ids, list) else []
    if selected_ids:
        wanted = set(selected_ids)
        rows = [item for item in rows if str(item.get("recommendation_id") or "") in wanted]
    else:
        rows = [item for item in rows if item.get("type") == "create_review_task"] or rows[:max_items]
    seen = set()
    deduped = []
    for row in rows:
        key = str(row.get("recommendation_id") or stable_hash(row))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:max_items]

def _item_from_recommendation(index: int, recommendation: DomainDocument, *, report_id: str, source_hash: str, now: str) -> AcceptanceFixItem:
    target = _safe_dict(recommendation.get("target"))
    evidence = _safe_dict(recommendation.get("evidence"))
    issue_types = [str(item) for item in evidence.get("issue_types", []) if str(item).strip()] if isinstance(evidence.get("issue_types"), list) else []
    if issue_types:
        target["issue_types"] = issue_types
    severity = str(recommendation.get("severity") or "medium")
    priority = 90 if severity == "high" else 72 if severity == "medium" else 50
    return AcceptanceFixItem(
        item_id=f"afi-{index:06d}",
        status="open",
        priority=priority,
        severity=severity,
        source={"source_type": "analytics_recommendation", "report_id": report_id, "recommendation_id": recommendation.get("recommendation_id"), "source_hash": source_hash, "recommendation_hash": stable_hash(recommendation)},
        target=target,
        title=_bounded(recommendation.get("title"), 180) or "Fix acceptance weakness",
        summary=_bounded(recommendation.get("reason"), 800) or "Acceptance analytics recommends a follow-up fix.",
        evidence={**evidence, "weakness_score": recommendation.get("weakness_score")},
        created_at=now,
        updated_at=now,
    )

def _counts(items: list[AcceptanceFixItem], project_store: ProjectStore | None = None) -> DomainDocument:
    linked = len([item for item in items if item.review_task_id])
    completed = 0
    if project_store:
        for item in items:
            if not item.review_task_id or not item.target.get("project_id"):
                continue
            try:
                task = ReviewTaskStore(project_store.project_dir(str(item.target.get("project_id")))).read_task(str(item.review_task_id))
                if task.status in TERMINAL_REVIEW_TASK_STATUSES:
                    completed += 1
            except Exception:
                continue
    return {
        "item_count": len(items),
        "open_item_count": len([item for item in items if item.status in {"open", "linked", "in_progress", "needs_recheck", "blocked", "stale"}]),
        "linked_review_task_count": linked,
        "completed_review_task_count": completed,
        "waived_item_count": len([item for item in items if item.status == "waived"]),
        "fixed_item_count": len([item for item in items if item.status in {"fixed", "closed"}]),
    }

def _matching_open_review_task(project_dir: Path, song_id: str, issue_types: list[str]) -> ReviewTask | None:
    store = ReviewTaskStore(project_dir)
    wanted = set(issue_types)
    for task in store.list_tasks(include_archived=False):
        if task.status not in OPEN_REVIEW_TASK_STATUSES:
            continue
        blob = json.dumps({"source": task.source, "target": task.target, "title": task.title}, ensure_ascii=False)
        if song_id and song_id not in blob:
            continue
        if wanted and not wanted.intersection(set(_issue_types_from_blob(blob))):
            continue
        return task
    return None

def _issue_types_from_blob(blob: str) -> list[str]:
    found = []
    for value in ["hook", "rhythm", "melody", "arrangement", "mix", "structure", "ending", "lyrics", "performance", "other"]:
        if value in blob:
            found.append(value)
    return found

def _request_for_recheck(report: DomainDocument, song_id: str) -> DomainDocument:
    source = _as_document(report.get("source"))
    for suite_row in source.get("suites", []) if isinstance(source.get("suites"), list) else []:
        for case_row in suite_row.get("cases", []) if isinstance(suite_row.get("cases"), list) else []:
            case = _as_document(case_row.get("case"))
            if case.get("song_id") == song_id:
                summary = _as_document(case.get("request_summary"))
                return {"title": summary.get("title") or song_id, "language": summary.get("language") or "English", "style": summary.get("style") or "pop", "theme": summary.get("theme") or "acceptance fix recheck", "duration_seconds": 90}
    return {"title": song_id, "language": "English", "style": "pop", "theme": "acceptance fix recheck", "duration_seconds": 90}

def _source_report_id(sprint: AcceptanceFixSprint) -> str:
    return str(sprint.source.get("report_id") or sprint.source.get("analytics_report_id") or "")

def _song_deltas(source_report: DomainDocument, recheck_report: DomainDocument) -> list[DomainDocument]:
    before = {str(item.get("song_id") or ""): item for item in source_report.get("songbook_heatmap", []) if isinstance(item, dict)}
    after = {str(item.get("song_id") or ""): item for item in recheck_report.get("songbook_heatmap", []) if isinstance(item, dict)}
    rows = []
    for song_id in sorted(set(before) | set(after)):
        left = before.get(song_id, {})
        right = after.get(song_id, {})
        if not left and not right:
            continue
        rows.append({"song_id": song_id, "before_status": left.get("latest_status"), "after_status": right.get("latest_status"), "before_rating": left.get("average_rating"), "after_rating": right.get("average_rating"), "issue_delta": int(right.get("issue_count") or 0) - int(left.get("issue_count") or 0)})
    return rows[:50]

def _issue_deltas(source_report: DomainDocument, recheck_report: DomainDocument) -> list[DomainDocument]:
    before = {str(item.get("issue_type") or ""): int(item.get("count") or 0) for item in source_report.get("issue_taxonomy", []) if isinstance(item, dict)}
    after = {str(item.get("issue_type") or ""): int(item.get("count") or 0) for item in recheck_report.get("issue_taxonomy", []) if isinstance(item, dict)}
    return [{"issue_type": key, "before_count": before.get(key, 0), "after_count": after.get(key, 0), "count_delta": after.get(key, 0) - before.get(key, 0)} for key in sorted(set(before) | set(after))][:50]

def _review_task_close_rate(items: list[AcceptanceFixItem], project_store: ProjectStore | None) -> float:
    linked = [item for item in items if item.review_task_id and item.target.get("project_id")]
    if not linked or not project_store:
        return 0.0
    closed = 0
    for item in linked:
        try:
            task = ReviewTaskStore(project_store.project_dir(str(item.target.get("project_id")))).read_task(str(item.review_task_id))
            if task.status in TERMINAL_REVIEW_TASK_STATUSES:
                closed += 1
        except Exception:
            continue
    return round(closed / len(linked), 4)

def _accepted_count(report: DomainDocument, *, mode: str) -> int:
    summary = _as_document(report.get("summary"))
    key = f"{mode}_accepted_count"
    if key in summary:
        return _int(summary.get(key), 0)
    return sum(1 for row in report.get("cases", []) if isinstance(row, dict) and row.get("review_mode") == mode and row.get("review_status") == "accepted")

def _review_count(report: DomainDocument, *, mode: str) -> int:
    summary = _as_document(report.get("summary"))
    key = f"{mode}_review_count"
    if key in summary:
        return _int(summary.get(key), 0)
    return sum(1 for row in report.get("cases", []) if isinstance(row, dict) and row.get("review_mode") == mode and row.get("review_status") in {"accepted", "needs_fix", "rejected", "waived"})

def _close_check(check_id: str, passed: bool, severity: str, message: str, details: list[str]) -> DomainDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message if passed else f"{message} Problems: {', '.join(details[:5])}", "details": details}

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _optional_str(value: object, limit: int) -> str | None:
    text = _bounded(value, limit).strip()
    return text or None

def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{6}}", text):
        raise AcceptanceFixSprintError(f"Invalid {prefix} id.")
    return text

def _lock_for_root(root: Path) -> threading.RLock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]

def _append_event(path: Path, event: str, payload: DomainDocument | None = None, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = sanitize_metadata({"timestamp": now or now_iso(), "event": event, **(payload or {})})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
