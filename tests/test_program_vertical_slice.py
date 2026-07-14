from pathlib import Path

from song_agent.application.program import ProgramApplicationService
from song_agent.domains.program.model import ProgramComponent, ProgramOperation
from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY
from song_agent.interfaces.cli.app import REGISTRY
from song_agent.release_check_program_vertical import run_program_vertical_slice_smoke


def test_program_application_service_executes_canonical_domain_store(tmp_path: Path) -> None:
    service = ProgramApplicationService.build(root=tmp_path / "unified-release-programs")
    created = service.execute(
        ProgramOperation(
            ProgramComponent.PROGRAM,
            "create_program",
            ({"name": "Program vertical slice"},),
        )
    )

    assert created.component is ProgramComponent.PROGRAM
    assert type(service.component("program")).__module__.startswith("song_agent.domains.program")
    assert service.invoke("program", "get_program", created.value["program_id"])["program"]["name"] == "Program vertical slice"


def test_program_api_and_cli_use_explicit_registries() -> None:
    routes = PROGRAM_ROUTE_REGISTRY.inventory()
    specs = [
        REGISTRY.get(row["name"])
        for row in REGISTRY.inventory()
        if row["name"].startswith("unified-release-program")
    ]

    assert len(routes) == 5
    assert {row["handler"] for row in routes} == {"program_application.dispatch_http"}
    assert {row["request_schema"] for row in routes} == {"program-command-v1"}
    assert len(specs) == 13
    assert {spec.handler.__module__ for spec in specs if spec is not None} == {
        "song_agent.interfaces.cli.commands.program_context"
    }


def test_v134_program_vertical_slice_smoke() -> None:
    ok, detail = run_program_vertical_slice_smoke(Path(__file__).resolve().parents[1])

    assert ok is True, detail
