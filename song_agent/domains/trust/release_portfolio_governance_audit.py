from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore, portfolio_report_integrity_hash, portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance import ReleasePortfolioGovernanceStore, action_plan_integrity_ok, execution_report_integrity_ok, governance_manifest_integrity_hash, governance_manifest_integrity_ok, manual_action_list_integrity_ok, queue_integrity_ok, queue_summary
from song_agent.domains.trust.release_portfolio_governance_archive_verifier import release_portfolio_governance_archive_verification_summary
from song_agent.domains.trust.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore, governance_archive_manifest_hash, governance_archive_manifest_integrity_ok, governance_change_request_hash, governance_change_request_integrity_ok, governance_signoff_hash, governance_signoff_integrity_ok, governance_signoff_summary
from song_agent.domains.trust.release_portfolio_governance_verifier import release_portfolio_governance_verification_summary
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_audit_contracts import AUDIT_ENTRY_HASH_EXCLUDE_KEYS, AUDIT_MANIFEST_HASH_EXCLUDE_KEYS, AUDIT_REPORT_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS, _entry_hash_payload, audit_entry_hash, audit_ledger_hash, audit_ledger_integrity_ok, audit_manifest_integrity_hash, audit_report_integrity_hash


PORTFOLIO_GOVERNANCE_AUDIT_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_AUDIT_EXPORT_SCHEMA_VERSION = 1





DOMAIN_PRIORITY = {
    "portfolio": 10,
    "portfolio_export": 20,
    "governance_queue": 30,
    "governance_verifier": 40,
    "governance_signoff": 50,
    "governance_change_request": 60,
    "governance_archive": 70,
    "governance_audit": 80,
    "anomaly": 90,
}


class ReleasePortfolioGovernanceAuditError(ValueError):
    pass


class ReleasePortfolioGovernanceAuditNotFoundError(ReleasePortfolioGovernanceAuditError):
    pass


class ReleasePortfolioGovernanceAuditStateError(ReleasePortfolioGovernanceAuditError):
    pass


class ReleasePortfolioGovernanceAuditStore:
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        governance_store: ReleasePortfolioGovernanceStore,
        signoff_store: ReleasePortfolioGovernanceSignoffStore,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.governance_store = governance_store
        self.signoff_store = signoff_store
        self.lock = threading.RLock()

    def audit_dir(self, portfolio_id: str) -> Path:
        return self.portfolio_store.portfolio_dir(portfolio_id) / "governance-audit"

    def report_path(self, portfolio_id: str) -> Path:
        return self.audit_dir(portfolio_id) / "portfolio-governance-audit-report.json"

    def ledger_path(self, portfolio_id: str) -> Path:
        return self.audit_dir(portfolio_id) / "portfolio-governance-audit-ledger.jsonl"

    def events_path(self, portfolio_id: str) -> Path:
        return self.audit_dir(portfolio_id) / "portfolio-governance-audit-events.jsonl"

    def export_dir(self, portfolio_id: str) -> Path:
        return self.audit_dir(portfolio_id) / "export"

    def zip_path(self, portfolio_id: str) -> Path:
        return self.audit_dir(portfolio_id) / "portfolio-governance-audit.zip"

    def verification_report_path(self, portfolio_id: str) -> Path:
        return self.audit_dir(portfolio_id) / "portfolio-governance-audit-verification-report.json"

    def read_report(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(portfolio_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)

    def get_report(self, portfolio_id: str) -> dict[str, Any]:
        report = self.read_report(portfolio_id, default={})
        if not report:
            raise ReleasePortfolioGovernanceAuditNotFoundError("Release Portfolio Governance Audit report does not exist.")
        return report

    def read_ledger(self, portfolio_id: str) -> list[dict[str, Any]]:
        path = self.ledger_path(portfolio_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))
        return rows

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None) -> bool:
        report_data = report if isinstance(report, dict) else self.read_report(portfolio_id, default={})
        if not report_data:
            return False
        try:
            _entries, source = self.build_ledger_entries(portfolio_id)
        except Exception:
            return True
        return stable_hash(source) != str(report_data.get("source_hash") or "")

    def refresh(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            now = now or now_iso()
            entries, source = self.build_ledger_entries(portfolio_id)
            ledger_hash = audit_ledger_hash(entries)
            blockers, warnings = self._audit_findings(portfolio_id, entries)
            coverage = _coverage(entries)
            report = {
                "schema_version": PORTFOLIO_GOVERNANCE_AUDIT_SCHEMA_VERSION,
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "source_hash": stable_hash(source),
                "source": source,
                "ledger_hash": ledger_hash,
                "ledger": {
                    "entry_count": len(entries),
                    "ledger_head_hash": entries[-1].get("entry_hash") if entries else None,
                    "chain_status": "passed" if audit_ledger_integrity_ok(entries) else "failed",
                },
                "coverage": coverage,
                "readiness": {
                    "status": "failed" if blockers else "warning" if warnings else "passed",
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "ready_for_external_review": not blockers,
                },
                "summary": {
                    "entry_count": len(entries),
                    "queue_count": coverage.get("queue_count", 0),
                    "signed_queue_count": coverage.get("signed_queue_count", 0),
                    "archive_verified_count": coverage.get("archive_verified_count", 0),
                    "force_signed_count": coverage.get("force_signed_count", 0),
                    "reset_count": coverage.get("reset_count", 0),
                    "applied_change_request_count": coverage.get("applied_change_request_count", 0),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                },
                "queue_summaries": _queue_summaries(entries),
                "change_request_summary": _change_request_summary(entries),
                "archive_summary": _archive_summary(entries),
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = audit_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)
            root = self.audit_dir(portfolio_id)
            root.mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id), report)
            _write_ledger(self.ledger_path(portfolio_id), entries)
            self._append_event(portfolio_id, "refreshed", {"status": report.get("status"), "entry_count": len(entries)}, now=now)
            return report

    def build_ledger_entries(self, portfolio_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        report = self.portfolio_store.read_report(portfolio_id, default={})
        trend = self.portfolio_store.read_trend_report(portfolio_id, default={})
        risks = self.portfolio_store.read_risk_register(portfolio_id, default={})
        source: dict[str, Any] = {"portfolio_id": portfolio_id, "sources": []}
        rows: list[dict[str, Any]] = []

        rows.append(_entry_seed(portfolio_id, "", portfolio.get("created_at"), "portfolio", "portfolio_audit_created", "portfolio", portfolio_id, portfolio, payload_hash=stable_hash(portfolio), integrity_ok=True))
        source["sources"].append({"type": "portfolio", "hash": stable_hash(portfolio)})
        for event in _read_jsonl(self.portfolio_store.events_path(portfolio_id)):
            event_type = f"portfolio_audit_{_slug(event.get('type') or 'event')}"
            rows.append(_entry_seed(portfolio_id, "", event.get("at"), "portfolio", event_type, "portfolio_event", event.get("event_id"), event, payload_hash=stable_hash(event)))

        if report:
            rows.append(_entry_seed(portfolio_id, "", report.get("generated_at"), "portfolio", "portfolio_audit_refreshed", "portfolio_audit_report", "portfolio-audit-report", report, payload_hash=portfolio_report_integrity_hash(report), source_hash=report.get("source_hash"), integrity_ok=portfolio_report_integrity_ok(report), stale=self.portfolio_store.report_is_stale(portfolio_id, report)))
            source["sources"].append({"type": "portfolio_report", "hash": portfolio_report_integrity_hash(report), "source_hash": report.get("source_hash"), "stale": self.portfolio_store.report_is_stale(portfolio_id, report)})
        if trend:
            source["sources"].append({"type": "portfolio_trend", "hash": stable_hash(trend)})
        if risks:
            source["sources"].append({"type": "portfolio_risks", "hash": stable_hash(risks)})
        export_manifest = _read_optional_json(self.portfolio_store.export_dir(portfolio_id) / "manifest.json")
        if export_manifest:
            rows.append(_entry_seed(portfolio_id, "", export_manifest.get("created_at"), "portfolio_export", "portfolio_audit_exported", "portfolio_export", "manifest", export_manifest, payload_hash=export_manifest.get("integrity_hash"), source_hash=export_manifest.get("source_hash")))
        portfolio_verification = _read_optional_json(self.portfolio_store.verification_report_path(portfolio_id))
        if portfolio_verification:
            rows.append(_entry_seed(portfolio_id, "", portfolio_verification.get("generated_at"), "portfolio_export", "portfolio_audit_verified", "portfolio_verifier", "verification-report", portfolio_verification, payload_hash=stable_hash(portfolio_verification), integrity_ok=portfolio_verification.get("status") != "failed"))

        queues = self.governance_store.list_queues(portfolio_id=portfolio_id, include_archived=True)
        for queue in sorted(queues, key=lambda item: str(item.get("created_at") or "")):
            queue_id = str(queue.get("queue_id") or "")
            rows.extend(self._queue_entries(portfolio_id, queue_id, queue))
            source["sources"].append({"type": "governance_queue", "id": queue_id, "hash": queue.get("integrity_hash"), "status": queue.get("status")})

        rows = _finalize_entries(rows)
        _bind_change_request_causal_refs(rows)
        source["ledger_input_hash"] = stable_hash([_entry_hash_payload(item) for item in rows])
        return rows, sanitize_metadata(source, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)

    def _queue_entries(self, portfolio_id: str, queue_id: str, queue: ImplementationDocument) -> list[ImplementationDocument]:
        rows: list[dict[str, Any]] = []
        plan = self.governance_store.read_action_plan(queue_id, default={})
        execution = self.governance_store.read_execution_report(queue_id, default={})
        manual = self.governance_store.read_manual_action_list(queue_id, default={})
        rows.append(_entry_seed(portfolio_id, queue_id, queue.get("created_at"), "governance_queue", "governance_queue_created", "governance_queue", queue_id, queue, payload_hash=queue.get("integrity_hash"), source_hash=queue.get("source_hash"), integrity_ok=queue_integrity_ok(queue), stale=queue.get("status") == "stale", links={"queue_hash": queue.get("integrity_hash"), "action_plan_hash": plan.get("integrity_hash"), "execution_report_hash": execution.get("integrity_hash")}, summary=queue_summary(queue, execution)))
        for event in _read_jsonl(self.governance_store.events_path(queue_id)):
            raw_type = str(event.get("type") or "event")
            event_type = f"governance_queue_{_slug(raw_type)}"
            if raw_type == "governance_signoff_signed":
                event_type = "governance_signoff_signed"
            elif raw_type == "governance_signoff_reset":
                event_type = "governance_signoff_reset"
            rows.append(_entry_seed(portfolio_id, queue_id, event.get("at"), "governance_queue", event_type, "governance_event", event.get("event_id"), event, payload_hash=stable_hash(event)))
        if plan:
            rows.append(_entry_seed(portfolio_id, queue_id, plan.get("generated_at"), "governance_queue", "governance_action_plan_current", "action_plan", queue_id, plan, payload_hash=plan.get("integrity_hash"), integrity_ok=action_plan_integrity_ok(plan)))
        if execution:
            rows.append(_entry_seed(portfolio_id, queue_id, execution.get("generated_at"), "governance_queue", "governance_queue_run_safe_completed", "execution_report", queue_id, execution, payload_hash=execution.get("integrity_hash"), integrity_ok=execution_report_integrity_ok(execution), summary=execution.get("summary") if isinstance(execution.get("summary"), dict) else {}))
        if manual:
            rows.append(_entry_seed(portfolio_id, queue_id, manual.get("generated_at"), "governance_queue", "governance_manual_action_list_current", "manual_action_list", queue_id, manual, payload_hash=manual.get("integrity_hash"), integrity_ok=manual_action_list_integrity_ok(manual)))
        export_manifest = _read_optional_json(self.governance_store.export_dir(queue_id) / "manifest.json")
        if export_manifest:
            rows.append(_entry_seed(portfolio_id, queue_id, export_manifest.get("created_at"), "governance_queue", "governance_queue_exported", "governance_export", queue_id, export_manifest, payload_hash=export_manifest.get("integrity_hash"), source_hash=export_manifest.get("source_hash"), integrity_ok=governance_manifest_integrity_ok(export_manifest)))
        if queue.get("latest_zip_sha256"):
            rows.append(_entry_seed(portfolio_id, queue_id, queue.get("updated_at"), "governance_queue", "governance_queue_zipped", "governance_zip", queue_id, {"sha256": queue.get("latest_zip_sha256")}, payload_hash=queue.get("latest_zip_sha256")))
        verification = _read_optional_json(self.governance_store.verification_report_path(queue_id))
        if verification:
            rows.append(_entry_seed(portfolio_id, queue_id, verification.get("generated_at"), "governance_verifier", "governance_queue_verified", "queue_verifier", queue_id, verification, payload_hash=stable_hash(verification), integrity_ok=verification.get("status") != "failed", links={"queue_verification_report_hash": stable_hash(verification), "queue_zip_sha256": verification.get("zip_sha256"), "queue_export_manifest_hash": verification.get("manifest_hash")}, summary=release_portfolio_governance_verification_summary(verification)))
        signoff = self.signoff_store.read_signoff(queue_id, default={})
        if signoff:
            status = str(signoff.get("status") or "")
            event_type = "governance_signoff_reset" if status == "reset" else "governance_signoff_force_signed" if status == "force_signed" else "governance_signoff_signed"
            causal = [{"type": "change_request", "id": signoff.get("change_request_id")}] if status == "reset" and signoff.get("change_request_id") else []
            rows.append(_entry_seed(portfolio_id, queue_id, signoff.get("reset_at") or signoff.get("signed_at"), "governance_signoff", event_type, "governance_signoff", signoff.get("signoff_id") or status, signoff, payload_hash=signoff.get("integrity_hash") or governance_signoff_hash(signoff), source_hash=(signoff.get("source") if isinstance(signoff.get("source"), dict) else {}).get("current_source_hash"), integrity_ok=governance_signoff_integrity_ok(signoff), stale=self.signoff_store.signoff_summary(queue_id, signoff=signoff).get("stale", False), causal_refs=causal, links={"signoff_hash": signoff.get("integrity_hash"), "queue_verification_report_hash": (signoff.get("evidence") if isinstance(signoff.get("evidence"), dict) else {}).get("queue_verification_report_hash"), "queue_zip_sha256": (signoff.get("evidence") if isinstance(signoff.get("evidence"), dict) else {}).get("queue_zip_sha256")}, summary=governance_signoff_summary(signoff)))
        for event in _read_jsonl(self.signoff_store.history_path(queue_id)):
            summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
            change_request_id = str(summary.get("change_request_id") or "")
            reset_hash = str(summary.get("reset_hash") or "")
            rows.append(_entry_seed(portfolio_id, queue_id, event.get("at"), "governance_signoff", f"governance_signoff_history_{_slug(event.get('type') or 'event')}", "governance_signoff_history", event.get("event_id"), event, payload_hash=reset_hash or stable_hash(event), causal_refs=[{"type": "change_request", "id": change_request_id}] if change_request_id else []))
        for request in self.signoff_store.list_change_requests(queue_id):
            status = str(request.get("status") or "unknown")
            causal = []
            application = request.get("application") if isinstance(request.get("application"), dict) else {}
            if status == "applied" and application.get("applied_signoff_reset_hash"):
                causal = [{"type": "governance_signoff_reset", "payload_hash": application.get("applied_signoff_reset_hash")}]
            rows.append(_entry_seed(portfolio_id, queue_id, request.get("updated_at") or request.get("requested_at"), "governance_change_request", f"governance_change_request_{_slug(status)}", "change_request", request.get("change_request_id"), request, payload_hash=request.get("integrity_hash") or governance_change_request_hash(request), integrity_ok=governance_change_request_integrity_ok(request), causal_refs=causal))
        for event in _read_jsonl(self.signoff_store.change_request_events_path(queue_id)):
            rows.append(_entry_seed(portfolio_id, queue_id, event.get("at"), "governance_change_request", f"governance_change_request_event_{_slug(event.get('type') or 'event')}", "change_request_event", event.get("event_id"), event, payload_hash=stable_hash(event)))
        archive_manifest = _read_optional_json(self.signoff_store.archive_export_dir(queue_id) / "manifest.json")
        if archive_manifest:
            rows.append(_entry_seed(portfolio_id, queue_id, archive_manifest.get("created_at"), "governance_archive", "governance_archive_exported", "governance_archive", queue_id, archive_manifest, payload_hash=archive_manifest.get("integrity_hash") or governance_archive_manifest_hash(archive_manifest), source_hash=archive_manifest.get("source_hash"), integrity_ok=governance_archive_manifest_integrity_ok(archive_manifest), links={"archive_manifest_hash": archive_manifest.get("integrity_hash")}, summary=archive_manifest.get("summary") if isinstance(archive_manifest.get("summary"), dict) else {}))
        archive_zip_path = self.signoff_store.archive_zip_path(queue_id)
        if archive_zip_path.exists():
            rows.append(_entry_seed(portfolio_id, queue_id, queue.get("updated_at"), "governance_archive", "governance_archive_zipped", "governance_archive_zip", queue_id, {"sha256": _sha256(archive_zip_path), "size_bytes": archive_zip_path.stat().st_size}, payload_hash=_sha256(archive_zip_path)))
        archive_verification = _read_optional_json(self.signoff_store.archive_verification_report_path(queue_id))
        if archive_verification:
            rows.append(_entry_seed(portfolio_id, queue_id, archive_verification.get("generated_at"), "governance_archive", "governance_archive_verified", "governance_archive_verifier", queue_id, archive_verification, payload_hash=stable_hash(archive_verification), integrity_ok=archive_verification.get("status") != "failed", summary=release_portfolio_governance_archive_verification_summary(archive_verification)))
        return rows

    def export_audit(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(portfolio_id, default={}) or self.refresh(portfolio_id, now=now)
            if self.report_is_stale(portfolio_id, report):
                raise ReleasePortfolioGovernanceAuditStateError("Portfolio Governance Audit report is stale. Refresh before export.")
            if not audit_report_integrity_ok(report):
                raise ReleasePortfolioGovernanceAuditStateError("Portfolio Governance Audit report integrity failed. Refresh before export.")
            entries = self.read_ledger(portfolio_id)
            if not audit_ledger_integrity_ok(entries):
                raise ReleasePortfolioGovernanceAuditStateError("Portfolio Governance Audit ledger chain failed. Refresh before export.")
            export_dir = self.export_dir(portfolio_id).resolve()
            portfolio_dir = self.portfolio_store.portfolio_dir(portfolio_id).resolve()
            _ensure_within(portfolio_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "portfolio-governance-audit-ledger.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries), encoding="utf-8")
            _write_json(export_dir / "portfolio-governance-audit-report.json", report)
            _write_json(export_dir / "portfolio-summary.json", _portfolio_summary(self.portfolio_store.get_portfolio(portfolio_id), self.portfolio_store.read_report(portfolio_id, default={})))
            _write_json(export_dir / "queue-summaries.json", {"items": report.get("queue_summaries", []), "count": len(report.get("queue_summaries", []) if isinstance(report.get("queue_summaries"), list) else [])})
            _write_json(export_dir / "signoff-summaries.json", {"items": [item for item in report.get("queue_summaries", []) if isinstance(item, dict) and item.get("signoff_status")], "count": report.get("coverage", {}).get("signed_queue_count") if isinstance(report.get("coverage"), dict) else 0})
            _write_json(export_dir / "archive-verification-summaries.json", report.get("archive_summary", {}))
            _write_json(export_dir / "change-request-ledger.json", report.get("change_request_summary", {}))
            _write_markdown(export_dir, report)
            _write_readme(export_dir, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": PORTFOLIO_GOVERNANCE_AUDIT_EXPORT_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_audit",
                "tool": {"name": "MusicForge Release Portfolio Governance Audit", "version": __version__},
                "portfolio_id": portfolio_id,
                "created_at": now,
                "app_version": __version__,
                "source_hash": report.get("source_hash"),
                "ledger_hash": report.get("ledger_hash"),
                "summary": {"status": report.get("status"), **(report.get("summary") if isinstance(report.get("summary"), dict) else {})},
                "audit_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash"), "ledger_hash": report.get("ledger_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "entries": entries}),
            }
            manifest["integrity_hash"] = audit_manifest_integrity_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            self._append_event(portfolio_id, "exported", {"status": report.get("status"), "entry_count": len(entries)}, now=now)
            return sanitize_metadata(manifest, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(portfolio_id).resolve()
            portfolio_dir = self.portfolio_store.portfolio_dir(portfolio_id).resolve()
            zip_path = self.zip_path(portfolio_id).resolve()
            _ensure_within(portfolio_dir, export_dir)
            _ensure_within(portfolio_dir, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_audit(portfolio_id, now=now)
            report = self.read_report(portfolio_id, default={})
            if self.report_is_stale(portfolio_id, report):
                raise ReleasePortfolioGovernanceAuditStateError("Portfolio Governance Audit report is stale. Refresh before ZIP export.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = audit_manifest_integrity_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
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
            return sanitize_metadata({"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)

    def read_export_manifest(self, portfolio_id: str) -> dict[str, Any]:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceAuditNotFoundError("Portfolio Governance Audit export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)

    def summary(self, portfolio_id: str) -> dict[str, Any]:
        report = self.read_report(portfolio_id, default={})
        if not report:
            return {"status": "missing", "entry_count": 0, "integrity_ok": False}
        summary = audit_summary(report)
        summary["stale"] = self.report_is_stale(portfolio_id, report)
        return summary

    def _audit_findings(self, portfolio_id: str, entries: list[ImplementationDocument]) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        if not audit_ledger_integrity_ok(entries):
            blockers.append(_blocker("portfolio_governance_audit_ledger_chain", "Portfolio Governance Audit ledger hash chain failed."))
        portfolio_report = self.portfolio_store.read_report(portfolio_id, default={})
        if not portfolio_report:
            blockers.append(_blocker("portfolio_report_missing", "Portfolio Audit report is missing."))
        elif not portfolio_report_integrity_ok(portfolio_report):
            blockers.append(_blocker("portfolio_report_integrity", "Portfolio Audit report integrity failed."))
        queue_ids = {str(item.get("queue_id") or "") for item in entries if item.get("domain") == "governance_queue" and str(item.get("queue_id") or "")}
        for queue_id in sorted(queue_ids):
            queue = self.governance_store.get_queue(queue_id)
            signoff = self.signoff_store.read_signoff(queue_id, default={})
            verification = _read_optional_json(self.governance_store.verification_report_path(queue_id))
            archive_manifest = _read_optional_json(self.signoff_store.archive_export_dir(queue_id) / "manifest.json")
            archive_verification = _read_optional_json(self.signoff_store.archive_verification_report_path(queue_id))
            if not queue_integrity_ok(queue):
                blockers.append(_blocker("queue_integrity", f"Governance Queue {queue_id} integrity failed."))
            if signoff and not governance_signoff_integrity_ok(signoff):
                blockers.append(_blocker("governance_signoff_integrity", f"Governance Signoff {queue_id} integrity failed."))
            if signoff.get("status") in {"signed", "force_signed"}:
                if not verification:
                    blockers.append(_blocker("queue_verification_missing", f"Signed Governance Queue {queue_id} is missing queue verification report."))
                elif verification.get("status") == "failed":
                    blockers.append(_blocker("queue_verification_failed", f"Governance Queue {queue_id} verification failed."))
                elif (signoff.get("evidence") if isinstance(signoff.get("evidence"), dict) else {}).get("queue_verification_report_hash") != stable_hash(verification):
                    blockers.append(_blocker("queue_verification_signoff_hash", f"Governance Queue {queue_id} signoff does not match queue verification report."))
                if not archive_manifest:
                    blockers.append(_blocker("governance_archive_missing", f"Signed Governance Queue {queue_id} is missing Governance Archive export."))
                elif not governance_archive_manifest_integrity_ok(archive_manifest):
                    blockers.append(_blocker("governance_archive_manifest_integrity", f"Governance Archive {queue_id} manifest integrity failed."))
                if not archive_verification:
                    blockers.append(_blocker("governance_archive_verification_missing", f"Signed Governance Queue {queue_id} is missing Governance Archive verification report."))
                elif archive_verification.get("status") == "failed":
                    blockers.append(_blocker("governance_archive_verification_failed", f"Governance Archive {queue_id} verification failed."))
                elif not archive_verification.get("zip_sha256"):
                    blockers.append(_blocker("governance_archive_verification_zip_sha256_missing", f"Governance Archive {queue_id} verification report is missing archive ZIP sha256."))
                elif not self.signoff_store.archive_zip_path(queue_id).exists():
                    blockers.append(_blocker("governance_archive_zip_missing", f"Signed Governance Queue {queue_id} is missing current Governance Archive ZIP."))
                elif str(archive_verification.get("zip_sha256") or "") != _sha256(self.signoff_store.archive_zip_path(queue_id)):
                    blockers.append(_blocker("governance_archive_verification_zip_sha256", f"Governance Archive {queue_id} verification report does not match current archive ZIP."))
                elif not archive_verification.get("manifest_hash"):
                    blockers.append(_blocker("governance_archive_verification_manifest_hash_missing", f"Governance Archive {queue_id} verification report is missing archive manifest hash."))
                elif archive_manifest and str(archive_verification.get("manifest_hash") or "") != str(archive_manifest.get("integrity_hash") or ""):
                    blockers.append(_blocker("governance_archive_verification_manifest_hash", f"Governance Archive {queue_id} verification report does not match current archive manifest."))
                if signoff.get("status") == "force_signed":
                    reason = str(signoff.get("override_reason") or "").strip()
                    if not reason:
                        blockers.append(_blocker("force_signoff_reason_missing", f"Force signed Governance Queue {queue_id} is missing override reason."))
                    else:
                        warnings.append(_warning("force_signoff_present", f"Governance Queue {queue_id} was force signed."))
            if signoff.get("status") == "reset":
                change_request_id = str(signoff.get("change_request_id") or "")
                if not change_request_id:
                    blockers.append(_blocker("reset_change_request_missing", f"Governance Signoff reset for {queue_id} is missing Change Request id."))
                else:
                    try:
                        request = self.signoff_store.get_change_request(queue_id, change_request_id)
                    except Exception:
                        request = {}
                    application = request.get("application") if isinstance(request.get("application"), dict) else {}
                    if request.get("status") != "applied":
                        blockers.append(_blocker("reset_change_request_not_applied", f"Governance reset for {queue_id} requires applied Change Request."))
                    elif not governance_change_request_integrity_ok(request):
                        blockers.append(_blocker("change_request_integrity", f"Governance Change Request {change_request_id} integrity failed."))
                    elif str(application.get("applied_signoff_reset_hash") or "") != str(signoff.get("integrity_hash") or ""):
                        blockers.append(_blocker("reset_change_request_hash", f"Governance reset for {queue_id} is not bound to applied Change Request."))
        if _redaction_summary({"entries": entries}).get("status") == "failed":
            blockers.append(_blocker("portfolio_governance_audit_redaction", "Portfolio Governance Audit contains sensitive values."))
        return blockers, warnings

    def _append_event(self, portfolio_id: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.events_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgaevt-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")














def audit_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == audit_report_integrity_hash(data)





def audit_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == audit_manifest_integrity_hash(data)


def audit_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "portfolio_id": data.get("portfolio_id"),
            "entry_count": summary.get("entry_count", 0),
            "queue_count": summary.get("queue_count", 0),
            "signed_queue_count": summary.get("signed_queue_count", 0),
            "archive_verified_count": summary.get("archive_verified_count", 0),
            "ledger_hash": data.get("ledger_hash"),
            "source_hash": data.get("source_hash"),
            "integrity_ok": audit_report_integrity_ok(data),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS,
    )


def _entry_seed(
    portfolio_id: str,
    queue_id: str,
    occurred_at: Any,
    domain: str,
    event_type: str,
    source_kind: str,
    source_id: Any,
    payload: Any,
    *,
    payload_hash: Any = None,
    source_hash: Any = None,
    integrity_ok: bool = True,
    stale: bool = False,
    causal_refs: list[ImplementationDocument] | None = None,
    links: ImplementationDocument | None = None,
    summary: ImplementationDocument | None = None,
) -> ImplementationDocument:
    payload_hash = str(payload_hash or stable_hash(payload))
    return {
        "schema_version": PORTFOLIO_GOVERNANCE_AUDIT_SCHEMA_VERSION,
        "entry_id": "",
        "portfolio_id": portfolio_id,
        "queue_id": queue_id or None,
        "sequence": 0,
        "event_at": _safe_time(occurred_at),
        "domain": domain,
        "event_type": _safe_event_type(event_type),
        "source": {"kind": source_kind, "id": str(source_id or source_kind), "payload_hash": payload_hash},
        "links": links or {},
        "summary": summary or {},
        "source_hash": source_hash,
        "integrity_ok": bool(integrity_ok),
        "stale": bool(stale),
        "causal_refs": causal_refs or [],
        "warnings": [] if occurred_at else [{"check_id": "event_at_missing", "message": "Source event time is missing."}],
        "previous_entry_hash": "",
        "entry_hash": "",
    }


def _finalize_entries(rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    sorted_rows = sorted(rows, key=lambda item: (_safe_time(item.get("event_at")), DOMAIN_PRIORITY.get(str(item.get("domain") or ""), 999), str(item.get("event_type") or ""), str(item.get("queue_id") or ""), str((item.get("source") or {}).get("kind") or ""), str((item.get("source") or {}).get("payload_hash") or "")))
    previous = ""
    result: list[dict[str, Any]] = []
    for index, item in enumerate(sorted_rows, start=1):
        entry = dict(item)
        entry["entry_id"] = f"pgal-{index:06d}"
        entry["sequence"] = index
        entry["previous_entry_hash"] = previous
        entry["entry_hash"] = audit_entry_hash(entry)
        previous = entry["entry_hash"]
        result.append(sanitize_metadata(entry, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))
    return result


def _bind_change_request_causal_refs(entries: list[ImplementationDocument]) -> None:
    applied_by_id: dict[str, dict[str, Any]] = {}
    applied_by_reset_hash: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.get("event_type") != "governance_change_request_applied":
            continue
        source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
        request_id = str(source.get("id") or "")
        if request_id:
            applied_by_id[request_id] = entry
        for ref in entry.get("causal_refs", []) if isinstance(entry.get("causal_refs"), list) else []:
            if isinstance(ref, dict) and ref.get("payload_hash"):
                applied_by_reset_hash[str(ref.get("payload_hash"))] = entry
    changed = False
    for entry in entries:
        if entry.get("event_type") not in {"governance_signoff_reset", "governance_signoff_history_reset", "governance_queue_governance_signoff_reset"}:
            continue
        refs = entry.get("causal_refs") if isinstance(entry.get("causal_refs"), list) else []
        request_id = ""
        for ref in refs:
            if isinstance(ref, dict) and ref.get("type") == "change_request" and ref.get("id"):
                request_id = str(ref.get("id"))
                break
        reset_hash = str((entry.get("source") if isinstance(entry.get("source"), dict) else {}).get("payload_hash") or "")
        applied = applied_by_id.get(request_id) or applied_by_reset_hash.get(reset_hash)
        if not applied:
            continue
        entry["causal_refs"] = [{"type": "change_request", "id": request_id or (applied.get("source") or {}).get("id"), "entry_id": applied.get("entry_id"), "payload_hash": (applied.get("source") or {}).get("payload_hash")}]
        changed = True
    if changed:
        previous = ""
        for entry in entries:
            entry["previous_entry_hash"] = previous
            entry["entry_hash"] = audit_entry_hash(entry)
            previous = entry["entry_hash"]





def _write_ledger(path: Path, entries: list[ImplementationDocument]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries), encoding="utf-8")
    return path


def _coverage(entries: list[ImplementationDocument]) -> ImplementationDocument:
    queue_ids = sorted({str(item.get("queue_id") or "") for item in entries if item.get("queue_id")})
    signed = [item for item in entries if item.get("event_type") in {"governance_signoff_signed", "governance_signoff_force_signed"}]
    archives = [item for item in entries if item.get("event_type") == "governance_archive_verified"]
    stale = [item for item in entries if item.get("stale")]
    failed = [item for item in entries if item.get("integrity_ok") is False]
    return {
        "queue_count": len(queue_ids),
        "signed_queue_count": len({str(item.get("queue_id")) for item in signed if item.get("queue_id")}),
        "archive_verified_count": len({str(item.get("queue_id")) for item in archives if item.get("queue_id")}),
        "force_signed_count": sum(1 for item in entries if item.get("event_type") == "governance_signoff_force_signed"),
        "reset_count": sum(1 for item in entries if item.get("event_type") in {"governance_signoff_reset", "governance_signoff_history_reset"}),
        "applied_change_request_count": sum(1 for item in entries if item.get("event_type") == "governance_change_request_applied"),
        "stale_queue_count": len({str(item.get("queue_id")) for item in stale if item.get("queue_id")}),
        "failed_verification_count": sum(1 for item in failed if str(item.get("event_type") or "").endswith("_verified")),
    }


def _queue_summaries(entries: list[ImplementationDocument]) -> list[ImplementationDocument]:
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        queue_id = str(entry.get("queue_id") or "")
        if not queue_id:
            continue
        row = result.setdefault(queue_id, {"queue_id": queue_id, "events": 0})
        row["events"] += 1
        if entry.get("event_type") == "governance_queue_created":
            row["queue_status"] = (entry.get("summary") or {}).get("status")
        if entry.get("event_type") in {"governance_signoff_signed", "governance_signoff_force_signed", "governance_signoff_reset"}:
            row["signoff_status"] = (entry.get("summary") or {}).get("status") or entry.get("event_type")
            row["signoff_hash"] = (entry.get("source") or {}).get("payload_hash")
        if entry.get("event_type") == "governance_archive_verified":
            row["archive_verification_status"] = (entry.get("summary") or {}).get("status")
    return sorted(result.values(), key=lambda item: str(item.get("queue_id") or ""))


def _change_request_summary(entries: list[ImplementationDocument]) -> ImplementationDocument:
    counts: dict[str, int] = {}
    rows = []
    for entry in entries:
        if entry.get("domain") != "governance_change_request":
            continue
        event_type = str(entry.get("event_type") or "")
        status = event_type.removeprefix("governance_change_request_")
        counts[status] = counts.get(status, 0) + 1
        rows.append(entry)
    return {"count": len(rows), "status_counts": counts, "items": rows[:100]}


def _archive_summary(entries: list[ImplementationDocument]) -> ImplementationDocument:
    rows = [item for item in entries if item.get("domain") == "governance_archive"]
    return {"count": len(rows), "exported_count": sum(1 for item in rows if item.get("event_type") == "governance_archive_exported"), "verified_count": sum(1 for item in rows if item.get("event_type") == "governance_archive_verified"), "items": rows[:100]}


def _portfolio_summary(portfolio: ImplementationDocument, report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"portfolio_id": portfolio.get("portfolio_id"), "name": portfolio.get("name"), "status": report.get("status") or portfolio.get("status"), "source_hash": report.get("source_hash"), "release_count": summary.get("release_count", 0), "integrity_hash": report.get("integrity_hash")}


def _write_markdown(export_dir: Path, report: ImplementationDocument) -> None:
    coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
    lines = [
        "# Portfolio Governance Audit",
        "",
        f"Portfolio: {report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        f"Ledger: {report.get('ledger_hash')}",
        f"Queues: {coverage.get('queue_count', 0)}",
        f"Signed Queues: {coverage.get('signed_queue_count', 0)}",
        f"Verified Archives: {coverage.get('archive_verified_count', 0)}",
    ]
    (export_dir / "GOVERNANCE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(export_dir: Path, report: ImplementationDocument) -> None:
    lines = [
        "MusicForge Release Portfolio Governance Audit Package",
        "",
        f"Portfolio ID: {report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        f"Ledger Hash: {report.get('ledger_hash') or '-'}",
        "",
        "This package contains summary governance audit evidence only. It does not include credentials, platform accounts, audio, or artwork.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, value: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleasePortfolioGovernanceAuditStateError(f"Duplicate Portfolio Governance Audit ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceAuditStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceAuditStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceAuditStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAuditStateError("Refusing to operate outside Portfolio Governance Audit boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))
    return rows


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _safe_time(value: Any) -> str:
    text = str(value or "").strip()
    return text or "1970-01-01T00:00:00+00:00"


def _safe_event_type(value: Any) -> str:
    return _slug(str(value or "unknown")) or "unknown"


def _slug(value: Any) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch == "_").strip("_")


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
