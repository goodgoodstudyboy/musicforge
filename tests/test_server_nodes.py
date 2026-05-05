import json
import threading
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
    return response.status, json.loads(data.decode("utf-8"))


def wait_for_job(server, job_id):
    for _ in range(80):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
    raise AssertionError("job did not finish")


def test_nodes_endpoint_lists_records(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/nodes")
    finally:
        stop_test_server(server)

    assert status == 200
    assert final["status"] == "completed"
    assert final["pipeline_mode"] == "multinode"
    assert data["nodes"][0]["node"] == "brief_planner"
    assert "output" not in data["nodes"][0]


def test_node_detail_endpoint_returns_record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "GET",
            f"/api/jobs/{final['job_id']}/nodes/brief_planner",
        )
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["node"]["node"] == "brief_planner"
    assert data["node"]["output"]["title"] == "Server Nodes Song"


def test_node_detail_rejects_unknown_node(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "GET",
            f"/api/jobs/{final['job_id']}/nodes/missing",
        )
    finally:
        stop_test_server(server)

    assert status == 404
    assert data["error"] == "Node record not found."


def test_node_detail_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "GET",
            f"/api/jobs/{final['job_id']}/nodes/..%5Cjob-state",
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert "Node name" in data["error"]


def test_node_retry_placeholder_returns_501(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{final['job_id']}/nodes/brief_planner/retry",
        )
    finally:
        stop_test_server(server)

    assert status == 501
    assert "v0.3.1" in data["error"]


def test_node_retry_rejects_invalid_node_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{final['job_id']}/nodes/..%5Cjob-state/retry",
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert "Node name" in data["error"]


def test_provider_mock_multinode_job_writes_provider_nodes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                **payload(),
                "title": "Provider Nodes Song",
                "generation_mode": "provider",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(server, "GET", f"/api/jobs/{final['job_id']}/nodes")
    finally:
        stop_test_server(server)

    assert status == 200
    assert final["status"] == "completed"
    brief = next(node for node in data["nodes"] if node["node"] == "brief_planner")
    assert brief["provider_mode"] == "provider"
    assert (Path(final["output_dir"]) / "data" / "nodes" / "brief_planner.json").exists()


def test_invalid_pipeline_mode_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/jobs",
            {**payload(), "pipeline_mode": "graph"},
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert data["error"] == "pipeline_mode must be either single or multinode."


def payload():
    return {
        "title": "Server Nodes Song",
        "language": "en",
        "style": "pop",
        "theme": "nodes api",
        "pipeline_mode": "multinode",
    }
