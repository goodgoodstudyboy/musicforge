# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
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
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION, verify_unified_release_program_package as verify_unified_release_program_package, write_unified_release_program_verification_report as write_unified_release_program_verification_report
from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_release_train_handoff_package as verify_unified_command_center_release_train_handoff_package

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

UnifiedReleaseProgramStateError = _make_deferred_global('UnifiedReleaseProgramStateError')
_dependency_graph = _make_deferred_global('_dependency_graph')
_external_manifest = _make_deferred_global('_external_manifest')
_gap_plan = _make_deferred_global('_gap_plan')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_item_rows = _make_deferred_global('_item_rows')
_items_document = _make_deferred_global('_items_document')
_manifest_source = _make_deferred_global('_manifest_source')
_program_report = _make_deferred_global('_program_report')
_public_external_manifest = _make_deferred_global('_public_external_manifest')
_read_optional_json = _make_deferred_global('_read_optional_json')
_readiness_matrix = _make_deferred_global('_readiness_matrix')
_risk_register = _make_deferred_global('_risk_register')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramStateError, _dependency_graph, _external_manifest, _gap_plan, _integrity_hash, _integrity_ok, _item_rows, _items_document
    global _manifest_source, _program_report, _public_external_manifest, _read_optional_json, _readiness_matrix, _risk_register, read_json
    global row, write_json
    UnifiedReleaseProgramStateError = namespace.get('UnifiedReleaseProgramStateError', UnifiedReleaseProgramStateError)
    _dependency_graph = namespace.get('_dependency_graph', _dependency_graph)
    _external_manifest = namespace.get('_external_manifest', _external_manifest)
    _gap_plan = namespace.get('_gap_plan', _gap_plan)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _item_rows = namespace.get('_item_rows', _item_rows)
    _items_document = namespace.get('_items_document', _items_document)
    _manifest_source = namespace.get('_manifest_source', _manifest_source)
    _program_report = namespace.get('_program_report', _program_report)
    _public_external_manifest = namespace.get('_public_external_manifest', _public_external_manifest)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _readiness_matrix = namespace.get('_readiness_matrix', _readiness_matrix)
    _risk_register = namespace.get('_risk_register', _risk_register)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


DEFAULT_POLICY = {
    "require_all_required_trains_ready": True,
    "require_no_dependency_cycle": True,
    "require_no_critical_risk": True,
    "require_external_handoff_acceptance": False,
    "allow_advisory_warnings": True,
    "allow_optional_defer": True,
    "required_program_roles": ["release_owner"],
}




class UnifiedReleaseProgramStoreEvidenceMixin:
    def _build_documents(self, program_id: str, inputs: DomainDocument) -> DomainDocument:
        program = self.read_program(program_id)
        items_doc = self._read_items(program_id)
        runtime_external_manifest = _external_manifest(program_id, items_doc, inputs)
        exceptions = self._read_exceptions(program_id)
        item_rows = _item_rows(program, items_doc, runtime_external_manifest)
        external_manifest = _public_external_manifest(program_id, item_rows)
        now = now_iso()
        source = sanitize_metadata(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_source",
                "program_id": program_id,
                "created_at": now,
                "program_hash": program.get("integrity_hash"),
                "train_items_hash": items_doc.get("integrity_hash"),
                "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
                "exception_register_hash": exceptions.get("integrity_hash"),
                "train_handoff_fingerprints": [row.get("fingerprint", {}) | {"item_id": row.get("item_id"), "train_id": row.get("train_id"), "handoff_id": row.get("handoff_id")} for row in item_rows],
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash"}})
        source["integrity_hash"] = _integrity_hash(source)
        dependency = _dependency_graph(program_id, source["source_hash"], item_rows, now)
        readiness = _readiness_matrix(program_id, source["source_hash"], item_rows, dependency, program, now)
        risk = _risk_register(program_id, source["source_hash"], readiness, dependency, item_rows, now)
        gap = _gap_plan(program_id, source["source_hash"], readiness, risk, now)
        report = _program_report(program_id, source["source_hash"], program, items_doc, external_manifest, dependency, readiness, risk, exceptions, gap, now)
        return {"program": program, "source": source, "items": _items_document(program_id, item_rows), "external_manifest": external_manifest, "dependency": dependency, "readiness": readiness, "risk": risk, "exceptions": exceptions, "gap_plan": gap, "report": report}

    def _write_docs(self, program_id: str, docs: DomainDocument) -> None:
        for key, path in (
            ("items", self.items_path(program_id)),
            ("external_manifest", self.external_manifest_path(program_id)),
            ("dependency", self.dependency_path(program_id)),
            ("readiness", self.readiness_path(program_id)),
            ("risk", self.risk_path(program_id)),
            ("exceptions", self.exception_path(program_id)),
            ("gap_plan", self.gap_path(program_id)),
            ("report", self.report_path(program_id)),
        ):
            write_json(path, docs[key])

    def _read_items(self, program_id: str) -> DomainDocument:
        if not self.items_path(program_id).exists():
            self._write_items(program_id, [])
        return read_json(self.items_path(program_id))

    def _write_items(self, program_id: str, rows: list[DomainDocument]) -> None:
        doc = _items_document(program_id, rows)
        write_json(self.items_path(program_id), doc)

    def _read_exceptions(self, program_id: str) -> DomainDocument:
        if not self.exception_path(program_id).exists():
            self._write_exception_register(program_id, [])
        return read_json(self.exception_path(program_id))

    def _write_exception_register(self, program_id: str, rows: list[DomainDocument]) -> None:
        doc = sanitize_metadata(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_exception_register",
                "program_id": program_id,
                "exceptions": rows,
                "summary": {"approved": sum(1 for row in rows if row.get("status") == "approved"), "blocking_unapproved": sum(1 for row in rows if row.get("status") not in {"approved", "rejected"})},
            }
        )
        doc["integrity_hash"] = _integrity_hash(doc)
        write_json(self.exception_path(program_id), doc)

    def _docs_for_export(self, program_id: str) -> DomainDocument:
        if self.report_path(program_id).exists():
            docs = {
                "program": self.read_program(program_id),
                "items": read_json(self.items_path(program_id)),
                "external_manifest": read_json(self.external_manifest_path(program_id)),
                "dependency": read_json(self.dependency_path(program_id)),
                "readiness": read_json(self.readiness_path(program_id)),
                "risk": read_json(self.risk_path(program_id)),
                "exceptions": read_json(self.exception_path(program_id)),
                "gap_plan": read_json(self.gap_path(program_id)),
                "report": read_json(self.report_path(program_id)),
            }
        else:
            docs = self._build_documents(program_id, _read_optional_json(self.source_inputs_path(program_id)))
            self._write_docs(program_id, docs)
        state = self.latest_signoff_state(program_id)
        if state.get("status") == "signed":
            if not self.signoff_path(program_id).exists():
                raise UnifiedReleaseProgramStateError("Program signoff file is missing but history shows a signed state.")
            signoff = read_json(self.signoff_path(program_id))
            if not _integrity_ok(signoff) or signoff.get("status") != "signed":
                raise UnifiedReleaseProgramStateError("Program signoff integrity failed.")
            if state.get("signoff_hash") and state.get("signoff_hash") != signoff.get("integrity_hash"):
                raise UnifiedReleaseProgramStateError("Program signoff file does not match latest signed history state.")
            binding = self._read_signoff_binding(program_id, signoff)
            checks = {
                "program_report_hash": docs["report"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                "train_items_hash": docs["items"].get("integrity_hash"),
                "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                "risk_register_hash": docs["risk"].get("integrity_hash"),
                "exception_register_hash": docs["exceptions"].get("integrity_hash"),
                "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
            }
            for key, value in checks.items():
                if signoff.get(key) != value:
                    raise UnifiedReleaseProgramStateError("Program signed documents no longer match signoff.")
            docs["signoff"] = signoff
            docs["signoff_binding"] = binding
        return docs

    def _read_signoff_binding(self, program_id: str, signoff: DomainDocument) -> DomainDocument:
        path = self.signoff_binding_path(program_id)
        if not path.exists():
            raise UnifiedReleaseProgramStateError("Program signoff binding summary is missing.")
        binding = read_json(path)
        if not _integrity_ok(binding):
            raise UnifiedReleaseProgramStateError("Program signoff binding integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramStateError("Program signoff binding does not match current signoff.")
        return binding

    def _assert_export_current(self, program_id: str) -> None:
        manifest = read_json(self.manifest_path(program_id))
        docs = self._docs_for_export(program_id)
        expected_source = _manifest_source(docs)
        if manifest.get("source") != expected_source:
            raise UnifiedReleaseProgramStateError("Program export is stale. Rebuild export before ZIP.")

    def _append_history(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _signoff_binding_summary(self, program_id: str, signoff: DomainDocument, event: DomainDocument, docs: DomainDocument) -> DomainDocument:
        binding = sanitize_metadata(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_signoff_binding_summary",
                "program_id": program_id,
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "latest_history_event_hash": event.get("event_hash"),
                "history_event_payload_hash": event.get("payload_hash"),
                "program_report_hash": docs["report"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                "train_items_hash": docs["items"].get("integrity_hash"),
                "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                "risk_register_hash": docs["risk"].get("integrity_hash"),
                "exception_register_hash": docs["exceptions"].get("integrity_hash"),
                "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                "train_handoff_fingerprints": [
                    {
                        "item_id": row.get("item_id"),
                        "train_id": row.get("train_id"),
                        "handoff_id": row.get("handoff_id"),
                        **(_as_document(row.get("fingerprint"))),
                    }
                    for row in docs["items"].get("items", [])
                ],
            }
        )
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding

    def _exported_for_signoff(self, program_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "unified_release_program_exported" and event.get("signoff_hash") == signoff_hash for event in self.read_history(program_id))

    def _built_for_signoff(self, program_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "unified_release_program_zip_built" and event.get("signoff_hash") == signoff_hash for event in self.read_history(program_id))

    def _next_program_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.root.glob("urp-*/program.json"):
            try:
                max_seen = max(max_seen, int(path.parent.name.split("-")[-1]))
            except ValueError:
                continue
        return f"urp-{max_seen + 1:06d}"
