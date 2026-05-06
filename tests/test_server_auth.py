import json
import threading
from http.client import HTTPConnection

from song_agent.auth import AuthConfig
from song_agent.server import create_server


TOKEN = "local-dev-token-123"
WRONG_TOKEN = "wrong-local-token-123"


def start_test_server(auth_config: AuthConfig | None = None):
    server = create_server("127.0.0.1", 0, auth_config=auth_config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_test_server(server):
    server.shutdown()
    server.server_close()


def request_json(server, method, path, payload=None, token=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    auth_header = response.getheader("WWW-Authenticate")
    connection.close()
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8")), auth_header
    return response.status, data, auth_header


def auth_server():
    return start_test_server(AuthConfig(enabled=True, token=TOKEN))


def test_info_is_public_but_marks_auth_required(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, data, auth_header = request_json(server, "GET", "/api/info")
    finally:
        stop_test_server(server)

    assert status == 200
    assert auth_header is None
    assert data["auth_required"] is True
    assert set(data) == {"app", "version", "auth_required"}
    assert "cwd" not in data
    assert "runs_dir" not in data
    assert TOKEN not in json.dumps(data)


def test_info_with_bearer_returns_full_local_info(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, data, auth_header = request_json(server, "GET", "/api/info", token=TOKEN)
    finally:
        stop_test_server(server)

    assert status == 200
    assert auth_header is None
    assert data["auth_required"] is True
    assert data["cwd"] == str(tmp_path)
    assert data["runs_dir"] == "runs"
    assert data["mode"] == "local-deterministic"


def test_root_html_is_public_in_auth_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, _body, auth_header = request_json(server, "GET", "/")
    finally:
        stop_test_server(server)

    assert status == 200
    assert auth_header is None


def test_missing_token_returns_401_without_leaking_tokens(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, data, auth_header = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status == 401
    assert auth_header == "Bearer"
    assert data == {"error": "Unauthorized."}
    assert TOKEN not in json.dumps(data)


def test_wrong_token_returns_401_without_echo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, data, _auth_header = request_json(server, "GET", "/api/jobs", token=WRONG_TOKEN)
    finally:
        stop_test_server(server)

    assert status == 401
    assert data == {"error": "Unauthorized."}
    assert WRONG_TOKEN not in json.dumps(data)
    assert TOKEN not in json.dumps(data)


def test_correct_bearer_token_allows_jobs_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, data, _auth_header = request_json(server, "GET", "/api/jobs", token=TOKEN)
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["jobs"] == []


def test_auth_protects_job_create_provider_renderer_and_batch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        protected = [
            ("POST", "/api/jobs", {"title": "Auth Song", "language": "en", "style": "pop", "theme": "auth"}),
            ("GET", "/api/provider", None),
            ("GET", "/api/renderer", None),
            ("GET", "/api/batches", None),
            ("POST", "/api/batches/import-csv", {"name": "x", "csv_text": ""}),
            ("POST", "/api/batches/demo/render-stems", None),
            ("POST", "/api/batches/demo/render-stem-audio", None),
        ]
        statuses = [request_json(server, method, path, payload=payload)[0] for method, path, payload in protected]
    finally:
        stop_test_server(server)

    assert statuses == [401] * len(protected)


def test_auth_protects_dangerous_job_routes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = auth_server()
    try:
        status, job, _auth_header = request_json(
            server,
            "POST",
            "/api/jobs",
            {"title": "Danger Song", "language": "en", "style": "pop", "theme": "danger"},
            token=TOKEN,
        )
        assert status == 202
        job_id = job["job_id"]
        routes = [
            ("POST", f"/api/jobs/{job_id}/cancel"),
            ("POST", f"/api/jobs/{job_id}/delete"),
            ("POST", f"/api/jobs/{job_id}/open-folder"),
            ("POST", f"/api/jobs/{job_id}/render-audio"),
            ("POST", f"/api/jobs/{job_id}/render-stems"),
            ("POST", f"/api/jobs/{job_id}/render-stem-audio"),
            ("GET", f"/api/jobs/{job_id}/midi"),
            ("GET", f"/api/jobs/{job_id}/stems"),
            ("GET", f"/api/jobs/{job_id}/stems/melody/midi"),
            ("GET", f"/api/jobs/{job_id}/artifacts"),
            ("GET", f"/api/jobs/{job_id}/quality"),
        ]
        statuses = [request_json(server, method, path)[0] for method, path in routes]
    finally:
        stop_test_server(server)

    assert statuses == [401] * len(routes)


def test_no_auth_mode_still_allows_jobs_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server(AuthConfig(enabled=False))
    try:
        status, data, _auth_header = request_json(server, "GET", "/api/jobs")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["jobs"] == []
