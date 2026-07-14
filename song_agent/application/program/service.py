from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from song_agent.domains.program.model import ProgramComponent, ProgramOperation, ProgramResult
from song_agent.domains.program.ports import ProgramReleaseStore
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity import UnifiedReleaseProgramContinuityStore
from song_agent.domains.program.unified_release_program_continuity_acceptance import (
    UnifiedReleaseProgramContinuityAcceptanceStore,
)
from song_agent.domains.program.unified_release_program_continuity_acceptance_change import (
    UnifiedReleaseProgramContinuityAcceptanceChangeStore,
)
from song_agent.domains.program.unified_release_program_continuity_command_center import (
    UnifiedReleaseProgramContinuityCommandCenterStore,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff import (
    UnifiedReleaseProgramContinuityCommandCenterSignoffStore,
)
from song_agent.domains.program.unified_release_program_continuity_distribution import (
    UnifiedReleaseProgramContinuityDistributionStore,
)
from song_agent.domains.program.unified_release_program_handoff import UnifiedReleaseProgramHandoffStore
from song_agent.domains.program.unified_release_program_operations import UnifiedReleaseProgramOperationsStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_operations import (
    UnifiedReleaseProgramVaultOperationsStore,
)


class ProgramApplicationService:
    """Composition root and operation boundary for active Program workflows."""

    def __init__(self, components: Mapping[ProgramComponent | str, object]) -> None:
        self._components = {
            ProgramComponent(key): value
            for key, value in components.items()
        }
        missing = set(ProgramComponent) - set(self._components)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"Program application components are missing: {names}")

    @classmethod
    def build(
        cls,
        *,
        release_store: ProgramReleaseStore | None = None,
        root: Path | None = None,
    ) -> ProgramApplicationService:
        program = UnifiedReleaseProgramStore(release_store=release_store, root=root)
        return cls(
            {
                ProgramComponent.PROGRAM: program,
                ProgramComponent.OPERATIONS: UnifiedReleaseProgramOperationsStore(program),
                ProgramComponent.HANDOFF: UnifiedReleaseProgramHandoffStore(program),
                ProgramComponent.VAULT: UnifiedReleaseProgramVaultStore(program),
                ProgramComponent.VAULT_OPERATIONS: UnifiedReleaseProgramVaultOperationsStore(program),
                ProgramComponent.CONTINUITY: UnifiedReleaseProgramContinuityStore(program),
                ProgramComponent.CONTINUITY_DISTRIBUTION: UnifiedReleaseProgramContinuityDistributionStore(program),
                ProgramComponent.CONTINUITY_ACCEPTANCE: UnifiedReleaseProgramContinuityAcceptanceStore(program),
                ProgramComponent.CONTINUITY_ACCEPTANCE_CHANGE: UnifiedReleaseProgramContinuityAcceptanceChangeStore(program),
                ProgramComponent.COMMAND_CENTER: UnifiedReleaseProgramContinuityCommandCenterStore(program),
                ProgramComponent.COMMAND_CENTER_SIGNOFF: UnifiedReleaseProgramContinuityCommandCenterSignoffStore(program),
                ProgramComponent.RECEIVER_ACCEPTANCE: UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore(program),
                ProgramComponent.RECEIVER_ACCEPTANCE_CHANGE: UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore(program),
            }
        )

    @classmethod
    def from_components(cls, **components: object) -> ProgramApplicationService:
        return cls(components)

    def component(self, component: ProgramComponent | str) -> Any:
        return self._components[ProgramComponent(component)]

    def execute(self, operation: ProgramOperation) -> ProgramResult:
        target = self.component(operation.component)
        action = getattr(target, operation.action, None)
        if operation.action.startswith("_") or not callable(action):
            raise ValueError(
                f"Unsupported Program operation: {operation.component.value}.{operation.action}"
            )
        value = action(*operation.arguments, **dict(operation.options))
        return ProgramResult(operation.component, operation.action, value)

    def invoke(
        self,
        component: ProgramComponent | str,
        action: str,
        *arguments: Any,
        **options: Any,
    ) -> Any:
        operation = ProgramOperation(ProgramComponent(component), action, arguments, options)
        return self.execute(operation).value

    def dispatch_http(self, port: object, method: str, path: str) -> None:
        from song_agent.application.program.http import ProgramHttpApplication

        ProgramHttpApplication(self, port).dispatch(method, path)
