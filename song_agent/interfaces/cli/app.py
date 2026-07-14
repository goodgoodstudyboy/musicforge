from __future__ import annotations

import json
import os
import sys

from .commands import creation as creation_commands
from .commands import studio as studio_commands
from .commands import quality as quality_commands
from .commands import delivery as delivery_commands
from .commands import trust as trust_commands
from .commands import program as program_commands
from .commands import program_context as program_context_commands
from .commands import maintenance as maintenance_commands
from .commands import release_check as release_check_commands
from .registry import CommandRegistry


COMMAND_MODULES = (creation_commands, studio_commands, quality_commands, delivery_commands, trust_commands, program_commands, program_context_commands, maintenance_commands, release_check_commands,)
REGISTRY = CommandRegistry(spec for module in COMMAND_MODULES for spec in module.SPECS)


def command_inventory() -> list[dict[str, str]]:
    return REGISTRY.inventory()


def _main() -> None:
    raw_args = sys.argv[1:]
    if raw_args:
        spec = REGISTRY.get(raw_args[0])
        if spec is not None:
            REGISTRY.dispatch(spec.name, raw_args[1:])
            return
    creation_commands.handle_default_generate(raw_args)


def main() -> None:
    try:
        _main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
