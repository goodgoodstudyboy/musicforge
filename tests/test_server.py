import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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
    connection.close()
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8"))
    return response.status, data


def wait_for_job(server, job_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_info_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/info")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["app"] == "MusicForge"
    assert data["mode"] == "local-deterministic"


def test_server_close_stops_watchdog_without_serve_forever(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = create_server("127.0.0.1", 0)
    watchdog = server.watchdog_thread

    server.server_close()

    assert not watchdog.is_alive()


def test_create_job_completes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Panel Song",
                "language": "en",
                "style": "pop",
                "theme": "local panel test",
            },
        )
        assert status == 202

        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert final["status"] == "completed"
    output_dir = Path(final["output_dir"])
    assert (output_dir / "data" / "job-state.json").exists()
    assert (output_dir / "data" / "validator-report.json").exists()
    assert (output_dir / "data" / "song-plan.json").exists()
    assert (output_dir / "renders" / "song.mid").stat().st_size > 100


def test_job_detail_includes_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Artifact Song",
                "language": "en",
                "style": "pop",
                "theme": "artifacts",
            },
        )
        final = wait_for_job(server, job["job_id"])

        status, artifacts = request_json(server, "GET", f"/api/jobs/{final['job_id']}/artifacts")
        status_plan, plan = request_json(server, "GET", f"/api/jobs/{final['job_id']}/song-plan")
    finally:
        stop_test_server(server)

    assert status == 200
    assert status_plan == 200
    assert plan["title"] == "Artifact Song"
    names = {artifact["name"] for artifact in artifacts["artifacts"]}
    assert {"job-state.json", "validator-report.json", "song-plan.json", "song.mid"}.issubset(names)


def test_timeline_endpoint_returns_view(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Timeline Song",
                "language": "en",
                "style": "pop",
                "theme": "timeline",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/timeline")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job_id"] == final["job_id"]
    assert data["view"]["title"] == "Timeline Song"
    assert data["view"]["total_bars"] > 0
    assert data["view"]["sections"]


def test_tracks_endpoint_returns_view(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Tracks Song",
                "language": "en",
                "style": "pop",
                "theme": "tracks",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/tracks")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job_id"] == final["job_id"]
    assert data["view"]["track_count"] > 0
    assert data["view"]["note_count"] > 0


def test_quality_endpoint_returns_view(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Quality Endpoint Song",
                "language": "en",
                "style": "pop",
                "theme": "quality",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/quality")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job_id"] == final["job_id"]
    assert data["view"]["overall"] >= 70
    assert data["view"]["section_intents"]


def test_quality_endpoint_waiting_for_song_plan_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Queued Quality",
                "language": "en",
                "style": "pop",
                "theme": "queued",
            },
            start_immediately=False,
        )
        status, data = request_json(server, "GET", f"/api/jobs/{job.job_id}/quality")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "song-plan.json is not available for this job yet."


def test_validator_endpoint_returns_view(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Validator Song",
                "language": "en",
                "style": "pop",
                "theme": "validator",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/validator")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job_id"] == final["job_id"]
    assert data["view"]["status"] == "passed"
    assert data["view"]["passed"] is True
    assert data["view"]["midi"]["exists"] is True


def test_validator_endpoint_includes_quality_warnings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Validator Quality Warning",
                "language": "en",
                "style": "pop",
                "theme": "validator quality",
            },
        )
        final = wait_for_job(server, job["job_id"])
        plan_path = Path(final["output_dir"]) / "data" / "song-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["quality"]["warnings"] = ["quality warning from plan"]
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/validator")
    finally:
        stop_test_server(server)

    assert status == 200
    assert "quality warning from plan" in data["view"]["warnings"]


def test_runtime_view_endpoint_waiting_for_artifact_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Queued Timeline",
                "language": "en",
                "style": "pop",
                "theme": "queued",
            },
            start_immediately=False,
        )
        status, data = request_json(server, "GET", f"/api/jobs/{job.job_id}/timeline")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "song-plan.json is not available for this job yet."


def test_server_recovers_completed_jobs_on_startup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first_server = start_test_server()
    try:
        _, job = request_json(
            first_server,
            "POST",
            "/api/jobs",
            {
                "title": "Recovered Song",
                "language": "en",
                "style": "pop",
                "theme": "restart",
            },
        )
        final = wait_for_job(first_server, job["job_id"])
        assert final["status"] == "completed"
    finally:
        stop_test_server(first_server)

    second_server = start_test_server()
    try:
        status, data = request_json(second_server, "GET", "/api/jobs")
    finally:
        stop_test_server(second_server)

    assert status == 200
    assert any(job["title"] == "Recovered Song" for job in data["jobs"])


def test_startup_recovers_completed_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "runs" / "completed-job" / "data"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "job-state.json"
    state_path.write_text(
        json.dumps(
            {
                "job_id": "completed-job",
                "title": "Completed Job",
                "output_dir": str(tmp_path / "runs" / "completed-job"),
                "status": "completed",
                "created_at": "2026-05-05T00:00:00+00:00",
                "updated_at": "2026-05-05T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status == 200
    [job] = data["jobs"]
    assert job["job_id"] == "completed-job"
    assert job["status"] == "completed"
    assert job["heartbeat_at"] is None
    assert job["retry_count"] == 0
    assert job["stalled"] is False
    assert job["stall_timeout_seconds"] == 300
    assert job["generation_mode"] == "local"
    assert job["pipeline_mode"] == "single"


def test_job_state_includes_heartbeat_and_retry_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Heartbeat Defaults Song",
                "language": "en",
                "style": "pop",
                "theme": "heartbeat",
            },
        )
        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert final["status"] == "completed"
    assert final["attempt_count"] == 1
    assert final["heartbeat_at"] is not None
    assert final["retry_requested"] is False
    assert final["retry_count"] == 0
    assert final["max_retries"] == 0
    assert final["next_retry_at"] is None
    assert final["last_error"] is None
    assert final["stalled"] is False
    assert final["stall_timeout_seconds"] == 300


def test_startup_marks_running_job_interrupted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_path = write_job_state(
        tmp_path,
        "running-job",
        {"status": "running", "step": "generate"},
    )

    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status == 200
    [job] = data["jobs"]
    assert job["status"] == "interrupted"
    assert job["step"] == "interrupted"
    assert job["interrupted"] is True
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "interrupted"
    assert persisted["error"] == "Job was running when the server stopped."


def test_startup_marks_queued_job_interrupted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_job_state(tmp_path, "queued-job", {"status": "queued", "step": "queued"})

    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status == 200
    [job] = data["jobs"]
    assert job["status"] == "interrupted"


def test_startup_keeps_failed_job_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_job_state(tmp_path, "failed-job", {"status": "failed", "step": "failed"})

    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status == 200
    [job] = data["jobs"]
    assert job["status"] == "failed"
    assert job["step"] == "failed"


def test_startup_writes_interrupted_state_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_path = write_job_state(tmp_path, "paused-job", {"status": "paused", "step": "paused"})

    server = start_test_server()
    try:
        request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "interrupted"
    assert persisted["message"] == "This job was interrupted by a previous server shutdown."


def test_concurrent_same_title_jobs_get_unique_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    payload = {
        "title": "Same Title",
        "language": "en",
        "style": "pop",
        "theme": "parallel",
    }
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(
                pool.map(
                    lambda _: request_json(server, "POST", "/api/jobs", payload),
                    range(12),
                )
            )

        assert [status for status, _job in results] == [202] * 12
        job_ids = [job["job_id"] for _status, job in results]
        assert len(set(job_ids)) == len(job_ids)
        finals = [wait_for_job(server, job_id) for job_id in job_ids]
    finally:
        stop_test_server(server)

    assert all(job["status"] == "completed" for job in finals)
    output_dirs = [job["output_dir"] for job in finals]
    assert len(set(output_dirs)) == len(output_dirs)
    for output_dir in output_dirs:
        path = Path(output_dir)
        assert (path / "data" / "job-state.json").exists()
        assert (path / "data" / "song-plan.json").exists()
        assert (path / "renders" / "song.mid").exists()


def test_midi_endpoint_returns_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Midi Song",
                "language": "en",
                "style": "pop",
                "theme": "midi",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, body = request_json(server, "GET", f"/api/jobs/{final['job_id']}/midi")
    finally:
        stop_test_server(server)

    assert status == 200
    assert body.startswith(b"MThd")


def test_open_folder_requires_post(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Folder Song",
                "language": "en",
                "style": "pop",
                "theme": "folder",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/open-folder")
    finally:
        stop_test_server(server)

    assert status == 405
    assert "error" in data


def test_hide_job_excludes_from_default_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Hide Song",
                "language": "en",
                "style": "pop",
                "theme": "hide",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status_hide, hidden = request_json(server, "POST", f"/api/jobs/{final['job_id']}/hide")
        status_list, data = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status_hide == 200
    assert hidden["job"]["hidden"] is True
    assert status_list == 200
    assert all(job["job_id"] != final["job_id"] for job in data["jobs"])


def test_include_hidden_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Hidden Include Song",
                "language": "en",
                "style": "pop",
                "theme": "include hidden",
            },
        )
        final = wait_for_job(server, job["job_id"])
        request_json(server, "POST", f"/api/jobs/{final['job_id']}/hide")
        status, data = request_json(server, "GET", "/api/jobs?include_hidden=1")
    finally:
        stop_test_server(server)

    assert status == 200
    assert any(job["job_id"] == final["job_id"] and job["hidden"] for job in data["jobs"])


def test_unhide_job_restores_default_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Unhide Song",
                "language": "en",
                "style": "pop",
                "theme": "unhide",
            },
        )
        final = wait_for_job(server, job["job_id"])
        request_json(server, "POST", f"/api/jobs/{final['job_id']}/hide")
        status_unhide, visible = request_json(server, "POST", f"/api/jobs/{final['job_id']}/unhide")
        status_list, data = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status_unhide == 200
    assert visible["job"]["hidden"] is False
    assert status_list == 200
    assert any(job["job_id"] == final["job_id"] and not job["hidden"] for job in data["jobs"])


def test_delete_completed_job_removes_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Delete Song",
                "language": "en",
                "style": "pop",
                "theme": "delete",
            },
        )
        final = wait_for_job(server, job["job_id"])
        output_dir = Path(final["output_dir"])
        status_delete, data = request_json(server, "POST", f"/api/jobs/{final['job_id']}/delete")
        status_detail, detail = request_json(server, "GET", f"/api/jobs/{final['job_id']}")
    finally:
        stop_test_server(server)

    assert status_delete == 200
    assert data["deleted"] is True
    assert status_detail == 404
    assert detail["error"] == "Job not found."
    assert not output_dir.exists()


def test_delete_running_job_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Running Delete Song",
                "language": "en",
                "style": "pop",
                "theme": "delete running",
            },
            start_immediately=False,
        )
        server.job_store._update_job(job, status="running", step="generate")
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/delete")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Cannot delete a running job. Cancel it first."


def test_delete_rejects_output_dir_outside_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    keep_file = outside / "keep.txt"
    keep_file.write_text("keep", encoding="utf-8")
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Unsafe Delete Song",
                "language": "en",
                "style": "pop",
                "theme": "unsafe delete",
            },
            start_immediately=False,
        )
        with server.job_store.lock:
            server.job_store.jobs[job.job_id].output_dir = str(outside)
            server.job_store.jobs[job.job_id].status = "completed"
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/delete")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Refusing to delete outside runs directory."
    assert keep_file.exists()


def test_cancel_queued_job_marks_cancelled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Queued Cancel Song",
                "language": "en",
                "style": "pop",
                "theme": "cancel queued",
            },
            start_immediately=False,
        )
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/cancel")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job"]["status"] == "cancelled"
    assert data["job"]["cancel_requested"] is True


def test_cancel_running_job_sets_cancel_requested(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Running Cancel Song",
                "language": "en",
                "style": "pop",
                "theme": "cancel running",
            },
            start_immediately=False,
        )
        server.job_store._update_job(job, status="running", step="generate")
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/cancel")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job"]["status"] == "running"
    assert data["job"]["cancel_requested"] is True


def test_cancelled_queued_job_does_not_start(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Cancelled Before Start",
                "language": "en",
                "style": "pop",
                "theme": "cancel before start",
            },
            start_immediately=False,
        )
        request_json(server, "POST", f"/api/jobs/{job.job_id}/cancel")
        started = server.job_store.start_job(job.job_id)
        detail = server.job_store.get_job(job.job_id)
    finally:
        stop_test_server(server)

    assert started is False
    assert detail.status == "cancelled"
    assert not (Path(detail.output_dir) / "data" / "song-plan.json").exists()


def test_cancel_completed_job_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Completed Cancel Song",
                "language": "en",
                "style": "pop",
                "theme": "cancel completed",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "POST", f"/api/jobs/{final['job_id']}/cancel")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Cannot cancel a completed job."


def test_cancel_unknown_job_returns_404(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "POST", "/api/jobs/missing/cancel")
    finally:
        stop_test_server(server)

    assert status == 404
    assert data["error"] == "Job not found."


def test_retry_failed_job_requeues_and_completes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Retry Failed Song",
                "language": "en",
                "style": "pop",
                "theme": "retry",
            },
            start_immediately=False,
        )
        server.job_store._update_job(job, status="failed", step="failed", error="first failure")
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/retry")
        final = wait_for_job(server, job.job_id)
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job"]["retry_count"] == 1
    assert final["status"] == "completed"
    assert final["retry_count"] == 1
    assert final["last_error"] is None


def test_retry_failed_job_increments_retry_count(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Retry Count Song",
                "language": "en",
                "style": "pop",
                "theme": "retry count",
            },
            start_immediately=False,
        )
        server.job_store._update_job(job, status="failed", step="failed", error="first failure")
        request_json(server, "POST", f"/api/jobs/{job.job_id}/retry")
        final = wait_for_job(server, job.job_id)
    finally:
        stop_test_server(server)

    assert final["attempt_count"] == 1
    assert final["retry_count"] == 1


def test_retry_failed_job_preserves_input_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Retry Input Song",
                "language": "en",
                "style": "pop",
                "theme": "original input",
            },
            start_immediately=False,
        )
        original_payload = dict(job.input_payload)
        server.job_store._update_job(job, status="failed", step="failed", error="first failure")
        request_json(server, "POST", f"/api/jobs/{job.job_id}/retry")
        final = wait_for_job(server, job.job_id)
    finally:
        stop_test_server(server)

    assert final["input_payload"] == original_payload


def test_retry_running_job_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(
            {
                "title": "Retry Running Song",
                "language": "en",
                "style": "pop",
                "theme": "retry running",
            },
            start_immediately=False,
        )
        server.job_store._update_job(job, status="running", step="generate")
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/retry")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Cannot retry a running job."


def test_retry_completed_job_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Retry Completed Song",
                "language": "en",
                "style": "pop",
                "theme": "retry completed",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "POST", f"/api/jobs/{final['job_id']}/retry")
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Cannot retry a completed job."


def test_watchdog_marks_stale_running_job_stalled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    now = datetime.now(timezone.utc)
    try:
        job = server.job_store.create_job(
            {
                "title": "Stale Running Song",
                "language": "en",
                "style": "pop",
                "theme": "stalled",
            },
            start_immediately=False,
        )
        server.job_store._update_job(
            job,
            status="running",
            step="generate",
            heartbeat_at=(now - timedelta(seconds=301)).isoformat(),
        )
        marked = server.job_store.run_watchdog_tick(now=now)
        detail = server.job_store.get_job(job.job_id)
    finally:
        stop_test_server(server)

    assert marked == 1
    assert detail.status == "stalled"
    assert detail.stalled is True
    assert detail.error == "No heartbeat within stall timeout."


def test_watchdog_ignores_recent_heartbeat(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    now = datetime.now(timezone.utc)
    try:
        job = server.job_store.create_job(
            {
                "title": "Recent Heartbeat Song",
                "language": "en",
                "style": "pop",
                "theme": "recent heartbeat",
            },
            start_immediately=False,
        )
        server.job_store._update_job(
            job,
            status="running",
            step="generate",
            heartbeat_at=(now - timedelta(seconds=30)).isoformat(),
        )
        marked = server.job_store.run_watchdog_tick(now=now)
        detail = server.job_store.get_job(job.job_id)
    finally:
        stop_test_server(server)

    assert marked == 0
    assert detail.status == "running"
    assert detail.stalled is False


def test_watchdog_ignores_completed_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    now = datetime.now(timezone.utc)
    try:
        job = server.job_store.create_job(
            {
                "title": "Completed Watchdog Song",
                "language": "en",
                "style": "pop",
                "theme": "completed watchdog",
            },
            start_immediately=False,
        )
        server.job_store._update_job(
            job,
            status="completed",
            step="completed",
            heartbeat_at=(now - timedelta(seconds=900)).isoformat(),
        )
        marked = server.job_store.run_watchdog_tick(now=now)
        detail = server.job_store.get_job(job.job_id)
    finally:
        stop_test_server(server)

    assert marked == 0
    assert detail.status == "completed"


def test_stalled_job_can_retry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    now = datetime.now(timezone.utc)
    try:
        job = server.job_store.create_job(
            {
                "title": "Retry Stalled Song",
                "language": "en",
                "style": "pop",
                "theme": "retry stalled",
            },
            start_immediately=False,
        )
        server.job_store._update_job(
            job,
            status="running",
            step="generate",
            heartbeat_at=(now - timedelta(seconds=301)).isoformat(),
        )
        server.job_store.run_watchdog_tick(now=now)
        status, data = request_json(server, "POST", f"/api/jobs/{job.job_id}/retry")
        final = wait_for_job(server, job.job_id)
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["job"]["retry_count"] == 1
    assert final["status"] == "completed"


def test_invalid_request_returns_json_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "POST", "/api/jobs", {"title": "Broken"})
    finally:
        stop_test_server(server)

    assert status == 400
    assert "error" in data


def write_job_state(tmp_path, job_id, overrides):
    run_dir = tmp_path / "runs" / job_id
    state_dir = run_dir / "data"
    state_dir.mkdir(parents=True)
    state = {
        "job_id": job_id,
        "title": job_id.replace("-", " ").title(),
        "output_dir": str(run_dir),
        "status": "completed",
        "created_at": "2026-05-05T00:00:00+00:00",
        "updated_at": "2026-05-05T00:00:00+00:00",
    }
    state.update(overrides)
    state_path = state_dir / "job-state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path
