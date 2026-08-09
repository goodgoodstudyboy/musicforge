from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from song_agent.application.generation.service import generate_request
from song_agent.interfaces.api.router import RouteRegistry, RouteSpec, api_inventory
from song_agent.interfaces.cli.app import REGISTRY, command_inventory
from song_agent.release_check_interfaces import (
    EXPECTED_COMMAND_HELP_HASH,
    EXPECTED_COMMAND_INVENTORY_HASH,
    EXPECTED_PANEL_HASH,
    EXPECTED_ROUTE_INVENTORY_HASH,
    _hash_json,
    command_help_contract_rows,
)
from song_agent.webui import panel_html, panel_source, script_modules, web_script


ROOT = Path(__file__).resolve().parents[1]


def test_compatibility_facades_meet_line_budgets_and_exports() -> None:
    import song_agent.cli as cli
    import song_agent.server as server

    assert len((ROOT / "song_agent" / "cli.py").read_text(encoding="utf-8").splitlines()) < 500
    assert len((ROOT / "song_agent" / "server.py").read_text(encoding="utf-8").splitlines()) < 1000
    assert len((ROOT / "song_agent" / "webui.py").read_text(encoding="utf-8").splitlines()) < 200
    assert cli.generate_request is generate_request
    assert callable(cli.main)
    assert callable(server.create_server)
    assert server.api_inventory() == api_inventory()


def test_command_registry_inventory_help_and_exit_policy_snapshot() -> None:
    rows = command_inventory()
    names = [row["name"] for row in rows]
    assert len(rows) == 173
    assert len(names) == len(set(names))
    assert _hash_json(rows) == EXPECTED_COMMAND_INVENTORY_HASH
    for name in sorted(names):
        spec = REGISTRY.get(name)
        assert spec is not None
        expected_policy = "program-result-v1" if name.startswith("unified-release-program") else "legacy-compatible"
        assert spec.exit_code_policy == expected_policy
        assert spec.parser.__module__.startswith("song_agent.interfaces.cli.commands")
        assert spec.handler.__module__.startswith("song_agent.interfaces.cli.commands")
        assert len(inspect.getsourcelines(spec.handler)[0]) < 100
    assert _hash_json(command_help_contract_rows(REGISTRY)) == EXPECTED_COMMAND_HELP_HASH


def test_cli_registry_uses_static_command_ownership() -> None:
    cli_root = ROOT / "song_agent" / "interfaces" / "cli"
    assert not (cli_root / "bindings.py").exists()
    assert not (cli_root / "composition.py").exists()
    assert not list((cli_root / "composition_parts").glob("*.py"))
    for row in command_inventory():
        spec = REGISTRY.get(row["name"])
        assert spec is not None
        assert spec.parser.__module__.startswith("song_agent.interfaces.cli.commands")
        assert spec.handler.__module__.startswith("song_agent.interfaces.cli.commands")


def test_route_inventory_snapshot_and_conflict_detection() -> None:
    rows = api_inventory()
    keys = [(row["method"], row["pattern"]) for row in rows]
    assert len(rows) == 117
    assert len(keys) == len(set(keys))
    assert all(
        row["request_schema"] != "legacy-compatible"
        and row["response_schema"] != "legacy-compatible"
        for row in rows
    )
    assert _hash_json(rows) == EXPECTED_ROUTE_INVENTORY_HASH
    route = RouteSpec("GET", "/api/example", "example", "configured", "none", "json")
    with pytest.raises(ValueError, match="Route conflict"):
        RouteRegistry([route, route])


def test_web_static_resources_reconstruct_compatible_panel() -> None:
    html = panel_html()
    source = panel_source()
    assert hashlib.sha256(html.encode("utf-8")).hexdigest() == EXPECTED_PANEL_HASH
    assert "{{MUSICFORGE_" not in html
    assert "Authorization" in source
    assert "401" in source
    assert '<script type="module" src="/assets/musicforge/app.js"></script>' in html
    assert len(web_script("app.js").splitlines()) < 1000
    assert all(f"panels/{panel}.js" in script_modules() for panel in ("audio", "continuity", "maintenance", "program", "trust"))
    assert (ROOT / "song_agent" / "interfaces" / "web" / "index.html").is_file()
    assert (ROOT / "song_agent" / "interfaces" / "web" / "styles" / "studio.css").is_file()
    assert (ROOT / "song_agent" / "interfaces" / "web" / "scripts" / "app.js").is_file()


def test_interface_inventory_is_machine_readable() -> None:
    encoded = json.dumps(
        {"commands": command_inventory(), "routes": api_inventory()},
        ensure_ascii=False,
        sort_keys=True,
    )
    decoded = json.loads(encoded)
    assert decoded["commands"][0]["name"] == "acceptance-analytics"
    assert decoded["routes"][0]["method"] == "*"
