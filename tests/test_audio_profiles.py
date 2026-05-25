from __future__ import annotations

import json
from pathlib import Path

from song_agent.audio_profiles import AudioProfileStore
from tests.test_server_audio import create_completed_job, fake_render_audio
from song_agent.projectio import write_json
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_audio_profile_store_redacts_paths_and_hashes_soundfont(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    soundfont = tmp_path / "gm.sf2"
    soundfont.write_bytes(b"soundfont")
    store = AudioProfileStore(tmp_path / ".musicforge" / "audio-profiles")

    profile = store.upsert_profile({"name": "Local FluidSynth", "engine_path": r"C:\tools\fluidsynth.exe", "soundfont_path": str(soundfont), "is_default": True})
    summary = profile.public_summary()

    assert profile.profile_id == "arp-000001"
    assert summary["paths_redacted"] is True
    assert "engine_path" not in summary
    assert "soundfont_path" not in summary
    assert summary["soundfont_sha256"]
    assert summary["profile_hash"]
    assert store.get_profile().profile_id == profile.profile_id


def test_audio_profile_legacy_renderer_compatibility(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    soundfont = tmp_path / "legacy.sf2"
    soundfont.write_bytes(b"legacy")
    write_json(Path(".musicforge") / "renderer.json", {"renderer_type": "fluidsynth", "fluidsynth_path": "fluidsynth", "soundfont_path": str(soundfont), "sample_rate": 48000, "gain": 0.5})

    profile = AudioProfileStore(tmp_path / ".musicforge" / "audio-profiles").get_profile()
    summary = profile.public_summary()

    assert profile.profile_id == "arp-legacy"
    assert AudioProfileStore(tmp_path / ".musicforge" / "audio-profiles").list_profiles()[0].profile_id == "arp-legacy"
    assert summary["sample_rate"] == 48000
    assert summary["paths_redacted"] is True


def test_audio_profile_api_crud(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        soundfont = tmp_path / "api.sf2"
        soundfont.write_bytes(b"api-soundfont")
        create_status, created = request_json(server, "POST", "/api/audio/profiles", {"name": "API Profile", "engine_path": "fluidsynth", "soundfont_path": str(soundfont), "is_default": True})
        list_status, listed = request_json(server, "GET", "/api/audio/profiles")
        profile_id = created["profile"]["profile_id"]
        get_status, got = request_json(server, "GET", f"/api/audio/profiles/{profile_id}")
        hide_status, hidden = request_json(server, "POST", f"/api/audio/profiles/{profile_id}/hide")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert list_status == 200
    assert get_status == 200
    assert hide_status == 200
    assert listed["profiles"][0]["profile_id"] == profile_id
    assert "soundfont_path" not in json.dumps(got)
    assert hidden["profile"]["enabled"] is False


def test_job_render_audio_uses_profile_and_blocks_stale_download(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.server.render_audio", lambda midi, wav, config: fake_render_audio(midi, wav))
    server = start_test_server()
    try:
        final = create_completed_job(server, "Profile Render Audio")
        soundfont = tmp_path / "profile.sf2"
        soundfont.write_bytes(b"profile-soundfont")
        create_status, created = request_json(server, "POST", "/api/audio/profiles", {"name": "Render Profile", "soundfont_path": str(soundfont), "sample_rate": 48000})
        profile_id = created["profile"]["profile_id"]
        render_status, rendered = request_json(server, "POST", f"/api/jobs/{final['job_id']}/render-audio", {"profile_id": profile_id})
        audio_status, audio_body = request_json(server, "GET", f"/api/jobs/{final['job_id']}/audio")
        run_dir = Path(final["output_dir"])
        manifest = json.loads((run_dir / "renders" / "audio-artifact.json").read_text(encoding="utf-8"))
        request_json(server, "POST", f"/api/audio/profiles/{profile_id}", {"sample_rate": 44100, "soundfont_path": str(soundfont)})
        stale_status, stale = request_json(server, "GET", f"/api/jobs/{final['job_id']}/audio")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert render_status == 200
    assert rendered["audio_artifact_summary"]["renderer_profile_id"] == profile_id
    assert manifest["renderer"]["profile_id"] == profile_id
    assert manifest["renderer"]["sample_rate"] == 48000
    assert "soundfont_path" not in json.dumps(manifest)
    assert audio_status == 200
    assert audio_body.startswith(b"RIFF")
    assert stale_status == 409
    assert "stale" in stale["error"].lower()
