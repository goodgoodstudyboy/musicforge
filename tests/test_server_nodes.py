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
    for _ in range(120):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def wait_for_job_status(server, job_id, statuses):
    for _ in range(120):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in statuses:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job did not reach {statuses}")


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


def test_node_retry_updates_song_plan_and_midi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        stem_status, stem_data = request_json(server, "POST", f"/api/jobs/{final['job_id']}/render-stems")
        assert stem_status == 200
        assert stem_data["manifest"]["stems"][0]["midi_exists"] is True
        stem_manifest_path = Path(final["output_dir"]) / "stems" / "manifest.json"
        assert stem_manifest_path.exists()
        midi_path = Path(final["output_dir"]) / "renders" / "song.mid"
        before_mtime = midi_path.stat().st_mtime_ns
        before_brief = request_json(
            server,
            "GET",
            f"/api/jobs/{final['job_id']}/nodes/brief_planner",
        )[1]["node"]["started_at"]
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{final['job_id']}/nodes/brief_planner/retry",
        )
        after = wait_for_job_status(server, final["job_id"], {"completed", "failed", "cancelled"})
        node = request_json(
            server,
            "GET",
            f"/api/jobs/{final['job_id']}/nodes/brief_planner",
        )[1]["node"]
    finally:
        stop_test_server(server)

    assert status == 202
    assert data["retry"]["node"] == "brief_planner"
    assert "song_plan_builder" in data["retry"]["affected_nodes"]
    assert after["status"] == "completed"
    assert after["retry_count"] == 1
    assert node["started_at"] != before_brief
    assert node["retry_count"] == 1
    assert midi_path.stat().st_mtime_ns >= before_mtime
    assert not stem_manifest_path.exists()
    assert "stems" not in after["artifacts"]
    assert "stem_audio" not in after["artifacts"]


def test_node_retry_harmony_affects_arrangement_and_tail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        before = {}
        for node in ["melody_planner", "harmony_planner", "arrangement_planner", "critic"]:
            before[node] = request_json(
                server,
                "GET",
                f"/api/jobs/{final['job_id']}/nodes/{node}",
            )[1]["node"]["started_at"]
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{final['job_id']}/nodes/harmony_planner/retry",
        )
        after_job = wait_for_job_status(server, final["job_id"], {"completed", "failed", "cancelled"})
        after = {}
        for node in ["melody_planner", "harmony_planner", "arrangement_planner", "critic"]:
            after[node] = request_json(
                server,
                "GET",
                f"/api/jobs/{final['job_id']}/nodes/{node}",
            )[1]["node"]
    finally:
        stop_test_server(server)

    assert status == 202
    assert data["retry"]["affected_nodes"] == [
        "harmony_planner",
        "arrangement_planner",
        "critic",
        "repair",
        "song_plan_builder",
    ]
    assert after_job["status"] == "completed"
    assert after["melody_planner"]["started_at"] == before["melody_planner"]
    assert after["harmony_planner"]["started_at"] != before["harmony_planner"]
    assert after["arrangement_planner"]["started_at"] != before["arrangement_planner"]
    assert after["critic"]["started_at"] != before["critic"]


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


def test_node_retry_rejects_single_pipeline_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Single Retry Song",
                "language": "en",
                "style": "pop",
                "theme": "single retry",
            },
        )
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{final['job_id']}/nodes/brief_planner/retry",
        )
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Node retry requires a multinode job."


def test_node_retry_rejects_running_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job = server.job_store.create_job(payload(), start_immediately=False)
        server.job_store._update_job(job, status="running", step="generate")
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{job.job_id}/nodes/brief_planner/retry",
        )
    finally:
        stop_test_server(server)

    assert status == 409
    assert data["error"] == "Cannot retry a node while the job is running."


def test_node_retry_unknown_node_returns_404(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "POST",
            f"/api/jobs/{final['job_id']}/nodes/missing_node/retry",
        )
    finally:
        stop_test_server(server)

    assert status == 404
    assert data["error"] == "Node record not found."


def test_node_dependencies_endpoint_returns_graph(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, job = request_json(server, "POST", "/api/jobs", payload())
        final = wait_for_job(server, job["job_id"])
        status, data = request_json(
            server,
            "GET",
            f"/api/jobs/{final['job_id']}/nodes/lyric_planner/dependencies",
        )
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["upstream"] == ["brief_planner", "structure_planner"]
    assert data["affected_nodes"] == ["lyric_planner", "critic", "repair", "song_plan_builder"]


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
