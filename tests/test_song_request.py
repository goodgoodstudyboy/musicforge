import pytest

from song_agent.schemas.song import SongRequest


def test_song_request_accepts_minimal_payload():
    request = SongRequest.from_dict(
        {
            "title": "Test Song",
            "language": "zh",
            "style": "city pop",
            "theme": "rainy night",
        }
    )

    assert request.duration_seconds == 180
    assert request.vocal_mode == "guide_melody"


def test_song_request_rejects_invalid_duration():
    with pytest.raises(ValueError, match="duration_seconds"):
        SongRequest.from_dict(
            {
                "title": "Test Song",
                "language": "zh",
                "style": "city pop",
                "theme": "rainy night",
                "duration_seconds": 10,
            }
        )

