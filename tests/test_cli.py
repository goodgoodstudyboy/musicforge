import json

from song_agent.cli import main


def test_cli_generates_run_artifacts(tmp_path, monkeypatch, capsys):
    request_path = tmp_path / "request.json"
    out_dir = tmp_path / "demo-run"
    request_path.write_text(
        json.dumps(
            {
                "title": "CLI Song",
                "language": "en",
                "style": "pop",
                "theme": "local test",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", str(request_path), "--out", str(out_dir)],
    )

    main()

    output = capsys.readouterr().out
    assert "Wrote song plan" in output
    assert (out_dir / "data" / "request.json").exists()
    assert (out_dir / "data" / "song-plan.json").exists()
    assert (out_dir / "data" / "run-summary.json").exists()
    assert (out_dir / "logs" / "events.jsonl").exists()
    assert (out_dir / "renders" / "song.mid").stat().st_size > 100
