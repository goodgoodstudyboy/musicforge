from __future__ import annotations

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


def request_payload(title="Project API Song"):
    return {
        "title": title,
        "language": "English",
        "style": "synth pop",
        "theme": "project api",
    }


def test_project_crud_and_hide_delete_do_not_delete_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, created = request_json(
            server,
            "POST",
            "/api/projects",
            {"name": "Project API Song", "description": "workspace", "tags": ["demo"]},
        )
        project_id = created["project"]["project_id"]
        list_status, listed = request_json(server, "GET", "/api/projects")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
        hide_status, _hidden = request_json(server, "POST", f"/api/projects/{project_id}/hide")
        hidden_list_status, hidden_list = request_json(server, "GET", "/api/projects")
        all_list_status, all_list = request_json(server, "GET", "/api/projects?include_hidden=1")
        unhide_status, _visible = request_json(server, "POST", f"/api/projects/{project_id}/unhide")
        job_status, job = request_json(server, "POST", "/api/jobs", request_payload())
        final_job = wait_for_job(server, job["job_id"])
        attach_status, attached = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": final_job["job_id"]},
        )
        run_dir = Path(final_job["output_dir"])
        delete_status, deleted = request_json(server, "POST", f"/api/projects/{project_id}/delete")
    finally:
        stop_test_server(server)

    assert status == 201
    assert created["project"]["name"] == "Project API Song"
    assert created["versions"] == []
    assert list_status == 200
    assert listed["projects"][0]["project_id"] == project_id
    assert detail_status == 200
    assert detail["project"]["description"] == "workspace"
    assert hide_status == 200
    assert hidden_list_status == 200
    assert hidden_list["projects"] == []
    assert all_list_status == 200
    assert all_list["projects"][0]["hidden"] is True
    assert unhide_status == 200
    assert job_status == 202
    assert attach_status == 200
    assert attached["version"]["version_id"] == "v001"
    assert delete_status == 200
    assert deleted["deleted"] is True
    assert run_dir.exists()


def test_create_project_with_request_creates_first_version_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/projects",
            {
                "name": "Request Project",
                "request": request_payload("Request Project"),
                "pipeline_mode": "multinode",
            },
        )
        job = wait_for_job(server, data["job"]["job_id"])
        detail_status, detail = request_json(server, "GET", f"/api/projects/{data['project']['project_id']}")
    finally:
        stop_test_server(server)

    assert status == 201
    assert data["versions"][0]["version_id"] == "v001"
    assert data["versions"][0]["job_id"] == data["job"]["job_id"]
    assert job["status"] == "completed"
    assert detail_status == 200
    assert detail["versions"][0]["status"] == "completed"
    assert detail["versions"][0]["has_midi"] is True
    assert detail["project"]["best_quality_score"] is not None


def test_create_project_version_selected_final_diff_and_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Version Project"})
        project_id = created["project"]["project_id"]
        first_status, first = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": request_payload("Version One"), "name": "Version One"},
        )
        second_status, second = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": {**request_payload("Version Two"), "tempo_bpm": 96}, "name": "Version Two"},
        )
        first_job = wait_for_job(server, first["job"]["job_id"])
        second_job = wait_for_job(server, second["job"]["job_id"])
        selected_status, selected = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/selected",
            {"version_id": "v002"},
        )
        final_status, final = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/final",
            {"version_id": "v001"},
        )
        diff_status, diff = request_json(server, "GET", f"/api/projects/{project_id}/diff?left=v001&right=v002")
        export_status, export = request_json(server, "GET", f"/api/projects/{project_id}/export")
    finally:
        stop_test_server(server)

    assert first_status == 202
    assert second_status == 202
    assert first_job["status"] == "completed"
    assert second_job["status"] == "completed"
    assert selected_status == 200
    assert selected["project"]["selected_version_id"] == "v002"
    assert final_status == 200
    assert final["project"]["status"] == "finalized"
    assert final["project"]["final_version_id"] == "v001"
    assert diff_status == 200
    assert diff["changed"]["request"]["tempo_bpm"] == {"left": None, "right": 96}
    assert export_status == 200
    assert export["project"]["project_id"] == project_id
    assert (tmp_path / ".musicforge" / "projects" / project_id / "export.json").exists()


def test_project_rejects_duplicate_job_missing_job_and_non_completed_final(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Reject Project"})
        project_id = created["project"]["project_id"]
        job = server.job_store.create_job(request_payload("Queued Project Job"), start_immediately=False)
        attach_status, _attached = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": job.job_id},
        )
        duplicate_status, duplicate = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": job.job_id},
        )
        final_status, final = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/final",
            {"version_id": "v001"},
        )
        missing_status, missing = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": "missing"},
        )
    finally:
        stop_test_server(server)

    assert attach_status == 200
    assert duplicate_status == 409
    assert "already attached" in duplicate["error"]
    assert final_status == 409
    assert final["error"] == "Only completed versions can be marked final."
    assert missing_status == 404
    assert missing["error"] == "Job not found."


def test_project_marks_version_missing_when_job_deleted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Missing Job Project"})
        project_id = created["project"]["project_id"]
        job = server.job_store.create_job(request_payload("Missing Job"), start_immediately=False)
        request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": job.job_id},
        )
        server.job_store.jobs.pop(job.job_id)
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
    finally:
        stop_test_server(server)

    assert detail_status == 200
    assert detail["versions"][0]["status"] == "missing_job"
    assert detail["versions"][0]["missing_job"] is True


def test_create_variation_from_parent_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Variation Project"})
        project_id = created["project"]["project_id"]
        first_status, first = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": request_payload("Variation Parent"), "name": "Parent"},
        )
        wait_for_job(server, first["job"]["job_id"])
        variation_status, variation = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/variation",
            {
                "variant_type": "style_variation",
                "name": "Warmer synth version",
                "note": "Keep lyrics, warmer arrangement",
                "change_summary": "style -> warm synth pop; tempo -> 96",
                "request_patch": {
                    "style": "warm synth pop, softer drums",
                    "tempo_bpm": 96,
                },
                "pipeline_mode": "multinode",
            },
        )
        variation_job = wait_for_job(server, variation["job"]["job_id"])
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
        events_status, events = request_json(server, "GET", f"/api/projects/{project_id}/events")
    finally:
        stop_test_server(server)

    assert first_status == 202
    assert variation_status == 202
    assert variation["version"]["version_id"] == "v002"
    assert variation["version"]["parent_version_id"] == "v001"
    assert variation["version"]["variant_type"] == "style_variation"
    assert variation["version"]["change_summary"] == "style -> warm synth pop; tempo -> 96"
    assert variation["job"]["input_payload"]["title"] == "Variation Parent"
    assert variation["job"]["input_payload"]["style"] == "warm synth pop, softer drums"
    assert variation["job"]["input_payload"]["tempo_bpm"] == 96
    assert variation["job"]["pipeline_mode"] == "multinode"
    assert variation_job["status"] == "completed"
    assert detail_status == 200
    assert detail["project"]["version_count"] == 2
    assert events_status == 200
    assert any(event["type"] == "variation_created" for event in events["events"])


def test_create_variation_rejects_invalid_parent_job_and_patch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Bad Variation Project"})
        project_id = created["project"]["project_id"]
        job = server.job_store.create_job(request_payload("Missing Parent Job"), start_immediately=False)
        request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": job.job_id},
        )
        missing_parent_status, missing_parent = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v999/variation",
            {"request_patch": {"style": "x"}},
        )
        bad_patch_status, bad_patch = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/variation",
            {"request_patch": {"bad": "x"}},
        )
        server.job_store.jobs.pop(job.job_id)
        missing_job_status, missing_job = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/variation",
            {"request_patch": {"style": "x"}},
        )
    finally:
        stop_test_server(server)

    assert missing_parent_status == 404
    assert missing_parent["error"] == "Version not found."
    assert bad_patch_status == 400
    assert "unsupported fields" in bad_patch["error"]
    assert missing_job_status == 409
    assert missing_job["error"] == "Parent version job is missing."


def test_project_quality_gate_config_evaluate_and_final_response(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Gate Project"})
        project_id = created["project"]["project_id"]
        first_status, first = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": request_payload("Gate Version"), "name": "Gate Version"},
        )
        wait_for_job(server, first["job"]["job_id"])
        config_status, config = request_json(server, "GET", f"/api/projects/{project_id}/quality-gate")
        save_status, saved = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/quality-gate",
            {"min_overall": 70, "min_structure": 60, "min_melody": 60, "min_harmony": 60, "min_arrangement": 60},
        )
        eval_status, evaluated = request_json(server, "POST", f"/api/projects/{project_id}/versions/v001/evaluate")
        final_status, final = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/final",
            {"version_id": "v001"},
        )
    finally:
        stop_test_server(server)

    assert first_status == 202
    assert config_status == 200
    assert config["config"]["min_overall"] == 75
    assert save_status == 200
    assert saved["config"]["min_overall"] == 70
    assert eval_status == 200
    assert evaluated["quality_gate"]["status"] == "passed"
    assert evaluated["version"]["quality_gate_status"] == "passed"
    assert final_status == 200
    assert final["quality_gate"]["status"] == "passed"
    assert final["project"]["final_version_id"] == "v001"


def test_project_final_quality_gate_rejects_and_force_records_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Strict Gate Project"})
        project_id = created["project"]["project_id"]
        first_status, first = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": request_payload("Strict Gate Version"), "name": "Strict Gate Version"},
        )
        wait_for_job(server, first["job"]["job_id"])
        request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/quality-gate",
            {"min_overall": 100, "min_structure": 100, "min_melody": 100, "min_harmony": 100, "min_arrangement": 100},
        )
        blocked_status, blocked = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/final",
            {"version_id": "v001"},
        )
        forced_status, forced = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/final",
            {"version_id": "v001", "force": True},
        )
        events_status, events = request_json(server, "GET", f"/api/projects/{project_id}/events")
    finally:
        stop_test_server(server)

    assert first_status == 202
    assert blocked_status == 409
    assert blocked["error"] == "Quality gate failed."
    assert blocked["quality_gate"]["status"] == "failed"
    assert forced_status == 200
    assert forced["quality_gate"]["status"] == "failed"
    assert forced["project"]["final_version_id"] == "v001"
    assert events_status == 200
    event_types = [event["type"] for event in events["events"]]
    assert "final_version_gate_failed" in event_types
    assert "final_version_force_set" in event_types


def test_project_evaluate_all_marks_missing_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Missing Plan Gate Project"})
        project_id = created["project"]["project_id"]
        job = server.job_store.create_job(request_payload("No Plan"), start_immediately=False)
        request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/from-job",
            {"job_id": job.job_id},
        )
        status, data = request_json(server, "POST", f"/api/projects/{project_id}/quality-gate/evaluate-all")
    finally:
        stop_test_server(server)

    assert status == 200
    assert data["results"][0]["quality_gate"]["status"] == "missing_plan"
    assert data["versions"][0]["quality_gate_status"] == "missing_plan"
