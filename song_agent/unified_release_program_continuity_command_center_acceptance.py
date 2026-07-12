from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.platform.lifecycle import HistoryChain, SignoffService
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_release_program import UnifiedReleaseProgramStore
from song_agent.unified_release_program_continuity_command_center_acceptance_verifier import (
    ACCEPTED_EVIDENCE_ENTRIES,
    ACCEPTED_EVIDENCE_PACKAGE_TYPE,
    ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE,
    ARCHIVE_ENTRIES,
    ARCHIVE_PACKAGE_TYPE,
    ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    BOARD_REPORT_PACKAGE_TYPE,
    RESPONSE_BINDING_PACKAGE_TYPE,
    RESPONSE_PACKAGE_TYPE,
    RESPONSE_VERIFICATION_PACKAGE_TYPE,
    REVIEW_PACK_ENTRIES,
    REVIEW_PACK_PACKAGE_TYPE,
    REVIEW_PACK_VERIFICATION_PACKAGE_TYPE,
    SCHEMA_VERSION,
    SIGNOFF_BINDING_PACKAGE_TYPE,
    SIGNOFF_PACKAGE_TYPE,
    validate_response_proof,
    verify_accepted_evidence,
    verify_review_pack,
    verify_unified_release_program_continuity_command_center_acceptance_package,
    write_verification_report,
)
from song_agent.unified_release_program_continuity_command_center_signoff import (
    UnifiedReleaseProgramContinuityCommandCenterSignoffStore,
)
from song_agent.unified_release_program_continuity_command_center_signoff_verifier import (
    COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_command_center_final_handoff_package,
    verify_unified_release_program_continuity_command_center_signoff_package,
)


DEFAULT_POLICY = {
    "min_accepted_count": 2,
    "min_organization_count": 2,
    "required_roles": ["continuity_owner", "operations_owner"],
    "block_on_rejected": True,
    "block_on_needs_changes": True,
    "block_on_critical_findings": True,
}

BLOCKED_INPUT_KEYS = {
    "absolute_path",
    "api_key",
    "authorization",
    "file_path",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceError(ValueError):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError
):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError(
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError
):
    pass


class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.signoff_store = UnifiedReleaseProgramContinuityCommandCenterSignoffStore(self.program_store)
        self.root = self.program_store.root.parent / "urpccca"
        self.lock = threading.RLock()

    def acceptance_dir(self, program_id: str) -> Path:
        return self.root / _safe_id(program_id)

    def review_pack_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "review-pack"

    def review_pack_report_path(self, program_id: str) -> Path:
        return self.review_pack_dir(program_id) / "review-pack-report.json"

    def review_pack_manifest_path(self, program_id: str) -> Path:
        return self.review_pack_dir(program_id) / "manifest.json"

    def review_pack_package_index_path(self, program_id: str) -> Path:
        return self.review_pack_dir(program_id) / "package-index.json"

    def review_pack_verification_summary_path(self, program_id: str) -> Path:
        return self.review_pack_dir(program_id) / "verification-summary.json"

    def review_pack_zip_path(self, program_id: str) -> Path:
        return self.review_pack_dir(program_id) / "command-center-handoff-review-pack.zip"

    def review_pack_verification_report_path(self, program_id: str) -> Path:
        return self.review_pack_dir(program_id) / "verification-report.json"

    def responses_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "responses"

    def response_dir(self, program_id: str, response_id: str) -> Path:
        return self.responses_dir(program_id) / _safe_id(response_id)

    def response_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response.json"

    def response_verification_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response-verification-report.json"

    def response_binding_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response-binding-summary.json"

    def accepted_evidence_root(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "accepted-evidence"

    def accepted_evidence_dir(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_root(program_id) / _safe_id(evidence_id)

    def accepted_evidence_zip_path(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence.zip"

    def accepted_evidence_verification_path(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(program_id, evidence_id) / "verification-report.json"

    def board_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "board"

    def board_report_path(self, program_id: str) -> Path:
        return self.board_dir(program_id) / "receiver-acceptance-board-report.json"

    def decision_matrix_path(self, program_id: str) -> Path:
        return self.board_dir(program_id) / "receiver-decision-matrix.json"

    def quorum_report_path(self, program_id: str) -> Path:
        return self.board_dir(program_id) / "receiver-quorum-report.json"

    def findings_register_path(self, program_id: str) -> Path:
        return self.board_dir(program_id) / "receiver-findings-register.json"

    def accepted_index_path(self, program_id: str) -> Path:
        return self.board_dir(program_id) / "accepted-evidence-index.json"

    def response_index_path(self, program_id: str) -> Path:
        return self.board_dir(program_id) / "response-proof-index.json"

    def external_evidence_manifest_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "external-evidence-manifest.json"

    def signoff_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "signoff"

    def signoff_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "receiver-acceptance-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "receiver-acceptance-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "receiver-acceptance-history.jsonl"

    def state_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "receiver-acceptance-state.json"

    def policy_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "receiver-acceptance-policy.json"

    def archive_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "archive"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "receiver-acceptance-archive.zip"

    def archive_verification_report_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "receiver-acceptance-verification-report.json"

    def status(self, program_id: str) -> dict[str, Any]:
        latest = self.latest_signoff_state(program_id)
        report = _read_optional_json(self.board_report_path(program_id))
        return {
            "program_id": program_id,
            "status": latest.get("status") if latest.get("status") != "unsigned" else report.get("status") or "not_configured",
            "latest_signoff_state": latest,
            "review_pack": _read_optional_json(self.review_pack_report_path(program_id)),
            "board_report": report,
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "verification": _read_optional_json(self.archive_verification_report_path(program_id)),
            "summary": report.get("summary") or {},
        }

    def create_review_pack(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            self.ensure_unsigned(program_id)
            zip_path = self.review_pack_zip_path(program_id)
            if zip_path.exists():
                runtime = self._verify_review_pack_runtime(program_id, payload)
                if runtime.get("status") != "passed":
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                        "Existing Receiver Review Pack failed runtime verification: " + ", ".join(runtime.get("blockers") or [])
                    )
                return _zip_result(zip_path, runtime)
            if self.review_pack_report_path(program_id).exists():
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Receiver Review Pack ZIP was deleted and cannot be silently rebuilt."
                )
            context = self._current_v1210_context(program_id, payload)
            docs = self._review_pack_documents(program_id, context)
            self.review_pack_dir(program_id).mkdir(parents=True, exist_ok=True)
            for rel, value in docs.items():
                if rel.startswith("packages/") or rel == "README.txt":
                    continue
                write_json(self.review_pack_dir(program_id) / rel, value)
            _build_zip_from_values(zip_path, docs)
            runtime = self._verify_review_pack_runtime(program_id, payload)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Built Receiver Review Pack failed verification: " + ", ".join(runtime.get("blockers") or [])
                )
            return _zip_result(zip_path, runtime)

    def verify_review_pack(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        report = self._verify_review_pack_runtime(program_id, sanitize_metadata(payload or {}))
        return write_verification_report(report, self.review_pack_verification_report_path(program_id))

    def import_response(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(program_id)
            response, verification, binding = _response_payload_documents(payload)
            _reject_forbidden(response, "Receiver response")
            _reject_sensitive_mutation(response, "Receiver response")
            required = (
                "program_id",
                "response_id",
                "review_pack_id",
                "review_pack_source_hash",
                "review_pack_zip_sha256",
                "review_pack_manifest_hash",
                "review_pack_verification_report_hash",
                "command_center_signoff_archive_zip_sha256",
                "command_center_signoff_archive_manifest_hash",
                "command_center_signoff_archive_verification_report_hash",
                "command_center_final_handoff_zip_sha256",
                "command_center_final_handoff_manifest_hash",
                "command_center_final_handoff_verification_report_hash",
                "command_center_signoff_binding_hash",
                "reviewer",
                "organization",
                "role",
                "decision",
                "created_at",
                "payload_hash",
                "integrity_hash",
            )
            missing = [field for field in required if response.get(field) in {None, ""}]
            if missing:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Receiver response missing explicit binding fields: " + ", ".join(missing)
                )
            if response.get("program_id") != program_id:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response program_id does not match.")
            source = self._current_review_source(program_id, {})
            failed = [row.get("check_id") for row in validate_response_proof(response, verification, binding, source) if row.get("status") == "failed"]
            if failed:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Receiver response external proof failed: " + ", ".join(str(value) for value in failed)
                )
            response_id = _safe_id(str(response.get("response_id") or ""))
            root = self.response_dir(program_id, response_id)
            if root.exists():
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"Receiver response already exists: {response_id}")
            root.mkdir(parents=True, exist_ok=False)
            write_json(self.response_path(program_id, response_id), response)
            write_json(self.response_verification_path(program_id, response_id), verification)
            write_json(self.response_binding_path(program_id, response_id), binding)
            return {"status": "imported", "response": response, "verification": verification, "binding": binding}

    def create_accepted_evidence(self, program_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            self.ensure_unsigned(program_id)
            response_id = _safe_id(response_id)
            source = self._current_review_source(program_id, {})
            response, verification, binding = self._response_bundle(program_id, response_id)
            failed = [row.get("check_id") for row in validate_response_proof(response, verification, binding, source) if row.get("status") == "failed"]
            if failed or binding.get("decision") != "accepted":
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Only a currently verified accepted response can create Accepted Evidence."
                )
            evidence_id = _safe_id(str(response.get("evidence_id") or response_id))
            zip_path = self.accepted_evidence_zip_path(program_id, evidence_id)
            if zip_path.exists():
                runtime = self._verify_accepted_evidence_runtime(program_id, evidence_id, response_id)
                if runtime.get("status") != "passed":
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Existing Accepted Evidence failed runtime verification.")
                return _zip_result(zip_path, runtime)
            evidence_root = self.accepted_evidence_dir(program_id, evidence_id)
            if (evidence_root / "accepted-evidence.json").exists():
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Accepted Evidence ZIP was deleted and cannot be silently rebuilt.")
            public = _with_integrity(_response_public_projection(response))
            verification_summary = _with_integrity(
                {
                    "schema_version": SCHEMA_VERSION,
                    "package_type": f"{RESPONSE_VERIFICATION_PACKAGE_TYPE}_summary",
                    "program_id": program_id,
                    "response_id": response_id,
                    "status": verification.get("status"),
                    "response_sha256": verification.get("response_sha256"),
                    "response_payload_hash": verification.get("response_payload_hash"),
                    "response_public_projection_hash": verification.get("response_public_projection_hash"),
                    "verification_report_hash": verification.get("integrity_hash"),
                }
            )
            accepted = _with_integrity(
                {
                    "schema_version": SCHEMA_VERSION,
                    "package_type": ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                    "program_id": program_id,
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "status": "accepted",
                    "reviewer": binding.get("reviewer"),
                    "organization": binding.get("organization"),
                    "role": binding.get("role"),
                    "decision": binding.get("decision"),
                    "response_public_projection_hash": public.get("integrity_hash"),
                    "response_verification_report_hash": verification.get("integrity_hash"),
                    "response_binding_hash": binding.get("integrity_hash"),
                    "review_pack_source_hash": source.get("review_pack_source_hash"),
                }
            )
            docs: dict[str, dict[str, Any] | str] = {
                "README.txt": f"MusicForge Receiver Accepted Evidence\n\nProgram: {program_id}\nResponse: {response_id}\n",
                "accepted-evidence.json": accepted,
                "original-response-public.json": public,
                "response-verification-summary.json": verification_summary,
                "response-binding-summary.json": binding,
            }
            manifest = _manifest(
                ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                program_id,
                docs,
                {
                    "accepted_evidence_hash": accepted.get("integrity_hash"),
                    "response_public_projection_hash": public.get("integrity_hash"),
                    "response_verification_summary_hash": verification_summary.get("integrity_hash"),
                    "response_binding_hash": binding.get("integrity_hash"),
                },
                ACCEPTED_EVIDENCE_ENTRIES,
            )
            docs = {"manifest.json": manifest, **docs}
            evidence_root.mkdir(parents=True, exist_ok=False)
            for rel, value in docs.items():
                if rel == "README.txt":
                    (evidence_root / rel).write_text(str(value), encoding="utf-8")
                else:
                    write_json(evidence_root / rel, value)
            _build_zip_from_values(zip_path, docs)
            runtime = self._verify_accepted_evidence_runtime(program_id, evidence_id, response_id)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Built Accepted Evidence failed verification: " + ", ".join(runtime.get("blockers") or [])
                )
            write_verification_report(runtime, self.accepted_evidence_verification_path(program_id, evidence_id))
            return {"status": "accepted", "evidence": accepted, **_zip_result(zip_path, runtime)}

    def verify_accepted_evidence(self, program_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        evidence_id = _safe_id(response_id)
        report = self._verify_accepted_evidence_runtime(program_id, evidence_id, _safe_id(response_id))
        return write_verification_report(report, self.accepted_evidence_verification_path(program_id, evidence_id))

    def refresh_board(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            self.ensure_unsigned(program_id)
            if self.latest_signoff_state(program_id).get("status") == "reset_pending":
                signed_policy = _read_optional_json(self.policy_path(program_id))
                preserved_policy = _policy(signed_policy)
                if "policy" in payload and _policy(payload.get("policy")) != preserved_policy:
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                        "Receiver Acceptance policy cannot change during a reset-scoped successor signoff."
                    )
                payload = {**payload, "policy": preserved_policy}
            docs = self._build_board_documents(program_id, payload)
            self._write_board_documents(program_id, docs)
            self._mark_reset_board_refreshed(program_id, docs)
            return docs["report"]

    def signoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            self._assert_signoff_allowed(program_id)
            previous_state = _read_optional_json(self.state_path(program_id))
            generation = int(previous_state.get("generation") or 1)
            reset_proof_hash = previous_state.get("reset_proof_hash") if previous_state.get("status") == "reset_pending" else None
            reset_binding_hash = previous_state.get("reset_binding_hash") if previous_state.get("status") == "reset_pending" else None
            docs = self._build_board_documents(program_id, {})
            if docs["report"].get("status") != "ready_for_signoff":
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Receiver Acceptance Board is not ready for signoff."
                )
            now = now_iso()
            docs["report"]["status"] = "signed"
            docs["report"]["signed_at"] = now
            docs["report"]["integrity_hash"] = _integrity_hash(docs["report"])
            signoff = {
                "schema_version": SCHEMA_VERSION,
                "package_type": SIGNOFF_PACKAGE_TYPE,
                "program_id": program_id,
                "status": "signed",
                "signed_by": _bounded(payload.get("signed_by") or "receiver-acceptance-chair", 120),
                "role": _bounded(payload.get("role") or "program_owner", 80),
                "reason": _bounded(payload.get("reason") or "Receiver acceptance quorum approved for operational takeover.", 1000),
                "signed_at": now,
                "board_report_hash": docs["report"].get("integrity_hash"),
                "decision_matrix_hash": docs["matrix"].get("integrity_hash"),
                "quorum_report_hash": docs["quorum"].get("integrity_hash"),
                "findings_register_hash": docs["findings"].get("integrity_hash"),
                "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                "response_proof_index_hash": docs["response_index"].get("integrity_hash"),
                "review_pack_source_hash": (docs["report"].get("source") or {}).get("review_pack_source_hash"),
                "generation": generation,
                "reset_proof_hash": reset_proof_hash,
                "reset_binding_hash": reset_binding_hash,
                "tool": {"name": "MusicForge Receiver Acceptance Board", "version": __version__},
            }
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "receiver_acceptance_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason_hash": stable_hash({"reason": signoff.get("reason")}),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "board_report_hash": signoff.get("board_report_hash"),
                    "review_pack_source_hash": signoff.get("review_pack_source_hash"),
                    "generation": generation,
                    "reset_proof_hash": reset_proof_hash,
                    "reset_binding_hash": reset_binding_hash,
                },
            )
            binding = _with_integrity(
                {
                    "schema_version": SCHEMA_VERSION,
                    "package_type": SIGNOFF_BINDING_PACKAGE_TYPE,
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason_hash": stable_hash({"reason": signoff.get("reason")}),
                    "signed_at": signoff.get("signed_at"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "history_event_hash": event.get("event_hash"),
                    "board_report_hash": signoff.get("board_report_hash"),
                    "decision_matrix_hash": signoff.get("decision_matrix_hash"),
                    "quorum_report_hash": signoff.get("quorum_report_hash"),
                    "findings_register_hash": signoff.get("findings_register_hash"),
                    "accepted_evidence_index_hash": signoff.get("accepted_evidence_index_hash"),
                    "response_proof_index_hash": signoff.get("response_proof_index_hash"),
                    "review_pack_source_hash": signoff.get("review_pack_source_hash"),
                    "generation": generation,
                    "reset_proof_hash": reset_proof_hash,
                    "reset_binding_hash": reset_binding_hash,
                }
            )
            policy = _with_integrity(
                {
                    "schema_version": SCHEMA_VERSION,
                    "package_type": f"{SIGNOFF_PACKAGE_TYPE}_policy",
                    "program_id": program_id,
                    **docs["report"].get("policy", DEFAULT_POLICY),
                    "reset_supported": True,
                }
            )
            state = _with_integrity(
                {
                    "schema_version": SCHEMA_VERSION,
                    "package_type": f"{SIGNOFF_PACKAGE_TYPE}_state",
                    "program_id": program_id,
                    "status": "signed",
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_binding_hash": binding.get("integrity_hash"),
                    "signoff_event_hash": event.get("event_hash"),
                    "signed_at": now,
                    "generation": generation,
                    "reset_proof_hash": reset_proof_hash,
                    "reset_binding_hash": reset_binding_hash,
                    "board_refresh_required": False,
                }
            )
            self._write_board_documents(program_id, docs)
            self.signoff_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.signoff_path(program_id), signoff)
            write_json(self.signoff_binding_path(program_id), binding)
            write_json(self.policy_path(program_id), policy)
            write_json(self.state_path(program_id), state)
            return signoff

    def export_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            context = self._signed_context(program_id, payload)
            event = self._find_history_event(program_id, "receiver_acceptance_archive_exported")
            if self.archive_dir(program_id).exists():
                if not event:
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Archive export exists without history evidence.")
                docs = self._archive_documents(program_id, context, event)
                self._validate_export_dir(self.archive_dir(program_id), docs)
                return read_json(self.archive_dir(program_id) / "manifest.json")
            if event:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Archive export was deleted and cannot be rebuilt.")
            event = self._append_history(
                program_id,
                {
                    "event_type": "receiver_acceptance_archive_exported",
                    "created_at": now_iso(),
                    "program_id": program_id,
                    "signoff_hash": context["signoff"].get("integrity_hash"),
                },
            )
            docs = self._archive_documents(program_id, context, event)
            self._write_export_dir(self.archive_dir(program_id), docs)
            return docs["manifest.json"]

    def build_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = sanitize_metadata(payload or {})
        with self.lock:
            self._signed_context(program_id, payload)
            zip_path = self.archive_zip_path(program_id)
            event = self._find_history_event(program_id, "receiver_acceptance_archive_built")
            if zip_path.exists():
                runtime = self._verify_archive_runtime(program_id, payload)
                if runtime.get("status") != "passed":
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Existing Receiver Acceptance Archive failed runtime verification.")
                return _zip_result(zip_path, runtime)
            if event:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance Archive ZIP was deleted and cannot be rebuilt.")
            self.export_archive(program_id, payload)
            _build_zip_from_dir(self.archive_dir(program_id), zip_path)
            runtime = self._verify_archive_runtime(program_id, payload)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Built Receiver Acceptance Archive failed verification: " + ", ".join(runtime.get("blockers") or [])
                )
            self._append_history(
                program_id,
                {
                    "event_type": "receiver_acceptance_archive_built",
                    "created_at": now_iso(),
                    "program_id": program_id,
                    "signoff_hash": read_json(self.signoff_path(program_id)).get("integrity_hash"),
                    "archive_zip_sha256": _sha256_path(zip_path),
                },
            )
            return _zip_result(zip_path, runtime)

    def verify_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        report = self._verify_archive_runtime(program_id, sanitize_metadata(payload or {}))
        return write_verification_report(report, self.archive_verification_report_path(program_id))

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            self._validate_history(program_id)
            if self.latest_signoff_state(program_id).get("status") != "signed":
                return _gate_failed("Receiver Acceptance is not current signed evidence.")
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.archive_verification_report_path(program_id)
        if not zip_path.is_file() or not report_path.is_file():
            return _gate_failed("Receiver Acceptance Archive or verification report is missing.")
        try:
            runtime = self._verify_archive_runtime(program_id, {**payload, "archive_zip": zip_path})
            external = read_json(report_path)
            if external.get("package_type") != ARCHIVE_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
                return _gate_failed("Receiver Acceptance verification report integrity or package type failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Receiver Acceptance runtime verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Receiver Acceptance verification report is stale.")
            return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def mark_reset_pending(
        self,
        program_id: str,
        reset_proof: dict[str, Any],
        reset_binding: dict[str, Any],
    ) -> dict[str, Any]:
        with self.lock:
            context = self._signed_context(program_id, {}, allow_reset_pending=True)
            if reset_proof.get("package_type") != "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof":
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset proof package type is invalid.")
            if reset_binding.get("package_type") != "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof_binding_summary":
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset binding package type is invalid.")
            if not _integrity_ok(reset_proof) or not _integrity_ok(reset_binding):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset proof integrity failed.")
            if reset_proof.get("program_id") != program_id or reset_binding.get("program_id") != program_id:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset proof program_id mismatch.")
            if reset_binding.get("reset_proof_hash") != reset_proof.get("integrity_hash"):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset binding does not reference reset proof.")
            expected = {
                "previous_signoff_hash": context["signoff"].get("integrity_hash"),
                "previous_signoff_binding_hash": context["binding"].get("integrity_hash"),
            }
            for field, value in expected.items():
                if reset_proof.get(field) != value:
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                        f"Receiver Acceptance reset proof {field} does not match current signed evidence."
                    )
            reset_event = self.read_history(program_id)[-1]
            if (
                reset_event.get("event_type") != "receiver_acceptance_signoff_reset"
                or reset_event.get("previous_signoff_hash") != context["signoff"].get("integrity_hash")
                or reset_event.get("change_request_id") != reset_proof.get("change_request_id")
            ):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset history event is invalid.")
            generation_before = int(reset_proof.get("previous_generation") or 0)
            generation_after = int(reset_proof.get("next_generation") or 0)
            if generation_before < 1 or generation_after != generation_before + 1:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset generation transition is invalid.")
            snapshot = self.acceptance_dir(program_id) / "change-control" / "generations" / f"gen-{generation_before:06d}" / "acceptance-snapshot"
            if snapshot.exists():
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance generation snapshot already exists.")
            snapshot.mkdir(parents=True, exist_ok=False)
            snapshot_files = {
                self.signoff_path(program_id): "receiver-acceptance-signoff.json",
                self.signoff_binding_path(program_id): "receiver-acceptance-signoff-binding-summary.json",
                self.state_path(program_id): "receiver-acceptance-state.json",
                self.policy_path(program_id): "receiver-acceptance-policy.json",
                self.history_path(program_id): "receiver-acceptance-history.jsonl",
                self.archive_zip_path(program_id): "receiver-acceptance-archive.zip",
                self.archive_verification_report_path(program_id): "receiver-acceptance-verification-report.json",
            }
            for source, name in snapshot_files.items():
                if not source.is_file():
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                        f"Receiver Acceptance signed snapshot source is missing: {source.name}"
                    )
                shutil.copy2(source, snapshot / name)
            if self.archive_dir(program_id).is_dir():
                shutil.copytree(self.archive_dir(program_id), snapshot / "archive-export")
            for source, name in (
                (self.review_pack_dir(program_id), "review-pack"),
                (self.responses_dir(program_id), "responses"),
                (self.accepted_evidence_root(program_id), "accepted-evidence"),
                (self.board_dir(program_id), "board"),
            ):
                if source.is_dir():
                    shutil.move(str(source), str(snapshot / name))
            if self.archive_dir(program_id).exists():
                shutil.rmtree(self.archive_dir(program_id))
            self.archive_zip_path(program_id).unlink(missing_ok=True)
            self.archive_verification_report_path(program_id).unlink(missing_ok=True)
            state = _with_integrity(
                {
                    "schema_version": SCHEMA_VERSION,
                    "package_type": f"{SIGNOFF_PACKAGE_TYPE}_state",
                    "program_id": program_id,
                    "status": "reset_pending",
                    "generation": generation_after,
                    "previous_generation": generation_before,
                    "previous_signoff_hash": context["signoff"].get("integrity_hash"),
                    "previous_signoff_binding_hash": context["binding"].get("integrity_hash"),
                    "reset_proof_hash": reset_proof.get("integrity_hash"),
                    "reset_binding_hash": reset_binding.get("integrity_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "board_refresh_required": True,
                    "reset_at": reset_proof.get("applied_at"),
                }
            )
            write_json(self.state_path(program_id), state)
            return state

    def ensure_unsigned(self, program_id: str) -> None:
        history_path = self.history_path(program_id)
        signed_artifacts = (
            self.signoff_path(program_id),
            self.signoff_binding_path(program_id),
            self.state_path(program_id),
            self.policy_path(program_id),
            self.archive_dir(program_id),
            self.archive_zip_path(program_id),
            self.archive_verification_report_path(program_id),
        )
        try:
            SignoffService.assert_transition_allowed(
                HistoryChain(history_path, sanitizer=sanitize_metadata),
                artifact_paths=signed_artifacts,
                signed_event_types={"receiver_acceptance_signoff_created"},
                reset_event_types={"receiver_acceptance_signoff_reset"},
            )
        except ValueError as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(str(exc)) from exc
        if not history_path.exists():
            report = _read_optional_json(self.board_report_path(program_id))
            if any(path.exists() for path in signed_artifacts) or report.get("status") == "signed":
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Receiver Acceptance history is missing while signed-state artifacts remain."
                )
            return
        self._validate_history(program_id)
        latest = self.latest_signoff_state(program_id)
        if latest.get("status") == "signed":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                "Receiver Acceptance is signed and immutable; use approved Change Control for reset."
            )
        if latest.get("status") != "reset_pending":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history has no valid current state.")
        state = _read_optional_json(self.state_path(program_id))
        if not _integrity_ok(state) or state.get("status") != "reset_pending" or state.get("reset_event_hash") != (latest.get("event") or {}).get("event_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset-pending state is invalid.")

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        rows = self.read_history(program_id)
        latest: dict[str, Any] = {"status": "unsigned", "event": None}
        for event in rows:
            if event.get("event_type") == "receiver_acceptance_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "receiver_acceptance_signoff_reset":
                latest = {
                    "status": "reset_pending",
                    "previous_signoff_hash": event.get("previous_signoff_hash"),
                    "reset_proof_hash": event.get("reset_proof_hash"),
                    "generation": event.get("next_generation"),
                    "event": event,
                }
        return latest

    def read_history(self, program_id: str) -> list[dict[str, Any]]:
        try:
            return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history is unreadable.") from exc

    def _assert_signoff_allowed(self, program_id: str) -> None:
        self.ensure_unsigned(program_id)
        latest = self.latest_signoff_state(program_id)
        if latest.get("status") == "reset_pending":
            state = read_json(self.state_path(program_id))
            if state.get("board_refresh_required"):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Receiver Acceptance Board must be refreshed after reset before successor signoff."
                )
            return
        if self.history_path(program_id).exists():
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history already exists; re-sign is not allowed.")

    def _mark_reset_board_refreshed(self, program_id: str, docs: dict[str, Any]) -> None:
        if self.latest_signoff_state(program_id).get("status") != "reset_pending":
            return
        state = read_json(self.state_path(program_id))
        if not _integrity_ok(state) or state.get("status") != "reset_pending":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance reset state integrity failed.")
        state.update(
            {
                "board_refresh_required": False,
                "board_refreshed_at": now_iso(),
                "board_report_hash": docs["report"].get("integrity_hash"),
                "decision_matrix_hash": docs["matrix"].get("integrity_hash"),
                "quorum_report_hash": docs["quorum"].get("integrity_hash"),
                "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                "response_proof_index_hash": docs["response_index"].get("integrity_hash"),
            }
        )
        state["integrity_hash"] = _integrity_hash(state)
        write_json(self.state_path(program_id), state)

    def _current_v1210_context(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        archive_path = Path(payload.get("command_center_signoff_archive") or payload.get("signoff_archive") or self.signoff_store.archive_zip_path(program_id))
        archive_report_path = Path(payload.get("command_center_signoff_archive_verification_report") or payload.get("signoff_archive_verification_report") or self.signoff_store.archive_verification_report_path(program_id))
        handoff_path = Path(payload.get("command_center_final_handoff") or payload.get("final_handoff") or self.signoff_store.final_handoff_zip_path(program_id))
        handoff_report_path = Path(payload.get("command_center_final_handoff_verification_report") or payload.get("final_handoff_verification_report") or self.signoff_store.final_handoff_verification_report_path(program_id))
        binding_path = Path(payload.get("command_center_signoff_binding") or payload.get("signoff_binding") or self.signoff_store.signoff_binding_path(program_id))
        command_path = Path(payload.get("command_center") or self.signoff_store.command_store.zip_path(program_id))
        command_report_path = Path(payload.get("command_center_verification_report") or self.signoff_store.command_store.verification_report_path(program_id))
        evidence_path = Path(payload.get("command_center_evidence_manifest") or payload.get("command_center_external_evidence_manifest") or self.signoff_store.command_store.local_evidence_manifest_path(program_id))
        paths = (archive_path, archive_report_path, handoff_path, handoff_report_path, binding_path, command_path, command_report_path, evidence_path)
        if not all(path.is_file() for path in paths):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Current v12.10 Signoff/Handoff evidence is incomplete.")
        archive_external = read_json(archive_report_path)
        handoff_external = read_json(handoff_report_path)
        binding = read_json(binding_path)
        archive_runtime = verify_unified_release_program_continuity_command_center_signoff_package(
            archive_path,
            strict=True,
            require_signed=True,
            signoff_binding_path=binding_path,
            command_center_zip_path=command_path,
            command_center_verification_report_path=command_report_path,
            command_center_external_evidence_manifest_path=evidence_path,
        )
        handoff_runtime = verify_unified_release_program_continuity_command_center_final_handoff_package(
            handoff_path,
            strict=True,
            require_archive=True,
            archive_zip_path=archive_path,
            archive_verification_report_path=archive_report_path,
            signoff_binding_path=binding_path,
            command_center_zip_path=command_path,
            command_center_verification_report_path=command_report_path,
            command_center_external_evidence_manifest_path=evidence_path,
        )
        if (
            archive_external.get("package_type") != COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE
            or handoff_external.get("package_type") != COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE
            or not all(_integrity_ok(doc) for doc in (archive_external, handoff_external, binding))
            or archive_external.get("status") != "passed"
            or handoff_external.get("status") != "passed"
            or archive_runtime.get("status") != "passed"
            or handoff_runtime.get("status") != "passed"
            or archive_external.get("zip_sha256") != archive_runtime.get("zip_sha256")
            or archive_external.get("manifest_hash") != archive_runtime.get("manifest_hash")
            or handoff_external.get("zip_sha256") != handoff_runtime.get("zip_sha256")
            or handoff_external.get("manifest_hash") != handoff_runtime.get("manifest_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Current v12.10 Signoff/Handoff runtime verification failed.")
        command_external = read_json(command_report_path)
        evidence = read_json(evidence_path)
        source = {
            "program_id": program_id,
            "command_center_signoff_archive_zip_sha256": _sha256_path(archive_path),
            "command_center_signoff_archive_zip_size_bytes": archive_path.stat().st_size,
            "command_center_signoff_archive_manifest_hash": archive_runtime.get("manifest_hash"),
            "command_center_signoff_archive_verification_report_hash": archive_external.get("integrity_hash"),
            "command_center_final_handoff_zip_sha256": _sha256_path(handoff_path),
            "command_center_final_handoff_zip_size_bytes": handoff_path.stat().st_size,
            "command_center_final_handoff_manifest_hash": handoff_runtime.get("manifest_hash"),
            "command_center_final_handoff_verification_report_hash": handoff_external.get("integrity_hash"),
            "command_center_signoff_binding_hash": binding.get("integrity_hash"),
            "command_center_zip_sha256": binding.get("command_center_zip_sha256"),
            "command_center_manifest_hash": binding.get("command_center_manifest_hash"),
            "command_center_verification_report_hash": command_external.get("integrity_hash"),
            "external_evidence_manifest_hash": evidence.get("integrity_hash"),
        }
        return {
            "archive_path": archive_path,
            "archive_report_path": archive_report_path,
            "handoff_path": handoff_path,
            "handoff_report_path": handoff_report_path,
            "binding_path": binding_path,
            "command_path": command_path,
            "command_report_path": command_report_path,
            "evidence_path": evidence_path,
            "archive_external": archive_external,
            "handoff_external": handoff_external,
            "archive_runtime": archive_runtime,
            "handoff_runtime": handoff_runtime,
            "binding": binding,
            "source": source,
        }

    def _review_pack_documents(self, program_id: str, context: dict[str, Any]) -> dict[str, dict[str, Any] | str | bytes]:
        source = context["source"]
        source_hash = stable_hash(source)
        report = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{REVIEW_PACK_PACKAGE_TYPE}_report",
                "program_id": program_id,
                "review_pack_id": f"urpcccarp-{_safe_id(program_id)}",
                "status": "ready",
                "source": source,
                "source_hash": source_hash,
                "summary": {"package_count": 2, "runtime_status": "passed"},
            }
        )
        packages = [
            {
                "component_type": "command_center_signoff_archive",
                "path": "packages/command-center-signoff-archive.zip",
                "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_archive",
                "zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
                "zip_size_bytes": source.get("command_center_signoff_archive_zip_size_bytes"),
                "manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
                "verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
            },
            {
                "component_type": "command_center_final_handoff",
                "path": "packages/command-center-final-handoff.zip",
                "package_type": "musicforge_unified_release_program_continuity_command_center_final_handoff",
                "zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
                "zip_size_bytes": source.get("command_center_final_handoff_zip_size_bytes"),
                "manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
                "verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
            },
        ]
        package_index = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{REVIEW_PACK_PACKAGE_TYPE}_package_index", "program_id": program_id, "packages": packages})
        verification = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{REVIEW_PACK_PACKAGE_TYPE}_verification_summary",
                "program_id": program_id,
                "status": "passed",
                "archive_runtime_status": context["archive_runtime"].get("status"),
                "handoff_runtime_status": context["handoff_runtime"].get("status"),
                "archive_verification_report_hash": context["archive_external"].get("integrity_hash"),
                "handoff_verification_report_hash": context["handoff_external"].get("integrity_hash"),
            }
        )
        docs: dict[str, dict[str, Any] | str | bytes] = {
            "README.txt": f"MusicForge Receiver Handoff Review Pack\n\nProgram: {program_id}\n",
            "review-pack-report.json": report,
            "package-index.json": package_index,
            "verification-summary.json": verification,
            "packages/command-center-signoff-archive.zip": context["archive_path"].read_bytes(),
            "packages/command-center-final-handoff.zip": context["handoff_path"].read_bytes(),
        }
        docs["manifest.json"] = _manifest(
            REVIEW_PACK_PACKAGE_TYPE,
            program_id,
            docs,
            {
                "review_pack_report_hash": report.get("integrity_hash"),
                "package_index_hash": package_index.get("integrity_hash"),
                "verification_summary_hash": verification.get("integrity_hash"),
                "source_hash": source_hash,
            },
            REVIEW_PACK_ENTRIES,
        )
        return {"manifest.json": docs.pop("manifest.json"), **docs}

    def _verify_review_pack_runtime(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = self._current_v1210_context(program_id, payload)
        return verify_review_pack(
            payload.get("review_pack") or self.review_pack_zip_path(program_id),
            strict=True,
            require_current=True,
            signoff_archive_verification_report_path=context["archive_report_path"],
            final_handoff_verification_report_path=context["handoff_report_path"],
            signoff_binding_path=context["binding_path"],
            command_center_zip_path=context["command_path"],
            command_center_verification_report_path=context["command_report_path"],
            command_center_external_evidence_manifest_path=context["evidence_path"],
        )

    def _current_review_source(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        review_pack = Path(payload.get("review_pack") or self.review_pack_zip_path(program_id))
        report_path = Path(payload.get("review_pack_verification_report") or self.review_pack_verification_report_path(program_id))
        if not review_pack.is_file() or not report_path.is_file():
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Current Receiver Review Pack and verification report are required.")
        runtime = self._verify_review_pack_runtime(program_id, {**payload, "review_pack": review_pack})
        external = read_json(report_path)
        if (
            external.get("package_type") != REVIEW_PACK_VERIFICATION_PACKAGE_TYPE
            or not _integrity_ok(external)
            or external.get("status") != "passed"
            or runtime.get("status") != "passed"
            or external.get("zip_sha256") != runtime.get("zip_sha256")
            or external.get("manifest_hash") != runtime.get("manifest_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Review Pack verification is stale or failed.")
        with zipfile.ZipFile(review_pack) as archive:
            review_report = json.loads(archive.read("review-pack-report.json").decode("utf-8"))
        review_source = review_report.get("source") if isinstance(review_report.get("source"), dict) else {}
        return {
            "program_id": program_id,
            "review_pack_id": review_report.get("review_pack_id"),
            "review_pack_source_hash": review_report.get("source_hash"),
            "review_pack_zip_sha256": runtime.get("zip_sha256"),
            "review_pack_manifest_hash": runtime.get("manifest_hash"),
            "review_pack_verification_report_hash": external.get("integrity_hash"),
            **review_source,
        }

    def _response_bundle(self, program_id: str, response_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        paths = (
            self.response_path(program_id, response_id),
            self.response_verification_path(program_id, response_id),
            self.response_binding_path(program_id, response_id),
        )
        if not all(path.is_file() for path in paths):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError(f"Receiver response proof not found: {response_id}")
        return tuple(read_json(path) for path in paths)  # type: ignore[return-value]

    def _response_bundles(self, program_id: str) -> dict[str, dict[str, Any]]:
        bundles: dict[str, dict[str, Any]] = {}
        if not self.responses_dir(program_id).exists():
            return bundles
        for root in sorted(path for path in self.responses_dir(program_id).iterdir() if path.is_dir()):
            try:
                response, verification, binding = self._response_bundle(program_id, root.name)
                bundles[root.name] = {"response": response, "verification": verification, "binding": binding}
            except (OSError, ValueError):
                bundles[root.name] = {"error": "response_proof_unreadable"}
        return bundles

    def _verify_accepted_evidence_runtime(self, program_id: str, evidence_id: str, response_id: str) -> dict[str, Any]:
        return verify_accepted_evidence(
            self.accepted_evidence_zip_path(program_id, evidence_id),
            strict=True,
            require_response=True,
            response_path=self.response_path(program_id, response_id),
            response_verification_report_path=self.response_verification_path(program_id, response_id),
            response_binding_summary_path=self.response_binding_path(program_id, response_id),
        )

    def _build_board_documents(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        stored_report = _read_optional_json(self.board_report_path(program_id))
        policy = _policy(payload.get("policy") if "policy" in payload else stored_report.get("policy"))
        conflicts: list[dict[str, Any]] = []
        try:
            source = self._current_review_source(program_id, payload)
        except Exception as exc:
            source = dict((stored_report.get("source") or {}))
            conflicts.append({"reason": "review_pack_runtime_failed", "message": sanitize_sensitive_text(str(exc))})
        responses = self._response_bundles(program_id)
        valid_responses: dict[str, dict[str, Any]] = {}
        for response_id, bundle in sorted(responses.items()):
            if bundle.get("error"):
                conflicts.append({"response_id": response_id, "reason": "response_proof_unreadable"})
                continue
            failed = [row.get("check_id") for row in validate_response_proof(bundle["response"], bundle["verification"], bundle["binding"], source) if row.get("status") == "failed"]
            if failed:
                conflicts.append({"response_id": response_id, "reason": "response_proof_invalid", "blockers": failed})
                continue
            valid_responses[response_id] = bundle
        participants: list[dict[str, Any]] = []
        accepted_rows: list[dict[str, Any]] = []
        if self.accepted_evidence_root(program_id).exists():
            for evidence_root in sorted(path for path in self.accepted_evidence_root(program_id).iterdir() if path.is_dir()):
                evidence_id = evidence_root.name
                accepted_path = evidence_root / "accepted-evidence.json"
                report_path = evidence_root / "verification-report.json"
                if not accepted_path.is_file() or not report_path.is_file():
                    conflicts.append({"evidence_id": evidence_id, "reason": "accepted_evidence_missing"})
                    continue
                accepted = read_json(accepted_path)
                response_id = str(accepted.get("response_id") or "")
                runtime = self._verify_accepted_evidence_runtime(program_id, evidence_id, response_id)
                external = read_json(report_path)
                bundle = valid_responses.get(response_id) or {}
                binding = bundle.get("binding") or {}
                if (
                    runtime.get("status") != "passed"
                    or external.get("package_type") != ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE
                    or not _integrity_ok(external)
                    or external.get("status") != "passed"
                    or external.get("zip_sha256") != runtime.get("zip_sha256")
                    or external.get("manifest_hash") != runtime.get("manifest_hash")
                    or accepted.get("role") != binding.get("role")
                    or accepted.get("organization") != binding.get("organization")
                    or accepted.get("decision") != binding.get("decision")
                ):
                    conflicts.append({"evidence_id": evidence_id, "response_id": response_id, "reason": "accepted_evidence_external_binding_failed", "blockers": runtime.get("blockers") or []})
                    continue
                participant = {
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "reviewer": binding.get("reviewer"),
                    "organization": binding.get("organization"),
                    "role": binding.get("role"),
                    "decision": binding.get("decision"),
                    "reviewer_identity_hash": binding.get("reviewer_identity_hash"),
                    "decision_hash": binding.get("decision_hash"),
                    "response_binding_hash": binding.get("integrity_hash"),
                    "accepted_evidence_verification_hash": external.get("integrity_hash"),
                }
                participants.append(participant)
                accepted_rows.append(
                    {
                        "evidence_id": evidence_id,
                        "response_id": response_id,
                        "zip_sha256": runtime.get("zip_sha256"),
                        "zip_size_bytes": runtime.get("zip_size_bytes"),
                        "manifest_hash": runtime.get("manifest_hash"),
                        "verification_report_hash": external.get("integrity_hash"),
                        "response_binding_hash": binding.get("integrity_hash"),
                    }
                )
        for response_id, bundle in valid_responses.items():
            decision = bundle["binding"].get("decision")
            if decision == "rejected" and policy.get("block_on_rejected", True):
                conflicts.append({"response_id": response_id, "reason": "rejected_response_present"})
            if decision == "needs_changes" and policy.get("block_on_needs_changes", True):
                conflicts.append({"response_id": response_id, "reason": "needs_changes_response_present"})
            if policy.get("block_on_critical_findings", True) and any(str(row.get("severity") or "").lower() == "critical" for row in bundle["response"].get("findings") or [] if isinstance(row, dict)):
                conflicts.append({"response_id": response_id, "reason": "critical_finding_present"})
        quorum_summary = _quorum_summary(policy, participants, conflicts)
        matrix_rows = sorted(participants, key=lambda row: (str(row.get("role") or ""), str(row.get("response_id") or "")))
        findings_rows = _findings_rows(valid_responses)
        policy_hash = stable_hash(policy)
        matrix = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_decision_matrix", "program_id": program_id, "rows": matrix_rows})
        quorum = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_quorum_report", "program_id": program_id, "policy_hash": policy_hash, "summary": quorum_summary})
        findings = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_findings_register", "program_id": program_id, "items": findings_rows, "summary": {"finding_count": len(findings_rows), "critical_count": sum(1 for row in findings_rows if row.get("severity") == "critical")}})
        accepted_index = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_accepted_evidence_index", "program_id": program_id, "items": sorted(accepted_rows, key=lambda row: str(row.get("evidence_id") or "")), "summary": {"accepted_count": len(accepted_rows)}})
        response_rows = []
        for response_id, bundle in sorted(valid_responses.items()):
            response_rows.append(
                {
                    "response_id": response_id,
                    "decision": bundle["binding"].get("decision"),
                    "response_integrity_hash": bundle["response"].get("integrity_hash"),
                    "verification_report_hash": bundle["verification"].get("integrity_hash"),
                    "binding_hash": bundle["binding"].get("integrity_hash"),
                    "reviewer_identity_hash": bundle["binding"].get("reviewer_identity_hash"),
                    "findings_hash": bundle["binding"].get("findings_hash"),
                }
            )
        response_index = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_response_proof_index", "program_id": program_id, "items": response_rows, "summary": {"response_count": len(response_rows)}})
        report = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": BOARD_REPORT_PACKAGE_TYPE,
                "program_id": program_id,
                "status": "ready_for_signoff" if quorum_summary.get("status") == "ready_for_signoff" and not conflicts else "blocked",
                "policy": policy,
                "policy_hash": policy_hash,
                "source": {
                    **source,
                    "policy_hash": policy_hash,
                    "accepted_evidence_set_hash": stable_hash(accepted_rows),
                    "response_proof_set_hash": stable_hash(response_rows),
                },
                "summary": {
                    **quorum_summary,
                    "response_count": len(response_rows),
                    "finding_count": len(findings_rows),
                    "conflict_count": len(conflicts),
                },
                "conflicts": conflicts,
            }
        )
        external_manifest = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_external_evidence_manifest",
                "program_id": program_id,
                "review_pack": {
                    "path": "review-pack/command-center-handoff-review-pack.zip",
                    "verification_report_path": "review-pack/verification-report.json",
                    "zip_sha256": source.get("review_pack_zip_sha256"),
                    "verification_report_hash": source.get("review_pack_verification_report_hash"),
                },
                "responses": [
                    {
                        "response_id": row.get("response_id"),
                        "response_path": f"responses/{row.get('response_id')}/response.json",
                        "verification_report_path": f"responses/{row.get('response_id')}/response-verification-report.json",
                        "binding_summary_path": f"responses/{row.get('response_id')}/response-binding-summary.json",
                        "binding_hash": row.get("binding_hash"),
                    }
                    for row in response_rows
                ],
                "accepted_evidence": [
                    {
                        "evidence_id": row.get("evidence_id"),
                        "response_id": row.get("response_id"),
                        "zip_path": f"accepted-evidence/{row.get('evidence_id')}/accepted-evidence.zip",
                        "verification_report_path": f"accepted-evidence/{row.get('evidence_id')}/verification-report.json",
                        "zip_sha256": row.get("zip_sha256"),
                        "verification_report_hash": row.get("verification_report_hash"),
                    }
                    for row in accepted_rows
                ],
            }
        )
        return {"report": report, "matrix": matrix, "quorum": quorum, "findings": findings, "accepted_index": accepted_index, "response_index": response_index, "external_manifest": external_manifest}

    def _write_board_documents(self, program_id: str, docs: dict[str, Any]) -> None:
        self.board_dir(program_id).mkdir(parents=True, exist_ok=True)
        for path, key in (
            (self.board_report_path(program_id), "report"),
            (self.decision_matrix_path(program_id), "matrix"),
            (self.quorum_report_path(program_id), "quorum"),
            (self.findings_register_path(program_id), "findings"),
            (self.accepted_index_path(program_id), "accepted_index"),
            (self.response_index_path(program_id), "response_index"),
            (self.external_evidence_manifest_path(program_id), "external_manifest"),
        ):
            write_json(path, docs[key])

    def _signed_context(
        self,
        program_id: str,
        payload: dict[str, Any],
        *,
        allow_reset_pending: bool = False,
    ) -> dict[str, Any]:
        latest = self.latest_signoff_state(program_id)
        if latest.get("status") == "reset_pending" and allow_reset_pending:
            event = next(
                (row for row in reversed(self.read_history(program_id)) if row.get("event_type") == "receiver_acceptance_signoff_created"),
                None,
            )
            if event:
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
        if latest.get("status") != "signed":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance is not current signed evidence.")
        paths = (self.signoff_path(program_id), self.signoff_binding_path(program_id), self.state_path(program_id), self.policy_path(program_id))
        if not all(path.is_file() for path in paths):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Signed Receiver Acceptance artifacts are missing; history prevents unsigned fallback.")
        signoff, binding, state, policy = (read_json(path) for path in paths)
        if not all(_integrity_ok(doc) for doc in (signoff, binding, state, policy)):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Signed Receiver Acceptance artifact integrity failed.")
        self._validate_history(program_id)
        event = latest.get("event") or {}
        if (
            binding.get("signoff_hash") != signoff.get("integrity_hash")
            or state.get("signoff_hash") != signoff.get("integrity_hash")
            or binding.get("history_event_hash") != event.get("event_hash")
            or state.get("signoff_event_hash") != event.get("event_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Signed Receiver Acceptance does not match history root.")
        current = self._build_board_documents(program_id, payload)
        stored = {
            "report": read_json(self.board_report_path(program_id)),
            "matrix": read_json(self.decision_matrix_path(program_id)),
            "quorum": read_json(self.quorum_report_path(program_id)),
            "findings": read_json(self.findings_register_path(program_id)),
            "accepted_index": read_json(self.accepted_index_path(program_id)),
            "response_index": read_json(self.response_index_path(program_id)),
        }
        current["report"]["status"] = "signed"
        current["report"]["signed_at"] = stored["report"].get("signed_at")
        current["report"]["integrity_hash"] = _integrity_hash(current["report"])
        if any(current[key] != stored[key] for key in stored):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Signed Receiver Acceptance board source changed after signoff.")
        expected_hashes = {
            "board_report_hash": stored["report"].get("integrity_hash"),
            "decision_matrix_hash": stored["matrix"].get("integrity_hash"),
            "quorum_report_hash": stored["quorum"].get("integrity_hash"),
            "findings_register_hash": stored["findings"].get("integrity_hash"),
            "accepted_evidence_index_hash": stored["accepted_index"].get("integrity_hash"),
            "response_proof_index_hash": stored["response_index"].get("integrity_hash"),
        }
        if any(signoff.get(key) != value or binding.get(key) != value for key, value in expected_hashes.items()):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Signoff does not bind frozen Receiver Acceptance board documents.")
        return {**stored, "signoff": signoff, "binding": binding, "state": state, "policy": policy, "event": event}

    def _archive_documents(self, program_id: str, context: dict[str, Any], event: dict[str, Any]) -> dict[str, dict[str, Any] | str]:
        source = context["report"].get("source") or {}
        handoff_summary = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{ARCHIVE_PACKAGE_TYPE}_source_handoff_summary",
                "program_id": program_id,
                "zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
                "manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
                "verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
                "signoff_binding_hash": source.get("command_center_signoff_binding_hash"),
            }
        )
        archive_summary = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{ARCHIVE_PACKAGE_TYPE}_source_signoff_archive_summary",
                "program_id": program_id,
                "zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
                "manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
                "verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
                "signoff_binding_hash": source.get("command_center_signoff_binding_hash"),
            }
        )
        docs: dict[str, dict[str, Any] | str] = {
            "README.txt": f"MusicForge Receiver Acceptance Archive\n\nProgram: {program_id}\n",
            "receiver-acceptance-signoff.json": context["signoff"],
            "receiver-acceptance-signoff-binding-summary.json": context["binding"],
            "receiver-acceptance-history.jsonl": _history_text(self._history_through(program_id, str(event.get("event_hash") or ""))),
            "receiver-acceptance-state.json": context["state"],
            "receiver-acceptance-policy.json": context["policy"],
            "receiver-acceptance-board-report.json": context["report"],
            "receiver-decision-matrix.json": context["matrix"],
            "receiver-quorum-report.json": context["quorum"],
            "receiver-findings-register.json": context["findings"],
            "accepted-evidence-index.json": context["accepted_index"],
            "response-proof-index.json": context["response_index"],
            "source-handoff-summary.json": handoff_summary,
            "source-signoff-archive-summary.json": archive_summary,
        }
        source_hashes = {
            "signoff_hash": context["signoff"].get("integrity_hash"),
            "signoff_binding_hash": context["binding"].get("integrity_hash"),
            "state_hash": context["state"].get("integrity_hash"),
            "policy_hash": context["policy"].get("integrity_hash"),
            "board_report_hash": context["report"].get("integrity_hash"),
            "decision_matrix_hash": context["matrix"].get("integrity_hash"),
            "quorum_report_hash": context["quorum"].get("integrity_hash"),
            "findings_register_hash": context["findings"].get("integrity_hash"),
            "accepted_evidence_index_hash": context["accepted_index"].get("integrity_hash"),
            "response_proof_index_hash": context["response_index"].get("integrity_hash"),
            "source_handoff_summary_hash": handoff_summary.get("integrity_hash"),
            "source_signoff_archive_summary_hash": archive_summary.get("integrity_hash"),
        }
        manifest = _manifest(ARCHIVE_PACKAGE_TYPE, program_id, docs, source_hashes, ARCHIVE_ENTRIES)
        return {"manifest.json": manifest, **docs}

    def _verify_archive_runtime(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = self._current_v1210_context(program_id, payload)
        return verify_unified_release_program_continuity_command_center_acceptance_package(
            payload.get("archive_zip") or self.archive_zip_path(program_id),
            strict=True,
            require_signed=True,
            signoff_binding_path=payload.get("acceptance_signoff_binding") or payload.get("signoff_binding") or self.signoff_binding_path(program_id),
            review_pack_path=payload.get("review_pack") or self.review_pack_zip_path(program_id),
            review_pack_verification_report_path=payload.get("review_pack_verification_report") or self.review_pack_verification_report_path(program_id),
            accepted_evidence_dir=payload.get("accepted_evidence_dir") or self.accepted_evidence_root(program_id),
            response_proof_dir=payload.get("response_proof_dir") or self.responses_dir(program_id),
            command_center_signoff_archive_path=context["archive_path"],
            command_center_signoff_archive_verification_report_path=context["archive_report_path"],
            command_center_final_handoff_path=context["handoff_path"],
            command_center_final_handoff_verification_report_path=context["handoff_report_path"],
            command_center_signoff_binding_path=context["binding_path"],
            command_center_path=context["command_path"],
            command_center_verification_report_path=context["command_report_path"],
            command_center_evidence_manifest_path=context["evidence_path"],
        )

    def _append_history(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _validate_history(self, program_id: str) -> None:
        validation = HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).validate()
        if not validation.rows:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history is missing.")
        if not validation.valid:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history hash chain is invalid.")

    def _find_history_event(self, program_id: str, event_type: str) -> dict[str, Any] | None:
        signoff_hash = self.latest_signoff_state(program_id).get("signoff_hash")
        return next((row for row in reversed(self.read_history(program_id)) if row.get("event_type") == event_type and row.get("signoff_hash") == signoff_hash), None)

    def _history_through(self, program_id: str, event_hash: str) -> list[dict[str, Any]]:
        try:
            return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).through(event_hash)
        except ValueError as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Frozen Receiver Acceptance history event is missing.") from exc

    def _write_export_dir(self, root: Path, docs: dict[str, dict[str, Any] | str]) -> None:
        if root.exists():
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Immutable Receiver Acceptance export already exists.")
        root.mkdir(parents=True, exist_ok=False)
        for rel, value in docs.items():
            path = root / rel
            if isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)

    def _validate_export_dir(self, root: Path, docs: dict[str, dict[str, Any] | str]) -> None:
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        if actual != ARCHIVE_ENTRIES:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Immutable Receiver Acceptance export file set changed.")
        for rel, expected in docs.items():
            path = root / rel
            if not path.is_file() or path.read_bytes() != _serialize(expected):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"Immutable Receiver Acceptance export changed: {rel}")


def _response_payload_documents(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _reject_forbidden(payload, "Receiver response import")
    if payload.get("response_zip_base64"):
        try:
            data = base64.b64decode(str(payload["response_zip_base64"]), validate=True)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = [item.filename for item in archive.infolist()]
                expected = {"response.json", "response-verification-report.json", "response-binding-summary.json"}
                if set(names) != expected or len(names) != len(expected):
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response ZIP must contain the fixed proof entries.")
                return tuple(json.loads(archive.read(name).decode("utf-8")) for name in ("response.json", "response-verification-report.json", "response-binding-summary.json"))  # type: ignore[return-value]
        except (ValueError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response ZIP is invalid.") from exc
    if payload.get("response_base64"):
        try:
            wrapper = json.loads(base64.b64decode(str(payload["response_base64"]), validate=True).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver response base64 JSON is invalid.") from exc
        payload = wrapper if isinstance(wrapper, dict) else {}
    response = payload.get("response") or payload.get("response_json")
    verification = payload.get("response_verification_report")
    binding = payload.get("response_binding_summary")
    if not all(isinstance(value, dict) for value in (response, verification, binding)):
        raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
            "Receiver response requires external response, verification report, and binding summary."
        )
    return dict(response), dict(verification), dict(binding)


def _policy(value: Any) -> dict[str, Any]:
    incoming = value if isinstance(value, dict) else {}
    return {
        "min_accepted_count": max(1, int(incoming.get("min_accepted_count") or DEFAULT_POLICY["min_accepted_count"])),
        "min_organization_count": max(1, int(incoming.get("min_organization_count") or DEFAULT_POLICY["min_organization_count"])),
        "required_roles": sorted({_bounded(role, 80) for role in incoming.get("required_roles") or DEFAULT_POLICY["required_roles"] if str(role).strip()}),
        "block_on_rejected": bool(incoming.get("block_on_rejected", DEFAULT_POLICY["block_on_rejected"])),
        "block_on_needs_changes": bool(incoming.get("block_on_needs_changes", DEFAULT_POLICY["block_on_needs_changes"])),
        "block_on_critical_findings": bool(incoming.get("block_on_critical_findings", DEFAULT_POLICY["block_on_critical_findings"])),
    }


def _quorum_summary(policy: dict[str, Any], participants: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {str(row.get("role") or "") for row in accepted}
    organizations = {str(row.get("organization") or "") for row in accepted}
    missing_roles = sorted(set(policy.get("required_roles") or []) - roles)
    blockers: list[str] = []
    if len(accepted) < int(policy.get("min_accepted_count") or 2):
        blockers.append("min_accepted_count")
    if len(organizations) < int(policy.get("min_organization_count") or 2):
        blockers.append("min_organization_count")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("receiver_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(organizations), "required_roles": sorted(policy.get("required_roles") or []), "missing_roles": missing_roles, "blockers": blockers}


def _findings_rows(responses: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for response_id, bundle in sorted(responses.items()):
        for index, finding in enumerate(bundle["response"].get("findings") or [], start=1):
            if not isinstance(finding, dict):
                continue
            rows.append({"response_id": response_id, "finding_id": str(finding.get("finding_id") or f"finding-{index:03d}"), "severity": str(finding.get("severity") or "info").lower(), "category": _bounded(finding.get("category") or "general", 120), "summary": _bounded(finding.get("summary") or "", 500), "finding_hash": stable_hash(finding)})
    return rows


def _response_public_projection(response: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "package_type": f"{RESPONSE_PACKAGE_TYPE}_public_projection", "program_id": response.get("program_id"), "response_id": response.get("response_id"), "reviewer": response.get("reviewer"), "organization": response.get("organization"), "role": response.get("role"), "decision": response.get("decision"), "findings": response.get("findings") or [], "created_at": response.get("created_at")}


def _manifest(package_type: str, program_id: str, docs: dict[str, Any], source: dict[str, Any], required: set[str]) -> dict[str, Any]:
    files = []
    for rel in sorted(required - {"manifest.json"}):
        data = _serialize(docs[rel])
        files.append({"path": rel, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": package_type, "program_id": program_id, "source": source, "files": files, "zip": {"entries": sorted(required)}})


def _build_zip_from_values(path: Path, docs: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel, value in docs.items():
            archive.writestr(rel, _serialize(value))


def _build_zip_from_dir(root: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(root.rglob("*")):
            if source.is_file():
                archive.write(source, source.relative_to(root).as_posix())


def _serialize(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.replace("\n", os.linesep).encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")


def _with_integrity(doc: dict[str, Any]) -> dict[str, Any]:
    output = dict(doc)
    output["integrity_hash"] = _integrity_hash(output)
    return output


def _integrity_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: dict[str, Any]) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_result(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    return {"status": "passed", "zip_path": str(path), "zip_sha256": _sha256_path(path), "zip_size_bytes": path.stat().st_size, "manifest_hash": report.get("manifest_hash")}


def _history_text(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return read_json(path)
    except (OSError, ValueError):
        return {}


def _reject_forbidden(value: Any, label: str) -> None:
    if isinstance(value, dict):
        forbidden = sorted(str(key) for key in value if str(key).lower() in BLOCKED_INPUT_KEYS)
        if forbidden:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"{label} contains forbidden path or secret fields: {', '.join(forbidden)}")
        for child in value.values():
            _reject_forbidden(child, label)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden(child, label)


def _reject_sensitive_mutation(value: dict[str, Any], label: str) -> None:
    if sanitize_metadata(value) != value:
        raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"{label} contains sensitive or local-path content.")


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
