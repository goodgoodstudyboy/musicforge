from __future__ import annotations

import json
from pathlib import Path

from song_agent.projectio import read_json, write_json
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job
from tests.test_server_review_sprints import _create_two_review_tasks


def test_review_sprint_action_queue_api_runs_safe_items_and_blocks_provider_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        provider_status, _provider = request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
        project_id, first_task_id, second_task_id = _create_two_review_tasks(server)
        asset_status, _asset = request_json(
            server,
            "POST",
            "/api/assets",
            {
                "asset_type": "bass_pattern",
                "name": "Action queue bass helper",
                "tags": ["bass", "arrangement"],
                "style": "synth pop",
                "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
            },
        )
        reference_status, _reference = request_json(
            server,
            "POST",
            "/api/references/import",
            {
                "reference_type": "style_note",
                "filename": "bass.md",
                "title": "Action queue bass arrangement",
                "tags": ["bass"],
                "content_base64": "YmFzcyBhcnJhbmdlbWVudCBjb250ZXh0",
            },
        )
        _index_status, _index = request_json(server, "POST", "/api/library/rebuild", {})
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints",
            {"name": "Action Queue Sprint", "task_ids": [first_task_id, second_task_id], "settings": {"provider_candidate_count": 2}},
        )
        sprint_id = created["sprint"]["sprint_id"]
        queue_status, queue_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        queue = queue_data["queue"]
        queue_id = queue["queue_id"]
        local_item_id = _item_id(queue, "generate_local_candidates")
        context_item_id = _item_id(queue, "save_recommended_context_pack")
        list_status, listed = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}")
        local_run_status, local_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": [context_item_id, local_item_id]})
        refreshed_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
        provider_queue_status, provider_queue = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": False})
        provider_queue_id = provider_queue["queue"]["queue_id"]
        provider_item_id = _item_id(provider_queue["queue"], "generate_provider_candidates")
        provider_default_status, provider_default = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}/run", {"item_ids": [provider_item_id]})
        provider_run_status, provider_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}/run", {"item_ids": [provider_item_id], "include_provider": True})
        decision_path = Path(".musicforge") / "projects" / project_id / "review-tasks" / first_task_id / "decision-report.json"
        if decision_path.exists():
            decision_path.unlink()
        decision_queue_status, decision_queue = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        decision_queue_id = decision_queue["queue"]["queue_id"]
        decision_item_id = _item_id(decision_queue["queue"], "refresh_decision_report")
        decision_run_status, decision_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{decision_queue_id}/run", {"item_ids": [decision_item_id]})
        manual_queue_status, manual_queue = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        manual_items = [item for item in manual_queue["queue"]["items"] if item["action"] == "manual_apply_candidate"]
        manual_run_status, manual_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{manual_queue['queue']['queue_id']}/run", {"item_ids": [manual_items[0]["item_id"]] if manual_items else []})
        provider_candidate_id = provider_run["results"][0]["result"]["created_candidate_ids"][0]
        apply_status, applied = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{first_task_id}/candidates/{provider_candidate_id}/apply", {"version_name": "Action Queue Candidate"})
        job = wait_for_job(server, applied["job"]["job_id"])
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={applied['version']['version_id']}")
        usage_status, usage = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        metadata = json.loads((Path(job["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
        serialized = json.dumps({"queue": queue_data, "run": provider_run, "metadata": metadata, "compare": compare, "export": project_export, "usage": usage}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert provider_status == 200
    assert asset_status == 201
    assert reference_status == 201
    assert create_status == 201
    assert queue_status == 201
    assert list_status == 200
    assert listed["summary"]["queue_count"] == 1
    assert detail_status == 200
    assert detail["events"][0]["event"] == "queue_created"
    assert provider_default_status == 200
    assert provider_default["results"][0]["status"] == "skipped"
    assert provider_default["queue"]["status"] == "pending"
    assert _queue_item(provider_default["queue"], provider_item_id)["status"] == "pending"
    assert local_run_status == 200
    assert any(result["status"] == "completed" for result in local_run["results"])
    assert any(result.get("result", {}).get("context_pack_id") for result in local_run["results"])
    assert local_run["summary"]["counts"]["local_candidate_count"] >= 1
    assert refreshed_status == 200
    assert refreshed["summary"]["top_recommendation"]["action"] in {"generate_provider", "refresh_decision_report", "apply_ready_candidate"}
    assert provider_queue_status == 201
    assert provider_run_status == 200
    assert provider_run["results"][0]["status"] == "completed"
    assert provider_run["results"][0]["result"]["created_count"] >= 1
    assert decision_queue_status == 201
    assert decision_run_status == 200
    assert decision_run["results"][0]["status"] == "completed"
    assert decision_run["results"][0]["result"]["decision_report"]["requires_manual_apply"] is True
    assert manual_queue_status == 201
    assert manual_items
    assert manual_items[0]["status"] == "manual_required"
    assert manual_run_status == 200
    assert manual_run["queue"]["summary"]["manual_required"] >= 1
    assert apply_status == 202
    assert job["status"] == "completed"
    assert metadata["review_sprint_action_queue"]["primary"]["sprint_id"] == sprint_id
    assert compare_status == 200
    assert compare["right"]["edit"]["review_sprint_action_queue"]["primary"]["sprint_id"] == sprint_id
    assert export_status == 200
    assert project_export["review_sprints"][0]["action_queue_summary"]["queue_count"] >= 1
    assert project_export["versions"][1]["edit"]["review_sprint_action_queue"]["primary"]["sprint_id"] == sprint_id
    assert usage_status == 200
    assert any(record["operation"] == "review_sprint_action_provider_candidates" for record in usage["records"])
    assert "sk-secret-value" not in serialized
    assert "api_key" not in serialized
    assert "C:\\Users" not in serialized


def test_review_sprint_action_queue_blocks_stale_recommendation_and_context_refs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, _second_task_id = _create_two_review_tasks(server)
        asset_status, asset = request_json(
            server,
            "POST",
            "/api/assets",
            {
                "asset_type": "bass_pattern",
                "name": "Stale action queue bass",
                "tags": ["bass"],
                "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
            },
        )
        _index_status, _index = request_json(server, "POST", "/api/library/rebuild", {})
        create_status, created = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]})
        sprint_id = created["sprint"]["sprint_id"]
        queue_status, queue_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        queue_id = queue_data["queue"]["queue_id"]
        local_item_id = _item_id(queue_data["queue"], "generate_local_candidates")
        report_path = Path(".musicforge") / "projects" / project_id / "review-sprints" / sprint_id / "recommendation-report.json"
        report = read_json(report_path)
        report["created_at"] = "2026-05-14T01:00:00+00:00"
        write_json(report_path, report)
        stale_status, stale = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": [local_item_id]})

        context_queue_status, context_queue = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        context_queue_id = context_queue["queue"]["queue_id"]
        context_item_id = _item_id(context_queue["queue"], "save_recommended_context_pack")
        asset_path = Path(".musicforge") / "assets" / asset["asset"]["asset_id"] / "asset.json"
        asset_doc = read_json(asset_path)
        asset_doc["hidden"] = True
        write_json(asset_path, asset_doc)
        context_status, context_run = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{context_queue_id}/run", {"item_ids": [context_item_id]})
    finally:
        stop_test_server(server)

    assert asset_status == 201
    assert create_status == 201
    assert queue_status == 201
    assert stale_status == 200
    assert stale["results"][0]["status"] == "blocked"
    assert "Recommendation Report changed" in stale["results"][0]["error"]
    assert context_queue_status == 201
    assert context_status == 200
    assert context_run["results"][0]["status"] == "blocked"
    assert "stale" in context_run["results"][0]["error"]


def _item_id(queue: dict, action: str) -> str:
    for item in queue["items"]:
        if item["action"] == action:
            return item["item_id"]
    raise AssertionError(f"missing action {action}")


def _queue_item(queue: dict, item_id: str) -> dict:
    for item in queue["items"]:
        if item["item_id"] == item_id:
            return item
    raise AssertionError(f"missing item {item_id}")
