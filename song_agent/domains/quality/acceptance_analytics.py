# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.music_acceptance import AcceptanceStore as AcceptanceStore, stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.regression_songbook import builtin_songbook as builtin_songbook
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore
from song_agent.domains.quality.review_tasks import REVIEW_TASK_SCHEMA_VERSION as REVIEW_TASK_SCHEMA_VERSION, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore


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

    def to_dict(self) -> DomainDocument:
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
    markers: list[ImplementationDocument] = field(default_factory=list)
    health_warnings: list[ImplementationDocument] = field(default_factory=list)
    health_blockers: list[ImplementationDocument] = field(default_factory=list)
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

    def latest_report(self, scope: AnalyticsScope) -> DomainDocument:
        path = self.latest_path(scope)
        if not path.exists():
            return self.refresh(scope)
        report = read_json(path)
        return self._with_stale(report)

    def get_report(self, report_id: str) -> DomainDocument:
        path = self.report_dir(report_id) / "report.json"
        if not path.exists():
            raise AcceptanceAnalyticsNotFoundError(report_id)
        return self._with_stale(read_json(path))

    def refresh(self, scope: AnalyticsScope | None = None, *, now: str | None = None) -> DomainDocument:
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

    def source_state(self, scope: AnalyticsScope | None = None) -> DomainDocument:
        scope = scope or AnalyticsScope()
        suite_ids = self._suite_ids_for_scope(scope)
        suites: list[ImplementationDocument] = []
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

    def create_review_task_from_recommendation(self, report_id: str, recommendation_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = self.get_report(report_id)
        if report.get("stale") is True:
            raise AcceptanceAnalyticsStateError("Acceptance analytics report is stale. Refresh analytics before creating ReviewTasks.")
        recommendation = next((item for item in report.get("recommendations", []) if isinstance(item, dict) and item.get("recommendation_id") == recommendation_id), None)
        if not recommendation:
            raise AcceptanceAnalyticsNotFoundError(recommendation_id)
        if recommendation.get("type") != "create_review_task":
            raise AcceptanceAnalyticsStateError("Recommendation does not support ReviewTask creation.")
        target = _as_document(recommendation.get("target"))
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

    def _with_stale(self, report: ImplementationDocument) -> ImplementationDocument:
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

    def _human_review_pack_sources(self, suite_id: str) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
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
                    "latest_import_summary": _as_document(data.get("latest_import_summary")),
                    "updated_at": data.get("updated_at"),
                }
            )
        imports = []
        for path in (suite_dir / "review-imports").glob("review-import-*/review-import.json"):
            try:
                data = read_json(path)
            except Exception:
                continue
            summary = _as_document(data.get("summary"))
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

    def _review_task_sources(self, scope: AnalyticsScope) -> list[ImplementationDocument]:
        project_ids = _scope_project_ids(scope, self.release_store, self.project_store)
        rows = []
        for document in self.project_store.list_projects(include_hidden=True):
            project_id = document.state.project_id
            if project_ids and project_id not in project_ids:
                continue
            store = ReviewTaskStore(self.project_store.project_dir(project_id))
            for task in store.list_tasks(include_archived=True):
                source = _as_document(task.source)
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

    def _release_source(self, scope: AnalyticsScope) -> ImplementationDocument:
        if scope.type != "release" or not scope.release_id:
            return {}
        release = self.release_store.get_release(scope.release_id)
        signoff = self.release_store.read_signoff(scope.release_id, default={})
        return {"release_id": release.release_id, "name": release.name, "track_project_ids": [track.project_id for track in release.tracks], "signoff": signoff}


from song_agent.domains.quality import v142_aa_readiness as _v142_aa_readiness
from song_agent.domains.quality.v142_aa_readiness import build_acceptance_analytics_report as build_acceptance_analytics_report, acceptance_analytics_summary as acceptance_analytics_summary, release_acceptance_analytics_evidence as release_acceptance_analytics_evidence, write_acceptance_analytics_summary as write_acceptance_analytics_summary, _case_facts as _case_facts, _songbook_heatmap as _songbook_heatmap, _style_breakdown as _style_breakdown, _issue_taxonomy as _issue_taxonomy, _reviewer_breakdown as _reviewer_breakdown, _trend as _trend, _trend_summary as _trend_summary, _weakness_ranking as _weakness_ranking, _recommendations as _recommendations, _summary as _summary
from song_agent.domains.quality import v142_aa_evidence as _v142_aa_evidence
from song_agent.domains.quality.v142_aa_evidence import _source_summary as _source_summary, _warnings as _warnings, _readiness as _readiness, _fact_issue_types as _fact_issue_types, _issue_sources as _issue_sources, _classify_text as _classify_text, _issue_excerpt as _issue_excerpt, _weakness_score as _weakness_score, _latest_fact as _latest_fact, _open_task_count as _open_task_count, _top_strings as _top_strings, _first_text as _first_text, _suite_source as _suite_source, _case_source as _case_source, _review_source as _review_source, _health_source as _health_source, _report_source as _report_source, _case_in_scope as _case_in_scope, _scope_project_ids as _scope_project_ids, _suite_matches_release as _suite_matches_release, _release_acceptance_suite_id as _release_acceptance_suite_id, _release_ids_for_project as _release_ids_for_project, _scope_from_report as _scope_from_report, _report_id as _report_id, _optional_id as _optional_id, _safe_storage_key as _safe_storage_key, _optional_int as _optional_int, _bounded as _bounded, _append_event as _append_event, _matching_open_review_task as _matching_open_review_task

_v142_aa_readiness.bind_globals(globals())
_v142_aa_evidence.bind_globals(globals())
