from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_int as _as_int, document_or as _document_or
from song_agent.platform.contracts.packages import require_registered_package_type as _require_registered_package_type

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_distribution import UnifiedReleaseProgramContinuityDistributionStore as UnifiedReleaseProgramContinuityDistributionStore
from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_distribution_package as verify_unified_release_program_continuity_distribution_package
from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE, verify_unified_release_program_continuity_acceptance_package as verify_unified_release_program_continuity_acceptance_package, write_unified_release_program_continuity_acceptance_verification_report as write_unified_release_program_continuity_acceptance_verification_report


DEFAULT_BOARD_POLICY = {
    "min_accepted_receipts": 2,
    "min_organizations": 2,
    "required_roles": ["recovery_owner", "external_custodian"],
    "block_on_needs_changes": True,
    "block_on_rejected": True,
    "require_current_continuity_distribution_kit": True,
    "require_accepted_evidence": True,
    "allow_synthetic_receiver": False,
}

BLOCKED_RESPONSE_KEYS = {
    "absolute_path",
    "api_key",
    "authorization",
    "file_path",
    "local_path",
    "password",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}


class UnifiedReleaseProgramContinuityAcceptanceError(ValueError):
    pass


class UnifiedReleaseProgramContinuityAcceptanceStateError(UnifiedReleaseProgramContinuityAcceptanceError):
    pass


class UnifiedReleaseProgramContinuityAcceptanceNotFoundError(UnifiedReleaseProgramContinuityAcceptanceError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityAcceptanceStateError)


class UnifiedReleaseProgramContinuityAcceptanceStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.kit_store = UnifiedReleaseProgramContinuityDistributionStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

    def acceptance_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "continuity-acceptance"

    def board_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "board.json"

    def report_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "board-report.json"

    def decision_matrix_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "decision-matrix.json"

    def receiver_index_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "receiver-index.json"

    def accepted_index_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "accepted-evidence-index.json"

    def external_manifest_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "external-evidence-manifest.json"

    def source_binding_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "source-binding-summary.json"

    def responses_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "responses"

    def response_path(self, program_id: str, response_id: str) -> Path:
        return self.responses_dir(program_id) / f"{_safe_id(response_id)}.json"

    def response_verification_path(self, program_id: str, response_id: str) -> Path:
        return self.responses_dir(program_id) / f"{_safe_id(response_id)}-verification-report.json"

    def response_binding_path(self, program_id: str, response_id: str) -> Path:
        return self.responses_dir(program_id) / f"{_safe_id(response_id)}-binding-summary.json"

    def accepted_evidence_dir(self, program_id: str, evidence_id: str) -> Path:
        return self.acceptance_dir(program_id) / "accepted-evidence" / _safe_id(evidence_id)

    def signoff_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "signoff"

    def signoff_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "continuity-acceptance-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "continuity-acceptance-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "continuity-acceptance-history.jsonl"

    def archive_export_dir(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "archive"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "unified-release-program-continuity-acceptance-archive.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.acceptance_dir(program_id) / "unified-release-program-continuity-acceptance-verification-report.json"

    def get_board(self, program_id: str) -> dict[str, Any]:
        return {
            "report": _read_optional_json(self.report_path(program_id)),
            "board": _read_optional_json(self.board_path(program_id)),
            "decision_matrix": _read_optional_json(self.decision_matrix_path(program_id)),
            "receiver_index": _read_optional_json(self.receiver_index_path(program_id)),
            "accepted_evidence_index": _read_optional_json(self.accepted_index_path(program_id)),
            "source_binding": _read_optional_json(self.source_binding_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def import_response(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        if payload.get("response_json"):
            payload.update(read_json(Path(payload["response_json"])))
        if payload.get("response_verification_report_json"):
            payload["response_verification_report"] = read_json(Path(payload["response_verification_report_json"]))
        if payload.get("response_binding_summary_json"):
            payload["response_binding_summary"] = read_json(Path(payload["response_binding_summary_json"]))
        response_payload = dict(_document_or(payload.get("response"), payload))
        verification_payload = payload.get("response_verification_report") or payload.get("verification_report") or payload.get("verification")
        binding_payload = payload.get("response_binding_summary") or payload.get("binding_summary") or payload.get("binding")
        if not isinstance(verification_payload, dict) or not isinstance(binding_payload, dict):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response requires external verification and binding proof.")
        for key in (
            "response",
            "response_json",
            "response_verification_report",
            "verification_report",
            "verification",
            "response_verification_report_json",
            "response_binding_summary",
            "binding_summary",
            "binding",
            "response_binding_summary_json",
        ):
            response_payload.pop(key, None)
        _reject_forbidden(response_payload, "Continuity Acceptance response")
        with self.lock:
            self.ensure_unsigned(program_id)
            required = [
                "program_id",
                "response_id",
                "kit_sha256",
                "kit_manifest_hash",
                "kit_verification_report_hash",
                "receiver_id",
                "receiver_role",
                "organization",
                "decision",
                "reviewed_at",
            ]
            missing = [field for field in required if not response_payload.get(field)]
            if missing:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response missing binding fields: " + ", ".join(missing))
            if response_payload.get("package_type") and response_payload.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response package_type is invalid.")
            if str(response_payload.get("program_id")) != program_id:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response program_id does not match.")
            source = self._current_kit_source(program_id)
            for field in ("kit_sha256", "kit_manifest_hash", "kit_verification_report_hash"):
                if response_payload.get(field) != source.get(field):
                    raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance response {field} does not match current Kit evidence.")
            response_id = _safe_id(str(response_payload.get("response_id") or ""))
            response = sanitize_metadata(
                {
                    **response_payload,
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE,
                    "response_id": response_id,
                    "status": "imported",
                    "imported_at": now_iso(),
                    "notes": _bounded(response_payload.get("notes") or "", 2000),
                }
            )
            response["payload_hash"] = _response_payload_hash(response)
            if response_payload.get("payload_hash") and response_payload.get("payload_hash") != response["payload_hash"]:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response payload_hash is invalid.")
            response["integrity_hash"] = _integrity_hash(response)
            verification = sanitize_metadata(dict(verification_payload))
            binding = sanitize_metadata(dict(binding_payload))
            self._validate_external_response_proof(program_id, response, verification, binding, source)
            self.responses_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.response_path(program_id, response_id), response)
            write_json(self.response_verification_path(program_id, response_id), verification)
            write_json(self.response_binding_path(program_id, response_id), binding)
            return {"status": "imported", "response": response, "verification": verification, "binding": binding}

    def create_accepted_evidence(self, program_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            self.ensure_unsigned(program_id)
            response_id = _safe_id(response_id)
            response = read_json(self.response_path(program_id, response_id))
            verification = read_json(self.response_verification_path(program_id, response_id))
            binding = read_json(self.response_binding_path(program_id, response_id))
            self._validate_external_response_proof(program_id, response, verification, binding, self._current_kit_source(program_id))
            if binding.get("decision") != "accepted" or response.get("decision") != "accepted":
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Only accepted continuity responses can create accepted evidence.")
            if verification.get("status") != "passed" or not _integrity_ok(verification) or not _integrity_ok(binding):
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity response verification or binding failed.")
            evidence_id = _safe_id(str(response.get("evidence_id") or self._next_evidence_id(program_id)))
            evidence_dir = self.accepted_evidence_dir(program_id, evidence_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            public = _with_integrity(_response_public_projection(response))
            verification_summary = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_acceptance_response_verification_summary",
                    "program_id": program_id,
                    "response_id": response_id,
                    "status": verification.get("status"),
                    "payload_hash": verification.get("payload_hash"),
                    "verification_report_hash": verification.get("integrity_hash"),
                    "receiver_public_projection_hash": verification.get("receiver_public_projection_hash"),
                }
            )
            accepted = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE,
                    "program_id": program_id,
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "receiver_id": binding.get("receiver_id"),
                    "receiver_role": binding.get("receiver_role"),
                    "organization": binding.get("organization"),
                    "decision": binding.get("decision"),
                    "source": {
                        "payload_hash": binding.get("payload_hash"),
                        "response_verification_hash": verification.get("integrity_hash"),
                        "response_binding_hash": binding.get("integrity_hash"),
                    },
                    "status": "accepted",
                }
            )
            report = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_acceptance_evidence_report",
                    "program_id": program_id,
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "status": "accepted",
                    "public_summary": {
                        "receiver_id": binding.get("receiver_id"),
                        "receiver_role": binding.get("receiver_role"),
                        "organization": binding.get("organization"),
                        "decision": binding.get("decision"),
                    },
                    "source": accepted.get("source"),
                }
            )
            write_json(evidence_dir / "accepted-evidence.json", accepted)
            write_json(evidence_dir / "original-response-public.json", public)
            write_json(evidence_dir / "response-verification-summary.json", verification_summary)
            write_json(evidence_dir / "response-binding-summary.json", binding)
            write_json(evidence_dir / "evidence-report.json", report)
            self.refresh_decision_board(program_id)
            return {"status": "accepted", "evidence": accepted, "report": report}

    def _validate_external_response_proof(self, program_id: str, response: ImplementationDocument, verification: ImplementationDocument, binding: ImplementationDocument, source: ImplementationDocument) -> None:
        if response.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response package_type is invalid.")
        if not _integrity_ok(response):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response integrity failed.")
        if response.get("payload_hash") != _response_payload_hash(response):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response payload_hash is invalid.")
        if verification.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response verification package_type is invalid.")
        if binding.get("package_type") != "musicforge_unified_release_program_continuity_acceptance_response_binding_summary":
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response binding package_type is invalid.")
        if not _integrity_ok(verification) or not _integrity_ok(binding):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response external proof integrity failed.")
        expected_projection_hash = stable_hash(_response_public_projection(response))
        checks = {
            "program_id": program_id,
            "response_id": response.get("response_id"),
            "payload_hash": response.get("payload_hash"),
            "receiver_id": response.get("receiver_id"),
            "receiver_role": response.get("receiver_role"),
            "organization": response.get("organization"),
            "decision": response.get("decision"),
            "kit_sha256": source.get("kit_sha256"),
            "kit_manifest_hash": source.get("kit_manifest_hash"),
            "kit_verification_report_hash": source.get("kit_verification_report_hash"),
        }
        for field, expected in checks.items():
            if verification.get(field) != expected:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance response verification {field} mismatch.")
            if binding.get(field) != expected:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance response binding {field} mismatch.")
        if verification.get("status") != "passed":
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response verification is not passed.")
        if verification.get("response_integrity_hash") and verification.get("response_integrity_hash") != response.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response verification integrity binding mismatch.")
        if verification.get("receiver_public_projection_hash") != expected_projection_hash:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response public projection binding mismatch.")
        if binding.get("verification_report_hash") != verification.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance response binding does not reference the verification report.")

    def refresh_decision_board(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._build_board_documents(program_id, payload)
            self.acceptance_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.board_path(program_id), docs["board"])
            write_json(self.report_path(program_id), docs["report"])
            write_json(self.decision_matrix_path(program_id), docs["matrix"])
            write_json(self.receiver_index_path(program_id), docs["receiver_index"])
            write_json(self.accepted_index_path(program_id), docs["accepted_index"])
            write_json(self.external_manifest_path(program_id), docs["external_manifest"])
            write_json(self.source_binding_path(program_id), docs["source"])
            return docs["board"]

    def signoff_acceptance(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._build_board_documents(program_id, payload if "policy" in payload else {})
            if docs["board"].get("status") != "ready_for_signoff":
                raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance Board is not ready for signoff.")
            role = _bounded(payload.get("role") or "program_owner", 80)
            now = now_iso()
            docs["report"]["status"] = "signed"
            docs["report"]["signed_at"] = now
            docs["report"]["integrity_hash"] = _integrity_hash(docs["report"])
            signoff = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE,
                    "program_id": program_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "continuity-acceptance-chair", 120),
                    "role": role,
                    "reason": _bounded(payload.get("reason") or "Continuity acceptance quorum met.", 1000),
                    "signed_at": now,
                    "board_report_hash": docs["report"].get("integrity_hash"),
                    "decision_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "receiver_index_hash": docs["receiver_index"].get("integrity_hash"),
                    "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                    "source_binding_hash": docs["source"].get("integrity_hash"),
                    "kit_sha256": docs["source"].get("kit_sha256"),
                    "kit_manifest_hash": docs["source"].get("kit_manifest_hash"),
                    "kit_verification_report_hash": docs["source"].get("kit_verification_report_hash"),
                    "tool": {"name": "MusicForge Continuity Acceptance Board", "version": __version__},
                }
            )
            signoff = SignoffService.seal(signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "continuity_acceptance_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "board_report_hash": signoff.get("board_report_hash"),
                    "decision_matrix_hash": signoff.get("decision_matrix_hash"),
                },
            )
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_acceptance_signoff_binding_summary",
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signed_at": signoff.get("signed_at"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "history_event_hash": event.get("event_hash"),
                    "history_event_payload_hash": event.get("payload_hash"),
                    "board_report_hash": docs["report"].get("integrity_hash"),
                    "decision_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "receiver_index_hash": docs["receiver_index"].get("integrity_hash"),
                    "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                    "source_binding_hash": docs["source"].get("integrity_hash"),
                    "kit_sha256": docs["source"].get("kit_sha256"),
                    "kit_manifest_hash": docs["source"].get("kit_manifest_hash"),
                    "kit_verification_report_hash": docs["source"].get("kit_verification_report_hash"),
                }
            )
            self.signoff_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.signoff_path(program_id), signoff)
            write_json(self.signoff_binding_path(program_id), binding)
            self._write_docs(program_id, docs)
            return signoff

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

            write_entry("README.txt", "MusicForge Unified Release Program Continuity Acceptance Archive\n")
            write_entry("board-report.json", docs["report"])
            write_entry("decision-matrix.json", docs["matrix"])
            write_entry("receiver-index.json", docs["receiver_index"])
            write_entry("accepted-evidence-index.json", docs["accepted_index"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            write_entry("source-binding-summary.json", docs["source"])
            write_entry("signoff/continuity-acceptance-signoff.json", docs["signoff"])
            write_entry("signoff/continuity-acceptance-signoff-binding-summary.json", docs["binding"])
            write_entry("signoff/continuity-acceptance-history.jsonl", _history_text(self.read_history(program_id)))
            for response_id in sorted(docs["responses"]):
                bundle = docs["responses"][response_id]
                write_entry(f"responses/{response_id}.json", bundle["response"])
                write_entry(f"responses/{response_id}-verification-report.json", bundle["verification"])
                write_entry(f"responses/{response_id}-binding-summary.json", bundle["binding"])
            for evidence_id in sorted(docs["evidences"]):
                bundle = docs["evidences"][evidence_id]
                prefix = f"accepted-evidence/{evidence_id}"
                write_entry(f"{prefix}/accepted-evidence.json", bundle["accepted"])
                write_entry(f"{prefix}/original-response-public.json", bundle["public"])
                write_entry(f"{prefix}/response-verification-summary.json", bundle["verification_summary"])
                write_entry(f"{prefix}/response-binding-summary.json", bundle["binding"])
                write_entry(f"{prefix}/evidence-report.json", bundle["report"])
            manifest = _package_manifest(
                UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE,
                program_id,
                files,
                {
                    "board_report_hash": docs["report"].get("integrity_hash"),
                    "decision_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "receiver_index_hash": docs["receiver_index"].get("integrity_hash"),
                    "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "source_binding_hash": docs["source"].get("integrity_hash"),
                    "signoff_hash": docs["signoff"].get("integrity_hash"),
                    "signoff_binding_hash": docs["binding"].get("integrity_hash"),
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
        report = verify_unified_release_program_continuity_acceptance_package(
            payload.get("archive_zip") or payload.get("zip_path") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current_kit=bool(payload.get("require_current_kit", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_quorum=bool(payload.get("require_quorum", True)),
            continuity_kit_path=payload.get("continuity_kit") or payload.get("continuity_kit_path") or self.kit_store.kit_zip_path(program_id),
            continuity_kit_verification_report_path=payload.get("continuity_kit_verification_report") or payload.get("continuity_kit_verification_report_path") or self.kit_store.verification_report_path(program_id),
            signoff_binding_path=payload.get("signoff_binding") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_continuity_acceptance_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, archive_zip_path: Path | str | None = None, verification_report_path: Path | str | None = None, **payload: Any) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Continuity Acceptance Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Continuity Acceptance verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_acceptance_package(
                zip_path,
                strict=True,
                require_current_kit=True,
                require_signed=True,
                require_quorum=True,
                continuity_kit_path=payload.get("continuity_kit") or self.kit_store.kit_zip_path(program_id),
                continuity_kit_verification_report_path=payload.get("continuity_kit_verification_report") or self.kit_store.verification_report_path(program_id),
                signoff_binding_path=payload.get("signoff_binding") or self.signoff_binding_path(program_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Continuity Acceptance verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Continuity Acceptance verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Continuity Acceptance verification report does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, program_id: str) -> None:
        if self.latest_signoff_state(program_id).get("status") == "signed":
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance Board is signed. Create a new Board for changes.")

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "continuity_acceptance_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            if event.get("event_type") == "continuity_acceptance_signoff_reset":
                latest = {"status": "reset", "previous_signoff_hash": event.get("previous_signoff_hash"), "event": event}
        if latest:
            return latest
        return {"status": "unsigned"}

    def read_history(self, program_id: str) -> list[dict[str, Any]]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()

    def _build_board_documents(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        source = self._current_kit_source(program_id)
        policy = _board_policy(payload.get("policy") if "policy" in payload else (_read_optional_json(self.board_path(program_id)).get("policy") or None))
        responses = self._response_bundles(program_id)
        evidences = self._evidence_bundles(program_id)
        participants, evidence_conflicts = self._participants_from_evidence(evidences, responses, source)
        negative_conflicts = self._response_decision_conflicts(responses, policy)
        conflicts = evidence_conflicts + negative_conflicts
        readiness = _decision_readiness(policy, participants, conflicts)
        matrix = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_decision_matrix", "program_id": program_id, "rows": _matrix_rows(participants)})
        receiver_index = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_receiver_index", "program_id": program_id, "receivers": _receiver_rows(participants), "summary": {"receiver_count": len(participants)}})
        accepted_index = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_accepted_evidence_index", "program_id": program_id, "items": _accepted_rows(participants), "summary": {"accepted_count": len(participants)}})
        external_manifest = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_external_evidence_manifest", "program_id": program_id, "items": [{"evidence_type": "continuity_distribution_kit", **source}], "summary": {"item_count": 1}})
        report_status = "ready_for_signoff" if readiness["status"] == "ready_for_signoff" else "blocked"
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE,
                "program_id": program_id,
                "status": report_status,
                "policy": policy,
                "source": source,
                "summary": {
                    "accepted_count": readiness.get("accepted_count"),
                    "organization_count": readiness.get("organization_count"),
                    "required_roles_met": not readiness.get("missing_roles"),
                    "needs_changes_count": sum(1 for item in responses.values() if item["binding"].get("decision") == "needs_changes"),
                    "rejected_count": sum(1 for item in responses.values() if item["binding"].get("decision") == "rejected"),
                    "blocker_count": len(readiness.get("blockers") or []),
                },
                "blockers": readiness.get("blockers"),
                "warnings": [],
                "created_at": now_iso(),
            }
        )
        board = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_board",
                "program_id": program_id,
                "policy": policy,
                "participants": participants,
                "conflicts": conflicts,
                "readiness": readiness,
                "status": readiness.get("status"),
            }
        )
        return {
            "source": source,
            "responses": responses,
            "evidences": evidences,
            "participants": participants,
            "board": board,
            "report": report,
            "matrix": matrix,
            "receiver_index": receiver_index,
            "accepted_index": accepted_index,
            "external_manifest": external_manifest,
        }

    def _current_kit_source(self, program_id: str) -> ImplementationDocument:
        kit_path = self.kit_store.kit_zip_path(program_id)
        report_path = self.kit_store.verification_report_path(program_id)
        if not kit_path.exists() or not report_path.exists():
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Distribution Kit ZIP and verification report are required.")
        external = read_json(report_path)
        runtime = verify_unified_release_program_continuity_distribution_package(kit_path, strict=True, deep=True)
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Distribution Kit verification report is invalid.")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Distribution Kit verification failed.")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Distribution Kit verification report does not match current ZIP.")
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_source_binding",
                "program_id": program_id,
                "kit_sha256": runtime.get("zip_sha256"),
                "kit_size_bytes": runtime.get("zip_size_bytes"),
                "kit_manifest_hash": runtime.get("manifest_hash"),
                "kit_verification_report_hash": external.get("integrity_hash"),
                "kit_verification_status": external.get("status"),
                "runtime_status": runtime.get("status"),
            }
        )

    def _response_bundles(self, program_id: str) -> dict[str, ImplementationDocument]:
        bundles: dict[str, dict[str, Any]] = {}
        if not self.responses_dir(program_id).exists():
            return bundles
        for path in sorted(self.responses_dir(program_id).glob("response-*.json")):
            if path.name.endswith("-verification-report.json") or path.name.endswith("-binding-summary.json"):
                continue
            response_id = path.stem
            bundles[response_id] = {
                "response": read_json(path),
                "verification": read_json(self.response_verification_path(program_id, response_id)),
                "binding": read_json(self.response_binding_path(program_id, response_id)),
            }
        return bundles

    def _evidence_bundles(self, program_id: str) -> dict[str, ImplementationDocument]:
        base = self.acceptance_dir(program_id) / "accepted-evidence"
        bundles: dict[str, dict[str, Any]] = {}
        if not base.exists():
            return bundles
        for evidence_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            evidence_id = evidence_dir.name
            bundles[evidence_id] = {
                "accepted": read_json(evidence_dir / "accepted-evidence.json"),
                "public": read_json(evidence_dir / "original-response-public.json"),
                "verification_summary": read_json(evidence_dir / "response-verification-summary.json"),
                "binding": read_json(evidence_dir / "response-binding-summary.json"),
                "report": read_json(evidence_dir / "evidence-report.json"),
            }
        return bundles

    def _participants_from_evidence(self, evidences: dict[str, ImplementationDocument], responses: dict[str, ImplementationDocument], source: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
        participants: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for evidence_id, bundle in sorted(evidences.items()):
            accepted = bundle["accepted"]
            binding = bundle["binding"]
            summary = bundle["verification_summary"]
            response_id = str(accepted.get("response_id") or "")
            response_bundle = responses.get(response_id)
            response_binding = response_bundle.get("binding") if response_bundle else {}
            response_verification = response_bundle.get("verification") if response_bundle else {}
            stale_fields = [
                field
                for field in ("kit_sha256", "kit_manifest_hash", "kit_verification_report_hash")
                if binding.get(field) != source.get(field)
                or _as_document(response_binding).get(field) != source.get(field)
                or _as_document(response_verification).get(field) != source.get(field)
            ]
            if not response_bundle:
                conflicts.append({"reason": "accepted_evidence_response_missing", "evidence_id": evidence_id})
            if stale_fields:
                conflicts.append({"reason": "accepted_evidence_stale_kit", "evidence_id": evidence_id, "fields": stale_fields})
            if accepted.get("receiver_role") != binding.get("receiver_role") or binding.get("receiver_role") != _as_document(response_binding).get("receiver_role"):
                conflicts.append({"reason": "accepted_evidence_role_mismatch", "evidence_id": evidence_id})
            if accepted.get("organization") != binding.get("organization") or binding.get("organization") != _as_document(response_binding).get("organization"):
                conflicts.append({"reason": "accepted_evidence_organization_mismatch", "evidence_id": evidence_id})
            if accepted.get("decision") != binding.get("decision") or binding.get("decision") != _as_document(response_binding).get("decision"):
                conflicts.append({"reason": "accepted_evidence_decision_mismatch", "evidence_id": evidence_id})
            if summary.get("verification_report_hash") != _as_document(response_verification).get("integrity_hash"):
                conflicts.append({"reason": "accepted_evidence_verification_mismatch", "evidence_id": evidence_id})
            participants.append(
                {
                    "response_id": response_id,
                    "evidence_id": evidence_id,
                    "receiver_id": binding.get("receiver_id"),
                    "role": binding.get("receiver_role"),
                    "organization": binding.get("organization"),
                    "decision": binding.get("decision"),
                    "payload_hash": binding.get("payload_hash"),
                    "binding_hash": binding.get("integrity_hash"),
                    "source": "accepted_evidence_proof",
                }
            )
        return participants, conflicts

    def _response_decision_conflicts(self, responses: dict[str, ImplementationDocument], policy: ImplementationDocument) -> list[ImplementationDocument]:
        conflicts: list[dict[str, Any]] = []
        for response_id, bundle in responses.items():
            decision = bundle["binding"].get("decision")
            if decision == "rejected" and bool(policy.get("block_on_rejected", True)):
                conflicts.append({"reason": "rejected_response_present", "response_id": response_id})
            if decision == "needs_changes" and bool(policy.get("block_on_needs_changes", True)):
                conflicts.append({"reason": "needs_changes_response_present", "response_id": response_id})
        return conflicts

    def _write_docs(self, program_id: str, docs: ImplementationDocument) -> None:
        self.acceptance_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.board_path(program_id), docs["board"])
        write_json(self.report_path(program_id), docs["report"])
        write_json(self.decision_matrix_path(program_id), docs["matrix"])
        write_json(self.receiver_index_path(program_id), docs["receiver_index"])
        write_json(self.accepted_index_path(program_id), docs["accepted_index"])
        write_json(self.external_manifest_path(program_id), docs["external_manifest"])
        write_json(self.source_binding_path(program_id), docs["source"])

    def _archive_documents(self, program_id: str) -> ImplementationDocument:
        if self.latest_signoff_state(program_id).get("status") != "signed":
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance Board must be signed before archive export.")
        docs = {
            "report": read_json(self.report_path(program_id)),
            "matrix": read_json(self.decision_matrix_path(program_id)),
            "receiver_index": read_json(self.receiver_index_path(program_id)),
            "accepted_index": read_json(self.accepted_index_path(program_id)),
            "external_manifest": read_json(self.external_manifest_path(program_id)),
            "source": read_json(self.source_binding_path(program_id)),
            "signoff": read_json(self.signoff_path(program_id)),
            "binding": read_json(self.signoff_binding_path(program_id)),
            "responses": self._response_bundles(program_id),
            "evidences": self._evidence_bundles(program_id),
        }
        binding = docs["binding"]
        expected = {
            "signoff_hash": docs["signoff"].get("integrity_hash"),
            "board_report_hash": docs["report"].get("integrity_hash"),
            "decision_matrix_hash": docs["matrix"].get("integrity_hash"),
            "receiver_index_hash": docs["receiver_index"].get("integrity_hash"),
            "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
            "source_binding_hash": docs["source"].get("integrity_hash"),
        }
        mismatched = [key for key, value in expected.items() if binding.get(key) != value]
        if mismatched:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance signed archive source is stale: " + ", ".join(mismatched))
        self._validate_signed_archive_sources(program_id, docs)
        return docs

    def _validate_signed_archive_sources(self, program_id: str, docs: ImplementationDocument) -> None:
        source = self._current_kit_source(program_id)
        if docs["source"].get("integrity_hash") != source.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance signed source no longer matches current Kit evidence.")
        for response_id, bundle in sorted(docs["responses"].items()):
            response = bundle["response"]
            verification = bundle["verification"]
            binding = bundle["binding"]
            if response.get("response_id") != response_id:
                raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance response {response_id} id mismatch.")
            self._validate_external_response_proof(program_id, response, verification, binding, source)
        for evidence_id, bundle in sorted(docs["evidences"].items()):
            self._validate_accepted_evidence_bundle(program_id, evidence_id, bundle, docs["responses"], source)
        participants, conflicts = self._participants_from_evidence(docs["evidences"], docs["responses"], source)
        if conflicts:
            reasons = sorted({str(row.get("reason") or "conflict") for row in conflicts})
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance accepted evidence source is stale: " + ", ".join(reasons))
        expected_docs = {
            "matrix": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_decision_matrix", "program_id": program_id, "rows": _matrix_rows(participants)}),
            "receiver_index": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_receiver_index", "program_id": program_id, "receivers": _receiver_rows(participants), "summary": {"receiver_count": len(participants)}}),
            "accepted_index": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_accepted_evidence_index", "program_id": program_id, "items": _accepted_rows(participants), "summary": {"accepted_count": len(participants)}}),
            "external_manifest": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_acceptance_external_evidence_manifest", "program_id": program_id, "items": [{"evidence_type": "continuity_distribution_kit", **source}], "summary": {"item_count": 1}}),
        }
        mismatched = [
            name
            for name, expected_doc in expected_docs.items()
            if docs[name].get("integrity_hash") != expected_doc.get("integrity_hash")
        ]
        if mismatched:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance signed indexes are stale: " + ", ".join(mismatched))
        self._validate_history_chain(program_id, docs["signoff"], docs["binding"])

    def _validate_accepted_evidence_bundle(self, program_id: str, evidence_id: str, bundle: ImplementationDocument, responses: dict[str, ImplementationDocument], source: ImplementationDocument) -> None:
        accepted = bundle["accepted"]
        public = bundle["public"]
        verification_summary = bundle["verification_summary"]
        binding = bundle["binding"]
        report = bundle["report"]
        docs = {
            "accepted evidence": accepted,
            "accepted response public projection": public,
            "accepted response verification summary": verification_summary,
            "accepted response binding": binding,
            "accepted evidence report": report,
        }
        failed = [name for name, doc in docs.items() if not _integrity_ok(doc)]
        if failed:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance {evidence_id} integrity failed: " + ", ".join(failed))
        if accepted.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance {evidence_id} package_type is invalid.")
        if accepted.get("evidence_id") != evidence_id or accepted.get("program_id") != program_id:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance {evidence_id} identity mismatch.")
        response_id = str(accepted.get("response_id") or report.get("response_id") or "")
        response_bundle = responses.get(response_id)
        if not response_bundle:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance {evidence_id} response is missing.")
        response = response_bundle["response"]
        response_verification = response_bundle["verification"]
        response_binding = response_bundle["binding"]
        self._validate_external_response_proof(program_id, response, response_verification, response_binding, source)
        expected_public = _with_integrity(_response_public_projection(response))
        expected_summary = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_response_verification_summary",
                "program_id": program_id,
                "response_id": response_id,
                "status": response_verification.get("status"),
                "payload_hash": response_verification.get("payload_hash"),
                "verification_report_hash": response_verification.get("integrity_hash"),
                "receiver_public_projection_hash": response_verification.get("receiver_public_projection_hash"),
            }
        )
        expected_source = {
            "payload_hash": response_binding.get("payload_hash"),
            "response_verification_hash": response_verification.get("integrity_hash"),
            "response_binding_hash": response_binding.get("integrity_hash"),
        }
        expected_report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_acceptance_evidence_report",
                "program_id": program_id,
                "evidence_id": evidence_id,
                "response_id": response_id,
                "status": "accepted",
                "public_summary": {
                    "receiver_id": response_binding.get("receiver_id"),
                    "receiver_role": response_binding.get("receiver_role"),
                    "organization": response_binding.get("organization"),
                    "decision": response_binding.get("decision"),
                },
                "source": expected_source,
            }
        )
        checks = {
            "public": public.get("integrity_hash") == expected_public.get("integrity_hash"),
            "verification_summary": verification_summary.get("integrity_hash") == expected_summary.get("integrity_hash"),
            "binding": binding.get("integrity_hash") == response_binding.get("integrity_hash"),
            "accepted_source": accepted.get("source") == expected_source,
            "accepted_role": accepted.get("receiver_role") == response_binding.get("receiver_role"),
            "accepted_organization": accepted.get("organization") == response_binding.get("organization"),
            "accepted_decision": accepted.get("decision") == response_binding.get("decision") == "accepted",
            "report": report.get("integrity_hash") == expected_report.get("integrity_hash"),
        }
        failed_checks = [key for key, ok in checks.items() if not ok]
        if failed_checks:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance {evidence_id} source binding failed: " + ", ".join(failed_checks))

    def _validate_history_chain(self, program_id: str, signoff: ImplementationDocument, binding: ImplementationDocument) -> None:
        validation = HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).validate()
        if not validation.valid:
            index = (validation.error_index or 0) + 1
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance history chain failed at event {index}.")
        latest_signoff_event: dict[str, Any] = {}
        for row in validation.rows:
            if row.get("event_type") == "continuity_acceptance_signoff_created":
                latest_signoff_event = row
        if not latest_signoff_event:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance signoff history event is missing.")
        checks = {
            "signoff_hash": latest_signoff_event.get("signoff_hash") == signoff.get("integrity_hash") == binding.get("signoff_hash"),
            "payload_hash": latest_signoff_event.get("signoff_payload_hash") == signoff.get("payload_hash") == binding.get("signoff_payload_hash"),
            "history_hash": latest_signoff_event.get("event_hash") == binding.get("history_event_hash"),
            "signed_by": latest_signoff_event.get("signed_by") == signoff.get("signed_by") == binding.get("signed_by"),
            "role": latest_signoff_event.get("role") == signoff.get("role") == binding.get("role"),
            "reason": latest_signoff_event.get("reason") == signoff.get("reason") == binding.get("reason"),
        }
        failed = [key for key, ok in checks.items() if not ok]
        if failed:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError("Continuity Acceptance signoff history binding failed: " + ", ".join(failed))

    def _append_history(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _next_response_id(self, program_id: str) -> str:
        self.responses_dir(program_id).mkdir(parents=True, exist_ok=True)
        return f"response-{len([p for p in self.responses_dir(program_id).glob('response-*.json') if not p.name.endswith('-verification-report.json') and not p.name.endswith('-binding-summary.json')]) + 1:06d}"

    def _next_evidence_id(self, program_id: str) -> str:
        base = self.acceptance_dir(program_id) / "accepted-evidence"
        base.mkdir(parents=True, exist_ok=True)
        return f"evidence-{len(list(base.glob('evidence-*'))) + 1:06d}"


def _board_policy(value: Any) -> ImplementationDocument:
    raw = _as_document(value)
    return {
        "min_accepted_receipts": _as_int(raw.get("min_accepted_receipts") or raw.get("minimum_acceptances") or DEFAULT_BOARD_POLICY["min_accepted_receipts"]),
        "min_organizations": _as_int(raw.get("min_organizations") or raw.get("minimum_organizations") or DEFAULT_BOARD_POLICY["min_organizations"]),
        "required_roles": [_bounded(role, 80) for role in raw.get("required_roles", DEFAULT_BOARD_POLICY["required_roles"])],
        "block_on_needs_changes": bool(raw.get("block_on_needs_changes", DEFAULT_BOARD_POLICY["block_on_needs_changes"])),
        "block_on_rejected": bool(raw.get("block_on_rejected", DEFAULT_BOARD_POLICY["block_on_rejected"])),
        "require_current_continuity_distribution_kit": bool(raw.get("require_current_continuity_distribution_kit", DEFAULT_BOARD_POLICY["require_current_continuity_distribution_kit"])),
        "require_accepted_evidence": bool(raw.get("require_accepted_evidence", DEFAULT_BOARD_POLICY["require_accepted_evidence"])),
        "allow_synthetic_receiver": bool(raw.get("allow_synthetic_receiver", DEFAULT_BOARD_POLICY["allow_synthetic_receiver"])),
    }


def _decision_readiness(policy: ImplementationDocument, participants: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {row.get("role") for row in accepted}
    orgs = {row.get("organization") for row in accepted}
    required_roles = set(policy.get("required_roles") or [])
    missing_roles = sorted(required_roles - roles)
    blockers: list[str] = []
    if len(accepted) < int(policy.get("min_accepted_receipts") or 2):
        blockers.append("min_accepted_receipts")
    if len(orgs) < int(policy.get("min_organizations") or 2):
        blockers.append("min_organizations")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("receiver_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(orgs), "missing_roles": missing_roles, "blockers": blockers}


def _matrix_rows(participants: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {
            "response_id": row.get("response_id"),
            "evidence_id": row.get("evidence_id"),
            "receiver_id": row.get("receiver_id"),
            "role": row.get("role"),
            "organization": row.get("organization"),
            "decision": row.get("decision"),
            "source": row.get("source"),
            "payload_hash": row.get("payload_hash"),
            "binding_hash": row.get("binding_hash"),
        }
        for row in sorted(participants, key=lambda item: str(item.get("evidence_id") or ""))
    ]


def _receiver_rows(participants: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [{"receiver_id": row.get("receiver_id"), "role": row.get("role"), "organization": row.get("organization"), "decision": row.get("decision"), "response_id": row.get("response_id")} for row in participants]


def _accepted_rows(participants: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [{"evidence_id": row.get("evidence_id"), "response_id": row.get("response_id"), "role": row.get("role"), "organization": row.get("organization"), "decision": row.get("decision"), "binding_hash": row.get("binding_hash")} for row in participants]


def _response_public_projection(response: ImplementationDocument) -> ImplementationDocument:
    return {
        "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
        "package_type": "musicforge_unified_release_program_continuity_acceptance_response_public_projection",
        "program_id": response.get("program_id"),
        "response_id": response.get("response_id"),
        "receiver_id": response.get("receiver_id"),
        "receiver_role": response.get("receiver_role"),
        "organization": response.get("organization"),
        "decision": response.get("decision"),
        "reviewed_at": response.get("reviewed_at"),
        "notes": _bounded(response.get("notes") or "", 1000),
    }


def _response_payload_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key not in {"payload_hash", "integrity_hash", "status", "imported_at"}})


def _package_manifest(package_type: str, program_id: str, files: list[ImplementationDocument], source: ImplementationDocument) -> ImplementationDocument:
    manifest = sanitize_metadata({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION, "package_type": _require_registered_package_type(package_type, writer_id="song_agent.domains.program.unified_release_program_continuity_acceptance._package_manifest"), "program_id": program_id, "created_at": now_iso(), "source": source, "files": sorted(files, key=lambda row: row.get("path") or ""), "zip": {}})
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _reject_forbidden(payload: ImplementationDocument, label: str) -> None:
    for key, value in payload.items():
        lowered = str(key).lower()
        if lowered in BLOCKED_RESPONSE_KEYS and value:
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"{key} is not allowed for {label}.")


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip("-")[:140]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]
