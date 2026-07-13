from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path


EXPECTED_COMMAND_INVENTORY_HASH = "9dae3beeaf2b17fae7ecec894aa0a3d4bf1d03d870863d10da3009105ce805ca"
EXPECTED_COMMAND_HELP_HASH = "cfc4491ce0eebdd7b732689c942ca16f04e73c7bb1ed01c3d4c2749fa3797c35"
EXPECTED_ROUTE_INVENTORY_HASH = "d35613b0de81ad2aa3e2ad51e0d8f31c553671c888c6aaead1c0b737df50a77c"
EXPECTED_PANEL_HASH = "bb8262059999784e01bc3c97d501bdf3e1270e106528e05b2697246bbd0abd3a"


def _hash_json(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_interface_registry_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.interfaces.api.router import api_inventory
        from song_agent.interfaces.cli.app import REGISTRY
        from song_agent.webui import panel_html

        repo_root = Path(__file__).resolve().parents[1]
        commands = REGISTRY.inventory()
        command_names = [row["name"] for row in commands]
        help_rows = []
        handlers_small = True
        parser_colocated = True
        for name in sorted(command_names):
            spec = REGISTRY.get(name)
            if spec is None:
                raise RuntimeError(f"Missing registered command: {name}")
            parser = spec.parser()
            parser.prog = name
            help_rows.append({"name": name, "help": parser.format_help()})
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
            "help_snapshot": _hash_json(help_rows) == EXPECTED_COMMAND_HELP_HASH,
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
