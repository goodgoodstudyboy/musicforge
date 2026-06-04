from __future__ import annotations

from tests.test_release_operations_reviewer_pack import accepted_reviewer_fixture

from song_agent.release_operations_reviewer_pack_verifier import verify_release_operations_reviewer_pack


def test_reviewer_pack_verifier_require_flags(tmp_path, monkeypatch) -> None:
    release, _operations_store, _runbook_store, _signoff_store, _audit_store, reviewer_store = accepted_reviewer_fixture(tmp_path, monkeypatch)
    reviewer_store.refresh(release.release_id)
    reviewer_store.export_pack(release.release_id)
    reviewer_store.build_zip(release.release_id)

    report = verify_release_operations_reviewer_pack(
        reviewer_store.zip_path(release.release_id),
        strict=True,
        require_audit=True,
        require_signed=True,
        require_archive=True,
    )

    assert report["status"] == "passed"
    assert any(item["check_id"] == "reviewer_pack_require_audit" and item["status"] == "passed" for item in report["checks"])
    assert any(item["check_id"] == "reviewer_pack_require_signed" and item["status"] == "passed" for item in report["checks"])
    assert any(item["check_id"] == "reviewer_pack_require_archive" and item["status"] == "passed" for item in report["checks"])
