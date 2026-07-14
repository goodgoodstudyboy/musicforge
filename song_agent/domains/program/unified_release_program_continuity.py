from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder, HistoryChain, SignoffService
from song_agent.platform.persistence import WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade
from song_agent.platform.time import now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata, sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_verifier import (
    REQUIRED_ENTRIES,
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
    verify_unified_release_program_continuity_package,
    write_unified_release_program_continuity_verification_report,
)
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore
from song_agent.domains.program.unified_release_program_vault_operations_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_operations_package,
)


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


class UnifiedReleaseProgramContinuityError(ValueError):
    pass


class UnifiedReleaseProgramContinuityNotFoundError(UnifiedReleaseProgramContinuityError):
    pass


class UnifiedReleaseProgramContinuityStateError(UnifiedReleaseProgramContinuityError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityStateError)


class UnifiedReleaseProgramContinuityStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.vault_operations_store = UnifiedReleaseProgramVaultOperationsStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

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

    def get_continuity(self, program_id: str) -> dict[str, Any]:
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

    def init_policy(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def create_recovery_plan(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def run_recovery_drill(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def refresh_readiness(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def generate_runbook(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def signoff_continuity(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def export_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
            files: list[dict[str, Any]] = []

            def write_doc(rel: str, value: dict[str, Any] | str) -> None:
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

    def build_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
        **_: Any,
    ) -> dict[str, Any]:
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

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        events = _read_history(self.history_path(program_id))
        signoffs = [row for row in events if row.get("event_type") == "continuity_signoff_created"]
        if not signoffs:
            return {"status": "unsigned", "signed": False}
        latest = signoffs[-1]
        return {"status": "signed", "signed": True, "signoff_hash": latest.get("signoff_hash"), "event_hash": latest.get("event_hash"), "event_index": latest.get("event_index")}

    def _ensure_unsigned(self, program_id: str) -> None:
        if self.latest_signoff_state(program_id).get("signed"):
            raise UnifiedReleaseProgramContinuityStateError("Unified Release Program Continuity is signed. Create a successor continuity record before mutation.")

    def _evidence_paths(self, program_id: str, payload: dict[str, Any]) -> dict[str, Path]:
        local = _read_optional_json(self.local_evidence_manifest_path(program_id))
        return {
            "archive_path": Path(payload.get("vault_operations_archive") or local.get("vault_operations_archive") or self.vault_operations_store.archive_zip_path(program_id)),
            "verification_report_path": Path(payload.get("vault_operations_verification_report") or local.get("vault_operations_verification_report") or self.vault_operations_store.verification_report_path(program_id)),
            "signoff_binding_path": Path(payload.get("vault_operations_signoff_binding") or local.get("vault_operations_signoff_binding") or self.vault_operations_store.signoff_binding_path(program_id)),
        }

    def _vault_operations_context(self, program_id: str, payload: dict[str, Any], *, require_passed: bool) -> dict[str, Any]:
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

    def _write_evidence_manifests(self, program_id: str, context: dict[str, Any], payload: dict[str, Any]) -> None:
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

    def _signed_archive_docs(self, program_id: str) -> dict[str, Any]:
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

    def _assert_export_dir_matches_signed_docs(self, program_id: str, docs: dict[str, Any]) -> None:
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
        source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
        expected_source = _archive_manifest_document(program_id, docs, []).get("source") or {}
        for key, value in expected_source.items():
            if source.get(key) != value:
                raise UnifiedReleaseProgramContinuityStateError(f"Continuity Archive manifest source mismatch: {key}.")

    def _write_continuity_report(self, program_id: str, policy: dict[str, Any], plan: dict[str, Any], drill: dict[str, Any], readiness: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
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

    def _write_redaction_report(self, program_id: str) -> dict[str, Any]:
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

    def _read_policy(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.policy_path(program_id), "Continuity policy")

    def _read_plan(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.recovery_plan_path(program_id), "Recovery plan")

    def _read_drill(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.drill_report_path(program_id), "Recovery drill report")

    def _read_readiness(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.readiness_path(program_id), "Continuity readiness")

    def _read_runbook(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.runbook_path(program_id), "Continuity runbook")

    def _read_report(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.report_path(program_id), "Continuity report")

    def _read_external_evidence_manifest(self, program_id: str) -> dict[str, Any]:
        return _read_required_doc(self.external_evidence_manifest_path(program_id), "Continuity external evidence manifest")

    def _append_history(self, program_id: str, event: dict[str, Any]) -> dict[str, Any]:
        path = self.history_path(program_id)
        chain = HistoryChain(path, sanitizer=lambda value: sanitize_metadata(value, blocked_keys=CONTINUITY_BLOCKED_METADATA_KEYS))
        return chain.append({**event, "event_index": len(chain.read()) + 1})

    def _history_has(self, program_id: str, event_type: str) -> bool:
        return any(row.get("event_type") == event_type for row in _read_history(self.history_path(program_id)))


def _source_binding_from_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "vault_operations_archive_sha256": _sha256_path(context["archive_path"]),
        "vault_operations_archive_size_bytes": context["archive_path"].stat().st_size if context["archive_path"].exists() else None,
        "vault_operations_manifest_hash": context["runtime"].get("manifest_hash"),
        "vault_operations_verification_report_hash": context["external"].get("integrity_hash"),
        "vault_operations_runtime_verification_hash": context["runtime"].get("integrity_hash"),
        "vault_operations_signoff_binding_hash": context["signoff_binding"].get("integrity_hash"),
        "vault_operations_signoff_hash": context["signoff_binding"].get("signoff_hash"),
    }


def _signoff_binding_document(program_id: str, signoff: dict[str, Any], event: dict[str, Any], policy: dict[str, Any], plan: dict[str, Any], drill: dict[str, Any], readiness: dict[str, Any], runbook: dict[str, Any], report: dict[str, Any], evidence_manifest: dict[str, Any]) -> dict[str, Any]:
    source = {key: signoff.get(key) for key in signoff if key.startswith("vault_operations_")}
    return _with_integrity(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_continuity_signoff_binding_summary",
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
            "policy_hash": policy.get("integrity_hash"),
            "recovery_plan_hash": plan.get("integrity_hash"),
            "drill_report_hash": drill.get("integrity_hash"),
            "readiness_hash": readiness.get("integrity_hash"),
            "runbook_hash": runbook.get("integrity_hash"),
            "continuity_report_hash": report.get("integrity_hash"),
            "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
            **source,
        }
    )


def _archive_manifest_document(program_id: str, docs: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    source = {
        "policy_hash": docs["policy"].get("integrity_hash"),
        "recovery_plan_hash": docs["plan"].get("integrity_hash"),
        "drill_report_hash": docs["drill"].get("integrity_hash"),
        "readiness_hash": docs["readiness"].get("integrity_hash"),
        "runbook_hash": docs["runbook"].get("integrity_hash"),
        "continuity_report_hash": docs["report"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["evidence_manifest"].get("integrity_hash"),
        "signoff_hash": docs["signoff"].get("integrity_hash"),
        "signoff_binding_hash": docs["binding"].get("integrity_hash"),
        "vault_operations_archive_sha256": docs["binding"].get("vault_operations_archive_sha256"),
        "vault_operations_archive_size_bytes": docs["binding"].get("vault_operations_archive_size_bytes"),
        "vault_operations_manifest_hash": docs["binding"].get("vault_operations_manifest_hash"),
        "vault_operations_verification_report_hash": docs["binding"].get("vault_operations_verification_report_hash"),
        "vault_operations_signoff_binding_hash": docs["binding"].get("vault_operations_signoff_binding_hash"),
    }
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=CONTINUITY_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _read_required_doc(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise UnifiedReleaseProgramContinuityNotFoundError(f"{label} is missing.")
    doc = read_json(path)
    if not _integrity_ok(doc):
        raise UnifiedReleaseProgramContinuityStateError(f"{label} integrity failed.")
    return doc


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def _read_history(path: Path) -> list[dict[str, Any]]:
    return HistoryChain(path).read()


def _json_line(doc: dict[str, Any]) -> str:
    import json

    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for forbidden in ("source_path", "local_path", "file_path"):
        if payload.get(forbidden):
            raise UnifiedReleaseProgramContinuityStateError(f"{forbidden} is not allowed for Continuity.")
    return payload


def _with_integrity(doc: dict[str, Any]) -> dict[str, Any]:
    return SignoffService.seal(
        sanitize_metadata(doc, blocked_keys=CONTINUITY_BLOCKED_METADATA_KEYS),
        payload_hash=False,
    )


def _integrity_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: dict[str, Any]) -> bool:
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


def _file_record(path: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _safe_id(value: str) -> str:
    import re

    value = sanitize_sensitive_text(str(value or "")).strip()
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value[:120] or "item"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
