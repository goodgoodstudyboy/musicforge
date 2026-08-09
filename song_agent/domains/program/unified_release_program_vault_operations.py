from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

import shutil as shutil
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.domains.legacy_documents import _program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore as UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package as verify_unified_release_program_vault_package
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package, write_unified_release_program_vault_operations_verification_report as write_unified_release_program_vault_operations_verification_report


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


class UnifiedReleaseProgramVaultOperationsError(ValueError):
    pass


class UnifiedReleaseProgramVaultOperationsNotFoundError(UnifiedReleaseProgramVaultOperationsError):
    pass


class UnifiedReleaseProgramVaultOperationsStateError(UnifiedReleaseProgramVaultOperationsError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramVaultOperationsStateError)


class UnifiedReleaseProgramVaultOperationsStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.vault_store = UnifiedReleaseProgramVaultStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

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

    def get_operations(self, program_id: str) -> dict[str, Any]:
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

    def init_policy(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def register_vault(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def refresh_registry(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        _sanitize_payload(payload or {})
        with self.lock:
            self._ensure_unsigned(program_id)
            registry = self._read_registry(program_id)
            registry["updated_at"] = now_iso()
            registry["integrity_hash"] = _integrity_hash(registry)
            write_json(self.registry_path(program_id), registry)
            self.refresh_report(program_id)
            return registry

    def run_custody_review(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def create_rotation_plan(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def supersede_vault(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
            generations: list[dict[str, Any]] = []
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

    def revoke_vault(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def create_transfer_pack(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def refresh_report(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def signoff_operations(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def export_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        _sanitize_payload(payload or {})
        with self.lock:
            docs = self._signed_archive_docs(program_id)
            export_dir = self.export_dir(program_id)
            manifest_path = self.manifest_path(program_id)
            if manifest_path.exists():
                manifest = read_json(manifest_path)
                if manifest.get("source", {}).get("signoff_binding_hash") != docs["binding"].get("integrity_hash"):
                    raise UnifiedReleaseProgramVaultOperationsStateError("Existing Vault Operations archive export does not match current signoff binding.")
                return manifest
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_doc(rel: str, value: dict[str, Any] | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, str):
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            def copy_file(source: Path, rel: str) -> None:
                if not source.exists() or not source.is_file():
                    raise UnifiedReleaseProgramVaultOperationsStateError(f"Required Vault Operations archive evidence is missing: {source}")
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, path)
                files.append(_file_record(path, rel))

            write_doc("vault-operations-report.json", docs["report"])
            write_doc("registry.json", docs["registry"])
            write_doc("policy.json", docs["policy"])
            write_doc("latest-review-report.json", docs["review"])
            write_doc("rotation-plan-summary.json", docs["rotation"])
            write_doc("transfer-report.json", docs["transfer"])
            write_doc("vault-operations-signoff.json", docs["signoff"])
            write_doc("vault-operations-signoff-binding-summary.json", docs["binding"])
            history_text = self.history_path(program_id).read_text(encoding="utf-8") if self.history_path(program_id).exists() else ""
            write_doc("vault-operations-history.jsonl", history_text)
            vault_zip, vault_anchor, vault_verification = self._vault_evidence_paths(program_id, docs["current_vault"])
            copy_file(vault_zip, "packages/current-vault.zip")
            copy_file(vault_anchor, "proofs/current-vault-anchor.json")
            copy_file(vault_verification, "proofs/current-vault-verification-report.json")
            write_doc("docs/recipient-guide.md", self.recipient_guide_path(program_id).read_text(encoding="utf-8") if self.recipient_guide_path(program_id).exists() else _recipient_guide(program_id, docs["transfer"]))
            write_doc("docs/replica-checklist.json", _read_optional_json(self.replica_checklist_path(program_id)) or _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_replica_checklist", "program_id": program_id, "items": []}))
            write_doc("README.txt", "MusicForge Unified Release Program Vault Operations Archive\n")
            manifest = _archive_manifest_document(program_id, docs, files)
            write_json(manifest_path, manifest)
            return manifest

    def build_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        _sanitize_payload(payload or {})
        with self.lock:
            self._signed_archive_docs(program_id)
            zip_path = self.archive_zip_path(program_id)
            if zip_path.exists():
                return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": _read_optional_json(self.manifest_path(program_id)).get("integrity_hash")}
            manifest = self.export_archive(program_id)
            export_dir = self.export_dir(program_id)
            entries = sorted(path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file())
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": manifest.get("integrity_hash")}

    def verify_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        report = verify_unified_release_program_vault_operations_package(
            payload.get("archive_zip") or payload.get("zip_path") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current_vault=bool(payload.get("require_current_vault", True)),
            signoff_binding_path=payload.get("signoff_binding") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_vault_operations_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        binding_path = Path(signoff_binding_path) if signoff_binding_path else self.signoff_binding_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Vault Operations archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Vault Operations verification report is missing.")
        if not binding_path.exists():
            return _gate_failed("Unified Release Program Vault Operations signoff binding is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_vault_operations_package(zip_path, strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=binding_path)
        except Exception as exc:
            return _gate_failed(f"Unified Release Program Vault Operations gate could not verify evidence: {sanitize_sensitive_text(str(exc))}")
        if external.get("package_type") != "musicforge_unified_release_program_vault_operations_verification":
            return _gate_failed("Unified Release Program Vault Operations verification report package type is invalid.")
        if not _integrity_ok(external):
            return _gate_failed("Unified Release Program Vault Operations verification report integrity failed.")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            return _gate_failed("Unified Release Program Vault Operations verifier failed.", summary=runtime.get("summary", {}), blockers=runtime.get("blockers", []))
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            return _gate_failed("Unified Release Program Vault Operations verification report does not match current archive ZIP.")
        return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {}), "verification_report_hash": external.get("integrity_hash")}

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        events = _read_history(self.history_path(program_id))
        signoffs = [row for row in events if row.get("event_type") == "vault_operations_signoff_created"]
        if not signoffs:
            return {"status": "unsigned", "signed": False}
        latest = signoffs[-1]
        return {"status": "signed", "signed": True, "signoff_hash": latest.get("signoff_hash"), "event_hash": latest.get("event_hash"), "event_index": latest.get("event_index")}

    def _ensure_unsigned(self, program_id: str) -> None:
        state = self.latest_signoff_state(program_id)
        if state.get("signed"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Unified Release Program Vault Operations are signed. Create a successor operations record before mutation.")

    def _read_registry(self, program_id: str) -> ImplementationDocument:
        registry = _read_optional_json(self.registry_path(program_id))
        if not registry:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Vault Operations registry is missing.")
        if not _integrity_ok(registry):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations registry integrity failed.")
        return registry

    def _read_policy(self, program_id: str) -> ImplementationDocument:
        policy = _read_optional_json(self.policy_path(program_id))
        if not policy:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Vault Operations policy is missing.")
        if not _integrity_ok(policy):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations policy integrity failed.")
        return policy

    def _read_latest_review(self, program_id: str) -> ImplementationDocument:
        review = _read_optional_json(self.latest_review_path(program_id))
        if not review:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Latest Vault custody review is missing.")
        if not _integrity_ok(review):
            raise UnifiedReleaseProgramVaultOperationsStateError("Latest Vault custody review integrity failed.")
        return review

    def _read_transfer(self, program_id: str) -> ImplementationDocument:
        transfer = _read_optional_json(self.transfer_report_path(program_id))
        if not transfer:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Vault transfer report is missing.")
        if not _integrity_ok(transfer):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault transfer report integrity failed.")
        return transfer

    def _current_generation(self, registry: ImplementationDocument) -> ImplementationDocument:
        current_id = str(registry.get("current_generation_id") or "")
        for row in registry.get("generations", []) or []:
            if isinstance(row, dict) and row.get("generation_id") == current_id:
                return row
        return {}

    def _current_vault_binding(self, program_id: str, payload: ImplementationDocument, *, require_passed: bool) -> ImplementationDocument:
        vault_zip = Path(payload.get("vault_zip") or payload.get("vault") or self.vault_store.zip_path(program_id))
        vault_anchor = Path(payload.get("vault_anchor") or payload.get("anchor") or self.vault_store.anchor_path(program_id))
        vault_verification = Path(payload.get("vault_verification_report") or self.vault_store.verification_report_path(program_id))
        for label, path in (("Vault ZIP", vault_zip), ("Vault anchor", vault_anchor), ("Vault verification report", vault_verification)):
            if not path.exists():
                raise UnifiedReleaseProgramVaultOperationsStateError(f"{label} is missing: {path}")
        runtime = verify_unified_release_program_vault_package(vault_zip, strict=True, deep=True, require_anchor=True, vault_anchor_path=vault_anchor, require_accepted_evidence=True)
        external = read_json(vault_verification)
        anchor = read_json(vault_anchor)
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault verification report package type is invalid.")
        if anchor.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault anchor package type is invalid.")
        if not _integrity_ok(external):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault verification report integrity failed.")
        if not _integrity_ok(anchor):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault anchor integrity failed.")
        if require_passed and (runtime.get("status") != "passed" or external.get("status") != "passed"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Current Vault runtime and external verification must pass.")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault verification report does not match current Vault ZIP.")
        if anchor.get("vault_zip_sha256") != runtime.get("zip_sha256") or anchor.get("vault_manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault anchor does not match current Vault ZIP.")
        return {
            "vault_zip_sha256": _sha256_path(vault_zip),
            "vault_zip_size_bytes": vault_zip.stat().st_size,
            "vault_manifest_hash": runtime.get("manifest_hash"),
            "vault_source_hash": (runtime.get("summary") or {}).get("source_hash") or anchor.get("vault_source_hash"),
            "vault_anchor_hash": anchor.get("integrity_hash"),
            "vault_verification_report_hash": external.get("integrity_hash"),
            "runtime_vault_verification_hash": runtime.get("integrity_hash"),
        }

    def _vault_evidence_paths(self, program_id: str, vault: ImplementationDocument) -> tuple[Path, Path, Path]:
        candidates = (
            Path(str(vault.get("vault_zip_path") or "")),
            Path(str(vault.get("vault_anchor_path") or "")),
            Path(str(vault.get("vault_verification_report_path") or "")),
        )
        defaults = (
            self.vault_store.zip_path(program_id),
            self.vault_store.anchor_path(program_id),
            self.vault_store.verification_report_path(program_id),
        )
        resolved: list[Path] = []
        for candidate, default in zip(candidates, defaults, strict=True):
            resolved.append(candidate if candidate.exists() and candidate.is_file() else default)
        return resolved[0], resolved[1], resolved[2]

    def _signed_archive_docs(self, program_id: str) -> ImplementationDocument:
        state = self.latest_signoff_state(program_id)
        if not state.get("signed"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations must be signed before archive export.")
        signoff = _read_optional_json(self.signoff_path(program_id))
        binding = _read_optional_json(self.signoff_binding_path(program_id))
        if not signoff or not binding:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signoff and binding are required.")
        registry = self._read_registry(program_id)
        policy = self._read_policy(program_id)
        review = self._read_latest_review(program_id)
        transfer = self._read_transfer(program_id)
        report = _read_optional_json(self.report_path(program_id))
        rotation = _read_optional_json(self.rotation_plan_path(program_id)) or _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_rotation_plan", "program_id": program_id, "status": "not_required", "actions": []})
        if not _integrity_ok(signoff) or not _integrity_ok(binding) or not _integrity_ok(report):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signed documents integrity failed.")
        if signoff.get("integrity_hash") != state.get("signoff_hash") or binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signoff does not match signed history.")
        if binding.get("latest_history_event_hash") != state.get("event_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signoff binding does not match latest history event.")
        expected = {
            "report_hash": report.get("integrity_hash"),
            "registry_hash": registry.get("integrity_hash"),
            "policy_hash": policy.get("integrity_hash"),
            "latest_review_hash": review.get("integrity_hash"),
            "transfer_report_hash": transfer.get("integrity_hash"),
        }
        for key, value in expected.items():
            if signoff.get(key) != value or binding.get(key) != value:
                raise UnifiedReleaseProgramVaultOperationsStateError(f"Vault Operations signed binding mismatch: {key}.")
        context = self._current_registry_vault_binding(program_id, registry)
        if context["blockers"]:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations current Vault binding failed: " + ", ".join(context["blockers"]))
        vault = context["vault"]
        vault_expected = {
            "vault_zip_sha256": vault.get("vault_zip_sha256"),
            "vault_zip_size_bytes": vault.get("vault_zip_size_bytes"),
            "vault_manifest_hash": vault.get("vault_manifest_hash"),
            "vault_anchor_hash": vault.get("vault_anchor_hash"),
            "vault_verification_report_hash": vault.get("vault_verification_report_hash"),
        }
        for key, value in vault_expected.items():
            if binding.get(key) != value:
                raise UnifiedReleaseProgramVaultOperationsStateError(f"Vault Operations signed Vault binding mismatch: {key}.")
        return {"report": report, "registry": registry, "policy": policy, "review": review, "rotation": rotation, "transfer": transfer, "signoff": signoff, "binding": binding, "current_vault": vault}

    def _current_registry_vault_binding(self, program_id: str, registry: ImplementationDocument) -> ImplementationDocument:
        current = self._current_generation(registry)
        if not current:
            raise UnifiedReleaseProgramVaultOperationsStateError("A current Vault generation is required.")
        vault = _as_document(current.get("vault"))
        if not vault:
            raise UnifiedReleaseProgramVaultOperationsStateError("Current Vault generation binding is missing.")
        vault_zip, vault_anchor, vault_verification = self._vault_evidence_paths(program_id, vault)
        for label, path in (("Vault ZIP", vault_zip), ("Vault anchor", vault_anchor), ("Vault verification report", vault_verification)):
            if not path.exists() or not path.is_file():
                raise UnifiedReleaseProgramVaultOperationsStateError(f"{label} is missing: {path}")
        runtime = verify_unified_release_program_vault_package(
            vault_zip,
            strict=True,
            deep=True,
            require_anchor=True,
            vault_anchor_path=vault_anchor,
            require_accepted_evidence=True,
        )
        external = read_json(vault_verification)
        anchor = read_json(vault_anchor)
        blockers = self._current_registry_vault_blockers(vault, vault_zip, runtime, external, anchor)
        return {
            "current": current,
            "vault": vault,
            "vault_zip": vault_zip,
            "vault_anchor": vault_anchor,
            "vault_verification": vault_verification,
            "runtime": runtime,
            "external": external,
            "anchor": anchor,
            "blockers": blockers,
        }

    def _current_registry_vault_blockers(self, vault: ImplementationDocument, vault_zip: Path, runtime: ImplementationDocument, external: ImplementationDocument, anchor: ImplementationDocument) -> list[str]:
        blockers: list[str] = []
        if runtime.get("status") != "passed":
            blockers.append("runtime_vault_verification_failed")
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE:
            blockers.append("external_vault_verification_package_type")
        if anchor.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE:
            blockers.append("vault_anchor_package_type")
        if external.get("status") != "passed" or not _integrity_ok(external):
            blockers.append("external_vault_verification_failed")
        if not _integrity_ok(anchor):
            blockers.append("vault_anchor_integrity_failed")
        current_zip_hash = _sha256_path(vault_zip)
        current_zip_size = vault_zip.stat().st_size if vault_zip.exists() else None
        expected = {
            "vault_zip_sha256": current_zip_hash,
            "vault_zip_size_bytes": current_zip_size,
            "vault_manifest_hash": runtime.get("manifest_hash"),
            "vault_anchor_hash": anchor.get("integrity_hash"),
            "vault_verification_report_hash": external.get("integrity_hash"),
        }
        for key, value in expected.items():
            if vault.get(key) != value:
                blockers.append(f"registry_current_{key}")
        if external.get("zip_sha256") != current_zip_hash or external.get("zip_sha256") != runtime.get("zip_sha256"):
            blockers.append("external_vault_verification_zip_sha256")
        if external.get("manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("external_vault_verification_manifest_hash")
        if anchor.get("vault_zip_sha256") != current_zip_hash or anchor.get("vault_zip_sha256") != runtime.get("zip_sha256"):
            blockers.append("vault_anchor_zip_sha256")
        if int(anchor.get("vault_zip_size_bytes") or -1) != int(current_zip_size or -2):
            blockers.append("vault_anchor_zip_size")
        if anchor.get("vault_manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("vault_anchor_manifest_hash")
        vault_source = (runtime.get("summary") or {}).get("source_hash") or anchor.get("vault_source_hash")
        if vault.get("vault_source_hash") and vault_source and vault.get("vault_source_hash") != vault_source:
            blockers.append("registry_current_vault_source_hash")
        if vault.get("runtime_vault_verification_hash") and runtime.get("integrity_hash") and vault.get("runtime_vault_verification_hash") != runtime.get("integrity_hash"):
            blockers.append("registry_current_runtime_vault_verification_hash")
        return sorted(set(blockers))

    def _append_history(self, program_id: str, event: ImplementationDocument) -> ImplementationDocument:
        path = self.history_path(program_id)
        chain = HistoryChain(path, sanitizer=lambda value: sanitize_metadata(value, blocked_keys=VAULT_OPERATIONS_BLOCKED_METADATA_KEYS))
        return chain.append({**event, "event_index": len(chain.read()) + 1})

    def _next_review_id(self, program_id: str) -> str:
        base = self.ops_dir(program_id) / "custody-review-runs"
        count = len([path for path in base.glob("vault-review-*") if path.is_dir()]) if base.exists() else 0
        return f"vault-review-{count + 1:06d}"


def _signoff_binding_document(program_id: str, signoff: ImplementationDocument, event: ImplementationDocument, report: ImplementationDocument, registry: ImplementationDocument, policy: ImplementationDocument, review: ImplementationDocument, transfer: ImplementationDocument) -> ImplementationDocument:
    current = next((row for row in registry.get("generations", []) if isinstance(row, dict) and row.get("generation_id") == registry.get("current_generation_id")), {})
    vault = _as_document(current.get("vault"))
    return _with_integrity(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_vault_operations_signoff_binding_summary",
            "program_id": program_id,
            "status": "signed",
            "signed_by": signoff.get("signed_by"),
            "role": signoff.get("role"),
            "reason": signoff.get("reason"),
            "signed_at": signoff.get("signed_at"),
            "signoff_hash": signoff.get("integrity_hash"),
            "signoff_payload_hash": signoff.get("payload_hash"),
            "latest_history_event_hash": event.get("event_hash"),
            "latest_history_payload_hash": event.get("payload_hash"),
            "report_hash": report.get("integrity_hash"),
            "registry_hash": registry.get("integrity_hash"),
            "policy_hash": policy.get("integrity_hash"),
            "latest_review_hash": review.get("integrity_hash"),
            "transfer_report_hash": transfer.get("integrity_hash"),
            "current_generation_id": registry.get("current_generation_id"),
            "vault_zip_sha256": vault.get("vault_zip_sha256"),
            "vault_zip_size_bytes": vault.get("vault_zip_size_bytes"),
            "vault_manifest_hash": vault.get("vault_manifest_hash"),
            "vault_anchor_hash": vault.get("vault_anchor_hash"),
            "vault_verification_report_hash": vault.get("vault_verification_report_hash"),
        }
    )


def _archive_manifest_document(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    source = {
        "report_hash": docs["report"].get("integrity_hash"),
        "registry_hash": docs["registry"].get("integrity_hash"),
        "policy_hash": docs["policy"].get("integrity_hash"),
        "latest_review_hash": docs["review"].get("integrity_hash"),
        "rotation_plan_hash": docs["rotation"].get("integrity_hash"),
        "transfer_report_hash": docs["transfer"].get("integrity_hash"),
        "signoff_hash": docs["signoff"].get("integrity_hash"),
        "signoff_binding_hash": docs["binding"].get("integrity_hash"),
        "vault_zip_sha256": docs["current_vault"].get("vault_zip_sha256"),
        "vault_anchor_hash": docs["current_vault"].get("vault_anchor_hash"),
        "vault_verification_report_hash": docs["current_vault"].get("vault_verification_report_hash"),
    }
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=VAULT_OPERATIONS_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _recipient_guide(program_id: str, transfer: ImplementationDocument) -> str:
    return "\n".join(
        [
            "# Unified Release Program Vault Transfer",
            "",
            f"Program: {program_id}",
            f"Transfer: {transfer.get('transfer_id') or 'pending'}",
            "",
            "Verify the Vault Operations Archive before storing or mirroring the Vault.",
            "",
        ]
    )


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _read_history(path: Path) -> list[ImplementationDocument]:
    return HistoryChain(path).read()


def _json_line(doc: ImplementationDocument) -> str:
    import json

    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sanitize_payload(payload: ImplementationDocument) -> ImplementationDocument:
    for forbidden in ("source_path", "local_path", "file_path"):
        if payload.get(forbidden):
            raise UnifiedReleaseProgramVaultOperationsStateError(f"{forbidden} is not allowed for Vault Operations.")
    return payload


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(
        sanitize_metadata(doc, blocked_keys=VAULT_OPERATIONS_BLOCKED_METADATA_KEYS),
        payload_hash=False,
    )


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _safe_id(value: str) -> str:
    import re

    value = sanitize_sensitive_text(str(value or "")).strip()
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value[:120] or "item"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
