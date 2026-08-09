from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument

from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from typing import Any as Any


def _require_mapping(data: Any, name: str) -> ImplementationDocument:
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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _float_list(data: Any, name: str) -> list[float]:
    return [float(item) for item in _require_list(data, name)]


def _int_list(data: Any, name: str) -> list[int]:
    return [int(item) for item in _require_list(data, name)]


def _range_int(data: ImplementationDocument, field_name: str, low: int, high: int, default: int | None = None) -> int:
    if field_name not in data:
        if default is None:
            raise ValueError(f"Missing field: {field_name}")
        value = default
    else:
        value = int(data[field_name])
    if value < low or value > high:
        raise ValueError(f"{field_name} must be between {low} and {high}.")
    return value


@dataclass(frozen=True)
class MotifPlan:
    name: str
    description: str
    rhythm_pattern: list[float] = field(default_factory=list)
    pitch_intervals: list[int] = field(default_factory=list)
    anchor_section: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotifPlan":
        data = _require_mapping(data, "motif")
        required = ["name", "description"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing motif fields: {', '.join(missing)}")
        return cls(
            name=str(data["name"]),
            description=str(data["description"]),
            rhythm_pattern=_float_list(data.get("rhythm_pattern", []), "motif.rhythm_pattern"),
            pitch_intervals=_int_list(data.get("pitch_intervals", []), "motif.pitch_intervals"),
            anchor_section=_optional_str(data.get("anchor_section")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectionIntent:
    section_name: str
    role: str
    energy: int
    tension: int
    density: int
    transition: str = ""
    hook: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionIntent":
        data = _require_mapping(data, "section_intent")
        if "section_name" not in data:
            raise ValueError("Missing section intent fields: section_name")
        return cls(
            section_name=str(data["section_name"]),
            role=str(data.get("role", "")),
            energy=_range_int(data, "energy", 0, 10, default=0),
            tension=_range_int(data, "tension", 0, 10, default=0),
            density=_range_int(data, "density", 0, 10, default=0),
            transition=str(data.get("transition", "")),
            hook=bool(data.get("hook", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityScores:
    overall: int
    structure: int
    melody: int
    harmony: int
    arrangement: int
    lyric_fit: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityScores":
        data = _require_mapping(data, "quality_scores")
        required = ["overall", "structure", "melody", "harmony", "arrangement"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing quality score fields: {', '.join(missing)}")
        return cls(
            overall=_range_int(data, "overall", 0, 100),
            structure=_range_int(data, "structure", 0, 100),
            melody=_range_int(data, "melody", 0, 100),
            harmony=_range_int(data, "harmony", 0, 100),
            arrangement=_range_int(data, "arrangement", 0, 100),
            lyric_fit=_range_int(data, "lyric_fit", 0, 100, default=0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SongQualityMeta:
    summary: str = ""
    primary_motif: MotifPlan | None = None
    section_intents: list[SectionIntent] = field(default_factory=list)
    hook_sections: list[str] = field(default_factory=list)
    scores: QualityScores | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongQualityMeta":
        data = _require_mapping(data, "quality")
        primary_motif = data.get("primary_motif")
        scores = data.get("scores")
        return cls(
            summary=str(data.get("summary", "")),
            primary_motif=None if primary_motif is None else MotifPlan.from_dict(primary_motif),
            section_intents=[
                SectionIntent.from_dict(intent)
                for intent in _require_list(data.get("section_intents", []), "quality.section_intents")
            ],
            hook_sections=[str(section) for section in _require_list(data.get("hook_sections", []), "quality.hook_sections")],
            scores=None if scores is None else QualityScores.from_dict(scores),
            warnings=[str(warning) for warning in _require_list(data.get("warnings", []), "quality.warnings")],
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
    quality: SongQualityMeta | None = None

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
        quality_data = data.get("quality")
        return cls(
            title=str(data["title"]),
            key=str(data["key"]),
            tempo_bpm=int(data["tempo_bpm"]),
            meter=str(data["meter"]),
            sections=sections,
            tracks=tracks,
            quality=None if quality_data is None else SongQualityMeta.from_dict(quality_data),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        from song_agent.domains.quality.quality import validate_song_plan

        validate_song_plan(self)
