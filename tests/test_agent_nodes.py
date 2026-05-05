import pytest

from song_agent.schemas.agent_nodes import (
    ArrangementPlan,
    CriticReport,
    HarmonyPlan,
    MelodyPlan,
    RepairPlan,
    SongBrief,
    SonicPalette,
    StructurePlan,
)


def note():
    return {"pitch": 64, "start_beat": 0, "duration_beats": 1, "velocity": 90}


def test_song_brief_from_dict():
    brief = SongBrief.from_dict(
        {
            "title": "Node Song",
            "language": "en",
            "style": "city pop",
            "theme": "rain",
            "duration_seconds": 120,
            "vocal_mode": "guide_melody",
            "tempo_bpm": 92,
            "key": "C major",
            "mood_tags": ["warm"],
        }
    )

    assert brief.title == "Node Song"
    assert brief.mood_tags == ["warm"]
    assert brief.to_dict()["tempo_bpm"] == 92


def test_sonic_palette_from_dict():
    palette = SonicPalette.from_dict(
        {
            "genre_tags": ["city pop"],
            "instrumentation": ["electric piano", "bass", "drums"],
            "lead_instrument": "lead synth",
            "bass_style": "syncopated",
            "drum_style": "tight",
        }
    )

    assert palette.lead_instrument == "lead synth"
    assert "bass" in palette.instrumentation


def test_structure_plan_from_dict():
    plan = StructurePlan.from_dict(
        {
            "meter": "4/4",
            "sections": [
                {
                    "name": "intro",
                    "start_bar": 1,
                    "bars": 4,
                    "energy": 2,
                    "purpose": "set mood",
                }
            ],
        }
    )

    assert plan.sections[0].bars == 4


def test_harmony_plan_from_dict():
    plan = HarmonyPlan.from_dict(
        {
            "key": "C major",
            "progressions": [{"section_name": "intro", "chords": ["Cmaj7", "Am7"]}],
        }
    )

    assert plan.progressions[0].chords == ["Cmaj7", "Am7"]


def test_melody_plan_from_dict():
    plan = MelodyPlan.from_dict(
        {
            "lead_instrument": "lead",
            "phrases": [{"section_name": "intro", "notes": [note()]}],
        }
    )

    assert plan.phrases[0].notes[0].pitch == 64


def test_arrangement_plan_from_dict():
    plan = ArrangementPlan.from_dict(
        {
            "tracks": [
                {
                    "name": "melody",
                    "instrument": "lead",
                    "role": "melody",
                    "notes": [note()],
                }
            ]
        }
    )

    assert plan.tracks[0].role == "melody"


def test_critic_report_from_dict():
    report = CriticReport.from_dict(
        {
            "passed": False,
            "score": 70,
            "issues": [
                {
                    "severity": "warning",
                    "code": "missing_texture",
                    "message": "Texture is sparse.",
                }
            ],
        }
    )

    assert report.issues[0].severity == "warning"


def test_repair_plan_from_dict():
    plan = RepairPlan.from_dict(
        {
            "applied": True,
            "actions": [
                {
                    "target": "tracks.melody.notes.0.pitch",
                    "action": "clamp",
                    "reason": "out of MIDI range",
                }
            ],
        }
    )

    assert plan.actions[0].action == "clamp"


def test_schema_rejects_invalid_notes():
    data = {
        "lead_instrument": "lead",
        "phrases": [{"section_name": "intro", "notes": [note()]}],
    }
    data["phrases"][0]["notes"][0]["pitch"] = 128

    with pytest.raises(ValueError, match="pitch"):
        MelodyPlan.from_dict(data)
