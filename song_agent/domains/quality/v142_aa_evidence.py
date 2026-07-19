# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.music_acceptance import AcceptanceStore as AcceptanceStore, stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.regression_songbook import builtin_songbook as builtin_songbook
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore
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

AcceptanceAnalyticsError = _make_deferred_global('AcceptanceAnalyticsError')
AnalyticsScope = _make_deferred_global('AnalyticsScope')
CaseFact = _make_deferred_global('CaseFact')
key = _make_deferred_global('key')
keyword = _make_deferred_global('keyword')
track = _make_deferred_global('track')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceAnalyticsError, AnalyticsScope, CaseFact, key, keyword, track
    AcceptanceAnalyticsError = namespace.get('AcceptanceAnalyticsError', AcceptanceAnalyticsError)
    AnalyticsScope = namespace.get('AnalyticsScope', AnalyticsScope)
    CaseFact = namespace.get('CaseFact', CaseFact)
    key = namespace.get('key', key)
    keyword = namespace.get('keyword', keyword)
    track = namespace.get('track', track)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_ANALYTICS_SCHEMA_VERSION = "acceptance_analytics.v1"
ISSUE_TYPES = (
    "hook",
    "melody",
    "harmony",
    "rhythm",
    "arrangement",
    "structure",
    "lyrics",
    "sound",
    "mix",
    "performance",
    "rendering",
    "metadata",
    "workflow",
    "other",
)
ISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hook": ("hook", "chorus", "memorable", "catchy", "refrain", "副歌", "记忆点", "抓耳"),
    "melody": ("melody", "tune", "vocal line", "bland melody", "旋律", "主旋律"),
    "harmony": ("chord", "progression", "key", "modulation", "harmony", "和弦", "调性"),
    "rhythm": ("rhythm", "groove", "beat", "flow", "timing", "节奏", "律动", "卡点"),
    "arrangement": ("arrangement", "instrument", "layer", "build", "drop", "编曲", "层次", "配器"),
    "structure": ("intro", "verse", "bridge", "outro", "length", "transition", "结构", "段落", "转场"),
    "lyrics": ("lyric", "words", "rhyme", "line", "歌词", "押韵", "文案"),
    "sound": ("sound", "tone", "timbre", "synth", "声音", "音色"),
    "mix": ("mix", "balance", "loudness", "clipping", "muddy", "混音", "响度", "爆音"),
    "performance": ("performance", "expression", "human feel", "表现", "情绪", "人味"),
    "rendering": ("midi", "wav", "render", "missing audio", "soundfont", "渲染", "音频缺失"),
    "metadata": ("title", "artist", "credit", "metadata", "元数据", "版权信息"),
    "workflow": ("review", "pack", "import", "signoff", "task", "workflow", "流程", "签核"),
}
STATUS_SEVERITY = {"rejected": 3, "needs_fix": 2, "failed": 2, "missing": 1, "waived": 0, "accepted": 0}
OPEN_TASK_STATUSES = {"open", "candidate_ready", "needs_more_work", "stale"}




def _source_summary(source: DomainDocument, facts: list[CaseFact], tasks: list[DomainDocument]) -> DomainDocument:
    suites = _as_list(source.get("suites"))
    pack_count = 0
    import_count = 0
    for suite in suites:
        if isinstance(suite, dict):
            pack_count += len(suite.get("human_review_packs", [])) if isinstance(suite.get("human_review_packs"), list) else 0
            import_count += len(suite.get("human_review_imports", [])) if isinstance(suite.get("human_review_imports"), list) else 0
    return {
        "suite_count": len(suites),
        "case_count": len(facts),
        "manual_review_count": sum(1 for fact in facts if fact.review_mode == "manual" and fact.review_status != "missing"),
        "synthetic_review_count": sum(1 for fact in facts if fact.review_mode == "synthetic"),
        "human_review_pack_count": pack_count,
        "human_review_import_count": import_count,
        "review_task_count": len(tasks),
    }

def _warnings(source: DomainDocument, facts: list[CaseFact], summary: DomainDocument) -> list[str]:
    warnings = []
    if not source.get("suites"):
        warnings.append("no_acceptance_suites")
    if facts and summary.get("manual_coverage_rate", 0.0) < 1.0:
        warnings.append("manual_review_coverage_incomplete")
    if any(fact.release_ready_profile and fact.review_mode == "synthetic" and fact.review_status == "accepted" for fact in facts):
        warnings.append("release_ready_suite_contains_synthetic_review")
    return warnings

def _readiness(summary: DomainDocument, recommendations: list[DomainDocument], warnings: list[str]) -> str:
    if int(summary.get("case_count") or 0) == 0:
        return "empty"
    if int(summary.get("rejected_count") or 0) > 0 or int(summary.get("critical_issue_count") or 0) > 0:
        return "blocked"
    if int(summary.get("needs_fix_count") or 0) > 0 or any(item.get("severity") == "high" for item in recommendations):
        return "needs_work"
    if warnings or float(summary.get("manual_coverage_rate") or 0.0) < 1.0:
        return "watch"
    return "ready"

def _fact_issue_types(fact: CaseFact) -> list[str]:
    values: list[tuple[str, str]] = []
    for tag in fact.tags:
        values.append(("tag", tag))
    for marker in fact.markers:
        values.append(("marker", f"{marker.get('label', '')} {marker.get('note', '')}"))
    for issue in fact.issues:
        values.append(("issue", issue))
    for item in [*fact.health_warnings, *fact.health_blockers]:
        values.append(("health", f"{item.get('check_id', '')} {item.get('message', '')}"))
    if fact.review_status in {"needs_fix", "rejected"}:
        values.append(("status", fact.review_status))
    values.append(("notes", fact.notes))
    found: set[str] = set()
    for _source_type, text in values:
        for issue_type in _classify_text(text):
            found.add(issue_type)
    return sorted(found) if found else (["other"] if fact.review_status in {"needs_fix", "rejected"} else [])

def _issue_sources(fact: CaseFact, issue_type: str) -> list[str]:
    sources = []
    if any(issue_type in _classify_text(tag) for tag in fact.tags):
        sources.append("tag")
    if any(issue_type in _classify_text(f"{marker.get('label', '')} {marker.get('note', '')}") for marker in fact.markers):
        sources.append("marker")
    if issue_type in _classify_text(fact.notes):
        sources.append("notes")
    if fact.health_warnings or fact.health_blockers:
        sources.append("health")
    if fact.review_status in {"needs_fix", "rejected"}:
        sources.append("review_status")
    return sorted(set(sources or ["manual_review"]))

def _classify_text(value: str) -> list[str]:
    text = sanitize_sensitive_text(str(value or "")).lower()
    found = []
    for issue_type, keywords in ISSUE_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            found.append(issue_type)
    return found

def _issue_excerpt(fact: CaseFact) -> str:
    for value in [*fact.issues, fact.notes, *[str(marker.get("note") or marker.get("label") or "") for marker in fact.markers]]:
        text = _bounded(value, 160)
        if text:
            return text
    return ""

def _weakness_score(row: DomainDocument) -> int:
    score = 0
    latest = str(row.get("latest_status") or "")
    if latest == "rejected":
        score += 35
    elif latest in {"needs_fix", "failed"}:
        score += 25
    rating = row.get("average_rating")
    if isinstance(rating, (int, float)):
        if rating < 3.0:
            score += 20
        elif rating < 4.0:
            score += 10
    score += min(int(row.get("issue_count") or 0) * 4, 20)
    score += min(int(row.get("recurring_issue_count") or 0) * 8, 20)
    if float(row.get("manual_coverage_rate") or 0.0) < 1.0:
        score += 10
    if int(row.get("open_review_task_count") or 0) > 0:
        score += 10
    return min(score, 100)

def _latest_fact(items: list[CaseFact]) -> CaseFact | None:
    if not items:
        return None
    return sorted(items, key=lambda fact: (fact.listened_at or fact.suite_updated_at or fact.suite_created_at, fact.case_id))[-1]

def _open_task_count(tasks: list[DomainDocument], song_id: str) -> int:
    count = 0
    for task in tasks:
        if task.get("status") not in OPEN_TASK_STATUSES:
            continue
        payload = json.dumps({"source": task.get("source"), "target": task.get("target"), "title": task.get("title")}, ensure_ascii=False)
        if song_id and song_id in payload:
            count += 1
    return count

def _top_strings(values: list[str], *, limit: int) -> list[str]:
    counts = {value: values.count(value) for value in set(values) if value}
    return sorted(counts, key=lambda value: (-counts[value], value))[:limit]

def _first_text(values: list[str]) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None

def _suite_source(data: DomainDocument) -> DomainDocument:
    keys = (
        "suite_id",
        "name",
        "status",
        "mode",
        "profile_id",
        "songbook_id",
        "songbook_version",
        "require_manual_review",
        "allow_synthetic_review",
        "release_ready_profile",
        "min_rating",
        "created_at",
        "updated_at",
    )
    return {key: data.get(key) for key in keys}

def _case_source(data: DomainDocument) -> DomainDocument:
    keys = (
        "case_id",
        "suite_id",
        "name",
        "source_type",
        "status",
        "song_id",
        "songbook_id",
        "songbook_version",
        "expectations",
        "request_summary",
        "project_id",
        "version_id",
        "health_summary",
        "created_at",
        "updated_at",
    )
    return {key: data.get(key) for key in keys}

def _review_source(data: DomainDocument) -> DomainDocument:
    keys = ("case_id", "status", "rating", "playback_confirmed", "listened_by", "listened_at", "audio_mode", "notes", "issues", "waivers", "review_mode", "source", "tags", "markers")
    return {key: data.get(key) for key in keys}

def _health_source(data: DomainDocument) -> DomainDocument:
    return {
        "status": data.get("status"),
        "summary": _as_document(data.get("summary")),
        "warnings": _as_list(data.get("warnings")),
        "blockers": _as_list(data.get("blockers")),
    }

def _report_source(data: DomainDocument) -> DomainDocument:
    return {
        "suite_id": data.get("suite_id"),
        "status": data.get("status"),
        "source_hash": data.get("source_hash"),
        "profile_id": data.get("profile_id"),
        "songbook_id": data.get("songbook_id"),
        "songbook_version": data.get("songbook_version"),
        "summary": _as_document(data.get("summary")),
        "blockers": _as_list(data.get("blockers")),
    }

def _case_in_scope(case: DomainDocument, scope: AnalyticsScope) -> bool:
    if scope.type == "project" and scope.project_id:
        return str(case.get("project_id") or "") == scope.project_id
    return True

def _scope_project_ids(scope: AnalyticsScope, release_store: ReleaseStore, project_store: ProjectStore) -> set[str]:
    if scope.type == "project" and scope.project_id:
        return {scope.project_id}
    if scope.type == "release" and scope.release_id:
        release = release_store.get_release(scope.release_id)
        return {track.project_id for track in release.tracks}
    return set()

def _suite_matches_release(suite_id: str, project_ids: set[str], store: AcceptanceStore) -> bool:
    if not project_ids:
        return False
    return any(case.project_id in project_ids for case in store.list_cases(suite_id))

def _release_acceptance_suite_id(signoff: DomainDocument) -> str:
    gate = _as_document(signoff.get("acceptance_gate"))
    return str(gate.get("suite_id") or "")

def _release_ids_for_project(project_id: str, release_store: ReleaseStore) -> list[str]:
    rows = []
    for release in release_store.list_releases(include_hidden=True):
        if any(track.project_id == project_id for track in release.tracks):
            rows.append(release.release_id)
    return sorted(rows)

def _scope_from_report(report: DomainDocument) -> AnalyticsScope:
    scope = _as_document(report.get("scope"))
    return AnalyticsScope.from_values(
        scope_type=str(scope.get("type") or "global"),
        suite_id=scope.get("suite_id"),
        release_id=scope.get("release_id"),
        project_id=scope.get("project_id"),
    )

def _report_id(scope: AnalyticsScope, source: DomainDocument, now: str) -> str:
    digits = re.sub(r"[^0-9]", "", now)[:14].ljust(14, "0")
    return f"analytics-{digits}-{stable_hash({'scope': scope.to_dict(), 'source': source})[:8]}"

def _optional_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not re.match(r"^[A-Za-z0-9_.:-]+$", text):
        raise AcceptanceAnalyticsError("Invalid analytics scope id.")
    return text

def _safe_storage_key(prefix: str, value: str | None) -> str:
    text = value or "missing"
    return f"{prefix}-{re.sub(r'[^A-Za-z0-9_.-]+', '-', text).strip('-') or 'missing'}"

def _optional_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]

def _append_event(path: Path, event_type: str, payload: DomainDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"timestamp": now_iso(), "event": event_type, **payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

def _matching_open_review_task(project_dir: Path, song_id: str, issue_types: list[str]) -> ReviewTask | None:
    store = ReviewTaskStore(project_dir)
    for task in store.list_tasks(include_archived=True):
        if task.status not in OPEN_TASK_STATUSES:
            continue
        source = _as_document(task.source)
        if source.get("source_type") != "acceptance_analytics":
            continue
        if song_id and source.get("song_id") != song_id:
            continue
        existing_issues = [str(item) for item in source.get("issue_types", [])] if isinstance(source.get("issue_types"), list) else []
        if sorted(existing_issues) == sorted(issue_types):
            return task
    return None
