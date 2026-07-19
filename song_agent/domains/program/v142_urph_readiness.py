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

UnifiedReleaseProgramHandoffNotFoundError = _make_deferred_global('UnifiedReleaseProgramHandoffNotFoundError')
UnifiedReleaseProgramHandoffStateError = _make_deferred_global('UnifiedReleaseProgramHandoffStateError')
_bounded = _make_deferred_global('_bounded')
_file_record = _make_deferred_global('_file_record')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest_hash_from_zip = _make_deferred_global('_manifest_hash_from_zip')
_package_manifest = _make_deferred_global('_package_manifest')
_public_handoff_summary = _make_deferred_global('_public_handoff_summary')
_public_inventory = _make_deferred_global('_public_inventory')
_read_optional_json = _make_deferred_global('_read_optional_json')
_response_payload_hash = _make_deferred_global('_response_payload_hash')
_response_public_projection = _make_deferred_global('_response_public_projection')
_risk_summary = _make_deferred_global('_risk_summary')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
field = _make_deferred_global('field')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramHandoffNotFoundError, UnifiedReleaseProgramHandoffStateError, _bounded, _file_record, _integrity_hash, _integrity_ok, _manifest_hash_from_zip
    global _package_manifest, _public_handoff_summary, _public_inventory, _read_optional_json, _response_payload_hash, _response_public_projection, _risk_summary, _safe_id
    global _sha256_path, _with_integrity, field, read_json, write_json
    UnifiedReleaseProgramHandoffNotFoundError = namespace.get('UnifiedReleaseProgramHandoffNotFoundError', UnifiedReleaseProgramHandoffNotFoundError)
    UnifiedReleaseProgramHandoffStateError = namespace.get('UnifiedReleaseProgramHandoffStateError', UnifiedReleaseProgramHandoffStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _file_record = namespace.get('_file_record', _file_record)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest_hash_from_zip = namespace.get('_manifest_hash_from_zip', _manifest_hash_from_zip)
    _package_manifest = namespace.get('_package_manifest', _package_manifest)
    _public_handoff_summary = namespace.get('_public_handoff_summary', _public_handoff_summary)
    _public_inventory = namespace.get('_public_inventory', _public_inventory)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _response_payload_hash = namespace.get('_response_payload_hash', _response_payload_hash)
    _response_public_projection = namespace.get('_response_public_projection', _response_public_projection)
    _risk_summary = namespace.get('_risk_summary', _risk_summary)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    field = namespace.get('field', field)
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




class UnifiedReleaseProgramHandoffStoreReadinessMixin:
    def handoff_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "handoff"

    def report_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "handoff-report.json"

    def inventory_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "evidence-inventory.json"

    def guide_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "recipient-guide.md"

    def external_manifest_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "external-evidence-manifest.json"

    def runtime_external_manifest_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "runtime-external-evidence-manifest.json"

    def decision_board_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "decision-board.json"

    def conflict_report_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "conflict-report.json"

    def accepted_index_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "accepted-evidence-index.json"

    def readiness_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "handoff-readiness-matrix.json"

    def gap_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "handoff-gap-plan.json"

    def review_pack_dir(self, program_id: str, review_pack_id: str) -> Path:
        return self.handoff_dir(program_id) / "review-packs" / _safe_id(review_pack_id)

    def review_pack_zip_path(self, program_id: str, review_pack_id: str) -> Path:
        return self.review_pack_dir(program_id, review_pack_id) / "review-pack.zip"

    def review_pack_verification_report_path(self, program_id: str, review_pack_id: str) -> Path:
        return self.review_pack_dir(program_id, review_pack_id) / "review-pack-verification-report.json"

    def response_dir(self, program_id: str, response_id: str) -> Path:
        return self.handoff_dir(program_id) / "responses" / _safe_id(response_id)

    def response_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response.json"

    def response_verification_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response-verification-report.json"

    def response_binding_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response-binding-summary.json"

    def accepted_evidence_dir(self, program_id: str, evidence_id: str) -> Path:
        return self.handoff_dir(program_id) / "accepted-evidence" / _safe_id(evidence_id)

    def accepted_evidence_zip_path(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence.zip"

    def accepted_evidence_verification_report_path(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence-verification-report.json"

    def signoff_dir(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "signoff"

    def signoff_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "program-handoff-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "program-handoff-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "program-handoff-history.jsonl"

    def frozen_dir(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "frozen"

    def archive_dir(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "archive"

    def archive_export_dir(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "export"

    def archive_manifest_path(self, program_id: str) -> Path:
        return self.archive_export_dir(program_id) / "manifest.json"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "program-handoff-archive.zip"

    def archive_verification_report_path(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "program-handoff-archive-verification-report.json"

    def get_handoff(self, program_id: str) -> DomainDocument:
        return {
            "report": _read_optional_json(self.report_path(program_id)),
            "evidence_inventory": _read_optional_json(self.inventory_path(program_id)),
            "external_evidence_manifest": _read_optional_json(self.external_manifest_path(program_id)),
            "runtime_external_evidence_manifest": _read_optional_json(self.runtime_external_manifest_path(program_id)),
            "decision_board": _read_optional_json(self.decision_board_path(program_id)),
            "conflict_report": _read_optional_json(self.conflict_report_path(program_id)),
            "accepted_evidence_index": _read_optional_json(self.accepted_index_path(program_id)),
            "readiness_matrix": _read_optional_json(self.readiness_path(program_id)),
            "gap_plan": _read_optional_json(self.gap_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "verification": _read_optional_json(self.archive_verification_report_path(program_id)),
        }

    def refresh_handoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._build_documents(program_id, payload, write_external=True)
            self._write_live_docs(program_id, docs)
            return docs["report"]

    def export_review_pack(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._ensure_live_docs(program_id, payload)
            review_pack_id = _safe_id(str(payload.get("review_pack_id") or self._next_review_pack_id(program_id)))
            pack_dir = self.review_pack_dir(program_id, review_pack_id)
            export_dir = pack_dir / "export"
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            now = now_iso()
            source_hash = stable_hash(
                {
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "review_pack_id": review_pack_id,
                }
            )
            report = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_review_pack_report",
                    "program_id": program_id,
                    "handoff_id": docs["report"].get("handoff_id"),
                    "review_pack_id": review_pack_id,
                    "audience": _bounded(payload.get("audience") or "release_owner", 80),
                    "status": "ready",
                    "source_hash": source_hash,
                    "created_at": now,
                    "summary": docs["report"].get("summary", {}),
                }
            )
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_review_pack_binding_summary",
                    "program_id": program_id,
                    "handoff_id": report.get("handoff_id"),
                    "review_pack_id": review_pack_id,
                    "source_hash": source_hash,
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                }
            )
            template = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_reviewer_form_template",
                    "required_fields": [
                        "review_pack_id",
                        "review_pack_source_hash",
                        "review_pack_zip_sha256",
                        "review_pack_manifest_hash",
                        "program_id",
                        "handoff_id",
                        "reviewer_id",
                        "reviewer_role",
                        "organization",
                        "decision",
                        "payload_hash",
                    ],
                }
            )
            files: list[DomainDocument] = []

            def write_entry(rel: str, value: DomainDocument | str) -> None:
                path = export_dir / rel
                if isinstance(value, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            write_entry("review-pack-report.json", report)
            write_entry("review-pack-binding-summary.json", binding)
            write_entry("recipient-guide.md", docs["guide"])
            write_entry("data/handoff-summary.json", _public_handoff_summary(docs))
            write_entry("data/evidence-inventory-public.json", _public_inventory(docs["inventory"]))
            write_entry("data/risk-summary-public.json", _risk_summary(docs))
            write_entry("data/reviewer-form-template.json", template)
            write_entry("README.txt", "MusicForge Unified Release Program Review Pack\n")
            manifest = _package_manifest(UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE, program_id, _as_text(report.get("handoff_id")), files, {"review_pack_report_hash": report.get("integrity_hash"), "review_pack_binding_hash": binding.get("integrity_hash")})
            write_json(export_dir / "manifest.json", manifest)
            write_json(pack_dir / "review-pack-report.json", report)
            write_json(pack_dir / "review-pack-binding-summary.json", binding)
            return {"status": "ready", "review_pack_id": review_pack_id, "manifest": manifest, "review_pack_report": report, "binding": binding}

    def build_review_pack_zip(self, program_id: str, review_pack_id: str | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            review_pack_id = _safe_id(str(review_pack_id or payload.get("review_pack_id") or ""))
            if not review_pack_id:
                created = self.export_review_pack(program_id, payload)
                review_pack_id = str(created["review_pack_id"])
            pack_dir = self.review_pack_dir(program_id, review_pack_id)
            export_dir = pack_dir / "export"
            if not (export_dir / "manifest.json").exists():
                self.export_review_pack(program_id, {**payload, "review_pack_id": review_pack_id})
            return self._build_zip(export_dir, self.review_pack_zip_path(program_id, review_pack_id), "review_pack")

    def verify_review_pack_zip(self, program_id: str, review_pack_id: str | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        review_pack_id = _safe_id(str(review_pack_id or payload.get("review_pack_id") or ""))
        zip_path = payload.get("review_pack_zip") or payload.get("zip_path") or self.review_pack_zip_path(program_id, review_pack_id)
        report = verify_unified_release_program_review_pack_package(zip_path, strict=bool(payload.get("strict", True)))
        if review_pack_id:
            write_unified_release_program_review_pack_verification_report(report, self.review_pack_verification_report_path(program_id, review_pack_id))
        return report

    def import_response(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = dict(payload or {})
        if payload.get("response_json"):
            payload.update(read_json(Path(payload["response_json"])))
        for forbidden in ("source_path", "local_path", "file_path"):
            if payload.get(forbidden):
                raise UnifiedReleaseProgramHandoffStateError(f"{forbidden} is not allowed for reviewer response import.")
        with self.lock:
            self.ensure_unsigned(program_id)
            required = [
                "review_pack_id",
                "review_pack_source_hash",
                "review_pack_zip_sha256",
                "review_pack_manifest_hash",
                "program_id",
                "handoff_id",
                "reviewer_id",
                "reviewer_role",
                "organization",
                "decision",
                "payload_hash",
            ]
            missing = [field for field in required if not payload.get(field)]
            if missing:
                raise UnifiedReleaseProgramHandoffStateError(f"Reviewer response missing binding fields: {', '.join(missing)}")
            if str(payload.get("program_id")) != program_id:
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response program_id does not match.")
            expected_hash = _response_payload_hash(payload)
            if payload.get("payload_hash") != expected_hash:
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response payload_hash is invalid.")
            review_pack_id = _safe_id(str(payload.get("review_pack_id")))
            pack_report_path = self.review_pack_dir(program_id, review_pack_id) / "review-pack-report.json"
            binding_path = self.review_pack_dir(program_id, review_pack_id) / "review-pack-binding-summary.json"
            if not pack_report_path.exists() or not binding_path.exists():
                raise UnifiedReleaseProgramHandoffNotFoundError(f"Review Pack not found: {review_pack_id}")
            pack_report = read_json(pack_report_path)
            pack_binding = read_json(binding_path)
            zip_path = self.review_pack_zip_path(program_id, review_pack_id)
            if payload.get("review_pack_source_hash") != pack_report.get("source_hash"):
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response review_pack_source_hash does not match current Review Pack.")
            if not zip_path.exists() or payload.get("review_pack_zip_sha256") != _sha256_path(zip_path):
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response review_pack_zip_sha256 does not match current Review Pack ZIP.")
            manifest_hash = _manifest_hash_from_zip(zip_path)
            if payload.get("review_pack_manifest_hash") != manifest_hash:
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response review_pack_manifest_hash does not match current Review Pack manifest.")
            response_id = _safe_id(str(payload.get("response_id") or self._next_response_id(program_id)))
            response = sanitize_metadata({**payload, "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "response_type": "musicforge_unified_release_program_review_response", "response_id": response_id, "status": "imported", "imported_at": now_iso()})
            response["integrity_hash"] = _integrity_hash(response)
            public = _response_public_projection(response)
            response_dir = self.response_dir(program_id, response_id)
            response_dir.mkdir(parents=True, exist_ok=True)
            write_json(self.response_path(program_id, response_id), response)
            verification = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE,
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "response_id": response_id,
                    "status": "passed",
                    "response_payload_hash": response.get("payload_hash"),
                    "response_integrity_hash": response.get("integrity_hash"),
                    "response_public_summary_hash": stable_hash(public),
                    "review_pack_source_hash": response.get("review_pack_source_hash"),
                    "review_pack_zip_sha256": response.get("review_pack_zip_sha256"),
                    "review_pack_manifest_hash": response.get("review_pack_manifest_hash"),
                }
            )
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_response_binding_summary",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "response_id": response_id,
                    "review_pack_id": response.get("review_pack_id"),
                    "review_pack_source_hash": response.get("review_pack_source_hash"),
                    "review_pack_zip_sha256": response.get("review_pack_zip_sha256"),
                    "review_pack_manifest_hash": response.get("review_pack_manifest_hash"),
                    "reviewer_id": response.get("reviewer_id"),
                    "reviewer_role": response.get("reviewer_role"),
                    "organization": response.get("organization"),
                    "decision": response.get("decision"),
                    "response_payload_hash": response.get("payload_hash"),
                    "response_integrity_hash": response.get("integrity_hash"),
                    "review_pack_binding_hash": pack_binding.get("integrity_hash"),
                }
            )
            write_json(self.response_verification_path(program_id, response_id), verification)
            write_json(self.response_binding_path(program_id, response_id), binding)
            (response_dir / "response-raw-sha256.txt").write_text(str(response.get("payload_hash")), encoding="utf-8")
            return {"status": "imported", "response": response, "verification": verification, "binding": binding}

    def create_accepted_evidence(self, program_id: str, response_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            self.ensure_unsigned(program_id)
            response_id = _safe_id(response_id)
            response = read_json(self.response_path(program_id, response_id))
            if response.get("decision") not in {"accepted", "accepted_with_notes"}:
                raise UnifiedReleaseProgramHandoffStateError("Only accepted reviewer responses can create accepted evidence.")
            verification = read_json(self.response_verification_path(program_id, response_id))
            binding = read_json(self.response_binding_path(program_id, response_id))
            if verification.get("status") != "passed" or not _integrity_ok(verification) or not _integrity_ok(binding):
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response verification or binding failed.")
            evidence_id = _safe_id(str(response.get("evidence_id") or self._next_evidence_id(program_id)))
            evidence_dir = self.accepted_evidence_dir(program_id, evidence_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            public_response = _with_integrity(_response_public_projection(response))
            verification_summary = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_response_verification_summary",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "response_id": response_id,
                    "status": verification.get("status"),
                    "response_payload_hash": verification.get("response_payload_hash"),
                    "response_verification_hash": verification.get("integrity_hash"),
                    "response_public_summary_hash": verification.get("response_public_summary_hash"),
                }
            )
            report = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_accepted_evidence_report",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "decision": response.get("decision"),
                    "reviewer": {
                        "reviewer_id": response.get("reviewer_id"),
                        "role": binding.get("reviewer_role"),
                        "organization": binding.get("organization"),
                    },
                    "source": {
                        "response_payload_hash": binding.get("response_payload_hash"),
                        "response_verification_hash": verification.get("integrity_hash"),
                        "response_binding_hash": binding.get("integrity_hash"),
                        "review_pack_source_hash": binding.get("review_pack_source_hash"),
                    },
                    "public_summary": {"accepted": True, "role": binding.get("reviewer_role"), "organization": binding.get("organization")},
                    "status": "accepted",
                }
            )
            evidence_binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_accepted_evidence_binding_summary",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "accepted_evidence_report_hash": report.get("integrity_hash"),
                    "response_verification_hash": verification.get("integrity_hash"),
                    "response_binding_hash": binding.get("integrity_hash"),
                    "reviewer_role": binding.get("reviewer_role"),
                    "organization": binding.get("organization"),
                    "decision": binding.get("decision"),
                }
            )
            write_json(evidence_dir / "original-response-public.json", public_response)
            write_json(evidence_dir / "response-verification-summary.json", verification_summary)
            write_json(evidence_dir / "response-binding-summary.json", binding)
            write_json(evidence_dir / "accepted-evidence-report.json", report)
            write_json(evidence_dir / "accepted-evidence-binding-summary.json", evidence_binding)
            self.build_accepted_evidence_zip(program_id, evidence_id)
            self.verify_accepted_evidence_zip(program_id, evidence_id)
            self.refresh_decision_board(program_id, {})
            return {"status": "accepted", "evidence": report, "binding": evidence_binding}

    def build_accepted_evidence_zip(self, program_id: str, evidence_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        evidence_id = _safe_id(evidence_id)
        evidence_dir = self.accepted_evidence_dir(program_id, evidence_id)
        export_dir = evidence_dir / "export"
        if export_dir.exists():
            shutil.rmtree(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        files: list[DomainDocument] = []

        def copy_entry(rel: str) -> None:
            source = evidence_dir / rel
            dest = export_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            files.append(_file_record(dest, rel))

        for rel in sorted(ACCEPTED_EVIDENCE_REQUIRED_ENTRIES - {"manifest.json", "README.txt"}):
            copy_entry(rel)
        readme = export_dir / "README.txt"
        readme.write_text("MusicForge Unified Release Program Accepted Evidence\n", encoding="utf-8")
        files.append(_file_record(readme, "README.txt"))
        report = read_json(evidence_dir / "accepted-evidence-report.json")
        manifest = _package_manifest(UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, program_id, _as_text(report.get("handoff_id")), files, {"accepted_evidence_report_hash": report.get("integrity_hash")})
        write_json(export_dir / "manifest.json", manifest)
        return self._build_zip(export_dir, self.accepted_evidence_zip_path(program_id, evidence_id), "accepted_evidence")
