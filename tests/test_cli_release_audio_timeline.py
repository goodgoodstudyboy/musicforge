from __future__ import annotations

from pathlib import Path

from song_agent.cli import main
from song_agent.projectio import read_json
from tests.test_release_audio_timeline import _prepare_timeline_release
from tests.test_server_releases import start_test_server, stop_test_server


def test_verify_release_audio_timeline_cli_accepts_signed_package(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, store = _prepare_timeline_release(server, "Timeline CLI Track")
        refreshed = store.refresh_timeline(release_id)
        timeline_id = refreshed["timeline_id"]
        store.signoff_timeline(release_id, timeline_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(release_id, timeline_id)
        store.verify_zip(release_id, timeline_id, strict=True, require_passed=True, require_signed=True, require_real_audio=True, require_manual_review=True, require_current_certification=True)
        report_out = tmp_path / "timeline-verification.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "song-agent",
                "verify-release-audio-timeline-package",
                str(zipped["zip_path"]),
                "--strict",
                "--require-passed",
                "--require-signed",
                "--require-real-audio",
                "--require-manual-review",
                "--report-out",
                str(report_out),
                "--json",
            ],
        )
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 0
    finally:
        stop_test_server(server)

    output = capsys.readouterr().out
    assert '"status": "passed"' in output
    assert report_out.exists()
    assert read_json(report_out)["status"] == "passed"
