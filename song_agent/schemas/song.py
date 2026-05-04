from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SongRequest:
    title: str
    language: str
    style: str
    theme: str
    duration_seconds: int = 180
    vocal_mode: str = "guide_melody"
    tempo_bpm: int | None = None
    key: str | None = None
    lyrics: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongRequest":
        required = ["title", "language", "style", "theme"]
        missing = [field_name for field_name in required if not data.get(field_name)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        duration = int(data.get("duration_seconds", 180))
        if duration < 30 or duration > 600:
            raise ValueError("duration_seconds must be between 30 and 600.")

        tempo = data.get("tempo_bpm")
        if tempo is not None:
            tempo = int(tempo)
            if tempo < 40 or tempo > 240:
                raise ValueError("tempo_bpm must be between 40 and 240.")

        return cls(
            title=str(data["title"]),
            language=str(data["language"]),
            style=str(data["style"]),
            theme=str(data["theme"]),
            duration_seconds=duration,
            vocal_mode=str(data.get("vocal_mode", "guide_melody")),
            tempo_bpm=tempo,
            key=data.get("key"),
            lyrics=data.get("lyrics"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NoteEvent:
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int = 90


@dataclass(frozen=True)
class TrackPlan:
    name: str
    instrument: str
    notes: list[NoteEvent] = field(default_factory=list)


@dataclass(frozen=True)
class SongSection:
    name: str
    start_bar: int
    bars: int
    chords: list[str]
    lyrics: str | None = None


@dataclass(frozen=True)
class SongPlan:
    title: str
    key: str
    tempo_bpm: int
    meter: str
    sections: list[SongSection]
    tracks: list[TrackPlan]

