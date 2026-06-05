from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.release_operations_audit import ReleaseOperationsAuditStore
from song_agent.release_operations_audit_verifier import verify_release_operations_audit_package, write_release_operations_audit_verification_report
from song_agent.release_operations_archive_verifier import verify_release_operations_archive_package, write_release_operations_archive_verification_report
from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
from song_agent.release_operations_reviewer_pack_verifier import verify_release_operations_reviewer_pack, write_release_operations_reviewer_pack_verification_report
from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
from song_agent.release_portfolio_audit import (
    ReleasePortfolioAuditStore,
    portfolio_report_integrity_ok,
    portfolio_risk_register_integrity_ok,
    portfolio_trend_integrity_ok,
)
from song_agent.releases import stable_hash


PORTFOLIO_GOVERNANCE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_EXPORT_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}
QUEUE_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at", "latest_execution_report_hash", "latest_export_manifest_hash", "latest_zip_sha256", "existing"}
ACTION_PLAN_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
EXECUTION_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
MANUAL_LIST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
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


class ReleasePortfolioGovernanceError(ValueError):
    pass


class ReleasePortfolioGovernanceNotFoundError(ReleasePortfolioGovernanceError):
    pass


class ReleasePortfolioGovernanceStateError(ReleasePortfolioGovernanceError):
    pass


class ReleasePortfolioGovernanceStore:
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        reviewer_pack_store: ReleaseOperationsReviewerPackStore,
        audit_store: ReleaseOperationsAuditStore,
        signoff_store: ReleaseOperationsSignoffStore,
        root: Path | str | None = None,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.reviewer_pack_store = reviewer_pack_store
        self.audit_store = audit_store
        self.signoff_store = signoff_store
        self.root = Path(root).resolve() if root is not None else (portfolio_store.root.parent / "portfolio-governance-queues").resolve()
        self.lock = threading.RLock()

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

    def list_queues(self, *, portfolio_id: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
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

    def get_queue(self, queue_id: str) -> dict[str, Any]:
        path = self.queue_path(queue_id)
        if not path.exists():
            raise ReleasePortfolioGovernanceNotFoundError("Release Portfolio Governance Queue does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)

    def read_action_plan(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.action_plan_path(queue_id), default=default)

    def read_execution_report(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.execution_report_path(queue_id), default=default)

    def read_manual_action_list(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.manual_action_list_path(queue_id), default=default)

    def read_export_manifest(self, queue_id: str) -> dict[str, Any]:
        path = self.export_dir(queue_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceNotFoundError("Release Portfolio Governance export has not been generated.")
        return _read_json_default(path, default={})

    def create_from_portfolio(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def run_safe_actions(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            queue = self.get_queue(queue_id)
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
                raise ReleasePortfolioGovernanceStateError("Portfolio Governance Queue source is stale. Refresh Portfolio Audit and create a new queue.")
            allowed_types = {str(item).strip() for item in payload.get("action_types", []) if str(item).strip()} if isinstance(payload.get("action_types"), list) else set()
            max_items = int(payload.get("max_items") or 500)
            max_items = max(1, min(500, max_items))
            queue["status"] = "running"
            previous_run_count = int((queue.get("execution") if isinstance(queue.get("execution"), dict) else {}).get("run_count") or 0)
            queue["execution"] = {**(queue.get("execution") if isinstance(queue.get("execution"), dict) else {}), "started_at": now, "run_count": previous_run_count + 1}
            queue["updated_at"] = now
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.queue_path(queue_id), queue)
            pre_source_hash = stable_hash(self._current_source(str(queue.get("portfolio_id") or "")))
            item_results: list[dict[str, Any]] = []
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

    def export_queue(self, queue_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            queue = self.get_queue(queue_id)
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

    def build_zip(self, queue_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
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

    def archive(self, queue_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            queue = self.get_queue(queue_id)
            queue["status"] = "archived"
            queue["updated_at"] = now or now_iso()
            queue["integrity_hash"] = queue_integrity_hash(queue)
            _write_json(self.queue_path(queue_id), queue)
            self._append_event(queue_id, "archived", {}, now=queue["updated_at"])
            return queue

    def _execute_safe_item(self, queue: dict[str, Any], item: dict[str, Any], *, now: str) -> dict[str, Any]:
        action_type = str(item.get("action_type") or "")
        release_id = str(item.get("release_id") or "")
        queue_id = str(queue.get("queue_id") or "")
        result = {
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
                from song_agent.release_portfolio_audit_verifier import verify_release_portfolio_audit_package, write_release_portfolio_audit_verification_report

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

    def _current_source(self, portfolio_id: str) -> dict[str, Any]:
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

    def _is_stale(self, queue: dict[str, Any], plan: dict[str, Any]) -> bool:
        if not queue_integrity_ok(queue):
            return True
        if not action_plan_integrity_ok(plan):
            return True
        current = self._current_source(str(queue.get("portfolio_id") or ""))
        return bool(current.get("stale")) or stable_hash(current) != str(queue.get("source_hash") or "") or str(plan.get("integrity_hash") or "") != str(queue.get("action_plan_hash") or "")

    def _find_open_queue(self, portfolio_id: str, source_hash: str) -> dict[str, Any] | None:
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

    def _append_event(self, queue_id: str, event_type: str, summary: dict[str, Any], *, now: str | None = None) -> None:
        path = self.events_path(queue_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = _event_count(path)
        event = sanitize_metadata({"event_id": f"pgqevt-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def queue_integrity_hash(queue: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (queue or {}).items() if key not in QUEUE_HASH_EXCLUDE_KEYS})


def queue_integrity_ok(queue: dict[str, Any] | None) -> bool:
    data = queue if isinstance(queue, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == queue_integrity_hash(data)


def action_plan_integrity_hash(plan: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (plan or {}).items() if key not in ACTION_PLAN_HASH_EXCLUDE_KEYS})


def action_plan_integrity_ok(plan: dict[str, Any] | None) -> bool:
    data = plan if isinstance(plan, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == action_plan_integrity_hash(data)


def execution_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in EXECUTION_REPORT_HASH_EXCLUDE_KEYS})


def execution_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == execution_report_integrity_hash(data)


def manual_action_list_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in MANUAL_LIST_HASH_EXCLUDE_KEYS})


def manual_action_list_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == manual_action_list_integrity_hash(data)


def item_result_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "integrity_hash"})


def governance_manifest_integrity_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in MANIFEST_HASH_EXCLUDE_KEYS})


def governance_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_manifest_integrity_hash(data)


def queue_summary(queue: dict[str, Any] | None, execution: dict[str, Any] | None = None) -> dict[str, Any]:
    q = queue if isinstance(queue, dict) else {}
    e = execution if isinstance(execution, dict) else {}
    summary = e.get("summary") if isinstance(e.get("summary"), dict) else q.get("execution") if isinstance(q.get("execution"), dict) else {}
    return sanitize_metadata(
        {
            "status": q.get("status") or e.get("status") or "missing",
            "queue_id": q.get("queue_id"),
            "portfolio_id": q.get("portfolio_id"),
            "total_items": summary.get("total_items", 0),
            "safe_completed": summary.get("safe_completed", 0),
            "manual_required": summary.get("manual_required", 0),
            "blocked": summary.get("blocked", 0),
            "failed": summary.get("failed", 0),
            "post_portfolio_refresh_required": bool((q.get("execution") if isinstance(q.get("execution"), dict) else {}).get("post_portfolio_refresh_required")),
            "integrity_ok": queue_integrity_ok(q),
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS,
    )


def _build_action_plan(queue_id: str, source: dict[str, Any], report: dict[str, Any], trend: dict[str, Any], risks: dict[str, Any], payload: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    risks_by_category = _ids_by_category(risks.get("risks", []) if isinstance(risks.get("risks"), list) else [])
    recs_by_category = _ids_by_category(report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else [], key_name="recommendation_id")
    release_summaries = report.get("release_summaries") if isinstance(report.get("release_summaries"), list) else []
    for release in release_summaries:
        if not isinstance(release, dict):
            continue
        release_id = str(release.get("release_id") or "")
        if not release_id:
            continue
        if release.get("reviewer_pack_verification_status") != "passed":
            for action in ("reviewer_pack.refresh", "reviewer_pack.export", "reviewer_pack.zip", "reviewer_pack.verify"):
                _add_item(items, action, release_id, "reviewer_pack", "high", "Reviewer Pack evidence is missing or not verified.", risks_by_category, recs_by_category)
        audit_summary = release.get("audit_summary") if isinstance(release.get("audit_summary"), dict) else {}
        if release.get("audit_verification_status") != "passed" or audit_summary.get("status") == "failed":
            for action in ("operations_audit.refresh", "operations_audit.export", "operations_audit.zip", "operations_audit.verify"):
                _add_item(items, action, release_id, "audit", "high", "Operations Audit evidence is missing or not verified.", risks_by_category, recs_by_category)
        archive = release.get("archive_summary") if isinstance(release.get("archive_summary"), dict) else {}
        if archive.get("verification_status") != "passed":
            if archive.get("manifest_hash"):
                _add_item(items, "operations_archive.verify", release_id, "archive", "medium", "Operations Archive verification is missing or failed.", risks_by_category, recs_by_category)
            else:
                _add_manual(items, "operations_archive.export_or_signoff_review", release_id, "archive", "medium", "Review Operations Signoff and export Archive before verification.", risks_by_category, recs_by_category)
        if int(release.get("applied_change_request_count") or 0) > 0:
            _add_manual(items, "change_request.review", release_id, "change_control", "medium", "Review recurring Change Request cause.", risks_by_category, recs_by_category)
            _add_manual(items, "process_rule_candidate.review", release_id, "change_control", "medium", "Decide whether a process rule should be updated.", risks_by_category, recs_by_category)
        reviewer_summary = release.get("reviewer_pack_summary") if isinstance(release.get("reviewer_pack_summary"), dict) else {}
        if int(reviewer_summary.get("manual_required_count") or 0) > 0:
            _add_manual(items, "runbook_policy.review", release_id, "manual_bottleneck", "low", "Review recurring manual-required runbook items.", risks_by_category, recs_by_category)
        if release.get("integrity_ok") is False or (audit_summary.get("status") == "failed"):
            _add_manual(items, "evidence_integrity.rebuild_review", release_id, "integrity", "critical", "Review corrupted evidence manually before rebuild.", risks_by_category, recs_by_category)
            _add_blocked(items, "unsafe_to_auto_fix", release_id, "integrity", "critical", "Unsafe to auto-fix evidence integrity issues.", risks_by_category, recs_by_category)
    if bool(payload.get("include_manual_actions", True)):
        for finding in trend.get("trend_findings", []) if isinstance(trend.get("trend_findings"), list) else []:
            if isinstance(finding, dict) and finding.get("category") == "change_control":
                _add_manual(items, "portfolio_policy.change", "", "change_control", "medium", "Review portfolio-level change-control trend.", risks_by_category, recs_by_category)
    if not bool(payload.get("include_low_risks", True)):
        items = [item for item in items if item.get("severity") != "low"]
    items = _dedupe_items(items)
    for index, item in enumerate(items, start=1):
        item["item_id"] = f"pgqitem-{index:06d}"
        item["status"] = "queued" if item.get("safety") == "safe" else item.get("safety")
    plan = {"schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION, "queue_id": queue_id, "generated_at": generated_at, "source_hash": stable_hash(source), "items": items}
    plan["integrity_hash"] = action_plan_integrity_hash(plan)
    return sanitize_metadata(plan, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _add_item(items: list[dict[str, Any]], action: str, release_id: str, category: str, severity: str, reason: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> None:
    items.append(_base_item(action, release_id, category, severity, reason, "safe", risks, recs))


def _add_manual(items: list[dict[str, Any]], action: str, release_id: str, category: str, severity: str, reason: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> None:
    item = _base_item(action, release_id, category, severity, reason, "manual_required", risks, recs)
    item["manual_instruction"] = _manual_instruction(action, category)
    items.append(item)


def _add_blocked(items: list[dict[str, Any]], action: str, release_id: str, category: str, severity: str, reason: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> None:
    items.append(_base_item(action, release_id, category, severity, reason, "blocked", risks, recs))


def _base_item(action: str, release_id: str, category: str, severity: str, reason: str, safety: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "item_id": "",
        "action_type": action,
        "scope": "release" if release_id else "portfolio",
        "release_id": release_id or None,
        "category": category,
        "severity": severity,
        "status": "queued",
        "safety": safety,
        "reason": reason,
        "source_risk_ids": risks.get(category, []),
        "source_recommendation_ids": recs.get(category, []),
        "depends_on": [],
        "expected_outputs": _expected_outputs(action),
        "manual_instruction": None,
    }


def _expected_outputs(action: str) -> list[str]:
    if action.endswith(".verify"):
        return ["verification_report"]
    if action.endswith(".zip"):
        return ["zip"]
    if action.endswith(".export"):
        return ["manifest"]
    if action.endswith(".refresh"):
        return ["report"]
    return []


def _manual_instruction(action: str, category: str) -> str:
    instructions = {
        "operations_archive.export_or_signoff_review": "Open Release Operations Signoff and Archive state, then decide whether archive export is allowed.",
        "change_request.review": "Review Release Operations Change Request history and decide whether a process fix is needed.",
        "process_rule_candidate.review": "Review whether this recurring issue should become a process rule.",
        "runbook_policy.review": "Review manual-required Runbook items and decide whether safe deterministic actions can be added later.",
        "evidence_integrity.rebuild_review": "Inspect corrupted evidence manually before any rebuild.",
        "portfolio_policy.change": "Review portfolio trend and decide whether governance policy needs adjustment.",
    }
    return instructions.get(action, f"Review {category} manually before taking action.")


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("action_type") or ""), str(item.get("release_id") or ""), str(item.get("safety") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _ids_by_category(items: list[Any], *, key_name: str = "risk_id") -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "")
        identifier = str(item.get(key_name) or "")
        if category and identifier:
            result.setdefault(category, []).append(identifier)
    return result


def _manual_action_list(queue_id: str, plan: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in plan.get("items", []) if isinstance(plan.get("items"), list) else []:
        if not isinstance(item, dict) or item.get("safety") != "manual_required":
            continue
        rows.append(
            {
                "item_id": item.get("item_id"),
                "release_id": item.get("release_id"),
                "action_type": item.get("action_type"),
                "title": item.get("reason"),
                "instruction": item.get("manual_instruction") or _manual_instruction(str(item.get("action_type") or ""), str(item.get("category") or "")),
                "required_role": "owner" if str(item.get("action_type") or "").startswith("change_request") else "reviewer",
                "risk_ids": item.get("source_risk_ids", []),
                "recommendation_ids": item.get("source_recommendation_ids", []),
            }
        )
    report = {"schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION, "queue_id": queue_id, "generated_at": generated_at, "items": rows}
    report["integrity_hash"] = manual_action_list_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _execution_report(queue_id: str, *, source_hash: str, plan: dict[str, Any], generated_at: str, item_results: list[dict[str, Any]], post_conditions: dict[str, Any]) -> dict[str, Any]:
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    summary = {
        "total_items": len(items),
        "safe_completed": sum(1 for item in items if isinstance(item, dict) and item.get("safety") == "safe" and item.get("status") == "completed"),
        "manual_required": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "manual_required"),
        "blocked": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "blocked"),
        "failed": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "failed"),
        "skipped": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "skipped"),
    }
    blockers = []
    warnings = []
    if summary["failed"]:
        blockers.append({"check_id": "failed_safe_actions", "message": "One or more safe actions failed."})
    if summary["blocked"]:
        warnings.append({"check_id": "blocked_actions", "message": "One or more actions are blocked."})
    if summary["manual_required"]:
        warnings.append({"check_id": "manual_required_actions", "message": "Manual-required governance actions remain."})
    if post_conditions.get("portfolio_refresh_required"):
        warnings.append({"check_id": "post_portfolio_refresh_required", "message": "Portfolio Audit must be refreshed after safe actions."})
    status = "failed" if summary["failed"] else "blocked" if summary["blocked"] else "manual_required" if summary["manual_required"] else "safe_completed"
    report = {
        "schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION,
        "queue_id": queue_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "status": status,
        "summary": summary,
        "item_results": item_results,
        "post_conditions": {
            "portfolio_refresh_required": bool(post_conditions.get("portfolio_refresh_required", False)),
            "portfolio_refreshed": bool(post_conditions.get("portfolio_refreshed", False)),
            "pre_source_hash": post_conditions.get("pre_source_hash"),
            "post_source_hash": post_conditions.get("post_source_hash"),
            "post_portfolio_report_hash": post_conditions.get("post_portfolio_report_hash"),
        },
        "warnings": warnings,
        "blockers": blockers,
    }
    report["integrity_hash"] = execution_report_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _queue_execution_summary(execution: dict[str, Any]) -> dict[str, Any]:
    summary = execution.get("summary") if isinstance(execution.get("summary"), dict) else {}
    post = execution.get("post_conditions") if isinstance(execution.get("post_conditions"), dict) else {}
    return {
        "started_at": None,
        "completed_at": execution.get("generated_at"),
        "run_count": 0,
        "safe_action_count": summary.get("safe_completed", 0),
        "manual_required_count": summary.get("manual_required", 0),
        "blocked_count": summary.get("blocked", 0),
        "failed_count": summary.get("failed", 0),
        "post_portfolio_refresh_required": bool(post.get("portfolio_refresh_required", False)),
        "post_portfolio_report_hash": post.get("post_portfolio_report_hash"),
        "total_items": summary.get("total_items", 0),
    }


def _queue_status_from_plan(plan: dict[str, Any]) -> str:
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    return "planned" if items else "safe_completed"


def _risk_recommendation_map(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_id": plan.get("queue_id"),
        "items": [
            {
                "item_id": item.get("item_id"),
                "action_type": item.get("action_type"),
                "release_id": item.get("release_id"),
                "risk_ids": item.get("source_risk_ids", []),
                "recommendation_ids": item.get("source_recommendation_ids", []),
            }
            for item in plan.get("items", [])
            if isinstance(item, dict)
        ],
    }


def _governance_actions_markdown(queue: dict[str, Any], plan: dict[str, Any], execution: dict[str, Any]) -> str:
    lines = [
        "# MusicForge Portfolio Governance Queue",
        "",
        f"Queue: {queue.get('queue_id')}",
        f"Portfolio: {queue.get('portfolio_id')}",
        f"Status: {queue.get('status')}",
        f"Execution: {execution.get('status')}",
        "",
        "## Actions",
    ]
    for item in plan.get("items", []) if isinstance(plan.get("items"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('item_id')} | {item.get('action_type')} | {item.get('release_id') or '-'} | {item.get('safety')} | {item.get('status')}")
    return "\n".join(lines) + "\n"


def _manual_actions_markdown(manual: dict[str, Any]) -> str:
    lines = ["# Manual Governance Actions", ""]
    items = manual.get("items") if isinstance(manual.get("items"), list) else []
    if not items:
        lines.append("- None")
    for item in items:
        if isinstance(item, dict):
            lines.append(f"- {item.get('item_id')} | {item.get('action_type')} | {item.get('release_id') or '-'} | {item.get('instruction')}")
    return "\n".join(lines) + "\n"


def _write_readme(export_dir: Path, queue: dict[str, Any], execution: dict[str, Any]) -> None:
    text = "\n".join(
        [
            "MusicForge Release Portfolio Governance Queue",
            "",
            f"Queue: {queue.get('queue_id')}",
            f"Portfolio: {queue.get('portfolio_id')}",
            f"Status: {execution.get('status')}",
            "",
            "This package contains summary governance actions only. It does not contain Release ZIPs, audio files, credentials, or external submission payloads.",
            "Verify with: python -m song_agent.cli verify-release-portfolio-governance-package governance-queue.zip --strict --json",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(text, encoding="utf-8")


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        entry = path.relative_to(root).as_posix()
        if not _is_safe_entry(entry):
            raise ReleasePortfolioGovernanceStateError(f"Unsafe governance export entry: {entry}")
        entries.append((path, entry))
    return entries


def _is_safe_entry(entry: str) -> bool:
    if "\\" in entry or not entry or entry.startswith("/") or entry.startswith("//"):
        return False
    parts = entry.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return True


def _ensure_within(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved != root_resolved and root_resolved not in target_resolved.parents:
        raise ReleasePortfolioGovernanceStateError("Resolved path escapes the Governance Queue directory.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    return write_json(path, sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS))


def _event_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _validate_queue_id(value: str) -> str:
    if not value.startswith("pgq-") or not value[4:].isdigit():
        raise ReleasePortfolioGovernanceNotFoundError("Invalid Portfolio Governance Queue id.")
    return value


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]
