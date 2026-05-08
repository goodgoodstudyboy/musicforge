from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.schemas.song import SongRequest
from song_agent.song_editor import (
    EditorPatchError,
    EditorPatchStaleError,
    EditorPreviewStore,
    apply_editor_patch,
    build_editor_state,
    song_plan_hash,
)


def sample_plan():
    return deterministic_compose(
        SongRequest(
            title="Editor Smoke",
            language="English",
            style="synth pop",
            theme="visual edit",
            duration_seconds=90,
            tempo_bpm=120,
            key="C",
        )
    )


def test_editor_state_generates_stable_ids() -> None:
    plan = sample_plan()
    first = build_editor_state(plan)
    second = build_editor_state(plan)

    assert first["base_plan_hash"] == song_plan_hash(plan)
    assert first["sections"][0]["section_id"] == "section-001"
    assert first["tracks"][0]["track_id"] == "track-001"
    assert first["tracks"][0]["notes"][0]["note_id"] == second["tracks"][0]["notes"][0]["note_id"]


def test_apply_editor_patch_updates_sections_tracks_and_notes() -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    melody_note_id = state["tracks"][0]["notes"][0]["note_id"]
    patch = {
        "schema_version": 1,
        "base_plan_hash": state["base_plan_hash"],
        "label": "Chorus polish",
        "operations": [
            {"op": "set_section_chords", "section_id": "section-001", "chords": ["Cmaj7", "G7", "Am7", "Fmaj7"]},
            {"op": "set_section_lyrics", "section_id": "section-001", "lyrics": "new safe lyric"},
            {"op": "set_track_instrument", "track_id": "track-001", "instrument": "warm lead synth"},
            {"op": "update_note", "track_id": "track-001", "note_id": melody_note_id, "patch": {"pitch": 67, "velocity": 99}},
            {"op": "add_note", "track_id": "track-001", "note": {"pitch": 69, "start_beat": 2.5, "duration_beats": 0.5, "velocity": 80}},
        ],
    }

    result = apply_editor_patch(plan, patch)

    assert result.plan.sections[0].chords == ["Cmaj7", "G7", "Am7", "Fmaj7"]
    assert result.plan.sections[0].lyrics == "new safe lyric"
    assert result.plan.tracks[0].instrument == "warm lead synth"
    assert any(note.pitch == 67 and note.velocity == 99 for note in result.plan.tracks[0].notes)
    assert any(note.pitch == 69 and note.start_beat == 2.5 for note in result.plan.tracks[0].notes)
    assert result.plan.quality is not None
    assert result.summary["changed_sections"] == ["intro"]
    assert result.summary["changed_tracks"] == ["melody"]


def test_editor_patch_rejects_stale_hash_and_bad_chord() -> None:
    plan = sample_plan()
    with pytest.raises(EditorPatchStaleError):
        apply_editor_patch(plan, {"schema_version": 1, "base_plan_hash": "bad", "operations": [{"op": "set_section_lyrics", "section_id": "section-001", "lyrics": "x"}]})

    state = build_editor_state(plan)
    with pytest.raises(EditorPatchError, match="Unsupported chord"):
        apply_editor_patch(plan, {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "operations": [{"op": "set_section_chords", "section_id": "section-001", "chords": ["Hmaj7"]}]})


def test_editor_patch_note_range_and_selection_guards() -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    with pytest.raises(EditorPatchError, match="song length"):
        apply_editor_patch(
            plan,
            {
                "schema_version": 1,
                "base_plan_hash": state["base_plan_hash"],
                "operations": [{"op": "add_note", "track_id": "track-001", "note": {"pitch": 60, "start_beat": 999, "duration_beats": 1}}],
            },
        )
    with pytest.raises(EditorPatchError, match="Unknown note"):
        apply_editor_patch(
            plan,
            {
                "schema_version": 1,
                "base_plan_hash": state["base_plan_hash"],
                "operations": [{"op": "delete_notes", "track_id": "track-001", "note_ids": ["note-track-001-9999-deadbeef"]}],
            },
        )


def test_editor_preview_store_creates_preview_and_marks_applied(tmp_path: Path) -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    result = apply_editor_patch(plan, {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "operations": [{"op": "set_track_instrument", "track_id": "track-001", "instrument": "soft lead"}]})
    store = EditorPreviewStore(tmp_path / "project-001")

    preview, preview_dir = store.create_preview(
        project_id="project-001",
        parent_version_id="v001",
        parent_job_id="parent-job",
        parent_plan=plan,
        patch=result.patch,
        result=result,
        now="2026-05-08T00:00:00+00:00",
    )
    applied = store.mark_applied(preview.preview_id, version_id="v002", job_id="editor-job")

    assert preview.preview_id == "preview-001"
    assert (preview_dir / "song.mid").exists()
    assert store.read_plan(preview.preview_id).tracks[0].instrument == "soft lead"
    assert applied.applied_version_id == "v002"
    with pytest.raises(EditorPatchStaleError):
        store.mark_applied(preview.preview_id, version_id="v003", job_id="other-job")
