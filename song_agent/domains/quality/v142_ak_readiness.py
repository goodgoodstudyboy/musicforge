# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixSprint as AcceptanceFixSprint, AcceptanceFixSprintStore as AcceptanceFixSprintStore, AcceptanceFixSprintError as AcceptanceFixSprintError, acceptance_fix_closeout_summary as acceptance_fix_closeout_summary
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text

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

AcceptanceKnowledgeBaseError = _make_deferred_global('AcceptanceKnowledgeBaseError')
AcceptanceKnowledgeBaseStore = _make_deferred_global('AcceptanceKnowledgeBaseStore')
KnowledgeEntry = _make_deferred_global('KnowledgeEntry')
key = _make_deferred_global('key')
status = _make_deferred_global('status')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceKnowledgeBaseError, AcceptanceKnowledgeBaseStore, KnowledgeEntry, key, status
    AcceptanceKnowledgeBaseError = namespace.get('AcceptanceKnowledgeBaseError', AcceptanceKnowledgeBaseError)
    AcceptanceKnowledgeBaseStore = namespace.get('AcceptanceKnowledgeBaseStore', AcceptanceKnowledgeBaseStore)
    KnowledgeEntry = namespace.get('KnowledgeEntry', KnowledgeEntry)
    key = namespace.get('key', key)
    status = namespace.get('status', status)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_KB_ENTRY_SCHEMA_VERSION = "acceptance_kb_entry.v1"
ACCEPTANCE_KB_REPORT_SCHEMA_VERSION = "acceptance_kb_report.v1"
ENTRY_STATUSES = {"active", "hidden", "stale"}
OUTCOME_STATUSES = {"effective", "mixed", "ineffective", "unknown"}
READINESS_ORDER = {"missing": 0, "empty": 0, "blocked": 1, "needs_work": 2, "watch": 3, "ready": 4}
SUCCESS_STATUSES = {"fixed", "closed"}




def build_knowledge_report(entries: list[KnowledgeEntry], *, scope: DomainDocument, report_id: str, generated_at: str, warnings: list[str] | None = None) -> DomainDocument:
    active = [entry for entry in entries if entry.status == "active"]
    scores = [int(entry.outcome.get("effectiveness_score") or 0) for entry in active if str(entry.outcome.get("outcome_status") or "") != "unknown"]
    issue_patterns = _issue_patterns(active)
    style_patterns = _style_patterns(active)
    song_patterns = _song_patterns(active)
    recommendations = _knowledge_recommendations(issue_patterns, style_patterns, song_patterns)
    report = {
        "schema_version": ACCEPTANCE_KB_REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "scope": _safe_scope(scope),
        "generated_at": generated_at,
        "source_hash": _entries_source_hash(active),
        "summary": {
            "entry_count": len(active),
            "effective_count": sum(1 for entry in active if entry.outcome.get("outcome_status") == "effective"),
            "mixed_count": sum(1 for entry in active if entry.outcome.get("outcome_status") == "mixed"),
            "ineffective_count": sum(1 for entry in active if entry.outcome.get("outcome_status") == "ineffective"),
            "waived_count": sum(int(entry.fix.get("waived_count") or 0) for entry in active),
            "average_effectiveness_score": round(sum(scores) / len(scores), 2) if scores else None,
            "recurring_issue_count": len([item for item in issue_patterns if int(item.get("entry_count") or 0) > 1]),
        },
        "issue_patterns": issue_patterns,
        "style_patterns": style_patterns,
        "song_patterns": song_patterns,
        "fix_patterns": _fix_patterns(active),
        "recommendations": recommendations,
        "warnings": sorted(set(_bounded(item, 180) for item in (warnings or []) if str(item).strip())),
        "stale": False,
    }
    return sanitize_metadata(report)

def knowledge_report_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    issue_patterns = [item for item in data.get("issue_patterns", []) if isinstance(item, dict)]
    warnings = [str(item) for item in data.get("warnings", []) if str(item).strip()] if isinstance(data.get("warnings"), list) else []
    return sanitize_metadata(
        {
            "status": "available" if data and int(summary.get("entry_count") or 0) > 0 else "missing",
            "report_id": data.get("report_id"),
            "entry_count": summary.get("entry_count", 0),
            "effective_count": summary.get("effective_count", 0),
            "mixed_count": summary.get("mixed_count", 0),
            "ineffective_count": summary.get("ineffective_count", 0),
            "waived_count": summary.get("waived_count", 0),
            "average_effectiveness_score": summary.get("average_effectiveness_score"),
            "recurring_issue_count": summary.get("recurring_issue_count", 0),
            "top_recurring_issues": [item.get("issue_type") for item in issue_patterns[:5] if item.get("issue_type")],
            "warning_count": len(warnings),
            "warnings": warnings[:5],
            "stale": bool(data.get("stale", False)),
        }
    )

def write_acceptance_kb_summary(path: Path, store: AcceptanceKnowledgeBaseStore, *, release_id: str | None = None, project_id: str | None = None) -> DomainDocument:
    summary = store.summary(release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary

def knowledge_entry_summary(entry: KnowledgeEntry | DomainDocument) -> DomainDocument:
    data = entry.to_dict() if isinstance(entry, KnowledgeEntry) else _as_document(entry)
    target = _as_document(data.get("target"))
    outcome = _as_document(data.get("outcome"))
    fix = _as_document(data.get("fix"))
    return sanitize_metadata(
        {
            "entry_id": data.get("entry_id"),
            "status": data.get("status"),
            "fix_sprint_id": (_as_document(data.get("source"))).get("fix_sprint_id"),
            "project_id": target.get("project_id"),
            "release_id": target.get("release_id"),
            "song_id": target.get("song_id"),
            "style": target.get("style"),
            "issue_types": _as_list(target.get("issue_types")),
            "outcome_status": outcome.get("outcome_status"),
            "effectiveness_score": outcome.get("effectiveness_score"),
            "waived_count": fix.get("waived_count", 0),
            "warnings": _as_list(data.get("warnings")),
        }
    )

def _issue_patterns(entries: list[KnowledgeEntry]) -> list[DomainDocument]:
    grouped: dict[str, list[KnowledgeEntry]] = {}
    for entry in entries:
        for issue in entry.target.get("issue_types", []) if isinstance(entry.target.get("issue_types"), list) else ["other"]:
            grouped.setdefault(str(issue or "other"), []).append(entry)
    rows = []
    for issue, items in grouped.items():
        scores = [int(entry.outcome.get("effectiveness_score") or 0) for entry in items]
        rows.append(
            {
                "issue_type": issue,
                "entry_count": len(items),
                "effective_count": sum(1 for entry in items if entry.outcome.get("outcome_status") == "effective"),
                "average_effectiveness_score": round(sum(scores) / len(scores), 2) if scores else None,
                "top_styles": _top_values([entry.target.get("style") for entry in items]),
                "common_resolution_types": _top_values([status for entry in items for status in entry.fix.get("resolution_types", [])]),
                "risk": _risk_for_items(items),
            }
        )
    return sorted(rows, key=lambda item: (-int(item.get("entry_count") or 0), str(item.get("issue_type") or "")))

def _style_patterns(entries: list[KnowledgeEntry]) -> list[DomainDocument]:
    grouped: dict[str, list[KnowledgeEntry]] = {}
    for entry in entries:
        grouped.setdefault(str(entry.target.get("style") or "unknown"), []).append(entry)
    rows = []
    for style, items in grouped.items():
        scores = [int(entry.outcome.get("effectiveness_score") or 0) for entry in items]
        recurring = _top_values([issue for entry in items for issue in entry.target.get("issue_types", [])], limit=5)
        average = round(sum(scores) / len(scores), 2) if scores else None
        rows.append({"style": style, "entry_count": len(items), "recurring_issues": recurring, "average_effectiveness_score": average, "stability_status": "stable" if average is not None and average >= 70 else "watch"})
    return sorted(rows, key=lambda item: (-int(item.get("entry_count") or 0), str(item.get("style") or "")))

def _song_patterns(entries: list[KnowledgeEntry]) -> list[DomainDocument]:
    grouped: dict[str, list[KnowledgeEntry]] = {}
    for entry in entries:
        grouped.setdefault(str(entry.target.get("song_id") or "unknown"), []).append(entry)
    rows = []
    for song_id, items in grouped.items():
        latest = sorted(items, key=lambda entry: entry.updated_at, reverse=True)[0]
        rows.append(
            {
                "song_id": song_id,
                "entry_count": len(items),
                "recurring_issues": _top_values([issue for entry in items for issue in entry.target.get("issue_types", [])], limit=5),
                "latest_outcome": latest.outcome.get("outcome_status"),
                "stability_status": "needs_monitoring" if len(items) > 1 or latest.outcome.get("outcome_status") != "effective" else "stable",
            }
        )
    return sorted(rows, key=lambda item: (-int(item.get("entry_count") or 0), str(item.get("song_id") or "")))

def _fix_patterns(entries: list[KnowledgeEntry]) -> list[DomainDocument]:
    return [
        {
            "pattern": "manual_review_task_resolution",
            "entry_count": len(entries),
            "resolved_task_count": sum(len([status for status in entry.fix.get("resolution_types", []) if status == "resolved"]) for entry in entries),
            "waived_count": sum(int(entry.fix.get("waived_count") or 0) for entry in entries),
        }
    ] if entries else []

def _knowledge_recommendations(issue_patterns: list[DomainDocument], style_patterns: list[DomainDocument], song_patterns: list[DomainDocument]) -> list[DomainDocument]:
    rows = []
    if issue_patterns:
        weakest = sorted(issue_patterns, key=lambda item: float(item.get("average_effectiveness_score") or 0))[0]
        rows.append({"recommendation_id": "akbr-rec-001", "type": "monitor_issue", "issue_type": weakest.get("issue_type"), "reason": f"Historical {weakest.get('issue_type')} fixes average {weakest.get('average_effectiveness_score')} effectiveness.", "manual_required": True})
    if style_patterns:
        watch = [item for item in style_patterns if item.get("stability_status") == "watch"]
        if watch:
            rows.append({"recommendation_id": "akbr-rec-002", "type": "review_style", "style": watch[0].get("style"), "reason": f"{watch[0].get('style')} remains in watch status.", "manual_required": True})
    if song_patterns:
        needs = [item for item in song_patterns if item.get("stability_status") == "needs_monitoring"]
        if needs:
            rows.append({"recommendation_id": "akbr-rec-003", "type": "monitor_song", "song_id": needs[0].get("song_id"), "reason": f"{needs[0].get('song_id')} has recurring acceptance history.", "manual_required": True})
    return rows

def _entries_source_hash(entries: list[KnowledgeEntry]) -> str:
    payload = [knowledge_entry_summary(entry) | {"source_fingerprint": entry.source.get("source_fingerprint")} for entry in sorted(entries, key=lambda item: item.entry_id)]
    return stable_hash(payload)

def _sprint_source(sprint: AcceptanceFixSprint) -> DomainDocument:
    return {"fix_sprint_id": sprint.fix_sprint_id, "status": sprint.status, "scope": sprint.scope, "source": sprint.source, "recheck": sprint.recheck, "delta_summary": sprint.delta_summary, "closeout_summary": sprint.closeout_summary}

def _item_source(item: DomainDocument) -> DomainDocument:
    return {"item_id": item.get("item_id"), "status": item.get("status"), "source": item.get("source"), "target": item.get("target"), "review_task_id": item.get("review_task_id"), "resolution": item.get("resolution")}

def _delta_source(delta: DomainDocument) -> DomainDocument:
    return {"source": delta.get("source"), "recheck": delta.get("recheck"), "summary": delta.get("summary"), "issue_deltas": delta.get("issue_deltas"), "song_deltas": delta.get("song_deltas")}

def _closeout_source(closeout: DomainDocument) -> DomainDocument:
    return {"status": closeout.get("status"), "forced": closeout.get("forced"), "checks": closeout.get("checks"), "summary": closeout.get("summary")}

def _issue_types_from_item(item: DomainDocument) -> list[str]:
    target = _as_document(item.get("target"))
    source = _as_document(item.get("source"))
    evidence = _as_document(item.get("evidence"))
    values: list[object] = []
    for container in (target, evidence, source):
        raw = container.get("issue_types")
        if isinstance(raw, list):
            values.extend(str(item).strip().lower() for item in raw if str(item).strip())
    if not values:
        text = f"{item.get('title') or ''} {item.get('summary') or ''}"
        values = _issue_types_from_text(text)
    return sorted(set(values or ["other"]))

def _issue_types_from_text(text: str) -> list[str]:
    lower = str(text or "").lower()
    found = []
    for issue in ("hook", "melody", "harmony", "rhythm", "arrangement", "structure", "lyrics", "sound", "mix", "performance", "rendering", "metadata", "workflow"):
        if issue in lower:
            found.append(issue)
    return found or ["other"]

def _issue_types_from_payload(payload: DomainDocument) -> list[str]:
    raw = payload.get("issue_types")
    if isinstance(raw, list):
        return [str(item).strip().lower() for item in raw if str(item).strip()]
    issue = str(payload.get("issue_type") or "").strip().lower()
    return [issue] if issue else []

def _normalize_issue(value: object) -> str:
    if isinstance(value, list):
        return str(value[0] if value else "").strip().lower()
    return str(value or "").strip().lower()

def _style_from_items(items: list[DomainDocument]) -> str:
    for item in items:
        target = _as_document(item.get("target"))
        if target.get("style"):
            return str(target.get("style"))
    return "unknown"

def _safe_scope(scope: DomainDocument) -> DomainDocument:
    return {"type": str(scope.get("type") or "global"), "project_id": scope.get("project_id"), "release_id": scope.get("release_id"), "song_id": scope.get("song_id"), "style": scope.get("style"), "issue_type": scope.get("issue_type")}

def _risk_for_items(items: list[KnowledgeEntry]) -> str:
    average = sum(int(entry.outcome.get("effectiveness_score") or 0) for entry in items) / max(1, len(items))
    if average < 40:
        return "high"
    if average < 70 or len(items) > 3:
        return "medium"
    return "low"

def _top_values(values: list[object], *, limit: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return [key for key, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]

def _bounded(value: object, limit: int = 300) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())
    return text[:limit]

def _normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9_ -]+", "", str(value or "").lower()).strip()

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value))

def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _validate_id(value: str, prefix: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-\d{{6}}", value):
        raise AcceptanceKnowledgeBaseError(f"Invalid {prefix} id.")
    return value

def _append_event(path: Path, event_type: str, payload: DomainDocument, now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"event_type": event_type, "created_at": now or now_iso(), "payload": payload})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
