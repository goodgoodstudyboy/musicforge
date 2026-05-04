from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from song_agent.projectio import ProjectPaths, append_event, read_run_state, write_run_state
from song_agent.state import RunState, StepStatus


StepFn = Callable[[RunState, ProjectPaths], None]


@dataclass(frozen=True)
class PipelineStep:
    name: str
    output_path: Path | None
    run: StepFn


class GraphRunner:
    def __init__(self, steps: list[PipelineStep], *, resume: bool = False) -> None:
        self.steps = steps
        self.resume = resume

    def run(self, state: RunState, paths: ProjectPaths) -> RunState:
        if self.resume and paths.summary_path.exists():
            state = read_run_state(paths)

        for step in self.steps:
            if self.resume and step.output_path and step.output_path.exists():
                state.mark_step(step.name, StepStatus.SKIPPED)
                append_event(paths, {"step": step.name, "status": StepStatus.SKIPPED})
                write_run_state(paths, state)
                continue

            state.mark_step(step.name, StepStatus.RUNNING)
            append_event(paths, {"step": step.name, "status": StepStatus.RUNNING})
            write_run_state(paths, state)

            try:
                step.run(state, paths)
            except Exception as exc:
                state.mark_step(step.name, StepStatus.FAILED)
                append_event(
                    paths,
                    {
                        "step": step.name,
                        "status": StepStatus.FAILED,
                        "error": str(exc),
                    },
                )
                write_run_state(paths, state)
                raise

            state.mark_step(step.name, StepStatus.COMPLETED)
            append_event(paths, {"step": step.name, "status": StepStatus.COMPLETED})
            write_run_state(paths, state)

        return state
