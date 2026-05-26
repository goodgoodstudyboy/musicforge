from __future__ import annotations

from pathlib import Path

from song_agent.audio_artifacts import build_audio_artifact_manifest, write_audio_artifact_manifest
from song_agent.projectio import read_json, write_json
from song_agent.renderers.audio import RendererConfig
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job
from tests.audio_fixtures import write_test_wav


def test_server_mix_preview_apply_stem_health_and_marker_draft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = _project(server)
        parent_plan_before = (Path(parent_job["output_dir"]) / "data" / "song-plan.json").read_bytes()

        state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/mix-state")
        preview_status, preview = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/mix-preview",
            {"operations": [{"op": "set_track_volume", "track_id": "track-001", "volume_db": -3}, {"op": "set_track_pan", "track_id": "track-001", "pan": 40}], "label": "melody softer"},
        )
        preview_id = preview["preview"]["preview_id"]
        apply_status, applied = request_json(server, "POST", f"/api/projects/{project_id}/versions/v001/mix-preview/{preview_id}/apply", {"version_name": "Mix Child"})
        child = wait_for_job(server, applied["job"]["job_id"])
        stems_status, stems = request_json(server, "POST", f"/api/projects/{project_id}/versions/v002/mix-stems/render", {"require_wav": False})
        final_status, _final = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v002"})
        export_status, export = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stem_audio": False})

        final_dir = Path(".musicforge") / "projects" / project_id / "final-export"
        write_test_wav(final_dir / "song.wav", duration_seconds=10)
        manifest = build_audio_artifact_manifest(
            artifact_id=f"project-{project_id}-v002",
            scope="project_final_export",
            wav_path=final_dir / "song.wav",
            midi_path=final_dir / "song.mid",
            song_plan_path=final_dir / "song-plan.json",
            renderer_config=RendererConfig(soundfont_path="fixture.sf2"),
            extra_source={"project_id": project_id, "version_id": "v002"},
        )
        write_audio_artifact_manifest(final_dir / "audio-artifact.json", manifest)
        request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip", {"force": True})
        request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": "mix test audio fixture"})
        request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "tester"})

        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Mix Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": False})
        review_status, review = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "markers": [{"time_seconds": 1, "category": "mix_balance", "message": "melody low"}]})
        marker_status, marker = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/{review['review']['review_id']}/markers/m-000001/mix-patch-draft", {})
    finally:
        stop_test_server(server)

    assert state_status == 200
    assert state["mix_state"]["tracks"]
    assert preview_status == 201
    assert preview["preview"]["summary"]["operation_count"] == 2
    assert apply_status == 201
    assert applied["version"]["version_id"] == "v002"
    assert applied["version"]["variant_type"] == "mix_control_edit"
    assert child["status"] == "completed"
    assert (Path(parent_job["output_dir"]) / "data" / "song-plan.json").read_bytes() == parent_plan_before
    assert stems_status == 200
    assert stems["summary"]["status"] in {"passed", "warning"}
    assert final_status == 200
    assert export_status == 200
    assert export["final_export"]["mix"]["mix_state_integrity_ok"] is True
    assert (final_dir / "mix-state.json").exists()
    assert (final_dir / "stems" / "stem-health.json").exists()
    assert release_status == 201
    assert review_status == 201
    assert marker_status == 201
    assert marker["patch"]["source"]["source_type"] == "release_audio_review_marker"


def _project(server):
    created_status, created = request_json(server, "POST", "/api/projects", {"name": "Mix Project"})
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions",
        {"request": {"title": "Mix Song", "language": "English", "style": "pop", "theme": "mix"}, "name": "Parent"},
    )
    assert version_status == 202
    job = wait_for_job(server, version["job"]["job_id"])
    assert job["status"] == "completed"
    return project_id, job
