# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.acceptance_analytics import AcceptanceAnalyticsStore as AcceptanceAnalyticsStore, AnalyticsScope as AnalyticsScope, acceptance_analytics_summary as acceptance_analytics_summary
from song_agent.domains.quality.acceptance_fix_plan_runtime import current_fix_plan_state as current_fix_plan_state
from song_agent.domains.quality.music_acceptance import AcceptanceStore as AcceptanceStore, stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import REVIEW_TASK_SCHEMA_VERSION as REVIEW_TASK_SCHEMA_VERSION, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore


ACCEPTANCE_FIX_SPRINT_ROOT = Path(".musicforge") / "acceptance-fix-sprints"
ACCEPTANCE_FIX_SPRINT_SCHEMA_VERSION = "acceptance_fix_sprint.v1"
ACCEPTANCE_FIX_ITEMS_SCHEMA_VERSION = "acceptance_fix_items.v1"
ACCEPTANCE_FIX_DELTA_SCHEMA_VERSION = "acceptance_fix_delta.v1"
ACCEPTANCE_FIX_CLOSEOUT_SCHEMA_VERSION = "acceptance_fix_closeout.v1"
SPRINT_STATUSES = {"draft", "planned", "in_progress", "recheck_ready", "rechecking", "delta_ready", "ready_to_close", "closed", "archived", "stale"}
ITEM_STATUSES = {"open", "linked", "in_progress", "needs_recheck", "fixed", "waived", "blocked", "stale", "closed"}
OPEN_REVIEW_TASK_STATUSES = {"open", "candidate_ready", "applied", "needs_more_work"}
TERMINAL_REVIEW_TASK_STATUSES = {"resolved", "archived"}


from song_agent.domains.quality import v142_afs_readiness as _v142_afs_readiness
from song_agent.domains.quality.v142_afs_readiness import (
    AcceptanceFixSprintError,
    AcceptanceFixSprintNotFoundError,
    AcceptanceFixSprintStateError,
    build_delta_report,
    build_closeout_report,
    fix_sprint_summary,
    acceptance_fix_closeout_summary,
    latest_fix_sprint_summary,
    write_acceptance_fix_sprints_summary,
    _selected_recommendations,
    _item_from_recommendation,
    _counts,
    _matching_open_review_task,
    _issue_types_from_blob,
    _request_for_recheck,
    _source_report_id,
    _song_deltas,
    _issue_deltas,
    _review_task_close_rate,
    _accepted_count,
    _review_count,
    _close_check,
    _safe_dict,
    _bounded,
    _optional_str,
    _int,
    _validate_id,
    _lock_for_root,
    _append_event,
)







@dataclass
class AcceptanceFixItem:
    item_id: str
    status: str
    priority: int
    severity: str
    source: ImplementationDocument
    target: ImplementationDocument
    title: str
    summary: str
    evidence: ImplementationDocument = field(default_factory=dict)
    review_task_id: str | None = None
    review_sprint_id: str | None = None
    resolution: ImplementationDocument = field(default_factory=lambda: {"status": "pending", "notes": ""})
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "item_id": self.item_id,
                "status": self.status,
                "priority": self.priority,
                "severity": self.severity,
                "source": self.source,
                "target": self.target,
                "title": self.title,
                "summary": self.summary,
                "evidence": self.evidence,
                "review_task_id": self.review_task_id,
                "review_sprint_id": self.review_sprint_id,
                "resolution": self.resolution,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "AcceptanceFixItem":
        now = now_iso()
        status = str(data.get("status") or "open")
        if status not in ITEM_STATUSES:
            status = "open"
        return cls(
            item_id=_validate_id(str(data.get("item_id") or "afi-000001"), "afi"),
            status=status,
            priority=max(1, min(100, _int(data.get("priority"), 50))),
            severity=_bounded(data.get("severity"), 40) or "medium",
            source=_safe_dict(data.get("source")),
            target=_safe_dict(data.get("target")),
            title=_bounded(data.get("title"), 180) or "Acceptance fix item",
            summary=_bounded(data.get("summary"), 800),
            evidence=_safe_dict(data.get("evidence")),
            review_task_id=_optional_str(data.get("review_task_id"), 80),
            review_sprint_id=_optional_str(data.get("review_sprint_id"), 80),
            resolution=_safe_dict(data.get("resolution")) or {"status": "pending", "notes": ""},
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
        )


@dataclass
class AcceptanceFixSprint:
    fix_sprint_id: str
    name: str
    status: str
    scope: ImplementationDocument
    source: ImplementationDocument
    settings: ImplementationDocument
    counts: ImplementationDocument
    recheck: ImplementationDocument
    delta_summary: ImplementationDocument = field(default_factory=dict)
    closeout_summary: ImplementationDocument = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "developer"

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": ACCEPTANCE_FIX_SPRINT_SCHEMA_VERSION,
                "fix_sprint_id": self.fix_sprint_id,
                "name": self.name,
                "status": self.status,
                "scope": self.scope,
                "source": self.source,
                "settings": self.settings,
                "counts": self.counts,
                "recheck": self.recheck,
                "delta_summary": self.delta_summary,
                "closeout_summary": self.closeout_summary,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "AcceptanceFixSprint":
        now = now_iso()
        status = str(data.get("status") or "draft")
        if status not in SPRINT_STATUSES:
            status = "draft"
        return cls(
            fix_sprint_id=_validate_id(str(data.get("fix_sprint_id") or "afs-000001"), "afs"),
            name=_bounded(data.get("name"), 160) or "Acceptance Fix Sprint",
            status=status,
            scope=_safe_dict(data.get("scope")),
            source=_safe_dict(data.get("source")),
            settings=_safe_dict(data.get("settings")),
            counts=_safe_dict(data.get("counts")),
            recheck=_safe_dict(data.get("recheck")) or {"suite_id": None, "analytics_report_id": None, "status": "not_started"},
            delta_summary=_safe_dict(data.get("delta_summary")),
            closeout_summary=_safe_dict(data.get("closeout_summary")),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now),
            created_by=_bounded(data.get("created_by"), 120) or "developer",
        )


class AcceptanceFixSprintStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        acceptance_store: AcceptanceStore | None = None,
        analytics_store: AcceptanceAnalyticsStore | None = None,
        project_store: ProjectStore | None = None,
    ):
        self.root = Path(root or ACCEPTANCE_FIX_SPRINT_ROOT)
        self.acceptance_store = acceptance_store or AcceptanceStore()
        self.project_store = project_store or self.acceptance_store.project_store
        self.analytics_store = analytics_store or AcceptanceAnalyticsStore(acceptance_store=self.acceptance_store, project_store=self.project_store)
        self.lock = _lock_for_root(self.root.resolve())

    def sprint_dir(self, fix_sprint_id: str) -> Path:
        base = self.root.resolve()
        target = (base / _validate_id(fix_sprint_id, "afs")).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise AcceptanceFixSprintError("Refusing to operate outside acceptance fix sprint store.") from exc
        return target

    def list_sprints(self, *, include_archived: bool = False, status: str | None = None) -> list[AcceptanceFixSprint]:
        rows: list[AcceptanceFixSprint] = []
        if not self.root.exists():
            return rows
        for path in self.root.glob("afs-*/fix-sprint.json"):
            try:
                sprint = AcceptanceFixSprint.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if sprint.status == "archived" and not include_archived:
                continue
            if status and sprint.status != status:
                continue
            rows.append(self._with_fresh_counts(sprint))
        return sorted(rows, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_sprint(self, fix_sprint_id: str) -> AcceptanceFixSprint:
        path = self.sprint_dir(fix_sprint_id) / "fix-sprint.json"
        if not path.exists():
            raise AcceptanceFixSprintNotFoundError(fix_sprint_id)
        return self._with_fresh_counts(AcceptanceFixSprint.from_dict(read_json(path)))

    def read_items(self, fix_sprint_id: str) -> list[AcceptanceFixItem]:
        path = self.sprint_dir(fix_sprint_id) / "fix-items.json"
        if not path.exists():
            return []
        data = read_json(path)
        rows = _as_list(data.get("items"))
        return [AcceptanceFixItem.from_dict(item) for item in rows if isinstance(item, dict)]

    def create_from_analytics(self, payload: DomainDocument | None = None, *, now: str | None = None) -> AcceptanceFixSprint:
        payload = payload or {}
        now = now or now_iso()
        report_id = str(payload.get("analytics_report_id") or "").strip()
        if not report_id:
            raise AcceptanceFixSprintStateError("analytics_report_id is required.")
        report = self.analytics_store.get_report(report_id)
        if report.get("stale") is True:
            raise AcceptanceFixSprintStateError("Fix Sprint source analytics is stale. Refresh analytics and create a new Fix Sprint.")
        recommendations = _selected_recommendations(report, payload.get("recommendation_ids"), max_items=_int(payload.get("max_items"), 20))
        if not recommendations:
            raise AcceptanceFixSprintStateError("Analytics report has no selected recommendations for a Fix Sprint.")
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            sprint_id, sprint_dir = self._reserve_sprint_dir()
            source_hash = str(report.get("source_hash") or "")
            items = [_item_from_recommendation(index, recommendation, report_id=report_id, source_hash=source_hash, now=now) for index, recommendation in enumerate(recommendations, start=1)]
            sprint = AcceptanceFixSprint(
                fix_sprint_id=sprint_id,
                name=_bounded(payload.get("name"), 160) or "Acceptance Fix Sprint",
                status="planned",
                scope=_safe_dict(payload.get("scope")) or _safe_dict(report.get("scope")),
                source={
                    "source_type": "acceptance_analytics",
                    "report_id": report_id,
                    "source_hash": source_hash,
                    "readiness_status": (_as_document(report.get("summary"))).get("readiness_status"),
                    "recommendation_ids": [item.source.get("recommendation_id") for item in items],
                    "recommendation_payload_hashes": {str(item.source.get("recommendation_id")): item.source.get("recommendation_hash") for item in items},
                },
                settings={
                    "profile_id": _bounded(payload.get("profile_id"), 80) or "developer_manual",
                    "require_manual_recheck": bool(payload.get("require_manual_recheck", True)),
                    "allow_synthetic_recheck": bool(payload.get("allow_synthetic_recheck", False)),
                    "max_items": _int(payload.get("max_items"), 20),
                },
                counts={},
                recheck={"suite_id": None, "analytics_report_id": None, "status": "not_started"},
                created_at=now,
                updated_at=now,
                created_by=_bounded(payload.get("created_by"), 120) or "developer",
            )
            sprint.counts = _counts(items, self.project_store)
            write_json(sprint_dir / "fix-sprint.json", sprint.to_dict())
            self._write_items(sprint.fix_sprint_id, items)
            _append_event(sprint_dir / "events.jsonl", "acceptance_fix_sprint_created", {"report_id": report_id, "item_count": len(items)}, now)
            return sprint

    def archive_sprint(self, fix_sprint_id: str, *, now: str | None = None) -> AcceptanceFixSprint:
        sprint = self.read_sprint(fix_sprint_id)
        updated = AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": "archived", "updated_at": now or now_iso()})
        self._write_sprint(updated)
        _append_event(self.sprint_dir(fix_sprint_id) / "events.jsonl", "acceptance_fix_sprint_archived", {}, now or now_iso())
        return updated

    def refresh_status(self, fix_sprint_id: str, *, now: str | None = None) -> AcceptanceFixSprint:
        sprint = self.read_sprint(fix_sprint_id)
        items = self.sync_items(fix_sprint_id)
        status = sprint.status
        if status not in {"closed", "archived"}:
            if self.sprint_is_stale(sprint):
                status = "stale"
            elif any(item.status in {"open", "linked", "in_progress", "needs_recheck"} for item in items):
                status = "in_progress" if any(item.review_task_id for item in items) else "planned"
            elif sprint.recheck.get("analytics_report_id"):
                status = "ready_to_close"
            elif sprint.recheck.get("suite_id"):
                status = "recheck_ready"
            else:
                status = "planned"
        updated = AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": status, "counts": _counts(items, self.project_store), "updated_at": now or now_iso()})
        self._write_sprint(updated)
        return updated

    def sync_items(self, fix_sprint_id: str, *, now: str | None = None) -> list[AcceptanceFixItem]:
        items = self.read_items(fix_sprint_id)
        changed = False
        synced = []
        for item in items:
            updated = self._sync_item_from_task(item, now=now)
            changed = changed or updated.to_dict() != item.to_dict()
            synced.append(updated)
        if changed:
            self._write_items(fix_sprint_id, synced)
        return synced

    def create_review_tasks(self, fix_sprint_id: str, item_id: str | None = None, *, now: str | None = None) -> DomainDocument:
        sprint = self._require_actionable(fix_sprint_id)
        items = self.read_items(sprint.fix_sprint_id)
        selected = [item for item in items if item.item_id == item_id] if item_id else items
        if item_id and not selected:
            raise AcceptanceFixSprintNotFoundError(item_id)
        results = []
        changed: dict[str, AcceptanceFixItem] = {}
        for item in selected:
            if item.status in {"waived", "fixed", "closed"}:
                results.append({"item_id": item.item_id, "status": "skipped", "reason": f"item is {item.status}"})
                continue
            result, updated = self._create_or_bind_review_task(sprint, item, now=now or now_iso())
            results.append(result)
            changed[item.item_id] = updated
        merged = [changed.get(item.item_id, item) for item in items]
        self._write_items(sprint.fix_sprint_id, merged)
        updated_sprint = self.refresh_status(sprint.fix_sprint_id, now=now)
        return {"fix_sprint": updated_sprint.to_dict(), "items": [item.to_dict() for item in merged], "results": results, "summary": fix_sprint_summary(updated_sprint, merged)}

    def add_item(self, fix_sprint_id: str, payload: DomainDocument, *, now: str | None = None) -> AcceptanceFixItem:
        sprint = self._require_actionable(fix_sprint_id)
        title = _bounded(payload.get("title"), 180)
        reason = _bounded(payload.get("reason") or payload.get("summary"), 800)
        target = _safe_dict(payload.get("target"))
        issue_types = [str(item) for item in target.get("issue_types", []) if str(item).strip()] if isinstance(target.get("issue_types"), list) else []
        if not title or not reason or not (target.get("song_id") or issue_types):
            raise AcceptanceFixSprintStateError("Manual fix item requires title, reason, and target.song_id or issue_types.")
        now = now or now_iso()
        items = self.read_items(fix_sprint_id)
        item = AcceptanceFixItem(
            item_id=f"afi-{len(items) + 1:06d}",
            status="open",
            priority=max(1, min(100, _int(payload.get("priority"), 50))),
            severity=_bounded(payload.get("severity"), 40) or "medium",
            source={"source_type": "manual", "source_hash": sprint.source.get("source_hash")},
            target=target,
            title=title,
            summary=reason,
            evidence=_safe_dict(payload.get("evidence")),
            created_at=now,
            updated_at=now,
        )
        items.append(item)
        self._write_items(fix_sprint_id, items)
        self.refresh_status(fix_sprint_id, now=now)
        return item

    def waive_item(self, fix_sprint_id: str, item_id: str, reason: str, *, now: str | None = None) -> AcceptanceFixItem:
        self._require_actionable(fix_sprint_id)
        note = _bounded(reason, 500)
        if not note:
            raise AcceptanceFixSprintStateError("waiver reason is required.")
        return self._update_item(fix_sprint_id, item_id, {"status": "waived", "resolution": {"status": "waived", "notes": note}}, now=now)

    def reopen_item(self, fix_sprint_id: str, item_id: str, *, now: str | None = None) -> AcceptanceFixItem:
        self._require_actionable(fix_sprint_id)
        return self._update_item(fix_sprint_id, item_id, {"status": "open", "resolution": {"status": "pending", "notes": ""}}, now=now)

    def create_recheck_suite(self, fix_sprint_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        sprint = self._require_actionable(fix_sprint_id)
        items = self.read_items(fix_sprint_id)
        song_ids = [str(item) for item in payload.get("song_ids", []) if str(item).strip()] if isinstance(payload.get("song_ids"), list) else []
        if not song_ids:
            song_ids = sorted({str(item.target.get("song_id") or "") for item in items if str(item.target.get("song_id") or "").strip()})
        if not song_ids:
            raise AcceptanceFixSprintStateError("Recheck suite requires at least one song_id.")
        suite = self.acceptance_store.create_suite(
            {
                "name": _bounded(payload.get("name"), 120) or f"Recheck {sprint.fix_sprint_id}",
                "profile_id": _bounded(payload.get("profile_id"), 80) or str(sprint.settings.get("profile_id") or "developer_manual"),
                "require_manual_review": bool(payload.get("require_manual_review", sprint.settings.get("require_manual_recheck", True))),
                "allow_synthetic_review": bool(payload.get("allow_synthetic_recheck", sprint.settings.get("allow_synthetic_recheck", False))),
                "require_audio_if_renderer_configured": bool(payload.get("require_audio_if_renderer_configured", False)),
                "mode": "acceptance_fix_recheck",
            }
        )
        warnings = []
        source_report = self.analytics_store.get_report(_source_report_id(sprint))
        for song_id in song_ids:
            source_item = next((item for item in items if str(item.target.get("song_id") or "") == song_id), None)
            target = source_item.target if source_item else {}
            case_payload: ImplementationDocument = {
                "name": f"Recheck {song_id}",
                "song_id": song_id,
                "request": _request_for_recheck(source_report, song_id),
                "expectations": {"fix_sprint_id": sprint.fix_sprint_id},
            }
            if target.get("project_id"):
                case_payload.update({"source_type": "project_version", "project_id": target.get("project_id"), "version_id": target.get("version_id") or "v001"})
            else:
                case_payload["source_type"] = "generated_request"
                warnings.append(f"{song_id}: missing project/version; created generated_request case")
            self.acceptance_store.add_case(suite.suite_id, case_payload)
        updated = AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": "recheck_ready", "recheck": {"suite_id": suite.suite_id, "analytics_report_id": None, "status": "created", "warnings": warnings}, "updated_at": now or now_iso()})
        self._write_sprint(updated)
        return {"fix_sprint": updated.to_dict(), "suite": suite.to_dict(), "warnings": warnings}

    def link_recheck_suite(self, fix_sprint_id: str, suite_id: str, *, now: str | None = None) -> AcceptanceFixSprint:
        sprint = self._require_actionable(fix_sprint_id)
        self.acceptance_store.get_suite(suite_id)
        updated = AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": "recheck_ready", "recheck": {**sprint.recheck, "suite_id": suite_id, "status": "linked"}, "updated_at": now or now_iso()})
        self._write_sprint(updated)
        return updated

    def refresh_delta(self, fix_sprint_id: str, *, now: str | None = None) -> DomainDocument:
        sprint = self._require_actionable(fix_sprint_id)
        suite_id = str(sprint.recheck.get("suite_id") or "")
        if not suite_id:
            raise AcceptanceFixSprintStateError("Recheck suite is required before delta refresh.")
        try:
            self.acceptance_store.read_report(suite_id)
        except Exception:
            self.acceptance_store.build_report(suite_id)
        recheck_report = self.analytics_store.refresh(AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id), now=now or now_iso())
        source_report = self.analytics_store.get_report(_source_report_id(sprint))
        items = self.sync_items(fix_sprint_id, now=now)
        delta = build_delta_report(sprint, items, source_report, recheck_report, now=now or now_iso(), project_store=self.project_store)
        write_json(self.sprint_dir(fix_sprint_id) / "delta-report.json", delta)
        updated = AcceptanceFixSprint.from_dict(
            {
                **sprint.to_dict(),
                "status": "delta_ready",
                "recheck": {**sprint.recheck, "analytics_report_id": recheck_report.get("report_id"), "status": "analytics_ready"},
                "delta_summary": delta.get("summary", {}),
                "updated_at": now or now_iso(),
            }
        )
        self._write_sprint(updated)
        return delta

    def read_delta(self, fix_sprint_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.sprint_dir(fix_sprint_id) / "delta-report.json"
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceFixSprintNotFoundError("delta-report.json")
        return sanitize_metadata(read_json(path))

    def close(self, fix_sprint_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        sprint = self.read_sprint(fix_sprint_id)
        force = bool(payload.get("force", False))
        if self.sprint_is_stale(sprint):
            raise AcceptanceFixSprintStateError("Fix Sprint source analytics is stale. Refresh analytics and create a new Fix Sprint.")
        items = self.sync_items(fix_sprint_id, now=now)
        delta = self.read_delta(fix_sprint_id, default={})
        closeout = build_closeout_report(sprint, items, delta, force=force, override_reason=str(payload.get("override_reason") or ""), now=now or now_iso())
        write_json(self.sprint_dir(fix_sprint_id) / "closeout-report.json", closeout)
        if closeout.get("status") == "failed" and not force:
            raise AcceptanceFixSprintStateError(str(closeout.get("message") or "Acceptance Fix Sprint closeout failed."))
        status = "closed" if closeout.get("status") in {"passed", "warning", "force_closed"} else sprint.status
        updated = AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": status, "closeout_summary": acceptance_fix_closeout_summary(closeout), "updated_at": now or now_iso()})
        self._write_sprint(updated)
        return closeout

    def read_closeout(self, fix_sprint_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.sprint_dir(fix_sprint_id) / "closeout-report.json"
        if not path.exists():
            if default is not None:
                return default
            raise AcceptanceFixSprintNotFoundError("closeout-report.json")
        return sanitize_metadata(read_json(path))

    def sprint_is_stale(self, sprint: AcceptanceFixSprint) -> bool:
        if sprint.source.get("source_type") == "acceptance_fix_plan":
            try:
                state = current_fix_plan_state(
                    str(sprint.source.get("fix_plan_id") or ""),
                    analytics_store=self.analytics_store,
                )
                plan = _as_document(state.get("plan"))
                if state.get("stale"):
                    return True
                source = _as_document(plan.get("source"))
                if str(source.get("source_hash") or "") != str(sprint.source.get("fix_plan_source_hash") or ""):
                    return True
                expected = _as_document(sprint.source.get("planned_item_hashes"))
                current = {str(item.get("planned_item_id") or ""): item for item in plan.get("planned_items", []) if isinstance(item, dict)}
                for planned_item_id, expected_hash in expected.items():
                    if planned_item_id not in current:
                        return True
                    if stable_hash(current[planned_item_id]) != expected_hash:
                        return True
                return False
            except Exception:
                return True
        report = self.analytics_store.get_report(_source_report_id(sprint))
        if report.get("stale") is True:
            return True
        if str(report.get("source_hash") or "") != str(sprint.source.get("source_hash") or ""):
            return True
        current = {str(item.get("recommendation_id") or ""): item for item in report.get("recommendations", []) if isinstance(item, dict)}
        expected = _as_document(sprint.source.get("recommendation_payload_hashes"))
        for recommendation_id, expected_hash in expected.items():
            if recommendation_id not in current:
                return True
            if stable_hash(current[recommendation_id]) != expected_hash:
                return True
        return False

    def _require_actionable(self, fix_sprint_id: str) -> AcceptanceFixSprint:
        sprint = self.read_sprint(fix_sprint_id)
        if sprint.status in {"closed", "archived"}:
            raise AcceptanceFixSprintStateError(f"Cannot modify a {sprint.status} Acceptance Fix Sprint.")
        if self.sprint_is_stale(sprint):
            stale = AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": "stale", "updated_at": now_iso()})
            self._write_sprint(stale)
            raise AcceptanceFixSprintStateError("Fix Sprint source analytics is stale. Refresh analytics and create a new Fix Sprint.")
        return sprint

    def _create_or_bind_review_task(self, sprint: AcceptanceFixSprint, item: AcceptanceFixItem, *, now: str) -> tuple[ImplementationDocument, AcceptanceFixItem]:
        project_id = str(item.target.get("project_id") or "").strip()
        if not project_id:
            raise AcceptanceFixSprintStateError(f"Fix item {item.item_id} cannot create ReviewTask without project_id.")
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.ensure_project_dir_is_safe(project_dir)
        document = self.project_store.get_project(project_id)
        issue_types = [str(value) for value in item.target.get("issue_types", []) if str(value).strip()] if isinstance(item.target.get("issue_types"), list) else []
        existing = _matching_open_review_task(project_dir, str(item.target.get("song_id") or ""), issue_types)
        if existing:
            updated = AcceptanceFixItem.from_dict({**item.to_dict(), "status": "linked", "review_task_id": existing.task_id, "updated_at": now})
            return {"item_id": item.item_id, "status": "existing", "project_id": project_id, "task_id": existing.task_id}, updated
        store = ReviewTaskStore(project_dir)
        with store.lock:
            task_id, task_dir = store._reserve_task_dir()
            task = ReviewTask.from_dict(
                {
                    "schema_version": REVIEW_TASK_SCHEMA_VERSION,
                    "task_id": task_id,
                    "project_id": project_id,
                    "parent_version_id": str(item.target.get("version_id") or document.state.final_version_id or document.state.selected_version_id or document.state.latest_version_id or ""),
                    "preview_id": f"acceptance-fix-{sprint.fix_sprint_id}",
                    "audition_id": f"acceptance-fix-{item.item_id}",
                    "status": "open",
                    "priority": item.priority,
                    "title": item.title[:160],
                    "summary": item.summary[:800],
                    "source": {"source_type": "acceptance_fix_sprint", "fix_sprint_id": sprint.fix_sprint_id, "item_id": item.item_id, "analytics_report_id": _source_report_id(sprint), "recommendation_id": item.source.get("recommendation_id"), "source_hash": sprint.source.get("source_hash")},
                    "review_snapshot": {"fix_item": item.to_dict()},
                    "target": {"scope": "project", "project_id": project_id, "song_id": item.target.get("song_id"), "issue_types": issue_types},
                    "hashes": {"analytics_source_hash": str(sprint.source.get("source_hash") or "")},
                    "counts": {"candidate_count": 0, "ready_candidate_count": 0, "failed_candidate_count": 0},
                    "created_at": now,
                    "updated_at": now,
                }
            )
            write_json(task_dir / "task.json", task.to_dict())
            _append_event(task_dir / "events.jsonl", "review_task_created_from_acceptance_fix_sprint", {"fix_sprint_id": sprint.fix_sprint_id, "item_id": item.item_id}, now)
        updated = AcceptanceFixItem.from_dict({**item.to_dict(), "status": "linked", "review_task_id": task.task_id, "updated_at": now})
        return {"item_id": item.item_id, "status": "created", "project_id": project_id, "task_id": task.task_id}, updated

    def _sync_item_from_task(self, item: AcceptanceFixItem, *, now: str | None = None) -> AcceptanceFixItem:
        task_id = item.review_task_id
        project_id = str(item.target.get("project_id") or "")
        if not task_id or not project_id:
            return item
        try:
            task = ReviewTaskStore(self.project_store.project_dir(project_id)).read_task(task_id)
        except Exception:
            return item
        status = item.status
        resolution = dict(item.resolution or {})
        if task.status in TERMINAL_REVIEW_TASK_STATUSES:
            status = "fixed" if task.status == "resolved" else "closed"
            resolution = {"status": status, "notes": task.resolution_note or ""}
        elif task.status in OPEN_REVIEW_TASK_STATUSES and item.status not in {"waived", "fixed"}:
            status = "in_progress"
        if status == item.status and resolution == item.resolution:
            return item
        return AcceptanceFixItem.from_dict({**item.to_dict(), "status": status, "resolution": resolution, "updated_at": now or now_iso()})

    def _with_fresh_counts(self, sprint: AcceptanceFixSprint) -> AcceptanceFixSprint:
        items = self.read_items(sprint.fix_sprint_id) if (self.sprint_dir(sprint.fix_sprint_id) / "fix-items.json").exists() else []
        stale = False
        if sprint.status not in {"archived", "closed"}:
            try:
                stale = self.sprint_is_stale(sprint)
            except Exception:
                stale = True
        status = "stale" if stale else sprint.status
        return AcceptanceFixSprint.from_dict({**sprint.to_dict(), "status": status, "counts": _counts(items, self.project_store)})

    def _update_item(self, fix_sprint_id: str, item_id: str, patch: ImplementationDocument, *, now: str | None = None) -> AcceptanceFixItem:
        now = now or now_iso()
        items = self.read_items(fix_sprint_id)
        updated = None
        rows = []
        for item in items:
            if item.item_id == item_id:
                updated = AcceptanceFixItem.from_dict({**item.to_dict(), **patch, "updated_at": now})
                rows.append(updated)
            else:
                rows.append(item)
        if updated is None:
            raise AcceptanceFixSprintNotFoundError(item_id)
        self._write_items(fix_sprint_id, rows)
        self.refresh_status(fix_sprint_id, now=now)
        return updated

    def _write_sprint(self, sprint: AcceptanceFixSprint) -> None:
        path = self.sprint_dir(sprint.fix_sprint_id) / "fix-sprint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, sprint.to_dict())

    def _write_items(self, fix_sprint_id: str, items: list[AcceptanceFixItem]) -> None:
        write_json(self.sprint_dir(fix_sprint_id) / "fix-items.json", {"schema_version": ACCEPTANCE_FIX_ITEMS_SCHEMA_VERSION, "items": [item.to_dict() for item in items]})

    def _reserve_sprint_dir(self) -> tuple[str, Path]:
        index = 1
        while True:
            sprint_id = f"afs-{index:06d}"
            path = self.root / sprint_id
            try:
                path.mkdir(parents=True, exist_ok=False)
                return sprint_id, path
            except FileExistsError:
                index += 1


















































_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()

_v142_afs_readiness.bind_globals(globals())
