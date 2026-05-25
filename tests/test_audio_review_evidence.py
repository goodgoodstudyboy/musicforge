from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.audio_artifacts import build_audio_artifact_manifest, write_audio_artifact_manifest
from song_agent.audio_review_evidence import AudioReviewEvidenceError, AudioReviewEvidenceStore, map_marker_to_song_plan
from song_agent.renderers.audio import RendererConfig
from song_agent.release_audio import build_release_audio_qa_report, write_release_audio_qa
from song_agent.releases import ReleaseStore
from tests.audio_fixtures import write_silent_wav, write_test_wav
from tests.test_server_edits import request_json, request_payload, start_test_server, stop_test_server, wait_for_job


def test_audio_review_summary_requires_each_track_and_detects_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        first = _signed_audio_project(server, "Audio Review One")
        second = _signed_audio_project(server, "Audio Review Two")
        status, created = request_json(server, "POST", "/api/releases", {"name": "Audio Review Release", "release_type": "ep", "primary_artist": "QA"})
        assert status == 201
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first})
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second})
        store = AudioReviewEvidenceStore(ReleaseStore(project_store=server.project_store), server.project_store)
        _write_audio_qa(store, release_id)

        first_review = store.create_review(release_id, {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "first ok"})
        synthetic = store.create_review(release_id, {"track_id": "track-000002", "status": "accepted", "review_mode": "synthetic", "rating": 5, "playback_confirmed": True, "notes": "synthetic only"})
        summary = store.build_summary(release_id)
        second_review = store.create_review(release_id, {"track_id": "track-000002", "status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True, "notes": "second ok"})
        passed = store.build_summary(release_id)

        first_project_dir = Path(".musicforge") / "projects" / first
        write_silent_wav(first_project_dir / "final-export" / "song.wav", duration_seconds=30)
        stale = store.read_review(release_id, first_review["review_id"])
    finally:
        stop_test_server(server)

    assert summary["status"] == "failed"
    assert summary["manual_accepted_track_count"] == 1
    assert "track-000002" in summary["missing_track_ids"]
    assert synthetic["review_mode"] == "synthetic"
    assert passed["status"] == "passed"
    assert passed["manual_accepted_track_count"] == 2
    assert second_review["stale"] is False
    assert stale["stale"] is True
    assert "wav_changed" in stale["stale_reasons"]


def test_marker_mapping_and_invalid_time(tmp_path: Path, monkeypatch) -> None:
    mapped = map_marker_to_song_plan(
        30.0,
        {
            "tempo_bpm": 120,
            "sections": [
                {"section_id": "section-001", "role": "verse", "start_beat": 0, "duration_beats": 32},
                {"section_id": "section-002", "role": "chorus", "start_beat": 32, "duration_beats": 64},
            ],
        },
    )
    assert mapped["status"] == "mapped"
    assert mapped["section_id"] == "section-002"
    assert mapped["beat"] == 60

    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Invalid Marker")
        status, created = request_json(server, "POST", "/api/releases", {"name": "Invalid Marker Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        store = AudioReviewEvidenceStore(ReleaseStore(project_store=server.project_store), server.project_store)
        with pytest.raises(AudioReviewEvidenceError):
            store.create_review(release_id, {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "markers": [{"time_seconds": 99_999}]})
    finally:
        stop_test_server(server)


def _write_audio_qa(store: AudioReviewEvidenceStore, release_id: str) -> None:
    release = store.release_store.get_release(release_id)
    report = build_release_audio_qa_report(release=release, release_store=store.release_store, project_store=store.project_store, require_audio=True)
    write_release_audio_qa(store.release_store, release_id, report)


def _signed_audio_project(server, title: str) -> str:
    created_status, created = request_json(server, "POST", "/api/projects", {"name": title})
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload(title), "name": title})
    assert version_status == 202
    job = wait_for_job(server, version_data["job"]["job_id"])
    assert job["status"] == "completed"
    assert request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})[0] == 200
    _add_audio_fixture(server, project_id)
    return project_id


def _add_audio_fixture(server, project_id: str) -> None:
    project_dir = Path(".musicforge") / "projects" / project_id
    versions = json.loads((project_dir / "versions.json").read_text(encoding="utf-8"))
    output_dir = Path(versions["versions"][0]["output_dir"])
    write_test_wav(output_dir / "renders" / "song.wav", duration_seconds=30)
    manifest = build_audio_artifact_manifest(
        artifact_id=f"project-{project_id}-v001",
        scope="project_version",
        wav_path=output_dir / "renders" / "song.wav",
        midi_path=output_dir / "renders" / "song.mid",
        song_plan_path=output_dir / "data" / "song-plan.json",
        renderer_config=RendererConfig(soundfont_path="fixture.sf2"),
        extra_source={"project_id": project_id, "version_id": "v001"},
    )
    write_audio_artifact_manifest(output_dir / "renders" / "audio-artifact.json", manifest)
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False, "include_audio": True, "force": True})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip", {"force": True})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff")[0] == 200
