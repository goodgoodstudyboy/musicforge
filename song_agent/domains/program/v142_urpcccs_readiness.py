# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import os as os
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.lifecycle import HistoryChain as HistoryChain
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center import UnifiedReleaseProgramContinuityCommandCenterStore as UnifiedReleaseProgramContinuityCommandCenterStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import ARCHIVE_REQUIRED_ENTRIES as ARCHIVE_REQUIRED_ENTRIES, COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION as COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION, HANDOFF_REQUIRED_ENTRIES as HANDOFF_REQUIRED_ENTRIES, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package, write_unified_release_program_continuity_command_center_final_handoff_verification_report as write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report as write_unified_release_program_continuity_command_center_signoff_verification_report
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package

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

UnifiedReleaseProgramContinuityCommandCenterSignoffStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterSignoffStateError')
_bounded = _make_deferred_global('_bounded')
_build_zip = _make_deferred_global('_build_zip')
_check = _make_deferred_global('_check')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_read_optional_json = _make_deferred_global('_read_optional_json')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
_zip_result = _make_deferred_global('_zip_result')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
value = _make_deferred_global('value')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterSignoffStateError, _bounded, _build_zip, _check, _integrity_hash, _integrity_ok, _read_optional_json
    global _safe_id, _sha256_path, _with_integrity, _zip_result, key, read_json, row, value
    global write_json
    UnifiedReleaseProgramContinuityCommandCenterSignoffStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterSignoffStateError', UnifiedReleaseProgramContinuityCommandCenterSignoffStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _build_zip = namespace.get('_build_zip', _build_zip)
    _check = namespace.get('_check', _check)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    _zip_result = namespace.get('_zip_result', _zip_result)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    value = namespace.get('value', value)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_command_center_signoff"
RESET_CHANGE_TYPE = "reset_command_center_signoff"




class UnifiedReleaseProgramContinuityCommandCenterSignoffStoreReadinessMixin:
    def signoff_dir(self, program_id: str) -> Path:
        return self.command_store.command_dir(program_id) / "signoff"

    def signoff_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff-history.jsonl"

    def policy_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff-policy.json"

    def state_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff-state.json"

    def reset_proof_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff-reset-proof.json"

    def change_request_dir(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "change-requests"

    def change_request_path(self, program_id: str, request_id: str) -> Path:
        return self.change_request_dir(program_id) / _safe_id(request_id) / "change-request.json"

    def change_approval_path(self, program_id: str, request_id: str) -> Path:
        return self.change_request_dir(program_id) / _safe_id(request_id) / "change-approval.json"

    def archive_dir(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "archive"

    def archive_manifest_path(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "manifest.json"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "unified-release-program-continuity-command-center-signoff-archive.zip"

    def archive_verification_report_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "command-center-signoff-archive-verification-report.json"

    def final_handoff_dir(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "final-handoff"

    def final_handoff_zip_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "unified-release-program-continuity-command-center-final-handoff.zip"

    def final_handoff_verification_report_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "final-handoff-verification-report.json"

    def archive_history_dir(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "history"

    def get_state(self, program_id: str) -> DomainDocument:
        latest = self.latest_signoff_state(program_id)
        return {
            "program_id": program_id,
            "status": latest.get("status") or "unsigned",
            "latest_event": latest.get("event"),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "state": _read_optional_json(self.state_path(program_id)),
            "archive_zip_path": str(self.archive_zip_path(program_id)) if self.archive_zip_path(program_id).exists() else None,
            "archive_verification": _read_optional_json(self.archive_verification_report_path(program_id)),
            "final_handoff_zip_path": str(self.final_handoff_zip_path(program_id)) if self.final_handoff_zip_path(program_id).exists() else None,
        }

    def preflight(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        checks: list[DomainDocument] = []
        try:
            context = self._current_command_center_context(program_id, payload)
            report = context["report"]
            current_state = context["current_state"]
            checks.extend(
                [
                    _check("command_center_runtime", context["runtime"].get("status") == "passed", "Command Center runtime verification passed."),
                    _check("command_center_external_verification", context["external_verification"].get("status") == "passed", "Command Center external verification passed."),
                    _check("command_center_ready", report.get("status") == "ready", "Command Center report is ready."),
                    _check("command_center_no_blockers", not (report.get("blockers") or []), "Command Center has no blockers."),
                    _check("current_generation_signed", current_state.get("current") is True and current_state.get("acceptance_status") == "signed", "Current generation is signed."),
                ]
            )
        except Exception as exc:
            context = {}
            checks.append(_check("command_center_runtime", False, sanitize_sensitive_text(str(exc))))
        blockers = [row["check_id"] for row in checks if row.get("status") == "failed"]
        return {
            "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_preflight",
            "program_id": program_id,
            "status": "passed" if not blockers else "failed",
            "checks": checks,
            "blockers": blockers,
            "source": context.get("source") if context else {},
            "summary": context.get("report", {}).get("summary", {}) if context else {},
        }

    def signoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            self._assert_signoff_transition_allowed(program_id)
            preflight = self.preflight(program_id, payload)
            if preflight.get("status") != "passed":
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                    "Continuity Command Center signoff preflight failed: " + ", ".join(preflight.get("blockers") or [])
                )
            context = self._current_command_center_context(program_id, payload)
            now = now_iso()
            source = context["source"]
            signoff = sanitize_metadata(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff",
                    "program_id": program_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "program-owner", 120),
                    "role": _bounded(payload.get("role") or "release_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Program continuity command center accepted.", 1000),
                    "signed_at": now,
                    "source": source,
                    "summary": context["report"].get("summary", {}),
                    "tool": {"name": "MusicForge Continuity Command Center Signoff", "version": __version__},
                }
            )
            signoff = SignoffService.seal(signoff)
            self.signoff_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "command_center_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason_hash": stable_hash({"reason": signoff.get("reason")}),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": stable_hash(source),
                    "command_center_zip_sha256": source.get("command_center_zip_sha256"),
                    "command_center_manifest_hash": source.get("command_center_manifest_hash"),
                },
            )
            binding = self._signoff_binding(signoff, event)
            write_json(self.signoff_binding_path(program_id), binding)
            policy = _with_integrity(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_policy",
                    "program_id": program_id,
                    "require_runtime_ready": True,
                    "require_current_generation": True,
                    "require_external_signoff_binding": True,
                    "reset_action": RESET_ACTION,
                }
            )
            write_json(self.policy_path(program_id), policy)
            state = _with_integrity(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_state",
                    "program_id": program_id,
                    "status": "signed",
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_binding_hash": binding.get("integrity_hash"),
                    "signoff_event_hash": event.get("event_hash"),
                    "signed_at": now,
                    "archive_history_event_hash": None,
                    "handoff_history_event_hash": None,
                }
            )
            write_json(self.state_path(program_id), state)
            return signoff

    def create_change_request(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            context = self._signed_context(program_id, payload)
            request_id = _safe_id(str(payload.get("change_request_id") or self._next_request_id(program_id)))
            if self.change_request_path(program_id, request_id).exists():
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(f"Change Request already exists: {request_id}")
            source = context["signoff"].get("source") or {}
            request = sanitize_metadata(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_change_request",
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "submitted",
                    "change_type": _bounded(payload.get("change_type") or RESET_CHANGE_TYPE, 120),
                    "allowed_actions": list(payload.get("allowed_actions") or [RESET_ACTION]),
                    "requested_by": _bounded(payload.get("requested_by") or "program-operator", 120),
                    "reason": _bounded(payload.get("reason") or "Continuity Command Center evidence changed.", 1000),
                    "created_at": now_iso(),
                    "target": {
                        "signoff_hash": context["signoff"].get("integrity_hash"),
                        "signoff_binding_hash": context["binding"].get("integrity_hash"),
                        "command_center_zip_sha256": source.get("command_center_zip_sha256"),
                        "command_center_manifest_hash": source.get("command_center_manifest_hash"),
                        "command_center_verification_report_hash": source.get("command_center_verification_report_hash"),
                        "external_evidence_manifest_hash": source.get("external_evidence_manifest_hash"),
                    },
                    "applied_at": None,
                }
            )
            request["payload_hash"] = stable_hash({key: value for key, value in request.items() if key not in {"payload_hash", "integrity_hash"}})
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.change_request_path(program_id, request_id), request)
            return request

    def approve_change_request(self, program_id: str, request_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            request = self._read_change_request(program_id, request_id)
            if request.get("status") not in {"submitted", "draft"}:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Only submitted Change Requests can be approved.")
            self._assert_request_current(program_id, request)
            submitted_request_hash = request.get("integrity_hash")
            approval = sanitize_metadata(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_change_approval",
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "approved",
                    "approved_by": _bounded(payload.get("approved_by") or "program-owner", 120),
                    "role": _bounded(payload.get("role") or "program_owner", 80),
                    "reason": _bounded(payload.get("reason") or request.get("reason"), 1000),
                    "approved_actions": list(request.get("allowed_actions") or []),
                    "approved_at": now_iso(),
                    "request_hash": submitted_request_hash,
                    "target": request.get("target"),
                }
            )
            approval["payload_hash"] = stable_hash({key: value for key, value in approval.items() if key not in {"payload_hash", "integrity_hash"}})
            approval["integrity_hash"] = _integrity_hash(approval)
            request["status"] = "approved"
            request["submitted_request_hash"] = submitted_request_hash
            request["approval_hash"] = approval.get("integrity_hash")
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.change_request_path(program_id, request_id), request)
            write_json(self.change_approval_path(program_id, request_id), approval)
            return approval

    def reset_signoff(self, program_id: str, change_request_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            request = self._read_change_request(program_id, change_request_id)
            if not _integrity_ok(request) or request.get("status") != "approved" or request.get("applied_at"):
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Change Request must be approved, valid, and unused before reset.")
            if request.get("change_type") != RESET_CHANGE_TYPE or RESET_ACTION not in set(request.get("allowed_actions") or []):
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(f"Change Request does not authorize {RESET_ACTION}.")
            approval_path = self.change_approval_path(program_id, change_request_id)
            if not approval_path.exists():
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Change Request approval proof is missing.")
            approval = read_json(approval_path)
            try:
                ChangeRequestService.validate_reset_authorization(
                    request,
                    approval,
                    ResetAuthorization(
                        program_id,
                        change_request_id,
                        RESET_ACTION,
                        RESET_CHANGE_TYPE,
                        request.get("target") or {},
                        request.get("source") if "source" in request else None,
                    ),
                )
            except ValueError as exc:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(str(exc)) from exc
            request_identity_valid = (
                request.get("program_id") == program_id
                and request.get("change_request_id") == change_request_id
            )
            approval_identity_valid = (
                approval.get("package_type")
                == "musicforge_unified_release_program_continuity_command_center_signoff_change_approval"
                and approval.get("program_id") == program_id
                and approval.get("change_request_id") == change_request_id
                and approval.get("target") == request.get("target")
                and approval.get("request_hash") == request.get("submitted_request_hash")
                and request.get("approval_hash") == approval.get("integrity_hash")
            )
            if "source" in request or "source" in approval:
                approval_identity_valid = approval_identity_valid and approval.get("source") == request.get("source")
            if (
                not request_identity_valid
                or not _integrity_ok(approval)
                or approval.get("status") != "approved"
                or not approval_identity_valid
            ):
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Change Request approval proof is invalid.")
            self._assert_request_current(program_id, request)
            context = self._signed_context(program_id, payload)
            self._preserve_current_archive(program_id, context["signoff"].get("integrity_hash"))
            now = now_iso()
            event = self._append_history(
                program_id,
                {
                    "event_type": "command_center_signoff_reset",
                    "created_at": now,
                    "program_id": program_id,
                    "change_request_id": change_request_id,
                    "reset_by": _bounded(payload.get("reset_by") or approval.get("approved_by") or "program-owner", 120),
                    "previous_signoff_hash": context["signoff"].get("integrity_hash"),
                    "previous_signoff_binding_hash": context["binding"].get("integrity_hash"),
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                },
            )
            proof = ResetService.build_proof(_with_integrity(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_reset_proof",
                    "program_id": program_id,
                    "change_request_id": change_request_id,
                    "status": "applied",
                    "applied_at": now,
                    "previous_signoff_hash": context["signoff"].get("integrity_hash"),
                    "previous_signoff_binding_hash": context["binding"].get("integrity_hash"),
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "reset_event_hash": event.get("event_hash"),
                }
            ))
            write_json(self.reset_proof_path(program_id), proof)
            request = ResetService.mark_applied(
                request,
                applied_at=now,
                proof_hash=str(proof.get("integrity_hash") or ""),
                event_hash=str(event.get("event_hash") or ""),
            )
            write_json(self.change_request_path(program_id, change_request_id), request)
            for path in (self.signoff_path(program_id), self.signoff_binding_path(program_id)):
                path.unlink(missing_ok=True)
            state = _with_integrity(
                {
                    "schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_state",
                    "program_id": program_id,
                    "status": "reset",
                    "previous_signoff_hash": proof.get("previous_signoff_hash"),
                    "reset_proof_hash": proof.get("integrity_hash"),
                    "reset_event_hash": event.get("event_hash"),
                    "updated_at": now,
                }
            )
            write_json(self.state_path(program_id), state)
            self._clear_current_outputs(program_id)
            return proof

    def export_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            context = self._signed_context(program_id, payload)
            state = context["state"]
            exported_event = self._find_history_event(program_id, "command_center_signoff_archive_exported", context["signoff"].get("integrity_hash"))
            if self.archive_dir(program_id).exists():
                if not exported_event:
                    raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Archive export exists without an immutable history event.")
                docs = self._archive_documents(program_id, context, exported_event)
                self._validate_export_dir(self.archive_dir(program_id), docs, ARCHIVE_REQUIRED_ENTRIES)
                return read_json(self.archive_manifest_path(program_id))
            if exported_event:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Signed Archive export was deleted and cannot be rebuilt without reset.")
            event = self._append_history(
                program_id,
                {
                    "event_type": "command_center_signoff_archive_exported",
                    "created_at": now_iso(),
                    "program_id": program_id,
                    "signoff_hash": context["signoff"].get("integrity_hash"),
                    "signoff_binding_hash": context["binding"].get("integrity_hash"),
                },
            )
            state["archive_history_event_hash"] = event.get("event_hash")
            state["archive_exported_at"] = event.get("created_at")
            state["integrity_hash"] = _integrity_hash(state)
            write_json(self.state_path(program_id), state)
            context["state"] = state
            docs = self._archive_documents(program_id, context, event)
            self._write_export_dir(self.archive_dir(program_id), docs)
            return _as_document(docs["manifest.json"])

    def build_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            context = self._signed_context(program_id, payload)
            zip_path = self.archive_zip_path(program_id)
            built_event = self._find_history_event(program_id, "command_center_signoff_archive_built", context["signoff"].get("integrity_hash"))
            if zip_path.exists():
                runtime = self._verify_archive_runtime(program_id, payload)
                if runtime.get("status") != "passed":
                    raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Existing signed Archive ZIP failed runtime verification.")
                return _zip_result(program_id, zip_path, runtime.get("manifest_hash"))
            if built_event:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Signed Archive ZIP was deleted and cannot be rebuilt without reset.")
            self.export_archive(program_id, payload)
            self._validate_export_dir(
                self.archive_dir(program_id),
                self._archive_documents(program_id, self._signed_context(program_id, payload), self._archive_export_event(program_id)),
                ARCHIVE_REQUIRED_ENTRIES,
            )
            _build_zip(self.archive_dir(program_id), zip_path)
            runtime = self._verify_archive_runtime(program_id, payload)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                    "Built Archive ZIP failed runtime verification: " + ", ".join(runtime.get("blockers") or [])
                )
            self._append_history(
                program_id,
                {
                    "event_type": "command_center_signoff_archive_built",
                    "created_at": now_iso(),
                    "program_id": program_id,
                    "signoff_hash": context["signoff"].get("integrity_hash"),
                    "archive_zip_sha256": _sha256_path(zip_path),
                    "archive_manifest_hash": runtime.get("manifest_hash"),
                },
            )
            return _zip_result(program_id, zip_path, runtime.get("manifest_hash"))
