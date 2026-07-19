from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class ArtifactRef:
    kind: str
    path: str
    description: str = ""

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass
class RunState:
    run_id: str
    request: ImplementationDocument
    steps: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)

    def mark_step(self, step_name: str, status: StepStatus) -> None:
        self.steps[step_name] = status.value

    def add_artifact(self, name: str, artifact: ArtifactRef) -> None:
        self.artifacts[name] = artifact

    def to_dict(self) -> DomainDocument:
        return {
            "run_id": self.run_id,
            "request": self.request,
            "steps": self.steps,
            "artifacts": {
                name: artifact.to_dict() for name, artifact in self.artifacts.items()
            },
        }

    @classmethod
    def from_dict(cls, data: DomainDocument) -> RunState:
        artifacts = {
            name: ArtifactRef(**artifact)
            for name, artifact in data.get("artifacts", {}).items()
        }
        return cls(
            run_id=str(data["run_id"]),
            request=dict(data["request"]),
            steps=dict(data.get("steps", {})),
            artifacts=artifacts,
        )


__all__ = ["ArtifactRef", "RunState", "StepStatus"]
