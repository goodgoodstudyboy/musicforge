from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from typing import Any

from song_agent.application.program import ProgramApplicationService
from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY
from song_agent.interfaces.cli.app import REGISTRY


PROGRAM_COMMAND_PREFIX = "unified-release-program"


def run_program_vertical_slice_smoke(root: Path) -> tuple[bool, str]:
    try:
        domain_root = root / "song_agent" / "domains" / "program"
        compatibility_files = sorted(root.glob("song_agent/unified_release_program*.py"))
        compatibility_files.extend(
            sorted(root.glob("song_agent/unified_command_center_release_train*_verifier.py"))
        )
        canonical_files = sorted(domain_root.glob("unified_release_program*.py"))
        canonical_files.extend(sorted(domain_root.glob("unified_command_center_release_train*_verifier.py")))

        with tempfile.TemporaryDirectory(prefix="mf-v134-program-") as temp:
            service = ProgramApplicationService.build(root=Path(temp) / "unified-release-programs")
            created = service.invoke("program", "create_program", {"name": "v13.4 vertical slice"})
            program_id = str(created["program_id"])
            loaded = service.invoke("program", "get_program", program_id)

        command_specs = [
            REGISTRY.get(row["name"])
            for row in REGISTRY.inventory()
            if row["name"].startswith(PROGRAM_COMMAND_PREFIX)
        ]
        route_handler = _program_route_handler(root)
        architecture = build_architecture_snapshot(root)
        compatibility_edges = [
            row
            for row in architecture["active_to_compatibility_imports"]
            if str(row["importer"]).startswith(
                ("song_agent.domains.program", "song_agent.application.program")
            )
        ]
        direct_flat_imports = _active_flat_program_imports(root)

        class _Application:
            called: tuple[str, str] | None = None

            def dispatch_http(self, port: object, method: str, path: str) -> None:
                del port
                self.called = (method, path)

        application = _Application()
        port = type("ProgramPort", (), {"program_application": application})()
        dispatched = PROGRAM_ROUTE_REGISTRY.dispatch(
            port,
            "GET",
            "/api/unified-release-programs/urp-000001",
        )

        signals: dict[str, Any] = {
            "canonical_modules": len(canonical_files) == 30,
            "compatibility_wrappers": len(compatibility_files) == 30
            and all(_is_short_wrapper(path) for path in compatibility_files),
            "application_service": len(service._components) == 13,
            "application_round_trip": loaded["program"]["program_id"] == program_id,
            "program_compatibility_edges": len(compatibility_edges) == 0,
            "active_flat_imports": len(direct_flat_imports) == 0,
            "api_route_handler_small": route_handler <= 100,
            "api_registry_dispatch": dispatched
            and application.called == ("GET", "/api/unified-release-programs/urp-000001")
            and len(PROGRAM_ROUTE_REGISTRY.inventory()) == 5,
            "cli_specs": len(command_specs) == 13
            and all(spec is not None for spec in command_specs),
            "cli_handlers_small": all(
                spec is not None
                and spec.handler.__module__ == "song_agent.interfaces.cli.commands.program_context"
                and len(inspect.getsource(spec.handler).splitlines()) <= 80
                for spec in command_specs
            ),
            "cli_no_store_import": not any(
                "domains.program" in line and "Store" in line
                for line in (
                    root / "song_agent" / "interfaces" / "cli" / "commands" / "program.py"
                ).read_text(encoding="utf-8").splitlines()
            ),
        }
        return all(signals.values()), "v13.4 Program vertical slice: " + ", ".join(
            f"{key}={value}" for key, value in signals.items()
        )
    except Exception as exc:
        return False, f"v13.4 Program vertical slice failed: {exc}"


def _is_short_wrapper(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    return len(source.splitlines()) <= 20 and "song_agent.domains.program" in source


def _program_route_handler(root: Path) -> int:
    routes = root / "song_agent" / "interfaces" / "api" / "routes"
    for source in [routes / "program.py", *sorted((routes / "program_parts").glob("*.py"))]:
        lines = source.read_text(encoding="utf-8").splitlines()
        for start, line in enumerate(lines):
            if "def _handle_unified_release_programs_route" not in line:
                continue
            indent = len(line) - len(line.lstrip())
            for end in range(start + 1, len(lines)):
                candidate = lines[end]
                if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= indent and candidate.lstrip().startswith("def "):
                    return end - start
            return len(lines) - start
    raise RuntimeError("Program route handler is missing.")


def _active_flat_program_imports(root: Path) -> list[str]:
    needles = (
        "song_agent.unified_release_program",
        "song_agent.unified_command_center_release_train_verifier",
        "song_agent.unified_command_center_release_train_change_control_verifier",
        "song_agent.unified_command_center_release_train_lifecycle_verifier",
        "song_agent.unified_command_center_release_train_handoff_verifier",
    )
    wrappers = {
        path.resolve()
        for path in [
            *root.glob("song_agent/unified_release_program*.py"),
            *root.glob("song_agent/unified_command_center_release_train*_verifier.py"),
        ]
    }
    rows: list[str] = []
    for path in (root / "song_agent").rglob("*.py"):
        if (
            path.resolve() in wrappers
            or "release_check" in path.parts
            or path.name.startswith("release_check")
        ):
            continue
        source = path.read_text(encoding="utf-8")
        if any(needle in source for needle in needles):
            rows.append(path.relative_to(root).as_posix())
    return rows
