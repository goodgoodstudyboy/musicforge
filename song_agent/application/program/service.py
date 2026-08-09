from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from song_agent.platform.contracts.documents import JsonDocument
from song_agent.domains.program.model import ProgramComponent


class ProgramUseCasePort(Protocol):
    def list_programs(self) -> list[JsonDocument]: ...

    def create_program(self, payload: JsonDocument | None = None) -> JsonDocument: ...

    def get_program(self, program_id: str) -> JsonDocument: ...


class ProgramApplicationService:
    """Typed use-case boundary for active Program workflows."""

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
    def from_components(cls, **components: object) -> ProgramApplicationService:
        return cls(components)

    def component(self, component: ProgramComponent | str) -> object:
        return self._components[ProgramComponent(component)]

    def list_programs(self) -> list[JsonDocument]:
        return self._program_store().list_programs()

    def create_program(self, payload: JsonDocument | None = None) -> JsonDocument:
        return self._program_store().create_program(payload)

    def get_program(self, program_id: str) -> JsonDocument:
        return self._program_store().get_program(program_id)

    def evaluate_gate(self, program_id: str, payload: JsonDocument) -> JsonDocument:
        from song_agent.application.program.policy_gate import ProgramGatePort, ProgramPolicyGate

        store = cast(ProgramGatePort, self.component(ProgramComponent.PROGRAM))
        return ProgramPolicyGate(store).evaluate(program_id, payload)

    def dispatch_http(self, port: object, method: str, path: str) -> None:
        from song_agent.application.program.http import ProgramHttpApplication

        ProgramHttpApplication(self, port).dispatch(method, path)

    def _program_store(self) -> ProgramUseCasePort:
        return cast(ProgramUseCasePort, self.component(ProgramComponent.PROGRAM))
