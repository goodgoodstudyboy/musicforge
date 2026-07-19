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
_accepted_rows = _make_deferred_global('_accepted_rows')
_board_policy = _make_deferred_global('_board_policy')
_decision_readiness = _make_deferred_global('_decision_readiness')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_matrix_rows = _make_deferred_global('_matrix_rows')
_read_optional_json = _make_deferred_global('_read_optional_json')
_receiver_rows = _make_deferred_global('_receiver_rows')
_response_public_projection = _make_deferred_global('_response_public_projection')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
doc = _make_deferred_global('doc')
expected_doc = _make_deferred_global('expected_doc')
field = _make_deferred_global('field')
info = _make_deferred_global('info')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
name = _make_deferred_global('name')
ok = _make_deferred_global('ok')
read_json = _make_deferred_global('read_json')
value = _make_deferred_global('value')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityAcceptanceStateError, _accepted_rows, _board_policy, _decision_readiness, _file_record, _gate_failed, _integrity_hash, _integrity_ok
    global _matrix_rows, _read_optional_json, _receiver_rows, _response_public_projection, _sha256_path, _with_integrity, doc
    global expected_doc, field, info, item, key, name, ok, read_json
    global value, write_json
    UnifiedReleaseProgramContinuityAcceptanceStateError = namespace.get('UnifiedReleaseProgramContinuityAcceptanceStateError', UnifiedReleaseProgramContinuityAcceptanceStateError)
    _accepted_rows = namespace.get('_accepted_rows', _accepted_rows)
    _board_policy = namespace.get('_board_policy', _board_policy)
    _decision_readiness = namespace.get('_decision_readiness', _decision_readiness)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _matrix_rows = namespace.get('_matrix_rows', _matrix_rows)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _receiver_rows = namespace.get('_receiver_rows', _receiver_rows)
    _response_public_projection = namespace.get('_response_public_projection', _response_public_projection)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    doc = namespace.get('doc', doc)
    expected_doc = namespace.get('expected_doc', expected_doc)
    field = namespace.get('field', field)
    info = namespace.get('info', info)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    name = namespace.get('name', name)
    ok = namespace.get('ok', ok)
    read_json = namespace.get('read_json', read_json)
    value = namespace.get('value', value)
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




class UnifiedReleaseProgramContinuityAcceptanceStoreEvidenceMixin:
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

    def gate(self, program_id: str, *, required: bool = False, archive_zip_path: Path | str | None = None, verification_report_path: Path | str | None = None, **payload: object) -> DomainDocument:
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

    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        latest: DomainDocument | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "continuity_acceptance_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            if event.get("event_type") == "continuity_acceptance_signoff_reset":
                latest = {"status": "reset", "previous_signoff_hash": event.get("previous_signoff_hash"), "event": event}
        if latest:
            return latest
        return {"status": "unsigned"}

    def read_history(self, program_id: str) -> list[DomainDocument]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()

    def _build_board_documents(self, program_id: str, payload: DomainDocument) -> DomainDocument:
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

    def _current_kit_source(self, program_id: str) -> DomainDocument:
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

    def _response_bundles(self, program_id: str) -> dict[str, DomainDocument]:
        bundles: dict[str, DomainDocument] = {}
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

    def _evidence_bundles(self, program_id: str) -> dict[str, DomainDocument]:
        base = self.acceptance_dir(program_id) / "accepted-evidence"
        bundles: dict[str, DomainDocument] = {}
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

    def _participants_from_evidence(self, evidences: dict[str, DomainDocument], responses: dict[str, DomainDocument], source: DomainDocument) -> tuple[list[DomainDocument], list[DomainDocument]]:
        participants: list[DomainDocument] = []
        conflicts: list[DomainDocument] = []
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

    def _response_decision_conflicts(self, responses: dict[str, DomainDocument], policy: DomainDocument) -> list[DomainDocument]:
        conflicts: list[DomainDocument] = []
        for response_id, bundle in responses.items():
            decision = bundle["binding"].get("decision")
            if decision == "rejected" and bool(policy.get("block_on_rejected", True)):
                conflicts.append({"reason": "rejected_response_present", "response_id": response_id})
            if decision == "needs_changes" and bool(policy.get("block_on_needs_changes", True)):
                conflicts.append({"reason": "needs_changes_response_present", "response_id": response_id})
        return conflicts

    def _write_docs(self, program_id: str, docs: DomainDocument) -> None:
        self.acceptance_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.board_path(program_id), docs["board"])
        write_json(self.report_path(program_id), docs["report"])
        write_json(self.decision_matrix_path(program_id), docs["matrix"])
        write_json(self.receiver_index_path(program_id), docs["receiver_index"])
        write_json(self.accepted_index_path(program_id), docs["accepted_index"])
        write_json(self.external_manifest_path(program_id), docs["external_manifest"])
        write_json(self.source_binding_path(program_id), docs["source"])

    def _archive_documents(self, program_id: str) -> DomainDocument:
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

    def _validate_signed_archive_sources(self, program_id: str, docs: DomainDocument) -> None:
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

    def _validate_accepted_evidence_bundle(self, program_id: str, evidence_id: str, bundle: DomainDocument, responses: dict[str, DomainDocument], source: DomainDocument) -> None:
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

    def _validate_history_chain(self, program_id: str, signoff: DomainDocument, binding: DomainDocument) -> None:
        validation = HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).validate()
        if not validation.valid:
            index = (validation.error_index or 0) + 1
            raise UnifiedReleaseProgramContinuityAcceptanceStateError(f"Continuity Acceptance history chain failed at event {index}.")
        latest_signoff_event: DomainDocument = {}
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
