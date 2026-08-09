from pathlib import Path

from song_agent.interfaces.bootstrap.api.program import build_program_application
from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY
from song_agent.interfaces.cli.app import REGISTRY
from song_agent.release_check_program_vertical import run_program_vertical_slice_smoke


def test_program_application_service_executes_canonical_domain_store(tmp_path: Path) -> None:
    service = build_program_application(root=tmp_path / "unified-release-programs")
    created = service.create_program({"name": "Program vertical slice"})

    assert type(service.component("program")).__module__.startswith("song_agent.domains.program")
    assert service.get_program(str(created["program_id"]))["program"]["name"] == "Program vertical slice"


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


def test_program_application_gate_is_policy_owned(tmp_path: Path) -> None:
    service = build_program_application(root=tmp_path / "unified-release-programs")
    created = service.create_program({"name": "Policy-owned Program"})

    legacy = service.evaluate_gate(created["program_id"], {})
    unknown = service.evaluate_gate(
        created["program_id"],
        {"policy": "program.unknown", "evidence_manifest_id": "program"},
    )

    assert legacy["policy_id"] == "program.compatibility"
    assert legacy["legacy_gate_summary"]["authoritative"] is False
    assert legacy["status"] == "failed"
    assert unknown["status"] == "failed"
    assert unknown["blockers"] == ["program_policy_id"]


def test_v134_program_vertical_slice_smoke() -> None:
    ok, detail = run_program_vertical_slice_smoke(Path(__file__).resolve().parents[1])

    assert ok is True, detail
