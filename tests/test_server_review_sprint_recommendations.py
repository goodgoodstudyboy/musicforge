from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_review_sprints import _create_two_review_tasks


def test_review_sprint_recommendation_api_refresh_and_save_context_pack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, second_task_id = _create_two_review_tasks(server)
        asset_status, asset_data = request_json(
            server,
            "POST",
            "/api/assets",
            {
                "asset_type": "bass_pattern",
                "name": "Sprint bass helper",
                "tags": ["bass", "arrangement"],
                "style": "synth pop",
                "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
            },
        )
        reference_status, reference_data = request_json(
            server,
            "POST",
            "/api/references/import",
            {
                "reference_type": "style_note",
                "filename": "bass.md",
                "title": "Sprint bass arrangement reference",
                "tags": ["bass"],
                "content_base64": "YmFzcyBhcnJhbmdlbWVudCBjb250ZXh0",
            },
        )
        index_status, _index = request_json(server, "POST", "/api/library/rebuild", {})
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints",
            {"name": "Recommendation Sprint", "task_ids": [first_task_id, second_task_id]},
        )
        sprint_id = created["sprint"]["sprint_id"]
        detail_before_status, detail_before = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
        get_status, get_data = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations")
        refresh_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
        detail_after_status, detail_after = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
        pack_status, pack_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/{first_task_id}/context-pack",
            {"name": "Saved Recommendation Context"},
        )
        pack_id = pack_data["context_pack"]["pack_id"]
        apply_status, applied_pack = request_json(server, "POST", f"/api/context-packs/{pack_id}/apply-preview", {})
        serialized = json.dumps({"get": get_data, "pack": pack_data}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert asset_status == 201
    assert reference_status == 201
    assert index_status == 200
    assert create_status == 201
    assert detail_before_status == 200
    assert sum(len(item["candidates"]) for item in detail_before["tasks"]) == 0
    assert get_status == 200
    assert get_data["recommendation_report"]["recommended_order"]
    assert get_data["summary"]["top_recommendation"]["action"] in {"generate_local", "generate_provider", "inspect_conflict"}
    assert refresh_status == 200
    assert refreshed["recommendation_report"]["created_at"]
    assert (Path(".musicforge") / "projects" / project_id / "review-sprints" / sprint_id / "recommendation-report.json").exists()
    assert detail_after_status == 200
    assert sum(len(item["candidates"]) for item in detail_after["tasks"]) == 0
    assert pack_status == 201
    assert pack_data["context_pack"]["created_from"]["source_type"] == "review_sprint_recommendation"
    assert pack_data["context_pack"]["created_from"]["task_id"] == first_task_id
    assert apply_status == 200
    assert applied_pack["asset_refs"][0]["asset_id"] == asset_data["asset"]["asset_id"]
    assert applied_pack["reference_refs"][0]["reference_id"] == reference_data["reference"]["reference_id"]
    assert "sk-secret-value" not in serialized
    assert "api_key" not in serialized
    assert "C:\\Users" not in serialized


def test_review_sprint_recommendation_context_pack_rejects_stale_refs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, _second_task_id = _create_two_review_tasks(server)
        asset_status, asset_data = request_json(
            server,
            "POST",
            "/api/assets",
            {
                "asset_type": "bass_pattern",
                "name": "Stale sprint bass",
                "tags": ["bass"],
                "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
            },
        )
        assert asset_status == 201
        _index_status, _index = request_json(server, "POST", "/api/library/rebuild", {})
        create_status, created = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]})
        sprint_id = created["sprint"]["sprint_id"]
        refresh_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
        asset_path = Path(".musicforge") / "assets" / asset_data["asset"]["asset_id"] / "asset.json"
        asset_doc = json.loads(asset_path.read_text(encoding="utf-8"))
        asset_doc["hidden"] = True
        asset_path.write_text(json.dumps(asset_doc), encoding="utf-8")
        pack_status, pack_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/{first_task_id}/context-pack", {})
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert refresh_status == 200
    assert refreshed["summary"]["context_recommendation_count"] >= 1
    assert pack_status == 409
    assert "stale" in pack_data["error"]
