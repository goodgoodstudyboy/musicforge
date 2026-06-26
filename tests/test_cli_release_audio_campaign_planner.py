from __future__ import annotations

import json
from pathlib import Path

from song_agent.cli import main
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_releases import _signed_project, request_json, start_test_server, stop_test_server


def _run_cli(argv: list[str], monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["song-agent", *argv])
    try:
        main()
    except SystemExit as exc:
        code = int(exc.code or 0)
    else:
        code = 0
    return code, capsys.readouterr()


def _release_fixture() -> str:
    server = start_test_server()
    try:
        project_id = _signed_project(server, "CLI Planner Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "CLI Planner Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        assert created_status == 201
        release_id = created["release"]["release_id"]
        assert request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})[0] == 200
        return release_id
    finally:
        stop_test_server(server)


def test_cli_release_audio_campaign_plan_preflight_create_status(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    release_id = _release_fixture()

    plan_code, plan_out = _run_cli(["audio-campaign", "plan-release", release_id, "--json"], monkeypatch, capsys)
    preflight_code, preflight_out = _run_cli(["audio-campaign", "preflight-release", release_id, "--json"], monkeypatch, capsys)
    create_code, create_out = _run_cli(["audio-campaign", "create-from-release", release_id, "--json"], monkeypatch, capsys)
    status_code, status_out = _run_cli(["audio-campaign", "release-status", release_id, "--json"], monkeypatch, capsys)

    assert plan_code == 0
    assert json.loads(plan_out.out)["plan"]["status"] == "planned"
    assert preflight_code == 0
    assert json.loads(preflight_out.out)["preflight"]["status"] == "passed"
    assert create_code == 0
    created = json.loads(create_out.out)
    assert created["link"]["coverage_status"] == "passed"
    assert created["session"]["items"][0]["release_id"] == release_id
    assert status_code == 0
    assert json.loads(status_out.out)["summary"]["coverage_status"] == "passed"
