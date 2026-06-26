from __future__ import annotations

from pathlib import Path

from tests.test_release_audio_campaign_planner import _release_with_audio_track
from tests.test_server_edits import request_json
from tests.test_server_releases import start_test_server, stop_test_server


def test_server_audio_campaign_remediation_routes_and_release_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _project_id = _release_with_audio_track(server, "Server Remediation Track")
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-plan/create", {})
        campaign_id = created["campaign"]["campaign_id"]
        session_id = created["session"]["session_id"]
        item_id = created["session"]["items"][0]["item_id"]
        request_json(
            server,
            "POST",
            f"/api/audio-lab/listening-sessions/{session_id}/items/{item_id}/review",
            {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
        )
        server.audio_lab_store.add_marker(session_id, item_id, {"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "Hook masked."})
        plan_status, plan = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/refresh")
        run_status, run = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/run-safe")
        force_status, force_block = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/signoff",
            {"signed_by": "QA", "force": True, "override_reason": "force must not bypass remediation", "require_audio_campaign_remediation": True},
        )

        sprint_id = server.audio_campaign_store.read_campaign(campaign_id)["cases"][0]["fix"]["fix_sprint_id"]
        fix_store = server.audio_campaign_store.audio_fix_sprint_store
        sprint = fix_store.read_sprint(sprint_id)
        item = sprint["items"][0]
        candidate_id = item["candidates"][0]["candidate_id"]
        fix_store.review_candidate(sprint_id, item["fix_item_id"], candidate_id, {"preferred": "right", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        fix_store.select_candidate(sprint_id, item["fix_item_id"], candidate_id)
        request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/run-safe")
        recheck = fix_store._read_recheck_session(sprint_id)  # type: ignore[attr-defined]
        fix_store.review_recheck_item(sprint_id, recheck["items"][0]["item_id"], {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/run-safe")
        closeout_status, closeout = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/closeout")
        signoff_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/signoff", {"signed_by": "QA", "role": "developer"})
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/zip")
        verify_status, verify = request_json(server, "POST", f"/api/releases/{release_id}/audio-campaign-remediation/verify", {"strict": True, "require_passed": True, "require_signed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        release_status, release_signoff = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/signoff",
            {"signed_by": "QA", "require_audio_campaign_remediation": True, "require_audio_campaign_remediation_signed": True},
        )
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert plan_status == 200
    assert plan["plan"]["status"] == "needs_action"
    assert run_status == 200
    assert run["closeout"]["status"] == "failed"
    assert force_status == 409
    assert force_block["acceptance_gate"]["audio_campaign_remediation"]["hard_block"] is True
    assert closeout_status == 200
    assert closeout["closeout"]["status"] == "passed"
    assert signoff_status == 201
    assert signoff["signoff"]["status"] == "signed"
    assert zip_status == 200
    assert zipped["zip_path"].endswith("audio-campaign-remediation.zip")
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert release_status == 200
    assert release_signoff["signoff"]["acceptance_gate"]["audio_campaign_remediation"]["status"] == "passed"
