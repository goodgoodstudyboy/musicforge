from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunState:
    run_id: str
    request: dict[str, Any]
    steps: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)

    def mark_step(self, step_name: str, status: StepStatus) -> None:
        self.steps[step_name] = status.value

    def add_artifact(self, name: str, artifact: ArtifactRef) -> None:
        self.artifacts[name] = artifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "request": self.request,
            "steps": self.steps,
            "artifacts": {
                name: artifact.to_dict() for name, artifact in self.artifacts.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
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
