from __future__ import annotations

import json
from pathlib import Path

from song_agent.renderers.audio import save_renderer_config_from_dict
import song_agent.domains.studio.editor_audition as editor_audition_module
import song_agent.server as server_module

from tests.test_server_edits import create_project_version, request_bytes, request_json, start_test_server, stop_test_server


def _create_preview(server):
    project_id, _parent_job = create_project_version(server)
    state_status, state = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
    assert state_status == 200
    note_id = state["tracks"][0]["notes"][0]["note_id"]
    preview_status, preview_data = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions/v001/editor-preview",
        {
            "patch": {
                "schema_version": 1,
                "base_plan_hash": state["base_plan_hash"],
                "label": "Audition patch",
                "operations": [
                    {"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 99}},
                ],
            },
            "render_midi": True,
        },
    )
    assert preview_status == 201
    return project_id, preview_data["preview"]["preview_id"]


def test_editor_audition_api_creates_lists_and_downloads_midi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
            {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-001"]},
        )
        audition_id = created["audition"]["audition_id"]
        list_status, listing = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}")
        midi_status, midi = request_bytes(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/midi")
        audio_status, audio = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/audio")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert created["audition"]["note_count"] > 0
    assert list_status == 200
    assert listing["auditions"][0]["audition_id"] == audition_id
    assert detail_status == 200
    assert detail["audition"]["range"]["mode"] == "section"
    assert midi_status == 200
    assert midi.startswith(b"MThd")
    assert audio_status == 404
    assert b"File not found" in json.dumps(audio).encode()


def test_editor_audition_render_audio_uses_fake_renderer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sf2 = tmp_path / "font.sf2"
    sf2.write_bytes(b"sf2")
    save_renderer_config_from_dict({"soundfont_path": str(sf2)})

    def fake_render_audio(midi_path, wav_path, config, **kwargs):
        wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
        return wav_path

    monkeypatch.setattr(editor_audition_module, "render_audio", fake_render_audio)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        _create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
            {"source": "parent", "range": {"mode": "full_song"}, "track_mode": "all"},
        )
        audition_id = created["audition"]["audition_id"]
        render_status, rendered = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/render-audio")
        audio_status, audio = request_bytes(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/audio")
    finally:
        stop_test_server(server)

    assert render_status == 200
    assert rendered["audition"]["audio"]["status"] == "completed"
    assert audio_status == 200
    assert audio.startswith(b"RIFF")


def test_editor_audition_renderer_missing_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        _create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
            {"source": "preview", "range": {"mode": "full_song"}, "track_mode": "all"},
        )
        audition_id = created["audition"]["audition_id"]
        render_status, rendered = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/render-audio")
    finally:
        stop_test_server(server)

    assert render_status == 400
    assert "soundfont_path is required" in rendered["error"]


def test_editor_audition_delete_removes_downloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        _create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
            {"source": "preview", "range": {"mode": "full_song"}, "track_mode": "solo", "track_ids": ["track-001"]},
        )
        audition_id = created["audition"]["audition_id"]
        delete_status, deleted = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/delete")
        midi_status, _midi = request_bytes(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/midi")
    finally:
        stop_test_server(server)

    assert delete_status == 200
    assert deleted["deleted"] is True
    assert midi_status == 404


def test_preview_audition_ignores_polluted_preview_song_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        polluted_path = Path(".musicforge") / "projects" / project_id / "editor-previews" / preview_id / "song-plan.json"
        polluted = json.loads(polluted_path.read_text(encoding="utf-8"))
        polluted["tracks"][0]["notes"] = []
        polluted_path.write_text(json.dumps(polluted), encoding="utf-8")
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
            {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-001"]},
        )
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert created["audition"]["note_count"] > 0


def test_preview_and_parent_audio_routes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sf2 = tmp_path / "font.sf2"
    sf2.write_bytes(b"sf2")
    save_renderer_config_from_dict({"soundfont_path": str(sf2)})

    def fake_server_render_audio(midi_path, wav_path, config, **kwargs):
        wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
        return wav_path

    monkeypatch.setattr(server_module, "render_audio", fake_server_render_audio)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        preview_render_status, preview_rendered = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/render-audio")
        preview_audio_status, preview_audio = request_bytes(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}/audio")
        parent_render_status, parent_rendered = request_json(server, "POST", f"/api/projects/{project_id}/versions/v001/render-audio")
        parent_audio_status, parent_audio = request_bytes(server, "GET", f"/api/projects/{project_id}/versions/v001/audio")
    finally:
        stop_test_server(server)

    assert preview_render_status == 200
    assert preview_rendered["preview"]["audio_status"] == "completed"
    assert preview_audio_status == 200
    assert preview_audio.startswith(b"RIFF")
    assert parent_render_status == 200
    assert parent_rendered["audio_status"] == "completed"
    assert parent_audio_status == 200
    assert parent_audio.startswith(b"RIFF")


def test_preview_audio_recomputes_plan_and_midi_before_render(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sf2 = tmp_path / "font.sf2"
    sf2.write_bytes(b"sf2")
    save_renderer_config_from_dict({"soundfont_path": str(sf2)})
    seen = {}

    def fake_server_render_audio(midi_path, wav_path, config, **kwargs):
        data = midi_path.read_bytes()
        seen["midi"] = data
        wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
        return wav_path

    monkeypatch.setattr(server_module, "render_audio", fake_server_render_audio)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        preview_dir = Path(".musicforge") / "projects" / project_id / "editor-previews" / preview_id
        polluted_plan = json.loads((preview_dir / "song-plan.json").read_text(encoding="utf-8"))
        polluted_plan["tracks"][0]["instrument"] = "polluted preview instrument"
        polluted_plan["tracks"][0]["notes"] = []
        (preview_dir / "song-plan.json").write_text(json.dumps(polluted_plan), encoding="utf-8")
        (preview_dir / "song.mid").write_bytes(b"MThd polluted midi")
        render_status, rendered = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/render-audio")
        recomputed_plan = json.loads((preview_dir / "song-plan.json").read_text(encoding="utf-8"))
    finally:
        stop_test_server(server)

    assert render_status == 200
    assert rendered["preview"]["audio_status"] == "completed"
    assert seen["midi"].startswith(b"MThd")
    assert seen["midi"] != b"MThd polluted midi"
    assert recomputed_plan["tracks"][0]["instrument"] != "polluted preview instrument"
    assert recomputed_plan["tracks"][0]["notes"]


def test_preview_audio_failure_records_sanitized_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sf2 = tmp_path / "font.sf2"
    sf2.write_bytes(b"sf2")
    save_renderer_config_from_dict({"soundfont_path": str(sf2)})

    def failing_render_audio(midi_path, wav_path, config, **kwargs):
        raise server_module.RendererError(f"failed at {tmp_path} with sk-secret-value")

    monkeypatch.setattr(server_module, "render_audio", failing_render_audio)
    server = start_test_server()
    try:
        project_id, preview_id = _create_preview(server)
        render_status, rendered = request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/render-audio")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview_id}")
    finally:
        stop_test_server(server)

    assert render_status == 400
    assert detail_status == 200
    assert detail["preview"]["audio_status"] == "failed"
    assert "sk-secret-value" not in detail["preview"]["audio_error"]
    assert str(tmp_path) not in detail["preview"]["audio_error"]
