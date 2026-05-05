import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import song_agent.server as server_module
from song_agent.provider import ProviderRequestError
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


def test_get_provider_returns_masked_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/provider",
            {
                "base_url": "https://api.example.com/v1",
                "wire_api": "openai_chat_completions",
                "api_key": "sk-example-secret",
                "model": "example-main",
            },
        )
        status, data = request_json(server, "GET", "/api/provider")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["configured"] is True
    assert data["config"]["api_key_set"] is True
    assert data["config"]["api_key_masked"] == "sk-...cret"
    assert "api_key" not in data["config"]


def test_post_provider_saves_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/provider",
            {
                "wire_api": "mock",
                "api_key": "secret",
                "model": "mock-main",
                "timeout_seconds": 30,
                "max_retries": 2,
            },
        )
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["ok"] is True
    assert data["configured"] is True
    provider_file = tmp_path / ".musicforge" / "provider.json"
    assert provider_file.exists()
    raw = json.loads(provider_file.read_text(encoding="utf-8"))
    assert raw["api_key"] == "secret"
    assert data["config"]["api_key_masked"] == "***"


def test_provider_reset_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        status, data = request_json(server, "POST", "/api/provider/reset")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data == {"ok": True, "configured": False}
    assert not (tmp_path / ".musicforge" / "provider.json").exists()


def test_provider_api_never_returns_plain_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, post_data = request_json(
            server,
            "POST",
            "/api/provider",
            {
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-plain-secret",
                "model": "example-main",
            },
        )
        _status, get_data = request_json(server, "GET", "/api/provider")
    finally:
        stop_test_server(server)

    assert "sk-plain-secret" not in json.dumps(post_data)
    assert "sk-plain-secret" not in json.dumps(get_data)


def test_provider_test_without_key_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/provider",
            {"wire_api": "openai_chat_completions", "model": "example-main"},
        )
        status, data = request_json(server, "POST", "/api/provider/test")
    finally:
        stop_test_server(server)

    assert status == 400
    assert data["error"] == "Provider config is incomplete: base_url, api_key is required."


def test_provider_test_with_mock_returns_ok(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        status, data = request_json(server, "POST", "/api/provider/test")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["ok"] is True
    assert data["provider"]["wire_api"] == "mock"
    assert data["message"] == "Mock provider test completed."


def test_provider_test_failure_returns_json_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        monkeypatch.setattr(
            "song_agent.provider.test_provider_config",
            lambda config: _raise(ProviderRequestError("mock provider down")),
        )
        monkeypatch.setattr(
            "song_agent.server.test_provider_config",
            lambda config: _raise(ProviderRequestError("mock provider down")),
        )
        status, data = request_json(server, "POST", "/api/provider/test")
    finally:
        stop_test_server(server)

    assert status == 400
    assert data["error"] == "mock provider down"


def test_post_provider_rejects_invalid_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "POST", "/api/provider", {"timeout_seconds": 1})
    finally:
        stop_test_server(server)

    assert status == 400
    assert "timeout_seconds" in data["error"]


def test_local_generation_mode_still_completes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Local Mode Song",
                "language": "en",
                "style": "pop",
                "theme": "local mode",
                "generation_mode": "local",
            },
        )
        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert status == 202
    assert final["status"] == "completed"
    assert final["provider_snapshot"]["mode"] == "local"


def test_provider_generation_mode_requires_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Needs Provider",
                "language": "en",
                "style": "pop",
                "theme": "provider required",
                "generation_mode": "provider",
            },
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert "Provider config is incomplete" in data["error"]


def test_provider_generation_mode_writes_provider_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/provider",
            {
                "wire_api": "mock",
                "model": "mock-main",
                "api_key": "sk-provider-secret",
            },
        )
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Provider Snapshot Song",
                "language": "en",
                "style": "pop",
                "theme": "snapshot",
                "generation_mode": "provider",
            },
        )
        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert final["status"] == "completed"
    assert final["provider_snapshot"]["mode"] == "provider"
    assert final["provider_snapshot"]["api_key_masked"] == "sk-...cret"
    snapshot_path = Path(final["output_dir"]) / "data" / "provider-snapshot.json"
    assert snapshot_path.exists()
    raw = snapshot_path.read_text(encoding="utf-8")
    assert "sk-provider-secret" not in raw
    assert "sk-...cret" in raw


def test_provider_generation_mode_renders_midi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Provider Midi Song",
                "language": "en",
                "style": "pop",
                "theme": "provider midi",
                "generation_mode": "provider",
            },
        )
        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert final["status"] == "completed"
    assert (Path(final["output_dir"]) / "renders" / "song.mid").stat().st_size > 100


def test_provider_failure_marks_job_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        server_module,
        "generate_request",
        lambda request, **kwargs: (_raise(ProviderRequestError("mock failure"))),
    )
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Provider Failure Song",
                "language": "en",
                "style": "pop",
                "theme": "provider failure",
                "generation_mode": "provider",
            },
        )
        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert final["status"] == "failed"
    assert final["error"] == "mock failure"
    snapshot_path = Path(final["output_dir"]) / "data" / "provider-snapshot.json"
    assert snapshot_path.exists()


def test_provider_snapshot_masks_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/provider",
            {"wire_api": "mock", "model": "mock-main", "api_key": "plain-secret-key"},
        )
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Snapshot Mask Song",
                "language": "en",
                "style": "pop",
                "theme": "mask",
                "generation_mode": "provider",
            },
        )
        final = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    serialized = json.dumps(final)
    assert "plain-secret-key" not in serialized
    assert "pla...-key" in serialized


def test_retry_provider_job_writes_masked_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/provider",
            {"wire_api": "mock", "model": "mock-main", "api_key": "retry-secret-key"},
        )
        _status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Retry Provider Snapshot",
                "language": "en",
                "style": "pop",
                "theme": "retry provider snapshot",
                "generation_mode": "provider",
            },
        )
        final = wait_for_job(server, job["job_id"])
        assert final["status"] == "completed"
        server.job_store._update_job(
            server.job_store.get_job(final["job_id"]),
            status="failed",
            step="failed",
            error="forced failure",
        )
        status, retry = request_json(server, "POST", f"/api/jobs/{final['job_id']}/retry")
        retried = wait_for_job(server, final["job_id"])
    finally:
        stop_test_server(server)

    assert status == 200
    assert retry["job"]["retry_count"] == 1
    assert retried["status"] == "completed"
    serialized = json.dumps(retried)
    assert "retry-secret-key" not in serialized
    assert "ret...-key" in serialized


def _raise(exc):
    raise exc
