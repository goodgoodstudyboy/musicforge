from __future__ import annotations

import pytest

from song_agent.assets import AssetStore
from song_agent.editor_clips import (
    EditorClipError,
    build_clip_insert_patch,
    build_editor_clip_from_ref,
    list_editor_clips,
)
from song_agent.editor_view import build_editor_view_from_result
from song_agent.projects import ProjectStore
from song_agent.references import ReferenceStore
from song_agent.schemas.song import NoteEvent, SongPlan, SongSection, TrackPlan
from song_agent.song_editor import apply_editor_patch


def sample_plan() -> SongPlan:
    return SongPlan(
        title="Clip Test",
        key="C",
        tempo_bpm=120,
        meter="4/4",
        sections=[
            SongSection("intro", 1, 4, ["Cmaj7"]),
            SongSection("verse", 5, 4, ["Fmaj7"]),
        ],
        tracks=[
            TrackPlan("melody", "lead", [NoteEvent(60, 0, 1, 80), NoteEvent(62, 4, 1, 82)]),
            TrackPlan("chords", "piano", [NoteEvent(60, 0, 4, 70), NoteEvent(65, 16, 4, 72)]),
            TrackPlan("bass", "electric bass", [NoteEvent(36, 0, 1, 84)]),
            TrackPlan("drums", "gm drums", [NoteEvent(36, 0, 0.25, 96), NoteEvent(38, 2, 0.25, 90)]),
        ],
    )


def create_asset(store: AssetStore):
    return store.create_asset(
        {
            "asset_type": "motif",
            "name": "Hook Motif",
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


def test_asset_clip_insert_builds_patch_and_derived_draft_view(tmp_path):
    asset_store = AssetStore(tmp_path / "assets")
    asset = create_asset(asset_store)
    clip = build_editor_clip_from_ref(
        {"source_type": "asset", "asset_id": asset.asset_id},
        default_project_id="project-001",
        asset_store=asset_store,
        reference_store=ReferenceStore(tmp_path / "refs"),
        project_store=ProjectStore(tmp_path / "projects"),
    )

    patch, summary, warnings = build_clip_insert_patch(
        sample_plan(),
        clip,
        {
            "target": {"track_id": "track-001", "section_id": "section-001", "start_beat": 1},
            "options": {"mode": "overlay", "transpose": 1, "velocity_scale": 1, "quantize_grid": "1/16"},
        },
    )
    result = apply_editor_patch(sample_plan(), patch)
    view = build_editor_view_from_result(result)
    derived = [note for note in view["lanes"][0]["notes"] if note["derived"]]

    assert summary["source_type"] == "asset"
    assert warnings == []
    assert len(patch["operations"]) == 2
    assert patch["metadata"]["clip_inserts"][0]["source_id"] == asset.asset_id
    assert result.summary["operation_counts"]["add_note"] == 2
    assert [note["pitch"] for note in derived] == [73, 75]
    assert all(note["editable"] is False for note in derived)


def test_replace_range_deletes_base_notes_before_insert(tmp_path):
    asset_store = AssetStore(tmp_path / "assets")
    asset = create_asset(asset_store)
    clip = build_editor_clip_from_ref(
        {"source_type": "asset", "asset_id": asset.asset_id},
        default_project_id="project-001",
        asset_store=asset_store,
        reference_store=ReferenceStore(tmp_path / "refs"),
        project_store=ProjectStore(tmp_path / "projects"),
    )

    patch, _summary, _warnings = build_clip_insert_patch(
        sample_plan(),
        clip,
        {
            "target": {"track_id": "track-001", "section_id": "section-001", "start_beat": 0},
            "options": {"mode": "replace_range"},
        },
    )

    assert patch["operations"][0]["op"] == "delete_notes"
    assert len(patch["operations"][0]["note_ids"]) == 1
    assert patch["metadata"]["clip_inserts"][0]["replaced_note_count"] == 1


def test_clip_insert_rejects_oversize_asset(tmp_path):
    asset_store = AssetStore(tmp_path / "assets")
    notes = [{"pitch": 60, "start_beat": index * 0.25, "duration_beats": 0.25, "velocity": 80} for index in range(129)]
    asset = asset_store.create_asset(
        {
            "asset_type": "motif",
            "name": "Too Many Notes",
            "duration_beats": 32,
            "content": {"kind": "motif", "notes": notes},
        },
        now="2026-05-11T00:00:00+00:00",
    )

    with pytest.raises(EditorClipError):
        build_editor_clip_from_ref(
            {"source_type": "asset", "asset_id": asset.asset_id},
            default_project_id="project-001",
            asset_store=asset_store,
            reference_store=ReferenceStore(tmp_path / "refs"),
            project_store=ProjectStore(tmp_path / "projects"),
        )


def test_list_editor_clips_exposes_note_based_assets(tmp_path):
    asset_store = AssetStore(tmp_path / "assets")
    asset = create_asset(asset_store)

    catalog = list_editor_clips(
        project_id="project-001",
        version_id="v001",
        asset_store=asset_store,
        reference_store=ReferenceStore(tmp_path / "refs"),
        project_store=ProjectStore(tmp_path / "projects"),
    )

    assert catalog["clips"][0]["source_id"] == asset.asset_id
    assert catalog["clips"][0]["clip_ref"]["source_type"] == "asset"
