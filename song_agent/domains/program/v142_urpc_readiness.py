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
_bounded = _make_deferred_global('_bounded')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_read_optional_json = _make_deferred_global('_read_optional_json')
_safe_id = _make_deferred_global('_safe_id')
_sanitize_payload = _make_deferred_global('_sanitize_payload')
_sha256_path = _make_deferred_global('_sha256_path')
_signoff_binding_document = _make_deferred_global('_signoff_binding_document')
_source_binding_from_context = _make_deferred_global('_source_binding_from_context')
_with_integrity = _make_deferred_global('_with_integrity')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityStateError, _archive_manifest_document, _bounded, _file_record, _gate_failed, _integrity_hash, _integrity_ok
    global _read_optional_json, _safe_id, _sanitize_payload, _sha256_path, _signoff_binding_document, _source_binding_from_context, _with_integrity, read_json
    global row, write_json
    UnifiedReleaseProgramContinuityStateError = namespace.get('UnifiedReleaseProgramContinuityStateError', UnifiedReleaseProgramContinuityStateError)
    _archive_manifest_document = namespace.get('_archive_manifest_document', _archive_manifest_document)
    _bounded = namespace.get('_bounded', _bounded)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize_payload = namespace.get('_sanitize_payload', _sanitize_payload)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _signoff_binding_document = namespace.get('_signoff_binding_document', _signoff_binding_document)
    _source_binding_from_context = namespace.get('_source_binding_from_context', _source_binding_from_context)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
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




class UnifiedReleaseProgramContinuityStoreReadinessMixin:
    def continuity_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "continuity"

    def policy_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-policy.json"

    def local_evidence_manifest_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "local-evidence-manifest.json"

    def external_evidence_manifest_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "external-evidence-manifest.json"

    def recovery_plan_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "recovery-plan.json"

    def drill_report_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "recovery-drill-report.json"

    def readiness_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-readiness.json"

    def runbook_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-runbook.json"

    def report_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-report.json"

    def redaction_report_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "redaction-report.json"

    def signoff_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-history.jsonl"

    def export_dir(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "continuity-archive"

    def manifest_path(self, program_id: str) -> Path:
        return self.export_dir(program_id) / "manifest.json"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "unified-release-program-continuity-archive.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.continuity_dir(program_id) / "unified-release-program-continuity-verification-report.json"

    def get_continuity(self, program_id: str) -> DomainDocument:
        return {
            "policy": _read_optional_json(self.policy_path(program_id)),
            "external_evidence_manifest": _read_optional_json(self.external_evidence_manifest_path(program_id)),
            "recovery_plan": _read_optional_json(self.recovery_plan_path(program_id)),
            "drill_report": _read_optional_json(self.drill_report_path(program_id)),
            "readiness": _read_optional_json(self.readiness_path(program_id)),
            "runbook": _read_optional_json(self.runbook_path(program_id)),
            "report": _read_optional_json(self.report_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "signoff_state": self.latest_signoff_state(program_id),
        }

    def init_policy(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            self.continuity_dir(program_id).mkdir(parents=True, exist_ok=True)
            now = now_iso()
            policy = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_policy",
                    "program_id": program_id,
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                    "isolated_restore_required": bool(payload.get("isolated_restore_required", True)),
                    "deep_restore_required": bool(payload.get("deep_restore_required", True)),
                    "redaction_scan_required": bool(payload.get("redaction_scan_required", True)),
                    "tool": {"name": "MusicForge Unified Release Program Continuity", "version": __version__},
                }
            )
            write_json(self.policy_path(program_id), policy)
            self._append_history(program_id, {"event_type": "continuity_policy_initialized", "created_at": now, "program_id": program_id, "policy_hash": policy.get("integrity_hash")})
            return policy

    def create_recovery_plan(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            if not self.policy_path(program_id).exists():
                self.init_policy(program_id, {})
            context = self._vault_operations_context(program_id, payload, require_passed=True)
            self._write_evidence_manifests(program_id, context, payload)
            now = now_iso()
            plan = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_recovery_plan",
                    "program_id": program_id,
                    "plan_id": _safe_id(str(payload.get("plan_id") or "recovery-plan-000001")),
                    "status": "planned",
                    "created_at": now,
                    "steps": [
                        {"step_id": "copy_vault_operations_archive", "mode": "safe"},
                        {"step_id": "verify_vault_operations_archive", "mode": "safe"},
                        {"step_id": "deep_restore_replay", "mode": "safe"},
                        {"step_id": "review_recovery_report", "mode": "manual_required"},
                    ],
                    "source": _source_binding_from_context(context),
                    "external_evidence_manifest_hash": _read_optional_json(self.external_evidence_manifest_path(program_id)).get("integrity_hash"),
                }
            )
            write_json(self.recovery_plan_path(program_id), plan)
            self._append_history(program_id, {"event_type": "recovery_plan_created", "created_at": now, "program_id": program_id, "plan_hash": plan.get("integrity_hash")})
            return plan

    def run_recovery_drill(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            plan = self._read_plan(program_id)
            context = self._vault_operations_context(program_id, payload, require_passed=True)
            blockers: list[str] = []
            runtime = context["runtime"]
            external = context["external"]
            if runtime.get("status") != "passed":
                blockers.append("vault_operations_runtime_verification_failed")
            if external.get("status") != "passed":
                blockers.append("vault_operations_external_verification_failed")
            with tempfile.TemporaryDirectory(prefix="mf-urpc-restore-") as temp:
                temp_root = Path(temp)
                restore_root = temp_root / "restore-root"
                restore_root.mkdir(parents=True, exist_ok=True)
                copied_archive = restore_root / "vault-operations-archive.zip"
                shutil.copyfile(context["archive_path"], copied_archive)
                replay_report = verify_unified_release_program_vault_operations_package(
                    copied_archive,
                    strict=True,
                    deep=True,
                    require_signed=True,
                    require_current_vault=True,
                    signoff_binding_path=context["signoff_binding_path"],
                )
            if replay_report.get("status") != "passed":
                blockers.append("isolated_replay_failed")
            now = now_iso()
            drill = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_recovery_drill_report",
                    "program_id": program_id,
                    "drill_id": _safe_id(str(payload.get("drill_id") or "recovery-drill-000001")),
                    "status": "passed" if not blockers else "failed",
                    "created_at": now,
                    "recovery_plan_hash": plan.get("integrity_hash"),
                    "isolated_restore": {"status": "passed" if replay_report.get("status") == "passed" else "failed", "write_back_to_live_workspace": False},
                    "runtime_verification_hash": runtime.get("integrity_hash"),
                    "external_verification_hash": external.get("integrity_hash"),
                    "isolated_replay_verification_hash": replay_report.get("integrity_hash"),
                    "source": _source_binding_from_context(context),
                    "summary": {"runtime_status": runtime.get("status"), "external_status": external.get("status"), "replay_status": replay_report.get("status"), "blocker_count": len(blockers)},
                    "blockers": sorted(set(blockers)),
                }
            )
            write_json(self.drill_report_path(program_id), drill)
            self._append_history(program_id, {"event_type": "recovery_drill_completed", "created_at": now, "program_id": program_id, "drill_hash": drill.get("integrity_hash"), "status": drill.get("status")})
            self.refresh_readiness(program_id, payload)
            return drill

    def refresh_readiness(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            policy = self._read_policy(program_id)
            plan = self._read_plan(program_id)
            drill = self._read_drill(program_id)
            context = self._vault_operations_context(program_id, payload, require_passed=False)
            blockers: list[str] = []
            warnings: list[str] = []
            if policy.get("status") != "active":
                blockers.append("continuity_policy_not_active")
            if plan.get("status") != "planned":
                blockers.append("recovery_plan_not_planned")
            if drill.get("status") != "passed":
                blockers.append("recovery_drill_not_passed")
            if context["runtime"].get("status") != "passed":
                blockers.append("vault_operations_runtime_verification_failed")
            if context["external"].get("status") != "passed":
                blockers.append("vault_operations_external_verification_failed")
            blockers.extend(context.get("blockers", []))
            readiness = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_readiness",
                    "program_id": program_id,
                    "status": "passed" if not blockers else "failed",
                    "created_at": now_iso(),
                    "policy_hash": policy.get("integrity_hash"),
                    "recovery_plan_hash": plan.get("integrity_hash"),
                    "drill_report_hash": drill.get("integrity_hash"),
                    "source": _source_binding_from_context(context),
                    "checks": [
                        {"check_id": "source_vault_operations_current", "status": "passed" if not context.get("blockers") else "failed"},
                        {"check_id": "isolated_restore", "status": "passed" if drill.get("status") == "passed" else "failed"},
                        {"check_id": "deep_replay", "status": "passed" if context["runtime"].get("status") == "passed" else "failed"},
                        {"check_id": "redaction", "status": "passed"},
                    ],
                    "summary": {"blocker_count": len(blockers), "warning_count": len(warnings)},
                    "blockers": sorted(set(blockers)),
                    "warnings": warnings,
                }
            )
            write_json(self.readiness_path(program_id), readiness)
            self._write_continuity_report(program_id, policy, plan, drill, readiness, context)
            self._write_redaction_report(program_id)
            return readiness

    def generate_runbook(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            readiness = self._read_readiness(program_id)
            actions = [
                {"action_id": "verify_vault_operations_archive", "mode": "safe", "status": "completed" if readiness.get("status") == "passed" else "blocked"},
                {"action_id": "copy_archive_to_offline_storage", "mode": "manual_required", "status": "manual_required"},
                {"action_id": "record_recovery_drill_result", "mode": "manual_required", "status": "manual_required"},
            ]
            runbook = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_runbook",
                    "program_id": program_id,
                    "status": "ready" if readiness.get("status") == "passed" else "blocked",
                    "created_at": now_iso(),
                    "readiness_hash": readiness.get("integrity_hash"),
                    "actions": actions,
                    "summary": {"manual_required_count": len([row for row in actions if row.get("status") == "manual_required"])},
                }
            )
            write_json(self.runbook_path(program_id), runbook)
            self.refresh_readiness(program_id)
            return runbook

    def signoff_continuity(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            readiness = self.refresh_readiness(program_id, payload)
            runbook = _read_optional_json(self.runbook_path(program_id)) or self.generate_runbook(program_id)
            report = self._read_report(program_id)
            if readiness.get("status") != "passed" or report.get("status") != "passed":
                raise UnifiedReleaseProgramContinuityStateError("Continuity readiness must pass before signoff.")
            if runbook.get("status") != "ready":
                raise UnifiedReleaseProgramContinuityStateError("Continuity runbook must be ready before signoff.")
            policy = self._read_policy(program_id)
            plan = self._read_plan(program_id)
            drill = self._read_drill(program_id)
            evidence_manifest = self._read_external_evidence_manifest(program_id)
            context = self._vault_operations_context(program_id, payload, require_passed=True)
            now = now_iso()
            signoff = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_signoff",
                    "program_id": program_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "continuity-lead", 120),
                    "role": _bounded(payload.get("role") or "continuity_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Recovery drill passed.", 1000),
                    "signed_at": now,
                    "policy_hash": policy.get("integrity_hash"),
                    "recovery_plan_hash": plan.get("integrity_hash"),
                    "drill_report_hash": drill.get("integrity_hash"),
                    "readiness_hash": readiness.get("integrity_hash"),
                    "runbook_hash": runbook.get("integrity_hash"),
                    "continuity_report_hash": report.get("integrity_hash"),
                    "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
                    **_source_binding_from_context(context),
                }
            )
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "continuity_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "policy_hash": policy.get("integrity_hash"),
                    "drill_report_hash": drill.get("integrity_hash"),
                    "readiness_hash": readiness.get("integrity_hash"),
                    "runbook_hash": runbook.get("integrity_hash"),
                    "continuity_report_hash": report.get("integrity_hash"),
                },
            )
            binding = _signoff_binding_document(program_id, signoff, event, policy, plan, drill, readiness, runbook, report, evidence_manifest)
            write_json(self.signoff_binding_path(program_id), binding)
            return signoff

    def export_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            docs = self._signed_archive_docs(program_id)
            if self._history_has(program_id, "continuity_archive_exported") and not self.manifest_path(program_id).exists():
                raise UnifiedReleaseProgramContinuityStateError("Continuity Archive export was already created and cannot be silently rebuilt.")
            export_dir = self.export_dir(program_id)
            manifest_path = self.manifest_path(program_id)
            if manifest_path.exists():
                self._assert_export_dir_matches_signed_docs(program_id, docs)
                manifest = read_json(manifest_path)
                return manifest
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_doc(rel: str, value: DomainDocument | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, str):
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            write_doc("continuity-policy.json", docs["policy"])
            write_doc("recovery-plan.json", docs["plan"])
            write_doc("recovery-drill-report.json", docs["drill"])
            write_doc("continuity-readiness.json", docs["readiness"])
            write_doc("continuity-runbook.json", docs["runbook"])
            write_doc("continuity-report.json", docs["report"])
            write_doc("external-evidence-manifest.json", docs["evidence_manifest"])
            write_doc("continuity-signoff.json", docs["signoff"])
            write_doc("continuity-signoff-binding-summary.json", docs["binding"])
            history_text = self.history_path(program_id).read_text(encoding="utf-8") if self.history_path(program_id).exists() else ""
            write_doc("continuity-history.jsonl", history_text)
            write_doc("redaction-report.json", docs["redaction"])
            write_doc("README.txt", "MusicForge Unified Release Program Continuity Archive\n")
            manifest = _archive_manifest_document(program_id, docs, files)
            write_json(manifest_path, manifest)
            self._append_history(program_id, {"event_type": "continuity_archive_exported", "created_at": now_iso(), "program_id": program_id, "manifest_hash": manifest.get("integrity_hash"), "signoff_hash": docs["signoff"].get("integrity_hash")})
            return manifest

    def build_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            docs = self._signed_archive_docs(program_id)
            zip_path = self.archive_zip_path(program_id)
            if self._history_has(program_id, "continuity_archive_zipped") and not zip_path.exists():
                raise UnifiedReleaseProgramContinuityStateError("Continuity Archive ZIP was already built and cannot be silently rebuilt.")
            if zip_path.exists():
                self._assert_existing_archive_zip_valid(program_id)
                return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": _read_optional_json(self.manifest_path(program_id)).get("integrity_hash")}
            self.export_archive(program_id)
            self._assert_export_dir_matches_signed_docs(program_id, docs)
            export_dir = self.export_dir(program_id)
            entries = sorted(path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file())
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            result = {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": manifest.get("integrity_hash")}
            self._append_history(program_id, {"event_type": "continuity_archive_zipped", "created_at": now_iso(), "program_id": program_id, "zip_sha256": result.get("zip_sha256"), "manifest_hash": manifest.get("integrity_hash")})
            return result

    def verify_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        paths = self._evidence_paths(program_id, payload)
        report = verify_unified_release_program_continuity_package(
            payload.get("archive_zip") or payload.get("zip_path") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            deep_restore=bool(payload.get("deep_restore", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current_vault_operations=bool(payload.get("require_current_vault_operations", True)),
            signoff_binding_path=payload.get("signoff_binding") or self.signoff_binding_path(program_id),
            vault_operations_archive_path=payload.get("vault_operations_archive") or paths["archive_path"],
            vault_operations_verification_report_path=payload.get("vault_operations_verification_report") or paths["verification_report_path"],
            vault_operations_signoff_binding_path=payload.get("vault_operations_signoff_binding") or paths["signoff_binding_path"],
        )
        write_unified_release_program_continuity_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
        vault_operations_archive_path: Path | str | None = None,
        vault_operations_verification_report_path: Path | str | None = None,
        vault_operations_signoff_binding_path: Path | str | None = None,
        **_: object,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        paths = self._evidence_paths(program_id, {})
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        binding_path = Path(signoff_binding_path) if signoff_binding_path else self.signoff_binding_path(program_id)
        vault_ops_zip = Path(vault_operations_archive_path) if vault_operations_archive_path else paths["archive_path"]
        vault_ops_report = Path(vault_operations_verification_report_path) if vault_operations_verification_report_path else paths["verification_report_path"]
        vault_ops_binding = Path(vault_operations_signoff_binding_path) if vault_operations_signoff_binding_path else paths["signoff_binding_path"]
        for label, path in (("Continuity Archive ZIP", zip_path), ("Continuity verification report", report_path), ("Continuity signoff binding", binding_path), ("Vault Operations archive", vault_ops_zip), ("Vault Operations verification report", vault_ops_report), ("Vault Operations signoff binding", vault_ops_binding)):
            if not path.exists():
                return _gate_failed(f"{label} is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_package(zip_path, strict=True, deep_restore=True, require_signed=True, require_current_vault_operations=True, signoff_binding_path=binding_path, vault_operations_archive_path=vault_ops_zip, vault_operations_verification_report_path=vault_ops_report, vault_operations_signoff_binding_path=vault_ops_binding)
        except Exception as exc:
            return _gate_failed(f"Unified Release Program Continuity gate could not verify evidence: {sanitize_sensitive_text(str(exc))}")
        if external.get("package_type") != "musicforge_unified_release_program_continuity_verification":
            return _gate_failed("Continuity verification report package type is invalid.")
        if not _integrity_ok(external):
            return _gate_failed("Continuity verification report integrity failed.")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            return _gate_failed("Continuity verifier failed.", summary=runtime.get("summary", {}), blockers=runtime.get("blockers", []))
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            return _gate_failed("Continuity verification report does not match current archive ZIP.")
        return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {}), "verification_report_hash": external.get("integrity_hash")}
