from __future__ import annotations

import json
from pathlib import Path

from song_agent.auth import AuthConfig
from song_agent.server import create_server
from tests.test_server_auth import TOKEN, request_json as auth_request_json, stop_test_server as stop_auth_server
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job
from tests.test_server_review_sprints import _create_two_review_tasks


def test_review_sprint_metrics_api_refresh_project_export_and_final_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        provider_status, _provider = request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
        project_id, first_task_id, second_task_id = _create_two_review_tasks(server)
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints",
            {"name": r"Metrics C:\Users\demo", "task_ids": [first_task_id, second_task_id], "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2}},
        )
        sprint_id = created["sprint"]["sprint_id"]
        queue_status, queue_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        queue_id = queue_data["queue"]["queue_id"]
        local_item_ids = [item["item_id"] for item in queue_data["queue"]["items"] if item["action"] in {"save_recommended_context_pack", "generate_local_candidates"}]
        local_run_status, _local_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": local_item_ids})
        provider_queue_status, provider_queue = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        provider_queue_id = provider_queue["queue"]["queue_id"]
        provider_item_ids = [item["item_id"] for item in provider_queue["queue"]["items"] if item["action"] == "generate_provider_candidates"]
        provider_run_status, provider_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}/run", {"item_ids": provider_item_ids[:1], "include_provider": True})
        provider_candidate_id = provider_run["results"][0]["result"]["created_candidate_ids"][0]
        decision_queue_status, decision_queue = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        decision_item_ids = [item["item_id"] for item in decision_queue["queue"]["items"] if item["action"] == "refresh_decision_report"]
        decision_run_status, _decision_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{decision_queue['queue']['queue_id']}/run", {"item_ids": decision_item_ids[:1]})
        task_before_status, task_before = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{first_task_id}")
        queue_before_status, queue_before = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}")
        get_status, metrics_get = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics")
        refresh_status, metrics_refresh = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics/refresh")
        project_get_status, project_get = request_json(server, "GET", f"/api/projects/{project_id}/review-metrics")
        project_refresh_status, project_refresh = request_json(server, "POST", f"/api/projects/{project_id}/review-metrics/refresh")
        task_after_status, task_after = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{first_task_id}")
        queue_after_status, queue_after = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}")
        apply_status, applied = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{first_task_id}/candidates/{provider_candidate_id}/apply", {"version_name": "Metrics Candidate"})
        job = wait_for_job(server, applied["job"]["job_id"])
        metrics_after_apply_status, metrics_after_apply = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics/refresh")
        project_after_apply_status, project_after_apply = request_json(server, "POST", f"/api/projects/{project_id}/review-metrics/refresh")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        final_set_status, _final_set = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": applied["version"]["version_id"], "force": True})
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{project_id}/final-export")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
        events = detail.get("events", [])
        serialized = json.dumps({"metrics": metrics_after_apply, "project": project_after_apply, "export": project_export, "final": final_export}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert provider_status == 200
    assert create_status == 201
    assert queue_status == 201
    assert local_run_status == 200
    assert provider_queue_status == 201
    assert provider_run_status == 200
    assert decision_queue_status == 201
    assert decision_run_status == 200
    assert task_before_status == 200
    assert queue_before_status == 200
    assert get_status == 200
    assert refresh_status == 200
    assert project_get_status == 200
    assert project_refresh_status == 200
    assert task_after_status == 200
    assert queue_after_status == 200
    assert task_after["task"]["status"] == task_before["task"]["status"]
    assert queue_after["queue"]["status"] == queue_before["queue"]["status"]
    assert metrics_get["metrics_report"]["overview"]["task_count"] == 2
    assert metrics_refresh["summary"]["readiness"] in {"needs_candidates", "needs_review", "blocked", "ready_to_close"}
    assert project_get["summary"]["sprint_count"] == 1
    assert project_refresh["review_metrics"]["latest_sprint_id"] == sprint_id
    assert apply_status == 202
    assert job["status"] == "completed"
    assert metrics_after_apply_status == 200
    assert metrics_after_apply["metrics_report"]["candidate_funnel"]["provider_candidate_count"] >= 1
    assert metrics_after_apply["metrics_report"]["manual_decisions"]["manual_apply_count"] >= 1
    assert metrics_after_apply["metrics_report"]["provider_usage"]["provider_call_count"] >= 1
    assert metrics_after_apply["metrics_report"]["quality_delta"]["status"] in {"improved", "unchanged", "regressed", "not_available"}
    assert project_after_apply_status == 200
    assert project_after_apply["summary"]["latest_sprint_id"] == sprint_id
    assert export_status == 200
    assert project_export["review_sprints"][0]["metrics_summary"]["sprint_id"] == sprint_id
    assert project_export["review_metrics_summary"]["latest_sprint_id"] == sprint_id
    assert final_set_status == 200
    assert final_export_status == 200
    assert final_export["final_export"]["review_metrics"]["latest_sprint_id"] == sprint_id
    assert detail_status == 200
    assert any(event["event"] == "review_sprint_metrics_refreshed" for event in events)
    assert (Path(".musicforge") / "projects" / project_id / "review-sprints" / sprint_id / "metrics-report.json").exists()
    assert (Path(".musicforge") / "projects" / project_id / "review-metrics.json").exists()
    assert "sk-secret-value" not in serialized
    assert "api_key" not in serialized
    assert "C:\\Users" not in serialized


def test_review_metrics_api_auth_and_legacy_sprint_without_queue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = create_server("127.0.0.1", 0, auth_config=AuthConfig(enabled=True, token=TOKEN))
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        missing_status, missing_data, _ = auth_request_json(server, "GET", "/api/jobs")
        create_status, created, _ = auth_request_json(server, "POST", "/api/projects", {"name": "Metrics Auth"}, token=TOKEN)
        project_id = created["project"]["project_id"]
        version_status, version_data, _ = auth_request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": {"title": "Metrics Auth", "language": "English", "style": "synth pop", "theme": "auth"}}, token=TOKEN)
        assert version_status == 202, version_data
        job_id = version_data["job"]["job_id"]
        for _ in range(120):
            job_status, job, _ = auth_request_json(server, "GET", f"/api/jobs/{job_id}", token=TOKEN)
            if job["status"] == "completed":
                break
        sprint_status, sprint_data, _ = auth_request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": []}, token=TOKEN)
        sprint_id = sprint_data["sprint"]["sprint_id"]
        unauthorized_status, unauthorized_data, _ = auth_request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics")
        metrics_status, metrics, _ = auth_request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics", token=TOKEN)
        project_metrics_status, project_metrics, _ = auth_request_json(server, "GET", f"/api/projects/{project_id}/review-metrics", token=TOKEN)
    finally:
        stop_auth_server(server)

    assert missing_status == 401
    assert missing_data == {"error": "Unauthorized."}
    assert create_status == 201
    assert version_status == 202
    assert job_status == 200
    assert sprint_status == 201
    assert unauthorized_status == 401
    assert unauthorized_data == {"error": "Unauthorized."}
    assert metrics_status == 200
    assert metrics["metrics_report"]["overview"]["task_count"] == 0
    assert metrics["metrics_report"]["source_summary"]["has_action_queue"] is False
    assert project_metrics_status == 200
    assert project_metrics["summary"]["sprint_count"] == 1
