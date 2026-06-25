from __future__ import annotations

import json
from pathlib import Path

from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.cli import main
from song_agent.projectio import read_json


def _run_cli(argv: list[str], monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["song-agent", *argv])
    try:
        main()
    except SystemExit as exc:
        code = int(exc.code or 0)
    else:
        code = 0
    return code, capsys.readouterr()


def _real_session() -> str:
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    smoke = lab.run_smoke({"cases": 1, "render_audio": "auto"})
    session = lab.create_session({"from_smoke": smoke["smoke_run_id"]})
    session_id = session["session_id"]
    raw = read_json(lab.session_path(session_id))
    raw["items"][0]["renderer"] = {"runner_kind": "real", "profile_id": "test-real", "release_ready": True}
    raw["items"][0]["source_hash"] = "cli-audio-campaign-real-source"
    lab._write_session(raw)  # type: ignore[attr-defined]
    item_id = session["items"][0]["item_id"]
    lab.write_item_review(session_id, item_id, {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    return session_id


def test_cli_audio_campaign_signoff_zip_and_verify(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    session_id = _real_session()

    create_code, create_out = _run_cli(["audio-campaign", "create", "--from-session", session_id, "--json"], monkeypatch, capsys)
    campaign = json.loads(create_out.out)["campaign"]
    campaign_id = campaign["campaign_id"]
    report_code, report_out = _run_cli(["audio-campaign", "report", campaign_id, "--json"], monkeypatch, capsys)
    signoff_code, signoff_out = _run_cli(["audio-campaign", "signoff", campaign_id, "--signed-by", "QA", "--role", "developer", "--json"], monkeypatch, capsys)
    zip_code, zip_out = _run_cli(["audio-campaign", "zip", campaign_id, "--json"], monkeypatch, capsys)
    zip_path = json.loads(zip_out.out)["zip_path"]
    verify_code, verify_out = _run_cli(
        [
            "verify-audio-campaign-package",
            zip_path,
            "--require-real-audio",
            "--require-manual-review",
            "--require-signed",
            "--json",
        ],
        monkeypatch,
        capsys,
    )

    assert create_code == 0
    assert report_code == 0
    assert json.loads(report_out.out)["report"]["status"] == "passed"
    assert signoff_code == 0
    assert json.loads(signoff_out.out)["signoff"]["status"] == "signed"
    assert zip_code == 0
    assert verify_code == 0
    assert json.loads(verify_out.out)["status"] == "passed"


def test_cli_audio_campaign_governance_archive_and_reset(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    session_id = _real_session()

    _, create_out = _run_cli(["audio-campaign", "create", "--from-session", session_id, "--json"], monkeypatch, capsys)
    campaign_id = json.loads(create_out.out)["campaign"]["campaign_id"]
    _run_cli(["audio-campaign", "report", campaign_id, "--json"], monkeypatch, capsys)
    _run_cli(["audio-campaign", "signoff", campaign_id, "--signed-by", "QA", "--role", "developer", "--json"], monkeypatch, capsys)
    archive_code, archive_out = _run_cli(["audio-campaign", "archive-zip", campaign_id, "--json"], monkeypatch, capsys)
    verify_code, verify_out = _run_cli(["audio-campaign", "verify-archive", campaign_id, "--json"], monkeypatch, capsys)
    cr_code, cr_out = _run_cli(["audio-campaign", "change-request-create", campaign_id, "--reason", "Need new pass", "--json"], monkeypatch, capsys)
    cr_id = json.loads(cr_out.out)["change_request"]["change_request_id"]
    approve_code, _ = _run_cli(["audio-campaign", "change-request-approve", campaign_id, cr_id, "--json"], monkeypatch, capsys)
    reset_code, reset_out = _run_cli(["audio-campaign", "signoff-reset", campaign_id, "--change-request-id", cr_id, "--reason", "Approved reset", "--json"], monkeypatch, capsys)

    assert archive_code == 0
    assert json.loads(archive_out.out)["zip_sha256"]
    assert verify_code == 0
    assert json.loads(verify_out.out)["verification"]["status"] == "passed"
    assert cr_code == 0
    assert approve_code == 0
    assert reset_code == 0
    assert json.loads(reset_out.out)["status"] == "reset"
