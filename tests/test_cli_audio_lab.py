from __future__ import annotations

import json
from pathlib import Path

from song_agent.cli import main
from song_agent.audio_lab import write_lab_test_wav


def _run_cli(argv: list[str], monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["song-agent", *argv])
    try:
        main()
    except SystemExit as exc:
        code = int(exc.code or 0)
    else:
        code = 0
    captured = capsys.readouterr()
    return code, captured


def test_cli_audio_lab_status_and_smoke_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    code, captured = _run_cli(["audio-lab", "status", "--json"], monkeypatch, capsys)
    status = json.loads(captured.out)
    smoke_code, smoke_captured = _run_cli(["audio-lab", "smoke", "--cases", "1", "--render-audio", "never", "--json"], monkeypatch, capsys)
    smoke = json.loads(smoke_captured.out)

    assert code == 0
    assert status["environment"]["status"] == "missing"
    assert smoke_code == 0
    assert smoke["smoke_run"]["summary"]["midi_count"] == 1
    assert smoke["smoke_run"]["summary"]["wav_count"] == 0


def test_cli_audio_lab_required_audio_fails_without_renderer(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    code, captured = _run_cli(["audio-lab", "smoke", "--cases", "1", "--render-audio", "required", "--json"], monkeypatch, capsys)
    payload = json.loads(captured.out)

    assert code == 1
    assert payload["smoke_run"]["status"] == "failed"


def test_cli_audio_lab_comparison_review(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    dummy = tmp_path / "dummy.mid"
    dummy.write_bytes(b"MThd")
    left = write_lab_test_wav(dummy, tmp_path / "left.wav")
    right = write_lab_test_wav(dummy, tmp_path / "right.wav", amplitude=0.1)

    code, captured = _run_cli(["audio-lab", "compare", "create", "--left", str(left), "--right", str(right), "--json"], monkeypatch, capsys)
    created = json.loads(captured.out)
    comparison_id = created["comparison"]["comparison_id"]
    review_code, review_captured = _run_cli(
        [
            "audio-lab",
            "compare",
            "review",
            comparison_id,
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
    reviewed = json.loads(review_captured.out)

    assert code == 0
    assert review_code == 0
    assert reviewed["comparison"]["review"]["preferred"] == "right"
    assert "source_abspath" not in json.dumps(reviewed)
