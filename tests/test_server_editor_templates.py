from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_edits import create_project_version, request_json, start_test_server, stop_test_server


def test_editor_template_api_create_map_draft_preview_apply_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/section-templates",
            {"section_id": "section-001", "name": "Intro Lift", "tags": ["intro", "lift"]},
        )
        template = created["template"]
        list_status, listed = request_json(server, "GET", "/api/editor-templates")
        mapping_status, mapping = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-template-mapping",
            {"source_ref": {"source_type": "section_template", "template_id": template["template_id"]}},
        )
        lane_mappings = [
            {
                "lane_id": item["lane_id"],
                "target_track_id": item["suggested_track_id"],
                "mode": "overlay",
            }
            for item in mapping["suggestions"]
            if item.get("suggested_track_id")
        ][:2]
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-multitrack-clip-draft",
            {
                "source_ref": {"source_type": "section_template", "template_id": template["template_id"]},
                "target": {"section_id": "section-002", "start_beat": 16},
                "lane_mappings": lane_mappings,
                "options": {"mode": "overlay", "transpose": 0, "velocity_scale": 1},
            },
        )
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {"patch": draft["combined_patch"], "render_midi": True},
        )
        preview_id = preview_data["preview"]["preview_id"]
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/apply",
            {"version_name": "Template Child"},
        )
        metadata = json.loads((Path(applied["job"]["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right=v002")
        export_status, exported = request_json(server, "GET", f"/api/projects/{project_id}/export")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert list_status == 200
    assert listed["section_templates"][0]["template_id"] == template["template_id"]
    assert mapping_status == 200
    assert len(mapping["suggestions"]) >= 2
    assert draft_status == 200
    assert draft["template_summary"]["source_type"] == "section_template"
    assert draft["patch"]["metadata"]["template_inserts"][0]["template_group_id"].startswith("template-")
    assert len({op["track_id"] for op in draft["patch"]["operations"] if op["op"] == "add_note"}) >= 2
    derived = [note for lane in draft["draft_view"]["lanes"] for note in lane["notes"] if str(note["note_id"]).startswith("derived-note-")]
    assert len(derived) >= 2
    assert preview_status == 201
    assert apply_status == 201
    assert metadata["edit_type"] == "visual_editor_template_insert"
    assert metadata["template_inserts"][0]["source_id"] == template["template_id"]
    assert compare_status == 200
    assert compare["right"]["edit"]["template_inserts"][0]["source_id"] == template["template_id"]
    assert export_status == 200
    assert exported["versions"][1]["edit"]["template_inserts"][0]["source_id"] == template["template_id"]


def test_editor_multitrack_template_replace_range_uses_current_patch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        _create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/section-templates",
            {"section_id": "section-001", "name": "Intro Lift", "include_roles": ["melody"]},
        )
        state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        note_id = state["tracks"][0]["notes"][0]["note_id"]
        current_patch = {
            "schema_version": 1,
            "base_plan_hash": state["base_plan_hash"],
            "operations": [{"op": "delete_notes", "track_id": "track-001", "note_ids": [note_id]}],
        }
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-multitrack-clip-draft",
            {
                "source_ref": {"source_type": "section_template", "template_id": created["template"]["template_id"]},
                "current_patch": current_patch,
                "target": {"section_id": "section-001", "start_beat": 0},
                "lane_mappings": [{"lane_id": "lane-001", "target_track_id": "track-001", "mode": "replace_range"}],
            },
        )
        preview_status, _preview = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {"patch": draft["combined_patch"], "render_midi": False},
        )
    finally:
        stop_test_server(server)

    assert state_status == 200
    assert draft_status == 200
    assert all(note_id not in operation.get("note_ids", []) for operation in draft["patch"]["operations"])
    assert preview_status == 201


def test_editor_template_api_rejects_hidden_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        _status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/section-templates",
            {"section_id": "section-001", "name": "Hidden Template"},
        )
        hide_status, _hidden = request_json(server, "POST", f"/api/editor-templates/sections/{created['template']['template_id']}/hide")
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-multitrack-clip-draft",
            {
                "source_ref": {"source_type": "section_template", "template_id": created["template"]["template_id"]},
                "target": {"section_id": "section-001", "start_beat": 0},
                "lane_mappings": [{"lane_id": "lane-001", "target_track_id": "track-001", "mode": "overlay"}],
            },
        )
    finally:
        stop_test_server(server)

    assert hide_status == 200
    assert draft_status == 409
    assert "hidden" in draft["error"].lower()


def test_editor_multitrack_template_rejects_unknown_lane_id_with_clear_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        _status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/section-templates",
            {"section_id": "section-001", "name": "Lane Guard"},
        )
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-multitrack-clip-draft",
            {
                "source_ref": {"source_type": "section_template", "template_id": created["template"]["template_id"]},
                "target": {"section_id": "section-001", "start_beat": 0},
                "lane_mappings": [{"lane_id": "lane-missing", "target_track_id": "track-001", "mode": "overlay"}],
            },
        )
    finally:
        stop_test_server(server)

    assert draft_status == 400
    assert draft["error"] == "Unknown template lane_id: lane-missing."
