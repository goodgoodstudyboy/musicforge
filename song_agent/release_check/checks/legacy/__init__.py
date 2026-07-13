"""Read-only compatibility home for historical smoke implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def delegated_check(name: str) -> Callable[[Path], tuple[bool, str]]:
    def run(root: Path) -> tuple[bool, str]:
        from song_agent.release_check.checks.legacy import monolith

        return getattr(monolith, name)(root)

    run.__name__ = name
    return run


__all__ = ["delegated_check"]
