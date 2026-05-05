import json

import pytest

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
    assert (out_dir / "data" / "run-options.json").exists()
    assert (out_dir / "data" / "song-plan.json").exists()
    assert (out_dir / "data" / "run-summary.json").exists()
    assert (out_dir / "logs" / "events.jsonl").exists()
    assert (out_dir / "renders" / "song.mid").stat().st_size > 100


def test_cli_resume_rejects_different_request(tmp_path, monkeypatch, capsys):
    first_request = tmp_path / "first.json"
    second_request = tmp_path / "second.json"
    out_dir = tmp_path / "demo-run"
    first_request.write_text(
        json.dumps(
            {
                "title": "First Song",
                "language": "en",
                "style": "pop",
                "theme": "first",
            }
        ),
        encoding="utf-8",
    )
    second_request.write_text(
        json.dumps(
            {
                "title": "Second Song",
                "language": "en",
                "style": "pop",
                "theme": "second",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", str(first_request), "--out", str(out_dir)],
    )
    main()

    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", str(second_request), "--out", str(out_dir), "--resume"],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    error = capsys.readouterr().err
    assert "Cannot resume this run" in error
    plan = json.loads((out_dir / "data" / "song-plan.json").read_text(encoding="utf-8"))
    assert plan["title"] == "First Song"


def test_cli_force_replaces_existing_run(tmp_path, monkeypatch):
    first_request = tmp_path / "first.json"
    second_request = tmp_path / "second.json"
    out_dir = tmp_path / "demo-run"
    first_request.write_text(
        json.dumps(
            {
                "title": "First Song",
                "language": "en",
                "style": "pop",
                "theme": "first",
            }
        ),
        encoding="utf-8",
    )
    second_request.write_text(
        json.dumps(
            {
                "title": "Second Song",
                "language": "en",
                "style": "pop",
                "theme": "second",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", str(first_request), "--out", str(out_dir)],
    )
    main()

    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", str(second_request), "--out", str(out_dir), "--force"],
    )
    main()

    plan = json.loads((out_dir / "data" / "song-plan.json").read_text(encoding="utf-8"))
    assert plan["title"] == "Second Song"


def test_cli_generate_multinode_writes_node_artifacts(tmp_path, monkeypatch):
    request_path = tmp_path / "request.json"
    out_dir = tmp_path / "demo-run"
    request_path.write_text(
        json.dumps(
            {
                "title": "CLI Multinode Song",
                "language": "en",
                "style": "pop",
                "theme": "local multinode test",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "song-agent",
            "generate",
            str(request_path),
            "--out",
            str(out_dir),
            "--pipeline-mode",
            "multinode",
        ],
    )

    main()

    assert (out_dir / "data" / "nodes" / "brief_planner.json").exists()
    assert (out_dir / "data" / "nodes" / "song_plan_builder.json").exists()
    assert (out_dir / "renders" / "song.mid").stat().st_size > 100


def test_cli_multinode_resume_rejects_legacy_single_run(tmp_path, monkeypatch, capsys):
    request_path = tmp_path / "request.json"
    out_dir = tmp_path / "demo-run"
    request_path.write_text(
        json.dumps(
            {
                "title": "Resume Multinode Song",
                "language": "en",
                "style": "pop",
                "theme": "resume multinode",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", str(request_path), "--out", str(out_dir)],
    )
    main()
    assert not (out_dir / "data" / "nodes").exists()

    monkeypatch.setattr(
        "sys.argv",
        [
            "song-agent",
            "generate",
            str(request_path),
            "--out",
            str(out_dir),
            "--resume",
            "--pipeline-mode",
            "multinode",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "run-options.json does not match" in capsys.readouterr().err
    assert not (out_dir / "data" / "nodes").exists()


def test_cli_multinode_resume_rejects_missing_run_options_for_legacy_run(
    tmp_path,
    monkeypatch,
    capsys,
):
    request_path = tmp_path / "request.json"
    out_dir = tmp_path / "legacy-run"
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True)
    request = {
        "title": "Legacy Resume Song",
        "language": "en",
        "style": "pop",
        "theme": "legacy resume",
        "duration_seconds": 180,
        "vocal_mode": "guide_melody",
        "tempo_bpm": None,
        "key": None,
        "lyrics": None,
    }
    request_path.write_text(
        json.dumps(
            {
                "title": "Legacy Resume Song",
                "language": "en",
                "style": "pop",
                "theme": "legacy resume",
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "song-agent",
            "generate",
            str(request_path),
            "--out",
            str(out_dir),
            "--resume",
            "--pipeline-mode",
            "multinode",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "run-options.json is missing" in capsys.readouterr().err


def test_cli_reports_json_errors_without_traceback(tmp_path, monkeypatch, capsys):
    request_path = tmp_path / "broken.json"
    request_path.write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["song-agent", str(request_path), "--dry-run"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")
