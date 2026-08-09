from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import GenerationRef as GenerationRef, ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, GenerationService as GenerationService, HistoryChain as HistoryChain, ResetService as ResetService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.domains.legacy_documents import _program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_acceptance import UnifiedReleaseProgramContinuityAcceptanceStore as UnifiedReleaseProgramContinuityAcceptanceStore, _bounded as _bounded, _file_record as _file_record, _gate_failed as _gate_failed, _history_text as _history_text, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _package_manifest as _package_manifest, _read_optional_json as _read_optional_json, _safe_id as _safe_id, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_acceptance_package as verify_unified_release_program_continuity_acceptance_package
from song_agent.domains.program.unified_release_program_continuity_acceptance_change_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, continuity_acceptance_change_reset_semantic_checks as continuity_acceptance_change_reset_semantic_checks, verify_unified_release_program_continuity_acceptance_change_package as verify_unified_release_program_continuity_acceptance_change_package, write_unified_release_program_continuity_acceptance_change_verification_report as write_unified_release_program_continuity_acceptance_change_verification_report


RESET_ACTION = "reset_continuity_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_continuity_acceptance_signoff"


class UnifiedReleaseProgramContinuityAcceptanceChangeError(ValueError):
    pass


class UnifiedReleaseProgramContinuityAcceptanceChangeStateError(UnifiedReleaseProgramContinuityAcceptanceChangeError):
    pass


class UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError(UnifiedReleaseProgramContinuityAcceptanceChangeError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityAcceptanceChangeStateError)


class UnifiedReleaseProgramContinuityAcceptanceChangeStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.acceptance_store = UnifiedReleaseProgramContinuityAcceptanceStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

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

    def get_state(self, program_id: str) -> dict[str, Any]:
        return {
            "state": _read_optional_json(self.state_path(program_id)),
            "current_generation": _read_optional_json(self.current_generation_path(program_id)),
            "change_requests": self.list_change_requests(program_id),
            "reset_proofs": self.list_reset_proofs(program_id),
            "lifecycle_report": _read_optional_json(self.lifecycle_report_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def create_change_request(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def approve_change_request(self, program_id: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def reset_acceptance_signoff(self, program_id: str, request_id: str | dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def refresh_lifecycle_audit(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def export_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            docs = self._archive_documents(program_id)
            export_dir = self.archive_export_dir(program_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, value: dict[str, Any] | str) -> None:
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

    def build_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def gate(self, program_id: str, *, required: bool = False, archive_zip_path: Path | str | None = None, verification_report_path: Path | str | None = None, **payload: Any) -> dict[str, Any]:
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

    def read_change_request(self, program_id: str, request_id: str) -> dict[str, Any]:
        path = self.request_path(program_id, _safe_id(request_id))
        if not path.exists():
            raise UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError(f"Continuity Acceptance Change Request not found: {request_id}")
        return read_json(path)

    def list_change_requests(self, program_id: str) -> list[dict[str, Any]]:
        base = self.requests_dir(program_id)
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*/change-request.json"))]

    def list_reset_proofs(self, program_id: str) -> list[dict[str, Any]]:
        base = self.reset_proofs_dir(program_id)
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*/reset-proof.json"))]

    def read_lifecycle_events(self, program_id: str) -> list[dict[str, Any]]:
        return HistoryChain(self.lifecycle_event_log_path(program_id), sanitizer=sanitize_metadata).read()

    def _current_acceptance_state(self, program_id: str) -> ImplementationDocument:
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

    def _assert_request_current(self, program_id: str, request: ImplementationDocument) -> ImplementationDocument:
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

    def _target_from_state(self, state: ImplementationDocument) -> ImplementationDocument:
        return {
            "acceptance_signoff_hash": state.get("signoff_hash"),
            "acceptance_signoff_binding_hash": state.get("signoff_binding_hash"),
            "acceptance_archive_zip_sha256": state.get("archive_zip_sha256"),
            "acceptance_archive_manifest_hash": state.get("archive_manifest_hash"),
            "acceptance_verification_report_hash": state.get("verification_report_hash"),
            "generation": state.get("generation"),
        }

    def _existing_open_request(self, program_id: str, signoff_hash: str | None) -> ImplementationDocument | None:
        for request in self.list_change_requests(program_id):
            if request.get("status") in {"submitted", "draft", "approved"} and not request.get("applied_at") and (request.get("target") or {}).get("acceptance_signoff_hash") == signoff_hash:
                return request
        return None

    def _write_request_binding(self, program_id: str, request: ImplementationDocument, approval: ImplementationDocument | None, current: ImplementationDocument) -> ImplementationDocument:
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

    def _write_generation(self, program_id: str, generation: int, status: str, proof: ImplementationDocument | None = None) -> ImplementationDocument:
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

    def _change_control_state(self, program_id: str) -> ImplementationDocument:
        latest = self.acceptance_store.latest_signoff_state(program_id)
        current: dict[str, Any] = {}
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

    def _change_request_index(self, program_id: str) -> ImplementationDocument:
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

    def _reset_proof_index(self, program_id: str) -> ImplementationDocument:
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

    def _lifecycle_report(self, program_id: str, state: ImplementationDocument, request_index: ImplementationDocument, reset_index: ImplementationDocument) -> ImplementationDocument:
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

    def _archive_documents(self, program_id: str) -> ImplementationDocument:
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

    def _generation_summaries(self, program_id: str, state: ImplementationDocument, resets: dict[str, ImplementationDocument]) -> dict[int, ImplementationDocument]:
        generation_number = int((_read_optional_json(self.current_generation_path(program_id)).get("generation") or 1))
        summaries: dict[int, dict[str, Any]] = {}
        acceptance_verification = _read_optional_json(self.acceptance_store.verification_report_path(program_id))
        signoff_binding = _read_optional_json(self.acceptance_store.signoff_binding_path(program_id))
        source = _as_document(state.get("current_acceptance"))
        summaries[generation_number] = {
            "verification_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_generation_verification_summary", "program_id": program_id, "generation": generation_number, "verification_status": acceptance_verification.get("status"), "verification_report_hash": acceptance_verification.get("integrity_hash"), "archive_zip_sha256": acceptance_verification.get("zip_sha256"), "archive_manifest_hash": acceptance_verification.get("manifest_hash")}),
            "signoff_binding_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_generation_signoff_binding_summary", "program_id": program_id, "generation": generation_number, "signoff_hash": signoff_binding.get("signoff_hash"), "signoff_binding_hash": signoff_binding.get("integrity_hash"), "history_event_hash": signoff_binding.get("history_event_hash")}),
            "source_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_generation_source_summary", "program_id": program_id, "generation": generation_number, "source": source}),
        }
        return summaries

    def _append_lifecycle_event(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
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
