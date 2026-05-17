from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

from song_agent.distribution import DistributionStore
from song_agent.distribution_artwork import import_distribution_artwork
from song_agent.distribution_export import build_distribution_export_package, build_distribution_package_zip, sign_distribution_package
from song_agent.distribution_qa import build_distribution_qa_report
from song_agent.submission_export import build_submission_export_bundle, build_submission_package_zip, sign_submission_package
from song_agent.submission_qa import build_submission_qa_report
from song_agent.submission_verifier import verify_submission_package
from song_agent.submissions import SubmissionStore
from tests.test_distribution import _check, _png, _rewrite_zip, _signed_release_with_metadata


def test_submission_batch_export_signoff_and_verify(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    distribution_store = DistributionStore(release_store)
    target = _signed_distribution_target(distribution_store, release_id)
    store = SubmissionStore(release_store, distribution_store)
    batch = store.create_submission(release_id, {"name": "DSP Submission", "target_ids": [target.target_id]})
    qa = store.write_qa(release_id, batch.submission_id, build_submission_qa_report(store=store, release_id=release_id, submission=batch))
    manifest = build_submission_export_bundle(store=store, release_id=release_id, submission=batch, qa_report=qa)
    zip_info = build_submission_package_zip(store, release_id, store.get_submission(release_id, batch.submission_id))
    signoff = sign_submission_package(store=store, release_id=release_id, submission=store.get_submission(release_id, batch.submission_id), qa_report=qa, payload={"signed_by": "tester"})
    report = verify_submission_package(store.package_zip_path(release_id, batch.submission_id), deep=True)

    with zipfile.ZipFile(store.package_zip_path(release_id, batch.submission_id)) as archive:
        names = set(archive.namelist())
        zipped_manifest = json.loads(archive.read("submission-manifest.json").decode("utf-8"))
        zipped_signoff = json.loads(archive.read("submission-signoff.json").decode("utf-8"))

    assert batch.items[0].status == "ready"
    assert qa["status"] in {"passed", "warning"}
    assert manifest["summary"]["status"] == "exported"
    assert zip_info["sha256"]
    assert signoff["status"] == "signed"
    assert report["status"] == "passed"
    assert "submission-targets.csv" in names
    assert f"targets/{target.target_id}/distribution-package.zip" in names
    assert zipped_signoff["export_manifest_hash"] == signoff["export_manifest_hash"]
    assert zipped_manifest["sidecars"]["submission_signoff"]["payload_hash"]


def test_submission_verifier_tamper_guards(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    distribution_store = DistributionStore(release_store)
    target = _signed_distribution_target(distribution_store, release_id)
    store = SubmissionStore(release_store, distribution_store)
    batch = store.create_submission(release_id, {"target_ids": [target.target_id]})
    qa = store.write_qa(release_id, batch.submission_id, build_submission_qa_report(store=store, release_id=release_id, submission=batch))
    build_submission_export_bundle(store=store, release_id=release_id, submission=batch, qa_report=qa)
    build_submission_package_zip(store, release_id, store.get_submission(release_id, batch.submission_id))
    sign_submission_package(store=store, release_id=release_id, submission=store.get_submission(release_id, batch.submission_id), qa_report=qa, payload={"signed_by": "tester"})
    zip_path = store.package_zip_path(release_id, batch.submission_id)

    def tamper_signoff(data: bytes) -> bytes:
        payload = json.loads(data.decode("utf-8"))
        payload["signed_by"] = "tampered"
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    def tamper_target_zip(data: bytes) -> bytes:
        return data + b"tampered"

    tampered_signoff = verify_submission_package(_rewrite_zip(zip_path, tmp_path / "tampered-signoff.zip", transforms={"submission-signoff.json": tamper_signoff}))
    tampered_target = verify_submission_package(_rewrite_zip(zip_path, tmp_path / "tampered-target.zip", transforms={f"targets/{target.target_id}/distribution-package.zip": tamper_target_zip}))
    backslash = _backslash_submission_zip(tmp_path / "backslash-submission.zip")

    assert tampered_signoff["status"] == "failed"
    assert _check(tampered_signoff, "submission_signoff_sidecar_payload_hash")["status"] == "failed"
    assert _any_check(tampered_target, "target_distribution_zip_hash_match")["status"] == "failed"
    assert _check(backslash, "zip_entry_path_safe")["status"] == "failed"


def _signed_distribution_target(store: DistributionStore, release_id: str):
    target = store.create_target(release_id, {"profile_id": "demo_pitch", "name": "Pitch Target"})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    return store.get_target(release_id, target.target_id)


def _backslash_submission_zip(target: Path) -> dict:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("submission-manifest.json", "{}")
        archive.writestr("submission-signoff.json", "{}")
        archive.writestr("submission-report.json", "{}")
        archive.writestr("submission-targets.csv", "a\n")
        archive.writestr("submission-events.jsonl", "")
        archive.writestr("README.txt", "readme")
        archive.writestr("extra/name.txt", "x")
    target.write_bytes(target.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))
    return verify_submission_package(target)


def _any_check(report: dict, check_id: str) -> dict:
    return next(check for check in [*report.get("checks", []), *report.get("item_checks", [])] if check["check_id"] == check_id)
