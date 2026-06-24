from __future__ import annotations

from song_agent.audio_fix_sprints import AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.projectio import read_json
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _api_source_session(server) -> str:
    status, smoke = request_json(server, "POST", "/api/audio-lab/smoke-runs", {"cases": 1, "render_audio": "auto"})
    assert status == 201
    status, session_payload = request_json(server, "POST", "/api/audio-lab/listening-sessions", {"from_smoke": smoke["smoke_run"]["smoke_run_id"]})
    assert status == 201
    session = session_payload["session"]
    session_id = session["session_id"]
    item_id = session["items"][0]["item_id"]
    raw = read_json(server.audio_lab_store.session_path(session_id))
    raw["items"][0]["renderer"] = {"runner_kind": "real", "profile_id": "test-real", "release_ready": True}
    raw["items"][0]["source_hash"] = "release-ready-source"
    server.audio_lab_store._write_session(raw)
    status, _ = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/review", {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    assert status == 200
    status, _ = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/markers", {"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "Masking."})
    assert status == 201
    return session_id


def test_audio_fix_sprint_api_full_manual_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    server.audio_lab_store = AudioLabStore(wav_writer=write_lab_test_wav)
    server.audio_fix_sprint_store = AudioFixSprintStore(audio_lab_store=server.audio_lab_store)
    try:
        session_id = _api_source_session(server)
        status, create = request_json(server, "POST", "/api/audio-fix-sprints", {"from_session": session_id})
        sprint = create["sprint"]
        sprint_id = sprint["fix_sprint_id"]
        item_id = sprint["items"][0]["fix_item_id"]
        status_dup, duplicate = request_json(server, "POST", "/api/audio-fix-sprints", {"from_session": session_id})
        status_candidates, candidates = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/candidates", {})
        candidate_id = candidates["candidates"][0]["candidate_id"]
        status_select_bad, select_bad = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/items/{item_id}/candidates/{candidate_id}/select", {})
        status_review, _ = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/items/{item_id}/candidates/{candidate_id}/review", {"preferred": "right", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        status_select, _ = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/items/{item_id}/candidates/{candidate_id}/select", {})
        status_recheck, recheck = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/recheck-session", {})
        recheck_item_id = recheck["recheck_session"]["items"][0]["item_id"]
        status_recheck_review, _ = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/recheck-items/{recheck_item_id}/review", {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        status_closeout, closeout = request_json(server, "GET", f"/api/audio-fix-sprints/{sprint_id}/closeout")
        status_close, closed = request_json(server, "POST", f"/api/audio-fix-sprints/{sprint_id}/close", {"closed_by": "QA"})
    finally:
        stop_test_server(server)

    assert status == 201
    assert status_dup == 409
    assert "already assigned" in duplicate["error"]
    assert status_candidates == 201
    assert status_select_bad == 409
    assert "manual A/B" in select_bad["error"]
    assert status_review == 200
    assert status_select == 200
    assert status_recheck == 201
    assert status_recheck_review == 200
    assert status_closeout == 200
    assert closeout["closeout"]["status"] == "passed"
    assert status_close == 200
    assert closed["sprint"]["status"] == "closed"
