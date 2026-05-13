from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_editor_audition import _create_preview
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job


def _create_task_on_preview(server, project_id: str, preview_id: str, *, track_ids: list[str], notes: str, marker_beat: float = 1.0) -> str:
    create_status, created = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
        {
            "source": "preview",
            "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0},
            "track_mode": "solo",
            "track_ids": track_ids,
        },
    )
    assert create_status == 201
    audition_id = created["audition"]["audition_id"]
    review_status, _review = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review",
        {"rating": 3, "status": "needs_fix", "notes": notes, "tags": ["sprint"]},
    )
    assert review_status == 200
    marker_status, _marker = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
        {"beat": marker_beat, "kind": "fix", "label": notes},
    )
    assert marker_status == 201
    task_status, task_data = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task",
        {},
    )
    assert task_status == 201
    return task_data["task"]["task_id"]


def _create_two_review_tasks(server) -> tuple[str, str, str]:
    project_id, preview_id = _create_preview(server)
    first = _create_task_on_preview(server, project_id, preview_id, track_ids=["track-003"], notes="bass too dense", marker_beat=1.0)
    second = _create_task_on_preview(server, project_id, preview_id, track_ids=["track-003"], notes="bass needs movement", marker_beat=2.0)
    return project_id, first, second


def test_review_sprint_api_batch_candidates_apply_refresh_and_close(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        provider_status, provider = request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
        project_id, first_task_id, second_task_id = _create_two_review_tasks(server)
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints",
            {
                "name": r"Sprint C:\Users\demo token=sk-secret-value",
                "description": "provider review sprint",
                "task_ids": [first_task_id, second_task_id],
                "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2},
            },
        )
        sprint_id = created["sprint"]["sprint_id"]
        list_status, listed = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints?include_archived=1")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
        conflicts_status, conflicts = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/conflicts")
        local_status, local = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-local-candidates",
            {"strategies": ["balanced"], "render_midi": True},
        )
        provider_candidates_status, provider_candidates = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-provider-candidates",
            {"candidate_count": 2, "render_midi": True},
        )
        provider_candidate_id = next(candidate["candidate_id"] for item in provider_candidates["tasks"] for candidate in item["candidates"] if item["task"]["task_id"] == first_task_id and candidate["candidate_type"] == "provider_review_patch")
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-tasks/{first_task_id}/candidates/{provider_candidate_id}/apply",
            {"version_name": "Sprint Provider Candidate"},
        )
        job = wait_for_job(server, applied["job"]["job_id"])
        refresh_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/refresh")
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={applied['version']['version_id']}")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        final_set_status, _final_set = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": applied["version"]["version_id"]})
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{project_id}/final-export")
        close_status, closed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close")
        closed_local_status, closed_local = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-local-candidates", {})
        usage_status, usage = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        metadata = json.loads((Path(job["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
        serialized = json.dumps({"created": created, "provider_candidates": provider_candidates, "metadata": metadata, "export": project_export, "final_export": final_export}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert provider_status == 200
    assert provider["config"]["api_key_set"] is True
    assert create_status == 201
    assert created["sprint"]["status"] == "open"
    assert created["summary"]["counts"]["blocking_conflict_count"] == 0
    assert created["summary"]["counts"]["conflict_count"] >= 1
    assert list_status == 200
    assert listed["summary"]["total"] == 1
    assert detail_status == 200
    assert len(detail["tasks"]) == 2
    assert conflicts_status == 200
    assert any(item["kind"] in {"same_section_track", "same_track", "nearby_markers"} for item in conflicts["conflict_report"]["conflicts"])
    assert local_status == 202
    assert local["created_count"] >= 2
    assert all(item["status"] in {"generated", "skipped"} for item in local["results"])
    assert provider_candidates_status == 202
    assert provider_candidates["created_count"] >= 4
    assert provider_candidates["summary"]["counts"]["provider_candidate_count"] >= 4
    assert provider_candidate_id
    assert apply_status == 202
    assert applied["candidate"]["candidate_type"] == "provider_review_patch"
    assert job["status"] == "completed"
    assert refresh_status == 200
    assert refreshed["summary"]["counts"]["applied"] == 1
    assert compare_status == 200
    assert compare["right"]["edit"]["review_sprint"]["primary"]["sprint_id"] == sprint_id
    assert export_status == 200
    assert project_export["review_sprints"][0]["sprint_id"] == sprint_id
    assert project_export["versions"][1]["edit"]["review_sprint"]["primary"]["sprint_id"] == sprint_id
    assert final_set_status == 200
    assert final_export_status == 200
    assert final_export["final_export"]["edit"]["review_sprint"]["primary"]["sprint_id"] == sprint_id
    assert final_export["final_export"]["review_sprint_summary"]["latest_sprint_id"] == sprint_id
    assert close_status == 200
    assert closed["sprint"]["status"] == "closed"
    assert closed_local_status == 409
    assert "closed" in closed_local["error"]
    assert usage_status == 200
    assert any(item["operation"] == "review_sprint_provider_candidates" for item in usage["records"])
    assert metadata["edit_source"] == "review_task_candidate"
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_review_sprint_membership_and_conflict_routes_validate_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, second_task_id = _create_two_review_tasks(server)
        create_status, created = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]})
        sprint_id = created["sprint"]["sprint_id"]
        duplicate_status, duplicate = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/tasks", {"task_ids": [first_task_id]})
        add_status, added = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/tasks", {"task_ids": [second_task_id]})
        reorder_status, reordered = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/tasks/reorder", {"task_ids": [second_task_id, first_task_id]})
        remove_status, removed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/tasks/remove", {"task_id": first_task_id})
        conflict_refresh_status, conflict_refresh = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/conflicts/refresh")
        archive_status, archived = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/archive")
        add_archived_status, add_archived = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/tasks", {"task_ids": [first_task_id]})
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert duplicate_status == 400
    assert "already contains" in duplicate["error"]
    assert add_status == 200
    assert len(added["tasks"]) == 2
    assert reorder_status == 200
    assert reordered["sprint"]["task_refs"][0]["task_id"] == second_task_id
    assert remove_status == 200
    assert [item["task"]["task_id"] for item in removed["tasks"]] == [second_task_id]
    assert conflict_refresh_status == 200
    assert conflict_refresh["conflict_report"]["sprint_id"] == sprint_id
    assert archive_status == 200
    assert archived["sprint"]["status"] == "archived"
    assert add_archived_status == 409
    assert "archived" in add_archived["error"]
