from pathlib import Path

from song_agent.projectio import write_json
from song_agent.runtime_views import (
    build_quality_view,
    build_runtime_views,
    build_timeline_view,
    build_tracks_view,
    build_validator_view,
)


def sample_plan() -> dict:
    return {
        "title": "Rainy Convenience Store",
        "key": "C major",
        "tempo_bpm": 120,
        "meter": "4/4",
        "sections": [
            {
                "name": "intro",
                "start_bar": 1,
                "bars": 4,
                "chords": ["Cmaj7", "Am7", "Dm7", "G7"],
            },
            {
                "name": "verse",
                "start_bar": 5,
                "bars": 4,
                "chords": ["Fmaj7", "Em7", "Dm7", "G7"],
            },
        ],
        "tracks": [
            {
                "name": "Melody",
                "instrument": "lead synth",
                "notes": [
                    {"pitch": 64, "start_beat": 0, "duration_beats": 1, "velocity": 90},
                    {"pitch": 67, "start_beat": 1, "duration_beats": 2, "velocity": 80},
                ],
            },
            {
                "name": "Bass",
                "instrument": "electric bass",
                "notes": [
                    {"pitch": 40, "start_beat": 0, "duration_beats": 4},
                ],
            },
        ],
        "quality": {
            "summary": "Test quality",
            "section_intents": [
                {
                    "section_name": "intro",
                    "role": "establish",
                    "energy": 2,
                    "tension": 2,
                    "density": 2,
                    "hook": False,
                },
                {
                    "section_name": "verse",
                    "role": "narrative",
                    "energy": 4,
                    "tension": 4,
                    "density": 4,
                    "hook": False,
                },
            ],
            "hook_sections": [],
            "scores": {
                "overall": 75,
                "structure": 74,
                "melody": 76,
                "harmony": 75,
                "arrangement": 75,
                "lyric_fit": 0,
            },
            "warnings": [],
        },
    }


def test_timeline_view_calculates_section_times():
    view = build_timeline_view(sample_plan())

    assert view["title"] == "Rainy Convenience Store"
    assert view["total_bars"] == 8
    assert view["estimated_seconds"] == 16.0
    assert view["warnings"] == []
    assert view["sections"][0] == {
        "index": 0,
        "name": "intro",
        "start_bar": 1,
        "end_bar": 4,
        "bars": 4,
        "start_beat": 0,
        "end_beat": 16,
        "estimated_start_seconds": 0.0,
        "estimated_end_seconds": 8.0,
        "chords": ["Cmaj7", "Am7", "Dm7", "G7"],
        "energy": 2,
        "tension": 2,
        "density": 2,
        "role": "establish",
        "hook": False,
    }
    assert view["sections"][1]["estimated_start_seconds"] == 8.0
    assert view["sections"][1]["estimated_end_seconds"] == 16.0


def test_timeline_view_handles_empty_sections():
    plan = sample_plan()
    plan["sections"] = []

    view = build_timeline_view(plan)

    assert view["sections"] == []
    assert view["total_bars"] == 0
    assert view["estimated_seconds"] == 0.0


def test_timeline_view_warns_for_unsupported_meter():
    plan = sample_plan()
    plan["meter"] = "7/8"

    view = build_timeline_view(plan)

    assert view["warnings"] == [
        "Unsupported meter 7/8; timeline estimated with 4 beats per bar."
    ]
    assert view["sections"][0]["end_beat"] == 16


def test_tracks_view_counts_notes_and_ranges():
    view = build_tracks_view(sample_plan())

    assert view["track_count"] == 2
    assert view["note_count"] == 3
    assert view["total_bars"] == 8
    assert view["tracks"][0]["note_count"] == 2
    assert view["tracks"][0]["pitch_min"] == 64
    assert view["tracks"][0]["pitch_max"] == 67
    assert view["tracks"][0]["start_beat_min"] == 0
    assert view["tracks"][0]["end_beat_max"] == 3
    assert view["tracks"][0]["average_velocity"] == 85.0
    assert view["tracks"][0]["density_notes_per_bar"] == 0.25
    assert view["tracks"][1]["average_velocity"] == 90.0


def test_tracks_view_handles_empty_tracks():
    plan = sample_plan()
    plan["tracks"] = []

    view = build_tracks_view(plan)

    assert view["track_count"] == 0
    assert view["note_count"] == 0
    assert view["tracks"] == []


def test_quality_view_returns_scores_and_issues():
    view = build_quality_view(sample_plan())

    assert view["overall"] == 75
    assert view["scores"]["structure"] == 74
    assert isinstance(view["issues"], list)
    assert view["section_intents"][0]["energy"] == 2


def test_validator_view_handles_missing_report():
    view = build_validator_view(None)

    assert view["status"] == "missing"
    assert view["passed"] is False
    assert view["check_count"] == 0
    assert view["midi"] == {"exists": False, "size": 0}
    assert view["warnings"] == ["validator-report.json was not found."]


def test_build_runtime_views_reads_plan_and_validator(tmp_path: Path):
    plan_path = tmp_path / "song-plan.json"
    validator_path = tmp_path / "validator-report.json"
    write_json(plan_path, sample_plan())
    write_json(
        validator_path,
        {
            "status": "passed",
            "checks": ["song_plan_schema", "midi_render"],
            "midi_exists": True,
            "midi_size": 1234,
        },
    )

    views = build_runtime_views(plan_path, validator_path)

    assert views["summary"]["note_count"] == 3
    assert views["timeline"]["total_bars"] == 8
    assert views["tracks"]["track_count"] == 2
    assert views["validator"]["check_count"] == 2
    assert views["quality"]["overall"] == 75
