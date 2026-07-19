# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_int as _as_int, document_or as _document_or
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
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

UnifiedReleaseProgramContinuityAcceptanceStateError = _make_deferred_global('UnifiedReleaseProgramContinuityAcceptanceStateError')
_bounded = _make_deferred_global('_bounded')
_file_record = _make_deferred_global('_file_record')
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_package_manifest = _make_deferred_global('_package_manifest')
_read_optional_json = _make_deferred_global('_read_optional_json')
_reject_forbidden = _make_deferred_global('_reject_forbidden')
_response_payload_hash = _make_deferred_global('_response_payload_hash')
_response_public_projection = _make_deferred_global('_response_public_projection')
_safe_id = _make_deferred_global('_safe_id')
_with_integrity = _make_deferred_global('_with_integrity')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityAcceptanceStateError, _bounded, _file_record, _history_text, _integrity_hash, _integrity_ok, _package_manifest
    global _read_optional_json, _reject_forbidden, _response_payload_hash, _response_public_projection, _safe_id, _with_integrity, read_json, write_json
    UnifiedReleaseProgramContinuityAcceptanceStateError = namespace.get('UnifiedReleaseProgramContinuityAcceptanceStateError', UnifiedReleaseProgramContinuityAcceptanceStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _file_record = namespace.get('_file_record', _file_record)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _package_manifest = namespace.get('_package_manifest', _package_manifest)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _reject_forbidden = namespace.get('_reject_forbidden', _reject_forbidden)
    _response_payload_hash = namespace.get('_response_payload_hash', _response_payload_hash)
    _response_public_projection = namespace.get('_response_public_projection', _response_public_projection)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


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




class UnifiedReleaseProgramContinuityAcceptanceStoreReadinessMixin:
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

    def get_board(self, program_id: str) -> DomainDocument:
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

    def import_response(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def create_accepted_evidence(self, program_id: str, response_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def _validate_external_response_proof(self, program_id: str, response: DomainDocument, verification: DomainDocument, binding: DomainDocument, source: DomainDocument) -> None:
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

    def refresh_decision_board(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def signoff_acceptance(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
