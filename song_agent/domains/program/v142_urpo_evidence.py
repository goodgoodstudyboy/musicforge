# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, HistoryChain as HistoryChain, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package, write_unified_release_program_operations_verification_report as write_unified_release_program_operations_verification_report
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

UnifiedReleaseProgramOperationsStateError = _make_deferred_global('UnifiedReleaseProgramOperationsStateError')
_archive_source = _make_deferred_global('_archive_source')
_check = _make_deferred_global('_check')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
field = _make_deferred_global('field')
info = _make_deferred_global('info')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramOperationsStateError, _archive_source, _check, _file_record, _gate_failed, _integrity_hash, _integrity_ok
    global _sha256_path, _with_integrity, field, info, read_json, row, write_json
    UnifiedReleaseProgramOperationsStateError = namespace.get('UnifiedReleaseProgramOperationsStateError', UnifiedReleaseProgramOperationsStateError)
    _archive_source = namespace.get('_archive_source', _archive_source)
    _check = namespace.get('_check', _check)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    field = namespace.get('field', field)
    info = namespace.get('info', info)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)






class UnifiedReleaseProgramOperationsStoreEvidenceMixin:
    def build_operations_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        self.export_operations_archive(program_id, payload or {})
        archive_dir = self.archive_dir(program_id)
        zip_path = self.archive_zip_path(program_id)
        if zip_path.exists():
            zip_path.unlink()
        ArchiveBuilder.build_directory_zip(archive_dir, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            entries = sorted(info.filename for info in archive.infolist())
        manifest = read_json(self.archive_manifest_path(program_id))
        manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
        manifest["files"] = [_file_record(path, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(self.archive_manifest_path(program_id), manifest)
        zip_path.unlink(missing_ok=True)
        ArchiveBuilder.build_directory_zip(archive_dir, zip_path)
        return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_operations_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_release_program_operations_package(
            self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_signed_program=bool(payload.get("require_signed_program", True)),
            require_continuous_review_clear=bool(payload.get("require_continuous_review_clear", True)),
            require_lifecycle_audit=bool(payload.get("require_lifecycle_audit", True)),
            program_zip_path=payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id),
            program_verification_report_path=payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id),
            program_signoff_binding_path=payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id),
        )
        write_unified_release_program_operations_verification_report(report, self.archive_verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, operations_archive_zip_path: Path | str | None = None, operations_archive_verification_report_path: Path | str | None = None, **payload: object) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        if self.program_store.latest_signoff_state(program_id).get("status") != "signed":
            return _gate_failed("Unified Release Program is not currently signed.")
        zip_path = Path(operations_archive_zip_path) if operations_archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(operations_archive_verification_report_path) if operations_archive_verification_report_path else self.archive_verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Operations Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Operations Archive verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_operations_package(
                zip_path,
                strict=True,
                require_current=True,
                require_signed_program=True,
                require_continuous_review_clear=True,
                require_lifecycle_audit=True,
                program_zip_path=payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id),
                program_verification_report_path=payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id),
                program_signoff_binding_path=payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id),
                external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program Operations verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program Operations verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program Operations verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program Operations gate passed.", "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def read_change_history(self, program_id: str) -> list[DomainDocument]:
        return HistoryChain(self.change_history_path(program_id), sanitizer=sanitize_metadata).read()

    def _current_program_binding(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        if self.program_store.latest_signoff_state(program_id).get("status") != "signed":
            raise UnifiedReleaseProgramOperationsStateError("Unified Release Program must be currently signed.")
        program_zip = Path(payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id))
        verification_path = Path(payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id))
        binding_path = Path(payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id))
        external_manifest_path = Path(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id))
        runtime = verify_unified_release_program_package(program_zip, strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=external_manifest_path, program_signoff_binding_path=binding_path)
        verification = read_json(verification_path) if verification_path.exists() else {}
        if verification.get("package_type") != UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE:
            raise UnifiedReleaseProgramOperationsStateError("Current Program verification report package type is invalid.")
        if runtime.get("status") != "passed" or verification.get("status") != "passed":
            raise UnifiedReleaseProgramOperationsStateError("Current Program verification must be passed.")
        if verification.get("zip_sha256") != runtime.get("zip_sha256") or verification.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramOperationsStateError("Current Program verification report is stale.")
        signoff = read_json(self.program_store.signoff_path(program_id))
        binding = read_json(binding_path)
        external_manifest = read_json(external_manifest_path)
        return sanitize_metadata(
            {
                "program_id": program_id,
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "signoff_binding_hash": binding.get("integrity_hash"),
                "program_zip_sha256": _sha256_path(program_zip),
                "program_zip_size_bytes": program_zip.stat().st_size if program_zip.exists() else 0,
                "program_manifest_hash": runtime.get("manifest_hash"),
                "verification_report_hash": _integrity_hash(verification),
                "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
                "source_hash": signoff.get("source_hash"),
            }
        )

    def _program_binding_best_effort(self, program_id: str) -> DomainDocument:
        try:
            return self._current_program_binding(program_id, {})
        except Exception:
            state = self.program_store.latest_signoff_state(program_id)
            return {"program_id": program_id, "signoff_state": state.get("status"), "signoff_hash": state.get("signoff_hash")}

    def _current_program_state(self, program_id: str, payload: DomainDocument, *, require: bool) -> DomainDocument:
        checks: list[DomainDocument] = []
        state: DomainDocument = {"checks": checks}
        if not require:
            return state
        latest = self.program_store.latest_signoff_state(program_id)
        checks.append(_check("program_currently_signed", latest.get("status") == "signed", "Program is currently signed.", {"status": latest.get("status")}))
        if latest.get("status") != "signed":
            return state
        paths = {
            "program_zip": Path(payload.get("program_zip") or payload.get("program_zip_path") or self.program_store.zip_path(program_id)),
            "program_verification_report": Path(payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id)),
            "program_signoff_binding": Path(payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id)),
            "external_evidence_manifest": Path(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id)),
        }
        for key, path in paths.items():
            checks.append(_check(f"program_{key}_exists", path.exists(), f"{key} exists.", {"path": str(path)}))
        if any(row.get("status") == "failed" for row in checks):
            return state
        external = read_json(paths["program_verification_report"])
        binding = read_json(paths["program_signoff_binding"])
        evidence_manifest = read_json(paths["external_evidence_manifest"])
        runtime = verify_unified_release_program_package(paths["program_zip"], strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=paths["external_evidence_manifest"], program_signoff_binding_path=paths["program_signoff_binding"])
        checks.extend(
            [
                _check("program_runtime_verification_passed", runtime.get("status") == "passed", "Program runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
                _check("program_external_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, "Program external verification report package type is valid."),
                _check("program_external_verification_passed", external.get("status") == "passed" and _integrity_ok(external), "Program external verification report passed."),
                _check("program_zip_sha256_current", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(paths["program_zip"]), "Program ZIP hash matches runtime and report."),
                _check("program_manifest_hash_current", external.get("manifest_hash") == runtime.get("manifest_hash"), "Program manifest hash matches runtime and report."),
                _check("program_signoff_binding_integrity", _integrity_ok(binding), "Program signoff binding integrity is valid."),
                _check("program_external_manifest_integrity", _integrity_ok(evidence_manifest), "Program external evidence manifest integrity is valid."),
            ]
        )
        state.update({"program_zip_sha256": _sha256_path(paths["program_zip"]), "program_zip_size_bytes": paths["program_zip"].stat().st_size, "program_manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "verification_status": external.get("status"), "runtime_status": runtime.get("status"), "signoff_binding_hash": binding.get("integrity_hash"), "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash")})
        return sanitize_metadata(state)

    def _assert_request_current(self, program_id: str, request: DomainDocument, payload: DomainDocument) -> None:
        current = self._current_program_binding(program_id, payload)
        expected = _as_document(request.get("source"))
        fields = ("signoff_hash", "signoff_binding_hash", "program_zip_sha256", "program_manifest_hash", "verification_report_hash", "external_evidence_manifest_hash", "source_hash")
        mismatched = [field for field in fields if current.get(field) != expected.get(field)]
        if mismatched:
            raise UnifiedReleaseProgramOperationsStateError(f"Program Change Request binding is stale: {', '.join(mismatched)}")

    def _archive_documents(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        current = self._current_program_state(program_id, payload, require=True)
        failures = [row for row in current.get("checks", []) if row.get("status") == "failed"]
        if failures:
            raise UnifiedReleaseProgramOperationsStateError("Current Program evidence failed verification.")
        program = self.program_store.read_program(program_id)
        verification = read_json(Path(payload.get("program_verification_report") or payload.get("program_verification_report_path") or self.program_store.verification_report_path(program_id)))
        signoff = read_json(self.program_store.signoff_path(program_id))
        binding = read_json(Path(payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.program_store.signoff_binding_path(program_id)))
        external_manifest = read_json(Path(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.program_store.external_manifest_path(program_id)))
        review = self.refresh_continuous_review(program_id, payload)
        lifecycle = self.refresh_lifecycle_audit(program_id, payload)
        change_control = self.refresh_change_control_report(program_id)
        program_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_program_summary", "program_id": program_id, "status": program.get("status"), "program_zip_sha256": current.get("program_zip_sha256"), "program_manifest_hash": current.get("program_manifest_hash"), "signoff_hash": signoff.get("integrity_hash")})
        verification_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_program_verification_summary", "program_id": program_id, "verification_status": verification.get("status"), "verification_report_hash": _integrity_hash(verification), "zip_sha256": verification.get("zip_sha256"), "manifest_hash": verification.get("manifest_hash")})
        signoff_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_signoff_summary", "program_id": program_id, "status": signoff.get("status"), "signed_by": signoff.get("signed_by"), "role": signoff.get("role"), "signed_at": signoff.get("signed_at"), "signoff_hash": signoff.get("integrity_hash"), "signoff_binding_hash": binding.get("integrity_hash")})
        external_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_external_evidence_manifest_summary", "program_id": program_id, "external_manifest_hash": external_manifest.get("integrity_hash"), "item_count": len(external_manifest.get("items", []))})
        evidence = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_operations_evidence_index", "program_id": program_id, "items": [{"evidence_type": "program", **current}, {"evidence_type": "continuous_review", "status": review.get("status"), "review_hash": review.get("integrity_hash")}, {"evidence_type": "lifecycle_audit", "status": lifecycle.get("status"), "lifecycle_hash": lifecycle.get("integrity_hash")}], "summary": {"item_count": 3}})
        return {"program": program_summary, "program_verification": verification_summary, "signoff": signoff_summary, "binding": binding, "external_manifest": external_summary, "change_control": change_control, "review": review, "lifecycle": lifecycle, "evidence": evidence}

    def _assert_archive_current(self, program_id: str, payload: DomainDocument) -> None:
        manifest = read_json(self.archive_manifest_path(program_id))
        docs = self._archive_documents(program_id, payload)
        expected_source = _archive_source(docs)
        if manifest.get("source") != expected_source:
            raise UnifiedReleaseProgramOperationsStateError("Program Operations Archive export is stale. Re-export before ZIP.")

    def _request_summary(self, program_id: str, request: DomainDocument) -> DomainDocument:
        request_id = str(request.get("change_request_id") or "")
        approval = read_json(self.approval_path(program_id, request_id)) if self.approval_path(program_id, request_id).exists() else {}
        reset = read_json(self.reset_proof_path(program_id, request_id)) if self.reset_proof_path(program_id, request_id).exists() else {}
        return sanitize_metadata({"change_request_id": request_id, "status": request.get("status"), "change_type": request.get("change_type"), "reason": request.get("reason"), "request_hash": request.get("integrity_hash"), "approval_hash": approval.get("integrity_hash") or request.get("approval_hash"), "reset_proof_hash": reset.get("integrity_hash") or request.get("reset_proof_hash"), "reset_event_hash": request.get("reset_event_hash"), "previous_signoff_hash": (request.get("target") or {}).get("program_signoff_hash")})

    def _append_change_history(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.change_history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _lifecycle_ledger(self, program_id: str, program_history: list[DomainDocument], change_history: list[DomainDocument]) -> list[DomainDocument]:
        rows = []
        previous = ""
        source_rows = [("program_history", row) for row in program_history] + [("change_control_history", row) for row in change_history]
        for index, (source, raw) in enumerate(source_rows, start=1):
            event = HistoryChain.build_event(
                {"event_id": f"uple-{index:06d}", "source": source, "event_type": raw.get("event_type"), "created_at": raw.get("created_at"), "program_id": program_id, "signoff_hash": raw.get("signoff_hash") or raw.get("previous_signoff_hash"), "change_request_id": raw.get("change_request_id"), "source_event_hash": raw.get("event_hash")},
                previous_event_hash=previous,
                sanitizer=sanitize_metadata,
            )
            previous = event["event_hash"]
            rows.append(event)
        return rows

    def _next_request_id(self, program_id: str) -> str:
        base = self.change_dir(program_id) / "change-requests"
        base.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in base.glob("urpcr-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"urpcr-{max_seen + 1:06d}"

    def _next_runbook_id(self, program_id: str) -> str:
        base = self.ops_dir(program_id) / "runbooks"
        base.mkdir(parents=True, exist_ok=True)
        return f"urprb-{len([path for path in base.glob('urprb-*')]) + 1:06d}"

    def _next_review_id(self, program_id: str) -> str:
        base = self.ops_dir(program_id) / "continuous-reviews"
        base.mkdir(parents=True, exist_ok=True)
        return f"urpcrv-{len([path for path in base.glob('urpcrv-*')]) + 1:06d}"
