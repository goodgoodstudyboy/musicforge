from __future__ import annotations

import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso


AB_ID_PATTERN = re.compile(r"^ab-[0-9]{3,5}$")


@dataclass(frozen=True)
class PromptABExperiment:
    ab_id: str
    project_id: str
    parent_version_id: str
    instruction: str
    candidate_count: int
    template_ids: list[str]
    group_ids: list[str]
    status: str
    created_at: str
    updated_at: str
    notes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptABExperiment":
        return cls(
            ab_id=validate_ab_id(str(data.get("ab_id") or "")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            instruction=str(data.get("instruction") or ""),
            candidate_count=int(data.get("candidate_count") or 2),
            template_ids=[str(item) for item in data.get("template_ids", []) if str(item).strip()],
            group_ids=[str(item) for item in data.get("group_ids", []) if str(item).strip()],
            status=str(data.get("status") or "ready"),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            notes=dict(data.get("notes") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PromptABStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir)
        self.root = self.project_dir / "prompt-ab"
        self.lock = threading.RLock()

    def create_experiment(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        instruction: str,
        candidate_count: int,
        template_ids: list[str],
        group_ids: list[str],
        now: str | None = None,
    ) -> PromptABExperiment:
        now = now or now_iso()
        if len(template_ids) < 2 or len(group_ids) < 2:
            raise ValueError("Prompt A/B requires at least two templates and two groups.")
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            ab_id = self._next_ab_id()
            ab_dir = self.ab_dir(ab_id)
            ab_dir.mkdir(parents=True, exist_ok=False)
            experiment = PromptABExperiment(
                ab_id=ab_id,
                project_id=project_id,
                parent_version_id=parent_version_id,
                instruction=instruction,
                candidate_count=int(candidate_count),
                template_ids=list(template_ids),
                group_ids=list(group_ids),
                status="ready",
                created_at=now,
                updated_at=now,
            )
            write_json(ab_dir / "ab.json", experiment.to_dict())
            return experiment

    def read_experiment(self, ab_id: str) -> PromptABExperiment:
        ab_dir = self.ab_dir(ab_id)
        path = ab_dir / "ab.json"
        if not path.exists():
            raise FileNotFoundError(ab_id)
        return PromptABExperiment.from_dict(read_json(path))

    def list_experiments(self) -> list[PromptABExperiment]:
        if not self.root.exists():
            return []
        experiments = []
        for path in self.root.glob("*/ab.json"):
            try:
                experiments.append(PromptABExperiment.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError):
                continue
        return sorted(experiments, key=lambda item: item.created_at, reverse=True)

    def delete_experiment(self, ab_id: str) -> None:
        ab_dir = self.ab_dir(ab_id)
        if not ab_dir.exists():
            raise FileNotFoundError(ab_id)
        resolved = ab_dir.resolve()
        base = self.root.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to delete outside prompt-ab.") from exc
        if resolved.is_symlink():
            raise ValueError("Refusing to delete symlink prompt-ab experiment.")
        shutil.rmtree(resolved)

    def ab_dir(self, ab_id: str) -> Path:
        ab_id = validate_ab_id(ab_id)
        base = self.root.resolve()
        target = (base / ab_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside prompt-ab.") from exc
        return target

    def _next_ab_id(self) -> str:
        for index in range(1, 10_000):
            ab_id = f"ab-{index:03d}"
            if not (self.root / ab_id).exists():
                return ab_id
        raise RuntimeError("Could not allocate prompt A/B id.")


def validate_ab_id(ab_id: str) -> str:
    if not AB_ID_PATTERN.match(ab_id):
        raise ValueError("Invalid prompt A/B id.")
    return ab_id
