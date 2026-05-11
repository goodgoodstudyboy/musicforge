from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_editor_audition import _create_preview
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _create_audition(server):
    project_id, preview_id = _create_preview(server)
    status, created = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
        {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-001"]},
    )
    assert status == 201
    return project_id, preview_id, created["audition"]["audition_id"]


def test_audition_review_api_updates_board_and_sanitizes_notes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _create_audition(server)
        review_status, review = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review",
            {
                "rating": 5,
                "status": "keep",
                "favorite": True,
                "notes": r"great hook api_key=sk-secret-value C:\Users\demo\song.wav",
                "tags": ["hook", "winner"],
            },
        )
        marker_status, marker = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
            {"beat": 1, "kind": "hook", "label": "main hook sk-secret-value"},
        )
        board_status, board = request_json(server, "GET", f"/api/projects/{project_id}/audition-reviews?favorite=true&min_rating=4&sort=rating")
        preview_board_status, preview_board = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/audition-reviews")
    finally:
        stop_test_server(server)

    serialized = json.dumps({"review": review, "marker": marker, "board": board}, ensure_ascii=False)
    assert review_status == 200
    assert marker_status == 201
    assert board_status == 200
    assert preview_board_status == 200
    assert board["summary"]["audition_count"] == 1
    assert board["summary"]["favorite_count"] == 1
    assert board["summary"]["marker_count"] == 1
    assert preview_board["auditions"][0]["review"]["rating"] == 5
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_audition_marker_update_delete_and_bounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _create_audition(server)
        invalid_status, invalid = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
            {"beat": 999, "kind": "issue"},
        )
        marker_status, marker = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
            {"beat": 1, "kind": "issue", "label": "fix bass"},
        )
        marker_id = marker["marker"]["marker_id"]
        update_status, updated = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers/{marker_id}",
            {"kind": "fix", "severity": "warning"},
        )
        delete_status, deleted = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers/{marker_id}/delete",
        )
    finally:
        stop_test_server(server)

    assert invalid_status == 400
    assert "duration" in invalid["error"]
    assert marker_status == 201
    assert update_status == 200
    assert updated["marker"]["kind"] == "fix"
    assert delete_status == 200
    assert deleted["audition"]["review"]["markers"] == []


def test_audition_create_asset_api_records_safe_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _create_audition(server)
        asset_status, asset_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/create-asset",
            {"asset_type": "motif", "track_id": "track-001", "name": "Audition Hook", "tags": ["audition"], "description": "saved from review"},
        )
        board_status, board = request_json(server, "GET", f"/api/projects/{project_id}/audition-reviews")
        asset_path = Path(".musicforge") / "assets" / asset_data["asset"]["asset_id"] / "asset.json"
    finally:
        stop_test_server(server)

    assert asset_status == 201
    assert asset_data["asset"]["source"]["source_type"] == "editor_audition"
    assert asset_data["asset"]["content"]["notes"]
    assert asset_path.exists()
    assert board_status == 200
    assert board["summary"]["asset_count"] == 1
    assert board["auditions"][0]["review"]["last_asset_id"] == asset_data["asset"]["asset_id"]
