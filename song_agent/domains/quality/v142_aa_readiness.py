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

AnalyticsScope = _make_deferred_global('AnalyticsScope')
CaseFact = _make_deferred_global('CaseFact')
_bounded = _make_deferred_global('_bounded')
_fact_issue_types = _make_deferred_global('_fact_issue_types')
_first_text = _make_deferred_global('_first_text')
_issue_excerpt = _make_deferred_global('_issue_excerpt')
_issue_sources = _make_deferred_global('_issue_sources')
_latest_fact = _make_deferred_global('_latest_fact')
_open_task_count = _make_deferred_global('_open_task_count')
_optional_int = _make_deferred_global('_optional_int')
_readiness = _make_deferred_global('_readiness')
_source_summary = _make_deferred_global('_source_summary')
_top_strings = _make_deferred_global('_top_strings')
_warnings = _make_deferred_global('_warnings')
_weakness_score = _make_deferred_global('_weakness_score')
pair = _make_deferred_global('pair')
task = _make_deferred_global('task')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global AnalyticsScope, CaseFact, _bounded, _fact_issue_types, _first_text, _issue_excerpt, _issue_sources, _latest_fact
    global _open_task_count, _optional_int, _readiness, _source_summary, _top_strings, _warnings, _weakness_score
    global pair, task, value
    AnalyticsScope = namespace.get('AnalyticsScope', AnalyticsScope)
    CaseFact = namespace.get('CaseFact', CaseFact)
    _bounded = namespace.get('_bounded', _bounded)
    _fact_issue_types = namespace.get('_fact_issue_types', _fact_issue_types)
    _first_text = namespace.get('_first_text', _first_text)
    _issue_excerpt = namespace.get('_issue_excerpt', _issue_excerpt)
    _issue_sources = namespace.get('_issue_sources', _issue_sources)
    _latest_fact = namespace.get('_latest_fact', _latest_fact)
    _open_task_count = namespace.get('_open_task_count', _open_task_count)
    _optional_int = namespace.get('_optional_int', _optional_int)
    _readiness = namespace.get('_readiness', _readiness)
    _source_summary = namespace.get('_source_summary', _source_summary)
    _top_strings = namespace.get('_top_strings', _top_strings)
    _warnings = namespace.get('_warnings', _warnings)
    _weakness_score = namespace.get('_weakness_score', _weakness_score)
    pair = namespace.get('pair', pair)
    task = namespace.get('task', task)
    value = namespace.get('value', value)
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




def build_acceptance_analytics_report(source: DomainDocument, *, scope: AnalyticsScope, report_id: str, generated_at: str) -> DomainDocument:
    facts = _case_facts(source)
    tasks = [item for item in source.get("review_tasks", []) if isinstance(item, dict)]
    source_hash = stable_hash(source)
    heatmap = _songbook_heatmap(facts, tasks)
    style_breakdown = _style_breakdown(heatmap)
    taxonomy = _issue_taxonomy(facts)
    trend = _trend(source, facts)
    ranking = _weakness_ranking(heatmap, style_breakdown, taxonomy)
    recommendations = _recommendations(heatmap, taxonomy)
    summary = _summary(facts, tasks, taxonomy, recommendations)
    warnings = _warnings(source, facts, summary)
    readiness = _readiness(summary, recommendations, warnings)
    summary["readiness_status"] = readiness
    report = {
        "schema_version": ACCEPTANCE_ANALYTICS_SCHEMA_VERSION,
        "report_id": report_id,
        "scope": scope.to_dict(),
        "generated_at": generated_at,
        "source_hash": source_hash,
        "source_summary": _source_summary(source, facts, tasks),
        "summary": summary,
        "songbook_heatmap": heatmap,
        "style_breakdown": style_breakdown,
        "issue_taxonomy": taxonomy,
        "reviewer_breakdown": _reviewer_breakdown(facts),
        "trend": trend,
        "trend_summary": _trend_summary(trend),
        "weakness_ranking": ranking,
        "recommendations": recommendations,
        "warnings": warnings,
        "stale": False,
    }
    return sanitize_metadata(report)

def acceptance_analytics_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    weaknesses = _as_list(data.get("weakness_ranking"))
    issues = _as_list(data.get("issue_taxonomy"))
    return sanitize_metadata(
        {
            "status": "generated" if data else "missing",
            "report_id": data.get("report_id"),
            "scope": _as_document(data.get("scope")),
            "source_hash": data.get("source_hash"),
            "stale": bool(data.get("stale", False)),
            "readiness_status": summary.get("readiness_status") or "missing",
            "manual_coverage_rate": summary.get("manual_coverage_rate", 0.0),
            "average_rating": summary.get("average_rating"),
            "issue_count": summary.get("issue_count", 0),
            "open_review_task_count": summary.get("open_review_task_count", 0),
            "top_weaknesses": weaknesses[:5],
            "top_issues": issues[:5],
            "recommendation_count": len(data.get("recommendations", [])) if isinstance(data.get("recommendations"), list) else 0,
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
        }
    )

def release_acceptance_analytics_evidence(report: DomainDocument | None) -> DomainDocument:
    summary = acceptance_analytics_summary(report)
    return sanitize_metadata(
        {
            "report_id": summary.get("report_id"),
            "source_hash": summary.get("source_hash"),
            "stale": summary.get("stale"),
            "readiness_status": summary.get("readiness_status"),
            "manual_coverage_rate": summary.get("manual_coverage_rate"),
            "average_rating": summary.get("average_rating"),
            "top_weaknesses": summary.get("top_weaknesses", [])[:3],
            "warnings": summary.get("warnings", []),
        }
    )

def write_acceptance_analytics_summary(path: Path, report: DomainDocument) -> DomainDocument:
    summary = acceptance_analytics_summary(report)
    write_json(path, summary)
    return summary

def _case_facts(source: DomainDocument) -> list[CaseFact]:
    facts: list[CaseFact] = []
    for suite_row in source.get("suites", []):
        if not isinstance(suite_row, dict):
            continue
        suite = _as_document(suite_row.get("suite"))
        for case_row in suite_row.get("cases", []):
            if not isinstance(case_row, dict):
                continue
            case = _as_document(case_row.get("case"))
            review = _as_document(case_row.get("review"))
            health = _as_document(case_row.get("health"))
            request = _as_document(case.get("request_summary"))
            health_summary = _as_document(health.get("summary"))
            facts.append(
                CaseFact(
                    suite_id=str(suite.get("suite_id") or ""),
                    suite_name=str(suite.get("name") or ""),
                    suite_created_at=str(suite.get("created_at") or ""),
                    suite_updated_at=str(suite.get("updated_at") or ""),
                    profile_id=str(suite.get("profile_id") or ""),
                    release_ready_profile=bool(suite.get("release_ready_profile", False)),
                    case_id=str(case.get("case_id") or ""),
                    song_id=str(case.get("song_id") or case.get("case_id") or ""),
                    songbook_id=str(case.get("songbook_id") or ""),
                    songbook_version=str(case.get("songbook_version") or ""),
                    title=str(request.get("title") or case.get("name") or case.get("case_id") or ""),
                    style=str(request.get("style") or ""),
                    status=str(case.get("status") or ""),
                    health_status=str(health.get("status") or "missing"),
                    review_status=str(review.get("status") or "missing"),
                    rating=_optional_int(review.get("rating")),
                    playback_confirmed=bool(review.get("playback_confirmed", False)),
                    review_mode=str(review.get("review_mode") or "manual"),
                    review_source_type=str((review.get("source") or {}).get("source_type") or "") if isinstance(review.get("source"), dict) else "",
                    review_pack_id=str((review.get("source") or {}).get("pack_id") or "") if isinstance(review.get("source"), dict) else "",
                    review_import_id=str((review.get("source") or {}).get("import_id") or "") if isinstance(review.get("source"), dict) else "",
                    listened_by=str(review.get("listened_by") or ""),
                    listened_at=str(review.get("listened_at") or ""),
                    notes=str(review.get("notes") or ""),
                    issues=[str(item) for item in review.get("issues", []) if str(item).strip()] if isinstance(review.get("issues"), list) else [],
                    tags=[str(item) for item in review.get("tags", []) if str(item).strip()] if isinstance(review.get("tags"), list) else [],
                    markers=[item for item in review.get("markers", []) if isinstance(item, dict)] if isinstance(review.get("markers"), list) else [],
                    health_warnings=[item for item in health.get("warnings", []) if isinstance(item, dict)] if isinstance(health.get("warnings"), list) else [],
                    health_blockers=[item for item in health.get("blockers", []) if isinstance(item, dict)] if isinstance(health.get("blockers"), list) else [],
                    project_id=str(case.get("project_id") or ""),
                    version_id=str(case.get("version_id") or ""),
                    quality_overall=_optional_int(health_summary.get("quality_overall")),
                )
            )
    return facts

def _songbook_heatmap(facts: list[CaseFact], tasks: list[DomainDocument]) -> list[DomainDocument]:
    songbook = {song["song_id"]: song for song in builtin_songbook().get("songs", []) if isinstance(song, dict)}
    grouped: dict[str, list[CaseFact]] = {song_id: [] for song_id in songbook}
    for fact in facts:
        grouped.setdefault(fact.song_id, []).append(fact)
    rows = []
    for song_id in sorted(grouped):
        items = grouped[song_id]
        song = songbook.get(song_id, {})
        latest = _latest_fact(items)
        ratings = [fact.rating for fact in items if isinstance(fact.rating, int)]
        issue_types = []
        for fact in items:
            issue_types.extend(_fact_issue_types(fact))
        issue_counts = {issue: issue_types.count(issue) for issue in sorted(set(issue_types))}
        manual_count = sum(1 for fact in items if fact.review_mode == "manual" and fact.review_status in {"accepted", "needs_fix", "rejected", "waived"})
        synthetic_count = sum(1 for fact in items if fact.review_mode == "synthetic")
        open_tasks = _open_task_count(tasks, song_id)
        latest_status = latest.review_status if latest else "missing"
        recurring = sum(1 for count in issue_counts.values() if count > 1)
        row = {
            "song_id": song_id,
            "title": song.get("title") or (latest.title if latest else song_id),
            "style": song.get("style") or (latest.style if latest else ""),
            "case_ids": sorted({fact.case_id for fact in items if fact.case_id}),
            "suite_ids": sorted({fact.suite_id for fact in items if fact.suite_id}),
            "project_id": _first_text([fact.project_id for fact in items]),
            "version_id": _first_text([fact.version_id for fact in items]),
            "case_count": len(items),
            "manual_review_count": manual_count,
            "synthetic_review_count": synthetic_count,
            "latest_status": latest_status,
            "accepted_count": sum(1 for fact in items if fact.review_status == "accepted"),
            "needs_fix_count": sum(1 for fact in items if fact.review_status == "needs_fix"),
            "rejected_count": sum(1 for fact in items if fact.review_status == "rejected"),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "issue_count": len(issue_types),
            "recurring_issue_count": recurring,
            "top_issues": sorted(issue_counts, key=lambda issue: (-issue_counts[issue], issue))[:3],
            "open_review_task_count": open_tasks,
            "manual_coverage_rate": round(manual_count / len(items), 4) if items else 0.0,
            "weakness_score": 0,
            "warnings": [],
        }
        warnings = []
        if items and manual_count == 0 and synthetic_count > 0:
            warnings.append("synthetic_only_review")
        if not items:
            warnings.append("missing_songbook_case")
        row["warnings"] = warnings
        row["weakness_score"] = _weakness_score(row)
        rows.append(row)
    return sorted(rows, key=lambda item: (-int(item.get("weakness_score") or 0), -STATUS_SEVERITY.get(str(item.get("latest_status")), 0), -int(item.get("issue_count") or 0), str(item.get("song_id") or "")))

def _style_breakdown(heatmap: list[DomainDocument]) -> list[DomainDocument]:
    groups: dict[str, list[DomainDocument]] = {}
    for row in heatmap:
        groups.setdefault(str(row.get("style") or "unknown"), []).append(row)
    output: list[DomainDocument] = []
    for style, rows in groups.items():
        ratings: list[float] = [float(value) for row in rows if isinstance((value := row.get("average_rating")), (int, float))]
        case_count = sum(int(row.get("case_count") or 0) for row in rows)
        manual_count = sum(int(row.get("manual_review_count") or 0) for row in rows)
        accepted = sum(int(row.get("accepted_count") or 0) for row in rows)
        issues: list[str] = []
        for row in rows:
            issues.extend([str(item) for item in row.get("top_issues", [])])
        output.append(
            {
                "style": style,
                "song_count": len(rows),
                "case_count": case_count,
                "manual_coverage_rate": round(manual_count / case_count, 4) if case_count else 0.0,
                "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "acceptance_rate": round(accepted / case_count, 4) if case_count else 0.0,
                "top_issues": _top_strings(issues, limit=3),
                "weakness_score": max([int(row.get("weakness_score") or 0) for row in rows] or [0]),
            }
        )
    return sorted(output, key=lambda item: (-int(item.get("weakness_score") or 0), str(item.get("style") or "")))

def _issue_taxonomy(facts: list[CaseFact]) -> list[DomainDocument]:
    buckets: dict[str, DomainDocument] = {}
    for fact in facts:
        for issue_type in _fact_issue_types(fact):
            bucket = buckets.setdefault(issue_type, {"issue_type": issue_type, "count": 0, "song_ids": set(), "source_types": set(), "examples": []})
            bucket["count"] += 1
            bucket["song_ids"].add(fact.song_id)
            bucket["source_types"].update(_issue_sources(fact, issue_type))
            example = _issue_excerpt(fact)
            if example:
                bucket["examples"].append(example)
    rows = []
    for issue_type, bucket in buckets.items():
        count = int(bucket["count"])
        rows.append(
            {
                "issue_type": issue_type,
                "count": count,
                "severity": "high" if count >= 4 or issue_type == "rendering" else "medium" if count >= 2 else "low",
                "song_ids": sorted(bucket["song_ids"]),
                "example_excerpt": str((bucket["examples"] or [""])[0])[:160],
                "source_types": sorted(bucket["source_types"]),
            }
        )
    return sorted(rows, key=lambda item: (-int(item.get("count") or 0), str(item.get("issue_type") or "")))

def _reviewer_breakdown(facts: list[CaseFact]) -> list[DomainDocument]:
    groups: dict[str, list[CaseFact]] = {}
    for fact in facts:
        reviewer = fact.listened_by or "unknown"
        if fact.review_status == "missing":
            continue
        groups.setdefault(reviewer, []).append(fact)
    rows = []
    for reviewer, items in groups.items():
        ratings = [item.rating for item in items if isinstance(item.rating, int)]
        rows.append(
            {
                "reviewer": reviewer[:120],
                "review_count": len(items),
                "manual_review_count": sum(1 for item in items if item.review_mode == "manual"),
                "synthetic_review_count": sum(1 for item in items if item.review_mode == "synthetic"),
                "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "needs_fix_count": sum(1 for item in items if item.review_status == "needs_fix"),
                "rejected_count": sum(1 for item in items if item.review_status == "rejected"),
            }
        )
    return sorted(rows, key=lambda item: (-int(item.get("review_count") or 0), str(item.get("reviewer") or "")))

def _trend(source: DomainDocument, facts: list[CaseFact]) -> list[DomainDocument]:
    by_suite: dict[str, list[CaseFact]] = {}
    suite_meta: dict[str, DomainDocument] = {}
    for suite_row in source.get("suites", []):
        if isinstance(suite_row, dict) and isinstance(suite_row.get("suite"), dict):
            suite_meta[str(suite_row["suite"].get("suite_id") or "")] = suite_row["suite"]
    for fact in facts:
        by_suite.setdefault(fact.suite_id, []).append(fact)
    rows = []
    previous: DomainDocument | None = None
    for suite_id, items in sorted(by_suite.items(), key=lambda pair: str(suite_meta.get(pair[0], {}).get("created_at") or suite_meta.get(pair[0], {}).get("updated_at") or pair[0])):
        ratings = [item.rating for item in items if isinstance(item.rating, int)]
        issue_count = sum(len(_fact_issue_types(item)) for item in items)
        accepted = sum(1 for item in items if item.review_status == "accepted")
        manual = sum(1 for item in items if item.review_mode == "manual" and item.review_status != "missing")
        average = round(sum(ratings) / len(ratings), 2) if ratings else None
        row = {
            "suite_id": suite_id,
            "generated_at": suite_meta.get(suite_id, {}).get("created_at") or suite_meta.get(suite_id, {}).get("updated_at"),
            "case_count": len(items),
            "accepted_rate": round(accepted / len(items), 4) if items else 0.0,
            "average_rating": average,
            "manual_coverage_rate": round(manual / len(items), 4) if items else 0.0,
            "issue_count": issue_count,
            "readiness_status": "ready" if items and accepted == len(items) and manual == len(items) else "watch",
            "trend_status": "flat",
        }
        if previous:
            prev_rating = previous.get("average_rating")
            if isinstance(average, (int, float)) and isinstance(prev_rating, (int, float)) and average > prev_rating and issue_count < int(previous.get("issue_count") or 0):
                row["trend_status"] = "improving"
            elif (isinstance(average, (int, float)) and isinstance(prev_rating, (int, float)) and average < prev_rating) or issue_count > int(previous.get("issue_count") or 0):
                row["trend_status"] = "regressing"
        previous = row
        rows.append(row)
    return rows

def _trend_summary(trend: list[DomainDocument]) -> DomainDocument:
    latest = trend[-1] if trend else {}
    return {"status": latest.get("trend_status") or "none", "suite_count": len(trend)}

def _weakness_ranking(heatmap: list[DomainDocument], styles: list[DomainDocument], taxonomy: list[DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for row in heatmap:
        if int(row.get("weakness_score") or 0) <= 0:
            continue
        rows.append(
            {
                "type": "song",
                "id": row.get("song_id"),
                "song_id": row.get("song_id"),
                "style": row.get("style"),
                "weakness_score": row.get("weakness_score"),
                "latest_status": row.get("latest_status"),
                "issue_count": row.get("issue_count", 0),
                "top_issues": row.get("top_issues", []),
            }
        )
    for style in styles:
        if int(style.get("weakness_score") or 0) >= 40:
            rows.append(
                {
                    "type": "style",
                    "id": style.get("style"),
                    "style": style.get("style"),
                    "weakness_score": style.get("weakness_score"),
                    "issue_count": len(style.get("top_issues", [])),
                    "top_issues": style.get("top_issues", []),
                }
            )
    for issue in taxonomy:
        score = min(100, int(issue.get("count") or 0) * 12)
        if score >= 24:
            rows.append(
                {
                    "type": "issue",
                    "id": issue.get("issue_type"),
                    "issue_type": issue.get("issue_type"),
                    "weakness_score": score,
                    "issue_count": issue.get("count", 0),
                    "top_issues": [issue.get("issue_type")],
                }
            )
    return sorted(rows, key=lambda item: (-int(item.get("weakness_score") or 0), -int(item.get("issue_count") or 0), str(item.get("type") or ""), str(item.get("id") or "")))[:20]

def _recommendations(heatmap: list[DomainDocument], taxonomy: list[DomainDocument]) -> list[DomainDocument]:
    rows = []
    index = 1
    for item in heatmap:
        score = int(item.get("weakness_score") or 0)
        if score < 30:
            continue
        issue_types = [str(issue) for issue in item.get("top_issues", [])]
        rec_type = "create_review_task" if item.get("open_review_task_count", 0) == 0 and issue_types else "run_manual_review_again"
        severity = "high" if score >= 60 or item.get("latest_status") == "rejected" else "medium"
        rows.append(
            {
                "recommendation_id": f"rec-{index:03d}",
                "type": rec_type,
                "severity": severity,
                "title": f"{'Fix' if rec_type == 'create_review_task' else 'Review'} {item.get('song_id')} acceptance weakness",
                "reason": _bounded(f"{item.get('song_id')} has weakness score {score}, latest status {item.get('latest_status')}, and top issues {', '.join(issue_types) or 'none'}.", 300),
                "target": {"song_id": item.get("song_id"), "style": item.get("style"), "project_id": item.get("project_id"), "version_id": item.get("version_id")},
                "evidence": {"case_ids": item.get("case_ids", []), "suite_ids": item.get("suite_ids", []), "issue_types": issue_types},
                "manual_required": True,
                "created_review_task_id": None,
            }
        )
        index += 1
    for issue in taxonomy[:3]:
        if int(issue.get("count") or 0) < 2:
            continue
        rows.append(
            {
                "recommendation_id": f"rec-{index:03d}",
                "type": "create_fix_sprint_later",
                "severity": "medium",
                "title": f"Plan follow-up for recurring {issue.get('issue_type')} issues",
                "reason": _bounded(f"{issue.get('issue_type')} appears in {issue.get('count')} acceptance signals across {len(issue.get('song_ids', []))} song(s).", 300),
                "target": {"issue_type": issue.get("issue_type")},
                "evidence": {"song_ids": issue.get("song_ids", []), "issue_types": [issue.get("issue_type")]},
                "manual_required": True,
                "created_review_task_id": None,
            }
        )
        index += 1
    return rows[:20]

def _summary(facts: list[CaseFact], tasks: list[DomainDocument], taxonomy: list[DomainDocument], recommendations: list[DomainDocument]) -> DomainDocument:
    ratings = [fact.rating for fact in facts if isinstance(fact.rating, int)]
    manual_reviews = [fact for fact in facts if fact.review_mode == "manual" and fact.review_status != "missing"]
    manual_accepted = sum(1 for fact in facts if fact.review_mode == "manual" and fact.review_status == "accepted")
    synthetic_accepted = sum(1 for fact in facts if fact.review_mode == "synthetic" and fact.review_status == "accepted")
    critical_issues = [item for item in taxonomy if item.get("severity") == "high"]
    open_tasks = [task for task in tasks if task.get("status") in OPEN_TASK_STATUSES]
    return {
        "readiness_status": "empty",
        "accepted_count": sum(1 for fact in facts if fact.review_status == "accepted"),
        "manual_accepted_count": manual_accepted,
        "synthetic_accepted_count": synthetic_accepted,
        "needs_fix_count": sum(1 for fact in facts if fact.review_status == "needs_fix"),
        "rejected_count": sum(1 for fact in facts if fact.review_status == "rejected"),
        "waived_count": sum(1 for fact in facts if fact.review_status == "waived"),
        "case_count": len(facts),
        "manual_review_count": len(manual_reviews),
        "synthetic_review_count": sum(1 for fact in facts if fact.review_mode == "synthetic"),
        "manual_coverage_rate": round(len(manual_reviews) / len(facts), 4) if facts else 0.0,
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "issue_count": sum(int(item.get("count") or 0) for item in taxonomy),
        "critical_issue_count": len(critical_issues),
        "open_review_task_count": len(open_tasks),
        "recommendation_count": len(recommendations),
    }
