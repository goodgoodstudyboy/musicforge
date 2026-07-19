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

ReleasePortfolioGovernanceStateError = _make_deferred_global('ReleasePortfolioGovernanceStateError')
_event_count = _make_deferred_global('_event_count')
_write_json = _make_deferred_global('_write_json')
action_plan_integrity_ok = _make_deferred_global('action_plan_integrity_ok')
execution_report_integrity_ok = _make_deferred_global('execution_report_integrity_ok')
queue_integrity_ok = _make_deferred_global('queue_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceStateError, _event_count, _write_json, action_plan_integrity_ok, execution_report_integrity_ok, queue_integrity_ok
    ReleasePortfolioGovernanceStateError = namespace.get('ReleasePortfolioGovernanceStateError', ReleasePortfolioGovernanceStateError)
    _event_count = namespace.get('_event_count', _event_count)
    _write_json = namespace.get('_write_json', _write_json)
    action_plan_integrity_ok = namespace.get('action_plan_integrity_ok', action_plan_integrity_ok)
    execution_report_integrity_ok = namespace.get('execution_report_integrity_ok', execution_report_integrity_ok)
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




class ReleasePortfolioGovernanceStoreEvidenceMixin:
    def _is_stale(self, queue: DomainDocument, plan: DomainDocument) -> bool:
        if queue.get("status") == "stale":
            return True
        if not queue_integrity_ok(queue):
            return True
        if not action_plan_integrity_ok(plan):
            return True
        current = self._current_source(str(queue.get("portfolio_id") or ""))
        return bool(current.get("stale")) or stable_hash(current) != str(queue.get("source_hash") or "") or str(plan.get("integrity_hash") or "") != str(queue.get("action_plan_hash") or "")

    def _ensure_mutable(self, queue_id: str) -> None:
        path = self.queue_dir(queue_id) / "signoff.json"
        if not path.exists():
            return
        try:
            signoff = read_json(path)
        except Exception:
            raise ReleasePortfolioGovernanceStateError("Portfolio Governance Signoff exists but cannot be read. Reset signoff before mutating queue evidence.")
        if isinstance(signoff, dict) and signoff.get("status") in {"signed", "force_signed"}:
            raise ReleasePortfolioGovernanceStateError("Signed Portfolio Governance Queue is immutable. Reset signoff before mutating queue evidence.")

    def _ensure_queue_current_for_export(self, queue: DomainDocument, plan: DomainDocument, execution: DomainDocument, *, now: str) -> None:
        if queue.get("status") == "stale":
            self._mark_stale_and_raise(queue, now=now)
        if str(plan.get("integrity_hash") or "") != str(queue.get("action_plan_hash") or ""):
            self._mark_stale_and_raise(queue, now=now)
        current = self._current_source(str(queue.get("portfolio_id") or ""))
        current_hash = stable_hash(current)
        if not bool(current.get("stale")) and current_hash == str(queue.get("source_hash") or ""):
            return
        post = _as_document(execution.get("post_conditions"))
        documented_run_drift = (
            execution_report_integrity_ok(execution)
            and str(execution.get("integrity_hash") or "") == str(queue.get("latest_execution_report_hash") or "")
            and str(post.get("pre_source_hash") or "") == str(queue.get("source_hash") or "")
            and str(post.get("post_source_hash") or "") == current_hash
            and bool(post.get("portfolio_refresh_required"))
        )
        if documented_run_drift:
            return
        self._mark_stale_and_raise(queue, now=now)

    def _mark_stale_and_raise(self, queue: DomainDocument, *, now: str) -> None:
        queue["status"] = "stale"
        queue["updated_at"] = now
        queue["integrity_hash"] = queue_integrity_hash(queue)
        _write_json(self.queue_path(str(queue.get("queue_id") or "")), queue)
        raise ReleasePortfolioGovernanceStateError(PORTFOLIO_GOVERNANCE_STALE_MESSAGE)

    def _find_open_queue(self, portfolio_id: str, source_hash: str) -> DomainDocument | None:
        for queue in self.list_queues(portfolio_id=portfolio_id, include_archived=True):
            if queue.get("status") in OPEN_QUEUE_STATUSES and queue.get("source_hash") == source_hash:
                return queue
        return None

    def _reserve_queue_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            queue_id = f"pgq-{index:06d}"
            directory = self.root / queue_id
            try:
                directory.mkdir(parents=True, exist_ok=False)
                return queue_id
            except FileExistsError:
                continue
        raise ReleasePortfolioGovernanceStateError("Unable to allocate a unique Governance Queue id.")

    def _append_event(self, queue_id: str, event_type: str, summary: DomainDocument, *, now: str | None = None) -> None:
        path = self.events_path(queue_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = _event_count(path)
        event = sanitize_metadata({"event_id": f"pgqevt-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
