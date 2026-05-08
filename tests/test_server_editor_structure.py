from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_edits import create_project_version, request_json, start_test_server, stop_test_server


def test_project_editor_structure_preview_apply_history_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = create_project_version(server)
        parent_plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        parent_before = parent_plan_path.read_bytes()
        state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {
                "patch": {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "label": "duplicate chorus and add pad",
                    "operations": [
                        {"op": "duplicate_section", "section_id": "section-003", "name": "chorus 2", "copy_notes": True, "after_section_id": "section-003"},
                        {"op": "resize_section", "section_id": "section-002", "bars": 4, "note_policy": "crop"},
                        {"op": "add_track", "name": "pad", "instrument": "warm pad"},
                        {"op": "duplicate_track", "track_id": "track-001", "name": "counter melody", "transpose": 12},
                    ],
                }
            },
        )
        preview_id = preview_data["preview"]["preview_id"]
        history_status, history = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews")
        patch_status, patch_summary = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/patch")
        apply_status, apply_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/apply",
            {"version_name": "Structure Child", "change_summary": "structure edit"},
        )
        child_plan = json.loads((Path(apply_data["job"]["output_dir"]) / "data" / "song-plan.json").read_text(encoding="utf-8"))
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right=v002")
        cleanup_status, cleanup = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/cleanup", {"delete_unapplied_older_than_days": 0, "keep_latest": 5})
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}")
    finally:
        stop_test_server(server)

    assert state_status == 200
    assert preview_status == 201
    assert history_status == 200
    assert patch_status == 200
    assert apply_status == 201
    assert compare_status == 200
    assert cleanup_status == 200
    assert detail_status == 200
    assert parent_plan_path.read_bytes() == parent_before
    assert len(child_plan["sections"]) == len(state["sections"]) + 1
    assert len(child_plan["tracks"]) == len(state["tracks"]) + 2
    assert [section["start_bar"] for section in child_plan["sections"]] == [1, 5, 9, 17, 25]
    assert history["previews"][0]["preview_id"] == preview_id
    assert patch_summary["patch"]["operation_counts"]["duplicate_section"] == 1
    assert "operations" not in patch_summary["patch"]
    assert compare["summary"]["section_changes"] > 0
    assert compare["right"]["edit"]["summary"]["duplicate_section"] == 1
    assert cleanup["deleted_count"] == 0
    assert detail["preview"]["status"] == "applied"


def test_project_editor_patch_summary_can_include_operations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {
                "patch": {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "operations": [{"op": "add_section", "name": "bridge", "bars": 4, "chords": ["Fmaj7", "G7"]}],
                }
            },
        )
        preview_id = preview_data["preview"]["preview_id"]
        patch_status, patch_summary = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/patch?include_operations=true")
    finally:
        stop_test_server(server)

    assert state_status == 200
    assert preview_status == 201
    assert patch_status == 200
    assert patch_summary["patch"]["operations"][0]["op"] == "add_section"
    assert patch_summary["patch"]["operations_text"][0].startswith("add_section")
