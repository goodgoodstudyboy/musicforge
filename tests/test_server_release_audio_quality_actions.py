from __future__ import annotations

from song_agent.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore
from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_release_audio_quality_observatory import _post_json, _get_json
from tests.test_server_releases import start_test_server, stop_test_server


def test_audio_quality_action_queue_api_and_release_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue API Track")
        create_obs_status, create_obs = _post_json(server, "/api/audio-quality-observatories", {"release_ids": [release_id]})
        observatory_id = create_obs["observatory"]["observatory_id"]
        refresh_obs_status, _refresh_obs = _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/refresh")
        zip_obs_status, _zip_obs = _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/zip")
        verify_obs_status, _verify_obs = _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/verify", {"strict": True, "require_current_evidence": True})

        create_status, create_body = _post_json(server, "/api/audio-quality-actions", {"observatory_id": observatory_id})
        queue_id = create_body["queue"]["queue_id"]
        run_status, run_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/run-safe")
        zip_status, zip_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/zip")
        verify_status, verify_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/verify", {"strict": True, "require_current_observatory": True})
        get_status, get_body = _get_json(server, f"/api/audio-quality-actions/{queue_id}")
        signoff_status, signoff_body = _post_json(
            server,
            f"/api/releases/{release_id}/signoff",
            {
                "require_release_audio_quality_observatory": True,
                "release_audio_quality_observatory_id": observatory_id,
                "require_release_audio_quality_action_queue": True,
                "release_audio_quality_action_queue_id": queue_id,
                "force": True,
                "override_reason": "quality action queue gate smoke",
            },
        )
    finally:
        stop_test_server(server)

    assert create_obs_status == 201
    assert refresh_obs_status == 200
    assert zip_obs_status == 200
    assert verify_obs_status == 200
    assert create_status == 201
    assert run_status == 200
    assert run_body["status"] in {"completed", "completed_with_manual_actions"}
    assert zip_status == 200
    assert zip_body["status"] in {"completed", "completed_with_manual_actions"}
    assert verify_status == 200
    assert verify_body["status"] == "passed", verify_body["verification"].get("blockers")
    assert get_status == 200
    assert get_body["summary_report"]["status"] in {"completed", "completed_with_manual_actions"}
    assert signoff_status == 200, signoff_body
    assert signoff_body["signoff"]["acceptance_gate"]["release_audio_quality_action_queue"]["status"] == "passed"


def test_audio_quality_action_queue_signoff_api_and_release_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue Signoff API Track")
        create_obs_status, create_obs = _post_json(server, "/api/audio-quality-observatories", {"release_ids": [release_id]})
        observatory_id = create_obs["observatory"]["observatory_id"]
        _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/refresh")
        _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/zip")
        _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/verify", {"strict": True, "require_current_evidence": True})

        create_status, create_body = _post_json(server, "/api/audio-quality-actions", {"observatory_id": observatory_id})
        queue_id = create_body["queue"]["queue_id"]
        _post_json(server, f"/api/audio-quality-actions/{queue_id}/run-safe")
        _post_json(server, f"/api/audio-quality-actions/{queue_id}/zip")
        _post_json(server, f"/api/audio-quality-actions/{queue_id}/verify", {"strict": True, "require_current_observatory": True})
        signoff_store = ReleaseAudioQualityActionQueueSignoffStore(
            queue_store=server.release_audio_quality_action_queue_store,
            release_store=server.release_store,
        )
        for item in signoff_store.list_manual_items(queue_id)["manual_items"]:
            resolve_status, resolve_body = _post_json(
                server,
                f"/api/audio-quality-actions/{queue_id}/resolve-manual",
                {"item_id": item["item_id"], "status": "completed", "resolved_by": "api", "reason": "Handled."},
            )
            assert resolve_status == 200, resolve_body
        closeout_status, closeout_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/closeout")
        signoff_status, signoff_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/signoff", {"signed_by": "api", "reason": "Accepted."})
        archive_status, archive_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/archive-zip")
        verify_status, verify_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/archive-verify", {"strict": True, "require_current_queue": True})
        rerun_status, rerun_body = _post_json(server, f"/api/audio-quality-actions/{queue_id}/run-safe")
        release_status, release_body = _post_json(
            server,
            f"/api/releases/{release_id}/signoff",
            {
                "require_release_audio_quality_action_queue_signoff": True,
                "release_audio_quality_action_queue_id": queue_id,
                "force": True,
                "override_reason": "quality action signoff API gate smoke",
            },
        )
    finally:
        stop_test_server(server)

    assert create_obs_status == 201
    assert create_status == 201
    assert closeout_status == 200
    assert closeout_body["closeout"]["status"] == "passed"
    assert signoff_status == 200
    assert signoff_body["signoff"]["status"] == "signed"
    assert archive_status == 200
    assert archive_body["status"] == "passed"
    assert verify_status == 200
    assert verify_body["verification"]["status"] == "passed", verify_body["verification"].get("blockers")
    assert rerun_status == 409
    assert "signed" in rerun_body.get("error", "").lower()
    assert release_status == 200, release_body
    assert release_body["signoff"]["acceptance_gate"]["release_audio_quality_action_queue_signoff"]["status"] == "passed"
