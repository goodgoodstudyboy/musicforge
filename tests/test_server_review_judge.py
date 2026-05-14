from __future__ import annotations

import json
from pathlib import Path

from song_agent.auth import AuthConfig
from song_agent.server import create_server
from tests.test_server_auth import TOKEN, request_json as auth_request_json, stop_test_server as stop_auth_server
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job
from tests.test_server_review_tasks import _create_review_task


def test_review_judge_api_decision_apply_export_and_usage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        provider_status, _provider = request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
        project_id, _preview_id, _audition_id, task_id, _task_data = _create_review_task(server)
        local_status, _local = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {"strategies": ["balanced", "bold"]})
        judge_get_status, judge_get = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/judge-report")
        judge_refresh_status, judge_refresh = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/judge-report/refresh", {"note": r"judge C:\Users\demo"})
        judge_candidate_id = judge_refresh["judge_report"]["recommended_candidate_id"]
        decision_status, decision = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/decision-report/refresh", {})
        apply_status, applied = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{judge_candidate_id}/apply", {"version_name": "Judge Candidate"})
        job = wait_for_job(server, applied["job"]["job_id"])
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={applied['version']['version_id']}")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        final_status, _final = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": applied["version"]["version_id"], "force": True})
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{project_id}/final-export")
        usage_status, usage = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        metadata = json.loads((Path(job["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
        serialized = json.dumps({"judge": judge_refresh, "decision": decision, "metadata": metadata, "compare": compare, "export": project_export, "final": final_export, "usage": usage}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert provider_status == 200
    assert local_status == 201
    assert judge_get_status == 200
    assert judge_get["summary"]["status"] == "not_started"
    assert judge_refresh_status == 200
    assert judge_refresh["summary"]["status"] == "completed"
    assert judge_refresh["judge_report"]["candidate_scores"]
    assert decision_status == 200
    assert decision["decision_report"]["judge_summary"]["recommended_candidate_id"] == judge_candidate_id
    assert decision["decision_report"]["requires_manual_apply"] is True
    assert apply_status == 202
    assert job["status"] == "completed"
    assert metadata["review_judge"]["judge_recommended_candidate_id"] == judge_candidate_id
    assert metadata["review_judge"]["applied_matches_judge"] is True
    assert compare_status == 200
    assert compare["right"]["edit"]["review_judge"]["applied_matches_judge"] is True
    assert export_status == 200
    assert project_export["review_tasks"][0]["judge_summary"]["recommended_candidate_id"] == judge_candidate_id
    assert final_status == 200
    assert final_export_status == 200
    assert final_export["final_export"]["review_judge"]["applied_matches_judge"] is True
    assert usage_status == 200
    assert any(record["operation"] == "provider_review_judge" for record in usage["records"])
    assert (Path(".musicforge") / "projects" / project_id / "review-tasks" / task_id / "judge-report.json").exists()
    assert (Path(".musicforge") / "projects" / project_id / "review-tasks" / task_id / "judge-provider-usage.json").exists()
    assert "sk-secret-value" not in serialized
    assert "api_key" not in serialized
    assert "C:\\Users" not in serialized


def test_review_judge_api_requires_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = create_server("127.0.0.1", 0, auth_config=AuthConfig(enabled=True, token=TOKEN))
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _provider_status, _provider, _ = auth_request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review"}, token=TOKEN)
        create_status, created, _ = auth_request_json(server, "POST", "/api/projects", {"name": "Judge Auth"}, token=TOKEN)
        project_id = created["project"]["project_id"]
        unauthorized_status, unauthorized, _ = auth_request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/review-task-001/judge-report")
    finally:
        stop_auth_server(server)

    assert create_status == 201
    assert unauthorized_status == 401
    assert unauthorized == {"error": "Unauthorized."}
