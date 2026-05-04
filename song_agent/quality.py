from __future__ import annotations

from song_agent.schemas.song import SongPlan


REQUIRED_TRACKS = {"melody", "chords", "bass", "drums"}


def validate_song_plan(plan: SongPlan) -> None:
    """Validate hard rules that renderers and downstream tools rely on."""
    if not plan.title.strip():
        raise ValueError("SongPlan.title must not be empty.")
    if not plan.key.strip():
        raise ValueError("SongPlan.key must not be empty.")
    if plan.tempo_bpm < 40 or plan.tempo_bpm > 240:
        raise ValueError("SongPlan.tempo_bpm must be between 40 and 240.")
    if plan.meter != "4/4":
        raise ValueError("MVP only supports 4/4 meter.")
    if not plan.sections:
        raise ValueError("SongPlan.sections must not be empty.")
    if not plan.tracks:
        raise ValueError("SongPlan.tracks must not be empty.")

    total_bars = _validate_sections(plan)
    total_beats = total_bars * 4
    _validate_tracks(plan, total_beats)


def _validate_sections(plan: SongPlan) -> int:
    expected_start = 1
    total_bars = 0
    for section in plan.sections:
        if not section.name.strip():
            raise ValueError("SongSection.name must not be empty.")
        if section.start_bar < 1:
            raise ValueError(f"Section {section.name} start_bar must be >= 1.")
        if section.bars <= 0:
            raise ValueError(f"Section {section.name} bars must be > 0.")
        if section.start_bar != expected_start:
            raise ValueError(
                f"Section {section.name} must start at bar {expected_start}."
            )
        if not section.chords:
            raise ValueError(f"Section {section.name} must include chords.")
        if any(not chord.strip() for chord in section.chords):
            raise ValueError(f"Section {section.name} contains an empty chord.")

        expected_start += section.bars
        total_bars += section.bars

    return total_bars


def _validate_tracks(plan: SongPlan, total_beats: int) -> None:
    normalized_names = {_track_role(track.name) for track in plan.tracks}
    missing = sorted(REQUIRED_TRACKS - normalized_names)
    if missing:
        raise ValueError(f"SongPlan is missing required tracks: {', '.join(missing)}.")

    for track in plan.tracks:
        if not track.name.strip():
            raise ValueError("TrackPlan.name must not be empty.")
        if not track.instrument.strip():
            raise ValueError(f"Track {track.name} instrument must not be empty.")
        if not track.notes:
            raise ValueError(f"Track {track.name} must contain notes.")

        for note in track.notes:
            if note.pitch < 0 or note.pitch > 127:
                raise ValueError(f"Track {track.name} has pitch outside 0..127.")
            if note.velocity < 1 or note.velocity > 127:
                raise ValueError(f"Track {track.name} has velocity outside 1..127.")
            if note.start_beat < 0:
                raise ValueError(f"Track {track.name} has negative start_beat.")
            if note.duration_beats <= 0:
                raise ValueError(f"Track {track.name} has non-positive duration.")
            if note.start_beat + note.duration_beats > total_beats + 0.001:
                raise ValueError(f"Track {track.name} has notes beyond song length.")


def _track_role(name: str) -> str:
    lower_name = name.lower()
    for role in REQUIRED_TRACKS:
        if role in lower_name:
            return role
    return lower_name.strip()
