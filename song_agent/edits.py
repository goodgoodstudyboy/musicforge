from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from song_agent.agent.pipeline import _bass_pitch, _chord_pitches
from song_agent.music_quality import attach_quality
from song_agent.schemas.song import NoteEvent, SectionIntent, SongPlan, SongSection, TrackPlan


EDIT_TYPES = {
    "section_energy",
    "section_harmony",
    "track_density",
    "lyrics_rewrite",
    "melody_variation",
    "arrangement_variation",
}
PROVIDER_MODES = {"local", "provider"}
PRESERVE_FIELDS = {"tempo", "key", "structure", "lyrics", "harmony", "melody", "arrangement"}
TARGET_FIELDS = {"lyrics", "chords", "notes", "instrument"}
EDIT_VARIANT_TYPES = {
    "section_energy": "section_edit",
    "section_harmony": "section_edit",
    "track_density": "track_edit",
    "lyrics_rewrite": "lyrics_edit",
    "melody_variation": "melody_edit",
    "arrangement_variation": "arrangement_edit",
}
SUPPORTED_EDIT_TYPES = sorted(EDIT_TYPES)
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EditTarget:
    section_name: str | None = None
    track_name: str | None = None
    field: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EditTarget":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("target must be an object.")
        field_value = _optional_str(data.get("field"))
        if field_value is not None and field_value not in TARGET_FIELDS:
            raise ValueError(f"target.field must be one of: {', '.join(sorted(TARGET_FIELDS))}.")
        return cls(
            section_name=_optional_str(data.get("section_name")),
            track_name=_optional_str(data.get("track_name")),
            field=field_value,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EditIntent:
    edit_type: str
    target: EditTarget = field(default_factory=EditTarget)
    instruction: str = ""
    preserve: list[str] = field(default_factory=list)
    strength: int = 5
    provider_mode: str = "local"
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditIntent":
        if not isinstance(data, dict):
            raise ValueError("edit intent must be an object.")
        edit_type = str(data.get("edit_type") or "").strip()
        if edit_type not in EDIT_TYPES:
            raise ValueError(f"edit_type must be one of: {', '.join(sorted(EDIT_TYPES))}.")
        strength = int(data.get("strength", 5) or 5)
        if strength < 1 or strength > 10:
            raise ValueError("strength must be between 1 and 10.")
        provider_mode = str(data.get("provider_mode") or "local").strip()
        if provider_mode not in PROVIDER_MODES:
            raise ValueError("provider_mode must be either local or provider.")
        preserve = data.get("preserve", [])
        if preserve is None:
            preserve = []
        if not isinstance(preserve, list):
            raise ValueError("preserve must be a list.")
        clean_preserve = [str(item).strip() for item in preserve if str(item).strip()]
        unsupported = sorted(set(clean_preserve) - PRESERVE_FIELDS)
        if unsupported:
            raise ValueError(f"preserve contains unsupported fields: {', '.join(unsupported)}.")
        payload = data.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object.")
        return cls(
            edit_type=edit_type,
            target=EditTarget.from_dict(data.get("target")),
            instruction=str(data.get("instruction") or "").strip(),
            preserve=clean_preserve,
            strength=strength,
            provider_mode=provider_mode,
            payload=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "edit_type": self.edit_type,
            "target": self.target.to_dict(),
            "instruction": self.instruction,
            "preserve": list(self.preserve),
            "strength": self.strength,
            "provider_mode": self.provider_mode,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class EditedSongPlanResult:
    plan: SongPlan
    summary: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def apply_edit_intent(parent_plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    _validate_intent_target(parent_plan, intent)
    if intent.provider_mode == "provider":
        raise NotImplementedError("Provider-backed edit is not implemented in v1.1.0.")

    if intent.edit_type == "section_energy":
        result = _apply_section_energy(parent_plan, intent)
    elif intent.edit_type == "section_harmony":
        result = _apply_section_harmony(parent_plan, intent)
    elif intent.edit_type == "track_density":
        result = _apply_track_density(parent_plan, intent)
    elif intent.edit_type == "lyrics_rewrite":
        result = _apply_lyrics_rewrite(parent_plan, intent)
    elif intent.edit_type == "melody_variation":
        result = _apply_melody_variation(parent_plan, intent)
    elif intent.edit_type == "arrangement_variation":
        result = _apply_arrangement_variation(parent_plan, intent)
    else:
        raise ValueError(f"Unsupported edit_type: {intent.edit_type}.")

    plan = attach_quality(result.plan)
    plan.validate()
    summary = {
        "edit_type": intent.edit_type,
        "target": intent.target.to_dict(),
        "preserved": list(intent.preserve),
        **result.summary,
    }
    return EditedSongPlanResult(plan=plan, summary=summary, warnings=result.warnings)


def validate_edit_intent(parent_plan: SongPlan, intent: EditIntent) -> None:
    _validate_intent_target(parent_plan, intent)


def edit_variant_type(edit_type: str) -> str:
    if edit_type not in EDIT_VARIANT_TYPES:
        raise ValueError(f"Unsupported edit_type: {edit_type}.")
    return EDIT_VARIANT_TYPES[edit_type]


def edit_change_summary(intent: EditIntent, summary: dict[str, Any] | None = None) -> str:
    target = []
    if intent.target.section_name:
        target.append(f"section {intent.target.section_name}")
    if intent.target.track_name:
        target.append(f"track {intent.target.track_name}")
    if intent.target.field:
        target.append(f"field {intent.target.field}")
    target_text = ", ".join(target) if target else "song"
    changed = ", ".join((summary or {}).get("changed_tracks", []) or (summary or {}).get("changed_sections", []))
    if changed:
        return f"{intent.edit_type} on {target_text}: {changed}"
    return f"{intent.edit_type} on {target_text}"


def build_edit_metadata(
    *,
    project_id: str,
    parent_version_id: str,
    parent_job_id: str,
    intent: EditIntent,
    created_at: str,
    summary: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "parent_version_id": parent_version_id,
        "parent_job_id": parent_job_id,
        **intent.to_dict(),
        "summary": summary or {},
        "warnings": warnings or [],
        "created_at": created_at,
    }


def build_edit_targets(plan: SongPlan) -> dict[str, Any]:
    return {
        "sections": [
            {
                "name": section.name,
                "bars": section.bars,
                "start_bar": section.start_bar,
                "lyrics": section.lyrics,
                "chords": list(section.chords),
            }
            for section in plan.sections
        ],
        "tracks": [
            {
                "name": track.name,
                "instrument": track.instrument,
                "note_count": len(track.notes),
            }
            for track in plan.tracks
        ],
        "supported_edit_types": SUPPORTED_EDIT_TYPES,
        "supported_preserve": sorted(PRESERVE_FIELDS),
        "supported_fields": sorted(TARGET_FIELDS),
    }


def _validate_intent_target(plan: SongPlan, intent: EditIntent) -> None:
    if intent.target.section_name is not None:
        _find_section(plan, intent.target.section_name)
    if intent.target.track_name is not None:
        _find_track(plan, intent.target.track_name)

    if intent.edit_type in {"section_energy", "section_harmony", "lyrics_rewrite", "melody_variation"} and not intent.target.section_name:
        raise ValueError(f"{intent.edit_type} requires target.section_name.")
    if intent.edit_type == "track_density" and not intent.target.track_name:
        raise ValueError("track_density requires target.track_name.")
    if intent.edit_type == "lyrics_rewrite" and intent.target.field not in {None, "lyrics"}:
        raise ValueError("lyrics_rewrite target.field must be lyrics when provided.")
    if intent.edit_type == "section_harmony" and intent.target.field not in {None, "chords"}:
        raise ValueError("section_harmony target.field must be chords when provided.")
    if intent.edit_type == "melody_variation":
        track = _track_by_role(plan, "melody")
        if track is None:
            raise ValueError("melody_variation requires a melody track.")


def _apply_section_energy(plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    section = _find_section(plan, intent.target.section_name or "")
    start, end = _section_range(section)
    lift = intent.strength >= 6
    delta = 8 if lift else -8
    changed_tracks = []
    tracks = []
    for track in plan.tracks:
        role = _track_role(track.name)
        notes = []
        changed = False
        for note in track.notes:
            if start <= note.start_beat < end and (lift or role != "melody"):
                notes.append(replace(note, velocity=_clamp(note.velocity + delta, 1, 127)))
                changed = True
            else:
                notes.append(note)
        if lift and role == "drums":
            notes, added = _add_chorus_backbeat(notes, section)
            changed = changed or added
        elif not lift and role == "drums":
            notes, removed = _thin_notes(notes, section, keep_first=True)
            changed = changed or removed
        if changed:
            changed_tracks.append(track.name)
        tracks.append(replace(track, notes=sorted(notes, key=lambda item: (item.start_beat, item.pitch))))
    edited = _replace_quality_intent(replace(plan, tracks=tracks), section.name, energy_delta=2 if lift else -2)
    return EditedSongPlanResult(
        plan=edited,
        summary={"changed_sections": [section.name], "changed_tracks": changed_tracks, "energy_delta": 2 if lift else -2},
    )


def _apply_section_harmony(plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    section = _find_section(plan, intent.target.section_name or "")
    chords = _parse_chords(intent.payload.get("chords") or intent.instruction)
    if not chords:
        chords = ["Am7", "Fmaj7", "Dm7", "E7"] if "minor" in plan.key.lower() else ["Cmaj7", "Am7", "Fmaj7", "G7"]
    sections = [
        replace(item, chords=chords)
        if item.name == section.name
        else item
        for item in plan.sections
    ]
    tracks = []
    changed_tracks = []
    for track in plan.tracks:
        role = _track_role(track.name)
        if role == "chords":
            tracks.append(replace(track, notes=_replace_section_notes(track.notes, section, _make_chord_notes_for_section(section, chords))))
            changed_tracks.append(track.name)
        elif role == "bass":
            tracks.append(replace(track, notes=_replace_section_notes(track.notes, section, _make_bass_notes_for_section(section, chords))))
            changed_tracks.append(track.name)
        else:
            tracks.append(track)
    return EditedSongPlanResult(
        plan=replace(plan, sections=sections, tracks=tracks),
        summary={"changed_sections": [section.name], "changed_tracks": changed_tracks, "chords": chords},
    )


def _apply_track_density(plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    track = _find_track(plan, intent.target.track_name or "")
    section = _find_section(plan, intent.target.section_name) if intent.target.section_name else None
    section_start, section_end = _section_range(section) if section else (0.0, _song_end_beat(plan))
    role = _track_role(track.name)
    selected = [note for note in track.notes if section_start <= note.start_beat < section_end]
    outside = [note for note in track.notes if not (section_start <= note.start_beat < section_end)]
    if intent.strength >= 6:
        additions = []
        limit = max(1, min(len(selected), int(len(selected) * 0.35)))
        for note in selected[:limit]:
            offset = 0.5 if role != "drums" else 0.25
            start = note.start_beat + offset
            if start + note.duration_beats <= section_end:
                additions.append(replace(note, start_beat=round(start, 3), velocity=_clamp(note.velocity - 8, 1, 127)))
        new_selected = selected + additions
        changed = bool(additions)
    else:
        new_selected, changed = _thin_selected_notes(selected, role)
    tracks = [
        replace(item, notes=sorted([*outside, *new_selected], key=lambda note: (note.start_beat, note.pitch)))
        if item.name == track.name
        else item
        for item in plan.tracks
    ]
    return EditedSongPlanResult(
        plan=replace(plan, tracks=tracks),
        summary={
            "changed_sections": [section.name] if section else [item.name for item in plan.sections],
            "changed_tracks": [track.name] if changed else [],
            "note_count_before": len(track.notes),
            "note_count_after": len(outside) + len(new_selected),
        },
    )


def _apply_lyrics_rewrite(plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    section = _find_section(plan, intent.target.section_name or "")
    lyrics = intent.payload.get("lyrics")
    if lyrics is None or not str(lyrics).strip():
        lyrics = _placeholder_lyrics(section.name, intent.instruction)
    sections = [
        replace(item, lyrics=str(lyrics))
        if item.name == section.name
        else item
        for item in plan.sections
    ]
    return EditedSongPlanResult(
        plan=replace(plan, sections=sections, quality=None),
        summary={"changed_sections": [section.name], "changed_fields": ["lyrics"]},
    )


def _apply_melody_variation(plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    section = _find_section(plan, intent.target.section_name or "")
    start, end = _section_range(section)
    changed = False
    tracks = []
    for track in plan.tracks:
        if _track_role(track.name) != "melody":
            tracks.append(track)
            continue
        notes = []
        for index, note in enumerate(track.notes):
            if start <= note.start_beat < end:
                shift = 1 if index % 2 == 0 else 2
                if intent.strength <= 4:
                    shift = -1
                notes.append(replace(note, pitch=_clamp(note.pitch + shift, 0, 127)))
                changed = True
            else:
                notes.append(note)
        tracks.append(replace(track, notes=notes))
    return EditedSongPlanResult(
        plan=replace(plan, tracks=tracks, quality=None),
        summary={"changed_sections": [section.name], "changed_tracks": ["melody"] if changed else []},
    )


def _apply_arrangement_variation(plan: SongPlan, intent: EditIntent) -> EditedSongPlanResult:
    if intent.target.track_name:
        target_track = _find_track(plan, intent.target.track_name)
    else:
        target_track = None
    instrument = _optional_str(intent.payload.get("instrument"))
    if target_track is None and not instrument:
        density_intent = replace(intent, edit_type="track_density", target=replace(intent.target, track_name="drums"))
        return _apply_track_density(plan, density_intent)
    tracks = []
    changed_tracks = []
    for track in plan.tracks:
        if target_track is not None and track.name != target_track.name:
            tracks.append(track)
            continue
        tracks.append(replace(track, instrument=instrument or f"{track.instrument} alt"))
        changed_tracks.append(track.name)
    return EditedSongPlanResult(
        plan=replace(plan, tracks=tracks, quality=None),
        summary={"changed_tracks": changed_tracks, "changed_fields": ["instrument"]},
    )


def _find_section(plan: SongPlan, section_name: str | None) -> SongSection:
    if not section_name:
        raise ValueError("target.section_name is required.")
    for section in plan.sections:
        if section.name.lower() == section_name.lower():
            return section
    raise ValueError(f"Section not found: {section_name}.")


def _find_track(plan: SongPlan, track_name: str | None) -> TrackPlan:
    if not track_name:
        raise ValueError("target.track_name is required.")
    for track in plan.tracks:
        if track.name.lower() == track_name.lower():
            return track
    for track in plan.tracks:
        if track_name.lower() in track.name.lower():
            return track
    raise ValueError(f"Track not found: {track_name}.")


def _track_by_role(plan: SongPlan, role: str) -> TrackPlan | None:
    for track in plan.tracks:
        if role in track.name.lower():
            return track
    return None


def _section_range(section: SongSection) -> tuple[float, float]:
    start = float((section.start_bar - 1) * 4)
    return start, start + float(section.bars * 4)


def _song_end_beat(plan: SongPlan) -> float:
    return max(float((section.start_bar - 1 + section.bars) * 4) for section in plan.sections)


def _replace_quality_intent(plan: SongPlan, section_name: str, *, energy_delta: int) -> SongPlan:
    if plan.quality is None:
        return replace(plan, quality=None)
    intents = []
    found = False
    for intent in plan.quality.section_intents:
        if intent.section_name.lower() == section_name.lower():
            intents.append(replace(intent, energy=_clamp(intent.energy + energy_delta, 0, 10)))
            found = True
        else:
            intents.append(intent)
    if not found:
        intents.append(SectionIntent(section_name=section_name, role="section", energy=_clamp(5 + energy_delta, 0, 10), tension=5, density=5))
    return replace(plan, quality=replace(plan.quality, section_intents=intents))


def _add_chorus_backbeat(notes: list[NoteEvent], section: SongSection) -> tuple[list[NoteEvent], bool]:
    existing = {(round(note.start_beat, 3), note.pitch) for note in notes}
    added = []
    start, _end = _section_range(section)
    for bar_offset in range(section.bars):
        bar_start = start + bar_offset * 4
        for beat_offset, pitch, velocity in ((1, 38, 94), (3, 38, 94), (0, 49, 82)):
            key = (round(bar_start + beat_offset, 3), pitch)
            if key not in existing:
                added.append(NoteEvent(pitch, float(bar_start + beat_offset), 0.25, velocity))
    return [*notes, *added], bool(added)


def _thin_notes(notes: list[NoteEvent], section: SongSection, *, keep_first: bool = False) -> tuple[list[NoteEvent], bool]:
    start, end = _section_range(section)
    result = []
    removed = False
    for index, note in enumerate(notes):
        if start <= note.start_beat < end and index % 4 == 3 and not (keep_first and note.start_beat == start):
            removed = True
            continue
        result.append(note)
    return result, removed


def _thin_selected_notes(notes: list[NoteEvent], role: str) -> tuple[list[NoteEvent], bool]:
    if len(notes) <= 2:
        return notes, False
    result = []
    for index, note in enumerate(notes):
        keep_anchor = index == 0 or (role in {"drums", "bass", "melody"} and abs(note.start_beat % 4) < 0.001)
        if keep_anchor or index % 3 != 2:
            result.append(note)
    return result or notes[:1], len(result) != len(notes)


def _replace_section_notes(existing: list[NoteEvent], section: SongSection, replacement: list[NoteEvent]) -> list[NoteEvent]:
    start, end = _section_range(section)
    outside = [note for note in existing if not (start <= note.start_beat < end)]
    return sorted([*outside, *replacement], key=lambda item: (item.start_beat, item.pitch))


def _make_chord_notes_for_section(section: SongSection, chords: list[str]) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    section_start_beat = (section.start_bar - 1) * 4
    for bar_offset in range(section.bars):
        chord_name = chords[bar_offset % len(chords)]
        start_beat = section_start_beat + bar_offset * 4
        for pitch in _chord_pitches(chord_name):
            notes.append(NoteEvent(pitch, float(start_beat), 3.75, 72))
    return notes


def _make_bass_notes_for_section(section: SongSection, chords: list[str]) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    section_start_beat = (section.start_bar - 1) * 4
    for bar_offset in range(section.bars):
        chord_name = chords[bar_offset % len(chords)]
        root = _bass_pitch(chord_name)
        start_beat = section_start_beat + bar_offset * 4
        for beat_offset in (0, 2):
            notes.append(NoteEvent(root, float(start_beat + beat_offset), 1.75, 84))
    return notes


def _parse_chords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(chord).strip() for chord in value if str(chord).strip()][:8]
    text = str(value or "")
    candidates = re.findall(r"\b[A-G](?:#|b)?(?:maj7|m7|dim|aug|sus4|sus2|m|7)?\b", text)
    return candidates[:8]


def _placeholder_lyrics(section_name: str, instruction: str) -> str:
    seed = instruction.strip().rstrip(".") or f"new words for {section_name}"
    return f"{seed}\n{section_name} turns the story into a clearer hook"


def _track_role(track_name: str) -> str:
    lower = track_name.lower()
    for role in ("melody", "chords", "bass", "drums"):
        if role in lower:
            return role
    return lower.strip()


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
