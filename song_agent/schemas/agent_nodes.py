from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from song_agent.schemas.song import NoteEvent


def _require_mapping(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be an object.")
    return data


def _require_list(data: Any, name: str) -> list[Any]:
    if not isinstance(data, list):
        raise ValueError(f"{name} must be a list.")
    return data


def _string_list(data: Any, name: str) -> list[str]:
    return [str(item) for item in _require_list(data, name)]


def _validated_note(data: dict[str, Any]) -> NoteEvent:
    note = NoteEvent.from_dict(data)
    if note.pitch < 0 or note.pitch > 127:
        raise ValueError("note.pitch must be between 0 and 127.")
    if note.velocity < 1 or note.velocity > 127:
        raise ValueError("note.velocity must be between 1 and 127.")
    if note.start_beat < 0:
        raise ValueError("note.start_beat must be >= 0.")
    if note.duration_beats <= 0:
        raise ValueError("note.duration_beats must be > 0.")
    return note


@dataclass(frozen=True)
class SongBrief:
    title: str
    language: str
    style: str
    theme: str
    duration_seconds: int
    vocal_mode: str
    tempo_bpm: int
    key: str
    target_listener: str | None = None
    use_case: str | None = None
    mood_tags: list[str] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongBrief":
        data = _require_mapping(data, "song_brief")
        required = [
            "title",
            "language",
            "style",
            "theme",
            "duration_seconds",
            "vocal_mode",
            "tempo_bpm",
            "key",
        ]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing song brief fields: {', '.join(missing)}")
        return cls(
            title=str(data["title"]),
            language=str(data["language"]),
            style=str(data["style"]),
            theme=str(data["theme"]),
            duration_seconds=int(data["duration_seconds"]),
            vocal_mode=str(data["vocal_mode"]),
            tempo_bpm=int(data["tempo_bpm"]),
            key=str(data["key"]),
            target_listener=_optional_str(data.get("target_listener")),
            use_case=_optional_str(data.get("use_case")),
            mood_tags=_string_list(data.get("mood_tags", []), "mood_tags"),
            must_include=_string_list(data.get("must_include", []), "must_include"),
            avoid=_string_list(data.get("avoid", []), "avoid"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SonicPalette:
    genre_tags: list[str]
    instrumentation: list[str]
    lead_instrument: str
    bass_style: str
    drum_style: str
    texture_notes: str = ""
    mix_notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SonicPalette":
        data = _require_mapping(data, "sonic_palette")
        required = [
            "genre_tags",
            "instrumentation",
            "lead_instrument",
            "bass_style",
            "drum_style",
        ]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing sonic palette fields: {', '.join(missing)}")
        return cls(
            genre_tags=_string_list(data["genre_tags"], "genre_tags"),
            instrumentation=_string_list(data["instrumentation"], "instrumentation"),
            lead_instrument=str(data["lead_instrument"]),
            bass_style=str(data["bass_style"]),
            drum_style=str(data["drum_style"]),
            texture_notes=str(data.get("texture_notes", "")),
            mix_notes=str(data.get("mix_notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructureSectionPlan:
    name: str
    start_bar: int
    bars: int
    energy: int
    purpose: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructureSectionPlan":
        data = _require_mapping(data, "structure_section")
        required = ["name", "start_bar", "bars", "energy", "purpose"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing structure section fields: {', '.join(missing)}")
        return cls(
            name=str(data["name"]),
            start_bar=int(data["start_bar"]),
            bars=int(data["bars"]),
            energy=int(data["energy"]),
            purpose=str(data["purpose"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructurePlan:
    meter: str
    sections: list[StructureSectionPlan]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructurePlan":
        data = _require_mapping(data, "structure_plan")
        required = ["meter", "sections"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing structure plan fields: {', '.join(missing)}")
        return cls(
            meter=str(data["meter"]),
            sections=[
                StructureSectionPlan.from_dict(section)
                for section in _require_list(data["sections"], "sections")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LyricSection:
    section_name: str
    lyrics: str | None
    syllable_notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LyricSection":
        data = _require_mapping(data, "lyric_section")
        if "section_name" not in data:
            raise ValueError("Missing lyric section fields: section_name")
        return cls(
            section_name=str(data["section_name"]),
            lyrics=_optional_str(data.get("lyrics")),
            syllable_notes=_optional_str(data.get("syllable_notes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LyricPlan:
    language: str
    rhyme_style: str
    sections: list[LyricSection]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LyricPlan":
        data = _require_mapping(data, "lyric_plan")
        required = ["language", "rhyme_style", "sections"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing lyric plan fields: {', '.join(missing)}")
        return cls(
            language=str(data["language"]),
            rhyme_style=str(data["rhyme_style"]),
            sections=[
                LyricSection.from_dict(section)
                for section in _require_list(data["sections"], "sections")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectionHarmony:
    section_name: str
    chords: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionHarmony":
        data = _require_mapping(data, "section_harmony")
        required = ["section_name", "chords"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing section harmony fields: {', '.join(missing)}")
        return cls(
            section_name=str(data["section_name"]),
            chords=_string_list(data["chords"], "chords"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HarmonyPlan:
    key: str
    progressions: list[SectionHarmony]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HarmonyPlan":
        data = _require_mapping(data, "harmony_plan")
        required = ["key", "progressions"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing harmony plan fields: {', '.join(missing)}")
        return cls(
            key=str(data["key"]),
            progressions=[
                SectionHarmony.from_dict(progression)
                for progression in _require_list(data["progressions"], "progressions")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MelodyPhrase:
    section_name: str
    notes: list[NoteEvent]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MelodyPhrase":
        data = _require_mapping(data, "melody_phrase")
        required = ["section_name", "notes"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing melody phrase fields: {', '.join(missing)}")
        return cls(
            section_name=str(data["section_name"]),
            notes=[_validated_note(note) for note in _require_list(data["notes"], "notes")],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MelodyPlan:
    lead_instrument: str
    phrases: list[MelodyPhrase]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MelodyPlan":
        data = _require_mapping(data, "melody_plan")
        required = ["lead_instrument", "phrases"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing melody plan fields: {', '.join(missing)}")
        return cls(
            lead_instrument=str(data["lead_instrument"]),
            phrases=[
                MelodyPhrase.from_dict(phrase)
                for phrase in _require_list(data["phrases"], "phrases")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArrangementTrack:
    name: str
    instrument: str
    role: str
    notes: list[NoteEvent]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArrangementTrack":
        data = _require_mapping(data, "arrangement_track")
        required = ["name", "instrument", "role", "notes"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing arrangement track fields: {', '.join(missing)}")
        return cls(
            name=str(data["name"]),
            instrument=str(data["instrument"]),
            role=str(data["role"]),
            notes=[_validated_note(note) for note in _require_list(data["notes"], "notes")],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArrangementPlan:
    tracks: list[ArrangementTrack]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArrangementPlan":
        data = _require_mapping(data, "arrangement_plan")
        if "tracks" not in data:
            raise ValueError("Missing arrangement plan fields: tracks")
        return cls(
            tracks=[
                ArrangementTrack.from_dict(track)
                for track in _require_list(data["tracks"], "tracks")
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CriticIssue:
    severity: str
    code: str
    message: str
    target: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticIssue":
        data = _require_mapping(data, "critic_issue")
        required = ["severity", "code", "message"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing critic issue fields: {', '.join(missing)}")
        severity = str(data["severity"])
        if severity not in {"info", "warning", "error"}:
            raise ValueError("critic issue severity must be info, warning, or error.")
        return cls(
            severity=severity,
            code=str(data["code"]),
            message=str(data["message"]),
            target=_optional_str(data.get("target")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CriticReport:
    passed: bool
    score: int
    issues: list[CriticIssue]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticReport":
        data = _require_mapping(data, "critic_report")
        required = ["passed", "score", "issues"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing critic report fields: {', '.join(missing)}")
        return cls(
            passed=bool(data["passed"]),
            score=int(data["score"]),
            issues=[
                CriticIssue.from_dict(issue)
                for issue in _require_list(data["issues"], "issues")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairAction:
    target: str
    action: str
    reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepairAction":
        data = _require_mapping(data, "repair_action")
        required = ["target", "action", "reason"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing repair action fields: {', '.join(missing)}")
        return cls(
            target=str(data["target"]),
            action=str(data["action"]),
            reason=str(data["reason"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairPlan:
    applied: bool
    actions: list[RepairAction]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepairPlan":
        data = _require_mapping(data, "repair_plan")
        required = ["applied", "actions"]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing repair plan fields: {', '.join(missing)}")
        return cls(
            applied=bool(data["applied"]),
            actions=[
                RepairAction.from_dict(action)
                for action in _require_list(data["actions"], "actions")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
