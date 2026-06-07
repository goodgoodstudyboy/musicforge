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
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore, portfolio_report_integrity_hash, portfolio_report_integrity_ok
from song_agent.release_portfolio_governance_audit import (
    ReleasePortfolioGovernanceAuditStore,
    audit_ledger_hash,
    audit_ledger_integrity_ok,
    audit_report_integrity_hash,
    audit_report_integrity_ok,
    audit_summary,
)
from song_agent.release_portfolio_governance_reviewer_pack import (
    ReleasePortfolioGovernanceReviewerPackStore,
    reviewer_report_integrity_hash,
    reviewer_report_integrity_ok,
    reviewer_pack_summary,
)
from song_agent.releases import stable_hash


FINAL_BOARD_SCHEMA_VERSION = 1
FINAL_BOARD_ARCHIVE_SCHEMA_VERSION = 1
FINAL_BOARD_CHANGE_REQUEST_SCHEMA_VERSION = 1
FINAL_BOARD_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}
FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}
FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS = {"integrity_hash", "imported_at", "updated_at"}
FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}
FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}
SIGNED_STATUSES = {"signed", "force_signed"}
RESPONSE_DECISIONS = {"accepted", "accepted_with_notes", "needs_changes", "rejected"}
RESPONSE_BLOCKED_KEYS = {"source_path", "local_path", "file_path", "raw_file", "token", "api_key", "access_token", "authorization", "secret"}


class ReleasePortfolioGovernanceFinalBoardError(ValueError):
    pass


class ReleasePortfolioGovernanceFinalBoardNotFoundError(ReleasePortfolioGovernanceFinalBoardError):
    pass


class ReleasePortfolioGovernanceFinalBoardStateError(ReleasePortfolioGovernanceFinalBoardError):
    pass


class ReleasePortfolioGovernanceFinalBoardStore:
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        audit_store: ReleasePortfolioGovernanceAuditStore,
        reviewer_pack_store: ReleasePortfolioGovernanceReviewerPackStore,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.audit_store = audit_store
        self.reviewer_pack_store = reviewer_pack_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str) -> Path:
        return self.portfolio_store.portfolio_dir(portfolio_id) / "governance-final-board"

    def report_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "final-board-report.json"

    def signoff_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "final-board-signoff.json"

    def history_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "final-board-history.jsonl"

    def responses_root(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "reviewer-responses"

    def response_path(self, portfolio_id: str, response_id: str) -> Path:
        return self.responses_root(portfolio_id) / f"{_validate_id(response_id, 'fbr')}.json"

    def change_requests_root(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "change-requests"

    def change_request_path(self, portfolio_id: str, change_request_id: str) -> Path:
        return self.change_requests_root(portfolio_id) / f"{_validate_id(change_request_id, 'fcr')}.json"

    def change_request_events_path(self, portfolio_id: str) -> Path:
        return self.change_requests_root(portfolio_id) / "events.jsonl"

    def export_dir(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "export"

    def archive_zip_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "portfolio-governance-final-board-archive.zip"

    def verification_report_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "verification-report.json"

    def read_report(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id), default=default)

    def read_signoff(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.signoff_path(portfolio_id), default=default)

    def get_signoff(self, portfolio_id: str) -> dict[str, Any]:
        signoff = self.read_signoff(portfolio_id, default={})
        if not signoff:
            raise ReleasePortfolioGovernanceFinalBoardNotFoundError("Portfolio Governance Final Board Signoff does not exist.")
        return signoff

    def read_export_manifest(self, portfolio_id: str) -> dict[str, Any]:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceFinalBoardNotFoundError("Portfolio Governance Final Board Archive export has not been generated.")
        return _read_json_default(path, default={})

    def refresh_report(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            self.portfolio_store.get_portfolio(portfolio_id)
            responses = self.list_reviewer_responses(portfolio_id)
            source = self._source_with_responses(portfolio_id, responses)
            blockers, warnings, gates = self._final_board_findings(portfolio_id, source, responses, payload)
            summary = _summary_from_source(source, responses, blockers, warnings)
            status = "failed" if blockers else "warning" if warnings else "passed"
            report = {
                "schema_version": FINAL_BOARD_SCHEMA_VERSION,
                "report_id": self._reserve_report_id(portfolio_id),
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "status": status,
                "readiness": "blocked" if blockers else "requires_review" if warnings else "ready_for_final_signoff",
                "source_hash": stable_hash(source),
                "source": source,
                "summary": summary,
                "gates": gates,
                "reviewer_responses": [_response_summary(item) for item in responses],
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = final_board_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)
            self.root_dir(portfolio_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id), report)
            self._append_history(portfolio_id, "report_refreshed", {"status": status, "report_id": report["report_id"]}, now=now)
            return report

    def build_source(self, portfolio_id: str) -> dict[str, Any]:
        portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        portfolio_report = self.portfolio_store.read_report(portfolio_id, default={})
        governance_audit_report = self.audit_store.read_report(portfolio_id, default={})
        governance_ledger = self.audit_store.read_ledger(portfolio_id)
        audit_verification = _read_json_default(self.audit_store.verification_report_path(portfolio_id), default={})
        audit_manifest = _read_json_default(self.audit_store.export_dir(portfolio_id) / "manifest.json", default={})
        reviewer_report = self.reviewer_pack_store.read_report(portfolio_id, default={})
        reviewer_verification = _read_json_default(self.reviewer_pack_store.verification_report_path(portfolio_id), default={})
        reviewer_manifest = _read_json_default(self.reviewer_pack_store.export_dir(portfolio_id) / "manifest.json", default={})
        reviewer_zip_path = self.reviewer_pack_store.zip_path(portfolio_id)
        audit_zip_path = self.audit_store.zip_path(portfolio_id)
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "portfolio_hash": stable_hash(portfolio),
                "portfolio_report_hash": portfolio_report_integrity_hash(portfolio_report) if portfolio_report else None,
                "portfolio_report_integrity_hash": portfolio_report.get("integrity_hash") if portfolio_report else None,
                "portfolio_report_integrity_ok": portfolio_report_integrity_ok(portfolio_report) if portfolio_report else False,
                "portfolio_report_stale": self.portfolio_store.report_is_stale(portfolio_id, portfolio_report) if portfolio_report else False,
                "governance_audit_report_hash": audit_report_integrity_hash(governance_audit_report) if governance_audit_report else None,
                "governance_audit_report_integrity_hash": governance_audit_report.get("integrity_hash") if governance_audit_report else None,
                "governance_audit_report_integrity_ok": audit_report_integrity_ok(governance_audit_report) if governance_audit_report else False,
                "governance_audit_report_stale": self.audit_store.report_is_stale(portfolio_id, governance_audit_report) if governance_audit_report else False,
                "governance_audit_report_status": governance_audit_report.get("status") if governance_audit_report else "missing",
                "governance_audit_ledger_hash": audit_ledger_hash(governance_ledger) if governance_ledger else None,
                "governance_audit_ledger_integrity_ok": audit_ledger_integrity_ok(governance_ledger) if governance_ledger else False,
                "governance_audit_verification_hash": stable_hash(audit_verification) if audit_verification else None,
                "governance_audit_verification_status": audit_verification.get("status") if audit_verification else "missing",
                "governance_audit_verification_zip_sha256": audit_verification.get("zip_sha256") if audit_verification else None,
                "governance_audit_verification_zip_size_bytes": audit_verification.get("zip_size_bytes") if audit_verification else None,
                "governance_audit_verification_manifest_hash": audit_verification.get("manifest_hash") if audit_verification else None,
                "governance_audit_zip_exists": audit_zip_path.exists(),
                "governance_audit_zip_sha256": _sha256(audit_zip_path) if audit_zip_path.exists() else None,
                "governance_audit_zip_size_bytes": audit_zip_path.stat().st_size if audit_zip_path.exists() else None,
                "governance_audit_export_manifest_hash": audit_manifest.get("integrity_hash") if audit_manifest else None,
                "governance_reviewer_report_hash": reviewer_report_integrity_hash(reviewer_report) if reviewer_report else None,
                "governance_reviewer_report_integrity_hash": reviewer_report.get("integrity_hash") if reviewer_report else None,
                "governance_reviewer_report_integrity_ok": reviewer_report_integrity_ok(reviewer_report) if reviewer_report else False,
                "governance_reviewer_report_stale": self.reviewer_pack_store.report_is_stale(portfolio_id, reviewer_report) if reviewer_report else False,
                "governance_reviewer_report_status": reviewer_report.get("status") if reviewer_report else "missing",
                "governance_reviewer_pack_verification_hash": stable_hash(reviewer_verification) if reviewer_verification else None,
                "governance_reviewer_pack_verification_status": reviewer_verification.get("status") if reviewer_verification else "missing",
                "governance_reviewer_pack_verification_zip_sha256": reviewer_verification.get("zip_sha256") if reviewer_verification else None,
                "governance_reviewer_pack_verification_zip_size_bytes": reviewer_verification.get("zip_size_bytes") if reviewer_verification else None,
                "governance_reviewer_pack_zip_exists": reviewer_zip_path.exists(),
                "governance_reviewer_pack_zip_sha256": _sha256(reviewer_zip_path) if reviewer_zip_path.exists() else None,
                "governance_reviewer_pack_zip_size_bytes": reviewer_zip_path.stat().st_size if reviewer_zip_path.exists() else None,
                "governance_reviewer_pack_manifest_hash": reviewer_manifest.get("integrity_hash") if reviewer_manifest else None,
                "queue_count": int((governance_audit_report.get("coverage") if isinstance(governance_audit_report.get("coverage"), dict) else {}).get("queue_count") or 0),
                "signed_queue_count": int((governance_audit_report.get("coverage") if isinstance(governance_audit_report.get("coverage"), dict) else {}).get("signed_queue_count") or 0),
                "archive_verified_count": int((governance_audit_report.get("coverage") if isinstance(governance_audit_report.get("coverage"), dict) else {}).get("archive_verified_count") or 0),
                "force_signed_queue_count": int((governance_audit_report.get("coverage") if isinstance(governance_audit_report.get("coverage"), dict) else {}).get("force_signed_count") or 0),
                "reset_count": int((governance_audit_report.get("coverage") if isinstance(governance_audit_report.get("coverage"), dict) else {}).get("reset_count") or 0),
                "applied_change_request_count": int((governance_audit_report.get("coverage") if isinstance(governance_audit_report.get("coverage"), dict) else {}).get("applied_change_request_count") or 0),
            },
            blocked_keys=FINAL_BOARD_BLOCKED_KEYS,
        )

    def _source_with_responses(self, portfolio_id: str, responses: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        rows = responses if responses is not None else self.list_reviewer_responses(portfolio_id)
        source = self.build_source(portfolio_id)
        source["reviewer_responses_hash"] = stable_hash([item.get("integrity_hash") for item in rows])
        source["reviewer_response_count"] = len(rows)
        source["reviewer_response_status"] = _reviewer_response_status(rows, source)
        return sanitize_metadata(source, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None) -> bool:
        data = report if isinstance(report, dict) else self.read_report(portfolio_id, default={})
        if not data:
            return False
        try:
            return stable_hash(self._source_with_responses(portfolio_id)) != str(data.get("source_hash") or "")
        except Exception:
            return True

    def import_reviewer_response(self, portfolio_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ReleasePortfolioGovernanceFinalBoardStateError("Reviewer response payload must be a JSON object.")
        _reject_forbidden_keys(payload)
        with self.lock:
            now = now or now_iso()
            self.portfolio_store.get_portfolio(portfolio_id)
            if self.signoff_summary(portfolio_id).get("status") in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board is signed. Reset signoff before importing reviewer responses.")
            source = self.build_source(portfolio_id)
            decision = str(payload.get("decision") or "").strip()
            if decision not in RESPONSE_DECISIONS:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Reviewer response decision must be accepted, accepted_with_notes, needs_changes, or rejected.")
            response_id = self._reserve_response_id(portfolio_id)
            response = {
                "schema_version": FINAL_BOARD_SCHEMA_VERSION,
                "response_id": response_id,
                "portfolio_id": portfolio_id,
                "imported_at": now,
                "reviewer": sanitize_metadata(payload.get("reviewer") if isinstance(payload.get("reviewer"), dict) else {}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS),
                "source": {
                    "reviewer_pack_source_hash": source.get("governance_reviewer_report_hash"),
                    "reviewer_pack_zip_sha256": source.get("governance_reviewer_pack_zip_sha256"),
                    "reviewer_pack_verification_hash": source.get("governance_reviewer_pack_verification_hash"),
                },
                "decision": decision,
                "findings": _sanitize_findings(payload.get("findings")),
                "notes": sanitize_sensitive_text(str(payload.get("notes") or "").strip())[:2000],
            }
            response["integrity_hash"] = final_board_response_integrity_hash(response)
            self.responses_root(portfolio_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.response_path(portfolio_id, response_id), response)
            self._append_history(portfolio_id, "reviewer_response_imported", {"response_id": response_id, "decision": decision}, now=now)
            return response

    def list_reviewer_responses(self, portfolio_id: str) -> list[dict[str, Any]]:
        root = self.responses_root(portfolio_id)
        if not root.exists():
            return []
        rows = [_read_json_default(path, default={}) for path in sorted(root.glob("fbr-*.json"))]
        return sorted([item for item in rows if item], key=lambda item: str(item.get("imported_at") or ""), reverse=True)

    def signoff(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            existing = self.read_signoff(portfolio_id, default={})
            if final_board_signoff_summary(existing).get("status") in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board is already signed. Reset before signing again.")
            report = self.read_report(portfolio_id, default={}) or self.refresh_report(portfolio_id, now=now)
            if self.report_is_stale(portfolio_id, report):
                report = self.refresh_report(portfolio_id, now=now)
            if not final_board_report_integrity_ok(report):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Report integrity failed. Refresh before signoff.")
            force = bool(payload.get("force", False))
            override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "").strip())
            blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
            warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
            if blockers:
                detail = str((blockers[0] if isinstance(blockers[0], dict) else {}).get("message") or "Final Board gate failed.")
                raise ReleasePortfolioGovernanceFinalBoardStateError(f"Final Board Signoff gate failed: {detail}")
            if warnings and not force and not bool(payload.get("allow_warning_signoff", False)):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Report has warnings. Use force with override_reason or allow_warning_signoff.")
            if force and len(override_reason) < 20:
                raise ReleasePortfolioGovernanceFinalBoardStateError("override_reason must be at least 20 characters for force Final Board Signoff.")
            status = "force_signed" if force and warnings else "signed"
            source = report.get("source") if isinstance(report.get("source"), dict) else {}
            signoff = {
                "schema_version": FINAL_BOARD_SCHEMA_VERSION,
                "signoff_id": self._reserve_signoff_id(portfolio_id),
                "portfolio_id": portfolio_id,
                "status": status,
                "signed_at": now,
                "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
                "role": _safe_text(payload.get("role"), 120) or "portfolio_governance_owner",
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Portfolio governance evidence reviewed.").strip())[:1000],
                "force": status == "force_signed",
                "override_reason": override_reason or None,
                "source": {
                    "final_board_report_hash": report.get("integrity_hash"),
                    "final_board_report_source_hash": report.get("source_hash"),
                    "reviewer_pack_verification_hash": source.get("governance_reviewer_pack_verification_hash"),
                    "reviewer_pack_zip_sha256": source.get("governance_reviewer_pack_zip_sha256"),
                    "governance_audit_verification_hash": source.get("governance_audit_verification_hash"),
                    "governance_audit_zip_sha256": source.get("governance_audit_zip_sha256"),
                },
                "evidence": {
                    "report_status": report.get("status"),
                    "gate_status": "passed" if not blockers else "failed",
                    "reviewer_response_status": _reviewer_response_status(self.list_reviewer_responses(portfolio_id), source),
                    "archive_coverage_status": "passed" if int(source.get("archive_verified_count") or 0) >= int(source.get("signed_queue_count") or 0) and int(source.get("signed_queue_count") or 0) > 0 else "failed",
                    "warning_count": len(warnings),
                },
            }
            signoff["integrity_hash"] = final_board_signoff_hash(signoff)
            _write_json(self.signoff_path(portfolio_id), signoff)
            self._append_history(portfolio_id, "signed", {"status": status, "signoff_id": signoff["signoff_id"]}, now=now)
            return signoff

    def reset_signoff(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleasePortfolioGovernanceFinalBoardStateError("reason must be at least 8 characters.")
        change_request_id = str(payload.get("change_request_id") or "").strip()
        if not change_request_id:
            raise ReleasePortfolioGovernanceFinalBoardStateError("approved Final Board Change Request is required before reset.")
        with self.lock:
            now = now or now_iso()
            request = self.get_change_request(portfolio_id, change_request_id)
            if not final_board_change_request_integrity_ok(request):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Change Request integrity failed.")
            if request.get("status") != "approved":
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Change Request must be approved before reset.")
            existing = self.read_signoff(portfolio_id, default={})
            reset = {
                "schema_version": FINAL_BOARD_SCHEMA_VERSION,
                "portfolio_id": portfolio_id,
                "status": "reset",
                "reset_at": now,
                "reset_by": _safe_text(payload.get("reset_by"), 120) or "local-user",
                "reason": reason,
                "change_request_id": change_request_id,
                "previous_status": existing.get("status") if existing else "not_signed",
                "previous_integrity_hash": existing.get("integrity_hash") if existing else None,
            }
            reset["integrity_hash"] = final_board_signoff_hash(reset)
            _write_json(self.signoff_path(portfolio_id), reset)
            request["status"] = "applied"
            request["updated_at"] = now
            request["application"] = {"applied_at": now, "applied_by": reset["reset_by"], "applied_signoff_reset_hash": reset["integrity_hash"]}
            request["integrity_hash"] = final_board_change_request_hash(request)
            _write_json(self.change_request_path(portfolio_id, change_request_id), request)
            self._append_change_event(portfolio_id, "applied", request, now=now)
            self._append_history(portfolio_id, "reset", {"change_request_id": change_request_id, "reset_hash": reset["integrity_hash"]}, now=now)
            return reset

    def create_change_request(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleasePortfolioGovernanceFinalBoardStateError("reason must be at least 8 characters.")
        with self.lock:
            now = now or now_iso()
            self.portfolio_store.get_portfolio(portfolio_id)
            signoff = self.read_signoff(portfolio_id, default={})
            change_request_id = self._reserve_change_request_id(portfolio_id)
            item = {
                "schema_version": FINAL_BOARD_CHANGE_REQUEST_SCHEMA_VERSION,
                "change_request_id": change_request_id,
                "portfolio_id": portfolio_id,
                "status": "requested",
                "requested_at": now,
                "updated_at": now,
                "requested_by": _safe_text(payload.get("requested_by") or payload.get("created_by"), 120) or "local-user",
                "reason": reason,
                "scope": _scope(payload.get("scope")),
                "approval": {"approved_by": None, "approved_at": None, "note": None},
                "application": {"applied_at": None, "applied_by": None, "applied_signoff_reset_hash": None},
                "source": {"signoff_hash": signoff.get("integrity_hash"), "report_hash": self.read_report(portfolio_id, default={}).get("integrity_hash")},
            }
            item["payload_hash"] = stable_hash({key: value for key, value in item.items() if key not in {"payload_hash", "integrity_hash", "updated_at"}})
            item["integrity_hash"] = final_board_change_request_hash(item)
            self.change_requests_root(portfolio_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_request_path(portfolio_id, change_request_id), item)
            self._append_change_event(portfolio_id, "created", item, now=now)
            return item

    def update_change_request_status(self, portfolio_id: str, change_request_id: str, action: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            item = self.get_change_request(portfolio_id, change_request_id)
            if not final_board_change_request_integrity_ok(item):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Change Request integrity failed.")
            current = str(item.get("status") or "")
            if action == "approve":
                if current != "requested":
                    raise ReleasePortfolioGovernanceFinalBoardStateError("Only requested Change Requests can be approved.")
                approved_by = _safe_text(payload.get("approved_by") or payload.get("reviewed_by"), 120)
                if not approved_by:
                    raise ReleasePortfolioGovernanceFinalBoardStateError("approved_by is required.")
                item["status"] = "approved"
                item["approval"] = {"approved_by": approved_by, "approved_at": now, "note": sanitize_sensitive_text(str(payload.get("note") or payload.get("approval_note") or "").strip()) or None}
            elif action == "reject":
                if current != "requested":
                    raise ReleasePortfolioGovernanceFinalBoardStateError("Only requested Change Requests can be rejected.")
                reason = sanitize_sensitive_text(str(payload.get("reason") or payload.get("notes") or "").strip())
                if len(reason) < 8:
                    raise ReleasePortfolioGovernanceFinalBoardStateError("Rejection reason must be at least 8 characters.")
                item["status"] = "rejected"
                item["approval"] = {"approved_by": None, "approved_at": None, "note": reason}
            else:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Unknown Change Request action.")
            item["updated_at"] = now
            item["integrity_hash"] = final_board_change_request_hash(item)
            _write_json(self.change_request_path(portfolio_id, change_request_id), item)
            self._append_change_event(portfolio_id, action, item, now=now)
            return item

    def list_change_requests(self, portfolio_id: str) -> list[dict[str, Any]]:
        root = self.change_requests_root(portfolio_id)
        if not root.exists():
            return []
        rows = [_read_json_default(path, default={}) for path in sorted(root.glob("fcr-*.json"))]
        return sorted([item for item in rows if item], key=lambda item: str(item.get("requested_at") or ""), reverse=True)

    def get_change_request(self, portfolio_id: str, change_request_id: str) -> dict[str, Any]:
        data = _read_json_default(self.change_request_path(portfolio_id, change_request_id), default={})
        if not data:
            raise ReleasePortfolioGovernanceFinalBoardNotFoundError("Final Board Change Request does not exist.")
        return data

    def export_archive(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            signoff = self.get_signoff(portfolio_id)
            summary = self.signoff_summary(portfolio_id, signoff=signoff)
            if summary.get("status") not in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive requires signed Final Board Signoff.")
            if not summary.get("integrity_ok") or summary.get("stale"):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Signoff is stale or integrity failed. Reset and sign again.")
            export_dir = self.export_dir(portfolio_id).resolve()
            root = self.root_dir(portfolio_id).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "manifest.json", default={})
            if existing_manifest.get("final_board_signoff", {}).get("integrity_hash") == signoff.get("integrity_hash"):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive already exists for this signoff. Reset signoff before rebuilding archive evidence.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            report = self.read_report(portfolio_id, default={})
            responses = self.list_reviewer_responses(portfolio_id)
            change_requests = {"portfolio_id": portfolio_id, "items": self.list_change_requests(portfolio_id)}
            change_requests["payload_hash"] = stable_hash({key: value for key, value in change_requests.items() if key != "payload_hash"})
            history_text = self.history_path(portfolio_id).read_text(encoding="utf-8") if self.history_path(portfolio_id).exists() else ""
            reviewer_verification = _read_json_default(self.reviewer_pack_store.verification_report_path(portfolio_id), default={})
            audit_verification = _read_json_default(self.audit_store.verification_report_path(portfolio_id), default={})
            _write_json(export_dir / "final-board-report.json", report)
            _write_json(export_dir / "final-board-signoff.json", signoff)
            (export_dir / "final-board-history.jsonl").write_text(history_text, encoding="utf-8")
            _write_json(export_dir / "reviewer-response-summary.json", _reviewer_response_bundle(portfolio_id, responses, report.get("source", {})))
            _write_json(export_dir / "change-requests.json", change_requests)
            _write_json(export_dir / "governance-reviewer-pack-summary.json", {"summary": reviewer_pack_summary(self.reviewer_pack_store.read_report(portfolio_id, default={})), "verification": _verification_summary(reviewer_verification)})
            _write_json(export_dir / "governance-audit-summary.json", {"summary": audit_summary(self.audit_store.read_report(portfolio_id, default={})), "verification": _verification_summary(audit_verification)})
            _write_json(export_dir / "governance-archive-summary.json", self.audit_store.read_report(portfolio_id, default={}).get("archive_summary", {}))
            (export_dir / "final-board.md").write_text(_final_board_markdown(report, signoff), encoding="utf-8")
            (export_dir / "reviewer-response-summary.md").write_text(_reviewer_response_markdown(responses), encoding="utf-8")
            _write_readme(export_dir, report, signoff)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            source = report.get("source") if isinstance(report.get("source"), dict) else {}
            manifest = {
                "schema_version": FINAL_BOARD_ARCHIVE_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_final_board_archive",
                "tool": {"name": "MusicForge Release Portfolio Governance Final Board Archive", "version": __version__},
                "portfolio_id": portfolio_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "final_board_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "final_board_signoff": {"integrity_hash": signoff.get("integrity_hash"), "status": signoff.get("status")},
                "reviewer_pack_evidence": {
                    "verification_hash": source.get("governance_reviewer_pack_verification_hash"),
                    "zip_sha256": source.get("governance_reviewer_pack_zip_sha256"),
                    "manifest_hash": source.get("governance_reviewer_pack_manifest_hash"),
                },
                "audit_evidence": {
                    "verification_hash": source.get("governance_audit_verification_hash"),
                    "zip_sha256": source.get("governance_audit_zip_sha256"),
                    "manifest_hash": source.get("governance_audit_export_manifest_hash"),
                },
                "reviewer_response_summary": {"status": _reviewer_response_status(responses, source), "count": len(responses)},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "signoff": signoff, "responses": responses, "change_requests": change_requests}),
            }
            manifest["integrity_hash"] = final_board_archive_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            self._append_history(portfolio_id, "archive_exported", {"status": report.get("status"), "file_count": len(files)}, now=now)
            return sanitize_metadata(manifest, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)

    def build_archive_zip(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            signoff = self.signoff_summary(portfolio_id)
            if signoff.get("status") not in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive ZIP requires signed Final Board Signoff.")
            export_dir = self.export_dir(portfolio_id).resolve()
            root = self.root_dir(portfolio_id).resolve()
            zip_path = self.archive_zip_path(portfolio_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_archive(portfolio_id, now=now)
            if zip_path.exists():
                manifest = _read_zip_json(zip_path, "manifest.json")
                current = self.read_signoff(portfolio_id, default={})
                if manifest.get("final_board_signoff", {}).get("integrity_hash") == current.get("integrity_hash"):
                    raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive ZIP already exists for this signoff. Reset signoff before rebuilding archive evidence.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = final_board_archive_manifest_hash(manifest)
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
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            self._append_history(portfolio_id, "archive_zip_built", {"sha256": info["sha256"], "entry_count": len(entries)}, now=now)
            return sanitize_metadata(info, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)

    def signoff_summary(self, portfolio_id: str, *, signoff: dict[str, Any] | None = None) -> dict[str, Any]:
        data = signoff if isinstance(signoff, dict) else self.read_signoff(portfolio_id, default={})
        stale = False
        if data and data.get("status") in SIGNED_STATUSES:
            try:
                report = self.read_report(portfolio_id, default={})
                source = data.get("source") if isinstance(data.get("source"), dict) else {}
                stale = (
                    self.report_is_stale(portfolio_id, report)
                    or source.get("final_board_report_hash") != report.get("integrity_hash")
                    or source.get("reviewer_pack_verification_hash") != stable_hash(_read_json_default(self.reviewer_pack_store.verification_report_path(portfolio_id), default={}))
                    or source.get("governance_audit_verification_hash") != stable_hash(_read_json_default(self.audit_store.verification_report_path(portfolio_id), default={}))
                )
            except Exception:
                stale = True
        return final_board_signoff_summary(data, stale=stale)

    def summary(self, portfolio_id: str) -> dict[str, Any]:
        report = self.read_report(portfolio_id, default={})
        signoff = self.read_signoff(portfolio_id, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id), default={})
        return sanitize_metadata(
            {
                "status": final_board_signoff_summary(signoff).get("status") if signoff else report.get("status", "missing"),
                "report_status": report.get("status") if report else "missing",
                "signoff_status": final_board_signoff_summary(signoff).get("status"),
                "source_hash": report.get("source_hash"),
                "archive_zip_sha256": _sha256(self.archive_zip_path(portfolio_id)) if self.archive_zip_path(portfolio_id).exists() else None,
                "verification_status": verification.get("status") or "missing",
                "stale": self.report_is_stale(portfolio_id, report) if report else False,
            },
            blocked_keys=FINAL_BOARD_BLOCKED_KEYS,
        )

    def _final_board_findings(self, portfolio_id: str, source: dict[str, Any], responses: list[dict[str, Any]], payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        gates: list[dict[str, Any]] = []

        def gate(gate_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            status = "passed" if passed else "warning" if warning else "failed"
            item = {"gate_id": gate_id, "status": status, "severity": "warning" if warning else "blocking", "message": message}
            gates.append(item)
            if not passed and warning:
                warnings.append(_warning(gate_id, message))
            elif not passed:
                blockers.append(_blocker(gate_id, message))

        gate("portfolio_exists", bool(source.get("portfolio_hash")), "Portfolio exists.")
        gate("portfolio_report_current", bool(source.get("portfolio_report_integrity_ok")) and not source.get("portfolio_report_stale"), "Portfolio Audit report is current.")
        gate("governance_audit_report_current", bool(source.get("governance_audit_report_integrity_ok")) and not source.get("governance_audit_report_stale") and source.get("governance_audit_report_status") != "failed", "Governance Audit report is current.")
        gate("governance_audit_ledger_chain", bool(source.get("governance_audit_ledger_integrity_ok")), "Governance Audit ledger chain is valid.")
        gate(
            "governance_audit_verification_current",
            source.get("governance_audit_verification_status") == "passed"
            and source.get("governance_audit_verification_zip_sha256") == source.get("governance_audit_zip_sha256")
            and source.get("governance_audit_verification_zip_size_bytes") == source.get("governance_audit_zip_size_bytes")
            and source.get("governance_audit_verification_manifest_hash") == source.get("governance_audit_export_manifest_hash"),
            "Governance Audit verification matches the current Audit ZIP and manifest.",
        )
        gate("governance_reviewer_pack_report_current", bool(source.get("governance_reviewer_report_integrity_ok")) and not source.get("governance_reviewer_report_stale") and source.get("governance_reviewer_report_status") != "failed", "Governance Reviewer Pack report is current.")
        gate(
            "governance_reviewer_pack_verification_current",
            source.get("governance_reviewer_pack_verification_status") == "passed"
            and source.get("governance_reviewer_pack_verification_zip_sha256") == source.get("governance_reviewer_pack_zip_sha256")
            and source.get("governance_reviewer_pack_verification_zip_size_bytes") == source.get("governance_reviewer_pack_zip_size_bytes"),
            "Governance Reviewer Pack verification matches the current Reviewer Pack ZIP.",
        )
        queue_count = int(source.get("queue_count") or 0)
        signed_count = int(source.get("signed_queue_count") or 0)
        archive_count = int(source.get("archive_verified_count") or 0)
        gate("signed_queue_coverage", queue_count > 0 and signed_count >= queue_count, "All Governance Queues are signed.")
        gate("archive_verification_coverage", signed_count > 0 and archive_count >= signed_count, "All signed Governance Queues have verified Archive evidence.")
        gate("reset_change_request_causality", int(source.get("reset_count") or 0) == 0 or int(source.get("applied_change_request_count") or 0) >= int(source.get("reset_count") or 0), "Reset entries are bound to applied Change Requests.")
        response_status = _reviewer_response_status(responses, source)
        gate("reviewer_response_closed", response_status not in {"needs_changes", "rejected", "stale", "invalid"}, "Reviewer responses are closed.")
        if bool(payload.get("require_reviewer_response", False)):
            gate("external_reviewer_response_required", response_status in {"accepted", "accepted_with_notes"}, "Accepted reviewer response is required.")
        force_count = int(source.get("force_signed_queue_count") or 0)
        if force_count:
            gate("no_force_signoff", False, "Force-signed Governance Queue is present.", warning=not bool(payload.get("require_no_force", False)))
        if _redaction_summary({"source": source, "responses": responses}).get("status") == "failed":
            gate("redaction_scan", False, "Final Board source contains sensitive values.")
        else:
            gate("redaction_scan", True, "No sensitive values found in Final Board source.")
        return blockers, warnings, gates

    def _reserve_report_id(self, portfolio_id: str) -> str:
        existing = self.read_report(portfolio_id, default={})
        if str(existing.get("report_id") or "").startswith("fgb-"):
            return str(existing.get("report_id"))
        return "fgb-000001"

    def _reserve_response_id(self, portfolio_id: str) -> str:
        root = self.responses_root(portfolio_id)
        root.mkdir(parents=True, exist_ok=True)
        nums: list[int] = []
        for path in root.glob("fbr-*.json"):
            try:
                nums.append(int(path.stem.split("-")[-1]))
            except ValueError:
                pass
        return f"fbr-{(max(nums) if nums else 0) + 1:06d}"

    def _reserve_signoff_id(self, portfolio_id: str) -> str:
        path = self.history_path(portfolio_id)
        used: list[int] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                signoff_id = str((event.get("summary") if isinstance(event.get("summary"), dict) else {}).get("signoff_id") or "")
                if signoff_id.startswith("fgs-"):
                    try:
                        used.append(int(signoff_id.split("-")[-1]))
                    except ValueError:
                        pass
        return f"fgs-{(max(used) if used else 0) + 1:06d}"

    def _reserve_change_request_id(self, portfolio_id: str) -> str:
        root = self.change_requests_root(portfolio_id)
        root.mkdir(parents=True, exist_ok=True)
        nums: list[int] = []
        for path in root.glob("fcr-*.json"):
            try:
                nums.append(int(path.stem.split("-")[-1]))
            except ValueError:
                pass
        return f"fcr-{(max(nums) if nums else 0) + 1:06d}"

    def _append_history(self, portfolio_id: str, event_type: str, summary: dict[str, Any], *, now: str | None = None) -> None:
        path = self.history_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"fgbe-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _append_change_event(self, portfolio_id: str, event_type: str, item: dict[str, Any], *, now: str | None = None) -> None:
        path = self.change_request_events_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"fcre-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "change_request_id": item.get("change_request_id"), "status": item.get("status")}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def final_board_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS})


def final_board_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_report_integrity_hash(data)


def final_board_response_integrity_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS})


def final_board_response_integrity_ok(response: dict[str, Any] | None) -> bool:
    data = response if isinstance(response, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_response_integrity_hash(data)


def final_board_signoff_hash(signoff: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (signoff or {}).items() if key not in FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS})


def final_board_signoff_integrity_ok(signoff: dict[str, Any] | None) -> bool:
    data = signoff if isinstance(signoff, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_signoff_hash(data)


def final_board_signoff_summary(signoff: dict[str, Any] | None, *, stale: bool = False) -> dict[str, Any]:
    data = signoff if isinstance(signoff, dict) else {}
    if not data:
        return {"status": "not_signed", "integrity_ok": False, "stale": False}
    integrity_ok = final_board_signoff_integrity_ok(data)
    return sanitize_metadata({"status": data.get("status") or "missing", "signoff_id": data.get("signoff_id"), "portfolio_id": data.get("portfolio_id"), "signed_at": data.get("signed_at"), "signed_by": data.get("signed_by"), "force": bool(data.get("force")), "integrity_hash": data.get("integrity_hash"), "integrity_ok": integrity_ok, "stale": stale}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def final_board_change_request_hash(item: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (item or {}).items() if key not in FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS})


def final_board_change_request_integrity_ok(item: dict[str, Any] | None) -> bool:
    data = item if isinstance(item, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_change_request_hash(data)


def final_board_archive_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS})


def final_board_archive_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_archive_manifest_hash(data)


def final_board_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    if not data:
        return {"status": "missing", "integrity_ok": False}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata({"status": data.get("status"), "readiness": data.get("readiness"), "portfolio_id": data.get("portfolio_id"), "source_hash": data.get("source_hash"), "integrity_hash": data.get("integrity_hash"), "integrity_ok": final_board_report_integrity_ok(data), **summary}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def _summary_from_source(source: dict[str, Any], responses: list[dict[str, Any]], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "queue_count": int(source.get("queue_count") or 0),
        "signed_queue_count": int(source.get("signed_queue_count") or 0),
        "archive_verified_count": int(source.get("archive_verified_count") or 0),
        "reviewer_pack_status": source.get("governance_reviewer_report_status"),
        "reviewer_pack_verification_status": source.get("governance_reviewer_pack_verification_status"),
        "audit_status": source.get("governance_audit_report_status"),
        "audit_verification_status": source.get("governance_audit_verification_status"),
        "force_signed_queue_count": int(source.get("force_signed_queue_count") or 0),
        "reset_count": int(source.get("reset_count") or 0),
        "applied_change_request_count": int(source.get("applied_change_request_count") or 0),
        "reviewer_response_status": _reviewer_response_status(responses, source),
        "accepted_reviewer_response_count": sum(1 for item in responses if item.get("decision") in {"accepted", "accepted_with_notes"}),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


def _reviewer_response_status(responses: list[dict[str, Any]], source: dict[str, Any]) -> str:
    if not responses:
        return "missing"
    valid_current: list[dict[str, Any]] = []
    for item in responses:
        if not final_board_response_integrity_ok(item):
            return "invalid"
        response_source = item.get("source") if isinstance(item.get("source"), dict) else {}
        current = (
            response_source.get("reviewer_pack_source_hash") == source.get("governance_reviewer_report_hash")
            and response_source.get("reviewer_pack_zip_sha256") == source.get("governance_reviewer_pack_zip_sha256")
            and response_source.get("reviewer_pack_verification_hash") == source.get("governance_reviewer_pack_verification_hash")
        )
        if current:
            valid_current.append(item)
    if not valid_current:
        return "stale"
    latest = valid_current[0]
    decision = str(latest.get("decision") or "")
    return decision if decision in RESPONSE_DECISIONS else "missing"


def _response_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {"response_id": item.get("response_id"), "decision": item.get("decision"), "reviewer": item.get("reviewer", {}), "integrity_hash": item.get("integrity_hash"), "integrity_ok": final_board_response_integrity_ok(item)}


def _reviewer_response_bundle(portfolio_id: str, responses: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    bundle = {"portfolio_id": portfolio_id, "status": _reviewer_response_status(responses, source), "count": len(responses), "items": [_response_summary(item) for item in responses]}
    bundle["payload_hash"] = stable_hash({key: value for key, value in bundle.items() if key != "payload_hash"})
    return bundle


def _verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"status": report.get("status") or "missing", "zip_sha256": report.get("zip_sha256"), "zip_size_bytes": report.get("zip_size_bytes"), "manifest_hash": report.get("manifest_hash"), "summary": summary}


def _sanitize_findings(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        rows.append({"finding_id": _safe_text(item.get("finding_id"), 80) or f"finding-{index:03d}", "severity": _safe_text(item.get("severity"), 40) or "low", "status": _safe_text(item.get("status"), 40) or "closed", "category": _safe_text(item.get("category"), 80) or "general", "message": sanitize_sensitive_text(str(item.get("message") or "").strip())[:1000], "resolution_note": sanitize_sensitive_text(str(item.get("resolution_note") or "").strip())[:1000]})
    return rows


def _scope(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["final_board_signoff_reset"]
    rows = [_safe_text(item, 80) for item in value if _safe_text(item, 80)]
    return rows or ["final_board_signoff_reset"]


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in RESPONSE_BLOCKED_KEYS:
                raise ReleasePortfolioGovernanceFinalBoardStateError(f"Reviewer response field is not allowed: {key}.")
            _reject_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default if default is not None else {}
    try:
        value = read_json(path)
    except Exception:
        return default if default is not None else {}
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def _read_zip_json(path: Path, name: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            value = json.loads(archive.read(name).decode("utf-8"))
    except Exception:
        return {}
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(data, blocked_keys=FINAL_BOARD_BLOCKED_KEYS))


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    rel = _validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        resolved = path.resolve()
        _ensure_within(root.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(root.resolve()).as_posix())
        if entry in seen:
            raise ReleasePortfolioGovernanceFinalBoardStateError(f"Duplicate Final Board Archive ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceFinalBoardStateError("Refusing to operate outside Final Board boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _final_board_markdown(report: dict[str, Any], signoff: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return "\n".join(["# Portfolio Governance Final Board", "", f"Portfolio: {report.get('portfolio_id')}", f"Report status: {report.get('status')}", f"Signoff status: {signoff.get('status')}", f"Queues: {summary.get('signed_queue_count', 0)}/{summary.get('queue_count', 0)}", f"Archives: {summary.get('archive_verified_count', 0)}", ""]) 


def _reviewer_response_markdown(responses: list[dict[str, Any]]) -> str:
    lines = ["# Reviewer Responses", ""]
    for item in responses:
        reviewer = item.get("reviewer") if isinstance(item.get("reviewer"), dict) else {}
        lines.append(f"- {item.get('response_id')}: {item.get('decision')} by {reviewer.get('name') or 'reviewer'}")
    lines.append("")
    return "\n".join(lines)


def _write_readme(export_dir: Path, report: dict[str, Any], signoff: dict[str, Any]) -> None:
    lines = ["MusicForge Release Portfolio Governance Final Board Archive", "", f"Portfolio ID: {report.get('portfolio_id')}", f"Report Status: {report.get('status')}", f"Signoff Status: {signoff.get('status')}", "", "Verify with: python -m song_agent.cli verify-release-portfolio-governance-final-board-package portfolio-governance-final-board-archive.zip --strict --require-signed --require-reviewer-pack --require-audit --require-archives"]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocker(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "warning", "message": message}


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not text.startswith(f"{prefix}-") or any(ch in text for ch in "\\/:"):
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Invalid {prefix} id.")
    return text
