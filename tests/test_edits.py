from __future__ import annotations

from dataclasses import replace

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.edits import EditIntent, apply_edit_intent, build_edit_targets, edit_variant_type
from song_agent.schemas.song import SongRequest


def request() -> SongRequest:
    return SongRequest.from_dict(
        {
            "title": "Editable Song",
            "language": "English",
            "style": "synth pop",
            "theme": "controlled edits",
        }
    )


def plan():
    return deterministic_compose(request())


def test_edit_intent_round_trips_and_validates() -> None:
    intent = EditIntent.from_dict(
        {
            "edit_type": "section_energy",
            "target": {"section_name": "chorus"},
            "instruction": "lift the hook",
            "preserve": ["tempo", "key", "structure"],
            "strength": 7,
            "provider_mode": "local",
            "payload": {"x": 1},
        }
    )

    assert EditIntent.from_dict(intent.to_dict()) == intent
    assert edit_variant_type("lyrics_rewrite") == "lyrics_edit"


def test_edit_intent_rejects_unknown_type_strength_and_preserve() -> None:
    with pytest.raises(ValueError, match="edit_type"):
        EditIntent.from_dict({"edit_type": "bad"})
    with pytest.raises(ValueError, match="strength"):
        EditIntent.from_dict({"edit_type": "section_energy", "strength": 11})
    with pytest.raises(ValueError, match="preserve"):
        EditIntent.from_dict({"edit_type": "section_energy", "preserve": ["filesystem"]})


def test_section_energy_only_changes_target_section_velocity() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "section_energy",
            "target": {"section_name": "chorus"},
            "strength": 8,
        }
    )

    result = apply_edit_intent(parent, intent)

    parent_melody = next(track for track in parent.tracks if track.name == "melody")
    edited_melody = next(track for track in result.plan.tracks if track.name == "melody")
    verse_before = [note.velocity for note in parent_melody.notes if 16 <= note.start_beat < 48]
    verse_after = [note.velocity for note in edited_melody.notes if 16 <= note.start_beat < 48]
    chorus_before = [note.velocity for note in parent_melody.notes if 48 <= note.start_beat < 80]
    chorus_after = [note.velocity for note in edited_melody.notes if 48 <= note.start_beat < 80]

    assert result.plan.tempo_bpm == parent.tempo_bpm
    assert result.plan.key == parent.key
    assert [section.to_dict() for section in result.plan.sections] == [section.to_dict() for section in parent.sections]
    assert verse_after == verse_before
    assert all(after > before for before, after in zip(chorus_before, chorus_after))
    parent.validate()
    result.plan.validate()


def test_section_harmony_replaces_chords_and_rebuilds_chord_bass_notes() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "section_harmony",
            "target": {"section_name": "chorus", "field": "chords"},
            "payload": {"chords": ["g7", "Cmaj7"]},
        }
    )

    result = apply_edit_intent(parent, intent)
    chorus = next(section for section in result.plan.sections if section.name == "chorus")
    parent_chorus = next(section for section in parent.sections if section.name == "chorus")
    chord_track = next(track for track in result.plan.tracks if track.name == "chords")
    bass_track = next(track for track in result.plan.tracks if track.name == "bass")

    assert chorus.chords == ["G7", "Cmaj7"]
    assert parent_chorus.chords != chorus.chords
    assert any(note.pitch == 55 for note in chord_track.notes if 48 <= note.start_beat < 80)
    assert any(note.pitch == 31 for note in bass_track.notes if 48 <= note.start_beat < 80)
    result.plan.validate()


def test_section_harmony_rejects_unsupported_payload_chords() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "section_harmony",
            "target": {"section_name": "chorus", "field": "chords"},
            "payload": {"chords": ["Hmaj7", "Cmaj7"]},
        }
    )

    with pytest.raises(ValueError, match="Unsupported chord names: Hmaj7"):
        apply_edit_intent(parent, intent)


def test_section_harmony_uses_safe_default_chords_when_instruction_has_none() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "section_harmony",
            "target": {"section_name": "chorus"},
            "instruction": "use a richer lift",
        }
    )

    result = apply_edit_intent(parent, intent)
    chorus = next(section for section in result.plan.sections if section.name == "chorus")
    chord_track = next(track for track in result.plan.tracks if track.name == "chords")
    bass_track = next(track for track in result.plan.tracks if track.name == "bass")

    assert chorus.chords == ["Cmaj7", "Am7", "Fmaj7", "G7"]
    assert any(note.pitch == 53 for note in chord_track.notes if 48 <= note.start_beat < 80)
    assert any(note.pitch == 29 for note in bass_track.notes if 48 <= note.start_beat < 80)


def test_section_harmony_filters_instruction_chords_through_supported_set() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "section_harmony",
            "target": {"section_name": "chorus"},
            "instruction": "try Bm7 into Fmaj7 and e7",
        }
    )

    result = apply_edit_intent(parent, intent)
    chorus = next(section for section in result.plan.sections if section.name == "chorus")

    assert chorus.chords == ["Fmaj7", "E7"]


def test_track_density_changes_only_target_track() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "track_density",
            "target": {"track_name": "drums", "section_name": "verse"},
            "strength": 3,
        }
    )

    result = apply_edit_intent(parent, intent)
    parent_drums = next(track for track in parent.tracks if track.name == "drums")
    edited_drums = next(track for track in result.plan.tracks if track.name == "drums")
    parent_melody = next(track for track in parent.tracks if track.name == "melody")
    edited_melody = next(track for track in result.plan.tracks if track.name == "melody")

    assert len(edited_drums.notes) < len(parent_drums.notes)
    assert edited_melody.notes == parent_melody.notes
    result.plan.validate()


def test_lyrics_rewrite_only_changes_target_section_lyrics() -> None:
    parent = plan()
    intent = EditIntent.from_dict(
        {
            "edit_type": "lyrics_rewrite",
            "target": {"section_name": "verse", "field": "lyrics"},
            "payload": {"lyrics": "new verse line"},
        }
    )

    result = apply_edit_intent(parent, intent)

    assert next(section for section in result.plan.sections if section.name == "verse").lyrics == "new verse line"
    assert next(section for section in result.plan.sections if section.name == "chorus").lyrics is None
    assert next(section for section in parent.sections if section.name == "verse").lyrics is None
    result.plan.validate()


def test_melody_variation_preserves_rhythm_and_changes_pitch() -> None:
    parent = plan()
    intent = EditIntent.from_dict({"edit_type": "melody_variation", "target": {"section_name": "chorus"}, "strength": 6})

    result = apply_edit_intent(parent, intent)
    parent_notes = next(track for track in parent.tracks if track.name == "melody").notes
    edited_notes = next(track for track in result.plan.tracks if track.name == "melody").notes

    assert [note.start_beat for note in edited_notes] == [note.start_beat for note in parent_notes]
    assert [note.duration_beats for note in edited_notes] == [note.duration_beats for note in parent_notes]
    assert any(before.pitch != after.pitch for before, after in zip(parent_notes, edited_notes) if 48 <= before.start_beat < 80)


def test_missing_section_or_track_is_rejected() -> None:
    parent = plan()

    with pytest.raises(ValueError, match="Section not found"):
        apply_edit_intent(parent, EditIntent.from_dict({"edit_type": "section_energy", "target": {"section_name": "bridge"}}))
    with pytest.raises(ValueError, match="Track not found"):
        apply_edit_intent(parent, EditIntent.from_dict({"edit_type": "track_density", "target": {"track_name": "guitar"}}))


def test_parent_plan_is_not_mutated() -> None:
    parent = plan()
    before = parent.to_dict()

    apply_edit_intent(parent, EditIntent.from_dict({"edit_type": "section_energy", "target": {"section_name": "chorus"}}))

    assert parent.to_dict() == before


def test_build_edit_targets_lists_sections_tracks_and_supported_types() -> None:
    targets = build_edit_targets(plan())

    assert {section["name"] for section in targets["sections"]} >= {"verse", "chorus"}
    assert {track["name"] for track in targets["tracks"]} >= {"melody", "drums"}
    assert "section_energy" in targets["supported_edit_types"]
    assert "Hmaj7" not in targets["supported_chords"]
    assert {"Cmaj7", "G7"}.issubset(set(targets["supported_chords"]))
