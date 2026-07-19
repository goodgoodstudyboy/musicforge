# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import GenerationRef as GenerationRef, ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, GenerationService as GenerationService, HistoryChain as HistoryChain, ResetService as ResetService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_acceptance import UnifiedReleaseProgramContinuityAcceptanceStore as UnifiedReleaseProgramContinuityAcceptanceStore, _bounded as _bounded, _file_record as _file_record, _gate_failed as _gate_failed, _history_text as _history_text, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _package_manifest as _package_manifest, _read_optional_json as _read_optional_json, _safe_id as _safe_id, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_acceptance_package as verify_unified_release_program_continuity_acceptance_package
from song_agent.domains.program.unified_release_program_continuity_acceptance_change_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, continuity_acceptance_change_reset_semantic_checks as continuity_acceptance_change_reset_semantic_checks, verify_unified_release_program_continuity_acceptance_change_package as verify_unified_release_program_continuity_acceptance_change_package, write_unified_release_program_continuity_acceptance_change_verification_report as write_unified_release_program_continuity_acceptance_change_verification_report

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

UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError = _make_deferred_global('UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError')
UnifiedReleaseProgramContinuityAcceptanceChangeStateError = _make_deferred_global('UnifiedReleaseProgramContinuityAcceptanceChangeStateError')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
value = _make_deferred_global('value')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError, UnifiedReleaseProgramContinuityAcceptanceChangeStateError, item, key, read_json, row, value
    global write_json
    UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError = namespace.get('UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError', UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError)
    UnifiedReleaseProgramContinuityAcceptanceChangeStateError = namespace.get('UnifiedReleaseProgramContinuityAcceptanceChangeStateError', UnifiedReleaseProgramContinuityAcceptanceChangeStateError)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    value = namespace.get('value', value)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_continuity_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_continuity_acceptance_signoff"




class UnifiedReleaseProgramContinuityAcceptanceChangeStoreEvidenceMixin:
    def read_change_request(self, program_id: str, request_id: str) -> DomainDocument:
        path = self.request_path(program_id, _safe_id(request_id))
        if not path.exists():
            raise UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError(f"Continuity Acceptance Change Request not found: {request_id}")
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
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Board must be currently signed.")
        archive_path = self.acceptance_store.archive_zip_path(program_id)
        verification_path = self.acceptance_store.verification_report_path(program_id)
        signoff_path = self.acceptance_store.signoff_path(program_id)
        binding_path = self.acceptance_store.signoff_binding_path(program_id)
        missing = [str(path) for path in (archive_path, verification_path, signoff_path, binding_path) if not path.exists()]
        if missing:
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance signed evidence is incomplete: " + ", ".join(missing))
        runtime = verify_unified_release_program_continuity_acceptance_package(
            archive_path,
            strict=True,
            require_current_kit=True,
            require_signed=True,
            require_quorum=True,
            continuity_kit_path=self.acceptance_store.kit_store.kit_zip_path(program_id),
            continuity_kit_verification_report_path=self.acceptance_store.kit_store.verification_report_path(program_id),
            signoff_binding_path=binding_path,
        )
        external = read_json(verification_path)
        signoff = read_json(signoff_path)
        binding = read_json(binding_path)
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance verification report integrity failed.")
        if runtime.get("status") != "passed" or external.get("status") != "passed":
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Archive verification failed.")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance verification report does not match current archive.")
        if not _integrity_ok(signoff) or not _integrity_ok(binding):
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance signoff binding integrity failed.")
        if latest.get("signoff_hash") != signoff.get("integrity_hash") or binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance latest signoff does not match binding.")
        generation = int((_read_optional_json(self.current_generation_path(program_id)).get("generation") or 1))
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_current_state",
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
                "receiver_index_hash": signoff.get("receiver_index_hash"),
                "accepted_evidence_index_hash": signoff.get("accepted_evidence_index_hash"),
                "source_binding_hash": signoff.get("source_binding_hash"),
            }
        )

    def _assert_request_current(self, program_id: str, request: DomainDocument) -> DomainDocument:
        if not _integrity_ok(request):
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request integrity failed.")
        current = self._current_acceptance_state(program_id)
        expected_target = self._target_from_state(current)
        if request.get("target") != expected_target:
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request target no longer matches current signoff.")
        source = _as_document(request.get("source"))
        for field in ("signoff_hash", "signoff_binding_hash", "archive_zip_sha256", "archive_manifest_hash", "verification_report_hash"):
            if source.get(field) != current.get(field):
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError(f"Continuity Acceptance Change Request source mismatch: {field}")
        return current

    def _target_from_state(self, state: DomainDocument) -> DomainDocument:
        return {
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
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_change_request_binding_report",
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
        doc = GenerationService.build_document(
            GenerationRef(
                program_id,
                generation,
                status,
                previous_generation=(proof or {}).get("previous_generation"),
                reset_proof_hash=(proof or {}).get("integrity_hash"),
            ),
            package_type="musicforge_unified_release_program_continuity_acceptance_generation",
            schema_version=UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
            extra={"program_id": program_id, "updated_at": now_iso()},
        )
        write_json(self.current_generation_path(program_id), doc)
        return doc

    def _change_control_state(self, program_id: str) -> DomainDocument:
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
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_change_control_state",
                "program_id": program_id,
                "status": "passed" if status == "signed" else "needs_successor_signoff" if status == "reset" else status,
                "latest_acceptance_status": status,
                "latest_acceptance_signoff_hash": current.get("signoff_hash") or latest.get("signoff_hash"),
                "latest_reset_proof_hash": resets[-1].get("integrity_hash") if resets else None,
                "request_count": len(requests),
                "reset_count": len(resets),
                "current_acceptance": current,
                "created_at": now_iso(),
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
        return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_change_request_index", "program_id": program_id, "items": rows, "summary": {"request_count": len(rows), "approved_count": sum(1 for row in rows if row.get("status") in {"approved", "applied"}), "applied_count": sum(1 for row in rows if row.get("status") == "applied")}})

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
        return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_reset_proof_index", "program_id": program_id, "items": rows, "summary": {"reset_count": len(rows)}})

    def _lifecycle_report(self, program_id: str, state: DomainDocument, request_index: DomainDocument, reset_index: DomainDocument) -> DomainDocument:
        events = self.read_lifecycle_events(program_id)
        history_ok = all(row.get("event_hash") == stable_hash({key: value for key, value in row.items() if key != "event_hash"}) for row in events)
        blockers = []
        if not history_ok:
            blockers.append("lifecycle_history_integrity")
        if state.get("latest_acceptance_status") == "reset":
            blockers.append("successor_acceptance_signoff_required")
        status = "passed" if not blockers else "failed"
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_lifecycle_report",
                "program_id": program_id,
                "status": status,
                "summary": {
                    "change_request_count": (request_index.get("summary") or {}).get("request_count"),
                    "reset_count": (reset_index.get("summary") or {}).get("reset_count"),
                    "latest_acceptance_status": state.get("latest_acceptance_status"),
                    "event_count": len(events),
                },
                "blockers": blockers,
                "source": {
                    "state_hash": state.get("integrity_hash"),
                    "change_request_index_hash": request_index.get("integrity_hash"),
                    "reset_proof_index_hash": reset_index.get("integrity_hash"),
                    "event_hashes": [row.get("event_hash") for row in events],
                },
                "created_at": now_iso(),
            }
        )

    def _archive_documents(self, program_id: str) -> DomainDocument:
        state = self._change_control_state(program_id)
        if state.get("status") != "passed" or state.get("latest_acceptance_status") != "signed":
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Control Archive requires a current signed Acceptance Board.")
        request_index = self._change_request_index(program_id)
        reset_index = self._reset_proof_index(program_id)
        lifecycle = self._lifecycle_report(program_id, state, request_index, reset_index)
        events = self.read_lifecycle_events(program_id)
        generation = _read_optional_json(self.current_generation_path(program_id)) or self._write_generation(program_id, 1, "current_signed" if state.get("latest_acceptance_status") == "signed" else "unsigned")
        requests = {}
        for request in self.list_change_requests(program_id):
            request_id = str(request.get("change_request_id") or "")
            requests[request_id] = {"request": request, "approval": _read_optional_json(self.approval_path(program_id, request_id)), "binding": _read_optional_json(self.request_binding_path(program_id, request_id))}
        resets = {}
        for proof in self.list_reset_proofs(program_id):
            reset_id = str(proof.get("reset_id") or "")
            resets[reset_id] = {"proof": proof, "binding": _read_optional_json(self.reset_binding_path(program_id, reset_id))}
        reset_checks = continuity_acceptance_change_reset_semantic_checks(resets, requests, events, reset_index)
        reset_blockers = [row.get("check_id") for row in reset_checks if row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"]
        if reset_blockers:
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance reset proof binding failed: " + ", ".join(str(item) for item in reset_blockers[:5]))
        generations = self._generation_summaries(program_id, state, resets)
        return {"state": state, "request_index": request_index, "reset_index": reset_index, "lifecycle": lifecycle, "events": events, "generation": generation, "requests": requests, "resets": resets, "generations": generations}

    def _generation_summaries(self, program_id: str, state: DomainDocument, resets: dict[str, DomainDocument]) -> dict[int, DomainDocument]:
        generation_number = int((_read_optional_json(self.current_generation_path(program_id)).get("generation") or 1))
        summaries: dict[int, DomainDocument] = {}
        acceptance_verification = _read_optional_json(self.acceptance_store.verification_report_path(program_id))
        signoff_binding = _read_optional_json(self.acceptance_store.signoff_binding_path(program_id))
        source = _as_document(state.get("current_acceptance"))
        summaries[generation_number] = {
            "verification_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_generation_verification_summary", "program_id": program_id, "generation": generation_number, "verification_status": acceptance_verification.get("status"), "verification_report_hash": acceptance_verification.get("integrity_hash"), "archive_zip_sha256": acceptance_verification.get("zip_sha256"), "archive_manifest_hash": acceptance_verification.get("manifest_hash")}),
            "signoff_binding_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_generation_signoff_binding_summary", "program_id": program_id, "generation": generation_number, "signoff_hash": signoff_binding.get("signoff_hash"), "signoff_binding_hash": signoff_binding.get("integrity_hash"), "history_event_hash": signoff_binding.get("history_event_hash")}),
            "source_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_generation_source_summary", "program_id": program_id, "generation": generation_number, "source": source}),
        }
        return summaries

    def _append_lifecycle_event(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.lifecycle_event_log_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _next_request_id(self, program_id: str) -> str:
        self.requests_dir(program_id).mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.requests_dir(program_id).glob("cr-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"cr-{max_seen + 1:06d}"
