from __future__ import annotations

from song_agent.audio_campaigns import AudioCampaignStore
from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
from song_agent.audio_fix_sprints import AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.projectio import read_json
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_audio_campaign_api_full_real_signoff_verify(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    fix_store = AudioFixSprintStore(audio_lab_store=lab)
    server.audio_lab_store = lab
    server.audio_fix_sprint_store = fix_store
    server.audio_campaign_store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=fix_store)
    server.audio_campaign_governance_store = AudioCampaignGovernanceStore(campaign_store=server.audio_campaign_store)
    try:
        _, smoke = request_json(server, "POST", "/api/audio-lab/smoke-runs", {"cases": 1, "render_audio": "auto"})
        _, session_payload = request_json(server, "POST", "/api/audio-lab/listening-sessions", {"from_smoke": smoke["smoke_run"]["smoke_run_id"]})
        session = session_payload["session"]
        raw = read_json(lab.session_path(session["session_id"]))
        raw["items"][0]["renderer"] = {"runner_kind": "real", "release_ready": True, "profile_id": "test-real"}
        raw["items"][0]["source_hash"] = "api-real-source"
        lab._write_session(raw)  # type: ignore[attr-defined]
        item_id = session["items"][0]["item_id"]
        review_status, _ = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session['session_id']}/items/{item_id}/review", {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        create_status, created = request_json(server, "POST", "/api/audio-campaigns", {"from_session": session["session_id"]})
        campaign_id = created["campaign"]["campaign_id"]
        report_status, report = request_json(server, "GET", f"/api/audio-campaigns/{campaign_id}/report")
        signoff_status, signoff = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/signoff", {"signed_by": "QA", "role": "developer"})
        zip_status, zipped = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/zip")
        verify_status, verify = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/verify", {"require_real_audio": True, "require_manual_review": True, "require_signed": True})
    finally:
        stop_test_server(server)

    assert review_status == 200
    assert create_status == 201
    assert report_status == 200
    assert report["report"]["status"] == "passed"
    assert signoff_status == 200
    assert signoff["signoff"]["status"] == "signed"
    assert zip_status == 200
    assert zipped["zip_sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"


def test_audio_campaign_governance_api_archive_and_reset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    fix_store = AudioFixSprintStore(audio_lab_store=lab)
    server.audio_lab_store = lab
    server.audio_fix_sprint_store = fix_store
    server.audio_campaign_store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=fix_store)
    server.audio_campaign_governance_store = AudioCampaignGovernanceStore(campaign_store=server.audio_campaign_store)
    try:
        _, smoke = request_json(server, "POST", "/api/audio-lab/smoke-runs", {"cases": 1, "render_audio": "auto"})
        _, session_payload = request_json(server, "POST", "/api/audio-lab/listening-sessions", {"from_smoke": smoke["smoke_run"]["smoke_run_id"]})
        session = session_payload["session"]
        raw = read_json(lab.session_path(session["session_id"]))
        raw["items"][0]["renderer"] = {"runner_kind": "real", "release_ready": True, "profile_id": "test-real"}
        raw["items"][0]["source_hash"] = "api-governance-real-source"
        lab._write_session(raw)  # type: ignore[attr-defined]
        item_id = session["items"][0]["item_id"]
        request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session['session_id']}/items/{item_id}/review", {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        _, created = request_json(server, "POST", "/api/audio-campaigns", {"from_session": session["session_id"]})
        campaign_id = created["campaign"]["campaign_id"]
        request_json(server, "GET", f"/api/audio-campaigns/{campaign_id}/report")
        request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/signoff", {"signed_by": "QA", "role": "developer"})
        archive_status, archive = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/archive/zip")
        verify_status, verify = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/archive/verify", {"strict": True})
        cr_status, cr_payload = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/change-requests", {"reason": "Need reset"})
        cr_id = cr_payload["change_request"]["change_request_id"]
        approve_status, _ = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/change-requests/{cr_id}/approve", {"approved_by": "Lead"})
        reset_status, reset = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/signoff/reset", {"change_request_id": cr_id, "reason": "Approved"})
    finally:
        stop_test_server(server)

    assert archive_status == 200
    assert archive["zip_sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert cr_status == 201
    assert approve_status == 200
    assert reset_status == 200
    assert reset["status"] == "reset"
