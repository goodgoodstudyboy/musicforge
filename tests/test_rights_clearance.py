from __future__ import annotations

import json

from song_agent.distribution_verifier import verify_distribution_package
from song_agent.release_verifier import verify_release_zip
from song_agent.submission_verifier import verify_submission_package
from tests.test_distribution_encoded_audio import _export_metadata, _rewrite_zip
from tests.test_format_decisions import _prepared_release
from tests.test_server_audio_encoding import _check
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_references import import_reference, wait_for_job


def test_rights_clearance_release_distribution_submission_gate_and_verify(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _prepared_release(server, profiles=["mp3_320"])
        _export_metadata(server, release_id)
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        missing_status, missing = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})

        _complete_rights(server, release_id)
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})
        release_verify = verify_release_zip(server.release_store.zip_path(release_id), require_rights_clearance=True)
        tampered_zip = _rewrite_zip(server.release_store.zip_path(release_id), tmp_path / "tampered-rights.zip", {"rights/report.json": _tamper_rights_report})
        tampered_verify = verify_release_zip(tampered_zip, require_rights_clearance=True)

        request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "test distribution rights"})
        target_status, target = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/distribution/targets",
            {
                "profile_id": "demo_pitch",
                "name": "Rights Target",
                "options": {
                    "require_release_signed": False,
                    "require_release_zip_verified": False,
                    "require_metadata_export": False,
                    "require_artwork": False,
                    "require_rights_clearance": True,
                },
            },
        )
        target_id = target["target"]["target_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, dist_sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})
        dist_zip = server.distribution_store.package_zip_path(release_id, export["manifest"]["package_id"])
        dist_verify = verify_distribution_package(dist_zip, require_rights_clearance=True)

        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})
        sub_status, sub = request_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Rights Submission", "target_ids": [target_id]})
        submission_id = sub["submission"]["submission_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        sub_export_status, _sub_export = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        sub_sign_status, sub_sign = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})
        sub_verify = verify_submission_package(server.submission_store.package_zip_path(release_id, submission_id), require_rights_clearance=True)
    finally:
        stop_test_server(server)

    assert missing_status == 409
    assert "rights clearance" in missing["error"].lower()
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["rights_clearance"]["status"] == "passed"
    assert _check(release_verify, "rights_clearance_evidence")["status"] == "passed"
    assert _check(tampered_verify, "rights_clearance_evidence")["status"] == "failed"
    assert target_status == 201
    assert export_status == 201
    assert dist_sign_status == 200
    assert dist_sign["signoff"]["rights_clearance"]["status"] == "passed"
    assert _check(dist_verify, "distribution_rights_clearance_evidence")["status"] == "passed"
    assert sub_status == 201
    assert sub_export_status == 201
    assert sub_sign_status == 200
    assert sub_sign["signoff"]["rights_clearance"]["status"] == "passed"
    assert _check(sub_verify, "submission_rights_clearance_evidence")["status"] == "passed"


def test_rights_clearance_stale_export_blocks_signoff(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _prepared_release(server, profiles=["mp3_320"])
        _export_metadata(server, release_id)
        _complete_rights(server, release_id)
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        track_status, _track = request_json(server, "POST", f"/api/releases/{release_id}/rights/tracks/track-000001/sources", {"source_usages": [{"source_id": "sample-1", "name": "Uncleared sample", "status": "uncleared", "risk_level": "high"}]})
        refresh_status, report = request_json(server, "POST", f"/api/releases/{release_id}/rights/refresh")
        sign_status, sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})
    finally:
        stop_test_server(server)

    assert track_status == 200
    assert refresh_status == 200
    assert report["report"]["status"] == "failed"
    assert sign_status == 409
    assert "rights clearance" in sign["error"].lower()


def test_rights_clearance_requires_project_reference_provenance(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        reference = import_reference(server)
        ref_payload = [{"reference_id": reference["reference_id"], "role": "style", "strength": 0.7}]
        project_status, project = request_json(server, "POST", "/api/projects", {"name": "Rights Reference Project"})
        project_id = project["project"]["project_id"]
        version_status, version = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": {"title": "Rights Reference Track", "language": "English", "style": "pop", "theme": "rights"}, "reference_refs": ref_payload},
        )
        job = wait_for_job(server, version["job"]["job_id"])
        final_status, _final = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
        export_status, _export = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "tester"})
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Rights Reference Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        track_add_status, _track_add = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        _export_metadata(server, release_id)

        _, party = request_json(server, "POST", f"/api/releases/{release_id}/rights/parties", {"display_name": "Tester", "public_credit_name": "Tester"})
        party_id = party["party"]["party_id"]
        request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/rights/tracks/track-000001",
            {
                "instrumental": True,
                "contributors": [{"party_id": party_id, "role": "composer", "share": 100}],
                "source_usages": [{"source_id": "original-1", "name": "Original composition", "source_type": "original", "status": "original", "risk_level": "low"}],
            },
        )
        request_json(server, "POST", f"/api/releases/{release_id}/rights/tracks/track-000001/review", {"status": "accepted", "review_mode": "manual", "confirmed_by": "tester", "attestation": "Original local composition rights confirmed."})
        request_json(server, "POST", f"/api/releases/{release_id}/rights/refresh")
        first_sign_status, first_sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})
        first_report = server.rights_clearance_store.read_report(release_id)

        source_status, _source = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/rights/tracks/track-000001/sources",
            {
                "source_usages": [
                    {"source_id": "original-1", "name": "Original composition", "source_type": "original", "status": "original", "risk_level": "low"},
                    {"source_id": reference["reference_id"], "name": "Reference Seed", "source_type": "reference", "status": "cleared", "risk_level": "medium", "license_ref": "manual-clearance"},
                ]
            },
        )
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/rights/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        second_sign_status, _second_sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_rights_clearance": True})

        request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "hide reference regression"})
        hide_status, _hidden = request_json(server, "POST", f"/api/references/{reference['reference_id']}/hide")
        hidden_refresh_status, hidden_report = request_json(server, "POST", f"/api/releases/{release_id}/rights/refresh")
    finally:
        stop_test_server(server)

    assert project_status == 201
    assert version_status == 202
    assert job["status"] == "completed"
    assert final_status == 200
    assert export_status == 200
    assert release_status == 201
    assert track_add_status == 200
    assert first_sign_status == 409
    assert "rights clearance" in first_sign["error"].lower()
    assert first_report["tracks"][0]["required_source_count"] >= 1
    assert f"required_source_missing:reference:{reference['reference_id']}" in first_report["tracks"][0]["failures"]
    assert source_status == 200
    assert refresh_status == 200
    assert refreshed["report"]["status"] == "passed"
    assert second_sign_status == 200
    assert hide_status == 200
    assert hidden_refresh_status == 200
    assert hidden_report["report"]["status"] == "failed"
    assert any(f"required_source_hidden:{reference['reference_id']}" in item for item in hidden_report["report"]["failures"])


def _complete_rights(server, release_id: str) -> None:
    _, party = request_json(server, "POST", f"/api/releases/{release_id}/rights/parties", {"display_name": "Tester", "public_credit_name": "Tester"})
    party_id = party["party"]["party_id"]
    request_json(
        server,
        "POST",
        f"/api/releases/{release_id}/rights/tracks/track-000001",
        {
            "instrumental": True,
            "contributors": [{"party_id": party_id, "role": "composer", "share": 100}],
            "source_usages": [{"source_id": "original-1", "name": "Original composition", "status": "original", "risk_level": "low"}],
        },
    )
    request_json(server, "POST", f"/api/releases/{release_id}/rights/tracks/track-000001/review", {"status": "accepted", "review_mode": "manual", "confirmed_by": "tester", "attestation": "Original local composition rights confirmed."})
    status, report = request_json(server, "POST", f"/api/releases/{release_id}/rights/refresh")
    assert status == 200
    assert report["report"]["status"] == "passed"


def _tamper_rights_report(data: bytes) -> bytes:
    payload = json.loads(data.decode("utf-8"))
    payload["status"] = "passed"
    payload["manual_cleared_track_count"] = 99
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
