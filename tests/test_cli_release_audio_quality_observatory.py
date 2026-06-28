from __future__ import annotations

import pytest

from song_agent.cli import _main
from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def test_release_audio_quality_observatory_cli_verify(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Observatory CLI Track")
        store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        config = store.create({"release_ids": [release_id]})
        store.refresh(config["observatory_id"])
        store.build_zip(config["observatory_id"])
        monkeypatch.setattr(
            "sys.argv",
            [
                "song-agent",
                "verify-release-audio-quality-observatory-package",
                str(store.zip_path(config["observatory_id"])),
                "--strict",
                "--require-current-evidence",
                "--require-no-critical-risk",
                "--evidence-root",
                str(server.release_store.root),
                "--json",
            ],
        )
        with pytest.raises(SystemExit) as exc:
            _main()
    finally:
        stop_test_server(server)

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '"status": "passed"' in output
