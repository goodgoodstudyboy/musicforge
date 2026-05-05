import json
import threading
from concurrent.futures import ThreadPoolExecutor
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


def wait_for_job(server, job_id):
    for _ in range(80):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed"}:
            return job
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


def test_invalid_request_returns_json_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "POST", "/api/jobs", {"title": "Broken"})
    finally:
        stop_test_server(server)

    assert status == 400
    assert "error" in data
