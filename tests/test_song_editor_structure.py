from __future__ import annotations

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.schemas.song import SongRequest
from song_agent.song_editor import EditorPatchError, apply_editor_patch, build_editor_state


def sample_plan():
    return deterministic_compose(
        SongRequest(
            title="Structure Editor",
            language="English",
            style="synth pop",
            theme="section moves",
            duration_seconds=90,
            tempo_bpm=120,
            key="C",
        )
    )


def patch(plan, operations):
    state = build_editor_state(plan)
    return {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "operations": operations}


def test_add_section_normalizes_timeline_and_shifts_later_notes() -> None:
    plan = sample_plan()
    result = apply_editor_patch(
        plan,
        patch(
            plan,
            [
                {
                    "op": "add_section",
                    "after_section_id": "section-001",
                    "name": "pre chorus",
                    "bars": 2,
                    "chords": ["Fmaj7", "G7"],
                }
            ],
        ),
    )

    assert [section.start_bar for section in result.plan.sections] == [1, 5, 7, 15, 23]
    assert [section.name for section in result.plan.sections][1] == "pre chorus"
    assert min(note.start_beat for note in result.plan.tracks[0].notes if note.start_beat >= 16) >= 16
    assert "pre chorus" in result.summary["changed_sections"]
    assert any("without notes" in warning for warning in result.warnings)


def test_duplicate_section_copies_notes_to_new_section() -> None:
    plan = sample_plan()
    result = apply_editor_patch(
        plan,
        patch(
            plan,
            [
                {
                    "op": "duplicate_section",
                    "section_id": "section-003",
                    "name": "chorus 2",
                    "copy_notes": True,
                    "after_section_id": "section-003",
                }
            ],
        ),
    )

    chorus = next(section for section in result.plan.sections if section.name == "chorus")
    chorus_2 = next(section for section in result.plan.sections if section.name == "chorus 2")
    source_notes = [note for note in result.plan.tracks[0].notes if (chorus.start_bar - 1) * 4 <= note.start_beat < (chorus.start_bar - 1 + chorus.bars) * 4]
    copied_notes = [note for note in result.plan.tracks[0].notes if (chorus_2.start_bar - 1) * 4 <= note.start_beat < (chorus_2.start_bar - 1 + chorus_2.bars) * 4]

    assert chorus_2.start_bar == 21
    assert len(copied_notes) == len(source_notes)
    assert [(note.pitch, note.duration_beats, note.velocity) for note in copied_notes] == [
        (note.pitch, note.duration_beats, note.velocity) for note in source_notes
    ]


def test_delete_section_removes_range_and_shifts_tail_left() -> None:
    plan = sample_plan()
    result = apply_editor_patch(
        plan,
        patch(plan, [{"op": "delete_section", "section_id": "section-001", "note_policy": "delete"}]),
    )

    assert [section.name for section in result.plan.sections] == ["verse", "chorus", "outro"]
    assert [section.start_bar for section in result.plan.sections] == [1, 9, 17]
    assert min(note.start_beat for track in result.plan.tracks for note in track.notes) == 0
    assert max(section.start_bar - 1 + section.bars for section in result.plan.sections) == 20
    assert plan.sections[0].name == "intro"


def test_resize_section_crop_trims_notes_and_shifts_later_sections() -> None:
    plan = sample_plan()
    result = apply_editor_patch(
        plan,
        patch(plan, [{"op": "resize_section", "section_id": "section-002", "bars": 4, "note_policy": "crop"}]),
    )

    assert [section.start_bar for section in result.plan.sections] == [1, 5, 9, 17]
    assert result.plan.sections[1].bars == 4
    total_beats = max(section.start_bar - 1 + section.bars for section in result.plan.sections) * 4
    assert all(note.start_beat + note.duration_beats <= total_beats + 0.001 for track in result.plan.tracks for note in track.notes)


def test_move_section_reorders_timeline_and_moves_notes_by_section() -> None:
    plan = sample_plan()
    result = apply_editor_patch(
        plan,
        patch(plan, [{"op": "move_section", "section_id": "section-003", "after_section_id": "section-001", "move_notes": True}]),
    )

    assert [section.name for section in result.plan.sections] == ["intro", "chorus", "verse", "outro"]
    assert [section.start_bar for section in result.plan.sections] == [1, 5, 13, 21]
    chorus_notes = [note for note in result.plan.tracks[0].notes if 16 <= note.start_beat < 48]
    moved_chorus_notes = [note for note in result.plan.tracks[0].notes if 16 <= note.start_beat < 48 and note.pitch in {64, 67, 69, 71, 72}]
    assert chorus_notes
    assert moved_chorus_notes


def test_track_structure_operations() -> None:
    plan = sample_plan()
    result = apply_editor_patch(
        plan,
        patch(
            plan,
            [
                {"op": "add_track", "name": "pad", "instrument": "warm pad"},
                {"op": "duplicate_track", "track_id": "track-001", "name": "counter melody", "instrument": "soft lead", "transpose": 12},
                {"op": "rename_track", "track_id": "track-002", "name": "chords keys"},
            ],
        ),
    )

    tracks = {track.name: track for track in result.plan.tracks}
    assert tracks["pad"].notes == []
    assert tracks["counter melody"].instrument == "soft lead"
    assert tracks["counter melody"].notes[0].pitch == plan.tracks[0].notes[0].pitch + 12
    assert "chords keys" in tracks
    assert "chords" not in tracks


def test_delete_track_rejects_last_non_empty_track_without_override() -> None:
    plan = sample_plan()
    with pytest.raises(EditorPatchError, match="required track"):
        apply_editor_patch(
            plan,
            patch(
                plan,
                [
                    {"op": "delete_track", "track_id": "track-001"},
                ],
            ),
        )

    result = apply_editor_patch(
        plan,
        patch(
            plan,
            [
                {"op": "duplicate_track", "track_id": "track-001", "name": "melody sketch"},
                {"op": "delete_track", "track_id": "track-001"},
            ],
        ),
    )
    assert len(result.plan.tracks) == 4
    assert "melody" not in {track.name for track in result.plan.tracks}
    assert "melody sketch" in {track.name for track in result.plan.tracks}


def test_structure_validation_rejects_duplicates_and_bad_values() -> None:
    plan = sample_plan()
    with pytest.raises(EditorPatchError, match="Duplicate section"):
        apply_editor_patch(plan, patch(plan, [{"op": "add_section", "name": "verse", "bars": 4, "chords": ["Cmaj7"]}]))
    with pytest.raises(EditorPatchError, match="bars"):
        apply_editor_patch(plan, patch(plan, [{"op": "resize_section", "section_id": "section-001", "bars": 80}]))
    with pytest.raises(EditorPatchError, match="Duplicate track"):
        apply_editor_patch(plan, patch(plan, [{"op": "add_track", "name": "melody", "instrument": "lead"}]))
