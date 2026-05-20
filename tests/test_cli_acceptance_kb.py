from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.cli import _main
from tests.test_acceptance_kb import _closed_fix_sprint


def test_cli_acceptance_kb_refresh_search_and_recommend(tmp_path: Path, monkeypatch, capsys) -> None:
    _closed_fix_sprint(tmp_path, monkeypatch)

    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-kb", "refresh", "--json"])
    with pytest.raises(SystemExit) as refresh_exit:
        _main()
    refresh_output = capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-kb", "search", "--issue-type", "hook", "--json"])
    with pytest.raises(SystemExit) as search_exit:
        _main()
    search_output = capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["song-agent", "acceptance-kb", "recommend", "--issue-type", "hook", "--song-id", "rap_beat_001", "--json"])
    with pytest.raises(SystemExit) as recommend_exit:
        _main()
    recommend_output = capsys.readouterr().out

    assert refresh_exit.value.code == 0
    assert search_exit.value.code == 0
    assert recommend_exit.value.code == 0
    assert '"entry_count": 1' in refresh_output
    assert '"entry_count": 1' in search_output
    assert '"status": "available"' in recommend_output
