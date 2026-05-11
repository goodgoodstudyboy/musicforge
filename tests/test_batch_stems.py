import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

from song_agent.server import create_server


CSV_TEXT = """title,language,style,theme,duration_seconds,tempo_bpm,key,vocal_mode,lyrics,generation_mode,pipeline_mode
Batch One,English,pop,night walk,60,96,C,guide_melody,one,local,multinode
Batch Two,English,rock,open road,60,120,D,guide_melody,two,local,single
"""


def start_test_server():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_test_server(server):
    server.shutdown()
    server.server_close()


def request_json(server, method, path, payload=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
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
    return response.status, data


def import_batch(server):
    status, data = request_json(
        server,
        "POST",
        "/api/batches/import-csv",
        {"name": "Stem Batch", "csv_text": CSV_TEXT, "max_concurrency": 2},
    )
    assert status == 201
    return data


def wait_for_batch(server, batch_id):
    for _ in range(240):
        status, batch = request_json(server, "GET", f"/api/batches/{batch_id}")
        assert status == 200
        if batch["batch"]["status"] in {"completed", "completed_with_errors", "failed", "paused"}:
            return batch
        time.sleep(0.05)
    raise AssertionError("batch did not finish")


def wait_for_batch_stems(server, batch_id):
    for _ in range(240):
        status, batch = request_json(server, "GET", f"/api/batches/{batch_id}")
        assert status == 200
        statuses = {item.get("stem_status", "not_started") for item in batch["items"]}
        if not statuses & {"queued", "running"}:
            return batch
        time.sleep(0.05)
    raise AssertionError("batch stem render did not finish")


def wait_for_batch_stem_audio(server, batch_id):
    for _ in range(240):
        status, batch = request_json(server, "GET", f"/api/batches/{batch_id}")
        assert status == 200
        statuses = {item.get("stem_status", "not_started") for item in batch["items"]}
        if statuses & {"queued", "running"}:
            time.sleep(0.05)
            continue
        if all(item.get("stem_audio_completed_count", 0) >= item.get("stem_count", 0) > 0 for item in batch["items"]):
            return batch
        time.sleep(0.05)
    raise AssertionError("batch stem audio render did not finish")


def configure_renderer(tmp_path, server):
    soundfont = tmp_path / "test.sf2"
    soundfont.write_bytes(b"sf2")
    status, _data = request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
    assert status == 200


def fake_render_audio(midi_path, wav_path, config):
    assert midi_path.exists()
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(b"RIFFstemWAVE")
    return wav_path


def test_render_batch_stems_completes_items_and_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        wait_for_batch(server, batch_id)
        status_render, render_data = request_json(server, "POST", f"/api/batches/{batch_id}/render-stems")
        final = wait_for_batch_stems(server, batch_id)
        status_export, export = request_json(server, "GET", f"/api/batches/{batch_id}/export")
    finally:
        stop_test_server(server)

    assert status_render == 202
    assert render_data["queued_count"] == 2
    assert all(item["stem_status"] == "completed" for item in final["items"])
    assert all(item["stem_count"] == 4 for item in final["items"])
    assert status_export == 200
    assert export["items"][0]["stem_status"] == "completed"
    assert export["items"][0]["stem_manifest"].endswith(str(Path("stems") / "manifest.json"))


def test_render_batch_stem_audio_completes_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.stems.render_audio", fake_render_audio)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        wait_for_batch(server, batch_id)
        request_json(server, "POST", f"/api/batches/{batch_id}/render-stems")
        wait_for_batch_stems(server, batch_id)
        status_render, render_data = request_json(server, "POST", f"/api/batches/{batch_id}/render-stem-audio")
        final = wait_for_batch_stem_audio(server, batch_id)
    finally:
        stop_test_server(server)

    assert status_render == 202
    assert render_data["queued_count"] == 2
    assert all(item["stem_status"] == "completed" for item in final["items"])
    assert all(item["stem_audio_completed_count"] == 4 for item in final["items"])


def test_render_batch_stems_rejects_running_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    original_create_job = server.job_store.create_job

    def create_queued_job(payload, start_immediately=True):
        return original_create_job(payload, start_immediately=False)

    server.job_store.create_job = create_queued_job
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        status, data = request_json(server, "POST", f"/api/batches/{batch_id}/render-stems")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Cannot render batch stems while batch generation is running."


def test_render_failed_batch_stems_requires_failed_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        wait_for_batch(server, batch_id)
        status, data = request_json(server, "POST", f"/api/batches/{batch_id}/render-failed-stems")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Batch has no failed stem renders to retry."
