from __future__ import annotations

from song_agent.agent.pipeline import deterministic_compose
from song_agent.editor_view import build_editor_diff, build_editor_view, build_editor_view_from_result
from song_agent.schemas.song import NoteEvent, SongRequest, TrackPlan
from song_agent.song_editor import apply_editor_patch, build_editor_state


def sample_plan():
    return deterministic_compose(
        SongRequest(
            title="Editor View",
            language="English",
            style="synth pop",
            theme="visual editor",
            duration_seconds=90,
            tempo_bpm=120,
            key="C",
        )
    )


def test_build_editor_view_returns_arranger_and_piano_roll_data() -> None:
    plan = sample_plan()
    view = build_editor_view(plan)

    assert view["schema_version"] == 1
    assert view["song"]["total_beats"] == view["song"]["total_bars"] * view["song"]["beats_per_bar"]
    assert view["sections"][0]["section_id"] == "section-001"
    assert view["tracks"][0]["track_id"] == "track-001"
    assert view["lanes"][0]["track_id"] == "track-001"
    assert view["lanes"][0]["notes"][0]["end_beat"] > view["lanes"][0]["notes"][0]["start_beat"]
    assert view["lanes"][0]["notes"][0]["section_id"] == "section-001"
    assert view["pitch_range"]["min"] <= 36
    assert view["pitch_range"]["max"] >= 84


def test_build_editor_view_handles_empty_track_and_extreme_pitch() -> None:
    plan = sample_plan()
    plan.tracks.append(TrackPlan("empty", "pad", []))
    plan.tracks[0].notes.append(NoteEvent(127, 0.0, 1.0, 90))
    view = build_editor_view(plan)

    assert view["tracks"][-1]["note_count"] == 0
    assert view["lanes"][-1]["notes"] == []
    assert view["pitch_range"]["max"] == 127


def test_build_editor_diff_summarizes_patch_changes() -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    note_id = state["tracks"][0]["notes"][0]["note_id"]
    result = apply_editor_patch(
        plan,
        {
            "schema_version": 1,
            "base_plan_hash": state["base_plan_hash"],
            "operations": [
                {"op": "resize_section", "section_id": "section-002", "bars": 4, "note_policy": "crop"},
                {"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 77}},
                {"op": "move_notes", "track_id": "track-001", "note_ids": [note_id], "delta_beats": 0.5},
            ],
        },
    )
    diff = build_editor_diff(plan, result.plan, result.patch)

    assert "verse" in diff["sections"]["changed"]
    assert diff["notes"]["changed"] == 1
    assert diff["notes"]["moved"] == 1
    assert diff["operation_counts"]["resize_section"] == 1


def test_build_editor_view_from_result_keeps_base_note_ids_after_move() -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    note_id = state["tracks"][0]["notes"][0]["note_id"]
    result = apply_editor_patch(
        plan,
        {
            "schema_version": 1,
            "base_plan_hash": state["base_plan_hash"],
            "operations": [{"op": "move_notes", "track_id": "track-001", "note_ids": [note_id], "delta_beats": 0.5}],
        },
    )
    view = build_editor_view_from_result(result)

    moved = next(note for note in view["lanes"][0]["notes"] if note["note_id"] == note_id)
    assert moved["start_beat"] == plan.tracks[0].notes[0].start_beat + 0.5


def test_build_editor_view_from_result_keeps_base_section_ids_after_delete() -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    result = apply_editor_patch(
        plan,
        {
            "schema_version": 1,
            "base_plan_hash": state["base_plan_hash"],
            "operations": [{"op": "delete_section", "section_id": "section-001", "note_policy": "shift_left"}],
        },
    )
    view = build_editor_view_from_result(result)

    assert view["sections"][0]["name"] == "verse"
    assert view["sections"][0]["section_id"] == "section-002"
    assert all(section["section_id"] != "section-001" for section in view["sections"])


def test_build_editor_view_from_result_keeps_base_track_ids_after_delete_duplicate() -> None:
    plan = sample_plan()
    state = build_editor_state(plan)
    result = apply_editor_patch(
        plan,
        {
            "schema_version": 1,
            "base_plan_hash": state["base_plan_hash"],
            "operations": [
                {"op": "duplicate_track", "track_id": "track-001", "name": "melody copy"},
                {"op": "delete_track", "track_id": "track-001"},
            ],
        },
    )
    view = build_editor_view_from_result(result)

    assert view["tracks"][0]["name"] == "chords"
    assert view["tracks"][0]["track_id"] == "track-002"
    assert view["tracks"][-1]["name"] == "melody copy"
    assert view["tracks"][-1]["track_id"].startswith("derived-track-")
    assert view["tracks"][-1]["editable"] is False
