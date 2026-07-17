from __future__ import annotations

import json
import sys

import pytest

from song_agent.cli import main
from tests.test_release_verifier import _build_release_zip


def test_cli_verify_release_json_and_report_out(tmp_path, monkeypatch, capsys):
    zip_path = _build_release_zip(tmp_path, monkeypatch)
    report_path = tmp_path / "verification-report.json"
    monkeypatch.setattr(sys, "argv", ["song-agent", "verify-release", str(zip_path), "--json", "--report-out", str(report_path)])

    with pytest.raises(SystemExit) as exc:
        main()

    output = capsys.readouterr().out
    report = json.loads(output)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert exc.value.code == 0
    assert report["status"] == "warning"
    assert saved["status"] == "warning"


def test_cli_verify_release_failed_zip_exits_one(tmp_path, monkeypatch, capsys):
    broken = tmp_path / "broken.zip"
    broken.write_text("not a zip", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["song-agent", "verify-release", str(broken)])

    with pytest.raises(SystemExit) as exc:
        main()

    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert "status: failed" in output
