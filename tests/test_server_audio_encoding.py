from __future__ import annotations

import shutil
from pathlib import Path

from song_agent.release_verifier import verify_release_zip
from song_agent.audio_encoding import AudioEncoderConfig
from tests.test_mastering_qa import _signed_project
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_server_encoded_audio_release_signoff_gate_and_verifier(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Encoded API Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Encoded API Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        candidate_status, candidate = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
        candidate_id = candidate["candidate"]["candidate_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        missing_status, missing = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "required_audio_format_profiles": ["mp3_320"]})
        fake_config_status, fake_config = request_json(server, "POST", "/api/audio-encoding/config", {"fake_runner": True})
        server.audio_encoding_store.runner = _FixtureEncoderRunner()
        render_status, render = request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/render", {"profile_ids": ["mp3_320"]})
        stale_export_status, stale_export = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "required_audio_format_profiles": ["mp3_320"]})
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "required_audio_format_profiles": ["mp3_320"]})
        signed_render_status, signed_render = request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/render", {"profile_ids": ["mp3_320"]})
        verify = verify_release_zip(server.release_store.zip_path(release_id), require_encoded_audio=True, required_audio_format_profiles=["mp3_320"])
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert candidate_status == 201
    assert missing_status == 409
    assert "encoded audio" in missing["error"].lower()
    assert fake_config_status == 400
    assert "test-only" in fake_config["error"]
    assert render_status == 201
    assert render["summary"]["status"] == "completed"
    assert stale_export_status == 409
    assert "release export is stale" in stale_export["error"].lower()
    assert export_status == 200
    assert export["manifest"]["encoded_audio"]["profiles"][0]["profile_id"] == "mp3_320"
    assert zip_status == 200
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["encoded_audio"]["status"] == "passed"
    assert signed_render_status == 409
    assert "signed releases" in signed_render["error"].lower()
    assert verify["status"] in {"passed", "warning"}
    assert _check(verify, "encoded_audio_evidence")["status"] == "passed"


def _check(report: dict, check_id: str) -> dict:
    for item in [*report.get("checks", []), *report.get("track_checks", [])]:
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)


class _FixtureEncoderRunner:
    def encode(self, *, source: Path, target: Path, profile, config: AudioEncoderConfig) -> dict:
        target.parent.mkdir(parents=True, exist_ok=True)
        if profile.format == "mp3":
            target.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x15MusicForgeFixtureMP3")
        elif profile.format == "flac":
            target.write_bytes(b"fLaC\x00\x00\x00\"MusicForgeFixtureFLAC")
        elif profile.format == "aac":
            target.write_bytes(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A isommp42")
        elif profile.format == "wav":
            shutil.copy2(source, target)
        else:
            return {"status": "failed", "returncode": None, "message": "Unsupported fixture format."}
        return {"status": "completed", "returncode": 0, "message": "Fixture encoder completed."}
