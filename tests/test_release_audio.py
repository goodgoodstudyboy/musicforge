from __future__ import annotations

import json
from pathlib import Path

from song_agent.release_verifier import verify_release_zip
from song_agent.audio_artifacts import build_audio_artifact_manifest, write_audio_artifact_manifest
from song_agent.renderers.audio import RendererConfig
from song_agent.audio_profiles import AudioProfileStore
from tests.audio_fixtures import write_silent_wav, write_test_wav
from tests.test_server_edits import request_json, request_payload, start_test_server, stop_test_server, wait_for_job


def test_release_audio_qa_and_signoff_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Real Audio Release Track")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Real Audio Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        missing_audio_status, missing_audio = request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        sign_missing_status, sign_missing = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True})

        _add_final_export_audio(server, project_id, duration_seconds=30)
        request_json(server, "POST", f"/api/releases/{release_id}/tracks/track-000001/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_status, audio = request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        export_status, _export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")

        suite_id = _manual_wav_acceptance_suite(server)
        sign_status, signed = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/signoff",
            {"signed_by": "tester", "acceptance_suite_id": suite_id, "require_audio_health": True, "require_human_audio_review": True},
        )
        verify_report = verify_release_zip(Path(".musicforge") / "releases" / release_id / "release-export.zip", require_audio=True, require_human_review=True)
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert missing_audio_status == 200
    assert missing_audio["summary"]["status"] == "failed"
    assert sign_missing_status == 409
    assert "Audio QA" in sign_missing["error"]
    assert audio_status == 200
    assert audio["summary"]["status"] == "passed"
    assert export_status == 200
    assert zip_status == 200
    assert sign_status == 200
    assert signed["signoff"]["acceptance_gate"]["audio"]["status"] == "passed"
    assert signed["signoff"]["acceptance_gate"]["audio"]["manual_audio_accepted_count"] == 1
    assert verify_report["status"] in {"passed", "warning"}
    assert _check(verify_report, "human_audio_review_evidence")["status"] == "passed"


def test_release_audio_qa_detects_failed_and_stale_audio(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Failed Audio Release Track")
        project_dir = Path(".musicforge") / "projects" / project_id
        _add_final_export_audio(server, project_id, silent=True, duration_seconds=30)
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Failed Audio Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        failed_status, failed = request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        write_test_wav(project_dir / "final-export" / "song.wav", duration_seconds=30)
        stale_sign_status, stale_sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True})
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert failed_status == 200
    assert failed["summary"]["status"] == "failed"
    assert stale_sign_status == 409
    assert "stale" in stale_sign["error"].lower()


def test_release_audio_qa_detects_changed_renderer_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Profile Stale Audio Track")
        soundfont = tmp_path / "profile.sf2"
        soundfont.write_bytes(b"profile")
        profile = AudioProfileStore(tmp_path / ".musicforge" / "audio-profiles").upsert_profile({"name": "QA Profile", "soundfont_path": str(soundfont), "sample_rate": 44100})
        _add_final_export_audio(server, project_id, duration_seconds=30, profile=profile)
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Profile Stale Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        AudioProfileStore(tmp_path / ".musicforge" / "audio-profiles").upsert_profile({"profile_id": profile.profile_id, "soundfont_path": str(soundfont), "sample_rate": 48000})
        stale_status, stale = request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert stale_status == 200
    assert stale["summary"]["status"] == "failed"
    track = stale["audio_qa"]["tracks"][0]
    assert "renderer_profile_changed" in track["artifact"]["stale_reasons"]


def test_verify_release_requires_human_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Verifier Human Review Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Verifier Human Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester"})
        zip_path = Path(".musicforge") / "releases" / release_id / "release-export.zip"
        missing_human = verify_release_zip(zip_path, require_audio=True, require_human_review=True)
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert missing_human["status"] == "failed"
    assert _check(missing_human, "human_audio_review_evidence")["status"] == "failed"


def _signed_project(server, title: str) -> str:
    created_status, created = request_json(server, "POST", "/api/projects", {"name": title})
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload(title), "name": title})
    assert version_status == 202
    job = wait_for_job(server, version_data["job"]["job_id"])
    assert job["status"] == "completed"
    assert request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "server-test"})[0] == 200
    return project_id


def _add_final_export_audio(server, project_id: str, *, silent: bool = False, duration_seconds: float = 30, profile=None) -> None:
    project_dir = Path(".musicforge") / "projects" / project_id
    versions = json.loads((project_dir / "versions.json").read_text(encoding="utf-8"))
    output_dir = Path(versions["versions"][0]["output_dir"])
    wav_path = output_dir / "renders" / "song.wav"
    if silent:
        write_silent_wav(wav_path, duration_seconds=duration_seconds)
    else:
        write_test_wav(wav_path, duration_seconds=duration_seconds)
    manifest = build_audio_artifact_manifest(
        artifact_id=f"project-{project_id}-v001",
        scope="project_version",
        wav_path=wav_path,
        midi_path=output_dir / "renders" / "song.mid",
        song_plan_path=output_dir / "data" / "song-plan.json",
        renderer_config=RendererConfig(soundfont_path="fixture.sf2"),
        profile=profile,
        extra_source={"project_id": project_id, "version_id": "v001"},
    )
    write_audio_artifact_manifest(output_dir / "renders" / "audio-artifact.json", manifest)
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False, "include_audio": True, "force": True})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip", {"force": True})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": "add audio fixture"})[0] == 200
    assert request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "server-test"})[0] == 200


def _manual_wav_acceptance_suite(server) -> str:
    suite_status, suite_data = request_json(server, "POST", "/api/acceptance/suites", {"name": "Manual WAV Evidence", "profile_id": "developer_manual", "require_manual_review": True})
    assert suite_status == 201
    suite_id = suite_data["suite"]["suite_id"]
    case_status, case_data = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"request": {"title": "Manual WAV", "language": "English", "style": "pop", "theme": "audio", "duration_seconds": 30}})
    assert case_status == 201
    case_id = case_data["case"]["case_id"]
    request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
    case_dir = Path(".musicforge") / "acceptance" / suite_id / "cases" / case_id
    write_test_wav(case_dir / "song.wav", duration_seconds=30)
    request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
    review_status, _review = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Manual WAV listening review confirms the rendered audio is acceptable.", "audio_mode": "wav", "review_mode": "manual"})
    assert review_status == 200
    report_status, report = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
    assert report_status == 200
    assert report["summary"]["manual_audio_accepted_count"] == 1
    return suite_id


def _check(report: dict, check_id: str) -> dict:
    for item in [*report.get("checks", []), *report.get("track_checks", [])]:
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)
