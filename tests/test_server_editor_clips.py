from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_edits import create_project_version, request_json, start_test_server, stop_test_server
from tests.test_server_reference_analysis import import_reference, tiny_midi


def create_clip_asset(server):
    return server.asset_store.create_asset(
        {
            "asset_type": "motif",
            "name": "Server Clip Motif",
            "key": "C",
            "tempo_bpm": 120,
            "duration_beats": 2,
            "content": {
                "kind": "motif",
                "notes": [
                    {"pitch": 72, "start_beat": 0, "duration_beats": 0.5, "velocity": 90},
                    {"pitch": 74, "start_beat": 0.5, "duration_beats": 0.5, "velocity": 88},
                ],
            },
        },
        now="2026-05-11T00:00:00+00:00",
    )


def test_editor_clips_api_lists_assets_and_project_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        asset = create_clip_asset(server)
        status, data = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-clips")
    finally:
        stop_test_server(server)

    assert status == 200
    assert any(item["source_type"] == "asset" and item["source_id"] == asset.asset_id for item in data["clips"])
    assert any(item["source_type"] == "project_version_section" for item in data["clips"])
    assert data["limits"]["max_notes"] == 128


def test_editor_clip_draft_can_preview_and_apply_with_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        asset = create_clip_asset(server)
        clips_status, clips = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-clips")
        clip = next(item for item in clips["clips"] if item["source_type"] == "asset" and item["source_id"] == asset.asset_id)
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-clip-draft",
            {
                "clip_ref": clip["clip_ref"],
                "target": {"track_id": "track-001", "section_id": "section-001", "start_beat": 0},
                "options": {"mode": "overlay", "transpose": 1, "velocity_scale": 1},
            },
        )
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {"patch": draft["patch"], "render_midi": True},
        )
        preview_id = preview_data["preview"]["preview_id"]
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/apply",
            {"version_name": "Clip Child"},
        )
        metadata = json.loads((Path(applied["job"]["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right=v002")
        export_status, exported = request_json(server, "GET", f"/api/projects/{project_id}/export")
    finally:
        stop_test_server(server)

    derived = [note for lane in draft["draft_view"]["lanes"] for note in lane["notes"] if str(note["note_id"]).startswith("derived-note-")]
    assert clips_status == 200
    assert draft_status == 200
    assert len(draft["patch"]["operations"]) == 2
    assert draft["patch"]["metadata"]["clip_inserts"][0]["source_id"] == asset.asset_id
    assert len(derived) >= 2
    assert preview_status == 201
    assert apply_status == 201
    assert metadata["edit_type"] == "visual_editor_clip_insert"
    assert metadata["clip_inserts"][0]["source_id"] == asset.asset_id
    assert compare_status == 200
    assert compare["right"]["edit"]["clip_inserts"][0]["source_id"] == asset.asset_id
    assert export_status == 200
    assert exported["versions"][1]["edit"]["clip_inserts"][0]["source_id"] == asset.asset_id


def test_editor_clip_draft_rejects_stale_asset_ref(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        asset = create_clip_asset(server)
        status, data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-clip-draft",
            {
                "clip_ref": {"source_type": "asset", "asset_id": asset.asset_id, "source_hash": "stale"},
                "target": {"track_id": "track-001", "section_id": "section-001"},
            },
        )
    finally:
        stop_test_server(server)

    assert status == 409
    assert "stale" in data["error"].lower()


def test_editor_clip_draft_accepts_reference_midi_slice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        reference = import_reference(server, "midi", "seed.mid", tiny_midi())
        request_json(server, "POST", f"/api/references/{reference['reference_id']}/analyze")
        slice_status, slices = request_json(server, "POST", f"/api/references/{reference['reference_id']}/slices")
        slice_id = slices["manifest"]["slices"][0]["slice_id"]
        clips_status, clips = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-clips")
        clip = next(item for item in clips["clips"] if item["source_type"] == "reference_slice" and item["slice_id"] == slice_id)
        draft_status, draft = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-clip-draft",
            {
                "clip_ref": clip["clip_ref"],
                "target": {"track_id": "track-001", "section_id": "section-001", "start_beat": 0},
                "options": {"mode": "replace_range"},
            },
        )
    finally:
        stop_test_server(server)

    assert slice_status == 200
    assert clips_status == 200
    assert draft_status == 200
    assert draft["clip_summary"]["source_type"] == "reference_slice"
    assert draft["patch"]["metadata"]["clip_inserts"][0]["slice_id"] == slice_id
