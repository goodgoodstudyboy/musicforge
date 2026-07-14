from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path


EXPECTED_COMMAND_INVENTORY_HASH = "9dae3beeaf2b17fae7ecec894aa0a3d4bf1d03d870863d10da3009105ce805ca"
EXPECTED_COMMAND_HELP_HASH = "f767c652952eab00db3930cab08fe49f5c41d92f00dc781f10328f2d1d8745cd"
EXPECTED_ROUTE_INVENTORY_HASH = "d35613b0de81ad2aa3e2ad51e0d8f31c553671c888c6aaead1c0b737df50a77c"
EXPECTED_PANEL_HASH = "a5065e9852ef9b7ee18eac525a1b70c6a6e835c3f17fb5c494feb760b2468515"


def _hash_json(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def command_help_contract_rows(registry: object) -> list[dict[str, object]]:
    """Return the parser semantics without Python-version-specific help wrapping."""
    rows: list[dict[str, object]] = []
    inventory = registry.inventory()  # type: ignore[attr-defined]
    for name in sorted(str(row["name"]) for row in inventory):
        spec = registry.get(name)  # type: ignore[attr-defined]
        if spec is None:
            raise RuntimeError(f"Missing registered command: {name}")
        parser = spec.parser()
        parser.prog = name
        actions = []
        for action in parser._actions:
            choices = action.choices
            actions.append(
                {
                    "action_class": action.__class__.__name__,
                    "option_strings": list(action.option_strings),
                    "dest": action.dest,
                    "required": bool(action.required),
                    "nargs": _contract_value(action.nargs),
                    "const": _contract_value(action.const),
                    "default": _contract_value(action.default),
                    "choices": _contract_value(list(choices) if choices is not None else None),
                    "metavar": _contract_value(action.metavar),
                    "help": _contract_value(action.help),
                    "type": _callable_contract_name(action.type),
                }
            )
        exclusive_groups = [
            {
                "required": bool(group.required),
                "destinations": [action.dest for action in group._group_actions],
            }
            for group in parser._mutually_exclusive_groups
        ]
        rows.append(
            {
                "name": name,
                "description": _contract_value(parser.description),
                "epilog": _contract_value(parser.epilog),
                "usage": _contract_value(parser.usage),
                "actions": actions,
                "mutually_exclusive_groups": exclusive_groups,
            }
        )
    return rows


def _contract_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_contract_value(item) for item in value]
    return str(value)


def _callable_contract_name(value: object) -> str | None:
    if value is None:
        return None
    module = getattr(value, "__module__", "")
    name = getattr(value, "__qualname__", getattr(value, "__name__", ""))
    if name:
        return f"{module}.{name}" if module and module != "builtins" else str(name)
    return str(value)


def run_interface_registry_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.interfaces.api.router import api_inventory
        from song_agent.interfaces.cli.app import REGISTRY
        from song_agent.webui import panel_html

        repo_root = Path(__file__).resolve().parents[1]
        commands = REGISTRY.inventory()
        command_names = [row["name"] for row in commands]
        handlers_small = True
        parser_colocated = True
        for name in sorted(command_names):
            spec = REGISTRY.get(name)
            if spec is None:
                raise RuntimeError(f"Missing registered command: {name}")
            handlers_small = handlers_small and len(inspect.getsourcelines(spec.handler)[0]) < 100
            parser_colocated = parser_colocated and spec.parser.__module__ == spec.handler.__module__

        routes = api_inventory()
        route_keys = [(row["method"], row["pattern"]) for row in routes]
        html = panel_html()
        facade_limits = {
            "cli": len((repo_root / "song_agent" / "cli.py").read_text(encoding="utf-8").splitlines()) < 500,
            "server": len((repo_root / "song_agent" / "server.py").read_text(encoding="utf-8").splitlines()) < 1000,
            "webui": len((repo_root / "song_agent" / "webui.py").read_text(encoding="utf-8").splitlines()) < 200,
        }
        checks = {
            "commands": len(commands) == 173 and len(command_names) == len(set(command_names)),
            "command_snapshot": _hash_json(commands) == EXPECTED_COMMAND_INVENTORY_HASH,
            "help_snapshot": _hash_json(command_help_contract_rows(REGISTRY)) == EXPECTED_COMMAND_HELP_HASH,
            "handlers_small": handlers_small,
            "parser_colocated": parser_colocated,
            "routes": len(routes) == 113 and len(route_keys) == len(set(route_keys)),
            "route_snapshot": _hash_json(routes) == EXPECTED_ROUTE_INVENTORY_HASH,
            "web_snapshot": hashlib.sha256(html.encode("utf-8")).hexdigest() == EXPECTED_PANEL_HASH,
            "web_resources": "{{MUSICFORGE_" not in html and "MusicForge Studio" in html,
            "facade_limits": all(facade_limits.values()),
        }
        ok = all(checks.values())
        detail = ", ".join(f"{name}={value}" for name, value in checks.items())
        return ok, f"v12.18 interface registry: {detail}"
    except Exception as exc:
        return False, f"v12.18 interface registry failed: {exc}"
