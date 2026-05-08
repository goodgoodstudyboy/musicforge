from __future__ import annotations

import json
import threading
import time
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
    for _ in range(120):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def create_asset(server):
    status, data = request_json(
        server,
        "POST",
        "/api/assets",
        {
            "asset_type": "motif",
            "name": "Rainy hook motif",
            "tags": ["rainy", "hook"],
            "style": "synth pop",
            "key": "C",
            "tempo_bpm": 120,
            "content": {"notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1}]},
        },
    )
    assert status == 201
    return data["asset"]


def create_reference(server):
    status, data = request_json(
        server,
        "POST",
        "/api/references/import",
        {
            "reference_type": "style_note",
            "filename": "style.md",
            "title": "Rainy reference",
            "tags": ["rainy"],
            "content_base64": "UmFpbnkgaG9vayBzeW50aA==",
        },
    )
    assert status == 201
    return data["reference"]


def test_library_and_context_pack_api_use_pack_in_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        asset = create_asset(server)
        reference = create_reference(server)
        index_status, index = request_json(server, "POST", "/api/library/rebuild", {})
        search_status, search = request_json(server, "POST", "/api/library/search", {"query": "rainy hook", "roles": ["hook"]})
        recommend_status, recommend = request_json(
            server,
            "POST",
            "/api/library/recommend",
            {"source": "song_request", "goal": "generate", "song_request": {"title": "Rain", "style": "synth pop", "theme": "rainy hook", "tempo_bpm": 118, "key": "C"}},
        )
        pack_status, pack_data = request_json(
            server,
            "POST",
            "/api/context-packs",
            {
                "name": "Rainy Context",
                "asset_refs": [{"asset_id": asset["asset_id"], "role": "hook", "strength": 0.9}],
                "reference_refs": [{"reference_id": reference["reference_id"], "role": "style", "strength": 0.5}],
            },
        )
        pack_id = pack_data["context_pack"]["pack_id"]
        apply_status, applied = request_json(server, "POST", f"/api/context-packs/{pack_id}/apply-preview", {})
        job_status, job = request_json(
            server,
            "POST",
            "/api/jobs",
            {
                "title": "Context Job",
                "language": "English",
                "style": "synth pop",
                "theme": "rainy context",
                "context_pack_id": pack_id,
            },
        )
        completed = wait_for_job(server, job["job_id"])
    finally:
        stop_test_server(server)

    assert index_status == 200
    assert index["index"]["item_count"] == 2
    assert search_status == 200
    assert search["results"][0]["score_breakdown"]
    assert recommend_status == 200
    assert recommend["recommendation"]["context_pack_preview"]["asset_refs"]
    assert pack_status == 201
    assert apply_status == 200
    assert applied["asset_refs"][0]["asset_id"] == asset["asset_id"]
    assert job_status == 202
    assert completed["status"] == "completed"
    assert "context_pack" in completed["artifacts"]
    context_snapshot = json.loads((Path(completed["output_dir"]) / "data" / "context-pack.json").read_text(encoding="utf-8"))
    assert context_snapshot["pack_id"] == pack_id
    assert context_snapshot["asset_refs"][0]["asset_id"] == asset["asset_id"]


def test_context_pack_stale_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        asset = create_asset(server)
        pack_status, pack_data = request_json(server, "POST", "/api/context-packs", {"asset_refs": [{"asset_id": asset["asset_id"]}]})
        assert pack_status == 201
        path = Path(".musicforge") / "assets" / asset["asset_id"] / "asset.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["content"]["notes"].append({"pitch": 64, "start_beat": 1, "duration_beats": 1})
        path.write_text(json.dumps(data), encoding="utf-8")
        status, error = request_json(server, "POST", f"/api/context-packs/{pack_data['context_pack']['pack_id']}/apply-preview", {})
    finally:
        stop_test_server(server)

    assert status == 409
    assert "stale" in error["error"]


def test_context_pack_api_concurrent_create_uses_unique_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        asset = create_asset(server)
        reference = create_reference(server)

        def create_pack(index):
            status, data = request_json(
                server,
                "POST",
                "/api/context-packs",
                {
                    "name": "Concurrent Context",
                    "created_from": {"index": index},
                    "asset_refs": [{"asset_id": asset["asset_id"], "role": "hook"}],
                    "reference_refs": [{"reference_id": reference["reference_id"], "role": "style"}],
                },
            )
            assert status == 201
            return data["context_pack"]["pack_id"]

        with ThreadPoolExecutor(max_workers=12) as executor:
            pack_ids = list(executor.map(create_pack, range(24)))
    finally:
        stop_test_server(server)

    assert len(pack_ids) == 24
    assert len(set(pack_ids)) == 24
    for pack_id in pack_ids:
        assert (Path(".musicforge") / "context-packs" / pack_id / "pack.json").exists()
