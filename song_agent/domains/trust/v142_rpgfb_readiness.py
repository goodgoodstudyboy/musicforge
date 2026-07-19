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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore as ReleasePortfolioGovernanceAuditStore, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore as ReleasePortfolioGovernanceReviewerPackStore, reviewer_report_integrity_hash as reviewer_report_integrity_hash, reviewer_report_integrity_ok as reviewer_report_integrity_ok, reviewer_pack_summary as reviewer_pack_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_final_board_contracts import FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS as FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS, FINAL_BOARD_BLOCKED_KEYS as FINAL_BOARD_BLOCKED_KEYS, FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS as FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS, FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS as FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS, FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS as FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS, FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS as FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS, final_board_archive_manifest_hash as final_board_archive_manifest_hash, final_board_change_request_hash as final_board_change_request_hash, final_board_change_request_integrity_ok as final_board_change_request_integrity_ok, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_response_integrity_hash as final_board_response_integrity_hash, final_board_signoff_hash as final_board_signoff_hash

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

ReleasePortfolioGovernanceFinalBoardNotFoundError = _make_deferred_global('ReleasePortfolioGovernanceFinalBoardNotFoundError')
ReleasePortfolioGovernanceFinalBoardStateError = _make_deferred_global('ReleasePortfolioGovernanceFinalBoardStateError')
_read_json_default = _make_deferred_global('_read_json_default')
_reject_forbidden_keys = _make_deferred_global('_reject_forbidden_keys')
_response_summary = _make_deferred_global('_response_summary')
_reviewer_response_status = _make_deferred_global('_reviewer_response_status')
_safe_text = _make_deferred_global('_safe_text')
_sanitize_findings = _make_deferred_global('_sanitize_findings')
_scope = _make_deferred_global('_scope')
_sha256 = _make_deferred_global('_sha256')
_summary_from_source = _make_deferred_global('_summary_from_source')
_validate_id = _make_deferred_global('_validate_id')
_write_json = _make_deferred_global('_write_json')
final_board_report_integrity_ok = _make_deferred_global('final_board_report_integrity_ok')
final_board_signoff_summary = _make_deferred_global('final_board_signoff_summary')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceFinalBoardNotFoundError, ReleasePortfolioGovernanceFinalBoardStateError, _read_json_default, _reject_forbidden_keys, _response_summary, _reviewer_response_status, _safe_text
    global _sanitize_findings, _scope, _sha256, _summary_from_source, _validate_id, _write_json, final_board_report_integrity_ok, final_board_signoff_summary
    global key, value
    ReleasePortfolioGovernanceFinalBoardNotFoundError = namespace.get('ReleasePortfolioGovernanceFinalBoardNotFoundError', ReleasePortfolioGovernanceFinalBoardNotFoundError)
    ReleasePortfolioGovernanceFinalBoardStateError = namespace.get('ReleasePortfolioGovernanceFinalBoardStateError', ReleasePortfolioGovernanceFinalBoardStateError)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _reject_forbidden_keys = namespace.get('_reject_forbidden_keys', _reject_forbidden_keys)
    _response_summary = namespace.get('_response_summary', _response_summary)
    _reviewer_response_status = namespace.get('_reviewer_response_status', _reviewer_response_status)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _sanitize_findings = namespace.get('_sanitize_findings', _sanitize_findings)
    _scope = namespace.get('_scope', _scope)
    _sha256 = namespace.get('_sha256', _sha256)
    _summary_from_source = namespace.get('_summary_from_source', _summary_from_source)
    _validate_id = namespace.get('_validate_id', _validate_id)
    _write_json = namespace.get('_write_json', _write_json)
    final_board_report_integrity_ok = namespace.get('final_board_report_integrity_ok', final_board_report_integrity_ok)
    final_board_signoff_summary = namespace.get('final_board_signoff_summary', final_board_signoff_summary)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


FINAL_BOARD_SCHEMA_VERSION = 1
FINAL_BOARD_ARCHIVE_SCHEMA_VERSION = 1
FINAL_BOARD_CHANGE_REQUEST_SCHEMA_VERSION = 1
SIGNED_STATUSES = {"signed", "force_signed"}
RESPONSE_DECISIONS = {"accepted", "accepted_with_notes", "needs_changes", "rejected"}
RESPONSE_BLOCKED_KEYS = {"source_path", "local_path", "file_path", "raw_file", "token", "api_key", "access_token", "authorization", "secret"}




class ReleasePortfolioGovernanceFinalBoardStoreReadinessMixin:
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

    def read_report(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.report_path(portfolio_id), default=default)

    def read_signoff(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.signoff_path(portfolio_id), default=default)

    def get_signoff(self, portfolio_id: str) -> DomainDocument:
        signoff = self.read_signoff(portfolio_id, default={})
        if not signoff:
            raise ReleasePortfolioGovernanceFinalBoardNotFoundError("Portfolio Governance Final Board Signoff does not exist.")
        return signoff

    def read_export_manifest(self, portfolio_id: str) -> DomainDocument:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceFinalBoardNotFoundError("Portfolio Governance Final Board Archive export has not been generated.")
        return _read_json_default(path, default={})

    def refresh_report(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def build_source(self, portfolio_id: str) -> DomainDocument:
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
                "queue_count": int((_as_document(governance_audit_report.get("coverage"))).get("queue_count") or 0),
                "signed_queue_count": int((_as_document(governance_audit_report.get("coverage"))).get("signed_queue_count") or 0),
                "archive_verified_count": int((_as_document(governance_audit_report.get("coverage"))).get("archive_verified_count") or 0),
                "force_signed_queue_count": int((_as_document(governance_audit_report.get("coverage"))).get("force_signed_count") or 0),
                "reset_count": int((_as_document(governance_audit_report.get("coverage"))).get("reset_count") or 0),
                "applied_change_request_count": int((_as_document(governance_audit_report.get("coverage"))).get("applied_change_request_count") or 0),
            },
            blocked_keys=FINAL_BOARD_BLOCKED_KEYS,
        )

    def _source_with_responses(self, portfolio_id: str, responses: list[DomainDocument] | None = None) -> DomainDocument:
        rows = responses if responses is not None else self.list_reviewer_responses(portfolio_id)
        source = self.build_source(portfolio_id)
        source["reviewer_responses_hash"] = stable_hash([item.get("integrity_hash") for item in rows])
        source["reviewer_response_count"] = len(rows)
        source["reviewer_response_status"] = _reviewer_response_status(rows, source)
        return sanitize_metadata(source, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)

    def report_is_stale(self, portfolio_id: str, report: DomainDocument | None = None) -> bool:
        data = _document_or(report, self.read_report(portfolio_id, default={}))
        if not data:
            return False
        try:
            return stable_hash(self._source_with_responses(portfolio_id)) != str(data.get("source_hash") or "")
        except Exception:
            return True

    def import_reviewer_response(self, portfolio_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
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
                "reviewer": sanitize_metadata(_as_document(payload.get("reviewer")), blocked_keys=FINAL_BOARD_BLOCKED_KEYS),
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

    def list_reviewer_responses(self, portfolio_id: str) -> list[DomainDocument]:
        root = self.responses_root(portfolio_id)
        if not root.exists():
            return []
        rows = [_read_json_default(path, default={}) for path in sorted(root.glob("fbr-*.json"))]
        return sorted([item for item in rows if item], key=lambda item: str(item.get("imported_at") or ""), reverse=True)

    def signoff(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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
            blockers = _as_list(report.get("blockers"))
            warnings = _as_list(report.get("warnings"))
            if blockers:
                detail = str((_as_document(blockers[0])).get("message") or "Final Board gate failed.")
                raise ReleasePortfolioGovernanceFinalBoardStateError(f"Final Board Signoff gate failed: {detail}")
            if warnings and not force and not bool(payload.get("allow_warning_signoff", False)):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Report has warnings. Use force with override_reason or allow_warning_signoff.")
            if force and len(override_reason) < 20:
                raise ReleasePortfolioGovernanceFinalBoardStateError("override_reason must be at least 20 characters for force Final Board Signoff.")
            status = "force_signed" if force and warnings else "signed"
            source = _as_document(report.get("source"))
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
            self._append_history(portfolio_id, "signed", {"status": status, "signoff_id": signoff["signoff_id"], "signoff_integrity_hash": signoff["integrity_hash"]}, now=now)
            return signoff

    def reset_signoff(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def create_change_request(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def update_change_request_status(self, portfolio_id: str, change_request_id: str, action: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def list_change_requests(self, portfolio_id: str) -> list[DomainDocument]:
        root = self.change_requests_root(portfolio_id)
        if not root.exists():
            return []
        rows = [_read_json_default(path, default={}) for path in sorted(root.glob("fcr-*.json"))]
        return sorted([item for item in rows if item], key=lambda item: str(item.get("requested_at") or ""), reverse=True)

    def get_change_request(self, portfolio_id: str, change_request_id: str) -> DomainDocument:
        data = _read_json_default(self.change_request_path(portfolio_id, change_request_id), default={})
        if not data:
            raise ReleasePortfolioGovernanceFinalBoardNotFoundError("Final Board Change Request does not exist.")
        return data
