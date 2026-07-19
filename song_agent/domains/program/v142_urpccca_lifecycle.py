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

UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError')
UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError')
_findings_rows = _make_deferred_global('_findings_rows')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest = _make_deferred_global('_manifest')
_policy = _make_deferred_global('_policy')
_quorum_summary = _make_deferred_global('_quorum_summary')
_read_optional_json = _make_deferred_global('_read_optional_json')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
doc = _make_deferred_global('doc')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError, UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError, _findings_rows, _integrity_ok, _manifest, _policy, _quorum_summary
    global _read_optional_json, _safe_id, _sha256_path, _with_integrity, doc, read_json, row, write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError)
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError)
    _findings_rows = namespace.get('_findings_rows', _findings_rows)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest = namespace.get('_manifest', _manifest)
    _policy = namespace.get('_policy', _policy)
    _quorum_summary = namespace.get('_quorum_summary', _quorum_summary)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    doc = namespace.get('doc', doc)
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




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceStoreLifecycleMixin:
    def _current_v1210_context(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        archive_path = Path(payload.get("command_center_signoff_archive") or payload.get("signoff_archive") or self.signoff_store.archive_zip_path(program_id))
        archive_report_path = Path(payload.get("command_center_signoff_archive_verification_report") or payload.get("signoff_archive_verification_report") or self.signoff_store.archive_verification_report_path(program_id))
        handoff_path = Path(payload.get("command_center_final_handoff") or payload.get("final_handoff") or self.signoff_store.final_handoff_zip_path(program_id))
        handoff_report_path = Path(payload.get("command_center_final_handoff_verification_report") or payload.get("final_handoff_verification_report") or self.signoff_store.final_handoff_verification_report_path(program_id))
        binding_path = Path(payload.get("command_center_signoff_binding") or payload.get("signoff_binding") or self.signoff_store.signoff_binding_path(program_id))
        command_path = Path(payload.get("command_center") or self.signoff_store.command_store.zip_path(program_id))
        command_report_path = Path(payload.get("command_center_verification_report") or self.signoff_store.command_store.verification_report_path(program_id))
        evidence_path = Path(payload.get("command_center_evidence_manifest") or payload.get("command_center_external_evidence_manifest") or self.signoff_store.command_store.local_evidence_manifest_path(program_id))
        paths = (archive_path, archive_report_path, handoff_path, handoff_report_path, binding_path, command_path, command_report_path, evidence_path)
        if not all(path.is_file() for path in paths):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Current v12.10 Signoff/Handoff evidence is incomplete.")
        archive_external = read_json(archive_report_path)
        handoff_external = read_json(handoff_report_path)
        binding = read_json(binding_path)
        archive_runtime = verify_unified_release_program_continuity_command_center_signoff_package(
            archive_path,
            strict=True,
            require_signed=True,
            signoff_binding_path=binding_path,
            command_center_zip_path=command_path,
            command_center_verification_report_path=command_report_path,
            command_center_external_evidence_manifest_path=evidence_path,
        )
        handoff_runtime = verify_unified_release_program_continuity_command_center_final_handoff_package(
            handoff_path,
            strict=True,
            require_archive=True,
            archive_zip_path=archive_path,
            archive_verification_report_path=archive_report_path,
            signoff_binding_path=binding_path,
            command_center_zip_path=command_path,
            command_center_verification_report_path=command_report_path,
            command_center_external_evidence_manifest_path=evidence_path,
        )
        if (
            archive_external.get("package_type") != COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE
            or handoff_external.get("package_type") != COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE
            or not all(_integrity_ok(doc) for doc in (archive_external, handoff_external, binding))
            or archive_external.get("status") != "passed"
            or handoff_external.get("status") != "passed"
            or archive_runtime.get("status") != "passed"
            or handoff_runtime.get("status") != "passed"
            or archive_external.get("zip_sha256") != archive_runtime.get("zip_sha256")
            or archive_external.get("manifest_hash") != archive_runtime.get("manifest_hash")
            or handoff_external.get("zip_sha256") != handoff_runtime.get("zip_sha256")
            or handoff_external.get("manifest_hash") != handoff_runtime.get("manifest_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Current v12.10 Signoff/Handoff runtime verification failed.")
        command_external = read_json(command_report_path)
        evidence = read_json(evidence_path)
        source = {
            "program_id": program_id,
            "command_center_signoff_archive_zip_sha256": _sha256_path(archive_path),
            "command_center_signoff_archive_zip_size_bytes": archive_path.stat().st_size,
            "command_center_signoff_archive_manifest_hash": archive_runtime.get("manifest_hash"),
            "command_center_signoff_archive_verification_report_hash": archive_external.get("integrity_hash"),
            "command_center_final_handoff_zip_sha256": _sha256_path(handoff_path),
            "command_center_final_handoff_zip_size_bytes": handoff_path.stat().st_size,
            "command_center_final_handoff_manifest_hash": handoff_runtime.get("manifest_hash"),
            "command_center_final_handoff_verification_report_hash": handoff_external.get("integrity_hash"),
            "command_center_signoff_binding_hash": binding.get("integrity_hash"),
            "command_center_zip_sha256": binding.get("command_center_zip_sha256"),
            "command_center_manifest_hash": binding.get("command_center_manifest_hash"),
            "command_center_verification_report_hash": command_external.get("integrity_hash"),
            "external_evidence_manifest_hash": evidence.get("integrity_hash"),
        }
        return {
            "archive_path": archive_path,
            "archive_report_path": archive_report_path,
            "handoff_path": handoff_path,
            "handoff_report_path": handoff_report_path,
            "binding_path": binding_path,
            "command_path": command_path,
            "command_report_path": command_report_path,
            "evidence_path": evidence_path,
            "archive_external": archive_external,
            "handoff_external": handoff_external,
            "archive_runtime": archive_runtime,
            "handoff_runtime": handoff_runtime,
            "binding": binding,
            "source": source,
        }

    def _review_pack_documents(self, program_id: str, context: DomainDocument) -> dict[str, DomainDocument | str | bytes]:
        source = context["source"]
        source_hash = stable_hash(source)
        report = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{REVIEW_PACK_PACKAGE_TYPE}_report",
                "program_id": program_id,
                "review_pack_id": f"urpcccarp-{_safe_id(program_id)}",
                "status": "ready",
                "source": source,
                "source_hash": source_hash,
                "summary": {"package_count": 2, "runtime_status": "passed"},
            }
        )
        packages = [
            {
                "component_type": "command_center_signoff_archive",
                "path": "packages/command-center-signoff-archive.zip",
                "package_type": "musicforge_unified_release_program_continuity_command_center_signoff_archive",
                "zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
                "zip_size_bytes": source.get("command_center_signoff_archive_zip_size_bytes"),
                "manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
                "verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
            },
            {
                "component_type": "command_center_final_handoff",
                "path": "packages/command-center-final-handoff.zip",
                "package_type": "musicforge_unified_release_program_continuity_command_center_final_handoff",
                "zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
                "zip_size_bytes": source.get("command_center_final_handoff_zip_size_bytes"),
                "manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
                "verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
            },
        ]
        package_index = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{REVIEW_PACK_PACKAGE_TYPE}_package_index", "program_id": program_id, "packages": packages})
        verification = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{REVIEW_PACK_PACKAGE_TYPE}_verification_summary",
                "program_id": program_id,
                "status": "passed",
                "archive_runtime_status": context["archive_runtime"].get("status"),
                "handoff_runtime_status": context["handoff_runtime"].get("status"),
                "archive_verification_report_hash": context["archive_external"].get("integrity_hash"),
                "handoff_verification_report_hash": context["handoff_external"].get("integrity_hash"),
            }
        )
        docs: dict[str, DomainDocument | str | bytes] = {
            "README.txt": f"MusicForge Receiver Handoff Review Pack\n\nProgram: {program_id}\n",
            "review-pack-report.json": report,
            "package-index.json": package_index,
            "verification-summary.json": verification,
            "packages/command-center-signoff-archive.zip": context["archive_path"].read_bytes(),
            "packages/command-center-final-handoff.zip": context["handoff_path"].read_bytes(),
        }
        docs["manifest.json"] = _manifest(
            REVIEW_PACK_PACKAGE_TYPE,
            program_id,
            docs,
            {
                "review_pack_report_hash": report.get("integrity_hash"),
                "package_index_hash": package_index.get("integrity_hash"),
                "verification_summary_hash": verification.get("integrity_hash"),
                "source_hash": source_hash,
            },
            REVIEW_PACK_ENTRIES,
        )
        return {"manifest.json": docs.pop("manifest.json"), **docs}

    def _verify_review_pack_runtime(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        context = self._current_v1210_context(program_id, payload)
        return verify_review_pack(
            payload.get("review_pack") or self.review_pack_zip_path(program_id),
            strict=True,
            require_current=True,
            signoff_archive_verification_report_path=context["archive_report_path"],
            final_handoff_verification_report_path=context["handoff_report_path"],
            signoff_binding_path=context["binding_path"],
            command_center_zip_path=context["command_path"],
            command_center_verification_report_path=context["command_report_path"],
            command_center_external_evidence_manifest_path=context["evidence_path"],
        )

    def _current_review_source(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        review_pack = Path(payload.get("review_pack") or self.review_pack_zip_path(program_id))
        report_path = Path(payload.get("review_pack_verification_report") or self.review_pack_verification_report_path(program_id))
        if not review_pack.is_file() or not report_path.is_file():
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Current Receiver Review Pack and verification report are required.")
        runtime = self._verify_review_pack_runtime(program_id, {**payload, "review_pack": review_pack})
        external = read_json(report_path)
        if (
            external.get("package_type") != REVIEW_PACK_VERIFICATION_PACKAGE_TYPE
            or not _integrity_ok(external)
            or external.get("status") != "passed"
            or runtime.get("status") != "passed"
            or external.get("zip_sha256") != runtime.get("zip_sha256")
            or external.get("manifest_hash") != runtime.get("manifest_hash")
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError("Receiver Review Pack verification is stale or failed.")
        with zipfile.ZipFile(review_pack) as archive:
            review_report = json.loads(archive.read("review-pack-report.json").decode("utf-8"))
        review_source = _as_document(review_report.get("source"))
        return {
            "program_id": program_id,
            "review_pack_id": review_report.get("review_pack_id"),
            "review_pack_source_hash": review_report.get("source_hash"),
            "review_pack_zip_sha256": runtime.get("zip_sha256"),
            "review_pack_manifest_hash": runtime.get("manifest_hash"),
            "review_pack_verification_report_hash": external.get("integrity_hash"),
            **review_source,
        }

    def _response_bundle(self, program_id: str, response_id: str) -> tuple[DomainDocument, DomainDocument, DomainDocument]:
        paths = (
            self.response_path(program_id, response_id),
            self.response_verification_path(program_id, response_id),
            self.response_binding_path(program_id, response_id),
        )
        if not all(path.is_file() for path in paths):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError(f"Receiver response proof not found: {response_id}")
        return tuple(read_json(path) for path in paths)  # type: ignore[return-value]

    def _response_bundles(self, program_id: str) -> dict[str, DomainDocument]:
        bundles: dict[str, DomainDocument] = {}
        if not self.responses_dir(program_id).exists():
            return bundles
        for root in sorted(path for path in self.responses_dir(program_id).iterdir() if path.is_dir()):
            try:
                response, verification, binding = self._response_bundle(program_id, root.name)
                bundles[root.name] = {"response": response, "verification": verification, "binding": binding}
            except (OSError, ValueError):
                bundles[root.name] = {"error": "response_proof_unreadable"}
        return bundles

    def _verify_accepted_evidence_runtime(self, program_id: str, evidence_id: str, response_id: str) -> DomainDocument:
        return verify_accepted_evidence(
            self.accepted_evidence_zip_path(program_id, evidence_id),
            strict=True,
            require_response=True,
            response_path=self.response_path(program_id, response_id),
            response_verification_report_path=self.response_verification_path(program_id, response_id),
            response_binding_summary_path=self.response_binding_path(program_id, response_id),
        )

    def _build_board_documents(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        stored_report = _read_optional_json(self.board_report_path(program_id))
        policy = _policy(payload.get("policy") if "policy" in payload else stored_report.get("policy"))
        conflicts: list[DomainDocument] = []
        try:
            source = self._current_review_source(program_id, payload)
        except Exception as exc:
            source = dict((stored_report.get("source") or {}))
            conflicts.append({"reason": "review_pack_runtime_failed", "message": sanitize_sensitive_text(str(exc))})
        responses = self._response_bundles(program_id)
        valid_responses: dict[str, DomainDocument] = {}
        for response_id, bundle in sorted(responses.items()):
            if bundle.get("error"):
                conflicts.append({"response_id": response_id, "reason": "response_proof_unreadable"})
                continue
            failed = [row.get("check_id") for row in validate_response_proof(bundle["response"], bundle["verification"], bundle["binding"], source) if row.get("status") == "failed"]
            if failed:
                conflicts.append({"response_id": response_id, "reason": "response_proof_invalid", "blockers": failed})
                continue
            valid_responses[response_id] = bundle
        participants: list[DomainDocument] = []
        accepted_rows: list[DomainDocument] = []
        if self.accepted_evidence_root(program_id).exists():
            for evidence_root in sorted(path for path in self.accepted_evidence_root(program_id).iterdir() if path.is_dir()):
                evidence_id = evidence_root.name
                accepted_path = evidence_root / "accepted-evidence.json"
                report_path = evidence_root / "verification-report.json"
                if not accepted_path.is_file() or not report_path.is_file():
                    conflicts.append({"evidence_id": evidence_id, "reason": "accepted_evidence_missing"})
                    continue
                accepted = read_json(accepted_path)
                response_id = str(accepted.get("response_id") or "")
                runtime = self._verify_accepted_evidence_runtime(program_id, evidence_id, response_id)
                external = read_json(report_path)
                bundle = valid_responses.get(response_id) or {}
                binding = bundle.get("binding") or {}
                if (
                    runtime.get("status") != "passed"
                    or external.get("package_type") != ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE
                    or not _integrity_ok(external)
                    or external.get("status") != "passed"
                    or external.get("zip_sha256") != runtime.get("zip_sha256")
                    or external.get("manifest_hash") != runtime.get("manifest_hash")
                    or accepted.get("role") != binding.get("role")
                    or accepted.get("organization") != binding.get("organization")
                    or accepted.get("decision") != binding.get("decision")
                ):
                    conflicts.append({"evidence_id": evidence_id, "response_id": response_id, "reason": "accepted_evidence_external_binding_failed", "blockers": runtime.get("blockers") or []})
                    continue
                participant = {
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "reviewer": binding.get("reviewer"),
                    "organization": binding.get("organization"),
                    "role": binding.get("role"),
                    "decision": binding.get("decision"),
                    "reviewer_identity_hash": binding.get("reviewer_identity_hash"),
                    "decision_hash": binding.get("decision_hash"),
                    "response_binding_hash": binding.get("integrity_hash"),
                    "accepted_evidence_verification_hash": external.get("integrity_hash"),
                }
                participants.append(participant)
                accepted_rows.append(
                    {
                        "evidence_id": evidence_id,
                        "response_id": response_id,
                        "zip_sha256": runtime.get("zip_sha256"),
                        "zip_size_bytes": runtime.get("zip_size_bytes"),
                        "manifest_hash": runtime.get("manifest_hash"),
                        "verification_report_hash": external.get("integrity_hash"),
                        "response_binding_hash": binding.get("integrity_hash"),
                    }
                )
        for response_id, bundle in valid_responses.items():
            decision = bundle["binding"].get("decision")
            if decision == "rejected" and policy.get("block_on_rejected", True):
                conflicts.append({"response_id": response_id, "reason": "rejected_response_present"})
            if decision == "needs_changes" and policy.get("block_on_needs_changes", True):
                conflicts.append({"response_id": response_id, "reason": "needs_changes_response_present"})
            if policy.get("block_on_critical_findings", True) and any(str(row.get("severity") or "").lower() == "critical" for row in bundle["response"].get("findings") or [] if isinstance(row, dict)):
                conflicts.append({"response_id": response_id, "reason": "critical_finding_present"})
        quorum_summary = _quorum_summary(policy, participants, conflicts)
        matrix_rows = sorted(participants, key=lambda row: (str(row.get("role") or ""), str(row.get("response_id") or "")))
        findings_rows = _findings_rows(valid_responses)
        policy_hash = stable_hash(policy)
        matrix = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_decision_matrix", "program_id": program_id, "rows": matrix_rows})
        quorum = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_quorum_report", "program_id": program_id, "policy_hash": policy_hash, "summary": quorum_summary})
        findings = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_findings_register", "program_id": program_id, "items": findings_rows, "summary": {"finding_count": len(findings_rows), "critical_count": sum(1 for row in findings_rows if row.get("severity") == "critical")}})
        accepted_index = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_accepted_evidence_index", "program_id": program_id, "items": sorted(accepted_rows, key=lambda row: str(row.get("evidence_id") or "")), "summary": {"accepted_count": len(accepted_rows)}})
        response_rows = []
        for response_id, bundle in sorted(valid_responses.items()):
            response_rows.append(
                {
                    "response_id": response_id,
                    "decision": bundle["binding"].get("decision"),
                    "response_integrity_hash": bundle["response"].get("integrity_hash"),
                    "verification_report_hash": bundle["verification"].get("integrity_hash"),
                    "binding_hash": bundle["binding"].get("integrity_hash"),
                    "reviewer_identity_hash": bundle["binding"].get("reviewer_identity_hash"),
                    "findings_hash": bundle["binding"].get("findings_hash"),
                }
            )
        response_index = _with_integrity({"schema_version": SCHEMA_VERSION, "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_response_proof_index", "program_id": program_id, "items": response_rows, "summary": {"response_count": len(response_rows)}})
        report = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": BOARD_REPORT_PACKAGE_TYPE,
                "program_id": program_id,
                "status": "ready_for_signoff" if quorum_summary.get("status") == "ready_for_signoff" and not conflicts else "blocked",
                "policy": policy,
                "policy_hash": policy_hash,
                "source": {
                    **source,
                    "policy_hash": policy_hash,
                    "accepted_evidence_set_hash": stable_hash(accepted_rows),
                    "response_proof_set_hash": stable_hash(response_rows),
                },
                "summary": {
                    **quorum_summary,
                    "response_count": len(response_rows),
                    "finding_count": len(findings_rows),
                    "conflict_count": len(conflicts),
                },
                "conflicts": conflicts,
            }
        )
        external_manifest = _with_integrity(
            {
                "schema_version": SCHEMA_VERSION,
                "package_type": f"{BOARD_REPORT_PACKAGE_TYPE}_external_evidence_manifest",
                "program_id": program_id,
                "review_pack": {
                    "path": "review-pack/command-center-handoff-review-pack.zip",
                    "verification_report_path": "review-pack/verification-report.json",
                    "zip_sha256": source.get("review_pack_zip_sha256"),
                    "verification_report_hash": source.get("review_pack_verification_report_hash"),
                },
                "responses": [
                    {
                        "response_id": row.get("response_id"),
                        "response_path": f"responses/{row.get('response_id')}/response.json",
                        "verification_report_path": f"responses/{row.get('response_id')}/response-verification-report.json",
                        "binding_summary_path": f"responses/{row.get('response_id')}/response-binding-summary.json",
                        "binding_hash": row.get("binding_hash"),
                    }
                    for row in response_rows
                ],
                "accepted_evidence": [
                    {
                        "evidence_id": row.get("evidence_id"),
                        "response_id": row.get("response_id"),
                        "zip_path": f"accepted-evidence/{row.get('evidence_id')}/accepted-evidence.zip",
                        "verification_report_path": f"accepted-evidence/{row.get('evidence_id')}/verification-report.json",
                        "zip_sha256": row.get("zip_sha256"),
                        "verification_report_hash": row.get("verification_report_hash"),
                    }
                    for row in accepted_rows
                ],
            }
        )
        return {"report": report, "matrix": matrix, "quorum": quorum, "findings": findings, "accepted_index": accepted_index, "response_index": response_index, "external_manifest": external_manifest}

    def _write_board_documents(self, program_id: str, docs: DomainDocument) -> None:
        self.board_dir(program_id).mkdir(parents=True, exist_ok=True)
        for path, key in (
            (self.board_report_path(program_id), "report"),
            (self.decision_matrix_path(program_id), "matrix"),
            (self.quorum_report_path(program_id), "quorum"),
            (self.findings_register_path(program_id), "findings"),
            (self.accepted_index_path(program_id), "accepted_index"),
            (self.response_index_path(program_id), "response_index"),
            (self.external_evidence_manifest_path(program_id), "external_manifest"),
        ):
            write_json(path, docs[key])
