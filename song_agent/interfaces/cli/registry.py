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
        parser_module = getattr(spec.parser, "__module__", "")
        handler_module = getattr(spec.handler, "__module__", "")
        if handler_module and parser_module != handler_module:
            spec = CommandSpec(
                name=spec.name,
                parser=_parser_with_module(spec.parser, handler_module),
                handler=spec.handler,
                help=spec.help,
                exit_code_policy=spec.exit_code_policy,
                group=spec.group,
            )
        self._specs[spec.name] = spec

    def dispatch(self, name: str, argv: list[str]) -> None:
        self._specs[name].handler(argv)

    def get(self, name: str) -> CommandSpec | None:
        return self._specs.get(name)

    def inventory(self) -> list[dict[str, str]]:
        return [self._specs[name].inventory_row() for name in sorted(self._specs)]


def _parser_with_module(parser: ParserFactory, module: str) -> ParserFactory:
    def bound_parser() -> argparse.ArgumentParser:
        return parser()

    bound_parser.__name__ = getattr(parser, "__name__", "bound_parser")
    bound_parser.__qualname__ = getattr(parser, "__qualname__", bound_parser.__name__)
    bound_parser.__module__ = module
    return bound_parser
