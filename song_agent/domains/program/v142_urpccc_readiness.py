# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import shutil as shutil
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity import UnifiedReleaseProgramContinuityStore as UnifiedReleaseProgramContinuityStore
from song_agent.domains.program.unified_release_program_continuity_acceptance import UnifiedReleaseProgramContinuityAcceptanceStore as UnifiedReleaseProgramContinuityAcceptanceStore, _file_record as _file_record, _gate_failed as _gate_failed, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _package_manifest as _package_manifest, _read_optional_json as _read_optional_json, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_acceptance_change import UnifiedReleaseProgramContinuityAcceptanceChangeStore as UnifiedReleaseProgramContinuityAcceptanceChangeStore
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import EXPECTED_VERIFICATION_TYPES as EXPECTED_VERIFICATION_TYPES, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, runtime_verify_continuity_command_center_component as runtime_verify_continuity_command_center_component, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package, write_unified_release_program_continuity_command_center_verification_report as write_unified_release_program_continuity_command_center_verification_report
from song_agent.domains.program.unified_release_program_continuity_distribution import UnifiedReleaseProgramContinuityDistributionStore as UnifiedReleaseProgramContinuityDistributionStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore as UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore as UnifiedReleaseProgramVaultOperationsStore

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

UnifiedReleaseProgramContinuityCommandCenterStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterStateError')
_evidence_status = _make_deferred_global('_evidence_status')
_runtime_blockers = _make_deferred_global('_runtime_blockers')
_runtime_fingerprint = _make_deferred_global('_runtime_fingerprint')
_sanitize_payload = _make_deferred_global('_sanitize_payload')
item = _make_deferred_global('item')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterStateError, _evidence_status, _runtime_blockers, _runtime_fingerprint, _sanitize_payload, item, read_json
    global write_json
    UnifiedReleaseProgramContinuityCommandCenterStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterStateError', UnifiedReleaseProgramContinuityCommandCenterStateError)
    _evidence_status = namespace.get('_evidence_status', _evidence_status)
    _runtime_blockers = namespace.get('_runtime_blockers', _runtime_blockers)
    _runtime_fingerprint = namespace.get('_runtime_fingerprint', _runtime_fingerprint)
    _sanitize_payload = namespace.get('_sanitize_payload', _sanitize_payload)
    item = namespace.get('item', item)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


COMMAND_CENTER_COMPONENTS = (
    "evidence_vault",
    "vault_operations",
    "continuity_recovery",
    "continuity_distribution_kit",
    "continuity_acceptance_board",
    "continuity_acceptance_change_control",
)




class UnifiedReleaseProgramContinuityCommandCenterStoreReadinessMixin:
    def command_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "continuity-command-center"

    def report_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "command-center-report.json"

    def inventory_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "evidence-inventory.json"

    def readiness_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "readiness-matrix.json"

    def runtime_index_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "runtime-verification-index.json"

    def gap_plan_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "gap-plan.json"

    def runbook_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "safe-runbook.json"

    def external_manifest_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "external-evidence-manifest.json"

    def local_evidence_manifest_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "external-evidence-manifest.local.json"

    def export_dir(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "command-center-export"

    def zip_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "unified-release-program-continuity-command-center.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.command_dir(program_id) / "command-center-verification-report.json"

    def refresh_command_center(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            contexts = self._runtime_contexts(program_id, payload)
            docs = self._build_documents(program_id, contexts)
            self.command_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.report_path(program_id), docs["report"])
            write_json(self.inventory_path(program_id), docs["inventory"])
            write_json(self.readiness_path(program_id), docs["readiness"])
            write_json(self.runtime_index_path(program_id), docs["runtime_index"])
            write_json(self.gap_plan_path(program_id), docs["gap_plan"])
            write_json(self.runbook_path(program_id), docs["runbook"])
            write_json(self.external_manifest_path(program_id), docs["external_manifest"])
            write_json(self.local_evidence_manifest_path(program_id), docs["local_evidence_manifest"])
            return docs["report"]

    def get_command_center(self, program_id: str) -> DomainDocument:
        return {
            "report": _read_optional_json(self.report_path(program_id)),
            "inventory": _read_optional_json(self.inventory_path(program_id)),
            "readiness": _read_optional_json(self.readiness_path(program_id)),
            "runtime_index": _read_optional_json(self.runtime_index_path(program_id)),
            "gap_plan": _read_optional_json(self.gap_plan_path(program_id)),
            "safe_runbook": _read_optional_json(self.runbook_path(program_id)),
            "external_evidence_manifest": _read_optional_json(self.external_manifest_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def run_safe(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            if not self.runbook_path(program_id).exists():
                self.refresh_command_center(program_id, payload)
            runbook = read_json(self.runbook_path(program_id))
            results = []
            for action in runbook.get("actions") or []:
                action_id = str(action.get("action_id") or "")
                action_type = str(action.get("action_type") or "")
                if action_type == "continuity_command_center.refresh":
                    self.refresh_command_center(program_id, payload)
                    results.append({"action_id": action_id, "status": "completed", "action_type": action_type})
                elif action_type == "continuity_command_center.export":
                    self.export_package(program_id, payload)
                    results.append({"action_id": action_id, "status": "completed", "action_type": action_type})
                elif action_type == "continuity_command_center.zip":
                    self.build_zip(program_id, payload)
                    results.append({"action_id": action_id, "status": "completed", "action_type": action_type})
                elif action_type == "continuity_command_center.verify":
                    self.verify_zip(program_id, payload)
                    results.append({"action_id": action_id, "status": "completed", "action_type": action_type})
                else:
                    results.append({"action_id": action_id, "status": "skipped_unsupported", "action_type": action_type})
            completed = sum(1 for row in results if row.get("status") == "completed")
            unsupported = sum(1 for row in results if row.get("status") == "skipped_unsupported")
            result_doc = {
                "schema_version": 1,
                "package_type": "musicforge_unified_release_program_continuity_command_center_runbook_result",
                "program_id": program_id,
                "status": "passed" if unsupported == 0 else "warning",
                "created_at": now_iso(),
                "results": results,
                "summary": {"completed_count": completed, "unsupported_count": unsupported, "result_count": len(results)},
            }
            result_doc["integrity_hash"] = _integrity_hash(result_doc)
            return result_doc

    def export_package(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            report = self.refresh_command_center(program_id, payload)
            if report.get("status") != "ready":
                raise UnifiedReleaseProgramContinuityCommandCenterStateError(
                    "Continuity Command Center runtime verification is not ready: "
                    + ", ".join(str(item) for item in (report.get("blockers") or [])[:8])
                )
            docs = self._read_docs(program_id)
            export_dir = self.export_dir(program_id)
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

            write_entry("README.txt", "MusicForge Unified Release Program Continuity Command Center\n")
            write_entry("command-center-report.json", docs["report"])
            write_entry("evidence-inventory.json", docs["inventory"])
            write_entry("readiness-matrix.json", docs["readiness"])
            write_entry("runtime-verification-index.json", docs["runtime_index"])
            write_entry("gap-plan.json", docs["gap_plan"])
            write_entry("safe-runbook.json", docs["runbook"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            manifest = _package_manifest(
                UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE,
                program_id,
                files,
                {
                    "command_center_report_hash": docs["report"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                    "runtime_verification_index_hash": docs["runtime_index"].get("integrity_hash"),
                    "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
                    "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "status": docs["report"].get("status"),
                    "current_generation": docs["report"].get("current_generation"),
                },
            )
            write_json(export_dir / "manifest.json", manifest)
            return manifest

    def build_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self.export_package(program_id, payload)
            export_dir = self.export_dir(program_id)
            zip_path = self.zip_path(program_id)
            if zip_path.exists():
                zip_path.unlink()
            entries = sorted(path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            return {
                "status": "passed",
                "program_id": program_id,
                "zip_path": str(zip_path),
                "zip_sha256": _sha256_path(zip_path),
                "zip_size_bytes": zip_path.stat().st_size,
                "manifest_hash": manifest.get("integrity_hash"),
            }

    def verify_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        report = verify_unified_release_program_continuity_command_center_package(
            payload.get("command_center_zip") or payload.get("zip_path") or self.zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_ready=bool(payload.get("require_ready", True)),
            evidence_manifest_path=payload.get("evidence_manifest") or payload.get("external_evidence_manifest") or self.local_evidence_manifest_path(program_id),
        )
        write_unified_release_program_continuity_command_center_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        command_center_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        evidence_manifest_path: Path | str | None = None,
        **payload: object,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(command_center_zip_path) if command_center_zip_path else self.zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        evidence_path = Path(evidence_manifest_path) if evidence_manifest_path else self.local_evidence_manifest_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Continuity Command Center ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Continuity Command Center verification report is missing.")
        if not evidence_path.exists():
            return _gate_failed("Continuity Command Center external evidence manifest is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_command_center_package(
                zip_path,
                strict=True,
                deep=True,
                require_ready=True,
                evidence_manifest_path=evidence_path,
            )
            if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE or not _integrity_ok(external):
                return _gate_failed("Continuity Command Center verification report integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Continuity Command Center runtime verification failed.", verification=runtime)
            if (
                external.get("zip_sha256") != runtime.get("zip_sha256")
                or int(external.get("zip_size_bytes") or -1) != zip_path.stat().st_size
                or external.get("manifest_hash") != runtime.get("manifest_hash")
            ):
                return _gate_failed("Continuity Command Center verification report does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _read_docs(self, program_id: str) -> DomainDocument:
        return {
            "report": read_json(self.report_path(program_id)),
            "inventory": read_json(self.inventory_path(program_id)),
            "readiness": read_json(self.readiness_path(program_id)),
            "runtime_index": read_json(self.runtime_index_path(program_id)),
            "gap_plan": read_json(self.gap_plan_path(program_id)),
            "runbook": read_json(self.runbook_path(program_id)),
            "external_manifest": read_json(self.external_manifest_path(program_id)),
            "local_evidence_manifest": read_json(self.local_evidence_manifest_path(program_id)),
        }

    def _runtime_contexts(self, program_id: str, payload: DomainDocument) -> list[DomainDocument]:
        components = self._component_specs(program_id)
        generation = _read_optional_json(self.change_store.current_generation_path(program_id))
        acceptance_state = self.acceptance_store.latest_signoff_state(program_id)
        runtime_rows: dict[str, DomainDocument] = {}
        for spec in components:
            runtime_row = {
                "component_type": spec["component_type"],
                "component_id": spec["component_id"],
                "package_path": str(spec["package_path"]),
                "verification_report_path": str(spec["verification_report_path"]),
            }
            if spec.get("signoff_binding_path"):
                runtime_row["signoff_binding_path"] = str(spec["signoff_binding_path"])
            if spec.get("anchor_path"):
                runtime_row["anchor_path"] = str(spec["anchor_path"])
            runtime_rows[f"{spec['component_type']}::{spec['component_id']}"] = runtime_row
        contexts: list[DomainDocument] = []
        for spec in components:
            contexts.append(self._component_context(program_id, spec, payload, generation, acceptance_state, runtime_rows))
        return contexts

    def _component_specs(self, program_id: str) -> list[DomainDocument]:
        return [
            {
                "component_type": "evidence_vault",
                "component_id": "v12.3-evidence-vault",
                "package_path": self.vault_store.zip_path(program_id),
                "verification_report_path": self.vault_store.verification_report_path(program_id),
                "anchor_path": self.vault_store.anchor_path(program_id),
            },
            {
                "component_type": "vault_operations",
                "component_id": "v12.4-vault-operations",
                "package_path": self.vault_operations_store.archive_zip_path(program_id),
                "verification_report_path": self.vault_operations_store.verification_report_path(program_id),
                "signoff_binding_path": self.vault_operations_store.signoff_binding_path(program_id),
            },
            {
                "component_type": "continuity_recovery",
                "component_id": "v12.5-continuity-recovery",
                "package_path": self.continuity_store.archive_zip_path(program_id),
                "verification_report_path": self.continuity_store.verification_report_path(program_id),
                "signoff_binding_path": self.continuity_store.signoff_binding_path(program_id),
            },
            {
                "component_type": "continuity_distribution_kit",
                "component_id": "v12.6-continuity-distribution-kit",
                "package_path": self.distribution_store.kit_zip_path(program_id),
                "verification_report_path": self.distribution_store.verification_report_path(program_id),
            },
            {
                "component_type": "continuity_acceptance_board",
                "component_id": "v12.7-continuity-acceptance-board",
                "package_path": self.acceptance_store.archive_zip_path(program_id),
                "verification_report_path": self.acceptance_store.verification_report_path(program_id),
                "signoff_binding_path": self.acceptance_store.signoff_binding_path(program_id),
            },
            {
                "component_type": "continuity_acceptance_change_control",
                "component_id": "v12.8-continuity-acceptance-change-control",
                "package_path": self.change_store.archive_zip_path(program_id),
                "verification_report_path": self.change_store.verification_report_path(program_id),
            },
        ]

    def _component_context(
        self,
        program_id: str,
        spec: DomainDocument,
        payload: DomainDocument,
        generation: DomainDocument,
        acceptance_state: DomainDocument,
        runtime_rows: dict[str, DomainDocument],
    ) -> DomainDocument:
        del payload
        component_type = spec["component_type"]
        package_path = Path(spec["package_path"])
        verification_path = Path(spec["verification_report_path"])
        blockers: list[str] = []
        warnings: list[str] = []
        runtime: DomainDocument = {"status": "missing", "blockers": ["package_missing"], "summary": {}}
        external_readable = True
        try:
            external = _read_optional_json(verification_path)
        except Exception as exc:
            external = {}
            external_readable = False
            blockers.append(f"{component_type}_verification_projection_invalid")
            warnings.append(sanitize_sensitive_text(str(exc)))
        package_exists = package_path.exists() and package_path.is_file()
        verification_exists = verification_path.exists() and verification_path.is_file()
        package_sha = _sha256_path(package_path)
        package_size = package_path.stat().st_size if package_exists else None
        expected_package_type = EXPECTED_VERIFICATION_TYPES.get(component_type)
        if not package_exists:
            blockers.append(f"{component_type}_package_missing")
        if not verification_exists:
            blockers.append(f"{component_type}_verification_missing")
        if verification_exists and external_readable and external.get("package_type") != expected_package_type:
            blockers.append(f"{component_type}_wrong_package_type")
        if verification_exists and external_readable and not _integrity_ok(external):
            blockers.append(f"{component_type}_verification_integrity")
        if verification_exists and external_readable and external.get("status") != "passed":
            blockers.append(f"{component_type}_verification_failed")
        try:
            if package_exists:
                runtime_key = f"{component_type}::{spec['component_id']}"
                runtime = runtime_verify_continuity_command_center_component(component_type, runtime_rows[runtime_key], runtime_rows)
                if runtime.get("status") != "passed":
                    blockers.append(f"{component_type}_runtime_failed")
                runtime_fingerprint = _runtime_fingerprint(runtime)
                if external.get("zip_sha256") != package_sha:
                    blockers.append(f"{component_type}_verification_zip_sha256")
                if int(external.get("zip_size_bytes") or -1) != int(package_size or -2):
                    blockers.append(f"{component_type}_verification_zip_size_bytes")
                if external.get("manifest_hash") != runtime_fingerprint.get("manifest_hash"):
                    blockers.append(f"{component_type}_verification_manifest_hash")
        except Exception as exc:
            runtime = {"status": "failed", "blockers": [sanitize_sensitive_text(str(exc))], "summary": {}}
            blockers.append(f"{component_type}_runtime_exception")
        runtime_fingerprint = _runtime_fingerprint(runtime)
        runtime_blockers = _runtime_blockers(runtime)
        reset_pending = acceptance_state.get("status") != "signed"
        if reset_pending and component_type in {"continuity_acceptance_board", "continuity_acceptance_change_control"}:
            blockers.append(f"{component_type}_reset_pending")
        evidence_status = _evidence_status(blockers)
        status = "passed" if evidence_status == "ready" else "failed"
        generation_number = generation.get("generation")
        row = {
            "component_type": component_type,
            "component_id": spec["component_id"],
            "status": status,
            "evidence_status": evidence_status,
            "runtime_status": runtime.get("status"),
            "runtime_blockers": runtime_blockers,
            "report_status": external.get("status") or "missing",
            "external_status": external.get("status") or "missing",
            "zip_sha256": package_sha,
            "zip_size_bytes": package_size,
            "package_sha256": package_sha,
            "package_size_bytes": package_size,
            "manifest_hash": runtime_fingerprint.get("manifest_hash") or external.get("manifest_hash"),
            "verification_report_hash": external.get("integrity_hash"),
            "verification_package_type": external.get("package_type"),
            "generation": generation_number,
            "current": evidence_status == "ready" and not reset_pending,
            "blockers": blockers,
            "warnings": warnings,
        }
        for optional in ("signoff_binding_path", "anchor_path"):
            path_value = spec.get(optional)
            if path_value:
                row[optional.replace("_path", "_hash")] = _sha256_path(path_value) or (_read_optional_json(Path(path_value)).get("integrity_hash"))
        local_row = dict(row)
        local_row.update(runtime_rows[f"{component_type}::{spec['component_id']}"])
        return {"row": row, "local_row": local_row, "runtime": runtime, "external": external}
