from __future__ import annotations

from pathlib import Path

from song_agent.audio_encoding import AudioEncoderConfig
from song_agent.encoded_audio_acceptance import EncodedAudioAcceptanceStore, encoded_audio_acceptance_allows_signoff
from tests.test_mastering_qa import _signed_project
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_encoded_audio_acceptance_health_review_and_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Encoded Acceptance Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        _, release = request_json(server, "POST", "/api/releases", {"name": "Encoded Acceptance Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        _, candidate = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
        candidate_id = candidate["candidate"]["candidate_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        server.audio_encoding_store.runner = _FixtureEncoderRunner()
        server.audio_encoding_store.render_format(release_id, "mp3_320")
        store = EncodedAudioAcceptanceStore(server.release_store, project_store=server.project_store, audio_encoding_store=server.audio_encoding_store)
        health = store.refresh_health(release_id, ["mp3_320"])
        missing = store.build_summary(release_id, required_profiles=["mp3_320"])
        review = store.create_review(release_id, {"profile_id": "mp3_320", "track_id": "track-000001", "status": "accepted", "review_mode": "manual", "reviewer": {"name": "qa"}, "rating": 5, "playback_confirmed": True})
        passed = store.build_summary(release_id, required_profiles=["mp3_320"])
        track_path = server.audio_encoding_store.track_audio_path(release_id, "mp3_320", "track-000001")
        track_path.write_bytes(b"ID3\x04tampered" + (b"\0" * 20000))
        stale_review = store.read_review(release_id, review["review_id"])
    finally:
        stop_test_server(server)

    assert health["summary"]["status"] == "passed"
    assert missing["status"] == "failed"
    assert encoded_audio_acceptance_allows_signoff(missing) is False
    assert passed["status"] == "passed"
    assert encoded_audio_acceptance_allows_signoff(passed) is True
    assert stale_review["stale"] is True


class _FixtureEncoderRunner:
    def encode(self, *, source: Path, target: Path, profile, config: AudioEncoderConfig) -> dict:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x15MusicForgeFixtureMP3" + (b"\0" * 20000))
        return {"status": "completed", "returncode": 0, "message": "Fixture encoder completed."}
