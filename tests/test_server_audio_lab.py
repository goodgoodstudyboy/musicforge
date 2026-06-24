from __future__ import annotations

from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_audio_lab_api_smoke_session_marker_and_compare(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    server.audio_lab_store = AudioLabStore(wav_writer=write_lab_test_wav)
    try:
        env_status, env = request_json(server, "GET", "/api/audio-lab/environment")
        smoke_status, smoke = request_json(server, "POST", "/api/audio-lab/smoke-runs", {"cases": 1, "render_audio": "auto"})
        smoke_id = smoke["smoke_run"]["smoke_run_id"]
        session_status, session_payload = request_json(server, "POST", "/api/audio-lab/listening-sessions", {"from_smoke": smoke_id})
        session = session_payload["session"]
        session_id = session["session_id"]
        item_id = session["items"][0]["item_id"]
        bad_review_status, bad_review = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/review", {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}})
        review_status, review = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/review", {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        marker_status, marker = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/markers", {"time_seconds": 1.5, "category": "mix_balance", "severity": "high", "message": "Hook is masked."})
        marker_id = marker["marker"]["marker_id"]
        draft_status, draft = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/markers/{marker_id}/create-review-task", {"title": "Fix hook mask"})
        report_status, report = request_json(server, "GET", f"/api/audio-lab/listening-sessions/{session_id}/report")
    finally:
        stop_test_server(server)

    assert env_status == 200
    assert env["environment"]["summary"]["test_audio_runner"] is True
    assert smoke_status == 201
    assert smoke["smoke_run"]["summary"]["wav_count"] == 1
    assert session_status == 201
    assert bad_review_status == 400
    assert "playback_confirmed" in bad_review["error"]
    assert review_status == 200
    assert review["review"]["audio_evidence"]["wav_sha256"]
    assert marker_status == 201
    assert draft_status == 201
    assert draft["draft"]["auto_apply"] is False
    assert report_status == 200
    assert report["summary"]["needs_fix_count"] == 1
