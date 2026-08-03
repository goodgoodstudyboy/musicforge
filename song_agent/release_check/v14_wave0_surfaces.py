from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import cast

from song_agent.interfaces.api.router import api_inventory
from song_agent.interfaces.cli.app import command_inventory


_PANEL_ID = re.compile(r"\bid:\s*['\"]([a-z0-9_-]+)['\"]")

def collect_cli_commands() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "command_id": str(raw["name"]), "owner": "song_agent.interfaces.cli",
            "group": str(raw.get("group") or ""), "exit_code_policy": str(raw.get("exit_code_policy") or ""),
        }
        for raw in cast(list[dict[str, object]], command_inventory())
    ]
    return sorted(rows, key=lambda row: str(row["command_id"]))

def collect_cli_registrations(active: dict[str, dict[str, object]], trees: dict[str, ast.AST]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for module in sorted(active):
        if ".interfaces.cli." not in module and module != "song_agent.cli":
            continue
        source = str(active[module]["path"])
        for node in ast.walk(trees[module]):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "add_parser" or not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            name = node.args[0].value
            if isinstance(name, str):
                function = _enclosing_function(trees[module], node.lineno)
                rows.append({
                    "registration_id": f"{module}:{node.lineno}:{name}", "owner": module,
                    "source": source, "line": node.lineno, "command": name, "function": function,
                })
    return sorted(rows, key=lambda row: str(row["registration_id"]))

def _enclosing_function(tree: ast.AST, line: int) -> str:
    matches = [
        (int(getattr(node, "end_lineno", node.lineno)) - node.lineno, node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= line <= int(getattr(node, "end_lineno", node.lineno))
    ]
    return min(matches, default=(0, ""))[1]

def collect_api_routes() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "route_id": f"{raw['method']} {raw['pattern']}", "owner": "song_agent.interfaces.api",
            "handler": str(raw["handler"]), "auth": str(raw.get("auth") or ""),
            "request_schema": str(raw.get("request_schema") or ""),
            "response_schema": str(raw.get("response_schema") or ""),
        }
        for raw in cast(list[dict[str, object]], api_inventory())
    ]
    return sorted(rows, key=lambda row: str(row["route_id"]))

def collect_panels(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    panel_root = root / "song_agent" / "interfaces" / "web" / "scripts" / "panels"
    for path in sorted(panel_root.glob("*.js")):
        match = _PANEL_ID.search(path.read_text(encoding="utf-8"))
        if match is None:
            continue
        rows.append({"panel_id": match.group(1), "owner": path.relative_to(root).as_posix()})
    return rows
