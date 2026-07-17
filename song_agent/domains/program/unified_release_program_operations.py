from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, HistoryChain as HistoryChain, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package, write_unified_release_program_operations_verification_report as write_unified_release_program_operations_verification_report
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package


class UnifiedReleaseProgramOperationsError(ValueError):
    pass


class UnifiedReleaseProgramOperationsNotFoundError(UnifiedReleaseProgramOperationsError):
    pass


class UnifiedReleaseProgramOperationsStateError(UnifiedReleaseProgramOperationsError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramOperationsStateError)


class UnifiedReleaseProgramOperationsStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

    def ops_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "operations"

    def change_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "change-control"

    def request_dir(self, program_id: str, request_id: str) -> Path:
        return self.change_dir(program_id) / "change-requests" / _safe_id(request_id)

    def request_path(self, program_id: str, request_id: str) -> Path:
        return self.request_dir(program_id, request_id) / "program-change-request.json"

    def approval_path(self, program_id: str, request_id: str) -> Path:
        return self.request_dir(program_id, request_id) / "change-approval.json"

    def reset_proof_path(self, program_id: str, request_id: str) -> Path:
        return self.change_dir(program_id) / "reset-proofs" / f"{_safe_id(request_id)}.json"

    def change_history_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "change-control-history.jsonl"

    def change_report_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "change-control-report.json"

    def runbook_dir(self, program_id: str, runbook_id: str) -> Path:
        return self.ops_dir(program_id) / "runbooks" / _safe_id(runbook_id)

    def runbook_path(self, program_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(program_id, runbook_id) / "runbook.json"

    def runbook_results_path(self, program_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(program_id, runbook_id) / "runbook-results.json"

    def review_dir(self, program_id: str, review_id: str) -> Path:
        return self.ops_dir(program_id) / "continuous-reviews" / _safe_id(review_id)

    def review_report_path(self, program_id: str, review_id: str) -> Path:
        return self.review_dir(program_id, review_id) / "review-report.json"

    def latest_review_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "continuous-reviews" / "latest-review.json"

    def lifecycle_dir(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "lifecycle-audit"

    def lifecycle_report_path(self, program_id: str) -> Path:
        return self.lifecycle_dir(program_id) / "lifecycle-report.json"

    def lifecycle_ledger_path(self, program_id: str) -> Path:
        return self.lifecycle_dir(program_id) / "lifecycle-ledger.jsonl"

    def lifecycle_index_path(self, program_id: str) -> Path:
        return self.lifecycle_dir(program_id) / "lifecycle-index.json"

    def archive_dir(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "operations-archive"

    def archive_manifest_path(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "manifest.json"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "operations-archive.zip"

    def archive_verification_report_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "operations-archive-verification-report.json"

    def create_change_request(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            binding = self._current_program_binding(program_id, payload)
            request_id = _safe_id(str(payload.get("change_request_id") or self._next_request_id(program_id)))
            if self.request_path(program_id, request_id).exists():
                raise UnifiedReleaseProgramOperationsStateError(f"Program Change Request already exists: {request_id}")
            now = now_iso()
            request = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_change_request",
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "submitted",
                    "change_type": _bounded(payload.get("change_type") or "reset_signoff", 120),
                    "reason": _bounded(payload.get("reason") or "Program evidence changed after signoff.", 1000),
                    "requested_by": _bounded(payload.get("requested_by") or "program-operator", 120),
                    "allowed_actions": list(payload.get("allowed_actions") or ["reset_program_signoff", "refresh_program_report", "rebuild_program_zip"]),
                    "created_at": now,
                    "updated_at": now,
                    "target": {
                        "program_signoff_hash": binding.get("signoff_hash"),
                        "program_zip_sha256": binding.get("program_zip_sha256"),
                        "program_manifest_hash": binding.get("program_manifest_hash"),
                    },
                    "source": binding,
                    "tool": {"name": "MusicForge Unified Release Program Change Request", "version": __version__},
                }
            )
            request["payload_hash"] = stable_hash({key: value for key, value in request.items() if key not in {"payload_hash", "integrity_hash"}})
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.request_path(program_id, request_id), request)
            self._append_change_history(program_id, {"event_type": "program_change_request_submitted", "created_at": now, "program_id": program_id, "change_request_id": request_id, "request_hash": request["integrity_hash"]})
            self.refresh_change_control_report(program_id)
            return request

    def approve_change_request(self, program_id: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            request = self.read_change_request(program_id, request_id)
            if request.get("status") not in {"submitted", "draft"}:
                raise UnifiedReleaseProgramOperationsStateError("Only submitted Program Change Requests can be approved.")
            self._assert_request_current(program_id, request, payload)
            now = now_iso()
            submitted_request_hash = request.get("integrity_hash")
            approval = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_change_approval",
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "approved",
                    "approved_by": _bounded(payload.get("approved_by") or "program-owner", 120),
                    "role": _bounded(payload.get("role") or "program_owner", 80),
                    "reason": _bounded(payload.get("reason") or request.get("reason") or "Approved Program reset.", 1000),
                    "approved_actions": list(request.get("allowed_actions") or []),
                    "approved_at": now,
                    "request_hash": submitted_request_hash,
                    "target": request.get("target"),
                    "source": request.get("source"),
                }
            )
            approval["payload_hash"] = stable_hash({key: value for key, value in approval.items() if key not in {"payload_hash", "integrity_hash"}})
            approval["integrity_hash"] = _integrity_hash(approval)
            request["status"] = "approved"
            request["submitted_request_hash"] = submitted_request_hash
            request["approved_at"] = now
            request["approval_hash"] = approval.get("integrity_hash")
            request["updated_at"] = now
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.request_path(program_id, request_id), request)
            write_json(self.approval_path(program_id, request_id), approval)
            self._append_change_history(program_id, {"event_type": "program_change_request_approved", "created_at": now, "program_id": program_id, "change_request_id": request_id, "request_hash": request["integrity_hash"], "approval_hash": approval["integrity_hash"]})
            self.refresh_change_control_report(program_id)
            return approval

    def reset_program_signoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        request_id = _safe_id(str(payload.get("change_request_id") or ""))
        if not request_id:
            raise UnifiedReleaseProgramOperationsStateError("change_request_id is required for Program signoff reset.")
        with self.lock:
            request = self.read_change_request(program_id, request_id)
            if request.get("status") != "approved" or request.get("applied_at"):
                raise UnifiedReleaseProgramOperationsStateError("Program Change Request must be approved and unused before reset.")
            if request.get("change_type") != "reset_signoff":
                raise UnifiedReleaseProgramOperationsStateError("Program Change Request is not approved for signoff reset.")
            if "reset_program_signoff" not in set(request.get("allowed_actions") or []):
                raise UnifiedReleaseProgramOperationsStateError("Program Change Request does not allow reset_program_signoff.")
            if not self.approval_path(program_id, request_id).exists():
                raise UnifiedReleaseProgramOperationsStateError("Approved Program Change Request is missing approval proof.")
            approval = read_json(self.approval_path(program_id, request_id))
            try:
                ChangeRequestService.validate_reset_authorization(
                    request,
                    approval,
                    ResetAuthorization(program_id, request_id, "reset_program_signoff", "reset_signoff", request.get("target") or {}, request.get("source") or {}),
                )
            except ValueError as exc:
                raise UnifiedReleaseProgramOperationsStateError(str(exc)) from exc
            if not _integrity_ok(approval) or approval.get("status") != "approved":
                raise UnifiedReleaseProgramOperationsStateError("Program Change Request approval integrity failed.")
            if approval.get("target") != request.get("target") or approval.get("source") != request.get("source"):
                raise UnifiedReleaseProgramOperationsStateError("Program Change Request approval binding does not match request.")
            self._assert_request_current(program_id, request, payload)
            current = _as_document(request.get("source"))
            previous_signoff_hash = str(current.get("signoff_hash") or "")
            if not previous_signoff_hash:
                raise UnifiedReleaseProgramOperationsStateError("Program Change Request does not bind a signed Program.")
            now = now_iso()
            reset_event = self.program_store._append_history(
                program_id,
                {
                    "event_type": "unified_release_program_signoff_reset",
                    "created_at": now,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "approval_hash": approval.get("integrity_hash"),
                    "previous_signoff_hash": previous_signoff_hash,
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "previous_program_zip_sha256": current.get("program_zip_sha256"),
                    "previous_program_manifest_hash": current.get("program_manifest_hash"),
                    "previous_verification_report_hash": current.get("verification_report_hash"),
                    "external_evidence_manifest_hash": current.get("external_evidence_manifest_hash"),
                    "reset_by": _bounded(payload.get("reset_by") or approval.get("approved_by") or "program-owner", 120),
                    "reason": _bounded(payload.get("reason") or approval.get("reason") or "Approved Program reset.", 1000),
                },
            )
            reset_proof = ResetService.build_proof(sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_reset_proof",
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "applied",
                    "applied_at": now,
                    "approval_hash": approval.get("integrity_hash"),
                    "request_hash": request.get("integrity_hash"),
                    "previous_signoff_hash": previous_signoff_hash,
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "reset_event_payload_hash": reset_event.get("payload_hash"),
                    "source": current,
                }
            ))
            request = ResetService.mark_applied(
                request,
                applied_at=now,
                proof_hash=str(reset_proof.get("integrity_hash") or ""),
                event_hash=str(reset_event.get("event_hash") or ""),
                updates={"updated_at": now},
            )
            write_json(self.request_path(program_id, request_id), request)
            write_json(self.reset_proof_path(program_id, request_id), reset_proof)
            self._append_change_history(program_id, {"event_type": "program_change_request_reset_applied", "created_at": now, "program_id": program_id, "change_request_id": request_id, "request_hash": request["integrity_hash"], "approval_hash": approval["integrity_hash"], "reset_proof_hash": reset_proof["integrity_hash"], "reset_event_hash": reset_event["event_hash"]})
            program = self.program_store.read_program(program_id)
            program["status"] = "reset"
            program["previous_signoff_hash"] = previous_signoff_hash
            program["reset_at"] = now
            program["updated_at"] = now
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_store.program_path(program_id), program)
            self.refresh_change_control_report(program_id)
            return reset_proof

    def read_change_request(self, program_id: str, request_id: str) -> dict[str, Any]:
        path = self.request_path(program_id, request_id)
        if not path.exists():
            raise UnifiedReleaseProgramOperationsNotFoundError(f"Program Change Request not found: {request_id}")
        return read_json(path)

    def list_change_requests(self, program_id: str) -> list[dict[str, Any]]:
        base = self.change_dir(program_id) / "change-requests"
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*/program-change-request.json"))]

    def refresh_change_control_report(self, program_id: str) -> dict[str, Any]:
        requests = self.list_change_requests(program_id)
        summaries = [self._request_summary(program_id, request) for request in requests]
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_change_control_report",
                "program_id": program_id,
                "created_at": now_iso(),
                "status": "pending_reset" if any(row.get("status") == "approved" for row in summaries) else "passed",
                "requests": summaries,
                "summary": {
                    "request_count": len(summaries),
                    "approved_count": sum(1 for row in summaries if row.get("status") == "approved"),
                    "applied_reset_count": sum(1 for row in summaries if row.get("status") == "applied"),
                },
            }
        )
        write_json(self.change_report_path(program_id), report)
        return report

    def create_runbook(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        runbook_id = _safe_id(str(payload.get("runbook_id") or self._next_runbook_id(program_id)))
        binding = self._program_binding_best_effort(program_id)
        items = payload.get("items") if isinstance(payload.get("items"), list) else None
        if items is None:
            items = [
                {"item_id": "program-verify", "action": "program.verify", "safe": True, "status": "pending"},
                {"item_id": "continuous-review-refresh", "action": "program.refresh_continuous_review", "safe": True, "status": "pending"},
                {"item_id": "lifecycle-refresh", "action": "program.refresh_lifecycle_audit", "safe": True, "status": "pending"},
                {"item_id": "program-reset", "action": "program.reset_signoff", "safe": False, "status": "manual_required", "reason": "Requires approved Change Request."},
            ]
        runbook = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_operations_runbook",
                "program_id": program_id,
                "runbook_id": runbook_id,
                "created_at": now_iso(),
                "status": "pending",
                "source": binding,
                "items": [sanitize_metadata(dict(row)) for row in items],
                "summary": _runbook_summary(items),
            }
        )
        write_json(self.runbook_path(program_id, runbook_id), runbook)
        write_json(self.runbook_results_path(program_id, runbook_id), _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_runbook_results", "program_id": program_id, "runbook_id": runbook_id, "results": [], "summary": {}}))
        return runbook

    def run_safe(self, program_id: str, runbook_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        runbook = read_json(self.runbook_path(program_id, runbook_id))
        results = []
        for item in runbook.get("items", []):
            row = dict(item)
            if not row.get("safe"):
                row["status"] = "manual_required"
                results.append({"item_id": row.get("item_id"), "action": row.get("action"), "status": "manual_required"})
                continue
            action = str(row.get("action") or "")
            try:
                if action == "program.verify":
                    result = self.program_store.verify_package(program_id, {"strict": True, "require_current": True, "require_signed": True, **payload})
                    row["status"] = "completed" if result.get("status") == "passed" else "failed"
                elif action == "program.refresh_continuous_review":
                    result = self.refresh_continuous_review(program_id, payload)
                    row["status"] = "completed" if result.get("status") == "passed" else "failed"
                elif action == "program.refresh_lifecycle_audit":
                    result = self.refresh_lifecycle_audit(program_id, payload)
                    row["status"] = "completed" if result.get("status") == "passed" else "failed"
                else:
                    result = {"status": "skipped_unsupported"}
                    row["status"] = "skipped_unsupported"
                results.append({"item_id": row.get("item_id"), "action": action, "status": row["status"], "result_status": result.get("status")})
            except Exception as exc:
                row["status"] = "failed"
                results.append({"item_id": row.get("item_id"), "action": action, "status": "failed", "error": sanitize_sensitive_text(str(exc))})
            item.update(row)
        runbook["status"] = "completed" if all(row.get("status") in {"completed", "manual_required", "skipped_unsupported"} for row in runbook.get("items", [])) else "blocked"
        if any(row.get("status") == "manual_required" for row in runbook.get("items", [])):
            runbook["status"] = "completed_with_manual_actions" if runbook["status"] == "completed" else runbook["status"]
        runbook["summary"] = _runbook_summary(runbook.get("items", []))
        runbook["integrity_hash"] = _integrity_hash(runbook)
        write_json(self.runbook_path(program_id, runbook_id), runbook)
        result_doc = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_runbook_results", "program_id": program_id, "runbook_id": runbook_id, "results": results, "summary": runbook["summary"]})
        write_json(self.runbook_results_path(program_id, runbook_id), result_doc)
        return {"runbook": runbook, "results": result_doc, "status": runbook.get("status"), "summary": runbook.get("summary")}

    def refresh_continuous_review(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        review_id = _safe_id(str(payload.get("review_id") or self._next_review_id(program_id)))
        external = self._current_program_state(program_id, payload, require=True)
        checks = external.pop("checks")
        failed = [row for row in checks if row.get("status") == "failed"]
        review = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE,
                "program_id": program_id,
                "review_id": review_id,
                "created_at": now_iso(),
                "status": "failed" if failed else "passed",
                "source": external,
                "checks": checks,
                "drift": {
                    "has_drift": bool(failed),
                    "critical_drift_count": len(failed),
                    "missing_external_evidence_count": sum(1 for row in failed if "exists" in str(row.get("check_id")) or "required" in str(row.get("check_id"))),
                },
                "incident_candidates": [{"incident_id": f"incident-{index + 1:03d}", "source_check_id": row.get("check_id"), "severity": "critical", "status": "draft"} for index, row in enumerate(failed)],
                "remediation_draft": {"manual_actions": [{"source_check_id": row.get("check_id"), "status": "manual_required"} for row in failed], "safe_actions": []},
                "summary": {"critical_drift_count": len(failed), "check_count": len(checks)},
            }
        )
        write_json(self.review_report_path(program_id, review_id), review)
        write_json(self.latest_review_path(program_id), {"review_id": review_id, "review_hash": review.get("integrity_hash"), "status": review.get("status")})
        return review

    def refresh_lifecycle_audit(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        history = self.program_store.read_history(program_id)
        change_history = self.read_change_history(program_id)
        checks = _history_checks("program", history) + _history_checks("change_control", change_history)
        signoff_count = sum(1 for row in history if row.get("event_type") == "unified_release_program_signoff_created")
        reset_count = sum(1 for row in history if row.get("event_type") == "unified_release_program_signoff_reset")
        failed = [row for row in checks if row.get("status") == "failed"]
        ledger = self._lifecycle_ledger(program_id, history, change_history)
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
                "package_type": UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE,
                "program_id": program_id,
                "created_at": now_iso(),
                "status": "failed" if failed else "passed",
                "summary": {"signoff_count": signoff_count, "reset_count": reset_count, "latest_program_status": self.program_store.latest_signoff_state(program_id).get("status"), "history_chain_valid": not failed},
                "checks": checks,
                "ledger": {"event_count": len(ledger), "latest_event_hash": ledger[-1].get("event_hash") if ledger else "", "signoff_event_count": signoff_count, "reset_event_count": reset_count},
                "source_hash": stable_hash({"program_history": [row.get("event_hash") for row in history], "change_history": [row.get("event_hash") for row in change_history]}),
            }
        )
        self.lifecycle_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.lifecycle_report_path(program_id), report)
        self.lifecycle_ledger_path(program_id).write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
        write_json(self.lifecycle_index_path(program_id), _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_lifecycle_index", "program_id": program_id, "source_hash": report.get("source_hash"), "summary": report.get("summary")}))
        return report

    def export_operations_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        docs = self._archive_documents(program_id, payload)
        archive_dir = self.archive_dir(program_id)
        if archive_dir.exists():
            shutil.rmtree(archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        files: list[dict[str, Any]] = []

        def write_entry(rel: str, value: dict[str, Any] | str) -> None:
            path = archive_dir / rel
            if isinstance(value, str):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)
            files.append(_file_record(path, rel))

        write_entry("program-summary.json", docs["program"])
        write_entry("program-verification-summary.json", docs["program_verification"])
        write_entry("program-signoff-summary.json", docs["signoff"])
        write_entry("program-signoff-binding-summary.json", docs["binding"])
        write_entry("external-evidence-manifest-summary.json", docs["external_manifest"])
        write_entry("change-control-summary.json", docs["change_control"])
        write_entry("continuous-review-summary.json", docs["review"])
        write_entry("lifecycle-audit-summary.json", docs["lifecycle"])
        write_entry("evidence-index.json", docs["evidence"])
        write_entry("history/program-history.jsonl", _history_text(self.program_store.read_history(program_id)))
        write_entry("history/change-control-history.jsonl", _history_text(self.read_change_history(program_id)))
        write_entry("README.txt", "MusicForge Unified Release Program Operations Archive\n")
        manifest = _operations_manifest(program_id, docs, files)
        write_json(self.archive_manifest_path(program_id), manifest)
        return manifest

    def build_operations_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.export_operations_archive(program_id, payload or {})
        archive_dir = self.archive_dir(program_id)
        zip_path = self.archive_zip_path(program_id)
        if zip_path.exists():
            zip_path.unlink()
        ArchiveBuilder.build_directory_zip(archive_dir, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            entries = sorted(info.filename for info in archive.infolist())
        manifest = read_json(self.archive_manifest_path(program_id))
        manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
        manifest["files"] = [_file_record(path, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(self.archive_manifest_path(program_id), manifest)
        zip_path.unlink(missing_ok=True)
        ArchiveBuilder.build_directory_zip(archive_dir, zip_path)
        return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_operations_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_unified_release_program_operations_package(
            self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_signed_program=bool(payload.get("require_signed_program", True)),
            require_continuous_review_clear=bool(payload.get("require_continuous_review_clear", True)),
            require_lifecycle_audit=bool(payload.get("require_lifecycle_audit", True)),
            program_zip_path=payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id),
            program_verification_report_path=payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id),
            program_signoff_binding_path=payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id),
        )
        write_unified_release_program_operations_verification_report(report, self.archive_verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, operations_archive_zip_path: Path | str | None = None, operations_archive_verification_report_path: Path | str | None = None, **payload: Any) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        if self.program_store.latest_signoff_state(program_id).get("status") != "signed":
            return _gate_failed("Unified Release Program is not currently signed.")
        zip_path = Path(operations_archive_zip_path) if operations_archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(operations_archive_verification_report_path) if operations_archive_verification_report_path else self.archive_verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Operations Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Operations Archive verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_operations_package(
                zip_path,
                strict=True,
                require_current=True,
                require_signed_program=True,
                require_continuous_review_clear=True,
                require_lifecycle_audit=True,
                program_zip_path=payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id),
                program_verification_report_path=payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id),
                program_signoff_binding_path=payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id),
                external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program Operations verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program Operations verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program Operations verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program Operations gate passed.", "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def read_change_history(self, program_id: str) -> list[dict[str, Any]]:
        return HistoryChain(self.change_history_path(program_id), sanitizer=sanitize_metadata).read()

    def _current_program_binding(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        if self.program_store.latest_signoff_state(program_id).get("status") != "signed":
            raise UnifiedReleaseProgramOperationsStateError("Unified Release Program must be currently signed.")
        program_zip = Path(payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id))
        verification_path = Path(payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id))
        binding_path = Path(payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id))
        external_manifest_path = Path(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id))
        runtime = verify_unified_release_program_package(program_zip, strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=external_manifest_path, program_signoff_binding_path=binding_path)
        verification = read_json(verification_path) if verification_path.exists() else {}
        if verification.get("package_type") != UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE:
            raise UnifiedReleaseProgramOperationsStateError("Current Program verification report package type is invalid.")
        if runtime.get("status") != "passed" or verification.get("status") != "passed":
            raise UnifiedReleaseProgramOperationsStateError("Current Program verification must be passed.")
        if verification.get("zip_sha256") != runtime.get("zip_sha256") or verification.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramOperationsStateError("Current Program verification report is stale.")
        signoff = read_json(self.program_store.signoff_path(program_id))
        binding = read_json(binding_path)
        external_manifest = read_json(external_manifest_path)
        return sanitize_metadata(
            {
                "program_id": program_id,
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "signoff_binding_hash": binding.get("integrity_hash"),
                "program_zip_sha256": _sha256_path(program_zip),
                "program_zip_size_bytes": program_zip.stat().st_size if program_zip.exists() else 0,
                "program_manifest_hash": runtime.get("manifest_hash"),
                "verification_report_hash": _integrity_hash(verification),
                "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
                "source_hash": signoff.get("source_hash"),
            }
        )

    def _program_binding_best_effort(self, program_id: str) -> ImplementationDocument:
        try:
            return self._current_program_binding(program_id, {})
        except Exception:
            state = self.program_store.latest_signoff_state(program_id)
            return {"program_id": program_id, "signoff_state": state.get("status"), "signoff_hash": state.get("signoff_hash")}

    def _current_program_state(self, program_id: str, payload: ImplementationDocument, *, require: bool) -> ImplementationDocument:
        checks: list[dict[str, Any]] = []
        state: dict[str, Any] = {"checks": checks}
        if not require:
            return state
        latest = self.program_store.latest_signoff_state(program_id)
        checks.append(_check("program_currently_signed", latest.get("status") == "signed", "Program is currently signed.", {"status": latest.get("status")}))
        if latest.get("status") != "signed":
            return state
        paths = {
            "program_zip": Path(payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id)),
            "program_verification_report": Path(payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id)),
            "program_signoff_binding": Path(payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id)),
            "external_evidence_manifest": Path(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id)),
        }
        for key, path in paths.items():
            checks.append(_check(f"program_{key}_exists", path.exists(), f"{key} exists.", {"path": str(path)}))
        if any(row.get("status") == "failed" for row in checks):
            return state
        external = read_json(paths["program_verification_report"])
        binding = read_json(paths["program_signoff_binding"])
        evidence_manifest = read_json(paths["external_evidence_manifest"])
        runtime = verify_unified_release_program_package(paths["program_zip"], strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=paths["external_evidence_manifest"], program_signoff_binding_path=paths["program_signoff_binding"])
        checks.extend(
            [
                _check("program_runtime_verification_passed", runtime.get("status") == "passed", "Program runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
                _check("program_external_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, "Program external verification report package type is valid."),
                _check("program_external_verification_passed", external.get("status") == "passed" and _integrity_ok(external), "Program external verification report passed."),
                _check("program_zip_sha256_current", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(paths["program_zip"]), "Program ZIP hash matches runtime and report."),
                _check("program_manifest_hash_current", external.get("manifest_hash") == runtime.get("manifest_hash"), "Program manifest hash matches runtime and report."),
                _check("program_signoff_binding_integrity", _integrity_ok(binding), "Program signoff binding integrity is valid."),
                _check("program_external_manifest_integrity", _integrity_ok(evidence_manifest), "Program external evidence manifest integrity is valid."),
            ]
        )
        state.update({"program_zip_sha256": _sha256_path(paths["program_zip"]), "program_zip_size_bytes": paths["program_zip"].stat().st_size, "program_manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "verification_status": external.get("status"), "runtime_status": runtime.get("status"), "signoff_binding_hash": binding.get("integrity_hash"), "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash")})
        return sanitize_metadata(state)

    def _assert_request_current(self, program_id: str, request: ImplementationDocument, payload: ImplementationDocument) -> None:
        current = self._current_program_binding(program_id, payload)
        expected = _as_document(request.get("source"))
        fields = ("signoff_hash", "signoff_binding_hash", "program_zip_sha256", "program_manifest_hash", "verification_report_hash", "external_evidence_manifest_hash", "source_hash")
        mismatched = [field for field in fields if current.get(field) != expected.get(field)]
        if mismatched:
            raise UnifiedReleaseProgramOperationsStateError(f"Program Change Request binding is stale: {', '.join(mismatched)}")

    def _archive_documents(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        current = self._current_program_state(program_id, payload, require=True)
        failures = [row for row in current.get("checks", []) if row.get("status") == "failed"]
        if failures:
            raise UnifiedReleaseProgramOperationsStateError("Current Program evidence failed verification.")
        program = self.program_store.read_program(program_id)
        verification = read_json(Path(payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id)))
        signoff = read_json(self.program_store.signoff_path(program_id))
        binding = read_json(Path(payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id)))
        external_manifest = read_json(Path(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id)))
        review = self.refresh_continuous_review(program_id, payload)
        lifecycle = self.refresh_lifecycle_audit(program_id, payload)
        change_control = self.refresh_change_control_report(program_id)
        program_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_program_summary", "program_id": program_id, "status": program.get("status"), "program_zip_sha256": current.get("program_zip_sha256"), "program_manifest_hash": current.get("program_manifest_hash"), "signoff_hash": signoff.get("integrity_hash")})
        verification_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_program_verification_summary", "program_id": program_id, "verification_status": verification.get("status"), "verification_report_hash": _integrity_hash(verification), "zip_sha256": verification.get("zip_sha256"), "manifest_hash": verification.get("manifest_hash")})
        signoff_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_signoff_summary", "program_id": program_id, "status": signoff.get("status"), "signed_by": signoff.get("signed_by"), "role": signoff.get("role"), "signed_at": signoff.get("signed_at"), "signoff_hash": signoff.get("integrity_hash"), "signoff_binding_hash": binding.get("integrity_hash")})
        external_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_external_evidence_manifest_summary", "program_id": program_id, "external_manifest_hash": external_manifest.get("integrity_hash"), "item_count": len(external_manifest.get("items", []))})
        evidence = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_evidence_index", "program_id": program_id, "items": [{"evidence_type": "program", **current}, {"evidence_type": "continuous_review", "status": review.get("status"), "review_hash": review.get("integrity_hash")}, {"evidence_type": "lifecycle_audit", "status": lifecycle.get("status"), "lifecycle_hash": lifecycle.get("integrity_hash")}], "summary": {"item_count": 3}})
        return {"program": program_summary, "program_verification": verification_summary, "signoff": signoff_summary, "binding": binding, "external_manifest": external_summary, "change_control": change_control, "review": review, "lifecycle": lifecycle, "evidence": evidence}

    def _assert_archive_current(self, program_id: str, payload: ImplementationDocument) -> None:
        manifest = read_json(self.archive_manifest_path(program_id))
        docs = self._archive_documents(program_id, payload)
        expected_source = _archive_source(docs)
        if manifest.get("source") != expected_source:
            raise UnifiedReleaseProgramOperationsStateError("Program Operations Archive export is stale. Re-export before ZIP.")

    def _request_summary(self, program_id: str, request: ImplementationDocument) -> ImplementationDocument:
        request_id = str(request.get("change_request_id") or "")
        approval = read_json(self.approval_path(program_id, request_id)) if self.approval_path(program_id, request_id).exists() else {}
        reset = read_json(self.reset_proof_path(program_id, request_id)) if self.reset_proof_path(program_id, request_id).exists() else {}
        return sanitize_metadata({"change_request_id": request_id, "status": request.get("status"), "change_type": request.get("change_type"), "reason": request.get("reason"), "request_hash": request.get("integrity_hash"), "approval_hash": approval.get("integrity_hash") or request.get("approval_hash"), "reset_proof_hash": reset.get("integrity_hash") or request.get("reset_proof_hash"), "reset_event_hash": request.get("reset_event_hash"), "previous_signoff_hash": (request.get("target") or {}).get("program_signoff_hash")})

    def _append_change_history(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        return HistoryChain(self.change_history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _lifecycle_ledger(self, program_id: str, program_history: list[ImplementationDocument], change_history: list[ImplementationDocument]) -> list[ImplementationDocument]:
        rows = []
        previous = ""
        source_rows = [("program_history", row) for row in program_history] + [("change_control_history", row) for row in change_history]
        for index, (source, raw) in enumerate(source_rows, start=1):
            event = HistoryChain.build_event(
                {"event_id": f"uple-{index:06d}", "source": source, "event_type": raw.get("event_type"), "created_at": raw.get("created_at"), "program_id": program_id, "signoff_hash": raw.get("signoff_hash") or raw.get("previous_signoff_hash"), "change_request_id": raw.get("change_request_id"), "source_event_hash": raw.get("event_hash")},
                previous_event_hash=previous,
                sanitizer=sanitize_metadata,
            )
            previous = event["event_hash"]
            rows.append(event)
        return rows

    def _next_request_id(self, program_id: str) -> str:
        base = self.change_dir(program_id) / "change-requests"
        base.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in base.glob("urpcr-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"urpcr-{max_seen + 1:06d}"

    def _next_runbook_id(self, program_id: str) -> str:
        base = self.ops_dir(program_id) / "runbooks"
        base.mkdir(parents=True, exist_ok=True)
        return f"urprb-{len([path for path in base.glob('urprb-*')]) + 1:06d}"

    def _next_review_id(self, program_id: str) -> str:
        base = self.ops_dir(program_id) / "continuous-reviews"
        base.mkdir(parents=True, exist_ok=True)
        return f"urpcrv-{len([path for path in base.glob('urpcrv-*')]) + 1:06d}"


def _operations_manifest(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": _archive_source(docs),
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "sidecars": {
                "program_signoff_binding_hash": docs["binding"].get("integrity_hash"),
                "continuous_review_hash": docs["review"].get("integrity_hash"),
                "lifecycle_audit_hash": docs["lifecycle"].get("integrity_hash"),
            },
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _archive_source(docs: ImplementationDocument) -> ImplementationDocument:
    return {
        "program_summary_hash": docs["program"].get("integrity_hash"),
        "program_verification_summary_hash": docs["program_verification"].get("integrity_hash"),
        "program_signoff_summary_hash": docs["signoff"].get("integrity_hash"),
        "program_signoff_binding_summary_hash": docs["binding"].get("integrity_hash"),
        "external_evidence_manifest_summary_hash": docs["external_manifest"].get("integrity_hash"),
        "change_control_summary_hash": docs["change_control"].get("integrity_hash"),
        "continuous_review_summary_hash": docs["review"].get("integrity_hash"),
        "lifecycle_audit_summary_hash": docs["lifecycle"].get("integrity_hash"),
        "evidence_index_hash": docs["evidence"].get("integrity_hash"),
    }


def _runbook_summary(items: list[ImplementationDocument]) -> ImplementationDocument:
    return {
        "safe_count": sum(1 for row in items if row.get("safe")),
        "completed_count": sum(1 for row in items if row.get("status") == "completed"),
        "manual_required_count": sum(1 for row in items if row.get("status") == "manual_required"),
        "failed_count": sum(1 for row in items if row.get("status") == "failed"),
        "skipped_unsupported_count": sum(1 for row in items if row.get("status") == "skipped_unsupported"),
    }


def _history_checks(prefix: str, rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    checks = []
    previous = ""
    for index, event in enumerate(rows):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"{prefix}_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History payload hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    return checks


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}}


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip("-")[:140]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
