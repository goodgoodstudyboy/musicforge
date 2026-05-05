import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

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


def import_batch(server, **overrides):
    payload = {
        "name": "API Batch",
        "csv_text": CSV_TEXT,
        "generation_mode": "local",
        "pipeline_mode": "multinode",
        "max_concurrency": 2,
    }
    payload.update(overrides)
    status, data = request_json(server, "POST", "/api/batches/import-csv", payload)
    assert status == 201
    return data


def wait_for_batch(server, batch_id, terminal=True):
    terminal_statuses = {"completed", "completed_with_errors", "cancelled", "failed", "paused"}
    for _ in range(120):
        status, batch = request_json(server, "GET", f"/api/batches/{batch_id}")
        assert status == 200
        if not terminal or batch["batch"]["status"] in terminal_statuses:
            return batch
        time.sleep(0.05)
    raise AssertionError("batch did not finish")


def wait_for_batch_audio(server, batch_id):
    for _ in range(120):
        status, batch = request_json(server, "GET", f"/api/batches/{batch_id}")
        assert status == 200, batch
        statuses = {item.get("audio_status", "not_started") for item in batch["items"]}
        if not statuses.intersection({"queued", "running"}):
            return batch
        time.sleep(0.05)
    raise AssertionError("batch audio render did not finish")


def fake_render_audio(midi_path, wav_path, config):
    assert midi_path.exists()
    wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
    return wav_path


def fake_completed_process(cmd, **kwargs):
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def configure_renderer(tmp_path, server):
    soundfont = tmp_path / "font.sf2"
    soundfont.write_bytes(b"font")
    status, data = request_json(server, "POST", "/api/renderer", {"soundfont_path": str(soundfont)})
    assert status == 200
    assert data["configured"] is True


def test_import_batch_lists_and_reads_detail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        status_list, listed = request_json(server, "GET", "/api/batches")
        status_detail, detail = request_json(server, "GET", f"/api/batches/{batch_id}")
    finally:
        stop_test_server(server)

    assert status_list == 200
    assert status_detail == 200
    assert created["batch"]["status"] == "draft"
    assert created["batch"]["queued_count"] == 2
    assert listed["batches"][0]["batch_id"] == batch_id
    assert detail["items"][0]["request"]["title"] == "Batch One"


def test_import_batch_validation_error_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/batches/import-csv",
            {"name": "Bad", "csv_text": "title,language,style\nSong,English,pop\n"},
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert "theme" in data["error"]


def test_launch_batch_completes_items_and_exports_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server, max_concurrency=2)
        batch_id = created["batch"]["batch_id"]
        status_launch, launched = request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        final = wait_for_batch(server, batch_id)
        status_export, export = request_json(server, "GET", f"/api/batches/{batch_id}/export")
    finally:
        stop_test_server(server)

    assert status_launch == 202
    assert launched["started_count"] == 2
    assert final["batch"]["status"] == "completed"
    assert final["batch"]["completed_count"] == 2
    assert all(item["status"] == "completed" for item in final["items"])
    assert status_export == 200
    assert export["items"][0]["song_plan"].endswith(str(Path("data") / "song-plan.json"))
    assert export["items"][0]["midi"].endswith(str(Path("renders") / "song.mid"))


def test_launch_batch_respects_max_concurrency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    original_create_job = server.job_store.create_job

    def create_queued_job(payload, start_immediately=True):
        return original_create_job(payload, start_immediately=False)

    server.job_store.create_job = create_queued_job
    try:
        csv_text = CSV_TEXT + "Batch Three,English,jazz,late train,60,88,F,guide_melody,three,local,single\n"
        created = import_batch(server, csv_text=csv_text, max_concurrency=1)
        batch_id = created["batch"]["batch_id"]
        status_launch, launched = request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        status_detail, detail = request_json(server, "GET", f"/api/batches/{batch_id}")
    finally:
        stop_test_server(server)

    assert status_launch == 202
    assert launched["started_count"] == 1
    assert status_detail == 200
    assert detail["batch"]["running_count"] == 1
    assert detail["batch"]["queued_count"] == 2


def test_pause_resume_batch_stops_new_starts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    original_create_job = server.job_store.create_job

    def create_queued_job(payload, start_immediately=True):
        return original_create_job(payload, start_immediately=False)

    server.job_store.create_job = create_queued_job
    try:
        created = import_batch(server, max_concurrency=1)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        status_pause, paused = request_json(server, "POST", f"/api/batches/{batch_id}/pause")
        status_resume, resumed = request_json(server, "POST", f"/api/batches/{batch_id}/resume")
    finally:
        stop_test_server(server)

    assert status_pause == 200
    assert paused["batch"]["status"] == "paused"
    assert paused["batch"]["queued_count"] == 1
    assert status_resume == 202
    assert resumed["batch"]["status"] == "running"


def test_retry_failed_requeues_and_launches_new_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server, max_concurrency=1)
        batch_id = created["batch"]["batch_id"]
        document = server.batch_store.get_batch(batch_id)
        document.items[0].status = "failed"
        document.items[0].job_id = "old-job"
        document.items[0].output_dir = "runs/old-job"
        document.items[0].error = "old failure"
        document.items[1].status = "completed"
        server.batch_store.save_batch(document)

        status_retry, retry = request_json(server, "POST", f"/api/batches/{batch_id}/retry-failed")
        final = wait_for_batch(server, batch_id)
    finally:
        stop_test_server(server)

    assert status_retry == 202
    assert retry["reset_count"] == 1
    retried = final["items"][0]
    assert retried["status"] == "completed"
    assert retried["job_id"] != "old-job"
    assert retried["attempt_count"] == 1


def test_hide_unhide_and_delete_batch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        status_hide, hidden = request_json(server, "POST", f"/api/batches/{batch_id}/hide")
        status_list, listed = request_json(server, "GET", "/api/batches")
        status_hidden_list, hidden_list = request_json(server, "GET", "/api/batches?include_hidden=1")
        status_unhide, unhidden = request_json(server, "POST", f"/api/batches/{batch_id}/unhide")
        status_delete, deleted = request_json(server, "POST", f"/api/batches/{batch_id}/delete")
        status_detail, detail = request_json(server, "GET", f"/api/batches/{batch_id}")
    finally:
        stop_test_server(server)

    assert status_hide == 200
    assert hidden["batch"]["hidden"] is True
    assert status_list == 200
    assert listed["batches"] == []
    assert status_hidden_list == 200
    assert hidden_list["batches"][0]["batch_id"] == batch_id
    assert status_unhide == 200
    assert unhidden["batch"]["hidden"] is False
    assert status_delete == 200
    assert deleted["deleted"] is True
    assert status_detail == 404
    assert detail["error"] == "Batch not found."


def test_batch_open_folder_requires_post(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    opened = []
    monkeypatch.setattr("song_agent.server.open_folder", lambda path: opened.append(str(path)))
    server = start_test_server()
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        status_get, get_data = request_json(server, "GET", f"/api/batches/{batch_id}/open-folder")
        status_post, post_data = request_json(server, "POST", f"/api/batches/{batch_id}/open-folder")
    finally:
        stop_test_server(server)

    assert status_get == 405
    assert "error" in get_data
    assert status_post == 200
    assert post_data["ok"] is True
    assert opened


def test_provider_batch_requires_config_before_launch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server, generation_mode="provider", csv_text=CSV_TEXT.replace(",local,", ",provider,"))
        batch_id = created["batch"]["batch_id"]
        status_launch, data = request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        status_detail, detail = request_json(server, "GET", f"/api/batches/{batch_id}")
    finally:
        stop_test_server(server)

    assert status_launch == 400
    assert "provider" in data["error"].lower()
    assert detail["batch"]["status"] == "draft"
    assert all(item["job_id"] is None for item in detail["items"])


def test_render_batch_audio_requires_renderer_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        final = wait_for_batch(server, batch_id)
        status, data = request_json(server, "POST", f"/api/batches/{batch_id}/render-audio")
    finally:
        stop_test_server(server)

    assert final["batch"]["status"] == "completed"
    assert status == 400
    assert "soundfont_path" in data["error"]


def test_render_batch_audio_completes_items_and_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.server.render_audio", fake_render_audio)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        wait_for_batch(server, batch_id)
        status_render, render_data = request_json(server, "POST", f"/api/batches/{batch_id}/render-audio")
        final = wait_for_batch_audio(server, batch_id)
        status_export, export = request_json(server, "GET", f"/api/batches/{batch_id}/export")
    finally:
        stop_test_server(server)

    assert status_render == 202
    assert render_data["queued_count"] == 2
    assert all(item["audio_status"] == "completed" for item in final["items"])
    assert all(item["audio_path"].endswith(str(Path("renders") / "song.wav")) for item in final["items"])
    assert status_export == 200
    assert export["items"][0]["audio_status"] == "completed"
    assert export["items"][0]["audio"].endswith(str(Path("renders") / "song.wav"))


def test_render_batch_audio_marks_missing_midi_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.server.render_audio", fake_render_audio)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        document = server.batch_store.get_batch(batch_id)
        job = server.job_store.create_job(document.items[0].request, start_immediately=False)
        document.items[0].status = "completed"
        document.items[0].job_id = job.job_id
        document.items[0].output_dir = job.output_dir
        server.batch_store.save_batch(document)
        status_render, render_data = request_json(server, "POST", f"/api/batches/{batch_id}/render-audio")
        final = wait_for_batch_audio(server, batch_id)
    finally:
        stop_test_server(server)

    assert status_render == 202
    assert render_data["queued_count"] == 1
    assert final["items"][0]["audio_status"] == "failed"
    assert final["items"][0]["audio_error"] == "song.mid is not available for this job yet."


def test_render_batch_audio_partial_success_and_retry_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    attempts = {"count": 0}

    def flaky_render(midi_path, wav_path, config):
        attempts["count"] += 1
        if attempts["count"] == 1:
            from song_agent.renderers.audio import RendererExecutionError

            raise RendererExecutionError("render failed")
        return fake_render_audio(midi_path, wav_path, config)

    monkeypatch.setattr("song_agent.server.render_audio", flaky_render)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        wait_for_batch(server, batch_id)
        status_render, render_data = request_json(server, "POST", f"/api/batches/{batch_id}/render-audio")
        partial = wait_for_batch_audio(server, batch_id)
        status_retry, retry = request_json(server, "POST", f"/api/batches/{batch_id}/render-failed-audio")
        final = wait_for_batch_audio(server, batch_id)
    finally:
        stop_test_server(server)

    assert status_render == 202
    assert render_data["queued_count"] == 2
    assert sorted(item["audio_status"] for item in partial["items"]) == ["completed", "failed"]
    assert any(item["audio_error"] == "render failed" for item in partial["items"])
    assert status_retry == 202
    assert retry["queued_count"] == 1
    assert all(item["audio_status"] == "completed" for item in final["items"])


def test_render_failed_batch_audio_requires_failed_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("song_agent.server.render_audio", fake_render_audio)
    server = start_test_server()
    try:
        configure_renderer(tmp_path, server)
        created = import_batch(server)
        batch_id = created["batch"]["batch_id"]
        request_json(server, "POST", f"/api/batches/{batch_id}/launch")
        wait_for_batch(server, batch_id)
        status, data = request_json(server, "POST", f"/api/batches/{batch_id}/render-failed-audio")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Batch has no failed audio renders to retry."


def test_startup_recovers_running_batch_as_paused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first_server = start_test_server()
    original_create_job = first_server.job_store.create_job

    def create_queued_job(payload, start_immediately=True):
        return original_create_job(payload, start_immediately=False)

    first_server.job_store.create_job = create_queued_job
    try:
        created = import_batch(first_server, max_concurrency=1)
        batch_id = created["batch"]["batch_id"]
        request_json(first_server, "POST", f"/api/batches/{batch_id}/launch")
    finally:
        stop_test_server(first_server)

    second_server = start_test_server()
    try:
        status, detail = request_json(second_server, "GET", f"/api/batches/{batch_id}")
    finally:
        stop_test_server(second_server)

    assert status == 200
    assert detail["batch"]["status"] == "paused"
    assert detail["batch"]["failed_count"] == 1
    assert detail["batch"]["queued_count"] == 1
    assert detail["items"][0]["status"] == "failed"
    assert "stopped" in detail["items"][0]["error"]
