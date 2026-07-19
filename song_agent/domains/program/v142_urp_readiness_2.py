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

UnifiedReleaseProgramNotFoundError = _make_deferred_global('UnifiedReleaseProgramNotFoundError')
UnifiedReleaseProgramStateError = _make_deferred_global('UnifiedReleaseProgramStateError')
_bounded = _make_deferred_global('_bounded')
_file_index = _make_deferred_global('_file_index')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest_document = _make_deferred_global('_manifest_document')
_merge_inputs = _make_deferred_global('_merge_inputs')
_policy = _make_deferred_global('_policy')
_read_optional_json = _make_deferred_global('_read_optional_json')
_recipient_guide = _make_deferred_global('_recipient_guide')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_source_inputs = _make_deferred_global('_source_inputs')
info = _make_deferred_global('info')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramNotFoundError, UnifiedReleaseProgramStateError, _bounded, _file_index, _file_record, _gate_failed, _history_text, _integrity_hash
    global _integrity_ok, _manifest_document, _merge_inputs, _policy, _read_optional_json, _recipient_guide, _safe_id
    global _sha256_path, _source_inputs, info, read_json, write_json
    UnifiedReleaseProgramNotFoundError = namespace.get('UnifiedReleaseProgramNotFoundError', UnifiedReleaseProgramNotFoundError)
    UnifiedReleaseProgramStateError = namespace.get('UnifiedReleaseProgramStateError', UnifiedReleaseProgramStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _file_index = namespace.get('_file_index', _file_index)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest_document = namespace.get('_manifest_document', _manifest_document)
    _merge_inputs = namespace.get('_merge_inputs', _merge_inputs)
    _policy = namespace.get('_policy', _policy)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _recipient_guide = namespace.get('_recipient_guide', _recipient_guide)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _source_inputs = namespace.get('_source_inputs', _source_inputs)
    info = namespace.get('info', info)
    read_json = namespace.get('read_json', read_json)
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




class UnifiedReleaseProgramStoreReadinessMixin:
    def program_dir(self, program_id: str) -> Path:
        return self.root / _safe_id(program_id)

    def program_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program.json"

    def source_inputs_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "source-inputs.json"

    def items_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "train-items.json"

    def external_manifest_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "external-evidence-manifest.json"

    def dependency_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "dependency-graph.json"

    def readiness_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "readiness-matrix.json"

    def risk_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "risk-register.json"

    def exception_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "exception-register.json"

    def gap_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "gap-plan.json"

    def report_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-report.json"

    def history_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-history.jsonl"

    def signoff_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-signoff-binding-summary.json"

    def export_dir(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "export"

    def manifest_path(self, program_id: str) -> Path:
        return self.export_dir(program_id) / "manifest.json"

    def zip_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "unified-release-program.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "unified-release-program-verification-report.json"

    def create_program(self, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            program_id = _safe_id(str(payload.get("program_id") or self._next_program_id()))
            if self.program_path(program_id).exists():
                raise UnifiedReleaseProgramStateError(f"Unified Release Program already exists: {program_id}")
            now = now_iso()
            program = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_record",
                    "program_id": program_id,
                    "name": _bounded(payload.get("name") or "Unified Release Program", 200),
                    "status": "draft",
                    "created_at": now,
                    "updated_at": now,
                    "policy": _policy(payload.get("policy")),
                    "summary": {},
                }
            )
            program["integrity_hash"] = _integrity_hash(program)
            self.program_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.program_path(program_id), program)
            self._write_items(program_id, [])
            self._write_exception_register(program_id, [])
            if payload.get("items"):
                for item in payload.get("items") or []:
                    self.add_train_item(program_id, dict(item))
            return self.read_program(program_id)

    def list_programs(self) -> list[DomainDocument]:
        if not self.root.exists():
            return []
        rows = []
        for path in sorted(self.root.glob("urp-*")):
            program_path = path / "program.json"
            if program_path.exists():
                rows.append(read_json(program_path))
        return rows

    def read_program(self, program_id: str) -> DomainDocument:
        if not self.program_path(program_id).exists():
            raise UnifiedReleaseProgramNotFoundError(f"Unified Release Program not found: {program_id}")
        return read_json(self.program_path(program_id))

    def get_program(self, program_id: str) -> DomainDocument:
        return {
            "program": self.read_program(program_id),
            "items": _read_optional_json(self.items_path(program_id)),
            "external_evidence_manifest": _read_optional_json(self.external_manifest_path(program_id)),
            "dependency_graph": _read_optional_json(self.dependency_path(program_id)),
            "readiness_matrix": _read_optional_json(self.readiness_path(program_id)),
            "risk_register": _read_optional_json(self.risk_path(program_id)),
            "exception_register": _read_optional_json(self.exception_path(program_id)),
            "gap_plan": _read_optional_json(self.gap_path(program_id)),
            "report": _read_optional_json(self.report_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def add_train_item(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            self.ensure_unsigned(program_id)
            program = self.read_program(program_id)
            items_doc = self._read_items(program_id)
            rows = list(items_doc.get("items") or [])
            item_id = _safe_id(str(payload.get("item_id") or f"train-{len(rows) + 1:03d}"))
            train_id = _safe_id(str(payload.get("train_id") or ""))
            handoff_id = _safe_id(str(payload.get("handoff_id") or ""))
            if not train_id or not handoff_id:
                raise UnifiedReleaseProgramStateError("train_id and handoff_id are required.")
            if any(row.get("item_id") == item_id for row in rows):
                raise UnifiedReleaseProgramStateError(f"Duplicate Program item_id: {item_id}")
            if not bool(payload.get("allow_duplicate_train")) and any(row.get("train_id") == train_id and row.get("handoff_id") == handoff_id for row in rows):
                raise UnifiedReleaseProgramStateError("Duplicate train_id + handoff_id requires allow_duplicate_train=true.")
            item_type = str(payload.get("type") or payload.get("item_type") or "required")
            if item_type not in {"required", "optional", "advisory", "deferred"}:
                raise UnifiedReleaseProgramStateError("Program item type must be required, optional, advisory, or deferred.")
            external = _as_document(payload.get("external_evidence"))
            row = sanitize_metadata(
                {
                    "item_id": item_id,
                    "train_id": train_id,
                    "handoff_id": handoff_id,
                    "label": _bounded(payload.get("label") or train_id, 200),
                    "type": item_type,
                    "lane": _bounded(payload.get("lane") or "release", 80),
                    "wave": _bounded(payload.get("wave") or f"wave-{len(rows) + 1}", 80),
                    "depends_on": [_safe_id(str(item)) for item in payload.get("depends_on", []) if str(item)],
                    "expected_status": _bounded(payload.get("expected_status") or "signed", 80),
                    "defer_reason": _bounded(payload.get("defer_reason") or "", 500),
                    "external_evidence": {
                        "handoff_zip": str(payload.get("handoff_zip") or external.get("handoff_zip") or external.get("handoff_zip_path") or ""),
                        "handoff_verification_report": str(payload.get("handoff_verification_report") or external.get("handoff_verification_report") or external.get("handoff_verification_report_path") or ""),
                        "handoff_signoff_binding": str(payload.get("handoff_signoff_binding") or external.get("handoff_signoff_binding") or external.get("handoff_signoff_binding_path") or ""),
                        "accepted_evidence_dir": str(payload.get("accepted_evidence_dir") or external.get("accepted_evidence_dir") or ""),
                    },
                    "status": "pending",
                }
            )
            rows.append(row)
            self._write_items(program_id, rows)
            program["updated_at"] = now_iso()
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_path(program_id), program)
            return row

    def remove_train_item(self, program_id: str, item_id: str) -> DomainDocument:
        with self.lock:
            self.ensure_unsigned(program_id)
            rows = [row for row in self._read_items(program_id).get("items", []) if row.get("item_id") != item_id]
            self._write_items(program_id, rows)
            return self._read_items(program_id)

    def approve_exception(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            self.ensure_unsigned(program_id)
            register = self._read_exceptions(program_id)
            rows = list(register.get("exceptions") or [])
            exception = sanitize_metadata(
                {
                    "exception_id": _safe_id(str(payload.get("exception_id") or f"ex-{len(rows) + 1:06d}")),
                    "item_id": _safe_id(str(payload.get("item_id") or "")),
                    "type": _bounded(payload.get("type") or "waive_warning", 80),
                    "severity": _bounded(payload.get("severity") or "medium", 80),
                    "reason": _bounded(payload.get("reason") or "", 1000),
                    "approved_by": _bounded(payload.get("approved_by") or "program-owner", 120),
                    "created_at": now_iso(),
                    "status": "approved",
                }
            )
            exception["integrity_hash"] = _integrity_hash(exception)
            rows.append(exception)
            self._write_exception_register(program_id, rows)
            return exception

    def refresh_report(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            inputs = _merge_inputs(_read_optional_json(self.source_inputs_path(program_id)), _source_inputs(payload))
            docs = self._build_documents(program_id, inputs)
            self._write_docs(program_id, docs)
            write_json(self.source_inputs_path(program_id), inputs)
            program = docs["program"]
            program["status"] = "ready" if docs["report"].get("status") == "ready" else "blocked"
            program["summary"] = docs["report"].get("summary", {})
            program["source_hash"] = docs["report"].get("source_hash")
            program["updated_at"] = now_iso()
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_path(program_id), program)
            return docs["report"]

    def signoff(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._build_documents(program_id, _merge_inputs(_read_optional_json(self.source_inputs_path(program_id)), _source_inputs(payload)))
            if docs["report"].get("status") != "ready":
                self._write_docs(program_id, docs)
                raise UnifiedReleaseProgramStateError("Unified Release Program must be ready before signoff.")
            role = _bounded(payload.get("role") or "release_owner", 80)
            required_roles = set(docs["program"].get("policy", {}).get("required_program_roles") or ["release_owner"])
            if role not in required_roles:
                raise UnifiedReleaseProgramStateError("Program signer role is not allowed by policy.")
            self._write_docs(program_id, docs)
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_signoff",
                    "program_id": program_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "program-owner", 120),
                    "role": role,
                    "reason": _bounded(payload.get("reason") or "Unified Release Program approved for final delivery.", 1000),
                    "signed_at": now,
                    "source_hash": docs["report"].get("source_hash"),
                    "program_report_hash": docs["report"].get("integrity_hash"),
                    "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                    "train_items_hash": docs["items"].get("integrity_hash"),
                    "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                    "risk_register_hash": docs["risk"].get("integrity_hash"),
                    "exception_register_hash": docs["exceptions"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "tool": {"name": "MusicForge Unified Release Program Signoff", "version": __version__},
                }
            )
            signoff = SignoffService.seal(signoff)
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "unified_release_program_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": signoff.get("source_hash"),
                    "program_report_hash": signoff.get("program_report_hash"),
                },
            )
            write_json(self.signoff_binding_path(program_id), self._signoff_binding_summary(program_id, signoff, event, docs))
            program = docs["program"]
            program["status"] = "signed"
            program["signed_at"] = now
            program["signoff_hash"] = signoff.get("integrity_hash")
            program["updated_at"] = now
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_path(program_id), program)
            return signoff

    def export_program(self, program_id: str) -> DomainDocument:
        with self.lock:
            docs = self._docs_for_export(program_id)
            export_dir = self.export_dir(program_id)
            if docs.get("signoff"):
                signoff_hash = str(docs["signoff"].get("integrity_hash") or "")
                if self._exported_for_signoff(program_id, signoff_hash):
                    if self.manifest_path(program_id).exists():
                        return read_json(self.manifest_path(program_id))
                    raise UnifiedReleaseProgramStateError("Program export was already created for this signoff. Create a new Program for changes.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_entry(rel: str, payload_doc: DomainDocument | str) -> None:
                path = export_dir / rel
                if isinstance(payload_doc, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload_doc, encoding="utf-8")
                else:
                    write_json(path, payload_doc)
                files.append(_file_record(path, rel))

            write_entry("program-report.json", docs["report"])
            write_entry("train-items.json", docs["items"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            write_entry("dependency-graph.json", docs["dependency"])
            write_entry("readiness-matrix.json", docs["readiness"])
            write_entry("risk-register.json", docs["risk"])
            write_entry("exception-register.json", docs["exceptions"])
            write_entry("gap-plan.json", docs["gap_plan"])
            write_entry("recipient-guide.md", _recipient_guide(docs))
            write_entry("program-history.jsonl", _history_text(self.read_history(program_id)))
            if docs.get("signoff"):
                write_entry("program-signoff.json", docs["signoff"])
                write_entry("program-signoff-binding-summary.json", docs["signoff_binding"])
            write_entry("README.txt", "MusicForge Unified Release Program Board\n")
            file_index = _file_index(program_id, files)
            write_entry("file-index.json", file_index)
            manifest = _manifest_document(program_id, docs, files, file_index)
            write_json(self.manifest_path(program_id), manifest)
            if docs.get("signoff"):
                self._append_history(program_id, {"event_type": "unified_release_program_exported", "created_at": now_iso(), "program_id": program_id, "signoff_hash": docs["signoff"].get("integrity_hash"), "program_manifest_hash": manifest.get("integrity_hash")})
            return manifest

    def build_zip(self, program_id: str) -> DomainDocument:
        with self.lock:
            docs = self._docs_for_export(program_id)
            if docs.get("signoff"):
                signoff_hash = str(docs["signoff"].get("integrity_hash") or "")
                if self._built_for_signoff(program_id, signoff_hash):
                    raise UnifiedReleaseProgramStateError("Program ZIP already exists for this signoff. Create a new Program for changes.")
            if not self.manifest_path(program_id).exists():
                self.export_program(program_id)
            else:
                self._assert_export_current(program_id)
            export_dir = self.export_dir(program_id)
            zip_path = self.zip_path(program_id)
            if zip_path.exists():
                zip_path.unlink()
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            zip_path.unlink(missing_ok=True)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            final_sha = _sha256_path(zip_path)
            if docs.get("signoff"):
                self._append_history(program_id, {"event_type": "unified_release_program_zip_built", "created_at": now_iso(), "program_id": program_id, "signoff_hash": docs["signoff"].get("integrity_hash"), "program_zip_sha256": final_sha, "program_manifest_hash": manifest.get("integrity_hash")})
            return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest}

    def verify_package(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_release_program_package(
            self.zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_signed=bool(payload.get("require_signed", False)),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.external_manifest_path(program_id),
            program_signoff_binding_path=payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        *,
        required: bool = True,
        program_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        external_evidence_manifest_path: Path | str | None = None,
        program_signoff_binding_path: Path | str | None = None,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(program_zip_path) if program_zip_path else None
        verification_path = Path(verification_report_path) if verification_report_path else None
        if not zip_path or not zip_path.exists():
            return _gate_failed("Unified Release Program ZIP is missing.")
        if not verification_path or not verification_path.exists():
            return _gate_failed("Unified Release Program verification report is missing.")
        try:
            external = read_json(verification_path)
            runtime = verify_unified_release_program_package(
                zip_path,
                strict=True,
                require_current=True,
                require_signed=True,
                external_evidence_manifest_path=external_evidence_manifest_path,
                program_signoff_binding_path=program_signoff_binding_path,
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program gate passed.", "program_zip_sha256": runtime.get("zip_sha256"), "verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, program_id: str) -> None:
        state = self.latest_signoff_state(program_id)
        if state.get("status") == "signed":
            raise UnifiedReleaseProgramStateError("Unified Release Program is signed. Create a new Program for changes.")

    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        latest: DomainDocument | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "unified_release_program_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "unified_release_program_signoff_reset":
                previous_hash = event.get("previous_signoff_hash")
                if latest and (not previous_hash or latest.get("signoff_hash") == previous_hash):
                    latest = {"status": "reset", "previous_signoff_hash": previous_hash, "event": event}
        if latest:
            return latest
        if self.signoff_path(program_id).exists():
            signoff = read_json(self.signoff_path(program_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_history(self, program_id: str) -> list[DomainDocument]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()
