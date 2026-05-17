from __future__ import annotations

import sys
from pathlib import Path

from song_agent.cli import main
from song_agent.distribution import DistributionStore
from song_agent.submission_export import build_submission_export_bundle, build_submission_package_zip, sign_submission_package
from song_agent.submission_qa import build_submission_qa_report
from song_agent.submissions import SubmissionStore
from tests.test_distribution import _signed_release_with_metadata
from tests.test_submissions import _signed_distribution_target


def test_cli_verify_submission_package_json_and_report_out(tmp_path: Path, monkeypatch, capsys):
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    distribution_store = DistributionStore(release_store)
    target = _signed_distribution_target(distribution_store, release_id)
    store = SubmissionStore(release_store, distribution_store)
    batch = store.create_submission(release_id, {"target_ids": [target.target_id]})
    qa = store.write_qa(release_id, batch.submission_id, build_submission_qa_report(store=store, release_id=release_id, submission=batch))
    build_submission_export_bundle(store=store, release_id=release_id, submission=batch, qa_report=qa)
    build_submission_package_zip(store, release_id, store.get_submission(release_id, batch.submission_id))
    sign_submission_package(store=store, release_id=release_id, submission=store.get_submission(release_id, batch.submission_id), qa_report=qa, payload={"signed_by": "tester"})
    report_path = tmp_path / "submission-verification-report.json"

    monkeypatch.setattr(sys, "argv", ["song-agent", "verify-submission-package", str(store.package_zip_path(release_id, batch.submission_id)), "--json", "--report-out", str(report_path), "--deep"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert '"status": "passed"' in captured.out
    assert report_path.exists()
