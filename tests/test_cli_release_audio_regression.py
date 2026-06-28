from __future__ import annotations

from pathlib import Path

from song_agent.cli import main
from song_agent.projectio import read_json
from song_agent.release_audio_regression import ReleaseAudioRegressionStore
from tests.test_release_audio_regression import _configure_regression, _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def test_verify_release_audio_regression_cli_accepts_signed_package(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression CLI Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression CLI Track")
        store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(current_release_id)
        store.verify_zip(current_release_id, strict=True, require_passed=True, require_signed=True, require_current=True, require_baseline_current=True)
        report_out = tmp_path / "regression-verification.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "song-agent",
                "verify-release-audio-regression-package",
                str(zipped["zip_path"]),
                "--strict",
                "--require-passed",
                "--require-signed",
                "--require-current",
                "--require-baseline-current",
                "--baseline-timeline",
                str(baseline_store.zip_path(baseline_release_id, baseline_timeline_id)),
                "--baseline-timeline-verification-report",
                str(baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id)),
                "--baseline-certification",
                str(baseline_store.certification_store.zip_path(baseline_release_id)),
                "--baseline-certification-verification-report",
                str(baseline_store.certification_store.verification_report_path(baseline_release_id)),
                "--current-timeline",
                str(current_store.zip_path(current_release_id, current_timeline_id)),
                "--current-timeline-verification-report",
                str(current_store.verification_report_path(current_release_id, current_timeline_id)),
                "--current-certification",
                str(current_store.certification_store.zip_path(current_release_id)),
                "--current-certification-verification-report",
                str(current_store.certification_store.verification_report_path(current_release_id)),
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
