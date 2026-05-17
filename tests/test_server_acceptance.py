from __future__ import annotations

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_acceptance_api_end_to_end_and_signed_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        create_status, created = request_json(server, "POST", "/api/acceptance/suites", {"name": "Server Acceptance", "min_rating": 3})
        suite_id = created["suite"]["suite_id"]
        list_status, listing = request_json(server, "GET", "/api/acceptance/suites")
        case_status, case_data = request_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {"name": "upbeat pop", "request": {"title": "Server Song", "language": "English", "style": "upbeat pop", "theme": "api", "duration_seconds": 90}},
        )
        case_id = case_data["case"]["case_id"]
        generate_status, generated = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        health_status, health = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        midi_status, midi = request_bytes(server, "GET", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/midi")
        missing_audio_status, missing_audio = request_json(server, "GET", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/audio")
        bad_review_status, bad_review = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 4, "status": "accepted", "playback_confirmed": False, "notes": "Should be rejected by playback guard."})
        review_status, review = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "I listened to the MIDI and the structure is acceptable.", "audio_mode": "midi"})
        report_status, report = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        sign_status, signoff = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/signoff", {"signed_by": "server-test"})
        blocked_review_status, blocked_review = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "Cannot change signed review.", "audio_mode": "midi"})
        blocked_audio_status, blocked_audio = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/render-audio", {"mode": "never"})
        blocked_archive_status, blocked_archive = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/archive")
        reset_status, reset = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/signoff/reset", {"reason": "review update"})
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert list_status == 200
    assert listing["summary"]["suite_count"] == 1
    assert case_status == 201
    assert generate_status == 200
    assert generated["case"]["status"] == "generated"
    assert health_status == 200
    assert health["health"]["status"] in {"passed", "warning"}
    assert midi_status == 200
    assert midi.startswith(b"MThd")
    assert missing_audio_status == 404
    assert bad_review_status == 400
    assert "playback_confirmed" in bad_review["error"]
    assert review_status == 200
    assert review["summary"]["status"] == "accepted"
    assert report_status == 200
    assert report["summary"]["status"] == "passed"
    assert sign_status == 200
    assert signoff["summary"]["status"] == "signed"
    assert blocked_review_status == 409
    assert "signed" in blocked_review["error"].lower()
    assert blocked_audio_status == 409
    assert "signed" in blocked_audio["error"].lower()
    assert blocked_archive_status == 409
    assert "signed" in blocked_archive["error"].lower()
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
