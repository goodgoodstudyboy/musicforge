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
_bounded = _make_deferred_global('_bounded')
_build_zip_from_dir = _make_deferred_global('_build_zip_from_dir')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_read_optional_json = _make_deferred_global('_read_optional_json')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
_zip_result = _make_deferred_global('_zip_result')
path = _make_deferred_global('path')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError, _bounded, _build_zip_from_dir, _gate_failed, _integrity_hash, _integrity_ok, _read_optional_json
    global _sha256_path, _with_integrity, _zip_result, path, read_json, write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _build_zip_from_dir = namespace.get('_build_zip_from_dir', _build_zip_from_dir)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    _zip_result = namespace.get('_zip_result', _zip_result)
    path = namespace.get('path', path)
    read_json = namespace.get('read_json', read_json)
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




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreEvidenceMixin:
    def signoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
            signoff = SignoffService.seal(signoff)
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

    def export_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
            return _as_document(docs["manifest.json"])

    def build_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def verify_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        report = self._verify_archive_runtime(program_id, sanitize_metadata(payload or {}))
        return write_verification_report(report, self.archive_verification_report_path(program_id))

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        **payload: object,
    ) -> DomainDocument:
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
        reset_proof: DomainDocument,
        reset_binding: DomainDocument,
    ) -> DomainDocument:
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

    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        rows = self.read_history(program_id)
        latest: DomainDocument = {"status": "unsigned", "event": None}
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

    def read_history(self, program_id: str) -> list[DomainDocument]:
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

    def _mark_reset_board_refreshed(self, program_id: str, docs: DomainDocument) -> None:
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
