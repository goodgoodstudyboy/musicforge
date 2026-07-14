from __future__ import annotations

import ast
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LifecycleCapability:
    component_type: str
    module: str
    store_class: str
    signoff_method: str = ""
    reset_method: str = ""
    archive_method: str = ""
    required_services: tuple[str, ...] = ()

    def inventory(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "module": self.module,
            "store_class": self.store_class,
            "signoff_method": self.signoff_method,
            "reset_method": self.reset_method,
            "archive_method": self.archive_method,
            "required_services": list(self.required_services),
        }


class LifecycleCapabilityRegistry:
    def __init__(self, capabilities: tuple[LifecycleCapability, ...]) -> None:
        self._capabilities = capabilities
        identities = [row.component_type for row in capabilities]
        if len(identities) != len(set(identities)):
            raise ValueError("Lifecycle component identities must be unique.")

    def all(self) -> tuple[LifecycleCapability, ...]:
        return self._capabilities

    def inventory(self) -> list[dict[str, Any]]:
        return [row.inventory() for row in self._capabilities]

    def adoption_report(self) -> dict[str, Any]:
        rows = [_adoption_row(capability) for capability in self._capabilities]
        return {
            "schema_version": 1,
            "status": "passed" if all(row["status"] == "passed" for row in rows) else "failed",
            "rows": rows,
        }


def _lifecycle(
    component_type: str,
    module_leaf: str,
    store_class: str,
    *,
    signoff: str = "",
    reset: str = "",
    archive: str = "",
    services: tuple[str, ...],
) -> LifecycleCapability:
    return LifecycleCapability(
        component_type=component_type,
        module=f"song_agent.domains.program.{module_leaf}",
        store_class=store_class,
        signoff_method=signoff,
        reset_method=reset,
        archive_method=archive,
        required_services=services,
    )


ACTIVE_LIFECYCLE_CAPABILITIES = (
    _lifecycle("unified_release_program", "unified_release_program", "UnifiedReleaseProgramStore", signoff="signoff", archive="build_zip", services=("HistoryChain", "SignoffService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_operations", "unified_release_program_operations", "UnifiedReleaseProgramOperationsStore", reset="reset_program_signoff", archive="build_operations_archive_zip", services=("HistoryChain", "ChangeRequestService", "ResetService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_handoff", "unified_release_program_handoff", "UnifiedReleaseProgramHandoffStore", signoff="signoff_handoff", archive="build_handoff_archive_zip", services=("HistoryChain", "SignoffService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_vault", "unified_release_program_vault", "UnifiedReleaseProgramVaultStore", archive="build_vault_zip", services=("HistoryChain", "ArchiveBuilder")),
    _lifecycle("unified_release_program_vault_operations", "unified_release_program_vault_operations", "UnifiedReleaseProgramVaultOperationsStore", signoff="signoff_operations", archive="build_archive_zip", services=("HistoryChain", "SignoffService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_continuity", "unified_release_program_continuity", "UnifiedReleaseProgramContinuityStore", signoff="signoff_continuity", archive="build_archive_zip", services=("HistoryChain", "SignoffService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_continuity_kit", "unified_release_program_continuity_distribution", "UnifiedReleaseProgramContinuityDistributionStore", archive="build_kit_zip", services=("ArchiveBuilder",)),
    _lifecycle("unified_release_program_continuity_acceptance", "unified_release_program_continuity_acceptance", "UnifiedReleaseProgramContinuityAcceptanceStore", signoff="signoff_acceptance", archive="build_archive_zip", services=("HistoryChain", "SignoffService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_continuity_acceptance_change", "unified_release_program_continuity_acceptance_change", "UnifiedReleaseProgramContinuityAcceptanceChangeStore", reset="reset_acceptance_signoff", archive="build_archive_zip", services=("HistoryChain", "ChangeRequestService", "ResetService", "GenerationService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_continuity_command_center", "unified_release_program_continuity_command_center", "UnifiedReleaseProgramContinuityCommandCenterStore", archive="build_zip", services=("ArchiveBuilder",)),
    _lifecycle("unified_release_program_continuity_command_center_signoff", "unified_release_program_continuity_command_center_signoff", "UnifiedReleaseProgramContinuityCommandCenterSignoffStore", signoff="signoff", reset="reset_signoff", archive="build_archive_zip", services=("HistoryChain", "SignoffService", "ChangeRequestService", "ResetService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_receiver_acceptance", "unified_release_program_continuity_command_center_acceptance", "UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore", signoff="signoff", archive="build_archive_zip", services=("HistoryChain", "SignoffService", "ArchiveBuilder")),
    _lifecycle("unified_release_program_receiver_acceptance_change", "unified_release_program_continuity_command_center_acceptance_change", "UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore", reset="reset_receiver_acceptance_signoff", archive="build_archive_zip", services=("HistoryChain", "ChangeRequestService", "ResetService", "GenerationService", "ArchiveBuilder")),
)


active_lifecycle_registry = LifecycleCapabilityRegistry(ACTIVE_LIFECYCLE_CAPABILITIES)


def _adoption_row(capability: LifecycleCapability) -> dict[str, Any]:
    module = import_module(capability.module)
    store = getattr(module, capability.store_class)
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    call_owners = {
        node.func.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
    }
    call_owners.update(
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    missing_methods = [
        name
        for name in (capability.signoff_method, capability.reset_method, capability.archive_method)
        if name and not callable(getattr(store, name, None))
    ]
    missing_services = sorted(set(capability.required_services) - call_owners)
    return {
        **capability.inventory(),
        "status": "passed" if not missing_methods and not missing_services else "failed",
        "missing_methods": missing_methods,
        "missing_services": missing_services,
    }
