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

UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError')
UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError')
_file_record = _make_deferred_global('_file_record')
_package_manifest = _make_deferred_global('_package_manifest')
info = _make_deferred_global('info')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError, UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError, _file_record, _package_manifest, info, key, read_json
    global row, write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError)
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError)
    _file_record = namespace.get('_file_record', _file_record)
    _package_manifest = namespace.get('_package_manifest', _package_manifest)
    info = namespace.get('info', info)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_receiver_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_receiver_acceptance_signoff"




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreEvidenceMixin:
    def export_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            docs = self._archive_documents(program_id)
            export_dir = self.archive_export_dir(program_id)
            if export_dir.exists():
                self._validate_archive_export(program_id, export_dir, docs)
                return read_json(export_dir / "manifest.json")
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_entry(rel: str, value: DomainDocument | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, str):
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            write_entry("README.txt", "MusicForge Unified Release Program Command Center Receiver Acceptance Change Control Archive\n")
            write_entry("state.json", docs["state"])
            write_entry("request-index.json", docs["request_index"])
            write_entry("reset-index.json", docs["reset_index"])
            write_entry("generation.json", docs["generation"])
            write_entry("lifecycle.json", docs["lifecycle"])
            write_entry("events.jsonl", _history_text(docs["events"]))
            for request_id, bundle in sorted(docs["requests"].items()):
                write_entry(f"cr/{request_id}/request.json", bundle["request"])
                if bundle.get("approval"):
                    write_entry(f"cr/{request_id}/approval.json", bundle["approval"])
                write_entry(f"cr/{request_id}/binding.json", bundle["binding"])
            for reset_id, bundle in sorted(docs["resets"].items()):
                write_entry(f"rp/{reset_id}/proof.json", bundle["proof"])
                write_entry(f"rp/{reset_id}/binding.json", bundle["binding"])
            for generation, bundle in sorted(docs["generations"].items()):
                prefix = f"gen/g{generation:06d}"
                write_entry(f"{prefix}/verification.json", bundle["verification_summary"])
                write_entry(f"{prefix}/signoff-binding.json", bundle["signoff_binding_summary"])
                write_entry(f"{prefix}/source.json", bundle["source_summary"])
            manifest = _package_manifest(
                UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE,
                program_id,
                files,
                {
                    "change_control_state_hash": docs["state"].get("integrity_hash"),
                    "change_request_index_hash": docs["request_index"].get("integrity_hash"),
                    "reset_proof_index_hash": docs["reset_index"].get("integrity_hash"),
                    "current_generation_hash": docs["generation"].get("integrity_hash"),
                    "lifecycle_report_hash": docs["lifecycle"].get("integrity_hash"),
                    "latest_acceptance_signoff_hash": docs["state"].get("latest_acceptance_signoff_hash"),
                    "latest_reset_proof_hash": docs["state"].get("latest_reset_proof_hash"),
                },
            )
            write_json(export_dir / "manifest.json", manifest)
            return manifest

    def build_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            docs = self._archive_documents(program_id)
            zip_path = self.archive_zip_path(program_id)
            if zip_path.exists():
                export_dir = self.archive_export_dir(program_id)
                if export_dir.exists():
                    self._validate_archive_export(program_id, export_dir, docs)
                runtime = verify_unified_release_program_continuity_command_center_acceptance_change_package(
                    zip_path,
                    strict=True,
                    require_current_acceptance=True,
                    acceptance_archive_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
                    acceptance_verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.archive_verification_report_path(program_id),
                    acceptance_signoff_binding_path=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
                    previous_acceptance_root=payload.get("previous_acceptance_root") or self.generations_dir(program_id),
                    require_reset_proofs=True,
                )
                if runtime.get("status") != "passed":
                    raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                        "Existing Receiver Acceptance Change Control Archive failed runtime verification."
                    )
                return {
                    "status": "passed",
                    "zip_path": str(zip_path),
                    "zip_sha256": _sha256_path(zip_path),
                    "manifest_hash": runtime.get("manifest_hash"),
                }
            self.export_archive(program_id)
            export_dir = self.archive_export_dir(program_id)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "entries": entries, "entry_count": len(entries)}
            manifest["files"] = sorted(
                (
                    _file_record(path, path.relative_to(export_dir).as_posix())
                    for path in export_dir.rglob("*")
                    if path.is_file() and path.name != "manifest.json"
                ),
                key=lambda row: str(row.get("path") or ""),
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            zip_path.unlink(missing_ok=True)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            runtime = verify_unified_release_program_continuity_command_center_acceptance_change_package(
                zip_path,
                strict=True,
                require_current_acceptance=True,
                acceptance_archive_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
                acceptance_verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.archive_verification_report_path(program_id),
                acceptance_signoff_binding_path=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
                previous_acceptance_root=payload.get("previous_acceptance_root") or self.generations_dir(program_id),
                require_reset_proofs=True,
            )
            if runtime.get("status") != "passed":
                zip_path.unlink(missing_ok=True)
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    "Built Receiver Acceptance Change Control Archive failed verification: "
                    + ", ".join(runtime.get("blockers") or [])
                )
            return {"status": "passed", "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest_hash": manifest.get("integrity_hash")}

    def verify_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_release_program_continuity_command_center_acceptance_change_package(
            payload.get("archive_zip") or payload.get("zip_path") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current_acceptance=bool(payload.get("require_current_acceptance", True)),
            acceptance_archive_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
            acceptance_verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.archive_verification_report_path(program_id),
            acceptance_signoff_binding_path=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
            previous_acceptance_root=payload.get("previous_acceptance_root") or self.generations_dir(program_id),
            require_reset_proofs=bool(payload.get("require_reset_proofs", True)),
        )
        write_unified_release_program_continuity_command_center_acceptance_change_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, archive_zip_path: Path | str | None = None, verification_report_path: Path | str | None = None, **payload: object) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        if self.acceptance_store.latest_signoff_state(program_id).get("status") != "signed":
            return _gate_failed("Command Center Receiver Acceptance Board has been reset and must be re-signed.")
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Command Center Receiver Acceptance Change Control Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Command Center Receiver Acceptance Change Control verification report is missing.")
        try:
            self._archive_documents(program_id)
            acceptance_gate = self.acceptance_store.gate(
                program_id,
                required=True,
                archive_zip_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
                verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.archive_verification_report_path(program_id),
                acceptance_signoff_binding=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
                **{key: value for key, value in payload.items() if key not in {"acceptance_archive", "acceptance_verification_report", "acceptance_signoff_binding"}},
            )
            if acceptance_gate.get("status") != "passed":
                return _gate_failed("Current Receiver Acceptance runtime gate failed.", acceptance_gate=acceptance_gate)
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_command_center_acceptance_change_package(
                zip_path,
                strict=True,
                require_current_acceptance=True,
                acceptance_archive_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
                acceptance_verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.archive_verification_report_path(program_id),
                acceptance_signoff_binding_path=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
                previous_acceptance_root=payload.get("previous_acceptance_root") or self.generations_dir(program_id),
                require_reset_proofs=True,
            )
            if (
                external.get("package_type") != "musicforge_unified_release_program_continuity_command_center_acceptance_change_control_verification"
                or not _integrity_ok(external)
            ):
                return _gate_failed("Command Center Receiver Acceptance Change Control verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Command Center Receiver Acceptance Change Control verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Command Center Receiver Acceptance Change Control verification report does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def read_change_request(self, program_id: str, request_id: str) -> DomainDocument:
        path = self.request_path(program_id, _safe_id(request_id))
        if not path.exists():
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError(f"Command Center Receiver Acceptance Change Request not found: {request_id}")
        return read_json(path)

    def list_change_requests(self, program_id: str) -> list[DomainDocument]:
        base = self.requests_dir(program_id)
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*/change-request.json"))]

    def list_reset_proofs(self, program_id: str) -> list[DomainDocument]:
        base = self.reset_proofs_dir(program_id)
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*/reset-proof.json"))]

    def read_lifecycle_events(self, program_id: str) -> list[DomainDocument]:
        return HistoryChain(self.lifecycle_event_log_path(program_id), sanitizer=sanitize_metadata).read()

    def _current_acceptance_state(self, program_id: str) -> DomainDocument:
        latest = self.acceptance_store.latest_signoff_state(program_id)
        if latest.get("status") != "signed":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Board must be currently signed.")
        archive_path = self.acceptance_store.archive_zip_path(program_id)
        verification_path = self.acceptance_store.archive_verification_report_path(program_id)
        signoff_path = self.acceptance_store.signoff_path(program_id)
        binding_path = self.acceptance_store.signoff_binding_path(program_id)
        missing = [str(path) for path in (archive_path, verification_path, signoff_path, binding_path) if not path.exists()]
        if missing:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance signed evidence is incomplete: " + ", ".join(missing))
        runtime = self.acceptance_store._verify_archive_runtime(program_id, {})
        external = read_json(verification_path)
        signoff = read_json(signoff_path)
        binding = read_json(binding_path)
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance verification report integrity failed.")
        if runtime.get("status") != "passed" or external.get("status") != "passed":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Archive verification failed.")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance verification report does not match current archive.")
        if not _integrity_ok(signoff) or not _integrity_ok(binding):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance signoff binding integrity failed.")
        if latest.get("signoff_hash") != signoff.get("integrity_hash") or binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance latest signoff does not match binding.")
        acceptance_state = _read_optional_json(self.acceptance_store.state_path(program_id))
        generation = int(acceptance_state.get("generation") or signoff.get("generation") or 1)
        tracked_generation = _read_optional_json(self.current_generation_path(program_id))
        if tracked_generation and int(tracked_generation.get("generation") or 0) != generation:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                "Command Center Receiver Acceptance generation does not match Change Control."
            )
        report_source = (_read_optional_json(self.acceptance_store.board_report_path(program_id)).get("source") or {})
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_current_state",
                "program_id": program_id,
                "generation": generation,
                "status": "signed",
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "signoff_binding_hash": binding.get("integrity_hash"),
                "history_event_hash": binding.get("history_event_hash"),
                "archive_zip_sha256": runtime.get("zip_sha256"),
                "archive_size_bytes": runtime.get("zip_size_bytes"),
                "archive_manifest_hash": runtime.get("manifest_hash"),
                "verification_report_hash": external.get("integrity_hash"),
                "verification_status": external.get("status"),
                "board_report_hash": signoff.get("board_report_hash"),
                "decision_matrix_hash": signoff.get("decision_matrix_hash"),
                "quorum_report_hash": signoff.get("quorum_report_hash"),
                "findings_register_hash": signoff.get("findings_register_hash"),
                "accepted_evidence_index_hash": signoff.get("accepted_evidence_index_hash"),
                "response_proof_index_hash": signoff.get("response_proof_index_hash"),
                "review_pack_source_hash": signoff.get("review_pack_source_hash"),
                "command_center_signoff_archive_zip_sha256": report_source.get("command_center_signoff_archive_zip_sha256"),
                "command_center_final_handoff_zip_sha256": report_source.get("command_center_final_handoff_zip_sha256"),
            }
        )

    def _assert_request_current(self, program_id: str, request: DomainDocument) -> DomainDocument:
        if not _integrity_ok(request):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request integrity failed.")
        current = self._current_acceptance_state(program_id)
        expected_target = self._target_from_state(current)
        if request.get("target") != expected_target:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Request target no longer matches current signoff.")
        source = _as_document(request.get("source"))
        for field in ("signoff_hash", "signoff_binding_hash", "archive_zip_sha256", "archive_manifest_hash", "verification_report_hash"):
            if source.get(field) != current.get(field):
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(f"Command Center Receiver Acceptance Change Request source mismatch: {field}")
        return current

    def _target_from_state(self, state: DomainDocument) -> DomainDocument:
        return {
            "component_type": "unified_release_program_continuity_command_center_receiver_acceptance",
            "program_id": state.get("program_id"),
            "acceptance_signoff_hash": state.get("signoff_hash"),
            "acceptance_signoff_binding_hash": state.get("signoff_binding_hash"),
            "acceptance_archive_zip_sha256": state.get("archive_zip_sha256"),
            "acceptance_archive_manifest_hash": state.get("archive_manifest_hash"),
            "acceptance_verification_report_hash": state.get("verification_report_hash"),
            "generation": state.get("generation"),
        }

    def _existing_open_request(self, program_id: str, signoff_hash: str | None) -> DomainDocument | None:
        for request in self.list_change_requests(program_id):
            if request.get("status") in {"submitted", "draft", "approved"} and not request.get("applied_at") and (request.get("target") or {}).get("acceptance_signoff_hash") == signoff_hash:
                return request
        return None

    def _write_request_binding(self, program_id: str, request: DomainDocument, approval: DomainDocument | None, current: DomainDocument) -> DomainDocument:
        binding = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_change_request_binding_report",
                "program_id": program_id,
                "change_request_id": request.get("change_request_id"),
                "status": request.get("status"),
                "change_type": request.get("change_type"),
                "allowed_actions": request.get("allowed_actions") or [],
                "request_hash": request.get("integrity_hash"),
                "request_payload_hash": request.get("payload_hash"),
                "approval_hash": (approval or {}).get("integrity_hash"),
                "target": request.get("target"),
                "source": current,
            }
        )
        write_json(self.request_binding_path(program_id, str(request.get("change_request_id") or "")), binding)
        return binding

    def _write_generation(self, program_id: str, generation: int, status: str, proof: DomainDocument | None = None) -> DomainDocument:
        existing = _read_optional_json(self.current_generation_path(program_id))
        if int(existing.get("generation") or -1) != generation:
            existing = {}
        doc = GenerationService.build_document(
            GenerationRef(
                program_id,
                generation,
                status,
                previous_generation=(proof or {}).get("previous_generation") if proof else existing.get("previous_generation"),
                reset_proof_hash=(proof or {}).get("integrity_hash") or existing.get("reset_proof_hash"),
            ),
            package_type="musicforge_unified_release_program_continuity_command_center_acceptance_generation",
            schema_version=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
            extra={"program_id": program_id, "updated_at": now_iso()},
        )
        write_json(self.current_generation_path(program_id), doc)
        return doc

    def _change_control_state(self, program_id: str) -> DomainDocument:
        existing = _read_optional_json(self.state_path(program_id))
        latest = self.acceptance_store.latest_signoff_state(program_id)
        current: DomainDocument = {}
        status = str(latest.get("status") or "unsigned")
        try:
            if status == "signed":
                current = self._current_acceptance_state(program_id)
        except Exception as exc:
            current = {"status": "failed", "error": sanitize_sensitive_text(str(exc))}
            status = "failed"
        resets = self.list_reset_proofs(program_id)
        requests = self.list_change_requests(program_id)
        doc = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_change_control_state",
                "program_id": program_id,
                "status": "passed" if status == "signed" else "needs_successor_signoff" if status == "reset_pending" else status,
                "latest_acceptance_status": status,
                "latest_acceptance_signoff_hash": current.get("signoff_hash") or latest.get("signoff_hash"),
                "latest_reset_proof_hash": resets[-1].get("integrity_hash") if resets else None,
                "request_count": len(requests),
                "reset_count": len(resets),
                "current_acceptance": current,
                "created_at": existing.get("created_at") or now_iso(),
            }
        )
        return doc

    def _change_request_index(self, program_id: str) -> DomainDocument:
        rows = []
        for request in self.list_change_requests(program_id):
            request_id = str(request.get("change_request_id") or "")
            approval = _read_optional_json(self.approval_path(program_id, request_id))
            binding = _read_optional_json(self.request_binding_path(program_id, request_id))
            rows.append(
                {
                    "change_request_id": request_id,
                    "status": request.get("status"),
                    "change_type": request.get("change_type"),
                    "allowed_actions": request.get("allowed_actions") or [],
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "binding_hash": binding.get("integrity_hash"),
                    "target_signoff_hash": (request.get("target") or {}).get("acceptance_signoff_hash"),
                    "reset_proof_hash": request.get("reset_proof_hash"),
                }
            )
        return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_change_request_index", "program_id": program_id, "items": rows, "summary": {"request_count": len(rows), "approved_count": sum(1 for row in rows if row.get("status") in {"approved", "applied"}), "applied_count": sum(1 for row in rows if row.get("status") == "applied")}})

    def _reset_proof_index(self, program_id: str) -> DomainDocument:
        rows = []
        for proof in self.list_reset_proofs(program_id):
            reset_id = str(proof.get("reset_id") or "")
            binding = _read_optional_json(self.reset_binding_path(program_id, reset_id))
            rows.append(
                {
                    "reset_id": reset_id,
                    "change_request_id": proof.get("change_request_id"),
                    "status": proof.get("status"),
                    "reset_proof_hash": proof.get("integrity_hash"),
                    "binding_hash": binding.get("integrity_hash"),
                    "reset_event_hash": proof.get("reset_event_hash"),
                    "previous_signoff_hash": proof.get("previous_signoff_hash"),
                    "next_generation": proof.get("next_generation"),
                }
            )
        return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof_index", "program_id": program_id, "items": rows, "summary": {"reset_count": len(rows)}})
