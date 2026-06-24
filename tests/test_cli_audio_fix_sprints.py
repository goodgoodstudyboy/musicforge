from __future__ import annotations

import json

from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.cli import main


def _run_cli(argv: list[str], monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["song-agent", *argv])
    try:
        main()
    except SystemExit as exc:
        code = int(exc.code or 0)
    else:
        code = 0
    return code, capsys.readouterr()


def _write_needs_fix_session() -> tuple[str, str]:
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    smoke = lab.run_smoke({"cases": 1, "render_audio": "auto"})
    session = lab.create_session({"from_smoke": smoke["smoke_run_id"]})
    session_id = session["session_id"]
    item_id = session["items"][0]["item_id"]
    lab.write_item_review(session_id, item_id, {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    lab.add_marker(session_id, item_id, {"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "Masking."})
    return session_id, item_id


def test_cli_audio_fix_sprint_create_and_fake_closeout_block(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    session_id, _ = _write_needs_fix_session()

    blocked_code, blocked_out = _run_cli(["audio-fix-sprint", "create", "--from-session", session_id, "--json"], monkeypatch, capsys)
    create_code, create_out = _run_cli(["audio-fix-sprint", "create", "--from-session", session_id, "--include-test-audio", "--json"], monkeypatch, capsys)
    sprint = json.loads(create_out.out)["sprint"]
    sprint_id = sprint["fix_sprint_id"]
    item_id = sprint["items"][0]["fix_item_id"]
    candidate_code, candidate_out = _run_cli(["audio-fix-sprint", "generate-candidates", sprint_id, "--json"], monkeypatch, capsys)
    candidate_id = json.loads(candidate_out.out)["candidates"][0]["candidate_id"]
    review_code, _ = _run_cli(
        [
            "audio-fix-sprint",
            "review-candidate",
            sprint_id,
            item_id,
            candidate_id,
            "--preferred",
            "right",
            "--playback-confirmed",
            "--reviewer",
            "QA",
            "--role",
            "developer",
            "--json",
        ],
        monkeypatch,
        capsys,
    )
    select_code, _ = _run_cli(["audio-fix-sprint", "select-candidate", sprint_id, item_id, candidate_id, "--json"], monkeypatch, capsys)
    recheck_code, recheck_out = _run_cli(["audio-fix-sprint", "create-recheck-session", sprint_id, "--json"], monkeypatch, capsys)
    recheck_item_id = json.loads(recheck_out.out)["recheck_session"]["items"][0]["item_id"]
    recheck_review_code, _ = _run_cli(
        [
            "audio-fix-sprint",
            "review-recheck",
            sprint_id,
            recheck_item_id,
            "--result",
            "accepted",
            "--playback-confirmed",
            "--reviewer",
            "QA",
            "--role",
            "developer",
            "--json",
        ],
        monkeypatch,
        capsys,
    )
    closeout_code, closeout_out = _run_cli(["audio-fix-sprint", "closeout", sprint_id, "--json"], monkeypatch, capsys)
    closeout = json.loads(closeout_out.out)

    assert blocked_code == 1
    assert "No eligible" in blocked_out.err or "No eligible" in blocked_out.out
    assert create_code == 0
    assert candidate_code == 0
    assert review_code == 0
    assert select_code == 0
    assert recheck_code == 0
    assert recheck_review_code == 0
    assert closeout_code == 1
    assert closeout["closeout"]["status"] == "failed"
    assert "test_fake_audio_not_release_ready" in closeout["closeout"]["blockers"]
