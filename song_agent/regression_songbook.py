from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from song_agent.redaction import sanitize_metadata


REGRESSION_SONGBOOK_SCHEMA_VERSION = 1
BUILTIN_SONGBOOK_ID = "builtin_v1"
BUILTIN_SONGBOOK_VERSION = "2026-05-19"


@dataclass(frozen=True)
class RegressionSong:
    song_id: str
    title: str
    style: str
    theme: str
    language: str = "English"
    duration_seconds: int = 90
    expected_sections_min: int = 3
    expected_tracks_min: int = 3
    min_note_count: int = 64
    min_quality: int = 75
    min_rating: int = 3

    def request(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "title": self.title,
                "language": self.language,
                "style": self.style,
                "theme": self.theme,
                "duration_seconds": self.duration_seconds,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "song_id": self.song_id,
                "title": self.title,
                "style": self.style,
                "theme": self.theme,
                "language": self.language,
                "duration_seconds": self.duration_seconds,
                "request": self.request(),
                "expectations": {
                    "sections_min": self.expected_sections_min,
                    "tracks_min": self.expected_tracks_min,
                    "note_count_min": self.min_note_count,
                    "quality_min": self.min_quality,
                    "rating_min": self.min_rating,
                },
            }
        )


BUILTIN_REGRESSION_SONGS: tuple[RegressionSong, ...] = (
    RegressionSong("upbeat_pop_001", "Neon Morning", "upbeat pop", "bright city sunrise"),
    RegressionSong("sad_ballad_001", "Quiet Harbor", "sad ballad", "late night reflection"),
    RegressionSong("rock_chorus_001", "Signal Fire", "rock anthem chorus", "wide chorus lift"),
    RegressionSong("acoustic_folk_001", "Woodsmoke Letter", "acoustic folk", "warm homecoming"),
    RegressionSong("electronic_loop_001", "Circuit Bloom", "electronic loop", "glowing machines"),
    RegressionSong("cinematic_001", "Wide Sky Signal", "cinematic instrumental", "open landscape"),
    RegressionSong("rap_beat_001", "Sidewalk Cipher", "rap beat hip-hop", "confident street story"),
    RegressionSong("children_song_001", "Paper Kite Parade", "children song", "playful afternoon", duration_seconds=75),
    RegressionSong("chinese_pop_001", "雨后霓虹", "Chinese pop", "雨后城市与新的开始", language="Chinese"),
    RegressionSong("instrumental_001", "Glass River Theme", "instrumental", "flowing piano and strings"),
    RegressionSong("short_demo_001", "Spark Demo", "short demo pop", "compact product demo", duration_seconds=45),
    RegressionSong("long_structure_001", "Long Road Lanterns", "long structure pop rock", "journey with bridge and final chorus", duration_seconds=150),
)


def builtin_songbook() -> dict[str, Any]:
    return sanitize_metadata(
        {
            "schema_version": REGRESSION_SONGBOOK_SCHEMA_VERSION,
            "songbook_id": BUILTIN_SONGBOOK_ID,
            "songbook_version": BUILTIN_SONGBOOK_VERSION,
            "name": "Built-in Regression Songbook",
            "songs": [song.to_dict() for song in BUILTIN_REGRESSION_SONGS],
        }
    )


def list_regression_songs(limit: int | None = None) -> list[dict[str, Any]]:
    songs = [song.to_dict() for song in BUILTIN_REGRESSION_SONGS]
    if limit is None:
        return songs
    return songs[: max(0, min(len(songs), int(limit)))]


def get_regression_song(song_id: str) -> dict[str, Any]:
    for song in BUILTIN_REGRESSION_SONGS:
        if song.song_id == song_id:
            return song.to_dict()
    raise ValueError(f"Unknown regression song: {song_id}.")
