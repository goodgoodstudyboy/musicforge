from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.editor_templates import (
    EditorTemplateError,
    EditorTemplateStore,
    build_multitrack_clip_from_project_section,
    build_multitrack_clip_insert_patch,
    suggest_lane_mappings,
)
from song_agent.projectio import read_json
from song_agent.schemas.song import NoteEvent, SongPlan, SongSection, TrackPlan
from song_agent.song_editor import apply_editor_patch, build_editor_state, song_plan_hash
from song_agent.editor_view import build_editor_view_from_result
from tests.test_server_edits import create_project_version, start_test_server, stop_test_server


def template_plan() -> SongPlan:
    return SongPlan(
        title="Template Plan",
        key="C",
        tempo_bpm=120,
        meter="4/4",
        sections=[
            SongSection("intro", 1, 4, ["Cmaj7", "G7", "Am7", "Fmaj7"], "intro lyric"),
            SongSection("chorus", 5, 4, ["Fmaj7", "G7", "Cmaj7", "Am7"], "chorus lyric"),
        ],
        tracks=[
            TrackPlan("melody", "lead synth", [NoteEvent(72, 16, 1, 90), NoteEvent(74, 17, 1, 88)]),
            TrackPlan("chords", "electric piano", [NoteEvent(60, 16, 3, 70), NoteEvent(64, 16, 3, 70)]),
            TrackPlan("bass", "synth bass", [NoteEvent(36, 16, 1, 86), NoteEvent(38, 18, 1, 86)]),
        ],
    )


def test_extract_multitrack_clip_from_project_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = create_project_version(server)
        plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        original = read_json(plan_path)
        clip = build_multitrack_clip_from_project_section(
            project_store=server.project_store,
            project_id=project_id,
            version_id="v001",
            section_id="section-001",
        )
    finally:
        stop_test_server(server)

    assert clip.metadata["source_plan_hash"] == song_plan_hash(SongPlan.from_dict(original))
    assert clip.lanes
    assert len(clip.lanes) <= 8
    assert all(note.start_beat >= 0 for lane in clip.lanes for note in lane.notes)
    assert clip.summary()["note_count"] == sum(len(lane.notes) for lane in clip.lanes)


def test_section_and_track_template_store_persists_sanitized_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        store = EditorTemplateStore(tmp_path / ".musicforge" / "editor-templates")
        section = store.create_section_template_from_project_version(
            project_store=server.project_store,
            project_id=project_id,
            version_id="v001",
            section_id="section-001",
            payload={"name": "Hook api_key=sk-polluted-secret", "tags": ["hook"]},
            now="2026-05-11T00:00:00+00:00",
        )
        track = store.create_track_template_from_project_version(
            project_store=server.project_store,
            project_id=project_id,
            version_id="v001",
            track_id="track-001",
            payload={"name": "Lead", "range": {"start_beat": 0, "end_beat": 16}},
            now="2026-05-11T00:00:00+00:00",
        )
    finally:
        stop_test_server(server)

    assert section.template_id == "section-template-001"
    assert "sk-polluted-secret" not in section.to_dict()["name"]
    assert track.template_id == "track-template-001"
    assert store.read_section_template(section.template_id).clip is not None
    assert store.read_track_template(track.template_id).default_notes
    assert store.hide_template("section", section.template_id, True)["hidden"] is True
    assert store.list_section_templates() == []
    assert store.list_section_templates(include_hidden=True)[0].template_id == section.template_id


def test_multitrack_mapping_and_patch_insert_multiple_tracks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        clip = build_multitrack_clip_from_project_section(
            project_store=server.project_store,
            project_id=project_id,
            version_id="v001",
            section_id="section-001",
            include_roles=["melody", "chords"],
        )
        parent = SongPlan.from_dict(read_json(Path(server.project_store.get_project(project_id).versions[0].output_dir) / "data" / "song-plan.json"))
        state = build_editor_state(parent)
        suggestions = suggest_lane_mappings(clip, state)
        mappings = [
            {"lane_id": lane.lane_id, "target_track_id": suggestions[index]["suggested_track_id"], "mode": "overlay"}
            for index, lane in enumerate(clip.lanes)
            if suggestions[index]["suggested_track_id"]
        ]
        patch, summary, warnings = build_multitrack_clip_insert_patch(
            parent,
            clip,
            {
                "target": {"section_id": "section-002", "start_beat": 16},
                "lane_mappings": mappings,
                "options": {"transpose": 1, "velocity_scale": 1},
            },
        )
        result = apply_editor_patch(parent, patch)
    finally:
        stop_test_server(server)

    assert summary["lane_count"] >= 2
    assert not warnings
    assert patch["metadata"]["template_inserts"][0]["lane_count"] >= 2
    assert len({op["track_id"] for op in patch["operations"] if op["op"] == "add_note"}) >= 2
    assert result.summary["operation_counts"]["add_note"] >= 2


def test_multitrack_replace_range_uses_current_patch_and_ignores_derived_notes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        clip = build_multitrack_clip_from_project_section(
            project_store=server.project_store,
            project_id=project_id,
            version_id="v001",
            section_id="section-001",
            include_roles=["melody"],
        )
        parent = SongPlan.from_dict(read_json(Path(server.project_store.get_project(project_id).versions[0].output_dir) / "data" / "song-plan.json"))
        first_patch, _summary, _warnings = build_multitrack_clip_insert_patch(
            parent,
            clip,
            {
                "target": {"section_id": "section-001", "start_beat": 0},
                "lane_mappings": [{"lane_id": clip.lanes[0].lane_id, "target_track_id": "track-001", "mode": "overlay"}],
            },
        )
        first_result = apply_editor_patch(parent, first_patch)
        draft_state = build_editor_view_from_result(first_result)
        second_patch, _summary, _warnings = build_multitrack_clip_insert_patch(
            parent,
            clip,
            {
                "target": {"section_id": "section-001", "start_beat": 0},
                "lane_mappings": [{"lane_id": clip.lanes[0].lane_id, "target_track_id": "track-001", "mode": "replace_range"}],
            },
            draft_plan=first_result.plan,
            draft_state=draft_state,
        )
    finally:
        stop_test_server(server)

    deleted_ids = [note_id for operation in second_patch["operations"] for note_id in operation.get("note_ids", [])]
    assert deleted_ids
    assert all(not str(note_id).startswith("derived-note-") for note_id in deleted_ids)


def test_multitrack_insert_rejects_unknown_lane_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        clip = build_multitrack_clip_from_project_section(
            project_store=server.project_store,
            project_id=project_id,
            version_id="v001",
            section_id="section-001",
            include_roles=["melody"],
        )
        parent = SongPlan.from_dict(read_json(Path(server.project_store.get_project(project_id).versions[0].output_dir) / "data" / "song-plan.json"))
        with pytest.raises(EditorTemplateError, match="Unknown template lane_id: lane-missing"):
            build_multitrack_clip_insert_patch(
                parent,
                clip,
                {
                    "target": {"section_id": "section-001", "start_beat": 0},
                    "lane_mappings": [{"lane_id": "lane-missing", "target_track_id": "track-001", "mode": "overlay"}],
                },
            )
    finally:
        stop_test_server(server)
