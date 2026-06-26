from __future__ import annotations

from song_agent.projectio import read_json, write_json
from tests.test_release_audio_timeline import _prepare_timeline_release
from tests.test_server_releases import request_json, start_test_server, stop_test_server


def test_release_audio_timeline_api_refresh_signoff_zip_verify(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, _store = _prepare_timeline_release(server, "Timeline API Track")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/audio-timelines/refresh")
        timeline_id = refreshed["timeline_id"]
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/audio-timelines/{timeline_id}/signoff", {"signed_by": "QA", "role": "developer"})
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/audio-timelines/{timeline_id}/zip")
        verify_status, verified = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-timelines/{timeline_id}/verify",
            {"strict": True, "require_passed": True, "require_signed": True, "require_real_audio": True, "require_manual_review": True, "require_current_certification": True},
        )
        detail_status, detail = request_json(server, "GET", f"/api/releases/{release_id}/audio-timelines/{timeline_id}")
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert refreshed["report"]["status"] == "passed"
    assert sign_status == 201
    assert signed["status"] == "signed"
    assert zip_status == 200
    assert zipped["zip_sha256"]
    assert verify_status == 200
    assert verified["status"] == "passed", verified.get("blockers")
    assert detail_status == 200
    assert detail["report"]["status"] == "passed"
    assert detail["signoff"]["status"] == "signed"


def test_release_signoff_requires_current_release_audio_timeline_even_when_forced(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, _store = _prepare_timeline_release(server, "Timeline Signoff Gate Track")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/audio-timelines/refresh")
        timeline_id = refreshed["timeline_id"]
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/audio-timelines/{timeline_id}/signoff", {"signed_by": "QA", "role": "developer"})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        release_signoff_status, release_signoff = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/signoff",
            {
                "signed_by": "QA",
                "force": True,
                "override_reason": "timeline gate positive coverage",
                "require_release_audio_timeline": True,
                "require_release_audio_timeline_signed": True,
            },
        )

        stale_release_id, _stale_campaign_id, _stale_store = _prepare_timeline_release(server, "Timeline Signoff Stale Track")
        stale_refresh_status, stale_refreshed = request_json(server, "POST", f"/api/releases/{stale_release_id}/audio-timelines/refresh")
        stale_timeline_id = stale_refreshed["timeline_id"]
        request_json(server, "POST", f"/api/releases/{stale_release_id}/audio-timelines/{stale_timeline_id}/signoff", {"signed_by": "QA", "role": "developer"})
        request_json(server, "POST", f"/api/releases/{stale_release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{stale_release_id}/export")
        request_json(server, "POST", f"/api/releases/{stale_release_id}/export/zip")
        track = server.release_store.get_release(stale_release_id).tracks[0]
        manifest_path = server.project_store.project_dir(track.project_id) / "final-export" / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["tampered_after_timeline_signoff"] = True
        write_json(manifest_path, manifest)
        stale_signoff_status, stale_signoff = request_json(
            server,
            "POST",
            f"/api/releases/{stale_release_id}/signoff",
            {
                "signed_by": "QA",
                "force": True,
                "override_reason": "force must not bypass timeline gate",
                "require_release_audio_timeline": True,
                "require_release_audio_timeline_signed": True,
            },
        )
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert sign_status == 201
    assert signed["status"] == "signed"
    assert release_signoff_status == 200
    assert release_signoff["signoff"]["acceptance_gate"]["release_audio_timeline"]["status"] == "passed"
    assert stale_refresh_status == 200
    assert stale_signoff_status == 409
    assert stale_signoff["acceptance_gate"]["release_audio_timeline"]["hard_block"] is True
    assert "stale" in stale_signoff["acceptance_gate"]["release_audio_timeline"]["message"].lower()
