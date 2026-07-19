# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import shutil as shutil
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore as UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package as verify_unified_release_program_vault_package
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package, write_unified_release_program_vault_operations_verification_report as write_unified_release_program_vault_operations_verification_report

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

UnifiedReleaseProgramVaultOperationsError = _make_deferred_global('UnifiedReleaseProgramVaultOperationsError')
UnifiedReleaseProgramVaultOperationsStateError = _make_deferred_global('UnifiedReleaseProgramVaultOperationsStateError')
_bounded = _make_deferred_global('_bounded')
_integrity_hash = _make_deferred_global('_integrity_hash')
_read_optional_json = _make_deferred_global('_read_optional_json')
_recipient_guide = _make_deferred_global('_recipient_guide')
_safe_id = _make_deferred_global('_safe_id')
_sanitize_payload = _make_deferred_global('_sanitize_payload')
_signoff_binding_document = _make_deferred_global('_signoff_binding_document')
_with_integrity = _make_deferred_global('_with_integrity')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramVaultOperationsError, UnifiedReleaseProgramVaultOperationsStateError, _bounded, _integrity_hash, _read_optional_json, _recipient_guide, _safe_id
    global _sanitize_payload, _signoff_binding_document, _with_integrity, write_json
    UnifiedReleaseProgramVaultOperationsError = namespace.get('UnifiedReleaseProgramVaultOperationsError', UnifiedReleaseProgramVaultOperationsError)
    UnifiedReleaseProgramVaultOperationsStateError = namespace.get('UnifiedReleaseProgramVaultOperationsStateError', UnifiedReleaseProgramVaultOperationsStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _recipient_guide = namespace.get('_recipient_guide', _recipient_guide)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize_payload = namespace.get('_sanitize_payload', _sanitize_payload)
    _signoff_binding_document = namespace.get('_signoff_binding_document', _signoff_binding_document)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


VAULT_OPERATIONS_BLOCKED_METADATA_KEYS = {
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




class UnifiedReleaseProgramVaultOperationsStoreReadinessMixin:
    def ops_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "vault-operations"

    def registry_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "registry.json"

    def policy_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "policy.json"

    def review_dir(self, program_id: str, run_id: str) -> Path:
        return self.ops_dir(program_id) / "custody-review-runs" / _safe_id(run_id)

    def latest_review_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "latest-review-report.json"

    def latest_runtime_vault_verification_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "latest-runtime-vault-verification-report.json"

    def rotation_plan_path(self, program_id: str, plan_id: str | None = None) -> Path:
        if plan_id:
            return self.ops_dir(program_id) / "rotation-plans" / _safe_id(plan_id) / "rotation-plan.json"
        return self.ops_dir(program_id) / "rotation-plan-summary.json"

    def transfer_dir(self, program_id: str, transfer_id: str | None = None) -> Path:
        base = self.ops_dir(program_id) / "transfer-packs"
        return base / _safe_id(transfer_id) if transfer_id else base

    def transfer_report_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "transfer-report.json"

    def recipient_guide_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "recipient-guide.md"

    def replica_checklist_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "replica-checklist.json"

    def report_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "vault-operations-report.json"

    def signoff_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "vault-operations-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "vault-operations-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "vault-operations-history.jsonl"

    def export_dir(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "archive-export"

    def manifest_path(self, program_id: str) -> Path:
        return self.export_dir(program_id) / "manifest.json"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "unified-release-program-vault-operations-archive.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.ops_dir(program_id) / "unified-release-program-vault-operations-verification-report.json"

    def get_operations(self, program_id: str) -> DomainDocument:
        return {
            "registry": _read_optional_json(self.registry_path(program_id)),
            "policy": _read_optional_json(self.policy_path(program_id)),
            "latest_review": _read_optional_json(self.latest_review_path(program_id)),
            "rotation_plan": _read_optional_json(self.rotation_plan_path(program_id)),
            "transfer_report": _read_optional_json(self.transfer_report_path(program_id)),
            "report": _read_optional_json(self.report_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "signoff_state": self.latest_signoff_state(program_id),
        }

    def init_policy(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            self.ops_dir(program_id).mkdir(parents=True, exist_ok=True)
            now = now_iso()
            policy = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_custody_policy",
                    "program_id": program_id,
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                    "review_interval_days": int(payload.get("review_interval_days") or 90),
                    "deep_review_required": bool(payload.get("deep_review_required", True)),
                    "transfer_pack_required": bool(payload.get("transfer_pack_required", True)),
                    "allow_supersede": bool(payload.get("allow_supersede", True)),
                    "allow_revoke": bool(payload.get("allow_revoke", True)),
                    "tool": {"name": "MusicForge Unified Release Program Vault Operations", "version": __version__},
                }
            )
            write_json(self.policy_path(program_id), policy)
            self._append_history(program_id, {"event_type": "vault_operations_policy_initialized", "created_at": now, "program_id": program_id, "policy_hash": policy.get("integrity_hash")})
            self.refresh_report(program_id)
            return policy

    def register_vault(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            self.ops_dir(program_id).mkdir(parents=True, exist_ok=True)
            vault_binding = self._current_vault_binding(program_id, payload, require_passed=True)
            registry = _read_optional_json(self.registry_path(program_id))
            generation_id = _safe_id(str(payload.get("generation_id") or registry.get("current_generation_id") or "vaultgen-000001"))
            generations = [row for row in registry.get("generations", []) if isinstance(row, dict) and row.get("generation_id") != generation_id]
            now = now_iso()
            generation = {
                "generation_id": generation_id,
                "status": "current",
                "registered_at": now,
                "vault": vault_binding,
            }
            generations.append(generation)
            registry = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_registry",
                    "program_id": program_id,
                    "registry_id": str(registry.get("registry_id") or "urpvo-registry-000001"),
                    "status": "current",
                    "current_generation_id": generation_id,
                    "created_at": registry.get("created_at") or now,
                    "updated_at": now,
                    "generations": generations,
                    "summary": {"generation_count": len(generations), "current_generation_id": generation_id, "current_vault_zip_sha256": vault_binding.get("vault_zip_sha256")},
                }
            )
            write_json(self.registry_path(program_id), registry)
            if not self.policy_path(program_id).exists():
                self.init_policy(program_id, {})
            self._append_history(program_id, {"event_type": "vault_registered", "created_at": now, "program_id": program_id, "generation_id": generation_id, "registry_hash": registry.get("integrity_hash"), "vault_zip_sha256": vault_binding.get("vault_zip_sha256")})
            self.refresh_report(program_id)
            return registry

    def refresh_registry(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            registry = self._read_registry(program_id)
            registry["updated_at"] = now_iso()
            registry["integrity_hash"] = _integrity_hash(registry)
            write_json(self.registry_path(program_id), registry)
            self.refresh_report(program_id)
            return registry

    def run_custody_review(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            registry = self._read_registry(program_id)
            context = self._current_registry_vault_binding(program_id, registry)
            current = context["current"]
            vault = context["vault"]
            run_id = _safe_id(str(payload.get("run_id") or self._next_review_id(program_id)))
            runtime = context["runtime"]
            run_dir = self.review_dir(program_id, run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            write_json(run_dir / "runtime-vault-verification-report.json", runtime)
            write_json(self.latest_runtime_vault_verification_path(program_id), runtime)
            external = context["external"]
            blockers = list(context["blockers"])
            status = "passed" if not blockers else "failed"
            review = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_custody_review",
                    "program_id": program_id,
                    "review_id": run_id,
                    "status": status,
                    "created_at": now_iso(),
                    "current_generation_id": current.get("generation_id"),
                    "registry_hash": registry.get("integrity_hash"),
                    "runtime_vault_verification_hash": runtime.get("integrity_hash"),
                    "external_vault_verification_hash": external.get("integrity_hash"),
                    "vault_zip_sha256": vault.get("vault_zip_sha256"),
                    "vault_manifest_hash": vault.get("vault_manifest_hash"),
                    "summary": {"runtime_status": runtime.get("status"), "external_status": external.get("status"), "blocker_count": len(blockers)},
                    "blockers": blockers,
                }
            )
            write_json(run_dir / "review-report.json", review)
            write_json(self.latest_review_path(program_id), review)
            self._append_history(program_id, {"event_type": "vault_custody_review_completed", "created_at": review.get("created_at"), "program_id": program_id, "review_id": run_id, "review_hash": review.get("integrity_hash"), "status": status})
            self.refresh_report(program_id)
            return review

    def create_rotation_plan(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            latest_review = _read_optional_json(self.latest_review_path(program_id))
            plan_id = _safe_id(str(payload.get("plan_id") or "rotation-plan-000001"))
            needed = latest_review.get("status") != "passed" or bool(payload.get("force_rotation", False))
            plan = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_rotation_plan",
                    "program_id": program_id,
                    "plan_id": plan_id,
                    "status": "required" if needed else "not_required",
                    "created_at": now_iso(),
                    "latest_review_hash": latest_review.get("integrity_hash"),
                    "reason": _bounded(payload.get("reason") or ("Custody review failed." if needed else "Current Vault custody review is passed."), 1000),
                    "actions": [{"action": "create_successor_vault_generation", "mode": "manual_required"}] if needed else [],
                }
            )
            write_json(self.rotation_plan_path(program_id, plan_id), plan)
            write_json(self.rotation_plan_path(program_id), plan)
            self._append_history(program_id, {"event_type": "vault_rotation_plan_created", "created_at": plan.get("created_at"), "program_id": program_id, "plan_id": plan_id, "plan_hash": plan.get("integrity_hash")})
            self.refresh_report(program_id)
            return plan

    def supersede_vault(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            registry = self._read_registry(program_id)
            old_id = _safe_id(str(payload.get("old_generation_id") or registry.get("current_generation_id") or ""))
            new_id = _safe_id(str(payload.get("new_generation_id") or "vaultgen-000002"))
            if not old_id:
                raise UnifiedReleaseProgramVaultOperationsStateError("old_generation_id is required to supersede a Vault.")
            vault_binding = self._current_vault_binding(program_id, payload, require_passed=True)
            now = now_iso()
            generations: list[DomainDocument] = []
            for row in registry.get("generations", []) or []:
                if not isinstance(row, dict):
                    continue
                if row.get("generation_id") == old_id:
                    row = {**row, "status": "superseded", "superseded_at": now, "superseded_by": new_id}
                generations.append(row)
            generations.append({"generation_id": new_id, "status": "current", "registered_at": now, "supersedes": old_id, "vault": vault_binding})
            registry.update({"status": "current", "current_generation_id": new_id, "updated_at": now, "generations": generations})
            registry["summary"] = {"generation_count": len(generations), "current_generation_id": new_id, "current_vault_zip_sha256": vault_binding.get("vault_zip_sha256")}
            registry["integrity_hash"] = _integrity_hash(registry)
            write_json(self.registry_path(program_id), registry)
            self._append_history(program_id, {"event_type": "vault_superseded", "created_at": now, "program_id": program_id, "old_generation_id": old_id, "new_generation_id": new_id, "registry_hash": registry.get("integrity_hash")})
            self.refresh_report(program_id)
            return registry

    def revoke_vault(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            registry = self._read_registry(program_id)
            generation_id = _safe_id(str(payload.get("generation_id") or registry.get("current_generation_id") or ""))
            if not generation_id:
                raise UnifiedReleaseProgramVaultOperationsStateError("generation_id is required to revoke a Vault.")
            now = now_iso()
            generations = []
            for row in registry.get("generations", []) or []:
                if not isinstance(row, dict):
                    continue
                if row.get("generation_id") == generation_id:
                    row = {**row, "status": "revoked", "revoked_at": now, "revocation_reason": _bounded(payload.get("reason") or "Vault revoked by operator.", 1000)}
                generations.append(row)
            if registry.get("current_generation_id") == generation_id:
                registry["status"] = "revoked"
            registry["generations"] = generations
            registry["updated_at"] = now
            registry["summary"] = {"generation_count": len(generations), "current_generation_id": registry.get("current_generation_id"), "revoked_generation_id": generation_id}
            registry["integrity_hash"] = _integrity_hash(registry)
            write_json(self.registry_path(program_id), registry)
            self._append_history(program_id, {"event_type": "vault_revoked", "created_at": now, "program_id": program_id, "generation_id": generation_id, "registry_hash": registry.get("integrity_hash")})
            self.refresh_report(program_id)
            return registry

    def create_transfer_pack(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            registry = self._read_registry(program_id)
            current = self._current_generation(registry)
            latest_review = _read_optional_json(self.latest_review_path(program_id))
            transfer_id = _safe_id(str(payload.get("transfer_id") or "vault-transfer-000001"))
            blockers = []
            if not current or registry.get("status") != "current":
                blockers.append("vault_registry_not_current")
            if latest_review.get("status") != "passed":
                blockers.append("latest_custody_review_not_passed")
            try:
                blockers.extend(self._current_registry_vault_binding(program_id, registry)["blockers"])
            except UnifiedReleaseProgramVaultOperationsError:
                blockers.append("current_vault_binding_unavailable")
            status = "ready" if not blockers else "blocked"
            transfer = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_transfer_report",
                    "program_id": program_id,
                    "transfer_id": transfer_id,
                    "status": status,
                    "created_at": now_iso(),
                    "recipient": _bounded(payload.get("recipient") or "external-custodian", 160),
                    "registry_hash": registry.get("integrity_hash"),
                    "latest_review_hash": latest_review.get("integrity_hash"),
                    "current_generation_id": current.get("generation_id") if current else None,
                    "summary": {"blocker_count": len(blockers), "recipient": _bounded(payload.get("recipient") or "external-custodian", 160)},
                    "blockers": blockers,
                }
            )
            guide = _recipient_guide(program_id, transfer)
            checklist = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_replica_checklist",
                    "program_id": program_id,
                    "transfer_id": transfer_id,
                    "items": [
                        {"item_id": "verify_vault_operations_archive", "status": "manual_required"},
                        {"item_id": "store_vault_anchor_separately", "status": "manual_required"},
                        {"item_id": "record_custody_recipient", "status": "manual_required"},
                    ],
                }
            )
            write_json(self.transfer_report_path(program_id), transfer)
            self.recipient_guide_path(program_id).parent.mkdir(parents=True, exist_ok=True)
            self.recipient_guide_path(program_id).write_text(guide, encoding="utf-8")
            write_json(self.replica_checklist_path(program_id), checklist)
            transfer_dir = self.transfer_dir(program_id, transfer_id)
            transfer_dir.mkdir(parents=True, exist_ok=True)
            write_json(transfer_dir / "transfer-report.json", transfer)
            (transfer_dir / "recipient-guide.md").write_text(guide, encoding="utf-8")
            write_json(transfer_dir / "replica-checklist.json", checklist)
            self._append_history(program_id, {"event_type": "vault_transfer_pack_created", "created_at": transfer.get("created_at"), "program_id": program_id, "transfer_id": transfer_id, "transfer_hash": transfer.get("integrity_hash"), "status": status})
            self.refresh_report(program_id)
            return transfer

    def refresh_report(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            registry = _read_optional_json(self.registry_path(program_id))
            policy = _read_optional_json(self.policy_path(program_id))
            latest_review = _read_optional_json(self.latest_review_path(program_id))
            rotation = _read_optional_json(self.rotation_plan_path(program_id))
            transfer = _read_optional_json(self.transfer_report_path(program_id))
            blockers = []
            if registry.get("status") != "current" or not self._current_generation(registry):
                blockers.append("vault_registry_not_current")
            elif registry:
                try:
                    blockers.extend(self._current_registry_vault_binding(program_id, registry)["blockers"])
                except UnifiedReleaseProgramVaultOperationsError:
                    blockers.append("current_vault_binding_unavailable")
            if policy.get("status") != "active":
                blockers.append("custody_policy_not_active")
            if latest_review.get("status") != "passed":
                blockers.append("latest_custody_review_not_passed")
            if transfer.get("status") != "ready":
                blockers.append("transfer_pack_not_ready")
            report = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_operations_report",
                    "program_id": program_id,
                    "status": "passed" if not blockers else "failed",
                    "created_at": now_iso(),
                    "registry_hash": registry.get("integrity_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "latest_review_hash": latest_review.get("integrity_hash"),
                    "rotation_plan_hash": rotation.get("integrity_hash"),
                    "transfer_report_hash": transfer.get("integrity_hash"),
                    "summary": {
                        "registry_status": registry.get("status") or "missing",
                        "policy_status": policy.get("status") or "missing",
                        "latest_review_status": latest_review.get("status") or "missing",
                        "transfer_status": transfer.get("status") or "missing",
                        "blocker_count": len(blockers),
                    },
                    "blockers": blockers,
                    "tool": {"name": "MusicForge Unified Release Program Vault Operations", "version": __version__},
                }
            )
            write_json(self.report_path(program_id), report)
            return report

    def signoff_operations(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            report = self.refresh_report(program_id)
            if report.get("status") != "passed":
                raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations report must pass before signoff.")
            registry = self._read_registry(program_id)
            policy = self._read_policy(program_id)
            review = self._read_latest_review(program_id)
            transfer = self._read_transfer(program_id)
            now = now_iso()
            signoff = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_vault_operations_signoff",
                    "program_id": program_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "program-custodian", 120),
                    "role": _bounded(payload.get("role") or "custody_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Unified Release Program Vault Operations accepted.", 1000),
                    "signed_at": now,
                    "report_hash": report.get("integrity_hash"),
                    "registry_hash": registry.get("integrity_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "latest_review_hash": review.get("integrity_hash"),
                    "transfer_report_hash": transfer.get("integrity_hash"),
                }
            )
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "vault_operations_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "report_hash": report.get("integrity_hash"),
                    "registry_hash": registry.get("integrity_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "latest_review_hash": review.get("integrity_hash"),
                    "transfer_report_hash": transfer.get("integrity_hash"),
                },
            )
            binding = _signoff_binding_document(program_id, signoff, event, report, registry, policy, review, transfer)
            write_json(self.signoff_binding_path(program_id), binding)
            return signoff
