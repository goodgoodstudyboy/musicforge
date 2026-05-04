from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _require_mapping(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be an object.")
    return data


def _require_list(data: Any, name: str) -> list[Any]:
    if not isinstance(data, list):
        raise ValueError(f"{name} must be a list.")
    return data


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoteEvent":
        data = _require_mapping(data, "note")
        required = ["pitch", "start_beat", "duration_beats"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing note fields: {', '.join(missing)}")

        return cls(
            pitch=int(data["pitch"]),
            start_beat=float(data["start_beat"]),
            duration_beats=float(data["duration_beats"]),
            velocity=int(data.get("velocity", 90)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrackPlan:
    name: str
    instrument: str
    notes: list[NoteEvent] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackPlan":
        data = _require_mapping(data, "track")
        required = ["name", "instrument"]
        missing = [field_name for field_name in required if not data.get(field_name)]
        if missing:
            raise ValueError(f"Missing track fields: {', '.join(missing)}")

        notes = [
            NoteEvent.from_dict(note)
            for note in _require_list(data.get("notes", []), "track.notes")
        ]
        return cls(
            name=str(data["name"]),
            instrument=str(data["instrument"]),
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SongSection:
    name: str
    start_bar: int
    bars: int
    chords: list[str]
    lyrics: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongSection":
        data = _require_mapping(data, "section")
        required = ["name", "start_bar", "bars", "chords"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing section fields: {', '.join(missing)}")

        chords = [str(chord) for chord in _require_list(data["chords"], "section.chords")]
        lyrics = data.get("lyrics")
        return cls(
            name=str(data["name"]),
            start_bar=int(data["start_bar"]),
            bars=int(data["bars"]),
            chords=chords,
            lyrics=None if lyrics is None else str(lyrics),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SongPlan:
    title: str
    key: str
    tempo_bpm: int
    meter: str
    sections: list[SongSection]
    tracks: list[TrackPlan]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongPlan":
        data = _require_mapping(data, "song_plan")
        required = ["title", "key", "tempo_bpm", "meter", "sections", "tracks"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing song plan fields: {', '.join(missing)}")

        sections = [
            SongSection.from_dict(section)
            for section in _require_list(data["sections"], "sections")
        ]
        tracks = [
            TrackPlan.from_dict(track)
            for track in _require_list(data["tracks"], "tracks")
        ]
        return cls(
            title=str(data["title"]),
            key=str(data["key"]),
            tempo_bpm=int(data["tempo_bpm"]),
            meter=str(data["meter"]),
            sections=sections,
            tracks=tracks,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        from song_agent.quality import validate_song_plan

        validate_song_plan(self)
