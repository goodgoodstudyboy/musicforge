from __future__ import annotations

from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
from song_agent.audio_campaigns import AudioCampaignStore
from song_agent.audio_fix_sprints import AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_releases import _signed_project, request_json, start_test_server, stop_test_server


def test_release_audio_campaign_plan_api_create_and_release_signoff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    lab = AudioLabStore()
    fix_store = AudioFixSprintStore(audio_lab_store=lab)
    server.audio_lab_store = lab
    server.audio_fix_sprint_store = fix_store
    server.audio_campaign_store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=fix_store)
    server.audio_campaign_governance_store = AudioCampaignGovernanceStore(campaign_store=server.audio_campaign_store)
    try:
        project_id = _signed_project(server, "Planner API Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Planner API Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})

        refresh_status, refresh = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-plan/refresh")
        preflight_status, preflight = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-plan/preflight")
        create_status, created_campaign = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-plan/create")
        campaign_id = created_campaign["campaign"]["campaign_id"]
        session_id = created_campaign["session"]["session_id"]
        item_id = created_campaign["session"]["items"][0]["item_id"]
        review_status, _review = request_json(server, "POST", f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/review", {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        report_status, report = request_json(server, "GET", f"/api/audio-campaigns/{campaign_id}/report")
        signoff_status, _campaign_signoff = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/signoff", {"signed_by": "QA", "role": "developer"})
        archive_status, archive = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/archive/zip")
        verify_status, _verify = request_json(server, "POST", f"/api/audio-campaigns/{campaign_id}/archive/verify", {"strict": True})
        assert archive_status == 200, archive
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        release_sign_status, signed = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/signoff",
            {
                "signed_by": "tester",
                "require_audio_campaign": True,
                "audio_campaign_id": campaign_id,
                "audio_campaign_archive_zip_path": archive["zip_path"],
                "audio_campaign_archive_verification_report_path": str(server.audio_campaign_governance_store.archive_verification_report_path(campaign_id)),
            },
        )
        status_status, status = request_json(server, "GET", f"/api/releases/{release_id}/audio-campaign-plan/status")
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert refresh["plan"]["status"] == "planned"
    assert preflight_status == 200
    assert preflight["preflight"]["status"] == "passed"
    assert create_status == 201
    assert created_campaign["link"]["coverage_status"] == "passed"
    assert review_status == 200
    assert report_status == 200
    assert report["report"]["status"] == "passed"
    assert signoff_status == 200
    assert verify_status == 200
    assert release_sign_status == 200
    assert signed["signoff"]["acceptance_gate"]["audio_campaign"]["release_track_coverage"]["matched_track_count"] == 1
    assert status_status == 200
    assert status["summary"]["coverage_status"] == "passed"
