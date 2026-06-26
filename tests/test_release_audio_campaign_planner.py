from __future__ import annotations

from pathlib import Path

from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
from song_agent.audio_campaign_planner import AudioCampaignPlannerStateError, AudioCampaignPlannerStore
from song_agent.audio_campaigns import AudioCampaignStore
from song_agent.audio_fix_sprints import AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore
from song_agent.projectio import read_json
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_releases import _signed_project, request_json, start_test_server, stop_test_server


def _release_with_audio_track(server, title: str) -> tuple[str, str]:
    project_id = _signed_project(server, title)
    _add_final_export_audio(server, project_id, duration_seconds=30)
    created_status, created = request_json(server, "POST", "/api/releases", {"name": f"{title} Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
    assert created_status == 201
    release_id = created["release"]["release_id"]
    assert request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})[0] == 200
    return release_id, project_id


def test_release_audio_campaign_planner_creates_bound_session_and_campaign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _project_id = _release_with_audio_track(server, "Planner Track")
        planner = AudioCampaignPlannerStore(release_store=server.release_store, project_store=server.project_store, audio_lab_store=server.audio_lab_store, audio_campaign_store=server.audio_campaign_store)

        plan = planner.refresh_plan(release_id)
        preflight = planner.preflight(release_id)
        result = planner.create_campaign_from_release(release_id)
        session = result["session"]
        campaign = result["campaign"]
        link = result["link"]
        case_index = read_json(server.audio_campaign_store.case_index_path(campaign["campaign_id"]))
        release_track = server.release_store.get_release(release_id).tracks[0]
    finally:
        stop_test_server(server)

    assert plan["status"] == "planned"
    assert preflight["status"] == "passed"
    assert session["source"]["source_type"] == "release_audio_campaign_plan"
    assert session["items"][0]["release_id"] == release_id
    assert session["items"][0]["project_id"] == release_track.project_id
    assert session["items"][0]["version_id"] == release_track.version_id
    assert session["items"][0]["final_export_hash"] == release_track.final_export_hash
    assert case_index["cases"][0]["project_id"] == release_track.project_id
    assert case_index["cases"][0]["version_id"] == release_track.version_id
    assert case_index["cases"][0]["final_export_hash"] == release_track.final_export_hash
    assert link["coverage_status"] == "passed"


def test_release_audio_campaign_planner_blocks_unrelated_campaign_link(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    lab = AudioLabStore(wav_writer=None)
    fix_store = AudioFixSprintStore(audio_lab_store=lab)
    server.audio_lab_store = lab
    server.audio_fix_sprint_store = fix_store
    server.audio_campaign_store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=fix_store)
    server.audio_campaign_governance_store = AudioCampaignGovernanceStore(campaign_store=server.audio_campaign_store)
    try:
        release_id, _project_id = _release_with_audio_track(server, "Planner Mismatch Track")
        planner = AudioCampaignPlannerStore(release_store=server.release_store, project_store=server.project_store, audio_lab_store=lab, audio_campaign_store=server.audio_campaign_store)
        planner.refresh_plan(release_id)

        session = lab.create_session_from_items(
            [
                {
                    "item_id": "item-001",
                    "song_id": "wrong",
                    "title": "Wrong Track",
                    "project_id": "wrong-project",
                    "version_id": "v999",
                    "final_export_hash": "wrong-final-export",
                    "artifact_hashes": {"wav_sha256": "1" * 64},
                    "audio_status": "rendered",
                    "renderer": {"runner_kind": "real", "release_ready": True},
                    "source_hash": "wrong-source",
                }
            ],
            {"source_type": "test"},
        )
        lab.write_item_review(session["session_id"], "item-001", {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
        campaign = server.audio_campaign_store.create_campaign({"from_session": session["session_id"]})
        blocked = False
        try:
            planner.link_campaign(release_id, campaign["campaign_id"])
        except AudioCampaignPlannerStateError:
            blocked = True
    finally:
        stop_test_server(server)

    assert blocked is True
