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
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest = _make_deferred_global('_manifest')
_serialize = _make_deferred_global('_serialize')
_with_integrity = _make_deferred_global('_with_integrity')
doc = _make_deferred_global('doc')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError, _history_text, _integrity_hash, _integrity_ok, _manifest, _serialize, _with_integrity
    global doc, key, read_json, row, write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest = namespace.get('_manifest', _manifest)
    _serialize = namespace.get('_serialize', _serialize)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    doc = namespace.get('doc', doc)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
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




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreArchiveMixin:
    def _signed_context(
        self,
        program_id: str,
        payload: DomainDocument,
        *,
        allow_reset_pending: bool = False,
    ) -> DomainDocument:
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

    def _archive_documents(self, program_id: str, context: DomainDocument, event: DomainDocument) -> dict[str, DomainDocument | str]:
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
        docs: dict[str, DomainDocument | str] = {
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

    def _verify_archive_runtime(self, program_id: str, payload: DomainDocument) -> DomainDocument:
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

    def _append_history(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _validate_history(self, program_id: str) -> None:
        validation = HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).validate()
        if not validation.rows:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history is missing.")
        if not validation.valid:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Acceptance history hash chain is invalid.")

    def _find_history_event(self, program_id: str, event_type: str) -> DomainDocument | None:
        signoff_hash = self.latest_signoff_state(program_id).get("signoff_hash")
        return next((row for row in reversed(self.read_history(program_id)) if row.get("event_type") == event_type and row.get("signoff_hash") == signoff_hash), None)

    def _history_through(self, program_id: str, event_hash: str) -> list[DomainDocument]:
        try:
            return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).through(event_hash)
        except ValueError as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Frozen Receiver Acceptance history event is missing.") from exc

    def _write_export_dir(self, root: Path, docs: dict[str, DomainDocument | str]) -> None:
        if root.exists():
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Immutable Receiver Acceptance export already exists.")
        root.mkdir(parents=True, exist_ok=False)
        for rel, value in docs.items():
            path = root / rel
            if isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)

    def _validate_export_dir(self, root: Path, docs: dict[str, DomainDocument | str]) -> None:
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        if actual != ARCHIVE_ENTRIES:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Immutable Receiver Acceptance export file set changed.")
        for rel, expected in docs.items():
            path = root / rel
            if not path.is_file() or path.read_bytes() != _serialize(expected):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError(f"Immutable Receiver Acceptance export changed: {rel}")
