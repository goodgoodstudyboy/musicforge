from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

import json as json
import os as os
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.lifecycle import HistoryChain as HistoryChain
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.domains.legacy_documents import _program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center import UnifiedReleaseProgramContinuityCommandCenterStore as UnifiedReleaseProgramContinuityCommandCenterStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import ARCHIVE_REQUIRED_ENTRIES as ARCHIVE_REQUIRED_ENTRIES, COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION as COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION, HANDOFF_REQUIRED_ENTRIES as HANDOFF_REQUIRED_ENTRIES, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package, write_unified_release_program_continuity_command_center_final_handoff_verification_report as write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report as write_unified_release_program_continuity_command_center_signoff_verification_report
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package


RESET_ACTION = "reset_command_center_signoff"
RESET_CHANGE_TYPE = "reset_command_center_signoff"


class UnifiedReleaseProgramContinuityCommandCenterSignoffError(ValueError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError(
    UnifiedReleaseProgramContinuityCommandCenterSignoffError
):
    pass


class UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
    UnifiedReleaseProgramContinuityCommandCenterSignoffError
):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError)


class UnifiedReleaseProgramContinuityCommandCenterSignoffStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.command_store = UnifiedReleaseProgramContinuityCommandCenterStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write", on_commit=lambda: sync_active_v12_state(self.program_store.root.parent))

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

    def get_state(self, program_id: str) -> dict[str, Any]:
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

    def preflight(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        checks: list[dict[str, Any]] = []
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

    def signoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def create_change_request(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def approve_change_request(self, program_id: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def reset_signoff(self, program_id: str, change_request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def export_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def build_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        report = self._verify_archive_runtime(program_id, sanitize_metadata(payload or {}))
        return write_unified_release_program_continuity_command_center_signoff_verification_report(
            report, self.archive_verification_report_path(program_id)
        )

    def export_final_handoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            context = self._handoff_context(program_id, payload)
            signoff_hash = context["signoff"].get("integrity_hash")
            event = self._find_history_event(program_id, "command_center_final_handoff_exported", signoff_hash)
            if self.final_handoff_dir(program_id).exists():
                if not event:
                    raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Final Handoff export exists without history evidence.")
                docs = self._handoff_documents(program_id, context, event)
                self._validate_export_dir(self.final_handoff_dir(program_id), docs, HANDOFF_REQUIRED_ENTRIES)
                return read_json(self.final_handoff_dir(program_id) / "manifest.json")
            if event:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Final Handoff export was deleted and cannot be rebuilt without reset.")
            event = self._append_history(
                program_id,
                {
                    "event_type": "command_center_final_handoff_exported",
                    "created_at": now_iso(),
                    "program_id": program_id,
                    "signoff_hash": signoff_hash,
                    "archive_zip_sha256": context["archive_runtime"].get("zip_sha256"),
                    "archive_verification_report_hash": context["archive_external"].get("integrity_hash"),
                },
            )
            docs = self._handoff_documents(program_id, context, event)
            self._write_export_dir(self.final_handoff_dir(program_id), docs)
            return _as_document(docs["manifest.json"])

    def build_final_handoff_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            context = self._handoff_context(program_id, payload)
            signoff_hash = context["signoff"].get("integrity_hash")
            zip_path = self.final_handoff_zip_path(program_id)
            event = self._find_history_event(program_id, "command_center_final_handoff_built", signoff_hash)
            if zip_path.exists():
                runtime = self._verify_handoff_runtime(program_id, payload)
                if runtime.get("status") != "passed":
                    raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Existing Final Handoff ZIP failed runtime verification.")
                return _zip_result(program_id, zip_path, runtime.get("manifest_hash"))
            if event:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Final Handoff ZIP was deleted and cannot be rebuilt without reset.")
            self.export_final_handoff(program_id, payload)
            _build_zip(self.final_handoff_dir(program_id), zip_path)
            runtime = self._verify_handoff_runtime(program_id, payload)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                    "Built Final Handoff ZIP failed runtime verification: " + ", ".join(runtime.get("blockers") or [])
                )
            self._append_history(
                program_id,
                {
                    "event_type": "command_center_final_handoff_built",
                    "created_at": now_iso(),
                    "program_id": program_id,
                    "signoff_hash": signoff_hash,
                    "handoff_zip_sha256": _sha256_path(zip_path),
                },
            )
            return _zip_result(program_id, zip_path, runtime.get("manifest_hash"))

    def verify_final_handoff_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        report = self._verify_handoff_runtime(program_id, sanitize_metadata(payload or {}))
        return write_unified_release_program_continuity_command_center_final_handoff_verification_report(
            report, self.final_handoff_verification_report_path(program_id)
        )

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        archive_zip_path: Path | str | None = None,
        archive_verification_report_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
        command_center_zip_path: Path | str | None = None,
        command_center_verification_report_path: Path | str | None = None,
        command_center_external_evidence_manifest_path: Path | str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        latest = self.latest_signoff_state(program_id)
        if latest.get("status") != "signed":
            return _gate_failed("Continuity Command Center signoff is not current signed evidence.")
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(archive_verification_report_path) if archive_verification_report_path else self.archive_verification_report_path(program_id)
        binding_path = Path(signoff_binding_path) if signoff_binding_path else self.signoff_binding_path(program_id)
        command_zip = Path(command_center_zip_path) if command_center_zip_path else self.command_store.zip_path(program_id)
        command_report = Path(command_center_verification_report_path) if command_center_verification_report_path else self.command_store.verification_report_path(program_id)
        evidence = Path(command_center_external_evidence_manifest_path) if command_center_external_evidence_manifest_path else self.command_store.local_evidence_manifest_path(program_id)
        if not all(path.is_file() for path in (zip_path, report_path, binding_path, command_zip, command_report, evidence)):
            return _gate_failed("Continuity Command Center signoff gate is missing required external evidence.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_command_center_signoff_package(
                zip_path,
                strict=True,
                require_signed=True,
                signoff_binding_path=binding_path,
                command_center_zip_path=command_zip,
                command_center_verification_report_path=command_report,
                command_center_external_evidence_manifest_path=evidence,
            )
            if external.get("package_type") != COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
                return _gate_failed("Continuity Command Center signoff verification report integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Continuity Command Center signoff runtime verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Continuity Command Center signoff verification report is stale.")
            return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "command_center_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "command_center_signoff_reset":
                latest = {"status": "reset", "previous_signoff_hash": event.get("previous_signoff_hash"), "event": event}
        return latest or {"status": "unsigned", "event": None}

    def read_history(self, program_id: str) -> list[dict[str, Any]]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()

    def _assert_signoff_transition_allowed(self, program_id: str) -> None:
        history_path = self.history_path(program_id)
        root_artifacts = (
            self.signoff_path(program_id),
            self.signoff_binding_path(program_id),
            self.policy_path(program_id),
            self.state_path(program_id),
            self.reset_proof_path(program_id),
            self.archive_dir(program_id),
            self.archive_zip_path(program_id),
            self.archive_verification_report_path(program_id),
            self.final_handoff_dir(program_id),
            self.final_handoff_zip_path(program_id),
            self.final_handoff_verification_report_path(program_id),
            self.archive_history_dir(program_id),
            self.change_request_dir(program_id),
        )
        try:
            SignoffService.assert_transition_allowed(
                HistoryChain(history_path, sanitizer=sanitize_metadata),
                artifact_paths=root_artifacts,
                signed_event_types={"command_center_signoff_created"},
                reset_event_types={"command_center_signoff_reset"},
            )
        except ValueError as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(str(exc)) from exc
        if not history_path.exists():
            if any(path.exists() for path in root_artifacts):
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                    "Command Center signoff history is missing while signed-state artifacts remain."
                )
            return

        try:
            history = self.read_history(program_id)
            self._validate_history(program_id)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Command Center signoff history is unreadable or invalid."
            ) from exc
        if not history:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Command Center signoff history is empty and cannot authorize a new signoff."
            )

        latest = self.latest_signoff_state(program_id)
        if latest.get("status") == "signed":
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Continuity Command Center is already signed. Use an approved Change Request to reset signoff."
            )
        latest_event = _as_document(latest.get("event"))
        if (
            latest.get("status") != "reset"
            or history[-1].get("event_type") != "command_center_signoff_reset"
            or history[-1].get("event_hash") != latest_event.get("event_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Command Center signoff history does not end in an authorized reset."
            )

        stale_signed_artifacts = (
            self.signoff_path(program_id),
            self.signoff_binding_path(program_id),
            self.archive_dir(program_id),
            self.archive_zip_path(program_id),
            self.archive_verification_report_path(program_id),
            self.final_handoff_dir(program_id),
            self.final_handoff_zip_path(program_id),
            self.final_handoff_verification_report_path(program_id),
        )
        if any(path.exists() for path in stale_signed_artifacts):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Current signed artifacts remain after reset; a successor signoff is not allowed."
            )
        if not self.state_path(program_id).is_file() or not self.reset_proof_path(program_id).is_file():
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Command Center reset state or reset proof is missing."
            )
        state = read_json(self.state_path(program_id))
        proof = read_json(self.reset_proof_path(program_id))
        if (
            not _integrity_ok(state)
            or not _integrity_ok(proof)
            or state.get("status") != "reset"
            or state.get("reset_event_hash") != latest_event.get("event_hash")
            or proof.get("reset_event_hash") != latest_event.get("event_hash")
            or state.get("reset_proof_hash") != proof.get("integrity_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(
                "Command Center reset state does not match the latest history event."
            )

    def _current_command_center_context(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        zip_path = Path(payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.command_store.zip_path(program_id))
        report_path = Path(payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.command_store.verification_report_path(program_id))
        evidence_path = Path(payload.get("command_center_external_evidence_manifest") or payload.get("external_evidence_manifest") or payload.get("evidence_manifest") or self.command_store.local_evidence_manifest_path(program_id))
        for path, label in ((zip_path, "Command Center ZIP"), (report_path, "Command Center verification report"), (evidence_path, "Command Center external evidence manifest")):
            if not path.is_file():
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(f"{label} is missing.")
        external = read_json(report_path)
        evidence = read_json(evidence_path)
        runtime = verify_unified_release_program_continuity_command_center_package(zip_path, strict=True, deep=True, require_ready=True, evidence_manifest_path=evidence_path)
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center verification report integrity or package type failed.")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center runtime verification failed.")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or int(external.get("zip_size_bytes") or -1) != zip_path.stat().st_size or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center verification report does not match current ZIP.")
        if not _integrity_ok(evidence):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center external evidence manifest integrity failed.")
        with zipfile.ZipFile(zip_path) as archive:
            report = json.loads(archive.read("command-center-report.json").decode("utf-8"))
        current_state = _as_document(evidence.get("current_state"))
        source = {
            "command_center_zip_sha256": _sha256_path(zip_path),
            "command_center_zip_size_bytes": zip_path.stat().st_size,
            "command_center_manifest_hash": runtime.get("manifest_hash"),
            "command_center_verification_report_hash": external.get("integrity_hash"),
            "external_evidence_manifest_hash": evidence.get("integrity_hash"),
            "current_generation": current_state.get("generation"),
            "current_generation_hash": current_state.get("generation_hash"),
            "acceptance_signoff_hash": current_state.get("acceptance_signoff_hash"),
            "acceptance_history_event_hash": current_state.get("acceptance_history_event_hash"),
        }
        return {"zip_path": zip_path, "verification_path": report_path, "evidence_path": evidence_path, "external_verification": external, "evidence": evidence, "runtime": runtime, "report": report, "current_state": current_state, "source": source}

    def _signed_context(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        latest = self.latest_signoff_state(program_id)
        if latest.get("status") != "signed":
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Continuity Command Center signoff is not current signed evidence.")
        for path, label in ((self.signoff_path(program_id), "signoff"), (self.signoff_binding_path(program_id), "signoff binding"), (self.state_path(program_id), "signoff state"), (self.policy_path(program_id), "signoff policy")):
            if not path.exists():
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(f"Continuity Command Center {label} is missing; history prevents unsigned fallback.")
        signoff = read_json(self.signoff_path(program_id))
        binding = read_json(self.signoff_binding_path(program_id))
        state = read_json(self.state_path(program_id))
        if not all(_integrity_ok(doc) for doc in (signoff, binding, state, read_json(self.policy_path(program_id)))):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Signed Command Center material integrity failed.")
        if latest.get("signoff_hash") != signoff.get("integrity_hash") or binding.get("signoff_hash") != signoff.get("integrity_hash") or state.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Signed Command Center material does not match history state.")
        self._validate_history(program_id)
        current = self._current_command_center_context(program_id, payload)
        if current["source"] != signoff.get("source"):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Current Command Center evidence is stale relative to signoff.")
        return {**current, "signoff": signoff, "binding": binding, "state": state, "policy": read_json(self.policy_path(program_id))}

    def _archive_documents(self, program_id: str, context: ImplementationDocument, event: ImplementationDocument) -> dict[str, ImplementationDocument | str]:
        source = context["signoff"].get("source") or {}
        fingerprint = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_fingerprint_summary", "program_id": program_id, **source})
        verification = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_verification_summary", "program_id": program_id, "status": context["external_verification"].get("status"), "runtime_status": context["runtime"].get("status"), "zip_sha256": source.get("command_center_zip_sha256"), "manifest_hash": source.get("command_center_manifest_hash"), "verification_report_hash": source.get("command_center_verification_report_hash")})
        evidence = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_external_evidence_summary", "program_id": program_id, "external_evidence_manifest_hash": source.get("external_evidence_manifest_hash"), "current_generation": source.get("current_generation"), "current_generation_hash": source.get("current_generation_hash"), "acceptance_signoff_hash": source.get("acceptance_signoff_hash"), "acceptance_history_event_hash": source.get("acceptance_history_event_hash")})
        checklist = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_final_handoff_checklist", "program_id": program_id, "status": "ready", "items": [{"check_id": "runtime_ready", "status": "passed"}, {"check_id": "current_generation", "status": "passed"}, {"check_id": "external_binding", "status": "passed"}], "blockers": []})
        history_rows = self._history_through(program_id, str(event.get("event_hash") or ""))
        docs: dict[str, dict[str, Any] | str] = {
            "README.txt": _archive_readme(program_id, context["signoff"]),
            "command-center-signoff.json": context["signoff"],
            "command-center-signoff-binding-summary.json": context["binding"],
            "command-center-signoff-history.jsonl": "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in history_rows),
            "command-center-signoff-policy.json": context["policy"],
            "command-center-signoff-state.json": context["state"],
            "command-center-fingerprint-summary.json": fingerprint,
            "command-center-verification-summary.json": verification,
            "external-evidence-manifest-summary.json": evidence,
            "final-handoff-checklist.json": checklist,
        }
        files = [_memory_file_record(path, value) for path, value in docs.items()]
        manifest = _with_manifest_integrity({"schema_version": COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION, "package_type": COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, "program_id": program_id, "created_at": event.get("created_at"), "source": {"signoff_hash": context["signoff"].get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash"), "command_center_zip_sha256": source.get("command_center_zip_sha256"), "command_center_manifest_hash": source.get("command_center_manifest_hash"), "command_center_verification_report_hash": source.get("command_center_verification_report_hash"), "external_evidence_manifest_hash": source.get("external_evidence_manifest_hash")}, "files": files, "zip": {"entries": sorted(ARCHIVE_REQUIRED_ENTRIES)}})
        return {"manifest.json": manifest, **docs}

    def _handoff_context(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        signed = self._signed_context(program_id, payload)
        if not self.archive_zip_path(program_id).exists() or not self.archive_verification_report_path(program_id).exists():
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Verified Command Center Signoff Archive is required for Final Handoff.")
        external = read_json(self.archive_verification_report_path(program_id))
        runtime = self._verify_archive_runtime(program_id, payload)
        if external.get("package_type") != COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external) or external.get("status") != "passed" or runtime.get("status") != "passed" or external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center Signoff Archive verification is missing, stale, or failed.")
        return {**signed, "archive_external": external, "archive_runtime": runtime}

    def _handoff_documents(self, program_id: str, context: ImplementationDocument, event: ImplementationDocument) -> dict[str, ImplementationDocument | str]:
        archive_summary = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_archive_verification_summary", "program_id": program_id, "status": context["archive_external"].get("status"), "zip_sha256": context["archive_runtime"].get("zip_sha256"), "manifest_hash": context["archive_runtime"].get("manifest_hash"), "verification_report_hash": context["archive_external"].get("integrity_hash")})
        handoff = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_final_handoff_summary", "program_id": program_id, "status": "ready", "created_at": event.get("created_at"), "signed_by": context["signoff"].get("signed_by"), "signed_at": context["signoff"].get("signed_at"), "signoff_hash": context["signoff"].get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash"), "archive_zip_sha256": archive_summary.get("zip_sha256"), "archive_manifest_hash": archive_summary.get("manifest_hash"), "archive_verification_report_hash": archive_summary.get("verification_report_hash")})
        receiver = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_receiver_checklist", "program_id": program_id, "status": "ready", "items": [{"item_id": "verify-archive", "status": "required"}, {"item_id": "verify-signoff-binding", "status": "required"}]})
        docs: dict[str, dict[str, Any] | str] = {"README.txt": _handoff_readme(program_id), "final-handoff-summary.json": handoff, "receiver-checklist.json": receiver, "archive-verification-summary.json": archive_summary, "signoff-binding-summary.json": context["binding"]}
        manifest = _with_manifest_integrity({"schema_version": 1, "package_type": COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, "program_id": program_id, "created_at": event.get("created_at"), "source": {"final_handoff_summary_hash": handoff.get("integrity_hash"), "archive_verification_summary_hash": archive_summary.get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash")}, "files": [_memory_file_record(path, value) for path, value in docs.items()], "zip": {"entries": sorted(HANDOFF_REQUIRED_ENTRIES)}})
        return {"manifest.json": manifest, **docs}

    def _verify_archive_runtime(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        return verify_unified_release_program_continuity_command_center_signoff_package(
            payload.get("archive_zip") or payload.get("archive_zip_path") or self.archive_zip_path(program_id),
            strict=True,
            require_signed=True,
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_binding_path(program_id),
            command_center_zip_path=payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.command_store.zip_path(program_id),
            command_center_verification_report_path=payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.command_store.verification_report_path(program_id),
            command_center_external_evidence_manifest_path=payload.get("command_center_external_evidence_manifest") or payload.get("external_evidence_manifest") or self.command_store.local_evidence_manifest_path(program_id),
        )

    def _verify_handoff_runtime(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        return verify_unified_release_program_continuity_command_center_final_handoff_package(
            payload.get("handoff_zip") or payload.get("handoff_zip_path") or self.final_handoff_zip_path(program_id),
            strict=True,
            require_archive=True,
            archive_zip_path=payload.get("archive_zip") or payload.get("archive_zip_path") or self.archive_zip_path(program_id),
            archive_verification_report_path=payload.get("archive_verification_report") or payload.get("archive_verification_report_path") or self.archive_verification_report_path(program_id),
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_binding_path(program_id),
            command_center_zip_path=payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.command_store.zip_path(program_id),
            command_center_verification_report_path=payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.command_store.verification_report_path(program_id),
            command_center_external_evidence_manifest_path=payload.get("command_center_external_evidence_manifest") or payload.get("external_evidence_manifest") or self.command_store.local_evidence_manifest_path(program_id),
        )

    def _signoff_binding(self, signoff: ImplementationDocument, event: ImplementationDocument) -> ImplementationDocument:
        source = _as_document(signoff.get("source"))
        return _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_binding", "program_id": signoff.get("program_id"), "created_at": now_iso(), "signoff_hash": signoff.get("integrity_hash"), "signoff_payload_hash": signoff.get("payload_hash"), "signed_by": signoff.get("signed_by"), "role": signoff.get("role"), "reason_hash": stable_hash({"reason": signoff.get("reason")}), "signed_at": signoff.get("signed_at"), "history_event_hash": event.get("event_hash"), **source})

    def _append_history(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _validate_history(self, program_id: str) -> None:
        if not HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).validate().valid:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center signoff history hash chain is invalid.")

    def _find_history_event(self, program_id: str, event_type: str, signoff_hash: Any) -> ImplementationDocument | None:
        return next((row for row in reversed(self.read_history(program_id)) if row.get("event_type") == event_type and row.get("signoff_hash") == signoff_hash), None)

    def _archive_export_event(self, program_id: str) -> ImplementationDocument:
        latest = self.latest_signoff_state(program_id)
        event = self._find_history_event(program_id, "command_center_signoff_archive_exported", latest.get("signoff_hash"))
        if not event:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Archive export history event is missing.")
        return event

    def _history_through(self, program_id: str, event_hash: str) -> list[ImplementationDocument]:
        try:
            return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).through(event_hash)
        except ValueError as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Frozen archive history event is missing.") from exc

    def _assert_request_current(self, program_id: str, request: ImplementationDocument) -> None:
        context = self._signed_context(program_id, {})
        source = context["signoff"].get("source") or {}
        expected = {"signoff_hash": context["signoff"].get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash"), "command_center_zip_sha256": source.get("command_center_zip_sha256"), "command_center_manifest_hash": source.get("command_center_manifest_hash"), "command_center_verification_report_hash": source.get("command_center_verification_report_hash"), "external_evidence_manifest_hash": source.get("external_evidence_manifest_hash")}
        if request.get("target") != expected:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Change Request does not bind current signed Command Center evidence.")

    def _read_change_request(self, program_id: str, request_id: str) -> ImplementationDocument:
        path = self.change_request_path(program_id, request_id)
        if not path.exists():
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError(f"Change Request not found: {request_id}")
        return read_json(path)

    def _next_request_id(self, program_id: str) -> str:
        max_seen = 0
        for path in self.change_request_dir(program_id).glob("uccscr-*/change-request.json"):
            try:
                max_seen = max(max_seen, int(path.parent.name.rsplit("-", 1)[-1]))
            except ValueError:
                continue
        return f"uccscr-{max_seen + 1:06d}"

    def _write_export_dir(self, root: Path, docs: dict[str, ImplementationDocument | str]) -> None:
        if root.exists():
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Immutable export directory already exists.")
        root.mkdir(parents=True, exist_ok=False)
        for rel, value in docs.items():
            path = root / rel
            if isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)

    def _validate_export_dir(self, root: Path, docs: dict[str, ImplementationDocument | str], required: set[str]) -> None:
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        if actual != required:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Immutable export directory file set changed.")
        for rel, expected in docs.items():
            path = root / rel
            if not path.is_file():
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(f"Immutable export file is missing: {rel}")
            expected_bytes = _serialize_value(expected)
            if path.read_bytes() != expected_bytes:
                raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError(f"Immutable export file changed: {rel}")

    def _preserve_current_archive(self, program_id: str, signoff_hash: Any) -> None:
        if not signoff_hash:
            return
        destination = self.archive_history_dir(program_id) / f"a-{_safe_id(str(signoff_hash))[:16]}"
        if destination.exists():
            return
        destination.mkdir(parents=True, exist_ok=False)
        snapshots = (
            (self.signoff_path(program_id), "signoff.json"),
            (self.signoff_binding_path(program_id), "binding.json"),
            (self.archive_zip_path(program_id), "archive.zip"),
            (self.archive_verification_report_path(program_id), "archive-verification.json"),
            (self.final_handoff_zip_path(program_id), "handoff.zip"),
            (self.final_handoff_verification_report_path(program_id), "handoff-verification.json"),
        )
        for path, name in snapshots:
            if path.exists():
                shutil.copy2(path, destination / name)

    def _clear_current_outputs(self, program_id: str) -> None:
        for root in (self.archive_dir(program_id), self.final_handoff_dir(program_id)):
            if root.exists():
                shutil.rmtree(root)
        for path in (self.archive_zip_path(program_id), self.archive_verification_report_path(program_id), self.final_handoff_zip_path(program_id), self.final_handoff_verification_report_path(program_id)):
            path.unlink(missing_ok=True)


def _check(check_id: str, passed: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}


def _archive_readme(program_id: str, signoff: ImplementationDocument) -> str:
    return f"MusicForge Continuity Command Center Signoff Archive\n\nProgram: {program_id}\nSigned by: {signoff.get('signed_by')}\nSigned at: {signoff.get('signed_at')}\n"


def _handoff_readme(program_id: str) -> str:
    return f"MusicForge Continuity Command Center Final Handoff\n\nProgram: {program_id}\nThis package contains public-safe fingerprints and no nested ZIP.\n"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    return re_sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def re_sub(pattern: str, replacement: str, value: str) -> str:
    import re

    return re.sub(pattern, replacement, value)


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _with_manifest_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    output = sanitize_metadata(doc, blocked_keys=DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
    output["integrity_hash"] = _integrity_hash(output)
    return output


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _serialize_value(value: ImplementationDocument | str) -> bytes:
    if isinstance(value, str):
        return value.replace("\n", os.linesep).encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")


def _memory_file_record(path: str, value: ImplementationDocument | str) -> ImplementationDocument:
    data = _serialize_value(value)
    return {"path": path, "size_bytes": len(data), "sha256": _sha256_bytes(data)}


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _build_zip(root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    ArchiveBuilder.build_directory_zip(root, zip_path)


def _zip_result(program_id: str, zip_path: Path, manifest_hash: Any) -> ImplementationDocument:
    return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": manifest_hash}


def _read_optional_json(path: Path) -> ImplementationDocument:
    return read_json(path) if path.exists() else {}


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
