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

UnifiedReleaseProgramContinuityAcceptanceChangeStateError = _make_deferred_global('UnifiedReleaseProgramContinuityAcceptanceChangeStateError')
action = _make_deferred_global('action')
info = _make_deferred_global('info')
key = _make_deferred_global('key')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityAcceptanceChangeStateError, action, info, key, read_json, write_json
    UnifiedReleaseProgramContinuityAcceptanceChangeStateError = namespace.get('UnifiedReleaseProgramContinuityAcceptanceChangeStateError', UnifiedReleaseProgramContinuityAcceptanceChangeStateError)
    action = namespace.get('action', action)
    info = namespace.get('info', info)
    key = namespace.get('key', key)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_continuity_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_continuity_acceptance_signoff"




class UnifiedReleaseProgramContinuityAcceptanceChangeStoreReadinessMixin:
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
        with self.lock:
            current = self._current_acceptance_state(program_id)
            existing = self._existing_open_request(program_id, current.get("signoff_hash"))
            if existing:
                return existing
            request_id = _safe_id(str(payload.get("change_request_id") or self._next_request_id(program_id)))
            if self.request_path(program_id, request_id).exists():
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError(f"Continuity Acceptance Change Request already exists: {request_id}")
            now = now_iso()
            allowed_actions = list(payload.get("allowed_actions") or [RESET_ACTION])
            request = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE,
                    "program_id": program_id,
                    "change_request_id": request_id,
                    "status": "submitted",
                    "change_type": _bounded(payload.get("change_type") or RESET_CHANGE_TYPE, 160),
                    "allowed_actions": [_bounded(action, 160) for action in allowed_actions],
                    "reason": _bounded(payload.get("reason") or "Continuity Acceptance evidence requires controlled reset.", 1000),
                    "requested_by": _bounded(payload.get("requested_by") or "continuity-operator", 120),
                    "created_at": now,
                    "updated_at": now,
                    "target": self._target_from_state(current),
                    "source": current,
                    "tool": {"name": "MusicForge Continuity Acceptance Change Control", "version": __version__},
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
                    "event_type": "continuity_acceptance_change_request_submitted",
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
        request_id = _safe_id(request_id)
        with self.lock:
            request = self.read_change_request(program_id, request_id)
            if request.get("status") not in {"submitted", "draft"}:
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Only submitted Continuity Acceptance Change Requests can be approved.")
            current = self._assert_request_current(program_id, request)
            now = now_iso()
            submitted_request_hash = request.get("integrity_hash")
            approved_actions = list(payload.get("approved_actions") or request.get("allowed_actions") or [])
            approval = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_acceptance_change_approval",
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
                    "event_type": "continuity_acceptance_change_request_approved",
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

    def reset_acceptance_signoff(self, program_id: str, request_id: str | DomainDocument | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        if isinstance(request_id, dict):
            payload = request_id
            request_id = None
        payload = payload or {}
        request_id = _safe_id(str(request_id or payload.get("change_request_id") or ""))
        if not request_id:
            raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("change_request_id is required for Continuity Acceptance reset.")
        with self.lock:
            request = self.read_change_request(program_id, request_id)
            if request.get("status") != "approved" or request.get("applied_at"):
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request must be approved and unused before reset.")
            if request.get("change_type") != RESET_CHANGE_TYPE:
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request is not scoped to signoff reset.")
            if RESET_ACTION not in set(request.get("allowed_actions") or []):
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request does not allow reset_continuity_acceptance_signoff.")
            approval = read_json(self.approval_path(program_id, request_id))
            try:
                ChangeRequestService.validate_reset_authorization(
                    request,
                    approval,
                    ResetAuthorization(program_id, request_id, RESET_ACTION, RESET_CHANGE_TYPE, request.get("target") or {}, request.get("source") or {}),
                )
            except ValueError as exc:
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError(str(exc)) from exc
            if not _integrity_ok(approval) or approval.get("status") != "approved":
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request approval integrity failed.")
            if RESET_ACTION not in set(approval.get("approved_actions") or []):
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request approval does not allow reset.")
            if approval.get("target") != request.get("target") or approval.get("source") != request.get("source"):
                raise UnifiedReleaseProgramContinuityAcceptanceChangeStateError("Continuity Acceptance Change Request approval binding mismatch.")
            current = self._assert_request_current(program_id, request)
            now = now_iso()
            previous_generation = int(current.get("generation") or 1)
            reset_id = f"reset-{len(self.list_reset_proofs(program_id)) + 1:06d}"
            approved_request_hash = request.get("integrity_hash")
            reset_event = self.acceptance_store._append_history(
                program_id,
                {
                    "event_type": "continuity_acceptance_signoff_reset",
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
                    "reason": _bounded(payload.get("reason") or approval.get("reason") or "Approved Continuity Acceptance reset.", 1000),
                },
            )
            proof = ResetService.build_proof(sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_acceptance_reset_proof",
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
                    "previous_archive_manifest_hash": current.get("archive_manifest_hash"),
                    "previous_verification_report_hash": current.get("verification_report_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "reset_event_payload_hash": reset_event.get("payload_hash"),
                    "source": current,
                }
            ))
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_acceptance_reset_proof_binding_summary",
                    "program_id": program_id,
                    "reset_id": reset_id,
                    "change_request_id": request_id,
                    "reset_proof_hash": proof.get("integrity_hash"),
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "previous_signoff_hash": current.get("signoff_hash"),
                    "next_generation": previous_generation + 1,
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
            self._write_request_binding(program_id, request, approval, current)
            self._append_lifecycle_event(
                program_id,
                {
                    "event_type": "continuity_acceptance_signoff_reset_applied",
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
            self._write_generation(program_id, previous_generation + 1, "reset_pending", proof)
            self.refresh_lifecycle_audit(program_id)
            return proof

    def refresh_lifecycle_audit(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
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

    def export_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            docs = self._archive_documents(program_id)
            export_dir = self.archive_export_dir(program_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
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

            write_entry("README.txt", "MusicForge Unified Release Program Continuity Acceptance Change Control Archive\n")
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
                UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE,
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
        del payload
        with self.lock:
            self.export_archive(program_id)
            export_dir = self.archive_export_dir(program_id)
            zip_path = self.archive_zip_path(program_id)
            if zip_path.exists():
                zip_path.unlink()
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "entries": entries, "entry_count": len(entries)}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            zip_path.unlink(missing_ok=True)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            return {"status": "passed", "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest_hash": manifest.get("integrity_hash")}

    def verify_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_release_program_continuity_acceptance_change_package(
            payload.get("archive_zip") or payload.get("zip_path") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current_acceptance=bool(payload.get("require_current_acceptance", True)),
            acceptance_archive_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
            acceptance_verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.verification_report_path(program_id),
            acceptance_signoff_binding_path=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
        )
        write_unified_release_program_continuity_acceptance_change_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, archive_zip_path: Path | str | None = None, verification_report_path: Path | str | None = None, **payload: object) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        if self.acceptance_store.latest_signoff_state(program_id).get("status") != "signed":
            return _gate_failed("Continuity Acceptance Board has been reset and must be re-signed.")
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Continuity Acceptance Change Control Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Continuity Acceptance Change Control verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_acceptance_change_package(
                zip_path,
                strict=True,
                require_current_acceptance=True,
                acceptance_archive_path=payload.get("acceptance_archive") or self.acceptance_store.archive_zip_path(program_id),
                acceptance_verification_report_path=payload.get("acceptance_verification_report") or self.acceptance_store.verification_report_path(program_id),
                acceptance_signoff_binding_path=payload.get("acceptance_signoff_binding") or self.acceptance_store.signoff_binding_path(program_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Continuity Acceptance Change Control verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Continuity Acceptance Change Control verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Continuity Acceptance Change Control verification report does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))
