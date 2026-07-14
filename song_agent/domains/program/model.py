from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ProgramComponent(StrEnum):
    PROGRAM = "program"
    OPERATIONS = "operations"
    HANDOFF = "handoff"
    VAULT = "vault"
    VAULT_OPERATIONS = "vault_operations"
    CONTINUITY = "continuity"
    CONTINUITY_DISTRIBUTION = "continuity_distribution"
    CONTINUITY_ACCEPTANCE = "continuity_acceptance"
    CONTINUITY_ACCEPTANCE_CHANGE = "continuity_acceptance_change"
    COMMAND_CENTER = "command_center"
    COMMAND_CENTER_SIGNOFF = "command_center_signoff"
    RECEIVER_ACCEPTANCE = "receiver_acceptance"
    RECEIVER_ACCEPTANCE_CHANGE = "receiver_acceptance_change"


@dataclass(frozen=True, slots=True)
class ProgramOperation:
    component: ProgramComponent
    action: str
    arguments: tuple[Any, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action or self.action.startswith("_"):
            raise ValueError("Program application actions must name a public operation.")


@dataclass(frozen=True, slots=True)
class ProgramResult:
    component: ProgramComponent
    action: str
    value: Any
