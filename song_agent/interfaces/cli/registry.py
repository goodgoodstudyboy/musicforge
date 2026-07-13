from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable
import argparse

from .errors import CommandRegistrationError


ParserFactory = Callable[[], argparse.ArgumentParser]
CommandHandler = Callable[[list[str]], None]


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    parser: ParserFactory
    handler: CommandHandler
    help: str
    exit_code_policy: str = "legacy-compatible"
    group: str = "creation"

    def inventory_row(self) -> dict[str, str]:
        return {
            "name": self.name,
            "group": self.group,
            "help": self.help,
            "exit_code_policy": self.exit_code_policy,
        }


class CommandRegistry:
    def __init__(self, specs: Iterable[CommandSpec] = ()) -> None:
        self._specs: dict[str, CommandSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: CommandSpec) -> None:
        if spec.name in self._specs:
            raise CommandRegistrationError(f"Duplicate command registration: {spec.name}")
        self._specs[spec.name] = spec

    def dispatch(self, name: str, argv: list[str]) -> None:
        self._specs[name].handler(argv)

    def get(self, name: str) -> CommandSpec | None:
        return self._specs.get(name)

    def inventory(self) -> list[dict[str, str]]:
        return [self._specs[name].inventory_row() for name in sorted(self._specs)]
