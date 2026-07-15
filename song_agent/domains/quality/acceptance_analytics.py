from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.domains.quality.music_acceptance import AcceptanceStore, stable_hash
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import ProjectStore, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.creation.regression_songbook import builtin_songbook
from song_agent.domains.delivery.releases import ReleaseStore
from song_agent.domains.quality.review_tasks import REVIEW_TASK_SCHEMA_VERSION, ReviewTask, ReviewTaskStore


ACCEPTANCE_ANALYTICS_ROOT = Path(".musicforge") / "aa"
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


class AcceptanceAnalyticsError(ValueError):
    pass


class AcceptanceAnalyticsNotFoundError(AcceptanceAnalyticsError):
    pass


class AcceptanceAnalyticsStateError(AcceptanceAnalyticsError):
    pass


@dataclass(frozen=True)
class AnalyticsScope:
    type: str = "global"
    suite_id: str | None = None
    release_id: str | None = None
    project_id: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        scope_type: str = "global",
        suite_id: str | None = None,
        release_id: str | None = None,
        project_id: str | None = None,
    ) -> "AnalyticsScope":
        value = str(scope_type or "global").strip() or "global"
        if value not in {"global", "suite", "release", "project"}:
            raise AcceptanceAnalyticsError("scope must be global, suite, release, or project.")
        return cls(
            type=value,
            suite_id=_optional_id(suite_id),
            release_id=_optional_id(release_id),
            project_id=_optional_id(project_id),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "project_id": self.project_id,
            "release_id": self.release_id,
            "suite_id": self.suite_id,
        }

    def storage_key(self) -> str:
        if self.type == "suite":
            return _safe_storage_key("suite", self.suite_id)
        if self.type == "release":
            return _safe_storage_key("release", self.release_id)
        if self.type == "project":
            return _safe_storage_key("project", self.project_id)
        return "global"


@dataclass
class CaseFact:
    suite_id: str
    suite_name: str
    suite_created_at: str
    suite_updated_at: str
    profile_id: str
    release_ready_profile: bool
    case_id: str
    song_id: str
    songbook_id: str
    songbook_version: str
    title: str
    style: str
    status: str
    health_status: str
    review_status: str
    rating: int | None
    playback_confirmed: bool
    review_mode: str
    review_source_type: str
    review_pack_id: str
    review_import_id: str
    listened_by: str
    listened_at: str
    notes: str
    issues: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    markers: list[dict[str, Any]] = field(default_factory=list)
    health_warnings: list[dict[str, Any]] = field(default_factory=list)
    health_blockers: list[dict[str, Any]] = field(default_factory=list)
    project_id: str = ""
    version_id: str = ""
    quality_overall: int | None = None


class AcceptanceAnalyticsStore:
    def __init__(
        self,
        root: Path | str = ACCEPTANCE_ANALYTICS_ROOT,
        *,
        acceptance_store: AcceptanceStore | None = None,
        project_store: ProjectStore | None = None,
        release_store: ReleaseStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.acceptance_store = acceptance_store or AcceptanceStore()
        self.project_store = project_store or self.acceptance_store.project_store
        self.release_store = release_store or ReleaseStore(project_store=self.project_store)
        self.lock = threading.RLock()

    def reports_dir(self) -> Path:
        return self.root / "reports"

    def scope_dir(self, scope: AnalyticsScope) -> Path:
        base = self.reports_dir().resolve()
        target = (base / scope.storage_key()).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise AcceptanceAnalyticsError("Refusing to operate outside acceptance analytics reports.") from exc
        return target

    def report_dir(self, report_id: str) -> Path:
        base = self.reports_dir().resolve()
        for path in base.glob("*/analytics-*"):
            if path.name == report_id:
                return path
        raise AcceptanceAnalyticsNotFoundError(report_id)

    def latest_path(self, scope: AnalyticsScope) -> Path:
        return self.scope_dir(scope) / "latest.json"

    def latest_report(self, scope: AnalyticsScope) -> dict[str, Any]:
        path = self.latest_path(scope)
        if not path.exists():
            return self.refresh(scope)
        report = read_json(path)
        return self._with_stale(report)

    def get_report(self, report_id: str) -> dict[str, Any]:
        path = self.report_dir(report_id) / "report.json"
        if not path.exists():
            raise AcceptanceAnalyticsNotFoundError(report_id)
        return self._with_stale(read_json(path))

    def refresh(self, scope: AnalyticsScope | None = None, *, now: str | None = None) -> dict[str, Any]:
        scope = scope or AnalyticsScope()
        now = now or now_iso()
        with self.lock:
            source = self.source_state(scope)
            report = build_acceptance_analytics_report(
                source,
                scope=scope,
                report_id=_report_id(scope, source, now),
                generated_at=now,
            )
            scope_dir = self.scope_dir(scope)
            report_dir = scope_dir / str(report["report_id"])
            report_dir.mkdir(parents=True, exist_ok=True)
            write_json(report_dir / "report.json", report)
            write_json(report_dir / "source.json", report.get("source_summary", {}))
            _append_event(report_dir / "events.jsonl", "analytics_report_refreshed", {"report_id": report["report_id"], "scope": scope.to_dict()})
            write_json(self.latest_path(scope), report)
            return report

    def source_state(self, scope: AnalyticsScope | None = None) -> dict[str, Any]:
        scope = scope or AnalyticsScope()
        suite_ids = self._suite_ids_for_scope(scope)
        suites = []
        for suite_id in suite_ids:
            try:
                suite = self.acceptance_store.get_suite(suite_id)
            except Exception:
                continue
            if scope.type != "suite" and suite.mode == "acceptance_fix_recheck":
                continue
            cases = []
            for case in self.acceptance_store.list_cases(suite_id):
                health = self.acceptance_store.read_health(suite_id, case.case_id, default={})
                review = self.acceptance_store.read_review(suite_id, case.case_id, default={})
                if not _case_in_scope(case.to_dict(), scope):
                    continue
                cases.append(
                    {
                        "case": _case_source(case.to_dict()),
                        "health": _health_source(health),
                        "review": _review_source(review),
                    }
                )
            if not cases and scope.type in {"project"}:
                continue
            report = self.acceptance_store.read_report(suite_id, default={})
            packs, imports = self._human_review_pack_sources(suite_id)
            suites.append(
                {
                    "suite": _suite_source(suite.to_dict()),
                    "report": _report_source(report),
                    "cases": sorted(cases, key=lambda item: str(item.get("case", {}).get("case_id") or "")),
                    "human_review_packs": packs,
                    "human_review_imports": imports,
                }
            )
        review_tasks = self._review_task_sources(scope)
        release = self._release_source(scope)
        return sanitize_metadata(
            {
                "scope": scope.to_dict(),
                "suites": sorted(suites, key=lambda item: str(item.get("suite", {}).get("suite_id") or "")),
                "review_tasks": review_tasks,
                "release": release,
            }
        )

    def create_review_task_from_recommendation(self, report_id: str, recommendation_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = self.get_report(report_id)
        if report.get("stale") is True:
            raise AcceptanceAnalyticsStateError("Acceptance analytics report is stale. Refresh analytics before creating ReviewTasks.")
        recommendation = next((item for item in report.get("recommendations", []) if isinstance(item, dict) and item.get("recommendation_id") == recommendation_id), None)
        if not recommendation:
            raise AcceptanceAnalyticsNotFoundError(recommendation_id)
        if recommendation.get("type") != "create_review_task":
            raise AcceptanceAnalyticsStateError("Recommendation does not support ReviewTask creation.")
        target = recommendation.get("target") if isinstance(recommendation.get("target"), dict) else {}
        project_id = str(target.get("project_id") or payload.get("project_id") or "").strip()
        if not project_id:
            raise AcceptanceAnalyticsStateError("Recommendation cannot create ReviewTask without project_id.")
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.ensure_project_dir_is_safe(project_dir)
        document = self.project_store.get_project(project_id)
        issue_types = [str(item) for item in (recommendation.get("evidence") or {}).get("issue_types", []) if str(item).strip()] if isinstance(recommendation.get("evidence"), dict) else []
        existing = _matching_open_review_task(project_dir, str(target.get("song_id") or ""), issue_types)
        if existing:
            return {"status": "existing", "project_id": project_id, "task_id": existing.task_id, "recommendation_id": recommendation_id}
        store = ReviewTaskStore(project_dir)
        with store.lock:
            task_id, task_dir = store._reserve_task_dir()
            now = now_iso()
            task = ReviewTask.from_dict(
                {
                    "schema_version": REVIEW_TASK_SCHEMA_VERSION,
                    "task_id": task_id,
                    "project_id": project_id,
                    "parent_version_id": str(target.get("version_id") or document.state.final_version_id or document.state.selected_version_id or document.state.latest_version_id or ""),
                    "preview_id": f"acceptance-analytics-{recommendation_id}",
                    "audition_id": f"acceptance-analytics-{report_id}",
                    "status": "open",
                    "priority": 86 if recommendation.get("severity") == "high" else 72,
                    "title": str(recommendation.get("title") or "Acceptance analytics follow-up")[:160],
                    "summary": str(recommendation.get("reason") or "")[:800],
                    "source": {
                        "source_type": "acceptance_analytics",
                        "report_id": report_id,
                        "recommendation_id": recommendation_id,
                        "song_id": target.get("song_id"),
                        "issue_types": issue_types,
                    },
                    "review_snapshot": {"recommendation": recommendation},
                    "target": {"scope": "project", "project_id": project_id, "song_id": target.get("song_id")},
                    "hashes": {"analytics_source_hash": str(report.get("source_hash") or "")},
                    "counts": {"candidate_count": 0, "ready_candidate_count": 0, "failed_candidate_count": 0},
                    "created_at": now,
                    "updated_at": now,
                }
            )
            write_json(task_dir / "task.json", task.to_dict())
            _append_event(task_dir / "events.jsonl", "review_task_created_from_acceptance_analytics", {"report_id": report_id, "recommendation_id": recommendation_id})
        return {"status": "created", "project_id": project_id, "task_id": task.task_id, "recommendation_id": recommendation_id}

    def _with_stale(self, report: dict[str, Any]) -> dict[str, Any]:
        scope = _scope_from_report(report)
        current_hash = stable_hash(self.source_state(scope))
        stored_hash = str(report.get("source_hash") or "")
        stale = bool(stored_hash and current_hash != stored_hash)
        clean = dict(report)
        clean["stale"] = stale
        clean["current_source_hash"] = current_hash
        clean["stale_reason"] = "source_changed" if stale else ""
        return sanitize_metadata(clean)

    def _suite_ids_for_scope(self, scope: AnalyticsScope) -> list[str]:
        if scope.type == "suite":
            if not scope.suite_id:
                raise AcceptanceAnalyticsError("suite_id is required for suite analytics.")
            self.acceptance_store.get_suite(scope.suite_id)
            return [scope.suite_id]
        if scope.type == "release":
            if not scope.release_id:
                raise AcceptanceAnalyticsError("release_id is required for release analytics.")
            release = self.release_store.get_release(scope.release_id)
            project_ids = {track.project_id for track in release.tracks}
            explicit_suite = _release_acceptance_suite_id(self.release_store.read_signoff(scope.release_id, default={}))
            suite_ids = [suite.suite_id for suite in self.acceptance_store.list_suites(include_archived=True) if _suite_matches_release(suite.suite_id, project_ids, self.acceptance_store)]
            if explicit_suite and explicit_suite not in suite_ids:
                suite_ids.append(explicit_suite)
            return sorted(set(suite_ids))
        return [suite.suite_id for suite in self.acceptance_store.list_suites(include_archived=True)]

    def _human_review_pack_sources(self, suite_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        suite_dir = self.acceptance_store.suite_dir(suite_id)
        packs = []
        for path in (suite_dir / "human-review-packs").glob("hrpack-*/pack.json"):
            try:
                data = read_json(path)
            except Exception:
                continue
            packs.append(
                {
                    "pack_id": data.get("pack_id"),
                    "status": data.get("status"),
                    "source_hash": data.get("source_hash"),
                    "case_count": data.get("case_count", 0),
                    "latest_import_summary": data.get("latest_import_summary") if isinstance(data.get("latest_import_summary"), dict) else {},
                    "updated_at": data.get("updated_at"),
                }
            )
        imports = []
        for path in (suite_dir / "review-imports").glob("review-import-*/review-import.json"):
            try:
                data = read_json(path)
            except Exception:
                continue
            summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
            imports.append(
                {
                    "import_id": data.get("import_id"),
                    "pack_id": data.get("pack_id"),
                    "pack_source_hash": data.get("pack_source_hash"),
                    "imported_at": data.get("imported_at"),
                    "summary": summary,
                }
            )
        return (
            sorted(sanitize_metadata(packs), key=lambda item: str(item.get("pack_id") or "")),
            sorted(sanitize_metadata(imports), key=lambda item: str(item.get("import_id") or "")),
        )

    def _review_task_sources(self, scope: AnalyticsScope) -> list[dict[str, Any]]:
        project_ids = _scope_project_ids(scope, self.release_store, self.project_store)
        rows = []
        for document in self.project_store.list_projects(include_hidden=True):
            project_id = document.state.project_id
            if project_ids and project_id not in project_ids:
                continue
            store = ReviewTaskStore(self.project_store.project_dir(project_id))
            for task in store.list_tasks(include_archived=True):
                source = task.source if isinstance(task.source, dict) else {}
                if source.get("source_type") == "acceptance_fix_sprint":
                    continue
                if scope.type == "suite" and source.get("suite_id") != scope.suite_id:
                    continue
                rows.append(
                    {
                        "task_id": task.task_id,
                        "project_id": task.project_id,
                        "status": task.status,
                        "priority": task.priority,
                        "title": task.title,
                        "source": source,
                        "target": task.target,
                        "created_at": task.created_at,
                        "updated_at": task.updated_at,
                    }
                )
        return sorted(sanitize_metadata(rows), key=lambda item: str(item.get("task_id") or ""))

    def _release_source(self, scope: AnalyticsScope) -> dict[str, Any]:
        if scope.type != "release" or not scope.release_id:
            return {}
        release = self.release_store.get_release(scope.release_id)
        signoff = self.release_store.read_signoff(scope.release_id, default={})
        return {"release_id": release.release_id, "name": release.name, "track_project_ids": [track.project_id for track in release.tracks], "signoff": signoff}


def build_acceptance_analytics_report(source: dict[str, Any], *, scope: AnalyticsScope, report_id: str, generated_at: str) -> dict[str, Any]:
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


def acceptance_analytics_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    weaknesses = data.get("weakness_ranking") if isinstance(data.get("weakness_ranking"), list) else []
    issues = data.get("issue_taxonomy") if isinstance(data.get("issue_taxonomy"), list) else []
    return sanitize_metadata(
        {
            "status": "generated" if data else "missing",
            "report_id": data.get("report_id"),
            "scope": data.get("scope") if isinstance(data.get("scope"), dict) else {},
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


def release_acceptance_analytics_evidence(report: dict[str, Any] | None) -> dict[str, Any]:
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


def write_acceptance_analytics_summary(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    summary = acceptance_analytics_summary(report)
    write_json(path, summary)
    return summary


def _case_facts(source: dict[str, Any]) -> list[CaseFact]:
    facts: list[CaseFact] = []
    for suite_row in source.get("suites", []):
        if not isinstance(suite_row, dict):
            continue
        suite = suite_row.get("suite") if isinstance(suite_row.get("suite"), dict) else {}
        for case_row in suite_row.get("cases", []):
            if not isinstance(case_row, dict):
                continue
            case = case_row.get("case") if isinstance(case_row.get("case"), dict) else {}
            review = case_row.get("review") if isinstance(case_row.get("review"), dict) else {}
            health = case_row.get("health") if isinstance(case_row.get("health"), dict) else {}
            request = case.get("request_summary") if isinstance(case.get("request_summary"), dict) else {}
            health_summary = health.get("summary") if isinstance(health.get("summary"), dict) else {}
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


def _songbook_heatmap(facts: list[CaseFact], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _style_breakdown(heatmap: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in heatmap:
        groups.setdefault(str(row.get("style") or "unknown"), []).append(row)
    output = []
    for style, rows in groups.items():
        ratings = [row.get("average_rating") for row in rows if isinstance(row.get("average_rating"), (int, float))]
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


def _issue_taxonomy(facts: list[CaseFact]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
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


def _reviewer_breakdown(facts: list[CaseFact]) -> list[dict[str, Any]]:
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


def _trend(source: dict[str, Any], facts: list[CaseFact]) -> list[dict[str, Any]]:
    by_suite: dict[str, list[CaseFact]] = {}
    suite_meta: dict[str, dict[str, Any]] = {}
    for suite_row in source.get("suites", []):
        if isinstance(suite_row, dict) and isinstance(suite_row.get("suite"), dict):
            suite_meta[str(suite_row["suite"].get("suite_id") or "")] = suite_row["suite"]
    for fact in facts:
        by_suite.setdefault(fact.suite_id, []).append(fact)
    rows = []
    previous: dict[str, Any] | None = None
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


def _trend_summary(trend: list[dict[str, Any]]) -> dict[str, Any]:
    latest = trend[-1] if trend else {}
    return {"status": latest.get("trend_status") or "none", "suite_count": len(trend)}


def _weakness_ranking(heatmap: list[dict[str, Any]], styles: list[dict[str, Any]], taxonomy: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def _recommendations(heatmap: list[dict[str, Any]], taxonomy: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _summary(facts: list[CaseFact], tasks: list[dict[str, Any]], taxonomy: list[dict[str, Any]], recommendations: list[dict[str, Any]]) -> dict[str, Any]:
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


def _source_summary(source: dict[str, Any], facts: list[CaseFact], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    suites = source.get("suites") if isinstance(source.get("suites"), list) else []
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


def _warnings(source: dict[str, Any], facts: list[CaseFact], summary: dict[str, Any]) -> list[str]:
    warnings = []
    if not source.get("suites"):
        warnings.append("no_acceptance_suites")
    if facts and summary.get("manual_coverage_rate", 0.0) < 1.0:
        warnings.append("manual_review_coverage_incomplete")
    if any(fact.release_ready_profile and fact.review_mode == "synthetic" and fact.review_status == "accepted" for fact in facts):
        warnings.append("release_ready_suite_contains_synthetic_review")
    return warnings


def _readiness(summary: dict[str, Any], recommendations: list[dict[str, Any]], warnings: list[str]) -> str:
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


def _weakness_score(row: dict[str, Any]) -> int:
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


def _open_task_count(tasks: list[dict[str, Any]], song_id: str) -> int:
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


def _suite_source(data: dict[str, Any]) -> dict[str, Any]:
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


def _case_source(data: dict[str, Any]) -> dict[str, Any]:
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


def _review_source(data: dict[str, Any]) -> dict[str, Any]:
    keys = ("case_id", "status", "rating", "playback_confirmed", "listened_by", "listened_at", "audio_mode", "notes", "issues", "waivers", "review_mode", "source", "tags", "markers")
    return {key: data.get(key) for key in keys}


def _health_source(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": data.get("status"),
        "summary": data.get("summary") if isinstance(data.get("summary"), dict) else {},
        "warnings": data.get("warnings") if isinstance(data.get("warnings"), list) else [],
        "blockers": data.get("blockers") if isinstance(data.get("blockers"), list) else [],
    }


def _report_source(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite_id": data.get("suite_id"),
        "status": data.get("status"),
        "source_hash": data.get("source_hash"),
        "profile_id": data.get("profile_id"),
        "songbook_id": data.get("songbook_id"),
        "songbook_version": data.get("songbook_version"),
        "summary": data.get("summary") if isinstance(data.get("summary"), dict) else {},
        "blockers": data.get("blockers") if isinstance(data.get("blockers"), list) else [],
    }


def _case_in_scope(case: dict[str, Any], scope: AnalyticsScope) -> bool:
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


def _release_acceptance_suite_id(signoff: dict[str, Any]) -> str:
    gate = signoff.get("acceptance_gate") if isinstance(signoff.get("acceptance_gate"), dict) else {}
    return str(gate.get("suite_id") or "")


def _release_ids_for_project(project_id: str, release_store: ReleaseStore) -> list[str]:
    rows = []
    for release in release_store.list_releases(include_hidden=True):
        if any(track.project_id == project_id for track in release.tracks):
            rows.append(release.release_id)
    return sorted(rows)


def _scope_from_report(report: dict[str, Any]) -> AnalyticsScope:
    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    return AnalyticsScope.from_values(
        scope_type=str(scope.get("type") or "global"),
        suite_id=scope.get("suite_id"),
        release_id=scope.get("release_id"),
        project_id=scope.get("project_id"),
    )


def _report_id(scope: AnalyticsScope, source: dict[str, Any], now: str) -> str:
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


def _optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]


def _append_event(path: Path, event_type: str, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"timestamp": now_iso(), "event": event_type, **payload})
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def _matching_open_review_task(project_dir: Path, song_id: str, issue_types: list[str]) -> ReviewTask | None:
    store = ReviewTaskStore(project_dir)
    for task in store.list_tasks(include_archived=True):
        if task.status not in OPEN_TASK_STATUSES:
            continue
        source = task.source if isinstance(task.source, dict) else {}
        if source.get("source_type") != "acceptance_analytics":
            continue
        if song_id and source.get("song_id") != song_id:
            continue
        existing_issues = [str(item) for item in source.get("issue_types", [])] if isinstance(source.get("issue_types"), list) else []
        if sorted(existing_issues) == sorted(issue_types):
            return task
    return None
