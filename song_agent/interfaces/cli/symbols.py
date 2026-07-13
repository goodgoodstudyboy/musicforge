from __future__ import annotations

from importlib import import_module
from typing import Any, Callable


def resolve(group: str, name: str) -> Callable[..., Any]:
    module = import_module(f"song_agent.interfaces.cli.commands.{group}")
    return getattr(module, name)
