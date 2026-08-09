from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document


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

    def to_dict(self) -> JsonDocument:
        return {"kind": self.kind, "path": self.path, "description": self.description}


@dataclass
class RunState:
    run_id: str
    request: JsonDocument
    steps: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)

    def mark_step(self, step_name: str, status: StepStatus) -> None:
        self.steps[step_name] = status.value

    def add_artifact(self, name: str, artifact: ArtifactRef) -> None:
        self.artifacts[name] = artifact

    def to_dict(self) -> JsonDocument:
        return normalize_json_document({
            "run_id": self.run_id,
            "request": self.request,
            "steps": self.steps,
            "artifacts": {
                name: artifact.to_dict() for name, artifact in self.artifacts.items()
            },
        })

    @classmethod
    def from_dict(cls, data: JsonDocument) -> RunState:
        artifact_rows = data.get("artifacts")
        artifacts: dict[str, ArtifactRef] = {}
        if isinstance(artifact_rows, dict):
            for name, artifact in artifact_rows.items():
                if not isinstance(artifact, dict):
                    continue
                artifacts[name] = ArtifactRef(
                    kind=str(artifact.get("kind") or ""),
                    path=str(artifact.get("path") or ""),
                    description=str(artifact.get("description") or ""),
                )
        request = data.get("request")
        steps = data.get("steps")
        return cls(
            run_id=str(data["run_id"]),
            request=normalize_json_document(request) if isinstance(request, dict) else {},
            steps=(
                dict(zip(map(str, steps.keys()), map(str, steps.values()), strict=True))
                if isinstance(steps, dict)
                else {}
            ),
            artifacts=artifacts,
        )


__all__ = ["ArtifactRef", "RunState", "StepStatus"]
