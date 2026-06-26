from __future__ import annotations

from pathlib import Path

from song_agent.cli import main
from song_agent.projectio import read_json
from tests.test_release_audio_certification import _prepare_certified_release
from tests.test_server_releases import start_test_server, stop_test_server


def test_verify_release_audio_certification_cli_accepts_signed_package(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, store = _prepare_certified_release(server, "Certification CLI Track")
        store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(release_id)
        report_out = tmp_path / "certification-verification.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "song-agent",
                "verify-release-audio-certification-package",
                str(zipped["zip_path"]),
                "--strict",
                "--require-passed",
                "--require-signed",
                "--require-real-audio",
                "--require-manual-review",
                "--require-remediation-when-needed",
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
