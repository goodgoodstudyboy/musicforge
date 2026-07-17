from __future__ import annotations

import json as json
import os as os
import re as re
import threading as threading
from dataclasses import dataclass as dataclass
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.state import RunState as RunState


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    data: Path
    renders: Path
    logs: Path

    @classmethod
    def create(cls, root: Path) -> "ProjectPaths":
        paths = cls(
            root=root,
            data=root / "data",
            renders=root / "renders",
            logs=root / "logs",
        )
        for path in (paths.data, paths.renders, paths.logs):
            path.mkdir(parents=True, exist_ok=True)
        return paths

    @property
    def events_path(self) -> Path:
        return self.logs / "events.jsonl"

    @property
    def summary_path(self) -> Path:
        return self.data / "run-summary.json"


def default_run_dir(request_title: str, runs_dir: Path = Path("runs")) -> Path:
    return runs_dir / slugify(request_title)


def unique_run_dir(request_title: str, runs_dir: Path = Path("runs")) -> Path:
    base_dir = default_run_dir(request_title, runs_dir)
    if not base_dir.exists():
        return base_dir

    index = 2
    while True:
        candidate = base_dir.with_name(f"{base_dir.name}-{index}")
        if not candidate.exists():
            return candidate
        index += 1


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "song-run"


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".tmp-{os.getpid()}-{threading.get_ident()}.json")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_event(paths: ProjectPaths, event: dict[str, Any]) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    paths.events_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.events_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_run_state(paths: ProjectPaths, state: RunState) -> Path:
    return write_json(paths.summary_path, state.to_dict())


def read_run_state(paths: ProjectPaths) -> RunState:
    return RunState.from_dict(read_json(paths.summary_path))
