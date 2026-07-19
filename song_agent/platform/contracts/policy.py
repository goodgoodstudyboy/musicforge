from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class EvidenceRequirement:
    requirement_id: str
    component_types: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    minimum_count: int = 1
    description: str = ""


@dataclass(frozen=True)
class QuorumRequirement:
    requirement_id: str
    minimum_count: int = 1
    component_types: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class CurrentGenerationRequirement:
    required: bool = True


@dataclass(frozen=True)
class RuntimeVerificationRequirement:
    required: bool = True


@dataclass(frozen=True)
class NoBlockerRequirement:
    required: bool = True


@dataclass(frozen=True)
class PolicyProfile:
    policy_id: str
    description: str
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    quorum_requirements: tuple[QuorumRequirement, ...] = ()
    current_generation: CurrentGenerationRequirement = field(default_factory=CurrentGenerationRequirement)
    runtime_verification: RuntimeVerificationRequirement = field(default_factory=RuntimeVerificationRequirement)
    no_blockers: NoBlockerRequirement = field(default_factory=NoBlockerRequirement)
    schema_version: int = 1

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class GateResult:
    policy_id: str
    status: str
    checks: tuple[ImplementationDocument, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    graph_hash: str
    schema_version: int = 1

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> DomainDocument:
        return asdict(self)
