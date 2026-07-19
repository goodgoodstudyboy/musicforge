# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import GenerationRef as GenerationRef, ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, GenerationService as GenerationService, HistoryChain as HistoryChain, ResetService as ResetService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore as UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore, _bounded as _bounded, _gate_failed as _gate_failed, _history_text as _history_text, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _read_optional_json as _read_optional_json, _safe_id as _safe_id, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import (
    ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, command_center_acceptance_change_lifecycle_semantic_checks as command_center_acceptance_change_lifecycle_semantic_checks, command_center_acceptance_change_previous_evidence_checks as command_center_acceptance_change_previous_evidence_checks, command_center_acceptance_change_reset_semantic_checks as command_center_acceptance_change_reset_semantic_checks, verify_unified_release_program_continuity_command_center_acceptance_change_package as verify_unified_release_program_continuity_command_center_acceptance_change_package, write_unified_release_program_continuity_command_center_acceptance_change_verification_report as write_unified_release_program_continuity_command_center_acceptance_change_verification_report

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

UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError')
_reject_forbidden_payload = _make_deferred_global('_reject_forbidden_payload')
action = _make_deferred_global('action')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
value = _make_deferred_global('value')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError, _reject_forbidden_payload, action, key, read_json, value, write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError)
    _reject_forbidden_payload = namespace.get('_reject_forbidden_payload', _reject_forbidden_payload)
    action = namespace.get('action', action)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    value = namespace.get('value', value)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_receiver_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_receiver_acceptance_signoff"




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreReadinessMixin:
    def change_dir(self, program_id: str) -> Path:
        return self.acceptance_store.acceptance_dir(program_id) / "change-control"

    def requests_dir(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "change-requests"

    def request_dir(self, program_id: str, request_id: str) -> Path:
        return self.requests_dir(program_id) / _safe_id(request_id)

    def request_path(self, program_id: str, request_id: str) -> Path:
        return self.request_dir(program_id, request_id) / "change-request.json"

    def approval_path(self, program_id: str, request_id: str) -> Path:
        return self.request_dir(program_id, request_id) / "change-request-approval.json"

    def request_binding_path(self, program_id: str, request_id: str) -> Path:
        return self.request_dir(program_id, request_id) / "change-request-binding-report.json"

    def reset_proofs_dir(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "reset-proofs"

    def reset_proof_path(self, program_id: str, reset_id: str) -> Path:
        return self.reset_proofs_dir(program_id) / _safe_id(reset_id) / "reset-proof.json"

    def reset_binding_path(self, program_id: str, reset_id: str) -> Path:
        return self.reset_proofs_dir(program_id) / _safe_id(reset_id) / "reset-proof-binding-summary.json"

    def current_generation_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "current-generation.json"

    def state_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "change-control-state.json"

    def request_index_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "change-request-index.json"

    def reset_index_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "reset-proof-index.json"

    def lifecycle_report_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "lifecycle-report.json"

    def lifecycle_event_log_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "lifecycle-event-log.jsonl"

    def generations_dir(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "generations"

    def generation_dir(self, program_id: str, generation: int) -> Path:
        return self.generations_dir(program_id) / f"generation-{generation:06d}"

    def archive_export_dir(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "change-control-archive"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "cc-archive.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.change_dir(program_id) / "cc-verification-report.json"

    def get_state(self, program_id: str) -> DomainDocument:
        return {
            "state": _read_optional_json(self.state_path(program_id)),
            "current_generation": _read_optional_json(self.current_generation_path(program_id)),
            "change_requests": self.list_change_requests(program_id),
            "reset_proofs": self.list_reset_proofs(program_id),
            "lifecycle_report": _read_optional_json(self.lifecycle_report_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def create_change_request(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        _reject_forbidden_payload(payload, "Receiver Acceptance Change Request")
        with self.lock:
            current = self._current_acceptance_state(program_id)
            self._sync_acceptance_lifecycle_event(program_id)
            existing = self._existing_open_request(program_id, current.get("signoff_hash"))
            if existing:
                return existing
            request_id = _safe_id(str(payload.get("change_request_id") or self._next_request_id(program_id)))
            if self.request_path(program_id, request_id).exists():
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(f"Command Center Receiver Acceptance Change Request already exists: {request_id}")
            now = now_iso()
            allowed_actions = list(payload.get("allowed_actions") or [RESET_ACTION])
            if _bounded(payload.get("change_type") or RESET_CHANGE_TYPE, 160) != RESET_CHANGE_TYPE:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Receiver Acceptance Change Request change_type must be reset_receiver_acceptance_signoff."
                )
            if allowed_actions != [RESET_ACTION]:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Receiver Acceptance Change Request must authorize only reset_receiver_acceptance_signoff."
                )
            request = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "submitted",
                    "change_type": _bounded(payload.get("change_type") or RESET_CHANGE_TYPE, 160),
                    "allowed_actions": [_bounded(action, 160) for action in allowed_actions],
                    "reason": _bounded(payload.get("reason") or "Command Center Receiver Acceptance evidence requires controlled reset.", 1000),
                    "requested_by": _bounded(payload.get("requested_by") or "continuity-operator", 120),
                    "created_at": now,
                    "updated_at": now,
                    "target": self._target_from_state(current),
                    "source": current,
                    "tool": {"name": "MusicForge Command Center Receiver Acceptance Change Control", "version": __version__},
                }
            )
            request["payload_hash"] = stable_hash({key: value for key, value in request.items() if key not in {"payload_hash", "integrity_hash"}})
            request["integrity_hash"] = _integrity_hash(request)
            self.request_dir(program_id, request_id).mkdir(parents=True, exist_ok=True)
            write_json(self.request_path(program_id, request_id), request)
            self._write_request_binding(program_id, request, None, current)
            self._append_lifecycle_event(
                program_id,
                {
                    "event_type": "receiver_acceptance_change_request_submitted",
                    "created_at": now,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "request_hash": request.get("integrity_hash"),
                    "target_signoff_hash": current.get("signoff_hash"),
                },
            )
            self.refresh_lifecycle_audit(program_id)
            return request

    def approve_change_request(self, program_id: str, request_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        _reject_forbidden_payload(payload, "Receiver Acceptance Change Request approval")
        request_id = _safe_id(request_id)
        with self.lock:
            request = self.read_change_request(program_id, request_id)
            if request.get("status") not in {"submitted", "draft"}:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Only submitted Command Center Receiver Acceptance Change Requests can be approved.")
            current = self._assert_request_current(program_id, request)
            if "target" in payload and payload.get("target") != request.get("target"):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Receiver Acceptance approval target cannot differ from the Change Request."
                )
            if "source" in payload and payload.get("source") != request.get("source"):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Receiver Acceptance approval source cannot differ from the Change Request."
                )
            now = now_iso()
            submitted_request_hash = request.get("integrity_hash")
            approved_actions = list(payload.get("approved_actions") or request.get("allowed_actions") or [])
            if approved_actions != list(request.get("allowed_actions") or []):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Receiver Acceptance approval actions must exactly match the Change Request."
                )
            approval = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_change_approval",
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "approved",
                    "approved_by": _bounded(payload.get("approved_by") or "continuity-acceptance-owner", 120),
                    "role": _bounded(payload.get("role") or "program_owner", 80),
                    "reason": _bounded(payload.get("reason") or request.get("reason") or "Approved continuity acceptance reset.", 1000),
                    "approved_actions": [_bounded(action, 160) for action in approved_actions],
                    "approved_at": now,
                    "request_payload_hash": request.get("payload_hash"),
                    "request_hash": submitted_request_hash,
                    "target": request.get("target"),
                    "source": request.get("source"),
                }
            )
            approval["payload_hash"] = stable_hash({key: value for key, value in approval.items() if key not in {"payload_hash", "integrity_hash"}})
            approval["integrity_hash"] = _integrity_hash(approval)
            request["status"] = "approved"
            request["submitted_request_hash"] = submitted_request_hash
            request["approval_hash"] = approval.get("integrity_hash")
            request["approved_at"] = now
            request["updated_at"] = now
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.request_path(program_id, request_id), request)
            write_json(self.approval_path(program_id, request_id), approval)
            self._write_request_binding(program_id, request, approval, current)
            self._append_lifecycle_event(
                program_id,
                {
                    "event_type": "receiver_acceptance_change_request_approved",
                    "created_at": now,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "target_signoff_hash": current.get("signoff_hash"),
                },
            )
            self.refresh_lifecycle_audit(program_id)
            return approval

    def reset_receiver_acceptance_signoff(self, program_id: str, request_id: str | DomainDocument | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        if isinstance(request_id, dict):
            payload = request_id
            request_id = None
        payload = payload or {}
        _reject_forbidden_payload(payload, "Receiver Acceptance reset")
        request_id = _safe_id(str(request_id or payload.get("change_request_id") or ""))
        if not request_id:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("change_request_id is required for Command Center Receiver Acceptance reset.")
        with self.lock:
            request = self.read_change_request(program_id, request_id)
            if request.get("status") != "approved" or request.get("applied_at"):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request must be approved and unused before reset.")
            if request.get("change_type") != RESET_CHANGE_TYPE:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request is not scoped to signoff reset.")
            if RESET_ACTION not in set(request.get("allowed_actions") or []):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request does not allow reset_receiver_acceptance_signoff.")
            approval = read_json(self.approval_path(program_id, request_id))
            try:
                ChangeRequestService.validate_reset_authorization(
                    request,
                    approval,
                    ResetAuthorization(program_id, request_id, RESET_ACTION, RESET_CHANGE_TYPE, request.get("target") or {}, request.get("source") or {}),
                )
            except ValueError as exc:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(str(exc)) from exc
            request_binding = read_json(self.request_binding_path(program_id, request_id))
            if (
                approval.get("package_type") != "musicforge_unified_release_program_continuity_command_center_acceptance_change_approval"
                or not _integrity_ok(approval)
                or approval.get("status") != "approved"
                or approval.get("program_id") != program_id
                or approval.get("change_request_id") != request_id
            ):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request approval integrity failed.")
            if list(approval.get("approved_actions") or []) != [RESET_ACTION]:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request approval does not allow reset.")
            if approval.get("target") != request.get("target") or approval.get("source") != request.get("source"):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request approval binding mismatch.")
            if (
                not _integrity_ok(request_binding)
                or request_binding.get("request_hash") != request.get("integrity_hash")
                or request_binding.get("approval_hash") != approval.get("integrity_hash")
                or request_binding.get("target") != request.get("target")
                or request_binding.get("source") != request.get("source")
            ):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Command Center Receiver Acceptance Change Request binding report is invalid."
                )
            current = self._assert_request_current(program_id, request)
            now = now_iso()
            previous_generation = int(current.get("generation") or 1)
            reset_id = f"reset-{len(self.list_reset_proofs(program_id)) + 1:06d}"
            approved_request_hash = request.get("integrity_hash")
            reset_event = self.acceptance_store._append_history(
                program_id,
                {
                    "event_type": "receiver_acceptance_signoff_reset",
                    "created_at": now,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "approval_hash": approval.get("integrity_hash"),
                    "previous_signoff_hash": current.get("signoff_hash"),
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "previous_archive_zip_sha256": current.get("archive_zip_sha256"),
                    "previous_archive_manifest_hash": current.get("archive_manifest_hash"),
                    "previous_verification_report_hash": current.get("verification_report_hash"),
                    "reset_by": _bounded(payload.get("reset_by") or approval.get("approved_by") or "continuity-acceptance-owner", 120),
                    "reason": _bounded(payload.get("reason") or approval.get("reason") or "Approved Command Center Receiver Acceptance reset.", 1000),
                },
            )
            proof = ResetService.build_proof(sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof",
                    "program_id": program_id,
                    "reset_id": reset_id,
                    "change_request_id": request_id,
                    "status": "applied",
                    "applied_at": now,
                    "request_hash": approved_request_hash,
                    "approval_hash": approval.get("integrity_hash"),
                    "previous_generation": previous_generation,
                    "next_generation": previous_generation + 1,
                    "previous_signoff_hash": current.get("signoff_hash"),
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "previous_archive_zip_sha256": current.get("archive_zip_sha256"),
                    "previous_archive_size_bytes": current.get("archive_size_bytes"),
                    "previous_archive_manifest_hash": current.get("archive_manifest_hash"),
                    "previous_verification_report_hash": current.get("verification_report_hash"),
                    "previous_signoff_history_event_hash": current.get("history_event_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "reset_event_payload_hash": reset_event.get("payload_hash"),
                    "cr_binding_report_hash": request_binding.get("integrity_hash"),
                    "source": current,
                }
            ))
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof_binding_summary",
                    "program_id": program_id,
                    "reset_id": reset_id,
                    "change_request_id": request_id,
                    "reset_proof_hash": proof.get("integrity_hash"),
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "cr_binding_report_hash": request_binding.get("integrity_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "previous_signoff_hash": current.get("signoff_hash"),
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "previous_archive_zip_sha256": current.get("archive_zip_sha256"),
                    "previous_archive_manifest_hash": current.get("archive_manifest_hash"),
                    "previous_verification_report_hash": current.get("verification_report_hash"),
                    "previous_signoff_history_event_hash": current.get("history_event_hash"),
                    "previous_generation": previous_generation,
                    "next_generation": previous_generation + 1,
                    "single_use_consumed": True,
                }
            )
            self.reset_proof_path(program_id, reset_id).parent.mkdir(parents=True, exist_ok=True)
            write_json(self.reset_proof_path(program_id, reset_id), proof)
            write_json(self.reset_binding_path(program_id, reset_id), binding)
            request = ResetService.mark_applied(
                request,
                applied_at=now,
                proof_hash=str(proof.get("integrity_hash") or ""),
                event_hash=str(reset_event.get("event_hash") or ""),
                updates={"approved_request_hash": approved_request_hash, "reset_id": reset_id, "updated_at": now},
            )
            write_json(self.request_path(program_id, request_id), request)
            lifecycle_event = self._append_lifecycle_event(
                program_id,
                {
                    "event_type": "receiver_acceptance_signoff_reset_applied",
                    "created_at": now,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "reset_id": reset_id,
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "reset_proof_hash": proof.get("integrity_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "previous_signoff_hash": current.get("signoff_hash"),
                    "next_generation": previous_generation + 1,
                },
            )
            binding["lifecycle_event_hash"] = lifecycle_event.get("event_hash")
            binding["integrity_hash"] = _integrity_hash(binding)
            write_json(self.reset_binding_path(program_id, reset_id), binding)
            self.acceptance_store.mark_reset_pending(program_id, proof, binding)
            snapshot = self.generation_dir(program_id, previous_generation) / "acceptance-snapshot"
            if snapshot.exists():
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Receiver Acceptance Change Control generation snapshot already exists."
                )
            snapshot.mkdir(parents=True, exist_ok=False)
            if self.archive_zip_path(program_id).is_file():
                shutil.copy2(self.archive_zip_path(program_id), snapshot / "receiver-acceptance-change-control-archive.zip")
            if self.verification_report_path(program_id).is_file():
                shutil.copy2(
                    self.verification_report_path(program_id),
                    snapshot / "receiver-acceptance-change-control-verification-report.json",
                )
            if self.archive_export_dir(program_id).is_dir():
                shutil.copytree(
                    self.archive_export_dir(program_id),
                    snapshot / "change-control-archive-export",
                )
                shutil.rmtree(self.archive_export_dir(program_id))
            self.archive_zip_path(program_id).unlink(missing_ok=True)
            self.verification_report_path(program_id).unlink(missing_ok=True)
            self._write_generation(program_id, previous_generation + 1, "reset_pending", proof)
            self.refresh_lifecycle_audit(program_id)
            return proof

    def refresh_lifecycle_audit(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            self._sync_acceptance_lifecycle_event(program_id)
            state = self._change_control_state(program_id)
            request_index = self._change_request_index(program_id)
            reset_index = self._reset_proof_index(program_id)
            lifecycle = self._lifecycle_report(program_id, state, request_index, reset_index)
            self.change_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.state_path(program_id), state)
            write_json(self.request_index_path(program_id), request_index)
            write_json(self.reset_index_path(program_id), reset_index)
            write_json(self.lifecycle_report_path(program_id), lifecycle)
            return lifecycle
