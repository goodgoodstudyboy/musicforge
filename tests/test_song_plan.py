import pytest

from song_agent.agent.pipeline import SongAgent
from song_agent.quality import validate_song_plan
from song_agent.schemas.song import NoteEvent, SongPlan, SongRequest, SongSection, TrackPlan


def make_valid_plan() -> SongPlan:
    section = SongSection(
        name="intro",
        start_bar=1,
        bars=1,
        chords=["Cmaj7"],
    )
    return SongPlan(
        title="Test Song",
        key="C major",
        tempo_bpm=92,
        meter="4/4",
        sections=[section],
        tracks=[
            TrackPlan("melody", "lead", [NoteEvent(64, 0, 1)]),
            TrackPlan("chords", "keys", [NoteEvent(60, 0, 4)]),
            TrackPlan("bass", "bass", [NoteEvent(36, 0, 2)]),
            TrackPlan("drums", "gm drums", [NoteEvent(36, 0, 0.25)]),
        ],
    )


def test_song_plan_round_trips_through_dict():
    plan = make_valid_plan()

    restored = SongPlan.from_dict(plan.to_dict())

    assert restored == plan
    validate_song_plan(restored)


def test_song_plan_rejects_invalid_pitch():
    data = make_valid_plan().to_dict()
    data["tracks"][0]["notes"][0]["pitch"] = 128

    with pytest.raises(ValueError, match="pitch"):
        validate_song_plan(SongPlan.from_dict(data))


def test_song_plan_rejects_non_positive_duration():
    data = make_valid_plan().to_dict()
    data["tracks"][0]["notes"][0]["duration_beats"] = 0

    with pytest.raises(ValueError, match="duration"):
        validate_song_plan(SongPlan.from_dict(data))


def test_song_plan_rejects_missing_required_track():
    data = make_valid_plan().to_dict()
    data["tracks"] = [track for track in data["tracks"] if track["name"] != "drums"]

    with pytest.raises(ValueError, match="drums"):
        validate_song_plan(SongPlan.from_dict(data))


def test_song_plan_rejects_empty_section_chords():
    data = make_valid_plan().to_dict()
    data["sections"][0]["chords"] = []

    with pytest.raises(ValueError, match="chords"):
        validate_song_plan(SongPlan.from_dict(data))


def test_deterministic_agent_generates_valid_four_track_plan():
    request = SongRequest.from_dict(
        {
            "title": "Rainy Convenience Store",
            "language": "zh",
            "style": "city pop",
            "theme": "rainy night",
            "tempo_bpm": 92,
            "key": "C major",
        }
    )

    plan = SongAgent().generate(request)

    validate_song_plan(plan)
    assert [section.name for section in plan.sections] == [
        "intro",
        "verse",
        "chorus",
        "outro",
    ]
    assert {track.name for track in plan.tracks} == {"melody", "chords", "bass", "drums"}
