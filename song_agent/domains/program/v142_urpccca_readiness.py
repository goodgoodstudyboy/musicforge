# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list
import base64 as base64
import hashlib as hashlib
import io as io
import json as json
import os as os
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import ACCEPTED_EVIDENCE_ENTRIES as ACCEPTED_EVIDENCE_ENTRIES, ACCEPTED_EVIDENCE_PACKAGE_TYPE as ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE as ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, ARCHIVE_ENTRIES as ARCHIVE_ENTRIES, ARCHIVE_PACKAGE_TYPE as ARCHIVE_PACKAGE_TYPE, ARCHIVE_VERIFICATION_PACKAGE_TYPE as ARCHIVE_VERIFICATION_PACKAGE_TYPE, BOARD_REPORT_PACKAGE_TYPE as BOARD_REPORT_PACKAGE_TYPE, RESPONSE_PACKAGE_TYPE as RESPONSE_PACKAGE_TYPE, RESPONSE_VERIFICATION_PACKAGE_TYPE as RESPONSE_VERIFICATION_PACKAGE_TYPE, REVIEW_PACK_ENTRIES as REVIEW_PACK_ENTRIES, REVIEW_PACK_PACKAGE_TYPE as REVIEW_PACK_PACKAGE_TYPE, REVIEW_PACK_VERIFICATION_PACKAGE_TYPE as REVIEW_PACK_VERIFICATION_PACKAGE_TYPE, SCHEMA_VERSION as SCHEMA_VERSION, SIGNOFF_BINDING_PACKAGE_TYPE as SIGNOFF_BINDING_PACKAGE_TYPE, SIGNOFF_PACKAGE_TYPE as SIGNOFF_PACKAGE_TYPE, validate_response_proof as validate_response_proof, verify_accepted_evidence as verify_accepted_evidence, verify_review_pack as verify_review_pack, verify_unified_release_program_continuity_command_center_acceptance_package as verify_unified_release_program_continuity_command_center_acceptance_package, write_verification_report as write_verification_report
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff import UnifiedReleaseProgramContinuityCommandCenterSignoffStore as UnifiedReleaseProgramContinuityCommandCenterSignoffStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package

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

UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError')
_build_zip_from_values = _make_deferred_global('_build_zip_from_values')
_manifest = _make_deferred_global('_manifest')
_policy = _make_deferred_global('_policy')
_read_optional_json = _make_deferred_global('_read_optional_json')
_reject_forbidden = _make_deferred_global('_reject_forbidden')
_reject_sensitive_mutation = _make_deferred_global('_reject_sensitive_mutation')
_response_payload_documents = _make_deferred_global('_response_payload_documents')
_response_public_projection = _make_deferred_global('_response_public_projection')
_safe_id = _make_deferred_global('_safe_id')
_with_integrity = _make_deferred_global('_with_integrity')
_zip_result = _make_deferred_global('_zip_result')
field = _make_deferred_global('field')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError, _build_zip_from_values, _manifest, _policy, _read_optional_json, _reject_forbidden, _reject_sensitive_mutation
    global _response_payload_documents, _response_public_projection, _safe_id, _with_integrity, _zip_result, field, row, write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError)
    _build_zip_from_values = namespace.get('_build_zip_from_values', _build_zip_from_values)
    _manifest = namespace.get('_manifest', _manifest)
    _policy = namespace.get('_policy', _policy)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _reject_forbidden = namespace.get('_reject_forbidden', _reject_forbidden)
    _reject_sensitive_mutation = namespace.get('_reject_sensitive_mutation', _reject_sensitive_mutation)
    _response_payload_documents = namespace.get('_response_payload_documents', _response_payload_documents)
    _response_public_projection = namespace.get('_response_public_projection', _response_public_projection)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    _zip_result = namespace.get('_zip_result', _zip_result)
    field = namespace.get('field', field)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


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




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreReadinessMixin:
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

    def status(self, program_id: str) -> DomainDocument:
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

    def create_review_pack(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
                write_json(self.review_pack_dir(program_id) / rel, _as_document(value))
            _build_zip_from_values(zip_path, docs)
            runtime = self._verify_review_pack_runtime(program_id, payload)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Built Receiver Review Pack failed verification: " + ", ".join(runtime.get("blockers") or [])
                )
            return _zip_result(zip_path, runtime)

    def verify_review_pack(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        report = self._verify_review_pack_runtime(program_id, sanitize_metadata(payload or {}))
        return write_verification_report(report, self.review_pack_verification_report_path(program_id))

    def import_response(self, program_id: str, payload: DomainDocument) -> DomainDocument:
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

    def create_accepted_evidence(self, program_id: str, response_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
            docs: dict[str, DomainDocument | str] = {
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
                    write_json(evidence_root / rel, _as_document(value))
            _build_zip_from_values(zip_path, docs)
            runtime = self._verify_accepted_evidence_runtime(program_id, evidence_id, response_id)
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(
                    "Built Accepted Evidence failed verification: " + ", ".join(runtime.get("blockers") or [])
                )
            write_verification_report(runtime, self.accepted_evidence_verification_path(program_id, evidence_id))
            return {"status": "accepted", "evidence": accepted, **_zip_result(zip_path, runtime)}

    def verify_accepted_evidence(self, program_id: str, response_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        evidence_id = _safe_id(response_id)
        report = self._verify_accepted_evidence_runtime(program_id, evidence_id, _safe_id(response_id))
        return write_verification_report(report, self.accepted_evidence_verification_path(program_id, evidence_id))

    def refresh_board(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
