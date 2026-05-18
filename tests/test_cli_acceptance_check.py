from __future__ import annotations

import json
from pathlib import Path

from song_agent.cli import main


def test_cli_acceptance_check_auto_review_json_and_report_out(tmp_path, monkeypatch, capsys):
    report_path = tmp_path / "acceptance-report.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "song-agent",
            "acceptance-check",
            "--cases",
            "2",
            "--auto-review",
            "--render-audio",
            "never",
            "--json",
            "--report-out",
            str(report_path),
        ],
    )

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    report = json.loads(output)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["summary"]["case_count"] == 2
    assert saved["suite_id"] == report["suite_id"]


def test_cli_acceptance_check_without_auto_review_needs_review(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-check", "--cases", "1", "--render-audio", "never"])

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert "status: needs_review" in output


def _write_unusable_renderer_config(tmp_path):
    renderer_path = tmp_path / ".musicforge" / "renderer.json"
    renderer_path.parent.mkdir(parents=True)
    soundfont = tmp_path / "fake.sf2"
    soundfont.write_bytes(b"sf2")
    renderer_path.write_text(
        json.dumps(
            {
                "renderer_type": "fluidsynth",
                "fluidsynth_path": str(Path("missing-fluidsynth.exe")),
                "soundfont_path": str(soundfont),
                "sample_rate": 44100,
                "output_format": "wav",
                "gain": 0.6,
            }
        ),
        encoding="utf-8",
    )


def test_cli_acceptance_check_reports_health_failure_without_crashing(tmp_path, monkeypatch, capsys):
    _write_unusable_renderer_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-check", "--cases", "1", "--auto-review", "--render-audio", "auto", "--json"])

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 1

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert any("health blocking failures" in blocker for blocker in report["blockers"])


def test_cli_acceptance_check_render_audio_never_is_midi_only_even_when_renderer_configured(tmp_path, monkeypatch, capsys):
    _write_unusable_renderer_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-check", "--cases", "1", "--auto-review", "--render-audio", "never", "--json"])

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["summary"]["accepted_count"] == 1
    assert report["cases"][0]["audio_status"] == "skipped_by_request"


def test_cli_acceptance_release_candidate_auto_review_cannot_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-check", "--profile", "release_candidate", "--cases", "1", "--auto-review", "--render-audio", "never", "--json"])

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 1

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert report["summary"]["manual_required"] is True
    assert report["summary"]["release_ready"] is False
