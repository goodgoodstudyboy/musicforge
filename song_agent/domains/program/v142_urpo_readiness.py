# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
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

UnifiedReleaseProgramOperationsNotFoundError = _make_deferred_global('UnifiedReleaseProgramOperationsNotFoundError')
UnifiedReleaseProgramOperationsStateError = _make_deferred_global('UnifiedReleaseProgramOperationsStateError')
_bounded = _make_deferred_global('_bounded')
_file_record = _make_deferred_global('_file_record')
_history_checks = _make_deferred_global('_history_checks')
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_operations_manifest = _make_deferred_global('_operations_manifest')
_runbook_summary = _make_deferred_global('_runbook_summary')
_safe_id = _make_deferred_global('_safe_id')
_with_integrity = _make_deferred_global('_with_integrity')
index = _make_deferred_global('index')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramOperationsNotFoundError, UnifiedReleaseProgramOperationsStateError, _bounded, _file_record, _history_checks, _history_text, _integrity_hash, _integrity_ok
    global _operations_manifest, _runbook_summary, _safe_id, _with_integrity, index, key, read_json
    global write_json
    UnifiedReleaseProgramOperationsNotFoundError = namespace.get('UnifiedReleaseProgramOperationsNotFoundError', UnifiedReleaseProgramOperationsNotFoundError)
    UnifiedReleaseProgramOperationsStateError = namespace.get('UnifiedReleaseProgramOperationsStateError', UnifiedReleaseProgramOperationsStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _file_record = namespace.get('_file_record', _file_record)
    _history_checks = namespace.get('_history_checks', _history_checks)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _operations_manifest = namespace.get('_operations_manifest', _operations_manifest)
    _runbook_summary = namespace.get('_runbook_summary', _runbook_summary)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    index = namespace.get('index', index)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)






class UnifiedReleaseProgramOperationsStoreReadinessMixin:
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

    def create_change_request(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def approve_change_request(self, program_id: str, request_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def reset_program_signoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def read_change_request(self, program_id: str, request_id: str) -> DomainDocument:
        path = self.request_path(program_id, request_id)
        if not path.exists():
            raise UnifiedReleaseProgramOperationsNotFoundError(f"Program Change Request not found: {request_id}")
        return read_json(path)

    def list_change_requests(self, program_id: str) -> list[DomainDocument]:
        base = self.change_dir(program_id) / "change-requests"
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*/program-change-request.json"))]

    def refresh_change_control_report(self, program_id: str) -> DomainDocument:
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

    def create_runbook(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def run_safe(self, program_id: str, runbook_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def refresh_continuous_review(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def refresh_lifecycle_audit(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def export_operations_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        docs = self._archive_documents(program_id, payload)
        archive_dir = self.archive_dir(program_id)
        if archive_dir.exists():
            shutil.rmtree(archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        files: list[DomainDocument] = []

        def write_entry(rel: str, value: DomainDocument | str) -> None:
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
