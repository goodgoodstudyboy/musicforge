from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.acceptance_fix_sprints import AcceptanceFixSprint, AcceptanceFixSprintStore, AcceptanceFixSprintError, acceptance_fix_closeout_summary
from song_agent.music_acceptance import stable_hash
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text


ACCEPTANCE_KB_ROOT = Path(".musicforge") / "acceptance-kb"
ACCEPTANCE_KB_ENTRY_SCHEMA_VERSION = "acceptance_kb_entry.v1"
ACCEPTANCE_KB_REPORT_SCHEMA_VERSION = "acceptance_kb_report.v1"
ENTRY_STATUSES = {"active", "hidden", "stale"}
OUTCOME_STATUSES = {"effective", "mixed", "ineffective", "unknown"}
READINESS_ORDER = {"missing": 0, "empty": 0, "blocked": 1, "needs_work": 2, "watch": 3, "ready": 4}
SUCCESS_STATUSES = {"fixed", "closed"}


class AcceptanceKnowledgeBaseError(ValueError):
    pass


class AcceptanceKnowledgeBaseNotFoundError(AcceptanceKnowledgeBaseError):
    pass


@dataclass
class KnowledgeEntry:
    entry_id: str
    status: str
    source: dict[str, Any]
    target: dict[str, Any]
    problem: dict[str, Any]
    fix: dict[str, Any]
    outcome: dict[str, Any]
    evidence: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        status = self.status if self.status in ENTRY_STATUSES else "active"
        return sanitize_metadata(
            {
                "schema_version": ACCEPTANCE_KB_ENTRY_SCHEMA_VERSION,
                "entry_id": self.entry_id,
                "status": status,
                "source": self.source,
                "target": self.target,
                "problem": self.problem,
                "fix": self.fix,
                "outcome": self.outcome,
                "evidence": self.evidence,
                "warnings": self.warnings,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeEntry":
        now = now_iso()
        return cls(
            entry_id=_validate_id(str(data.get("entry_id") or "akb-000001"), "akb"),
            status=str(data.get("status") or "active") if str(data.get("status") or "active") in ENTRY_STATUSES else "active",
            source=_safe_dict(data.get("source")),
            target=_safe_dict(data.get("target")),
            problem=_safe_dict(data.get("problem")),
            fix=_safe_dict(data.get("fix")),
            outcome=_safe_dict(data.get("outcome")),
            evidence=_safe_dict(data.get("evidence")),
            warnings=[_bounded(item, 180) for item in data.get("warnings", []) if str(item).strip()] if isinstance(data.get("warnings"), list) else [],
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
        )


class AcceptanceKnowledgeBaseStore:
    def __init__(
        self,
        root: Path | str = ACCEPTANCE_KB_ROOT,
        *,
        fix_sprint_store: AcceptanceFixSprintStore | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.fix_sprint_store = fix_sprint_store or AcceptanceFixSprintStore()
        self.project_store = project_store or self.fix_sprint_store.project_store
        self.lock = threading.RLock()

    def entries_dir(self) -> Path:
        return self.root / "entries"

    def reports_dir(self) -> Path:
        return self.root / "reports"

    def entry_path(self, entry_id: str) -> Path:
        return self.entries_dir() / f"{_validate_id(entry_id, 'akb')}.json"

    def report_dir(self, report_id: str) -> Path:
        base = self.reports_dir().resolve()
        target = (base / _validate_id(report_id, "akbr")).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise AcceptanceKnowledgeBaseError("Refusing to operate outside acceptance KB reports.") from exc
        return target

    def latest_path(self) -> Path:
        return self.reports_dir() / "latest.json"

    def refresh(self, scope: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        with self.lock:
            self.entries_dir().mkdir(parents=True, exist_ok=True)
            existing_by_source = {str(entry.source.get("source_fingerprint") or ""): entry for entry in self.list_entries(include_hidden=True)}
            active_fingerprints: set[str] = set()
            generated: list[KnowledgeEntry] = []
            warnings: list[str] = []
            for sprint in self.fix_sprint_store.list_sprints(include_archived=True):
                try:
                    result = self._entry_from_sprint(sprint, existing_by_source, now=now)
                except AcceptanceKnowledgeBaseError as exc:
                    warnings.append(_bounded(str(exc), 180))
                    continue
                if result is None:
                    continue
                entry = result
                active_fingerprints.add(str(entry.source.get("source_fingerprint") or ""))
                self._write_entry(entry)
                generated.append(entry)
            for entry in self.list_entries(include_hidden=True):
                fingerprint = str(entry.source.get("source_fingerprint") or "")
                if fingerprint and fingerprint not in active_fingerprints and entry.status == "active":
                    stale = KnowledgeEntry.from_dict({**entry.to_dict(), "status": "stale", "updated_at": now, "warnings": sorted(set(entry.warnings + ["source_missing_or_changed"]))})
                    self._write_entry(stale)
            entries = self.search_entries(scope or {}, include_hidden=False)
            report = build_knowledge_report(entries, scope=scope or {"type": "global"}, report_id=self._next_report_id(), generated_at=now, warnings=warnings)
            report_dir = self.report_dir(str(report["report_id"]))
            report_dir.mkdir(parents=True, exist_ok=True)
            write_json(report_dir / "knowledge-report.json", report)
            write_json(report_dir / "source-summary.json", {"entry_count": len(entries), "source_hash": report.get("source_hash")})
            _append_event(report_dir / "events.jsonl", "acceptance_kb_refreshed", {"report_id": report["report_id"], "entry_count": len(entries)}, now)
            self.latest_path().parent.mkdir(parents=True, exist_ok=True)
            write_json(self.latest_path(), report)
            return report

    def latest_report(self) -> dict[str, Any]:
        path = self.latest_path()
        if not path.exists():
            return self.refresh()
        return self._with_stale(read_json(path))

    def get_report(self, report_id: str) -> dict[str, Any]:
        path = self.report_dir(report_id) / "knowledge-report.json"
        if not path.exists():
            raise AcceptanceKnowledgeBaseNotFoundError(report_id)
        return self._with_stale(read_json(path))

    def list_entries(self, *, include_hidden: bool = False) -> list[KnowledgeEntry]:
        entries: list[KnowledgeEntry] = []
        for path in sorted(self.entries_dir().glob("akb-*.json")):
            try:
                entry = KnowledgeEntry.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if not include_hidden and entry.status == "hidden":
                continue
            entries.append(entry)
        return entries

    def read_entry(self, entry_id: str) -> KnowledgeEntry:
        path = self.entry_path(entry_id)
        if not path.exists():
            raise AcceptanceKnowledgeBaseNotFoundError(entry_id)
        return KnowledgeEntry.from_dict(read_json(path))

    def hide_entry(self, entry_id: str, *, hidden: bool = True, now: str | None = None) -> KnowledgeEntry:
        with self.lock:
            entry = self.read_entry(entry_id)
            status = "hidden" if hidden else "active"
            if entry.status == "stale" and not hidden:
                status = "stale"
            updated = KnowledgeEntry.from_dict({**entry.to_dict(), "status": status, "updated_at": now or now_iso()})
            self._write_entry(updated)
            return updated

    def search_entries(self, query: dict[str, Any] | None = None, *, include_hidden: bool = False) -> list[KnowledgeEntry]:
        query = query or {}
        issue_type = _normalize_issue(query.get("issue_type") or query.get("issue_types"))
        style = _normalize_text(query.get("style"))
        song_id = str(query.get("song_id") or "").strip()
        project_id = str(query.get("project_id") or "").strip()
        release_id = str(query.get("release_id") or "").strip()
        outcome_status = str(query.get("outcome_status") or "").strip()
        rows = []
        for entry in self.list_entries(include_hidden=include_hidden):
            if entry.status == "hidden" and not include_hidden:
                continue
            if issue_type and issue_type not in {str(item) for item in entry.target.get("issue_types", []) if str(item).strip()}:
                continue
            if style and style not in _normalize_text(entry.target.get("style")):
                continue
            if song_id and str(entry.target.get("song_id") or "") != song_id:
                continue
            if project_id and str(entry.target.get("project_id") or "") != project_id:
                continue
            if release_id and str(entry.target.get("release_id") or "") != release_id:
                continue
            if outcome_status and str(entry.outcome.get("outcome_status") or "") != outcome_status:
                continue
            rows.append(entry)
        return sorted(rows, key=lambda entry: (-int(entry.outcome.get("effectiveness_score") or 0), str(entry.entry_id)))

    def recommend(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        matches = self.search_entries(payload)[:8]
        effective = [entry for entry in matches if entry.outcome.get("outcome_status") == "effective"]
        top = effective or matches
        issue_types = _issue_types_from_payload(payload)
        actions = [
            "Create Acceptance Fix Sprint from fresh analytics.",
            "Require manual review after fix.",
        ]
        if any(entry.fix.get("waived_count") for entry in top):
            actions.append("Avoid treating waived items as fixed; require explicit recheck evidence.")
        if any((entry.evidence.get("recheck_report_id") or "") for entry in top):
            actions.append("Prefer recheck suites with accepted manual reviews before closeout.")
        if issue_types:
            actions.append(f"Compare against historical {', '.join(issue_types[:3])} outcomes before choosing a fix path.")
        status = "available" if matches else "missing"
        summary = "No matching Acceptance KB entries yet."
        if matches:
            best = top[0]
            summary = f"Past {best.target.get('style') or 'matching'} fixes for {', '.join(best.target.get('issue_types') or ['acceptance'])} ended {best.outcome.get('outcome_status')} with score {best.outcome.get('effectiveness_score')}."
        return sanitize_metadata(
            {
                "status": status,
                "summary": _bounded(summary, 300),
                "matching_entry_count": len(matches),
                "effective_entry_count": len(effective),
                "top_entries": [knowledge_entry_summary(entry) for entry in top[:5]],
                "suggested_next_actions": actions[:6],
                "manual_required": True,
            }
        )

    def summary(self, *, project_id: str | None = None, release_id: str | None = None) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if project_id:
            query["project_id"] = project_id
        if release_id:
            query["release_id"] = release_id
        return knowledge_report_summary(build_knowledge_report(self.search_entries(query), scope=query or {"type": "global"}, report_id="summary", generated_at=now_iso()))

    def _entry_from_sprint(self, sprint: AcceptanceFixSprint, existing_by_source: dict[str, KnowledgeEntry], *, now: str) -> KnowledgeEntry | None:
        if sprint.status != "closed":
            return None
        try:
            if self.fix_sprint_store.sprint_is_stale(sprint):
                return None
        except AcceptanceFixSprintError:
            return None
        items = self.fix_sprint_store.read_items(sprint.fix_sprint_id)
        delta = self.fix_sprint_store.read_delta(sprint.fix_sprint_id, default={})
        closeout = self.fix_sprint_store.read_closeout(sprint.fix_sprint_id, default={})
        if not delta or not closeout:
            return None
        source_payload = {
            "fix_sprint": _sprint_source(sprint),
            "items": [_item_source(item.to_dict()) for item in items],
            "delta": _delta_source(delta),
            "closeout": _closeout_source(closeout),
            "tasks": self._review_task_sources(items),
        }
        source_fingerprint = stable_hash(source_payload)
        existing = existing_by_source.get(source_fingerprint)
        entry_id = existing.entry_id if existing else self._next_entry_id()
        created_at = existing.created_at if existing else now
        entry = build_entry_from_sources(entry_id=entry_id, sprint=sprint, items=[item.to_dict() for item in items], delta=delta, closeout=closeout, task_sources=source_payload["tasks"], source_fingerprint=source_fingerprint, created_at=created_at, now=now)
        return entry

    def _review_task_sources(self, items: list[Any]) -> list[dict[str, Any]]:
        sources = []
        for item in items:
            data = item.to_dict() if hasattr(item, "to_dict") else item if isinstance(item, dict) else {}
            task_id = str(data.get("review_task_id") or "").strip()
            project_id = str((data.get("target") if isinstance(data.get("target"), dict) else {}).get("project_id") or "").strip()
            if not task_id or not project_id:
                continue
            try:
                task_path = self.project_store.project_dir(project_id) / "review-tasks" / task_id / "task.json"
                task = read_json(task_path)
            except Exception:
                continue
            sources.append({"project_id": project_id, "task_id": task_id, "status": task.get("status"), "resolution_note": _bounded(task.get("resolution_note"), 180)})
        return sorted(sources, key=lambda item: str(item.get("task_id") or ""))

    def _write_entry(self, entry: KnowledgeEntry) -> None:
        self.entries_dir().mkdir(parents=True, exist_ok=True)
        write_json(self.entry_path(entry.entry_id), entry.to_dict())

    def _next_entry_id(self) -> str:
        index = 1
        while True:
            entry_id = f"akb-{index:06d}"
            if not self.entry_path(entry_id).exists():
                return entry_id
            index += 1

    def _next_report_id(self) -> str:
        index = 1
        base = self.reports_dir()
        while (base / f"akbr-{index:06d}").exists():
            index += 1
        return f"akbr-{index:06d}"

    def _with_stale(self, report: dict[str, Any]) -> dict[str, Any]:
        entries = self.search_entries(report.get("scope") if isinstance(report.get("scope"), dict) else {})
        current_hash = _entries_source_hash(entries)
        stored_hash = str(report.get("source_hash") or "")
        stale = bool(stored_hash and current_hash != stored_hash)
        clean = dict(report)
        clean["stale"] = stale
        clean["current_source_hash"] = current_hash
        clean["stale_reason"] = "source_changed" if stale else ""
        return sanitize_metadata(clean)


def build_entry_from_sources(
    *,
    entry_id: str,
    sprint: AcceptanceFixSprint,
    items: list[dict[str, Any]],
    delta: dict[str, Any],
    closeout: dict[str, Any],
    task_sources: list[dict[str, Any]],
    source_fingerprint: str,
    created_at: str,
    now: str,
) -> KnowledgeEntry:
    delta_summary = delta.get("summary") if isinstance(delta.get("summary"), dict) else {}
    closeout_summary = acceptance_fix_closeout_summary(closeout)
    issue_types = sorted({issue for item in items for issue in _issue_types_from_item(item)})
    first_target = next((item.get("target") for item in items if isinstance(item.get("target"), dict)), {})
    waived_count = sum(1 for item in items if item.get("status") == "waived")
    open_count = sum(1 for item in items if item.get("status") not in {"waived", "fixed", "closed"})
    task_statuses = [str(item.get("status") or "") for item in task_sources]
    provider_used = any("provider" in json.dumps(item, ensure_ascii=False).lower() for item in items)
    score = effectiveness_score(delta_summary, task_statuses=task_statuses, open_item_count=open_count, waived_count=waived_count, forced=bool(closeout.get("forced", False)))
    outcome_status = outcome_status_for_score(score, delta_summary)
    warnings = []
    if closeout.get("forced"):
        warnings.append("force_closed")
    if waived_count:
        warnings.append("waived_items_present")
    if open_count:
        warnings.append("open_items_present")
    return KnowledgeEntry(
        entry_id=entry_id,
        status="active",
        source={
            "source_type": "acceptance_fix_sprint",
            "fix_sprint_id": sprint.fix_sprint_id,
            "source_hash": sprint.source.get("source_hash"),
            "source_fingerprint": source_fingerprint,
            "delta_hash": stable_hash(_delta_source(delta)),
            "closeout_hash": stable_hash(_closeout_source(closeout)),
        },
        target={
            "project_id": first_target.get("project_id"),
            "release_id": sprint.scope.get("release_id") if isinstance(sprint.scope, dict) else None,
            "song_id": first_target.get("song_id"),
            "style": _bounded(first_target.get("style") or _style_from_items(items), 80),
            "issue_types": issue_types or ["other"],
        },
        problem={
            "readiness_before": delta_summary.get("before_readiness"),
            "rating_before": None,
            "issue_count_before": None,
            "top_issues": issue_types[:10],
        },
        fix={
            "fix_sprint_id": sprint.fix_sprint_id,
            "review_task_ids": [item.get("task_id") for item in task_sources if item.get("task_id")],
            "resolution_types": sorted(set(task_statuses)),
            "waived_count": waived_count,
            "provider_used": provider_used,
            "manual_required": True,
        },
        outcome={
            "readiness_after": delta_summary.get("after_readiness"),
            "rating_delta": delta_summary.get("rating_delta"),
            "issue_count_delta": delta_summary.get("issue_count_delta"),
            "effectiveness_score": score,
            "outcome_status": outcome_status,
            "delta_status": delta_summary.get("status"),
            "closeout_status": closeout_summary.get("status"),
        },
        evidence={
            "source_report_id": (delta.get("source") if isinstance(delta.get("source"), dict) else {}).get("analytics_report_id") or sprint.source.get("report_id"),
            "recheck_report_id": (delta.get("recheck") if isinstance(delta.get("recheck"), dict) else {}).get("analytics_report_id"),
            "suite_ids": [value for value in [sprint.recheck.get("suite_id") if isinstance(sprint.recheck, dict) else None] if value],
            "case_ids": [],
        },
        warnings=warnings,
        created_at=created_at,
        updated_at=now,
    )


def effectiveness_score(delta_summary: dict[str, Any], *, task_statuses: list[str], open_item_count: int, waived_count: int, forced: bool) -> int:
    score = 0
    before = str(delta_summary.get("before_readiness") or "missing")
    after = str(delta_summary.get("after_readiness") or "missing")
    if READINESS_ORDER.get(after, 0) > READINESS_ORDER.get(before, 0):
        score += 25
    if after in {"ready", "watch"}:
        score += 25
    rating_delta = _float_or_none(delta_summary.get("rating_delta"))
    if rating_delta is not None:
        if rating_delta >= 2:
            score += 20
        elif rating_delta >= 1:
            score += 10
    issue_delta = _int_or_none(delta_summary.get("issue_count_delta"))
    if issue_delta is not None:
        if issue_delta <= -2:
            score += 15
        elif issue_delta == -1:
            score += 8
    if task_statuses and all(status in {"resolved", "archived"} for status in task_statuses):
        score += 10
    if open_item_count:
        score -= 20
    if forced:
        score -= 12
    if waived_count:
        score -= 10
    return max(0, min(100, score))


def outcome_status_for_score(score: int, delta_summary: dict[str, Any]) -> str:
    if not delta_summary:
        return "unknown"
    if score >= 70:
        return "effective"
    if score >= 40:
        return "mixed"
    return "ineffective"


def build_knowledge_report(entries: list[KnowledgeEntry], *, scope: dict[str, Any], report_id: str, generated_at: str, warnings: list[str] | None = None) -> dict[str, Any]:
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


def knowledge_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
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


def write_acceptance_kb_summary(path: Path, store: AcceptanceKnowledgeBaseStore, *, release_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    summary = store.summary(release_id=release_id, project_id=project_id)
    write_json(path, summary)
    return summary


def knowledge_entry_summary(entry: KnowledgeEntry | dict[str, Any]) -> dict[str, Any]:
    data = entry.to_dict() if isinstance(entry, KnowledgeEntry) else entry if isinstance(entry, dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    outcome = data.get("outcome") if isinstance(data.get("outcome"), dict) else {}
    fix = data.get("fix") if isinstance(data.get("fix"), dict) else {}
    return sanitize_metadata(
        {
            "entry_id": data.get("entry_id"),
            "status": data.get("status"),
            "fix_sprint_id": (data.get("source") if isinstance(data.get("source"), dict) else {}).get("fix_sprint_id"),
            "project_id": target.get("project_id"),
            "release_id": target.get("release_id"),
            "song_id": target.get("song_id"),
            "style": target.get("style"),
            "issue_types": target.get("issue_types") if isinstance(target.get("issue_types"), list) else [],
            "outcome_status": outcome.get("outcome_status"),
            "effectiveness_score": outcome.get("effectiveness_score"),
            "waived_count": fix.get("waived_count", 0),
            "warnings": data.get("warnings") if isinstance(data.get("warnings"), list) else [],
        }
    )


def _issue_patterns(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
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


def _style_patterns(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
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


def _song_patterns(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
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


def _fix_patterns(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
    return [
        {
            "pattern": "manual_review_task_resolution",
            "entry_count": len(entries),
            "resolved_task_count": sum(len([status for status in entry.fix.get("resolution_types", []) if status == "resolved"]) for entry in entries),
            "waived_count": sum(int(entry.fix.get("waived_count") or 0) for entry in entries),
        }
    ] if entries else []


def _knowledge_recommendations(issue_patterns: list[dict[str, Any]], style_patterns: list[dict[str, Any]], song_patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _sprint_source(sprint: AcceptanceFixSprint) -> dict[str, Any]:
    return {"fix_sprint_id": sprint.fix_sprint_id, "status": sprint.status, "scope": sprint.scope, "source": sprint.source, "recheck": sprint.recheck, "delta_summary": sprint.delta_summary, "closeout_summary": sprint.closeout_summary}


def _item_source(item: dict[str, Any]) -> dict[str, Any]:
    return {"item_id": item.get("item_id"), "status": item.get("status"), "source": item.get("source"), "target": item.get("target"), "review_task_id": item.get("review_task_id"), "resolution": item.get("resolution")}


def _delta_source(delta: dict[str, Any]) -> dict[str, Any]:
    return {"source": delta.get("source"), "recheck": delta.get("recheck"), "summary": delta.get("summary"), "issue_deltas": delta.get("issue_deltas"), "song_deltas": delta.get("song_deltas")}


def _closeout_source(closeout: dict[str, Any]) -> dict[str, Any]:
    return {"status": closeout.get("status"), "forced": closeout.get("forced"), "checks": closeout.get("checks"), "summary": closeout.get("summary")}


def _issue_types_from_item(item: dict[str, Any]) -> list[str]:
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    values = []
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


def _issue_types_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("issue_types")
    if isinstance(raw, list):
        return [str(item).strip().lower() for item in raw if str(item).strip()]
    issue = str(payload.get("issue_type") or "").strip().lower()
    return [issue] if issue else []


def _normalize_issue(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0] if value else "").strip().lower()
    return str(value or "").strip().lower()


def _style_from_items(items: list[dict[str, Any]]) -> str:
    for item in items:
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        if target.get("style"):
            return str(target.get("style"))
    return "unknown"


def _safe_scope(scope: dict[str, Any]) -> dict[str, Any]:
    return {"type": str(scope.get("type") or "global"), "project_id": scope.get("project_id"), "release_id": scope.get("release_id"), "song_id": scope.get("song_id"), "style": scope.get("style"), "issue_type": scope.get("issue_type")}


def _risk_for_items(items: list[KnowledgeEntry]) -> str:
    average = sum(int(entry.outcome.get("effectiveness_score") or 0) for entry in items) / max(1, len(items))
    if average < 40:
        return "high"
    if average < 70 or len(items) > 3:
        return "medium"
    return "low"


def _top_values(values: list[Any], *, limit: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return [key for key, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _bounded(value: Any, limit: int = 300) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())
    return text[:limit]


def _normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9_ -]+", "", str(value or "").lower()).strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {})


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_id(value: str, prefix: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(rf"{re.escape(prefix)}-\d{{6}}", value):
        raise AcceptanceKnowledgeBaseError(f"Invalid {prefix} id.")
    return value


def _append_event(path: Path, event_type: str, payload: dict[str, Any], now: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"event_type": event_type, "created_at": now or now_iso(), "payload": payload})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
