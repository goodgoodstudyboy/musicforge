from __future__ import annotations

from pathlib import Path

from tests.test_server_edits import create_project_version, request_json, start_test_server, stop_test_server


def test_project_editor_view_and_draft_do_not_create_preview(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        view_status, view = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-view")
        note_id = state["tracks"][0]["notes"][0]["note_id"]
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-draft",
            {
                "include_view": True,
                "include_diff": True,
                "patch": {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "label": "draft only",
                    "operations": [
                        {"op": "resize_section", "section_id": "section-002", "bars": 4, "note_policy": "crop"},
                        {"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 77}},
                        {"op": "move_notes", "track_id": "track-001", "note_ids": [note_id], "delta_beats": 0.5},
                    ],
                },
            },
        )
        history_status, history = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews")
    finally:
        stop_test_server(server)

    assert state_status == 200
    assert view_status == 200
    assert view["view"]["lanes"][0]["notes"][0]["section_id"] == "section-001"
    assert draft_status == 200
    assert draft["operation_count"] == 3
    assert draft["view"]["lanes"][0]["notes"]
    assert draft["diff"]["notes"]["changed"] == 1
    assert draft["diff"]["notes"]["moved"] == 1
    assert draft["validator"]["status"] == "passed"
    assert history_status == 200
    assert history["previews"] == []
    assert not Path(".musicforge", "projects", project_id, "editor-previews").exists()
    assert not list(Path("runs").glob("*draft*"))


def test_project_editor_draft_errors_are_typed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        stale_status, stale = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-draft",
            {"patch": {"schema_version": 1, "base_plan_hash": "bad", "operations": [{"op": "set_section_lyrics", "section_id": "section-001", "lyrics": "x"}]}},
        )
        bad_status, bad = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-draft",
            {"patch": {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "operations": [{"op": "set_section_chords", "section_id": "section-001", "chords": ["Hmaj7"]}]}},
        )
    finally:
        stop_test_server(server)

    assert state_status == 200
    assert stale_status == 409
    assert "stale" in stale["error"].lower()
    assert bad_status == 400
    assert "Unsupported chord" in bad["error"]


def test_project_editor_draft_allows_continued_editing_with_visible_base_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        _state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        first_status, first = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-draft",
            {
                "include_view": True,
                "include_diff": True,
                "patch": {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "operations": [{"op": "delete_section", "section_id": "section-001", "note_policy": "shift_left"}],
                },
            },
        )
        visible_section = first["view"]["sections"][0]
        second_status, second = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-draft",
            {
                "include_view": True,
                "include_diff": True,
                "patch": {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "operations": [
                        {"op": "delete_section", "section_id": "section-001", "note_policy": "shift_left"},
                        {"op": "resize_section", "section_id": visible_section["section_id"], "bars": 4, "note_policy": "crop"},
                    ],
                },
            },
        )
    finally:
        stop_test_server(server)

    assert first_status == 200
    assert visible_section["name"] == "verse"
    assert visible_section["section_id"] == "section-002"
    assert second_status == 200
    assert "verse" in second["summary"]["changed_sections"]


def test_project_editor_draft_track_view_keeps_visible_base_track_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        _state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-draft",
            {
                "include_view": True,
                "include_diff": True,
                "patch": {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "operations": [
                        {"op": "duplicate_track", "track_id": "track-001", "name": "melody copy"},
                        {"op": "delete_track", "track_id": "track-001"},
                    ],
                },
            },
        )
    finally:
        stop_test_server(server)

    assert status == 200
    assert draft["view"]["tracks"][0]["name"] == "chords"
    assert draft["view"]["tracks"][0]["track_id"] == "track-002"
    assert draft["view"]["tracks"][-1]["name"] == "melody copy"
    assert draft["view"]["tracks"][-1]["track_id"].startswith("derived-track-")
