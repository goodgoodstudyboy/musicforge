from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_editor_audition import _create_preview
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job


def _reviewed_audition(server, *, notes: str = "bass 太满, chorus 更强", status: str = "needs_fix", rating: int = 4):
    project_id, preview_id = _create_preview(server)
    create_status, created = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
        {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-003"]},
    )
    assert create_status == 201
    audition_id = created["audition"]["audition_id"]
    review_status, _review = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review",
        {"rating": rating, "status": status, "favorite": rating >= 4, "notes": notes, "tags": ["review"]},
    )
    assert review_status == 200
    marker_status, _marker = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
        {"beat": 1, "kind": "fix" if status == "needs_fix" else "note", "label": "fix point"},
    )
    assert marker_status == 201
    return project_id, preview_id, audition_id


def test_review_edit_preview_and_create_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _reviewed_audition(server)
        preview_status, preview = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-edit-preview",
            {},
        )
        edit_status, edit = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-edit",
            {"version_name": "Review Edit Child", "version_note": "review-driven"},
        )
        job = wait_for_job(server, edit["job"]["job_id"])
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/versions/{edit['version']['version_id']}/edit")
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={edit['version']['version_id']}")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        metadata = json.loads((Path(job["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
    finally:
        stop_test_server(server)

    assert preview_status == 201
    assert preview["review_edit"]["intents"]
    assert preview["summary"]["intent_count"] >= 1
    assert edit_status == 202
    assert edit["version"]["variant_type"] in {"track_edit", "section_edit", "melody_edit", "arrangement_edit"}
    assert job["status"] == "completed"
    assert detail_status == 200
    assert detail["edit"]["edit_source"] == "audition_review"
    assert compare_status == 200
    assert compare["right"]["edit"]["review_edit"]["audition_id"] == audition_id
    assert export_status == 200
    assert project_export["versions"][1]["edit"]["review_edit"]["audition_id"] == audition_id
    assert metadata["edit_source"] == "audition_review"
    assert metadata["review_edit"]["audition_id"] == audition_id


def test_review_edit_rejected_review_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _reviewed_audition(server, notes="bad", status="reject", rating=1)
        status, error = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-edit-preview",
            {},
        )
    finally:
        stop_test_server(server)

    assert status == 409
    assert "rejected" in error["error"]


def test_review_edit_override_validation_and_context_pack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _reviewed_audition(server)
        invalid_status, invalid = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-edit-preview",
            {"intent_overrides": [{"edit_type": "unknown"}]},
        )
        asset_status, asset_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/create-asset",
            {"asset_type": "motif", "track_id": "track-001", "name": "Review Hook"},
        )
        pack_status, pack_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/create-context-pack",
            {},
        )
    finally:
        stop_test_server(server)

    assert invalid_status == 400
    assert "edit_type" in invalid["error"]
    assert asset_status == 201
    assert pack_status == 201
    assert pack_data["context_pack"]["asset_refs"][0]["asset_id"] == asset_data["asset"]["asset_id"]
    assert pack_data["context_pack"]["created_from"]["source_type"] == "audition_review"


def test_provider_review_edit_preview_uses_mock_provider_without_creating_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id, audition_id = _reviewed_audition(server, notes="bass too busy, make chorus stronger")
        provider_status, _provider = request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main", "api_key": "sk-provider-secret"})
        status, data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/provider-review-edit-preview",
            {},
        )
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
        serialized = json.dumps(data, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert provider_status == 200
    assert status == 201
    assert data["preview"]["template_id"] == "provider-review-edit-intent"
    assert data["preview"]["source"]["review_edit"]["audition_id"] == audition_id
    assert data["patch"]["operations"]
    assert detail_status == 200
    assert detail["project"]["version_count"] == 1
    assert "sk-provider-secret" not in serialized
