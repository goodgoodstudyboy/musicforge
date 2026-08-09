import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

from song_agent.server import create_server


def start_test_server():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_test_server(server):
    server.shutdown()
    server.server_close()


def request_json(server, method, path, payload=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=30)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8"))
    return response.status, data, response.getheader("Content-Type")


def wait_for_job(server, job_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def create_completed_job(server, title="Audio Song"):
    status, job = request_json(
        server,
        "POST",
        "/api/jobs",
        {
            "title": title,
            "language": "en",
            "style": "pop",
            "theme": "audio",
        },
    )
    assert status == 202
    return wait_for_job(server, job["job_id"])


def fake_audio_runner(cmd, **kwargs):
    wav_path = Path(cmd[cmd.index("-F") + 1])
    wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def fake_renderer_test_runner(cmd, **kwargs):
    return SimpleNamespace(returncode=0, stdout="FluidSynth", stderr="")


def test_get_renderer_returns_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/renderer")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["configured"] is False
    assert data["config"]["renderer_type"] == "fluidsynth"
    assert data["config"]["sample_rate"] == 44100


def test_post_renderer_saves_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    soundfont = tmp_path / "font.sf2"
    soundfont.write_bytes(b"font")
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/renderer",
            {
                "renderer_type": "fluidsynth",
                "fluidsynth_path": "fluidsynth",
                "soundfont_path": str(soundfont),
                "sample_rate": 48000,
                "gain": 0.9,
            },
        )
        status_get, loaded = request_json(server, "GET", "/api/renderer")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["configured"] is True
    assert status_get == 200
    assert loaded["config"]["soundfont_exists"] is True
    assert (tmp_path / ".musicforge" / "renderer.json").exists()


def test_renderer_reset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".musicforge").mkdir()
    (tmp_path / ".musicforge" / "renderer.json").write_text("{}", encoding="utf-8")
    server = start_test_server()
    try:
        status, data = request_json(server, "POST", "/api/renderer/reset")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["configured"] is False
    assert not (tmp_path / ".musicforge" / "renderer.json").exists()


def test_renderer_test_returns_400_when_missing_soundfont(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/renderer",
            {"soundfont_path": str(tmp_path / "missing.sf2")},
        )
        status, data = request_json(server, "POST", "/api/renderer/test")
    finally:
        stop_test_server(server)

    assert status == 400
    assert data["error"] == "SoundFont file does not exist."


def test_renderer_test_succeeds_with_fake_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    soundfont = tmp_path / "font.sf2"
    soundfont.write_bytes(b"font")
    monkeypatch.setattr(
        "song_agent.interfaces.api.runtime.test_renderer_config",
        lambda config: {
            "ok": True,
            "renderer": {
                "renderer_type": "fluidsynth",
                "fluidsynth_path": config.fluidsynth_path,
                "soundfont_exists": True,
            },
            "message": "Renderer test completed.",
        },
    )
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
        status, data = request_json(server, "POST", "/api/renderer/test")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["ok"] is True


def test_render_audio_requires_completed_midi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "No Midi",
                "language": "en",
                "style": "pop",
                "theme": "no midi",
            },
            start_immediately=False,
        )
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/render-audio")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "song.mid is not available for this job yet."


def test_render_audio_writes_wav_with_fake_renderer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    soundfont = tmp_path / "font.sf2"
    soundfont.write_bytes(b"font")
    monkeypatch.setattr(
        "song_agent.interfaces.api.runtime_parts.job_store_parts.retry_job.render_audio",
        lambda midi, wav, config: fake_render_audio(midi, wav),
    )
    server = start_test_server()
    try:
        final = create_completed_job(server)
        request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
        status, data = request_json(server, "POST", f"/api/jobs/{final['job_id']}/render-audio")
        status_job, job = request_json(server, "GET", f"/api/jobs/{final['job_id']}")
        status_artifacts, artifacts = request_json(server, "GET", f"/api/jobs/{final['job_id']}/artifacts")
        status_validator, validator = request_json(server, "GET", f"/api/jobs/{final['job_id']}/validator")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["audio"].endswith(str(Path("renders") / "song.wav"))
    assert data["artifact"]["name"] == "song.wav"
    assert status_job == 200
    assert job["status"] == "completed"
    assert "audio" in job["artifacts"]
    assert status_artifacts == 200
    assert any(item["kind"] == "audio" and item["name"] == "song.wav" for item in artifacts["artifacts"])
    assert status_validator == 200
    assert validator["view"]["audio"]["exists"] is True


def test_audio_endpoint_returns_wav(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "song_agent.interfaces.api.runtime_parts.job_store_parts.retry_job.render_audio",
        lambda midi, wav, config: fake_render_audio(midi, wav),
    )
    soundfont = tmp_path / "font.sf2"
    soundfont.write_bytes(b"font")
    server = start_test_server()
    try:
        final = create_completed_job(server, "Audio Endpoint Song")
        request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
        request_json(server, "POST", f"/api/jobs/{final['job_id']}/render-audio")
        status, body, content_type = request_json(server, "GET", f"/api/jobs/{final['job_id']}/audio")
    finally:
        stop_test_server(server)

    assert status == 200
    assert body.startswith(b"RIFF")
    assert content_type == "audio/wav"


def test_audio_endpoint_missing_returns_404(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        final = create_completed_job(server, "No Audio Song")
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/audio")
    finally:
        stop_test_server(server)

    assert status == 404
    assert data["error"] == "Audio render is not available for this job."


def test_render_audio_failure_does_not_mark_job_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    soundfont = tmp_path / "font.sf2"
    soundfont.write_bytes(b"font")

    def failing_render(midi, wav, config):
        from song_agent.renderers.audio import RendererExecutionError

        raise RendererExecutionError("render failed")

    monkeypatch.setattr(
        "song_agent.interfaces.api.runtime_parts.job_store_parts.retry_job.render_audio",
        failing_render,
    )
    server = start_test_server()
    try:
        final = create_completed_job(server, "Audio Failure Song")
        request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
        status, data = request_json(server, "POST", f"/api/jobs/{final['job_id']}/render-audio")
        status_job, job = request_json(server, "GET", f"/api/jobs/{final['job_id']}")
        error_path = Path(job["output_dir"]) / "logs" / "audio-render-error.json"
    finally:
        stop_test_server(server)

    assert status == 400
    assert data["error"] == "render failed"
    assert status_job == 200
    assert job["status"] == "completed"
    assert error_path.exists()


def fake_render_audio(midi_path, wav_path):
    assert midi_path.exists()
    wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
    return wav_path
