from __future__ import annotations

from song_agent.release_verifier import verify_release_zip
from tests.test_mastering_qa import _signed_project
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_server_encoded_audio_release_signoff_gate_and_verifier(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Encoded API Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Encoded API Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        candidate_status, candidate = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
        candidate_id = candidate["candidate"]["candidate_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        missing_status, missing = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "required_audio_format_profiles": ["mp3_320"]})
        config_status, _config = request_json(server, "POST", "/api/audio-encoding/config", {"fake_runner": True})
        render_status, render = request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/render", {"profile_ids": ["mp3_320"]})
        stale_export_status, stale_export = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "required_audio_format_profiles": ["mp3_320"]})
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "required_audio_format_profiles": ["mp3_320"]})
        signed_render_status, signed_render = request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/render", {"profile_ids": ["mp3_320"]})
        verify = verify_release_zip(server.release_store.zip_path(release_id), require_encoded_audio=True, required_audio_format_profiles=["mp3_320"])
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert candidate_status == 201
    assert missing_status == 409
    assert "encoded audio" in missing["error"].lower()
    assert config_status == 200
    assert render_status == 201
    assert render["summary"]["status"] == "completed"
    assert stale_export_status == 409
    assert "release export is stale" in stale_export["error"].lower()
    assert export_status == 200
    assert export["manifest"]["encoded_audio"]["profiles"][0]["profile_id"] == "mp3_320"
    assert zip_status == 200
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["encoded_audio"]["status"] == "passed"
    assert signed_render_status == 409
    assert "signed releases" in signed_render["error"].lower()
    assert verify["status"] in {"passed", "warning"}
    assert _check(verify, "encoded_audio_evidence")["status"] == "passed"


def _check(report: dict, check_id: str) -> dict:
    for item in [*report.get("checks", []), *report.get("track_checks", [])]:
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)
