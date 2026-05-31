from __future__ import annotations

from pathlib import Path

from song_agent.audio_encoding import (
    AudioEncoderConfig,
    AudioEncodingStore,
    FakeEncoderRunner,
    build_ffmpeg_command,
    detect_audio_format_bytes,
    encoded_audio_gate,
    encoded_manifest_integrity_ok,
)
from song_agent.audio_encoding_profiles import AudioEncodingProfileStore, audio_encoding_profile_integrity_ok
from tests.test_mastering_qa import _signed_project
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_audio_encoding_profiles_headers_and_ffmpeg_argv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AudioEncodingProfileStore(Path(".musicforge") / "audio-encoding-profiles")
    mp3 = store.get_profile("mp3_320")
    flac = store.get_profile("flac_lossless")
    assert audio_encoding_profile_integrity_ok(mp3.to_dict())
    assert audio_encoding_profile_integrity_ok(flac.to_dict())
    assert detect_audio_format_bytes(b"ID3\x04\x00\x00data") == "mp3"
    assert detect_audio_format_bytes(b"fLaCxxxx") == "flac"
    assert detect_audio_format_bytes(b"RIFFxxxxWAVEfmt ") == "wav"
    assert detect_audio_format_bytes(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00") == "aac"
    argv = build_ffmpeg_command(source=Path("in.wav"), target=Path("out.mp3"), profile=mp3, config=AudioEncoderConfig(ffmpeg_path="ffmpeg"))
    assert argv[0] == "ffmpeg"
    assert "-i" in argv
    assert "320k" in argv


def test_release_encoded_audio_fake_runner_manifest_and_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Encoding Store Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Encoding Store Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
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
        store = AudioEncodingStore(server.release_store, project_store=server.project_store, profile_store=server.audio_encoding_profile_store, runner=FakeEncoderRunner())
        manifest = store.render_format(release_id, "mp3_320")
        track_path = store.track_audio_path(release_id, "mp3_320", "track-000001")
        assert track_path.stat().st_size < 16 * 1024
        track_path.write_bytes(b"RIFFxxxxWAVEfake")
        stale = store.read_manifest(release_id, "mp3_320")
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert candidate_status == 201
    assert manifest["summary"]["status"] == "completed"
    assert manifest["tracks"][0]["header"]["detected_format"] == "mp3"
    assert encoded_manifest_integrity_ok(manifest)
    assert stale["stale"] is True
    assert "track-000001:output_hash" in stale["stale_reasons"]


def test_fake_encoder_evidence_is_not_valid_for_required_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Fake Evidence Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        _, release = request_json(server, "POST", "/api/releases", {"name": "Fake Evidence Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
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
        store = AudioEncodingStore(server.release_store, project_store=server.project_store, profile_store=server.audio_encoding_profile_store, runner=FakeEncoderRunner())
        manifest = store.render_format(release_id, "mp3_320")
        gate = encoded_audio_gate(store, release_id, required_profiles=["mp3_320"], required=True)
    finally:
        stop_test_server(server)

    assert manifest["encoder"]["runner"]["fake"] is True
    assert gate["status"] == "failed"
    assert gate["fake_profiles"] == ["mp3_320"]
