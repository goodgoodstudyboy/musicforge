from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

from song_agent.distribution import DistributionStore
from song_agent.submission_evidence import SubmissionEvidenceStateError, SubmissionEvidenceStore
from song_agent.submission_evidence_verifier import verify_submission_evidence_package
from song_agent.submission_export import build_submission_export_bundle, build_submission_package_zip, sign_submission_package
from song_agent.submission_qa import build_submission_qa_report
from song_agent.submissions import SubmissionStore
from tests.test_distribution import _check, _rewrite_zip, _signed_release_with_metadata
from tests.test_submissions import _signed_distribution_target


def test_submission_evidence_archive_export_signoff_and_verify(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    distribution_store = DistributionStore(release_store)
    target = _signed_distribution_target(distribution_store, release_id)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    batch = submission_store.create_submission(release_id, {"name": "Evidence Submission", "target_ids": [target.target_id]})
    item_id = batch.items[0].item_id
    qa = submission_store.write_qa(release_id, batch.submission_id, build_submission_qa_report(store=submission_store, release_id=release_id, submission=batch))
    build_submission_export_bundle(store=submission_store, release_id=release_id, submission=batch, qa_report=qa)
    build_submission_package_zip(submission_store, release_id, submission_store.get_submission(release_id, batch.submission_id))
    sign_submission_package(store=submission_store, release_id=release_id, submission=submission_store.get_submission(release_id, batch.submission_id), qa_report=qa, payload={"signed_by": "tester"})

    attachment = evidence_store.upload_attachment(
        release_id,
        batch.submission_id,
        item_id,
        {"filename": "receipt.txt", "content_type": "text/plain", "content_base64": base64.b64encode(b"submitted").decode("ascii")},
    )
    submitted, receipt = evidence_store.record_submission(release_id, batch.submission_id, item_id, {"external_reference": "DSP-1", "attachment_ids": [attachment["attachment_id"]]})
    feedback, feedback_evidence = evidence_store.record_feedback(release_id, batch.submission_id, item_id, {"status": "needs_changes", "message": "metadata"})
    accepted, accepted_evidence = evidence_store.mark_accepted(release_id, batch.submission_id, item_id, {"external_reference": "DSP-1"})
    report = evidence_store.refresh_report(release_id, batch.submission_id)
    manifest = evidence_store.export_evidence(release_id, batch.submission_id)
    zip_info = evidence_store.build_zip(release_id, batch.submission_id)
    signoff = evidence_store.signoff_evidence(release_id, batch.submission_id, {"signed_by": "tester", "require_submitted": True, "require_accepted": True})
    verified = verify_submission_evidence_package(evidence_store.package_zip_path(release_id, batch.submission_id), deep=True, require_submitted=True, require_accepted=True)

    assert attachment["sha256"]
    assert receipt["evidence_type"] == "submission_receipt"
    assert submitted.status == "submitted"
    assert feedback.status == "needs_changes"
    assert feedback_evidence["evidence_type"] == "needs_changes_notice"
    assert accepted.status == "accepted"
    assert accepted_evidence["evidence_type"] == "acceptance_confirmation"
    assert report["status"] == "passed"
    assert manifest["summary"]["accepted_count"] == 1
    assert zip_info["sha256"]
    assert signoff["status"] == "signed"
    assert verified["status"] == "passed"
    with zipfile.ZipFile(evidence_store.package_zip_path(release_id, batch.submission_id)) as archive:
        names = set(archive.namelist())
    assert "submission-package.zip" in names
    assert "submission-evidence-signoff.json" in names

    try:
        evidence_store.record_feedback(release_id, batch.submission_id, item_id, {"status": "needs_changes", "message": "late"})
    except SubmissionEvidenceStateError as exc:
        assert "signed" in str(exc).lower()
    else:
        raise AssertionError("signed evidence archive accepted a new record")


def test_submission_evidence_source_path_and_tamper_guards(tmp_path: Path) -> None:
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

    try:
        evidence_store.upload_attachment(release_id, batch.submission_id, item_id, {"filename": "receipt.txt", "content_type": "text/plain", "source_path": str(tmp_path / "receipt.txt")})
    except Exception as exc:
        assert "source_path" in str(exc)
    else:
        raise AssertionError("source_path attachment was accepted")

    evidence_store.record_submission(release_id, batch.submission_id, item_id, {"external_reference": "DSP-1"})
    evidence_store.mark_accepted(release_id, batch.submission_id, item_id, {"external_reference": "DSP-1"})
    evidence_store.signoff_evidence(release_id, batch.submission_id, {"signed_by": "tester", "require_accepted": True})
    zip_path = evidence_store.package_zip_path(release_id, batch.submission_id)

    def tamper_signoff(data: bytes) -> bytes:
        payload = json.loads(data.decode("utf-8"))
        payload["signed_by"] = "tampered"
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    def tamper_report(data: bytes) -> bytes:
        payload = json.loads(data.decode("utf-8"))
        payload["summary"]["accepted_count"] = 99
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    tampered_signoff = verify_submission_evidence_package(_rewrite_zip(zip_path, tmp_path / "tampered-evidence-signoff.zip", transforms={"submission-evidence-signoff.json": tamper_signoff}))
    tampered_report = verify_submission_evidence_package(_rewrite_zip(zip_path, tmp_path / "tampered-evidence-report.zip", transforms={"submission-evidence-report.json": tamper_report}))

    assert tampered_signoff["status"] == "failed"
    assert _check(tampered_signoff, "submission_evidence_signoff_sidecar_payload_hash")["status"] == "failed"
    assert tampered_report["status"] == "failed"
    assert _check(tampered_report, "submission_evidence_report_hash")["status"] == "failed"
