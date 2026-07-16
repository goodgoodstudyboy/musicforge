import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

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
    content_type = response.getheader("Content-Type", "")
    connection.close()
    if content_type.startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8")), content_type
    return response.status, data, content_type


def wait_for_job(server, job_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, job, _ = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def create_completed_job(server):
    status, job, _ = request_json(
        server,
        "POST",
        "/api/jobs",
        {
            "title": "Stem API Song",
            "language": "en",
            "style": "pop",
            "theme": "server stems",
        },
    )
    assert status == 202
    return wait_for_job(server, job["job_id"])


def fake_render_audio(midi_path, wav_path, config):
    assert midi_path.exists()
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(b"RIFFstemWAVE")
    return wav_path


def configure_renderer(tmp_path, server):
    soundfont = tmp_path / "test.sf2"
    soundfont.write_bytes(b"sf2")
    status, _data, _ = request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
    assert status == 200


def test_stems_endpoint_returns_preview_before_render(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = create_completed_job(server)
        status, data, _ = request_json(server, "GET", f"/api/jobs/{job['job_id']}/stems")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["status"] == "not_started"
    assert {stem["stem_id"] for stem in data["manifest"]["stems"]} == {"melody", "chords", "bass", "drums"}
    assert not (Path(job["output_dir"]) / "stems" / "manifest.json").exists()


def test_render_stems_writes_manifest_and_downloads_midi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = create_completed_job(server)
        status, data, _ = request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stems")
        midi_status, midi_body, midi_type = request_json(server, "GET", f"/api/jobs/{job['job_id']}/stems/melody/midi")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["manifest"]["stems"][0]["midi_exists"] is True
    assert data["status"] == "completed"
    assert (Path(job["output_dir"]) / "stems" / "manifest.json").exists()
    assert midi_status == 200
    assert midi_type == "audio/midi"
    assert midi_body.startswith(b"MThd")


def test_render_stem_audio_writes_wavs_without_marking_job_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.domains.creation.stems.render_audio", fake_render_audio)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        job = create_completed_job(server)
        request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stems")
        status, data, _ = request_json(
            server,
            "POST",
            f"/api/jobs/{job['job_id']}/render-stem-audio",
            {"stem_ids": ["melody"]},
        )
        audio_status, audio_body, audio_type = request_json(server, "GET", f"/api/jobs/{job['job_id']}/stems/melody/audio")
        job_status, latest, _ = request_json(server, "GET", f"/api/jobs/{job['job_id']}")
    finally:
        stop_test_server(server)

    melody = next(stem for stem in data["manifest"]["stems"] if stem["stem_id"] == "melody")
    assert status == 200
    assert data["status"] == "partial_completed"
    assert melody["audio_status"] == "completed"
    assert audio_status == 200
    assert audio_type == "audio/wav"
    assert audio_body.startswith(b"RIFF")
    assert job_status == 200
    assert latest["status"] == "completed"


def test_stems_preview_invalidates_stale_manifest_when_song_plan_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = create_completed_job(server)
        request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stems")
        run_dir = Path(job["output_dir"])
        assert (run_dir / "stems" / "manifest.json").exists()
        plan_path = run_dir / "data" / "song-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["tempo_bpm"] = int(plan["tempo_bpm"]) + 1
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        status, data, _ = request_json(server, "GET", f"/api/jobs/{job['job_id']}/stems")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["status"] == "not_started"
    assert not (run_dir / "stems" / "manifest.json").exists()


def test_stem_file_download_rejects_stale_manifest_when_song_plan_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = create_completed_job(server)
        request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stems")
        run_dir = Path(job["output_dir"])
        plan_path = run_dir / "data" / "song-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["tempo_bpm"] = int(plan["tempo_bpm"]) + 1
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        status, data, _ = request_json(server, "GET", f"/api/jobs/{job['job_id']}/stems/melody/midi")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Stem manifest is stale. Render stems again."
    assert not (run_dir / "stems").exists()


def test_stem_audio_rejects_stale_manifest_until_rerendered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.domains.creation.stems.render_audio", fake_render_audio)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        job = create_completed_job(server)
        request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stems")
        plan_path = Path(job["output_dir"]) / "data" / "song-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["tempo_bpm"] = int(plan["tempo_bpm"]) + 1
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        status, data, _ = request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stem-audio")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Stem manifest is stale. Render stems again."


def test_render_stem_audio_requires_renderer_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = create_completed_job(server)
        request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stems")
        status, data, _ = request_json(server, "POST", f"/api/jobs/{job['job_id']}/render-stem-audio")
    finally:
        stop_test_server(server)

    assert status == 400
    assert "soundfont_path" in data["error"]


def test_stem_routes_reject_missing_plan_and_bad_stem_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {"title": "Queued Stem", "language": "en", "style": "pop", "theme": "queued"},
            start_immediately=False,
        )
        missing_status, missing, _ = request_json(server, "GET", f"/api/jobs/{job.job_id}/stems")
        completed = create_completed_job(server)
        request_json(server, "POST", f"/api/jobs/{completed['job_id']}/render-stems")
        bad_status, bad, _ = request_json(server, "GET", f"/api/jobs/{completed['job_id']}/stems/..%2Fsecret/midi")
        configure_renderer(tmp_path, server)
        bad_audio_status, bad_audio, _ = request_json(
            server,
            "POST",
            f"/api/jobs/{completed['job_id']}/render-stem-audio",
            {"stem_ids": ["../secret"]},
        )
    finally:
        stop_test_server(server)

    assert missing_status == 409
    assert missing["error"] == "song-plan.json is not available for this job yet."
    assert bad_status == 404
    assert bad["error"] == "Stem not found."
    assert bad_audio_status == 404
    assert bad_audio["error"] == "Stem not found."
