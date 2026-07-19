# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_operations_audit import ReleaseOperationsAuditStore as ReleaseOperationsAuditStore
from song_agent.domains.trust.release_operations_audit_verifier import verify_release_operations_audit_package as verify_release_operations_audit_package, write_release_operations_audit_verification_report as write_release_operations_audit_verification_report
from song_agent.domains.trust.release_operations_archive_verifier import verify_release_operations_archive_package as verify_release_operations_archive_package, write_release_operations_archive_verification_report as write_release_operations_archive_verification_report
from song_agent.domains.trust.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore as ReleaseOperationsReviewerPackStore
from song_agent.domains.trust.release_operations_reviewer_pack_verifier import verify_release_operations_reviewer_pack as verify_release_operations_reviewer_pack, write_release_operations_reviewer_pack_verification_report as write_release_operations_reviewer_pack_verification_report
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore as ReleaseOperationsSignoffStore
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_ok as portfolio_report_integrity_ok, portfolio_risk_register_integrity_ok as portfolio_risk_register_integrity_ok, portfolio_trend_integrity_ok as portfolio_trend_integrity_ok
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_contracts import ACTION_PLAN_HASH_EXCLUDE_KEYS as ACTION_PLAN_HASH_EXCLUDE_KEYS, EXECUTION_REPORT_HASH_EXCLUDE_KEYS as EXECUTION_REPORT_HASH_EXCLUDE_KEYS, MANIFEST_HASH_EXCLUDE_KEYS as MANIFEST_HASH_EXCLUDE_KEYS, MANUAL_LIST_HASH_EXCLUDE_KEYS as MANUAL_LIST_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_BLOCKED_KEYS, QUEUE_HASH_EXCLUDE_KEYS as QUEUE_HASH_EXCLUDE_KEYS, action_plan_integrity_hash as action_plan_integrity_hash, execution_report_integrity_hash as execution_report_integrity_hash, governance_manifest_integrity_hash as governance_manifest_integrity_hash, manual_action_list_integrity_hash as manual_action_list_integrity_hash, queue_integrity_hash as queue_integrity_hash

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

ReleasePortfolioGovernanceNotFoundError = _make_deferred_global('ReleasePortfolioGovernanceNotFoundError')
ReleasePortfolioGovernanceStateError = _make_deferred_global('ReleasePortfolioGovernanceStateError')
_build_action_plan = _make_deferred_global('_build_action_plan')
_ensure_within = _make_deferred_global('_ensure_within')
_execution_report = _make_deferred_global('_execution_report')
_file_record = _make_deferred_global('_file_record')
_governance_actions_markdown = _make_deferred_global('_governance_actions_markdown')
_manual_action_list = _make_deferred_global('_manual_action_list')
_manual_actions_markdown = _make_deferred_global('_manual_actions_markdown')
_queue_execution_summary = _make_deferred_global('_queue_execution_summary')
_queue_status_from_plan = _make_deferred_global('_queue_status_from_plan')
_read_json_default = _make_deferred_global('_read_json_default')
_risk_recommendation_map = _make_deferred_global('_risk_recommendation_map')
_safe_text = _make_deferred_global('_safe_text')
_sha256 = _make_deferred_global('_sha256')
_validate_queue_id = _make_deferred_global('_validate_queue_id')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_zip_entries = _make_deferred_global('_zip_entries')
action_plan_integrity_ok = _make_deferred_global('action_plan_integrity_ok')
execution_report_integrity_ok = _make_deferred_global('execution_report_integrity_ok')
item_result_integrity_hash = _make_deferred_global('item_result_integrity_hash')
manual_action_list_integrity_ok = _make_deferred_global('manual_action_list_integrity_ok')
queue_integrity_ok = _make_deferred_global('queue_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceNotFoundError, ReleasePortfolioGovernanceStateError, _build_action_plan, _ensure_within, _execution_report, _file_record, _governance_actions_markdown
    global _manual_action_list, _manual_actions_markdown, _queue_execution_summary, _queue_status_from_plan, _read_json_default, _risk_recommendation_map, _safe_text, _sha256
    global _validate_queue_id, _write_json, _write_readme, _zip_entries, action_plan_integrity_ok, execution_report_integrity_ok, item_result_integrity_hash, manual_action_list_integrity_ok
    global queue_integrity_ok
    ReleasePortfolioGovernanceNotFoundError = namespace.get('ReleasePortfolioGovernanceNotFoundError', ReleasePortfolioGovernanceNotFoundError)
    ReleasePortfolioGovernanceStateError = namespace.get('ReleasePortfolioGovernanceStateError', ReleasePortfolioGovernanceStateError)
    _build_action_plan = namespace.get('_build_action_plan', _build_action_plan)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _execution_report = namespace.get('_execution_report', _execution_report)
    _file_record = namespace.get('_file_record', _file_record)
    _governance_actions_markdown = namespace.get('_governance_actions_markdown', _governance_actions_markdown)
    _manual_action_list = namespace.get('_manual_action_list', _manual_action_list)
    _manual_actions_markdown = namespace.get('_manual_actions_markdown', _manual_actions_markdown)
    _queue_execution_summary = namespace.get('_queue_execution_summary', _queue_execution_summary)
    _queue_status_from_plan = namespace.get('_queue_status_from_plan', _queue_status_from_plan)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _risk_recommendation_map = namespace.get('_risk_recommendation_map', _risk_recommendation_map)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _sha256 = namespace.get('_sha256', _sha256)
    _validate_queue_id = namespace.get('_validate_queue_id', _validate_queue_id)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    action_plan_integrity_ok = namespace.get('action_plan_integrity_ok', action_plan_integrity_ok)
    execution_report_integrity_ok = namespace.get('execution_report_integrity_ok', execution_report_integrity_ok)
    item_result_integrity_hash = namespace.get('item_result_integrity_hash', item_result_integrity_hash)
    manual_action_list_integrity_ok = namespace.get('manual_action_list_integrity_ok', manual_action_list_integrity_ok)
    queue_integrity_ok = namespace.get('queue_integrity_ok', queue_integrity_ok)
    _bind_deferred_defaults(namespace)


PORTFOLIO_GOVERNANCE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_EXPORT_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_STALE_MESSAGE = "Portfolio Governance Queue source is stale. Refresh Portfolio Audit and create a new queue."
OPEN_QUEUE_STATUSES = {"draft", "planned", "running", "safe_completed", "manual_required", "blocked", "failed"}
SAFE_ACTIONS = {
    "portfolio.refresh",
    "portfolio.export",
    "portfolio.zip",
    "portfolio.verify",
    "reviewer_pack.refresh",
    "reviewer_pack.export",
    "reviewer_pack.zip",
    "reviewer_pack.verify",
    "operations_audit.refresh",
    "operations_audit.export",
    "operations_audit.zip",
    "operations_audit.verify",
    "operations_archive.verify",
    "runbook.refresh_report",
}




class ReleasePortfolioGovernanceStoreReadinessMixin:
    def queue_dir(self, queue_id: str) -> Path:
        return self.root / _validate_queue_id(queue_id)

    def queue_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "queue.json"

    def action_plan_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "action-plan.json"

    def execution_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "execution-report.json"

    def manual_action_list_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "manual-action-list.json"

    def events_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "governance-events.jsonl"

    def item_results_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "item-results"

    def export_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "governance-export"

    def zip_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "governance-queue.zip"

    def verification_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "verification-report.json"

    def list_queues(self, *, portfolio_id: str | None = None, include_archived: bool = False) -> list[DomainDocument]:
        rows: list[DomainDocument] = []
        for path in self.root.glob("*/queue.json") if self.root.exists() else []:
            try:
                queue = self.get_queue(path.parent.name)
            except Exception:
                continue
            if portfolio_id and str(queue.get("portfolio_id") or "") != portfolio_id:
                continue
            if not include_archived and queue.get("status") == "archived":
                continue
            rows.append(queue)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def get_queue(self, queue_id: str) -> DomainDocument:
        path = self.queue_path(queue_id)
        if not path.exists():
            raise ReleasePortfolioGovernanceNotFoundError("Release Portfolio Governance Queue does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)

    def read_action_plan(self, queue_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.action_plan_path(queue_id), default=default)

    def read_execution_report(self, queue_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.execution_report_path(queue_id), default=default)

    def read_manual_action_list(self, queue_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.manual_action_list_path(queue_id), default=default)

    def read_export_manifest(self, queue_id: str) -> DomainDocument:
        path = self.export_dir(queue_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceNotFoundError("Release Portfolio Governance export has not been generated.")
        return _read_json_default(path, default={})

    def create_from_portfolio(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            source = self._current_source(portfolio_id)
            source_hash = stable_hash(source)
            if source.get("stale"):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Queue source is stale. Refresh Portfolio Audit and create a new queue.")
            if not bool(payload.get("force_new", False)):
                existing = self._find_open_queue(portfolio_id, source_hash)
                if existing:
                    existing["existing"] = True
                    return existing
            queue_id = self._reserve_queue_id()
            report = self.portfolio_store.read_report(portfolio_id, default={})
            trend = self.portfolio_store.read_trend_report(portfolio_id, default={})
            risks = self.portfolio_store.read_risk_register(portfolio_id, default={})
            plan = _build_action_plan(queue_id, source, report, trend, risks, payload, generated_at=now)
            manual = _manual_action_list(queue_id, plan, generated_at=now)
            execution = _execution_report(queue_id, source_hash=source_hash, plan=plan, generated_at=now, item_results=[], post_conditions={})
            queue = {
                "schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION,
                "queue_id": queue_id,
                "portfolio_id": portfolio_id,
                "name": _safe_text(payload.get("name"), 160) or "Portfolio Governance Queue",
                "status": _queue_status_from_plan(plan),
                "created_at": now,
                "updated_at": now,
                "source": source,
                "source_hash": source_hash,
                "action_plan_hash": plan.get("integrity_hash"),
                "execution": _queue_execution_summary(execution),
                "latest_execution_report_hash": execution.get("integrity_hash"),
                "latest_export_manifest_hash": None,
                "latest_zip_sha256": None,
            }
            queue["integrity_hash"] = queue_integrity_hash(queue)
            qdir = self.queue_dir(queue_id)
            qdir.mkdir(parents=True, exist_ok=True)
            self.item_results_dir(queue_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.queue_path(queue_id), queue)
            _write_json(self.action_plan_path(queue_id), plan)
            _write_json(self.execution_report_path(queue_id), execution)
            _write_json(self.manual_action_list_path(queue_id), manual)
            self._append_event(queue_id, "duplicate_source_queue_created" if payload.get("force_new") else "created", {"portfolio_id": portfolio_id, "item_count": len(plan.get("items", []))}, now=now)
            return sanitize_metadata(queue, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)

    def run_safe_actions(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            queue = self.get_queue(queue_id)
            self._ensure_mutable(queue_id)
            if queue.get("status") == "archived":
                raise ReleasePortfolioGovernanceStateError("Archived Portfolio Governance Queue cannot run.")
            plan = self.read_action_plan(queue_id, default={})
            if not action_plan_integrity_ok(plan):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Action Plan integrity failed.")
            if self._is_stale(queue, plan):
                queue["status"] = "stale"
                queue["updated_at"] = now
                queue["integrity_hash"] = queue_integrity_hash(queue)
                _write_json(self.queue_path(queue_id), queue)
                raise ReleasePortfolioGovernanceStateError(PORTFOLIO_GOVERNANCE_STALE_MESSAGE)
            allowed_types = {str(item).strip() for item in payload.get("action_types", []) if str(item).strip()} if isinstance(payload.get("action_types"), list) else set()
            max_items = int(payload.get("max_items") or 500)
            max_items = max(1, min(500, max_items))
            queue["status"] = "running"
            previous_run_count = int((_as_document(queue.get("execution"))).get("run_count") or 0)
            queue["execution"] = {**(_as_document(queue.get("execution"))), "started_at": now, "run_count": previous_run_count + 1}
            queue["updated_at"] = now
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.queue_path(queue_id), queue)
            pre_source_hash = stable_hash(self._current_source(str(queue.get("portfolio_id") or "")))
            item_results: list[DomainDocument] = []
            ran = 0
            for item in plan.get("items", []) if isinstance(plan.get("items"), list) else []:
                if not isinstance(item, dict):
                    continue
                if item.get("safety") == "manual_required":
                    item["status"] = "manual_required"
                    continue
                if item.get("safety") == "blocked":
                    item["status"] = "blocked"
                    continue
                if item.get("status") not in {"queued", "failed"}:
                    continue
                if allowed_types and str(item.get("action_type") or "") not in allowed_types:
                    item["status"] = "skipped"
                    continue
                if ran >= max_items:
                    break
                ran += 1
                result = self._execute_safe_item(queue, item, now=now)
                item.update({"status": result.get("status"), "result_hash": stable_hash(result), "ran_at": now})
                item_results.append(result)
                _write_json(self.item_results_dir(queue_id) / f"{item['item_id']}.json", result)
            post_source = self._current_source(str(queue.get("portfolio_id") or ""))
            post_source_hash = stable_hash(post_source)
            refresh_required = bool(post_source.get("stale")) or post_source_hash != pre_source_hash
            refreshed_report_hash = None
            if refresh_required and bool(payload.get("refresh_portfolio_after_safe_actions", False)):
                refreshed = self.portfolio_store.refresh(str(queue.get("portfolio_id") or ""))
                refreshed_report_hash = refreshed.get("integrity_hash")
                post_source = self._current_source(str(queue.get("portfolio_id") or ""))
                post_source_hash = stable_hash(post_source)
                refresh_required = bool(post_source.get("stale"))
            plan["integrity_hash"] = action_plan_integrity_hash(plan)
            execution = _execution_report(
                queue_id,
                source_hash=str(queue.get("source_hash") or ""),
                plan=plan,
                generated_at=now_iso(),
                item_results=item_results,
                post_conditions={
                    "pre_source_hash": pre_source_hash,
                    "post_source_hash": post_source_hash,
                    "portfolio_refresh_required": refresh_required,
                    "portfolio_refreshed": bool(refreshed_report_hash),
                    "post_portfolio_report_hash": refreshed_report_hash,
                },
            )
            manual = _manual_action_list(queue_id, plan, generated_at=now_iso())
            status = execution.get("status") or "safe_completed"
            execution_summary = _queue_execution_summary(execution)
            execution_summary["run_count"] = previous_run_count + 1
            execution_summary["started_at"] = now
            queue.update(
                {
                    "status": status,
                    "updated_at": now_iso(),
                    "action_plan_hash": action_plan_integrity_hash(plan),
                    "execution": execution_summary,
                    "latest_execution_report_hash": execution.get("integrity_hash"),
                }
            )
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.action_plan_path(queue_id), plan)
            _write_json(self.execution_report_path(queue_id), execution)
            _write_json(self.manual_action_list_path(queue_id), manual)
            _write_json(self.queue_path(queue_id), queue)
            self._append_event(queue_id, "run_safe_completed", {"executed_count": ran, "status": status, "post_portfolio_refresh_required": refresh_required}, now=now_iso())
            return sanitize_metadata(queue, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)

    def export_queue(self, queue_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            queue = self.get_queue(queue_id)
            self._ensure_mutable(queue_id)
            if queue.get("status") == "archived":
                raise ReleasePortfolioGovernanceStateError("Archived Portfolio Governance Queue cannot be exported.")
            plan = self.read_action_plan(queue_id, default={})
            execution = self.read_execution_report(queue_id, default={})
            manual = self.read_manual_action_list(queue_id, default={})
            if not queue_integrity_ok(queue):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Queue integrity failed.")
            if not action_plan_integrity_ok(plan):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Action Plan integrity failed.")
            if not execution_report_integrity_ok(execution):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Execution Report integrity failed.")
            self._ensure_queue_current_for_export(queue, plan, execution, now=now)
            if not manual_action_list_integrity_ok(manual):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Manual Action List integrity failed.")
            export_dir = self.export_dir(queue_id).resolve()
            queue_dir = self.queue_dir(queue_id).resolve()
            _ensure_within(queue_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            source_summary = {"queue_id": queue_id, "portfolio_id": queue.get("portfolio_id"), "source": queue.get("source"), "source_hash": queue.get("source_hash")}
            risk_map = _risk_recommendation_map(plan)
            _write_json(export_dir / "queue.json", queue)
            _write_json(export_dir / "action-plan.json", plan)
            _write_json(export_dir / "execution-report.json", execution)
            _write_json(export_dir / "manual-action-list.json", manual)
            _write_json(export_dir / "portfolio-source-summary.json", source_summary)
            _write_json(export_dir / "action-source-map.json", risk_map)
            (export_dir / "GOVERNANCE_ACTIONS.md").write_text(_governance_actions_markdown(queue, plan, execution), encoding="utf-8")
            (export_dir / "MANUAL_ACTIONS.md").write_text(_manual_actions_markdown(manual), encoding="utf-8")
            _write_readme(export_dir, queue, execution)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": PORTFOLIO_GOVERNANCE_EXPORT_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_queue",
                "tool": {"name": "MusicForge Release Portfolio Governance Queue", "version": __version__},
                "queue_id": queue_id,
                "portfolio_id": queue.get("portfolio_id"),
                "created_at": now,
                "source_hash": queue.get("source_hash"),
                "summary": execution.get("summary", {}),
                "sidecars": {
                    "queue": {"payload_hash": queue.get("integrity_hash")},
                    "action_plan": {"payload_hash": plan.get("integrity_hash")},
                    "execution_report": {"payload_hash": execution.get("integrity_hash")},
                    "manual_action_list": {"payload_hash": manual.get("integrity_hash")},
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
            }
            manifest["integrity_hash"] = governance_manifest_integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            queue.update({"updated_at": now, "latest_export_manifest_hash": manifest["integrity_hash"]})
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.queue_path(queue_id), queue)
            self._append_event(queue_id, "exported", {"file_count": len(files)}, now=now)
            return manifest

    def build_zip(self, queue_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            queue = self.get_queue(queue_id)
            self._ensure_mutable(queue_id)
            if queue.get("status") == "archived":
                raise ReleasePortfolioGovernanceStateError("Archived Portfolio Governance Queue cannot be zipped.")
            plan = self.read_action_plan(queue_id, default={})
            execution = self.read_execution_report(queue_id, default={})
            if not queue_integrity_ok(queue):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Queue integrity failed.")
            if not action_plan_integrity_ok(plan):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Action Plan integrity failed.")
            if not execution_report_integrity_ok(execution):
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Execution Report integrity failed.")
            self._ensure_queue_current_for_export(queue, plan, execution, now=now)
            queue_dir = self.queue_dir(queue_id).resolve()
            export_dir = self.export_dir(queue_id).resolve()
            zip_path = self.zip_path(queue_id).resolve()
            _ensure_within(queue_dir, export_dir)
            _ensure_within(queue_dir, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_queue(queue_id, now=now)
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = governance_manifest_integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            queue = self.get_queue(queue_id)
            queue.update({"updated_at": now, "latest_zip_sha256": info["sha256"]})
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.queue_path(queue_id), queue)
            self._append_event(queue_id, "zip_built", {"sha256": info["sha256"], "entry_count": len(entries)}, now=now)
            return sanitize_metadata(info, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)

    def archive(self, queue_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            queue = self.get_queue(queue_id)
            self._ensure_mutable(queue_id)
            queue["status"] = "archived"
            queue["updated_at"] = now or now_iso()
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.queue_path(queue_id), queue)
            self._append_event(queue_id, "archived", {}, now=queue["updated_at"])
            return queue

    def _execute_safe_item(self, queue: DomainDocument, item: DomainDocument, *, now: str) -> DomainDocument:
        action_type = str(item.get("action_type") or "")
        release_id = str(item.get("release_id") or "")
        queue_id = str(queue.get("queue_id") or "")
        result: object = {
            "schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION,
            "queue_id": queue_id,
            "item_id": item.get("item_id"),
            "action_type": action_type,
            "release_id": release_id or None,
            "started_at": now,
            "completed_at": now_iso(),
            "status": "completed",
            "message": "",
            "outputs": {},
        }
        try:
            if action_type == "portfolio.refresh":
                report = self.portfolio_store.refresh(str(queue.get("portfolio_id") or ""))
                result["outputs"] = {"portfolio_report_hash": report.get("integrity_hash"), "status": report.get("status")}
            elif action_type == "portfolio.export":
                manifest = self.portfolio_store.export_portfolio(str(queue.get("portfolio_id") or ""))
                result["outputs"] = {"manifest_hash": manifest.get("integrity_hash")}
            elif action_type == "portfolio.zip":
                result["outputs"] = self.portfolio_store.build_zip(str(queue.get("portfolio_id") or ""))
            elif action_type == "portfolio.verify":
                from song_agent.domains.trust.release_portfolio_audit_verifier import verify_release_portfolio_audit_package, write_release_portfolio_audit_verification_report

                portfolio_id = str(queue.get("portfolio_id") or "")
                report = verify_release_portfolio_audit_package(self.portfolio_store.zip_path(portfolio_id), strict=True, require_reviewer_packs=True, require_audit=True, require_archive=True)
                write_release_portfolio_audit_verification_report(report, self.portfolio_store.verification_report_path(portfolio_id))
                result["outputs"] = {"verification_status": report.get("status")}
            elif action_type == "reviewer_pack.refresh":
                report = self.reviewer_pack_store.refresh(release_id)
                result["outputs"] = {"reviewer_report_hash": report.get("integrity_hash"), "status": report.get("status")}
            elif action_type == "reviewer_pack.export":
                manifest = self.reviewer_pack_store.export_pack(release_id)
                result["outputs"] = {"manifest_hash": manifest.get("integrity_hash")}
            elif action_type == "reviewer_pack.zip":
                result["outputs"] = self.reviewer_pack_store.build_zip(release_id)
            elif action_type == "reviewer_pack.verify":
                report = verify_release_operations_reviewer_pack(self.reviewer_pack_store.zip_path(release_id), strict=True, require_audit=True, require_signed=True, require_archive=True)
                write_release_operations_reviewer_pack_verification_report(report, self.reviewer_pack_store.verification_report_path(release_id))
                result["outputs"] = {"verification_status": report.get("status")}
            elif action_type == "operations_audit.refresh":
                report = self.audit_store.refresh(release_id)
                result["outputs"] = {"audit_report_hash": report.get("integrity_hash"), "status": report.get("status")}
            elif action_type == "operations_audit.export":
                manifest = self.audit_store.export_audit(release_id)
                result["outputs"] = {"manifest_hash": manifest.get("integrity_hash")}
            elif action_type == "operations_audit.zip":
                result["outputs"] = self.audit_store.build_zip(release_id)
            elif action_type == "operations_audit.verify":
                report = verify_release_operations_audit_package(self.audit_store.zip_path(release_id), require_current=True, require_signed=True, require_archive=True)
                write_release_operations_audit_verification_report(report, self.audit_store.verification_report_path(release_id))
                result["outputs"] = {"verification_status": report.get("status")}
            elif action_type == "operations_archive.verify":
                zip_path = self.signoff_store.archive_zip_path(release_id)
                if not zip_path.exists():
                    result.update({"status": "blocked", "message": "Operations Archive ZIP is missing."})
                else:
                    report = verify_release_operations_archive_package(zip_path, require_signed=True)
                    write_release_operations_archive_verification_report(report, self.signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
                    result["outputs"] = {"verification_status": report.get("status")}
            elif action_type == "runbook.refresh_report":
                report = self.portfolio_store.operations_store.refresh(release_id)
                result["outputs"] = {"operations_report_hash": report.get("integrity_hash"), "status": report.get("status")}
            else:
                result.update({"status": "blocked", "message": f"Unsupported safe action: {action_type}"})
        except Exception as exc:
            result.update({"status": "failed", "message": sanitize_sensitive_text(str(exc))})
        result["completed_at"] = now_iso()
        result["integrity_hash"] = item_result_integrity_hash(result)
        return sanitize_metadata(result, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)

    def _current_source(self, portfolio_id: str) -> DomainDocument:
        report = self.portfolio_store.read_report(portfolio_id, default={})
        trend = self.portfolio_store.read_trend_report(portfolio_id, default={})
        risks = self.portfolio_store.read_risk_register(portfolio_id, default={})
        if not report:
            raise ReleasePortfolioGovernanceStateError("Portfolio Audit Report is missing. Refresh Portfolio Audit before creating a Governance Queue.")
        if not portfolio_report_integrity_ok(report):
            raise ReleasePortfolioGovernanceStateError("Portfolio Audit Report integrity failed.")
        if not portfolio_trend_integrity_ok(trend):
            raise ReleasePortfolioGovernanceStateError("Portfolio Trend Report integrity failed.")
        if not portfolio_risk_register_integrity_ok(risks):
            raise ReleasePortfolioGovernanceStateError("Portfolio Risk Register integrity failed.")
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "portfolio_report_hash": report.get("integrity_hash"),
                "portfolio_source_hash": report.get("source_hash"),
                "trend_report_hash": trend.get("integrity_hash"),
                "risk_register_hash": risks.get("integrity_hash"),
                "recommendation_count": len(report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else []),
                "risk_count": len(risks.get("risks", []) if isinstance(risks.get("risks"), list) else []),
                "stale": self.portfolio_store.report_is_stale(portfolio_id, report),
            },
            blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS,
        )
