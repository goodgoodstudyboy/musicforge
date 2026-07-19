# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list, as_text as _as_text
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.domains.program.ports import ProgramReleaseStore as ProgramReleaseStore
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_handoff_verifier import ACCEPTED_EVIDENCE_REQUIRED_ENTRIES as ACCEPTED_EVIDENCE_REQUIRED_ENTRIES, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE, verify_unified_release_program_accepted_evidence_package as verify_unified_release_program_accepted_evidence_package, verify_unified_release_program_handoff_package as verify_unified_release_program_handoff_package, verify_unified_release_program_review_pack_package as verify_unified_release_program_review_pack_package, write_unified_release_program_accepted_evidence_verification_report as write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_handoff_verification_report as write_unified_release_program_handoff_verification_report, write_unified_release_program_review_pack_verification_report as write_unified_release_program_review_pack_verification_report
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package

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

UnifiedReleaseProgramHandoffStateError = _make_deferred_global('UnifiedReleaseProgramHandoffStateError')
_archive_source = _make_deferred_global('_archive_source')
_board_policy = _make_deferred_global('_board_policy')
_bounded = _make_deferred_global('_bounded')
_check = _make_deferred_global('_check')
_decision_readiness = _make_deferred_global('_decision_readiness')
_external_manifest_from_rows = _make_deferred_global('_external_manifest_from_rows')
_file_record = _make_deferred_global('_file_record')
_gap_items = _make_deferred_global('_gap_items')
_gate_failed = _make_deferred_global('_gate_failed')
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest_row = _make_deferred_global('_manifest_row')
_package_manifest = _make_deferred_global('_package_manifest')
_path_checks = _make_deferred_global('_path_checks')
_public_external_manifest = _make_deferred_global('_public_external_manifest')
_read_optional_json = _make_deferred_global('_read_optional_json')
_readiness_rows = _make_deferred_global('_readiness_rows')
_recipient_guide = _make_deferred_global('_recipient_guide')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_source_without_checks = _make_deferred_global('_source_without_checks')
_verification_summary_from_state = _make_deferred_global('_verification_summary_from_state')
_with_integrity = _make_deferred_global('_with_integrity')
item = _make_deferred_global('item')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramHandoffStateError, _archive_source, _board_policy, _bounded, _check, _decision_readiness, _external_manifest_from_rows, _file_record
    global _gap_items, _gate_failed, _history_text, _integrity_hash, _integrity_ok, _manifest_row, _package_manifest
    global _path_checks, _public_external_manifest, _read_optional_json, _readiness_rows, _recipient_guide, _safe_id, _sha256_path, _source_without_checks
    global _verification_summary_from_state, _with_integrity, item, read_json, write_json
    UnifiedReleaseProgramHandoffStateError = namespace.get('UnifiedReleaseProgramHandoffStateError', UnifiedReleaseProgramHandoffStateError)
    _archive_source = namespace.get('_archive_source', _archive_source)
    _board_policy = namespace.get('_board_policy', _board_policy)
    _bounded = namespace.get('_bounded', _bounded)
    _check = namespace.get('_check', _check)
    _decision_readiness = namespace.get('_decision_readiness', _decision_readiness)
    _external_manifest_from_rows = namespace.get('_external_manifest_from_rows', _external_manifest_from_rows)
    _file_record = namespace.get('_file_record', _file_record)
    _gap_items = namespace.get('_gap_items', _gap_items)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest_row = namespace.get('_manifest_row', _manifest_row)
    _package_manifest = namespace.get('_package_manifest', _package_manifest)
    _path_checks = namespace.get('_path_checks', _path_checks)
    _public_external_manifest = namespace.get('_public_external_manifest', _public_external_manifest)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _readiness_rows = namespace.get('_readiness_rows', _readiness_rows)
    _recipient_guide = namespace.get('_recipient_guide', _recipient_guide)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _source_without_checks = namespace.get('_source_without_checks', _source_without_checks)
    _verification_summary_from_state = namespace.get('_verification_summary_from_state', _verification_summary_from_state)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    item = namespace.get('item', item)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


DEFAULT_BOARD_POLICY = {
    "minimum_acceptances": 1,
    "minimum_organizations": 1,
    "required_roles": ["release_owner"],
    "block_on_rejected": True,
    "block_on_needs_changes": True,
    "block_on_critical_finding": True,
}




class UnifiedReleaseProgramHandoffStoreEvidenceMixin:
    def verify_accepted_evidence_zip(self, program_id: str, evidence_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        evidence_id = _safe_id(evidence_id)
        report_doc = read_json(self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence-report.json")
        response_id = str(report_doc.get("response_id"))
        report = verify_unified_release_program_accepted_evidence_package(
            payload.get("accepted_evidence_zip") or self.accepted_evidence_zip_path(program_id, evidence_id),
            strict=bool(payload.get("strict", True)),
            require_accepted=bool(payload.get("require_accepted", True)),
            response_verification_report_path=payload.get("response_verification_report") or self.response_verification_path(program_id, response_id),
            response_binding_summary_path=payload.get("response_binding_summary") or self.response_binding_path(program_id, response_id),
        )
        write_unified_release_program_accepted_evidence_verification_report(report, self.accepted_evidence_verification_report_path(program_id, evidence_id))
        return report

    def refresh_decision_board(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            policy = _board_policy(payload.get("policy") if "policy" in payload else (_read_optional_json(self.decision_board_path(program_id)).get("policy") or None))
            participants, conflicts = self._accepted_participants(program_id)
            conflicts.extend(self._response_decision_conflicts(program_id, policy))
            readiness = _decision_readiness(policy, participants, conflicts)
            board = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_decision_board",
                    "program_id": program_id,
                    "handoff_id": self._handoff_id(program_id, payload),
                    "board_id": _safe_id(str(payload.get("board_id") or "urpdb-000001")),
                    "policy": policy,
                    "participants": participants,
                    "conflicts": conflicts,
                    "readiness": readiness,
                    "status": readiness.get("status"),
                }
            )
            conflict_report = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_conflict_report", "program_id": program_id, "handoff_id": board.get("handoff_id"), "conflicts": conflicts, "summary": {"conflict_count": len(conflicts)}})
            accepted_index = self._accepted_index_document(program_id, participants)
            readiness_doc = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_readiness_matrix", "program_id": program_id, "handoff_id": board.get("handoff_id"), "rows": _readiness_rows(readiness), "summary": readiness})
            gap = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_gap_plan", "program_id": program_id, "handoff_id": board.get("handoff_id"), "items": _gap_items(readiness), "summary": {"gap_count": len(_gap_items(readiness))}})
            write_json(self.decision_board_path(program_id), board)
            write_json(self.conflict_report_path(program_id), conflict_report)
            write_json(self.accepted_index_path(program_id), accepted_index)
            write_json(self.readiness_path(program_id), readiness_doc)
            write_json(self.gap_path(program_id), gap)
            if self.report_path(program_id).exists():
                report = read_json(self.report_path(program_id))
                report["summary"] = {**(report.get("summary") or {}), "quorum_status": readiness.get("status"), "accepted_response_count": len(participants), "missing_roles": readiness.get("missing_roles", [])}
                report["status"] = "ready_for_signoff" if readiness.get("status") == "ready_for_signoff" and not report.get("blockers") else report.get("status")
                report["integrity_hash"] = _integrity_hash(report)
                write_json(self.report_path(program_id), report)
            return board

    def signoff_handoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            if not self.report_path(program_id).exists():
                self.refresh_handoff(program_id, payload)
            board = self.refresh_decision_board(program_id, {})
            if board.get("status") != "ready_for_signoff":
                raise UnifiedReleaseProgramHandoffStateError("Program Handoff Decision Board is not ready for signoff.")
            docs = self._docs_for_signoff(program_id)
            now = now_iso()
            docs["report"]["status"] = "signed"
            docs["report"]["signed_at"] = now
            docs["report"]["integrity_hash"] = _integrity_hash(docs["report"])
            role = _bounded(payload.get("role") or "release_owner", 80)
            allowed_roles = set((board.get("policy") or {}).get("required_roles") or ["release_owner"])
            if role not in allowed_roles:
                raise UnifiedReleaseProgramHandoffStateError("Program Handoff signer role is not allowed by policy.")
            signoff = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_handoff_signoff",
                    "program_id": program_id,
                    "handoff_id": docs["report"].get("handoff_id"),
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "program-handoff-chair", 120),
                    "role": role,
                    "reason": _bounded(payload.get("reason") or "Unified Release Program final handoff accepted.", 1000),
                    "signed_at": now,
                    "source_hash": docs["report"].get("source_hash"),
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "decision_board_hash": docs["decision"].get("integrity_hash"),
                    "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "tool": {"name": "MusicForge Unified Release Program Final Handoff", "version": __version__},
                }
            )
            signoff = SignoffService.seal(signoff)
            self.signoff_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "unified_release_program_handoff_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "handoff_id": signoff.get("handoff_id"),
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": signoff.get("source_hash"),
                    "handoff_report_hash": signoff.get("handoff_report_hash"),
                    "decision_board_hash": signoff.get("decision_board_hash"),
                },
            )
            binding = self._signoff_binding(signoff, event, docs)
            write_json(self.signoff_binding_path(program_id), binding)
            self._write_frozen(program_id, docs)
            write_json(self.report_path(program_id), docs["report"])
            return signoff

    def export_handoff_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
                if isinstance(value, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            write_entry("program-handoff-report.json", docs["report"])
            write_entry("evidence-inventory.json", docs["inventory"])
            write_entry("recipient-guide.md", docs["guide"])
            write_entry("decision-board.json", docs["decision"])
            write_entry("conflict-report.json", docs["conflicts"])
            write_entry("accepted-evidence-index.json", docs["accepted_index"])
            write_entry("handoff-readiness-matrix.json", docs["readiness"])
            write_entry("handoff-gap-plan.json", docs["gap"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            write_entry("program-handoff-signoff.json", docs["signoff"])
            write_entry("program-handoff-signoff-binding-summary.json", docs["binding"])
            write_entry("program-handoff-history.jsonl", _history_text(self.read_history(program_id)))
            write_entry("verification-summaries/program-verification-summary.json", docs["program_summary"])
            write_entry("verification-summaries/operations-verification-summary.json", docs["operations_summary"])
            write_entry("verification-summaries/accepted-evidence-verification-summaries.json", docs["accepted_summary"])
            write_entry("README.txt", "MusicForge Unified Release Program Final Handoff Archive\n")
            manifest = _package_manifest(UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, program_id, docs["report"].get("handoff_id"), files, _archive_source(docs))
            write_json(self.archive_manifest_path(program_id), manifest)
            return manifest

    def build_handoff_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            self.export_handoff_archive(program_id)
            return self._build_zip(self.archive_export_dir(program_id), self.archive_zip_path(program_id), "handoff_archive")

    def verify_handoff_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_release_program_handoff_package(
            payload.get("handoff_zip") or payload.get("handoff_archive_zip") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_accepted=bool(payload.get("require_accepted", True)),
            require_signed=bool(payload.get("require_signed", True)),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or self.runtime_external_manifest_path(program_id),
            handoff_signoff_binding_path=payload.get("handoff_signoff_binding") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_handoff_verification_report(report, self.archive_verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, handoff_archive_zip_path: Path | str | None = None, handoff_archive_verification_report_path: Path | str | None = None, **payload: object) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(handoff_archive_zip_path) if handoff_archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(handoff_archive_verification_report_path) if handoff_archive_verification_report_path else self.archive_verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Final Handoff Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Final Handoff verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_handoff_package(
                zip_path,
                strict=True,
                require_current=True,
                require_accepted=True,
                require_signed=True,
                external_evidence_manifest_path=payload.get("external_evidence_manifest") or self.runtime_external_manifest_path(program_id),
                handoff_signoff_binding_path=payload.get("handoff_signoff_binding") or self.signoff_binding_path(program_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program Final Handoff verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program Final Handoff verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program Final Handoff verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program Final Handoff gate passed.", "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, program_id: str) -> None:
        if self.latest_signoff_state(program_id).get("status") == "signed":
            raise UnifiedReleaseProgramHandoffStateError("Unified Release Program Final Handoff is signed. Create a new handoff for changes.")

    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        latest: DomainDocument | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "unified_release_program_handoff_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
        if latest:
            return latest
        if self.signoff_path(program_id).exists():
            signoff = read_json(self.signoff_path(program_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_history(self, program_id: str) -> list[DomainDocument]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()

    def _build_documents(self, program_id: str, payload: DomainDocument, *, write_external: bool) -> DomainDocument:
        handoff_id = self._handoff_id(program_id, payload)
        runtime_external_manifest = self._external_manifest(program_id, handoff_id, payload)
        external_manifest = _public_external_manifest(runtime_external_manifest)
        if write_external:
            write_json(self.runtime_external_manifest_path(program_id), runtime_external_manifest)
            write_json(self.external_manifest_path(program_id), external_manifest)
        program_state = self._current_program_state(runtime_external_manifest)
        operations_state = self._current_operations_state(runtime_external_manifest)
        checks = list(program_state.get("checks", [])) + list(operations_state.get("checks", []))
        blockers = [row["check_id"] for row in checks if row.get("status") == "failed"]
        participants, conflicts = self._accepted_participants(program_id)
        decision = _read_optional_json(self.decision_board_path(program_id))
        policy = _board_policy(decision.get("policy") if decision else DEFAULT_BOARD_POLICY)
        conflicts.extend(self._response_decision_conflicts(program_id, policy))
        accepted_index = self._accepted_index_document(program_id, participants)
        if not decision:
            decision = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_decision_board", "program_id": program_id, "handoff_id": handoff_id, "board_id": "urpdb-000001", "policy": policy, "participants": participants, "conflicts": conflicts, "readiness": _decision_readiness(policy, participants, conflicts), "status": "pending"})
        else:
            decision = {**decision, "participants": participants, "conflicts": conflicts, "readiness": _decision_readiness(policy, participants, conflicts), "status": _decision_readiness(policy, participants, conflicts).get("status"), "integrity_hash": None}
            decision["integrity_hash"] = _integrity_hash(decision)
        inventory = self._evidence_inventory(program_id, handoff_id, program_state, operations_state, participants)
        now = now_iso()
        source = {
            "program": _source_without_checks(program_state),
            "operations": _source_without_checks(operations_state),
            "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
            "accepted_evidence_index_hash": accepted_index.get("integrity_hash"),
        }
        source_hash = stable_hash(source)
        readiness_summary = _decision_readiness(policy, participants, conflicts)
        status = "ready_for_signoff" if not blockers and readiness_summary.get("status") == "ready_for_signoff" else "ready_for_review" if not blockers else "blocked"
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_handoff_report",
                "program_id": program_id,
                "handoff_id": handoff_id,
                "status": status,
                "created_at": now,
                "source": source,
                "source_hash": source_hash,
                "summary": {
                    "accepted_response_count": len(participants),
                    "required_role_count": len(_as_list(_as_document(decision.get("policy") or DEFAULT_BOARD_POLICY).get("required_roles"))),
                    "quorum_status": readiness_summary.get("status"),
                    "open_blocker_count": len(blockers),
                    "risk_level": "low" if not blockers else "critical",
                    **inventory.get("summary", {}),
                },
                "warnings": [],
                "blockers": blockers,
            }
        )
        conflict_report = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_conflict_report", "program_id": program_id, "handoff_id": handoff_id, "conflicts": conflicts, "summary": {"conflict_count": len(conflicts)}})
        readiness = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_readiness_matrix", "program_id": program_id, "handoff_id": handoff_id, "rows": _readiness_rows(readiness_summary), "summary": readiness_summary})
        gap = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_gap_plan", "program_id": program_id, "handoff_id": handoff_id, "items": _gap_items(readiness_summary) + [{"check_id": row["check_id"], "status": "manual_required"} for row in checks if row.get("status") == "failed"], "summary": {"gap_count": len(_gap_items(readiness_summary)) + len(blockers)}})
        return {"report": report, "inventory": inventory, "guide": _recipient_guide(report, inventory), "external_manifest": external_manifest, "runtime_external_manifest": runtime_external_manifest, "decision": decision, "conflicts": conflict_report, "accepted_index": accepted_index, "readiness": readiness, "gap": gap, "program_state": program_state, "operations_state": operations_state}

    def _write_live_docs(self, program_id: str, docs: DomainDocument) -> None:
        self.handoff_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.report_path(program_id), docs["report"])
        write_json(self.inventory_path(program_id), docs["inventory"])
        self.guide_path(program_id).write_text(docs["guide"], encoding="utf-8")
        write_json(self.external_manifest_path(program_id), docs["external_manifest"])
        if docs.get("runtime_external_manifest"):
            write_json(self.runtime_external_manifest_path(program_id), docs["runtime_external_manifest"])
        write_json(self.decision_board_path(program_id), docs["decision"])
        write_json(self.conflict_report_path(program_id), docs["conflicts"])
        write_json(self.accepted_index_path(program_id), docs["accepted_index"])
        write_json(self.readiness_path(program_id), docs["readiness"])
        write_json(self.gap_path(program_id), docs["gap"])

    def _ensure_live_docs(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        if not self.report_path(program_id).exists():
            docs = self._build_documents(program_id, payload, write_external=True)
            self._write_live_docs(program_id, docs)
            return docs
        return {
            "report": read_json(self.report_path(program_id)),
            "inventory": read_json(self.inventory_path(program_id)),
            "guide": self.guide_path(program_id).read_text(encoding="utf-8") if self.guide_path(program_id).exists() else "",
            "external_manifest": read_json(self.external_manifest_path(program_id)),
            "runtime_external_manifest": _read_optional_json(self.runtime_external_manifest_path(program_id)),
            "decision": _read_optional_json(self.decision_board_path(program_id)),
            "conflicts": _read_optional_json(self.conflict_report_path(program_id)),
            "accepted_index": _read_optional_json(self.accepted_index_path(program_id)),
            "readiness": _read_optional_json(self.readiness_path(program_id)),
            "gap": _read_optional_json(self.gap_path(program_id)),
        }

    def _docs_for_signoff(self, program_id: str) -> DomainDocument:
        docs = self._ensure_live_docs(program_id, {})
        for key, path in (("report", self.report_path(program_id)), ("inventory", self.inventory_path(program_id)), ("decision", self.decision_board_path(program_id)), ("accepted_index", self.accepted_index_path(program_id)), ("external_manifest", self.external_manifest_path(program_id))):
            doc = read_json(path)
            if not _integrity_ok(doc):
                raise UnifiedReleaseProgramHandoffStateError(f"Program Handoff {key} integrity failed.")
            docs[key] = doc
        if docs["report"].get("blockers"):
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff report has blockers.")
        return docs

    def _archive_documents(self, program_id: str) -> DomainDocument:
        if self.latest_signoff_state(program_id).get("status") != "signed":
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff must be signed before archive export.")
        signoff = read_json(self.signoff_path(program_id))
        binding = read_json(self.signoff_binding_path(program_id))
        if not _integrity_ok(signoff) or not _integrity_ok(binding):
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff signoff integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff signoff binding does not match signoff.")
        frozen = self.frozen_dir(program_id)
        docs: DomainDocument = {
            "report": read_json(frozen / "program-handoff-report.json"),
            "inventory": read_json(frozen / "evidence-inventory.json"),
            "guide": (frozen / "recipient-guide.md").read_text(encoding="utf-8"),
            "decision": read_json(frozen / "decision-board.json"),
            "conflicts": read_json(frozen / "conflict-report.json"),
            "accepted_index": read_json(frozen / "accepted-evidence-index.json"),
            "readiness": read_json(frozen / "handoff-readiness-matrix.json"),
            "gap": read_json(frozen / "handoff-gap-plan.json"),
            "external_manifest": read_json(frozen / "external-evidence-manifest.json"),
            "signoff": signoff,
            "binding": binding,
        }
        expected = {
            "handoff_report_hash": docs["report"].get("integrity_hash"),
            "decision_board_hash": docs["decision"].get("integrity_hash"),
            "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
            "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        }
        for key, value in expected.items():
            if signoff.get(key) != value or binding.get(key) != value:
                raise UnifiedReleaseProgramHandoffStateError("Program Handoff frozen docs do not match signoff.")
        runtime_external_manifest = _as_document(
            _read_optional_json(self.runtime_external_manifest_path(program_id)) or docs["external_manifest"]
        )
        docs["program_summary"] = _verification_summary_from_state("program", self._current_program_state(_as_document(runtime_external_manifest)))
        docs["operations_summary"] = _verification_summary_from_state("operations", self._current_operations_state(_as_document(runtime_external_manifest)))
        docs["accepted_summary"] = self._accepted_verification_summary(_as_document(runtime_external_manifest))
        return docs

    def _write_frozen(self, program_id: str, docs: DomainDocument) -> None:
        frozen = self.frozen_dir(program_id)
        if frozen.exists():
            shutil.rmtree(frozen)
        frozen.mkdir(parents=True, exist_ok=True)
        write_json(frozen / "program-handoff-report.json", docs["report"])
        write_json(frozen / "evidence-inventory.json", docs["inventory"])
        (frozen / "recipient-guide.md").write_text(docs["guide"], encoding="utf-8")
        write_json(frozen / "decision-board.json", docs["decision"])
        write_json(frozen / "conflict-report.json", docs["conflicts"])
        write_json(frozen / "accepted-evidence-index.json", docs["accepted_index"])
        write_json(frozen / "handoff-readiness-matrix.json", docs["readiness"])
        write_json(frozen / "handoff-gap-plan.json", docs["gap"])
        write_json(frozen / "external-evidence-manifest.json", docs["external_manifest"])

    def _external_manifest(self, program_id: str, handoff_id: str, payload: DomainDocument) -> DomainDocument:
        path = payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path")
        if path:
            return read_json(Path(path))
        if self.runtime_external_manifest_path(program_id).exists():
            return read_json(self.runtime_external_manifest_path(program_id))
        if self.external_manifest_path(program_id).exists():
            return read_json(self.external_manifest_path(program_id))
        rows = payload.get("external_evidence") or payload.get("items") or []
        return _external_manifest_from_rows(program_id, handoff_id, rows)

    def _current_program_state(self, external_manifest: DomainDocument) -> DomainDocument:
        row = _manifest_row(external_manifest, "unified_release_program")
        checks: list[DomainDocument] = []
        if not row:
            return {"status": "missing", "checks": [_check("program_evidence_required", False, "Program evidence is required.")]}
        zip_path = Path(str(row.get("program_zip") or ""))
        report_path = Path(str(row.get("program_verification_report") or ""))
        binding_path = Path(str(row.get("program_signoff_binding") or ""))
        evidence_path = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or ""))
        checks.extend(_path_checks("program", {"zip": zip_path, "verification": report_path, "binding": binding_path, "external_manifest": evidence_path}))
        if any(item["status"] == "failed" for item in checks):
            return {"status": "missing", "checks": checks}
        external = read_json(report_path)
        runtime = verify_unified_release_program_package(zip_path, strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=evidence_path, program_signoff_binding_path=binding_path)
        checks.extend(
            [
                _check("program_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, "Program verification package type is valid."),
                _check("program_verification_integrity", _integrity_ok(external), "Program verification integrity is valid."),
                _check("program_runtime_passed", runtime.get("status") == "passed", "Program runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
                _check("program_external_passed", external.get("status") == "passed", "Program external verification passed."),
                _check("program_zip_sha256_current", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Program ZIP hash is current."),
                _check("program_manifest_hash_current", external.get("manifest_hash") == runtime.get("manifest_hash"), "Program manifest hash is current."),
            ]
        )
        return {
            "status": "ready" if not [item for item in checks if item.get("status") == "failed"] else "failed",
            "checks": checks,
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": _integrity_hash(external),
            "verification_status": external.get("status"),
            "runtime_status": runtime.get("status"),
            "signoff_binding_hash": _integrity_hash(read_json(binding_path)),
            "external_evidence_manifest_hash": _integrity_hash(read_json(evidence_path)),
        }
