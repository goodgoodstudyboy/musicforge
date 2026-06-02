from __future__ import annotations

import json
import sys
from pathlib import Path

from song_agent.distribution import DistributionStore
from song_agent.submission_evidence import SubmissionEvidenceStore
from song_agent.submission_export import build_submission_export_bundle, build_submission_package_zip, sign_submission_package
from song_agent.submission_qa import build_submission_qa_report
from song_agent.submissions import SubmissionStore
from tests.test_distribution import _signed_release_with_metadata
from tests.test_submissions import _signed_distribution_target


def test_cli_verify_submission_evidence_package_json(tmp_path: Path, monkeypatch, capsys) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    distribution_store = DistributionStore(release_store)
    target = _signed_distribution_target(distribution_store, release_id)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    batch = submission_store.create_submission(release_id, {"target_ids": [target.target_id]})
    item_id = batch.items[0].item_id
    qa = submission_store.write_qa(release_id, batch.submission_id, build_submission_qa_report(store=submission_store, release_id=release_id, submission=batch))
    build_submission_export_bundle(store=submission_store, release_id=release_id, submission=batch, qa_report=qa)
    build_submission_package_zip(submission_store, release_id, submission_store.get_submission(release_id, batch.submission_id))
    sign_submission_package(store=submission_store, release_id=release_id, submission=submission_store.get_submission(release_id, batch.submission_id), qa_report=qa, payload={"signed_by": "tester"})
    evidence_store.record_submission(release_id, batch.submission_id, item_id, {"external_reference": "DSP-1"})
    evidence_store.mark_accepted(release_id, batch.submission_id, item_id, {"external_reference": "DSP-1"})
    evidence_store.signoff_evidence(release_id, batch.submission_id, {"signed_by": "tester", "require_accepted": True})
    report_path = tmp_path / "submission-evidence-report.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "song-agent",
            "verify-submission-evidence-package",
            str(evidence_store.package_zip_path(release_id, batch.submission_id)),
            "--json",
            "--report-out",
            str(report_path),
            "--deep",
            "--require-accepted",
        ],
    )
    from song_agent.cli import main

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    output = json.loads(capsys.readouterr().out)
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert output["status"] == "passed"
    assert written["status"] == "passed"
    assert output["summary"]["submission_id"] == batch.submission_id
