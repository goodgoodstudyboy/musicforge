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

UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError')
UnifiedReleaseProgramContinuityCommandCenterSignoffStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterSignoffStateError')
_archive_readme = _make_deferred_global('_archive_readme')
_build_zip = _make_deferred_global('_build_zip')
_gate_failed = _make_deferred_global('_gate_failed')
_handoff_readme = _make_deferred_global('_handoff_readme')
_integrity_ok = _make_deferred_global('_integrity_ok')
_memory_file_record = _make_deferred_global('_memory_file_record')
_serialize_value = _make_deferred_global('_serialize_value')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
_with_manifest_integrity = _make_deferred_global('_with_manifest_integrity')
_zip_result = _make_deferred_global('_zip_result')
doc = _make_deferred_global('doc')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError, UnifiedReleaseProgramContinuityCommandCenterSignoffStateError, _archive_readme, _build_zip, _gate_failed, _handoff_readme, _integrity_ok
    global _memory_file_record, _serialize_value, _sha256_path, _with_integrity, _with_manifest_integrity, _zip_result, doc, read_json
    global row, write_json
    UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError', UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError)
    UnifiedReleaseProgramContinuityCommandCenterSignoffStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterSignoffStateError', UnifiedReleaseProgramContinuityCommandCenterSignoffStateError)
    _archive_readme = namespace.get('_archive_readme', _archive_readme)
    _build_zip = namespace.get('_build_zip', _build_zip)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _handoff_readme = namespace.get('_handoff_readme', _handoff_readme)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _memory_file_record = namespace.get('_memory_file_record', _memory_file_record)
    _serialize_value = namespace.get('_serialize_value', _serialize_value)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    _with_manifest_integrity = namespace.get('_with_manifest_integrity', _with_manifest_integrity)
    _zip_result = namespace.get('_zip_result', _zip_result)
    doc = namespace.get('doc', doc)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_command_center_signoff"
RESET_CHANGE_TYPE = "reset_command_center_signoff"




class UnifiedReleaseProgramContinuityCommandCenterSignoffStoreEvidenceMixin:
    def verify_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        report = self._verify_archive_runtime(program_id, sanitize_metadata(payload or {}))
        return write_unified_release_program_continuity_command_center_signoff_verification_report(
            report, self.archive_verification_report_path(program_id)
        )

    def export_final_handoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def build_final_handoff_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def verify_final_handoff_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
        **payload: object,
    ) -> DomainDocument:
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

    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        latest: DomainDocument | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "command_center_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "command_center_signoff_reset":
                latest = {"status": "reset", "previous_signoff_hash": event.get("previous_signoff_hash"), "event": event}
        return latest or {"status": "unsigned", "event": None}

    def read_history(self, program_id: str) -> list[DomainDocument]:
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

    def _current_command_center_context(self, program_id: str, payload: DomainDocument) -> DomainDocument:
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

    def _signed_context(self, program_id: str, payload: DomainDocument) -> DomainDocument:
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

    def _archive_documents(self, program_id: str, context: DomainDocument, event: DomainDocument) -> dict[str, DomainDocument | str]:
        source = context["signoff"].get("source") or {}
        fingerprint = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_fingerprint_summary", "program_id": program_id, **source})
        verification = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_verification_summary", "program_id": program_id, "status": context["external_verification"].get("status"), "runtime_status": context["runtime"].get("status"), "zip_sha256": source.get("command_center_zip_sha256"), "manifest_hash": source.get("command_center_manifest_hash"), "verification_report_hash": source.get("command_center_verification_report_hash")})
        evidence = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_external_evidence_summary", "program_id": program_id, "external_evidence_manifest_hash": source.get("external_evidence_manifest_hash"), "current_generation": source.get("current_generation"), "current_generation_hash": source.get("current_generation_hash"), "acceptance_signoff_hash": source.get("acceptance_signoff_hash"), "acceptance_history_event_hash": source.get("acceptance_history_event_hash")})
        checklist = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_final_handoff_checklist", "program_id": program_id, "status": "ready", "items": [{"check_id": "runtime_ready", "status": "passed"}, {"check_id": "current_generation", "status": "passed"}, {"check_id": "external_binding", "status": "passed"}], "blockers": []})
        history_rows = self._history_through(program_id, str(event.get("event_hash") or ""))
        docs: dict[str, DomainDocument | str] = {
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

    def _handoff_context(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        signed = self._signed_context(program_id, payload)
        if not self.archive_zip_path(program_id).exists() or not self.archive_verification_report_path(program_id).exists():
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Verified Command Center Signoff Archive is required for Final Handoff.")
        external = read_json(self.archive_verification_report_path(program_id))
        runtime = self._verify_archive_runtime(program_id, payload)
        if external.get("package_type") != COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external) or external.get("status") != "passed" or runtime.get("status") != "passed" or external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center Signoff Archive verification is missing, stale, or failed.")
        return {**signed, "archive_external": external, "archive_runtime": runtime}

    def _handoff_documents(self, program_id: str, context: DomainDocument, event: DomainDocument) -> dict[str, DomainDocument | str]:
        archive_summary = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_archive_verification_summary", "program_id": program_id, "status": context["archive_external"].get("status"), "zip_sha256": context["archive_runtime"].get("zip_sha256"), "manifest_hash": context["archive_runtime"].get("manifest_hash"), "verification_report_hash": context["archive_external"].get("integrity_hash")})
        handoff = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_final_handoff_summary", "program_id": program_id, "status": "ready", "created_at": event.get("created_at"), "signed_by": context["signoff"].get("signed_by"), "signed_at": context["signoff"].get("signed_at"), "signoff_hash": context["signoff"].get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash"), "archive_zip_sha256": archive_summary.get("zip_sha256"), "archive_manifest_hash": archive_summary.get("manifest_hash"), "archive_verification_report_hash": archive_summary.get("verification_report_hash")})
        receiver = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_receiver_checklist", "program_id": program_id, "status": "ready", "items": [{"item_id": "verify-archive", "status": "required"}, {"item_id": "verify-signoff-binding", "status": "required"}]})
        docs: dict[str, DomainDocument | str] = {"README.txt": _handoff_readme(program_id), "final-handoff-summary.json": handoff, "receiver-checklist.json": receiver, "archive-verification-summary.json": archive_summary, "signoff-binding-summary.json": context["binding"]}
        manifest = _with_manifest_integrity({"schema_version": 1, "package_type": COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, "program_id": program_id, "created_at": event.get("created_at"), "source": {"final_handoff_summary_hash": handoff.get("integrity_hash"), "archive_verification_summary_hash": archive_summary.get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash")}, "files": [_memory_file_record(path, value) for path, value in docs.items()], "zip": {"entries": sorted(HANDOFF_REQUIRED_ENTRIES)}})
        return {"manifest.json": manifest, **docs}

    def _verify_archive_runtime(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return verify_unified_release_program_continuity_command_center_signoff_package(
            payload.get("archive_zip") or payload.get("archive_zip_path") or self.archive_zip_path(program_id),
            strict=True,
            require_signed=True,
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_binding_path(program_id),
            command_center_zip_path=payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.command_store.zip_path(program_id),
            command_center_verification_report_path=payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.command_store.verification_report_path(program_id),
            command_center_external_evidence_manifest_path=payload.get("command_center_external_evidence_manifest") or payload.get("external_evidence_manifest") or self.command_store.local_evidence_manifest_path(program_id),
        )

    def _verify_handoff_runtime(self, program_id: str, payload: DomainDocument) -> DomainDocument:
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

    def _signoff_binding(self, signoff: DomainDocument, event: DomainDocument) -> DomainDocument:
        source = _as_document(signoff.get("source"))
        return _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_binding", "program_id": signoff.get("program_id"), "created_at": now_iso(), "signoff_hash": signoff.get("integrity_hash"), "signoff_payload_hash": signoff.get("payload_hash"), "signed_by": signoff.get("signed_by"), "role": signoff.get("role"), "reason_hash": stable_hash({"reason": signoff.get("reason")}), "signed_at": signoff.get("signed_at"), "history_event_hash": event.get("event_hash"), **source})

    def _append_history(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _validate_history(self, program_id: str) -> None:
        if not HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).validate().valid:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Command Center signoff history hash chain is invalid.")

    def _find_history_event(self, program_id: str, event_type: str, signoff_hash: object) -> DomainDocument | None:
        return next((row for row in reversed(self.read_history(program_id)) if row.get("event_type") == event_type and row.get("signoff_hash") == signoff_hash), None)

    def _archive_export_event(self, program_id: str) -> DomainDocument:
        latest = self.latest_signoff_state(program_id)
        event = self._find_history_event(program_id, "command_center_signoff_archive_exported", latest.get("signoff_hash"))
        if not event:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Archive export history event is missing.")
        return event

    def _history_through(self, program_id: str, event_hash: str) -> list[DomainDocument]:
        try:
            return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).through(event_hash)
        except ValueError as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Frozen archive history event is missing.") from exc

    def _assert_request_current(self, program_id: str, request: DomainDocument) -> None:
        context = self._signed_context(program_id, {})
        source = context["signoff"].get("source") or {}
        expected = {"signoff_hash": context["signoff"].get("integrity_hash"), "signoff_binding_hash": context["binding"].get("integrity_hash"), "command_center_zip_sha256": source.get("command_center_zip_sha256"), "command_center_manifest_hash": source.get("command_center_manifest_hash"), "command_center_verification_report_hash": source.get("command_center_verification_report_hash"), "external_evidence_manifest_hash": source.get("external_evidence_manifest_hash")}
        if request.get("target") != expected:
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Change Request does not bind current signed Command Center evidence.")

    def _read_change_request(self, program_id: str, request_id: str) -> DomainDocument:
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

    def _write_export_dir(self, root: Path, docs: dict[str, DomainDocument | str]) -> None:
        if root.exists():
            raise UnifiedReleaseProgramContinuityCommandCenterSignoffStateError("Immutable export directory already exists.")
        root.mkdir(parents=True, exist_ok=False)
        for rel, value in docs.items():
            path = root / rel
            if isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)

    def _validate_export_dir(self, root: Path, docs: dict[str, DomainDocument | str], required: set[str]) -> None:
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
