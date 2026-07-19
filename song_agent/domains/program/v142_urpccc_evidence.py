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

_gap_actions = _make_deferred_global('_gap_actions')
_safe_actions = _make_deferred_global('_safe_actions')
ctx = _make_deferred_global('ctx')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global _gap_actions, _safe_actions, ctx, item
    _gap_actions = namespace.get('_gap_actions', _gap_actions)
    _safe_actions = namespace.get('_safe_actions', _safe_actions)
    ctx = namespace.get('ctx', ctx)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


COMMAND_CENTER_COMPONENTS = (
    "evidence_vault",
    "vault_operations",
    "continuity_recovery",
    "continuity_distribution_kit",
    "continuity_acceptance_board",
    "continuity_acceptance_change_control",
)




class UnifiedReleaseProgramContinuityCommandCenterStoreEvidenceMixin:
    def _build_documents(self, program_id: str, contexts: list[DomainDocument]) -> DomainDocument:
        inventory_rows = [ctx["row"] for ctx in contexts]
        runtime_rows = [
            {
                "component_type": ctx["row"]["component_type"],
                "component_id": ctx["row"]["component_id"],
                "status": ctx["runtime"].get("status"),
                "report_status": ctx["row"].get("report_status"),
                "runtime_status": ctx["runtime"].get("status"),
                "runtime_blockers": ctx["row"].get("runtime_blockers") or [],
                "blockers": ctx["row"].get("runtime_blockers") or [],
                "zip_sha256": ctx["row"].get("zip_sha256"),
                "zip_size_bytes": ctx["row"].get("zip_size_bytes"),
                "manifest_hash": ctx["row"].get("manifest_hash"),
                "verification_report_hash": ctx["row"].get("verification_report_hash"),
                "generation": ctx["row"].get("generation"),
                "current": ctx["row"].get("current"),
                "integrity_hash": ctx["runtime"].get("integrity_hash"),
            }
            for ctx in contexts
        ]
        readiness_rows = []
        blockers: list[str] = []
        warnings: list[str] = []
        for row in inventory_rows:
            ready = row.get("status") == "passed"
            readiness_rows.append(
                {
                    "component_type": row.get("component_type"),
                    "component_id": row.get("component_id"),
                    "status": "ready" if ready else row.get("evidence_status") or "blocked",
                    "blockers": row.get("blockers") or [],
                    "report_status": row.get("report_status"),
                    "runtime_status": row.get("runtime_status"),
                    "runtime_blockers": row.get("runtime_blockers") or [],
                    "external_status": row.get("external_status"),
                    "generation": row.get("generation"),
                    "current": row.get("current"),
                }
            )
            blockers.extend(str(item) for item in (row.get("blockers") or []))
        generation = _read_optional_json(self.change_store.current_generation_path(program_id))
        acceptance_state = self.acceptance_store.latest_signoff_state(program_id)
        if acceptance_state.get("status") != "signed":
            blockers.append("continuity_acceptance_reset_pending")
        status = "ready" if not blockers else "blocked"
        now = now_iso()
        acceptance_event = _as_document(acceptance_state.get("event"))
        current_state = {
            "generation": generation.get("generation"),
            "generation_hash": generation.get("integrity_hash"),
            "acceptance_status": acceptance_state.get("status") or "unsigned",
            "acceptance_signoff_hash": acceptance_state.get("signoff_hash"),
            "acceptance_history_event_hash": acceptance_event.get("event_hash"),
            "current": acceptance_state.get("status") == "signed",
        }
        local_manifest = {
            "schema_version": 1,
            "package_type": "musicforge_unified_release_program_continuity_command_center_external_evidence_manifest",
            "program_id": program_id,
            "created_at": now,
            "current_state": {
                **current_state,
                "generation_path": str(self.change_store.current_generation_path(program_id)),
                "acceptance_history_path": str(self.acceptance_store.history_path(program_id)),
            },
            "items": [ctx["local_row"] for ctx in contexts],
            "summary": {"component_count": len(contexts), "failed_count": sum(1 for ctx in contexts if ctx["row"].get("status") != "passed")},
        }
        local_manifest["integrity_hash"] = _integrity_hash(local_manifest)
        public_manifest = _with_integrity(
            {
                "schema_version": 1,
                "package_type": "musicforge_unified_release_program_continuity_command_center_external_evidence_manifest",
                "program_id": program_id,
                "created_at": now,
                "current_state": current_state,
                "items": inventory_rows,
                "summary": local_manifest.get("summary"),
            }
        )
        inventory = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_evidence_inventory", "program_id": program_id, "created_at": now, "items": inventory_rows, "summary": public_manifest.get("summary")})
        runtime_index = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_runtime_verification_index", "program_id": program_id, "created_at": now, "items": runtime_rows, "summary": {"passed_count": sum(1 for row in runtime_rows if row.get("status") == "passed"), "failed_count": sum(1 for row in runtime_rows if row.get("status") != "passed")}})
        readiness = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_readiness_matrix", "program_id": program_id, "status": status, "created_at": now, "rows": readiness_rows, "blockers": sorted(set(blockers)), "warnings": sorted(set(warnings))})
        gap_plan = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_gap_plan", "program_id": program_id, "status": "clear" if status == "ready" else "action_required", "created_at": now, "actions": _gap_actions(readiness_rows)})
        runbook = _with_integrity({"schema_version": 1, "package_type": "musicforge_unified_release_program_continuity_command_center_safe_runbook", "program_id": program_id, "status": "ready", "created_at": now, "actions": _safe_actions(readiness_rows)})
        report = _with_integrity(
            {
                "schema_version": 1,
                "package_type": "musicforge_unified_release_program_continuity_command_center_report",
                "program_id": program_id,
                "status": status,
                "created_at": now,
                "current_generation": generation.get("generation"),
                "current_generation_status": "current_signed" if acceptance_state.get("status") == "signed" else "reset_pending",
                "stored_generation_status": generation.get("status"),
                "current_acceptance_signoff_hash": acceptance_state.get("signoff_hash"),
                "current_acceptance_history_event_hash": acceptance_event.get("event_hash"),
                "evidence_inventory_hash": inventory.get("integrity_hash"),
                "readiness_matrix_hash": readiness.get("integrity_hash"),
                "runtime_verification_index_hash": runtime_index.get("integrity_hash"),
                "gap_plan_hash": gap_plan.get("integrity_hash"),
                "safe_runbook_hash": runbook.get("integrity_hash"),
                "external_evidence_manifest_hash": public_manifest.get("integrity_hash"),
                "summary": {
                    "component_count": len(contexts),
                    "ready_count": sum(1 for row in readiness_rows if row.get("status") == "ready"),
                    "blocked_count": sum(1 for row in readiness_rows if row.get("status") != "ready"),
                    "blocker_count": len(set(blockers)),
                },
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "tool": {"name": "MusicForge Unified Release Program Continuity Command Center", "version": __version__},
            }
        )
        return {
            "report": report,
            "inventory": inventory,
            "readiness": readiness,
            "runtime_index": runtime_index,
            "gap_plan": gap_plan,
            "runbook": runbook,
            "external_manifest": public_manifest,
            "local_evidence_manifest": local_manifest,
        }
