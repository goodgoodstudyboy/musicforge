# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import shutil as shutil
import tempfile as tempfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION, verify_unified_release_program_continuity_package as verify_unified_release_program_continuity_package, write_unified_release_program_continuity_verification_report as write_unified_release_program_continuity_verification_report
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore as UnifiedReleaseProgramVaultOperationsStore
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package

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

UnifiedReleaseProgramContinuityStateError = _make_deferred_global('UnifiedReleaseProgramContinuityStateError')
_archive_manifest_document = _make_deferred_global('_archive_manifest_document')
_integrity_ok = _make_deferred_global('_integrity_ok')
_read_history = _make_deferred_global('_read_history')
_read_optional_json = _make_deferred_global('_read_optional_json')
_read_required_doc = _make_deferred_global('_read_required_doc')
_sha256_path = _make_deferred_global('_sha256_path')
_source_binding_from_context = _make_deferred_global('_source_binding_from_context')
_with_integrity = _make_deferred_global('_with_integrity')
item = _make_deferred_global('item')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityStateError, _archive_manifest_document, _integrity_ok, _read_history, _read_optional_json, _read_required_doc, _sha256_path
    global _source_binding_from_context, _with_integrity, item, read_json, row, write_json
    UnifiedReleaseProgramContinuityStateError = namespace.get('UnifiedReleaseProgramContinuityStateError', UnifiedReleaseProgramContinuityStateError)
    _archive_manifest_document = namespace.get('_archive_manifest_document', _archive_manifest_document)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _read_history = namespace.get('_read_history', _read_history)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _read_required_doc = namespace.get('_read_required_doc', _read_required_doc)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _source_binding_from_context = namespace.get('_source_binding_from_context', _source_binding_from_context)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    item = namespace.get('item', item)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


CONTINUITY_BLOCKED_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}




class UnifiedReleaseProgramContinuityStoreEvidenceMixin:
    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        events = _read_history(self.history_path(program_id))
        signoffs = [row for row in events if row.get("event_type") == "continuity_signoff_created"]
        if not signoffs:
            return {"status": "unsigned", "signed": False}
        latest = signoffs[-1]
        return {"status": "signed", "signed": True, "signoff_hash": latest.get("signoff_hash"), "event_hash": latest.get("event_hash"), "event_index": latest.get("event_index")}

    def _ensure_unsigned(self, program_id: str) -> None:
        if self.latest_signoff_state(program_id).get("signed"):
            raise UnifiedReleaseProgramContinuityStateError("Unified Release Program Continuity is signed. Create a successor continuity record before mutation.")

    def _evidence_paths(self, program_id: str, payload: DomainDocument) -> dict[str, Path]:
        local = _read_optional_json(self.local_evidence_manifest_path(program_id))
        return {
            "archive_path": Path(payload.get("vault_operations_archive") or local.get("vault_operations_archive") or self.vault_operations_store.archive_zip_path(program_id)),
            "verification_report_path": Path(payload.get("vault_operations_verification_report") or local.get("vault_operations_verification_report") or self.vault_operations_store.verification_report_path(program_id)),
            "signoff_binding_path": Path(payload.get("vault_operations_signoff_binding") or local.get("vault_operations_signoff_binding") or self.vault_operations_store.signoff_binding_path(program_id)),
        }

    def _vault_operations_context(self, program_id: str, payload: DomainDocument, *, require_passed: bool) -> DomainDocument:
        paths = self._evidence_paths(program_id, payload)
        for label, path in (("Vault Operations archive", paths["archive_path"]), ("Vault Operations verification report", paths["verification_report_path"]), ("Vault Operations signoff binding", paths["signoff_binding_path"])):
            if not path.exists() or not path.is_file():
                raise UnifiedReleaseProgramContinuityStateError(f"{label} is missing: {path}")
        runtime = verify_unified_release_program_vault_operations_package(paths["archive_path"], strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=paths["signoff_binding_path"])
        external = read_json(paths["verification_report_path"])
        binding = read_json(paths["signoff_binding_path"])
        blockers: list[str] = []
        if runtime.get("status") != "passed":
            blockers.append("vault_operations_runtime_verification_failed")
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE:
            blockers.append("vault_operations_external_package_type")
        if not _integrity_ok(external):
            blockers.append("vault_operations_external_integrity")
        if external.get("status") != "passed":
            blockers.append("vault_operations_external_failed")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("zip_sha256") != _sha256_path(paths["archive_path"]):
            blockers.append("vault_operations_zip_sha256")
        if external.get("manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("vault_operations_manifest_hash")
        if not _integrity_ok(binding):
            blockers.append("vault_operations_signoff_binding_integrity")
        if require_passed and blockers:
            raise UnifiedReleaseProgramContinuityStateError("Vault Operations evidence is not current: " + ", ".join(sorted(set(blockers))))
        return {**paths, "runtime": runtime, "external": external, "signoff_binding": binding, "blockers": sorted(set(blockers))}

    def _write_evidence_manifests(self, program_id: str, context: DomainDocument, payload: DomainDocument) -> None:
        local = {
            "vault_operations_archive": str(context["archive_path"]),
            "vault_operations_verification_report": str(context["verification_report_path"]),
            "vault_operations_signoff_binding": str(context["signoff_binding_path"]),
        }
        write_json(self.local_evidence_manifest_path(program_id), local)
        evidence = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_external_evidence_manifest",
                "program_id": program_id,
                "created_at": now_iso(),
                "evidence": [
                    {
                        "evidence_type": "vault_operations_archive",
                        "component_id": "vault-ops-current",
                        "program_id": program_id,
                        "archive_zip_sha256": _sha256_path(context["archive_path"]),
                        "archive_zip_size_bytes": context["archive_path"].stat().st_size,
                        "manifest_hash": context["runtime"].get("manifest_hash"),
                        "verification_report_hash": context["external"].get("integrity_hash"),
                        "verification_status": context["external"].get("status"),
                        "runtime_verification_hash": context["runtime"].get("integrity_hash"),
                        "signoff_binding_hash": context["signoff_binding"].get("integrity_hash"),
                    }
                ],
            }
        )
        write_json(self.external_evidence_manifest_path(program_id), evidence)

    def _signed_archive_docs(self, program_id: str) -> DomainDocument:
        state = self.latest_signoff_state(program_id)
        if not state.get("signed"):
            raise UnifiedReleaseProgramContinuityStateError("Continuity must be signed before archive export.")
        docs = {
            "policy": self._read_policy(program_id),
            "plan": self._read_plan(program_id),
            "drill": self._read_drill(program_id),
            "readiness": self._read_readiness(program_id),
            "runbook": self._read_runbook(program_id),
            "report": self._read_report(program_id),
            "evidence_manifest": self._read_external_evidence_manifest(program_id),
            "redaction": _read_required_doc(self.redaction_report_path(program_id), "Continuity redaction report"),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "binding": _read_optional_json(self.signoff_binding_path(program_id)),
        }
        signoff = docs["signoff"]
        binding = docs["binding"]
        if not signoff or not binding or not _integrity_ok(signoff) or not _integrity_ok(binding):
            raise UnifiedReleaseProgramContinuityStateError("Continuity signoff and binding are required.")
        if signoff.get("integrity_hash") != state.get("signoff_hash") or binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramContinuityStateError("Continuity signoff does not match signed history.")
        if binding.get("latest_history_event_hash") != state.get("event_hash"):
            raise UnifiedReleaseProgramContinuityStateError("Continuity signoff binding does not match latest history event.")
        expected = {
            "policy_hash": docs["policy"].get("integrity_hash"),
            "recovery_plan_hash": docs["plan"].get("integrity_hash"),
            "drill_report_hash": docs["drill"].get("integrity_hash"),
            "readiness_hash": docs["readiness"].get("integrity_hash"),
            "runbook_hash": docs["runbook"].get("integrity_hash"),
            "continuity_report_hash": docs["report"].get("integrity_hash"),
            "external_evidence_manifest_hash": docs["evidence_manifest"].get("integrity_hash"),
        }
        for key, value in expected.items():
            if signoff.get(key) != value or binding.get(key) != value:
                raise UnifiedReleaseProgramContinuityStateError(f"Continuity signed binding mismatch: {key}.")
        context = self._vault_operations_context(program_id, {}, require_passed=True)
        for key, value in _source_binding_from_context(context).items():
            if binding.get(key) != value:
                raise UnifiedReleaseProgramContinuityStateError(f"Continuity source binding mismatch: {key}.")
        return docs

    def _assert_existing_archive_zip_valid(self, program_id: str) -> None:
        paths = self._evidence_paths(program_id, {})
        report = verify_unified_release_program_continuity_package(
            self.archive_zip_path(program_id),
            strict=True,
            deep_restore=True,
            require_signed=True,
            require_current_vault_operations=True,
            signoff_binding_path=self.signoff_binding_path(program_id),
            vault_operations_archive_path=paths["archive_path"],
            vault_operations_verification_report_path=paths["verification_report_path"],
            vault_operations_signoff_binding_path=paths["signoff_binding_path"],
        )
        if report.get("status") != "passed":
            blockers = ", ".join(str(item) for item in report.get("blockers") or []) or "unknown"
            raise UnifiedReleaseProgramContinuityStateError(f"Existing Continuity Archive ZIP failed verification: {blockers}")

    def _assert_export_dir_matches_signed_docs(self, program_id: str, docs: DomainDocument) -> None:
        export_dir = self.export_dir(program_id)
        if not export_dir.exists():
            raise UnifiedReleaseProgramContinuityStateError("Continuity Archive export directory is missing.")
        actual_entries = {path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file()}
        if actual_entries != REQUIRED_ENTRIES:
            raise UnifiedReleaseProgramContinuityStateError("Continuity Archive export directory does not match the fixed archive layout.")
        expected_docs = {
            "continuity-policy.json": docs["policy"],
            "recovery-plan.json": docs["plan"],
            "recovery-drill-report.json": docs["drill"],
            "continuity-readiness.json": docs["readiness"],
            "continuity-runbook.json": docs["runbook"],
            "continuity-report.json": docs["report"],
            "external-evidence-manifest.json": docs["evidence_manifest"],
            "continuity-signoff.json": docs["signoff"],
            "continuity-signoff-binding-summary.json": docs["binding"],
            "redaction-report.json": docs["redaction"],
        }
        for rel, expected in expected_docs.items():
            actual = read_json(export_dir / rel)
            if not _integrity_ok(actual) or actual.get("integrity_hash") != expected.get("integrity_hash"):
                raise UnifiedReleaseProgramContinuityStateError(f"Continuity Archive export file does not match signed snapshot: {rel}.")
        if (export_dir / "README.txt").read_text(encoding="utf-8") != "MusicForge Unified Release Program Continuity Archive\n":
            raise UnifiedReleaseProgramContinuityStateError("Continuity Archive README does not match signed snapshot.")
        history = _read_history(export_dir / "continuity-history.jsonl")
        latest_signoff = next((row for row in reversed(history) if row.get("event_type") == "continuity_signoff_created"), {})
        if not latest_signoff or latest_signoff.get("event_hash") != docs["binding"].get("latest_history_event_hash"):
            raise UnifiedReleaseProgramContinuityStateError("Continuity Archive history does not match signed snapshot.")
        manifest = read_json(export_dir / "manifest.json")
        if not _integrity_ok(manifest):
            raise UnifiedReleaseProgramContinuityStateError("Continuity Archive manifest integrity failed.")
        source = _as_document(manifest.get("source"))
        expected_source = _archive_manifest_document(program_id, docs, []).get("source") or {}
        for key, value in expected_source.items():
            if source.get(key) != value:
                raise UnifiedReleaseProgramContinuityStateError(f"Continuity Archive manifest source mismatch: {key}.")

    def _write_continuity_report(self, program_id: str, policy: DomainDocument, plan: DomainDocument, drill: DomainDocument, readiness: DomainDocument, context: DomainDocument) -> DomainDocument:
        blockers = list(readiness.get("blockers") or [])
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_report",
                "program_id": program_id,
                "status": "passed" if not blockers else "failed",
                "created_at": now_iso(),
                "policy_hash": policy.get("integrity_hash"),
                "recovery_plan_hash": plan.get("integrity_hash"),
                "drill_report_hash": drill.get("integrity_hash"),
                "readiness_hash": readiness.get("integrity_hash"),
                "external_evidence_manifest_hash": _read_optional_json(self.external_evidence_manifest_path(program_id)).get("integrity_hash"),
                "source": _source_binding_from_context(context),
                "summary": {"drill_status": drill.get("status"), "readiness_status": readiness.get("status"), "blocker_count": len(blockers)},
                "blockers": blockers,
                "tool": {"name": "MusicForge Unified Release Program Continuity", "version": __version__},
            }
        )
        write_json(self.report_path(program_id), report)
        return report

    def _write_redaction_report(self, program_id: str) -> DomainDocument:
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_redaction_report",
                "program_id": program_id,
                "status": "passed",
                "created_at": now_iso(),
                "offenders": [],
            }
        )
        write_json(self.redaction_report_path(program_id), report)
        return report

    def _read_policy(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.policy_path(program_id), "Continuity policy")

    def _read_plan(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.recovery_plan_path(program_id), "Recovery plan")

    def _read_drill(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.drill_report_path(program_id), "Recovery drill report")

    def _read_readiness(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.readiness_path(program_id), "Continuity readiness")

    def _read_runbook(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.runbook_path(program_id), "Continuity runbook")

    def _read_report(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.report_path(program_id), "Continuity report")

    def _read_external_evidence_manifest(self, program_id: str) -> DomainDocument:
        return _read_required_doc(self.external_evidence_manifest_path(program_id), "Continuity external evidence manifest")

    def _append_history(self, program_id: str, event: DomainDocument) -> DomainDocument:
        path = self.history_path(program_id)
        chain = HistoryChain(path, sanitizer=lambda value: sanitize_metadata(value, blocked_keys=CONTINUITY_BLOCKED_METADATA_KEYS))
        return chain.append({**event, "event_index": len(chain.read()) + 1})

    def _history_has(self, program_id: str, event_type: str) -> bool:
        return any(row.get("event_type") == event_type for row in _read_history(self.history_path(program_id)))
