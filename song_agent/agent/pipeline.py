from __future__ import annotations

from dataclasses import dataclass

from song_agent.music_quality import attach_quality
from song_agent.providers.base import LLMProvider
from song_agent.schemas.song import NoteEvent, SongPlan, SongRequest, SongSection, TrackPlan


@dataclass
class SongAgent:
    provider: LLMProvider | None = None

    def generate(self, request: SongRequest) -> SongPlan:
        """Run the fixed songwriting workflow."""
        plan = deterministic_compose(request)
        plan.validate()
        return plan


def deterministic_compose(request: SongRequest) -> SongPlan:
    tempo_bpm = request.tempo_bpm or 92
    key = request.key or "C major"
    sections = _make_sections(request)
    total_bars = sum(section.bars for section in sections)

    tracks = [
        TrackPlan(
            name="melody",
            instrument="lead",
            notes=_make_melody_for_sections(sections),
        ),
        TrackPlan(
            name="chords",
            instrument="electric piano",
            notes=_make_chord_notes(sections),
        ),
        TrackPlan(
            name="bass",
            instrument="electric bass",
            notes=_make_bass_notes(sections),
        ),
        TrackPlan(
            name="drums",
            instrument="gm drums",
            notes=_make_drum_notes_for_sections(sections),
        ),
    ]
    plan = SongPlan(
        title=request.title,
        key=key,
        tempo_bpm=tempo_bpm,
        meter="4/4",
        sections=sections,
        tracks=tracks,
    )
    return attach_quality(plan)


def _make_sections(request: SongRequest) -> list[SongSection]:
    section_specs = [
        ("intro", 1, 4),
        ("verse", 5, 8),
        ("chorus", 13, 8),
        ("outro", 21, 4),
    ]
    chords = ["Cmaj7", "Am7", "Dm7", "G7"]
    return [
        SongSection(
            name=name,
            start_bar=start_bar,
            bars=bars,
            chords=chords,
            lyrics=request.lyrics if name == "verse" else None,
        )
        for name, start_bar, bars in section_specs
    ]


def _make_melody(total_beats: int) -> list[NoteEvent]:
    motif = [64, 67, 69, 71, 72, 71, 69, 67]
    notes: list[NoteEvent] = []
    for beat in range(0, total_beats, 2):
        pitch = motif[(beat // 2) % len(motif)]
        duration = 1.5 if beat + 1.5 <= total_beats else total_beats - beat
        notes.append(
            NoteEvent(
                pitch=pitch,
                start_beat=float(beat),
                duration_beats=float(duration),
                velocity=92,
            )
        )
    return notes


def _make_melody_for_sections(sections: list[SongSection]) -> list[NoteEvent]:
    motif = [64, 67, 69, 71, 72, 71, 69, 67]
    notes: list[NoteEvent] = []
    for section in sections:
        section_start = (section.start_bar - 1) * 4
        total_beats = section.bars * 4
        lower_name = section.name.lower()
        transpose = 5 if "chorus" in lower_name else -2 if "outro" in lower_name else 0
        velocity = 104 if "chorus" in lower_name else 86 if "intro" in lower_name else 94
        for beat in range(0, total_beats, 2):
            pitch = motif[(beat // 2) % len(motif)] + transpose
            duration = 1.5 if beat + 1.5 <= total_beats else total_beats - beat
            notes.append(
                NoteEvent(
                    pitch=pitch,
                    start_beat=float(section_start + beat),
                    duration_beats=float(duration),
                    velocity=velocity,
                )
            )
    return notes


def _make_chord_notes(sections: list[SongSection]) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for section in sections:
        section_start_beat = (section.start_bar - 1) * 4
        for bar_offset in range(section.bars):
            chord_name = section.chords[bar_offset % len(section.chords)]
            start_beat = section_start_beat + bar_offset * 4
            for pitch in _chord_pitches(chord_name):
                notes.append(
                    NoteEvent(
                        pitch=pitch,
                        start_beat=float(start_beat),
                        duration_beats=3.75,
                        velocity=72,
                    )
                )
    return notes


def _make_bass_notes(sections: list[SongSection]) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for section in sections:
        section_start_beat = (section.start_bar - 1) * 4
        for bar_offset in range(section.bars):
            chord_name = section.chords[bar_offset % len(section.chords)]
            root = _bass_pitch(chord_name)
            start_beat = section_start_beat + bar_offset * 4
            for beat_offset in (0, 2):
                notes.append(
                    NoteEvent(
                        pitch=root,
                        start_beat=float(start_beat + beat_offset),
                        duration_beats=1.75,
                        velocity=84,
                    )
                )
    return notes


def _make_drum_notes(total_bars: int) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for bar in range(total_bars):
        bar_start = bar * 4
        for beat in range(4):
            notes.append(
                NoteEvent(
                    pitch=42,
                    start_beat=float(bar_start + beat),
                    duration_beats=0.25,
                    velocity=58,
                )
            )
        for beat_offset in (0, 2):
            notes.append(
                NoteEvent(
                    pitch=36,
                    start_beat=float(bar_start + beat_offset),
                    duration_beats=0.25,
                    velocity=96,
                )
            )
        for beat_offset in (1, 3):
            notes.append(
                NoteEvent(
                    pitch=38,
                    start_beat=float(bar_start + beat_offset),
                    duration_beats=0.25,
                    velocity=88,
                )
            )
    return notes


def _make_drum_notes_for_sections(sections: list[SongSection]) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for section in sections:
        section_start_bar = section.start_bar - 1
        lower_name = section.name.lower()
        for bar_offset in range(section.bars):
            bar_start = (section_start_bar + bar_offset) * 4
            if "intro" in lower_name:
                hat_beats = (0, 2)
                kicks = (0,)
                snares = ()
            elif "chorus" in lower_name:
                hat_beats = (0, 1, 2, 3)
                kicks = (0, 2)
                snares = (1, 3)
                notes.append(NoteEvent(49, float(bar_start), 0.25, 88))
            else:
                hat_beats = (0, 1, 2, 3)
                kicks = (0, 2)
                snares = (1, 3)
            for beat in hat_beats:
                notes.append(NoteEvent(42, float(bar_start + beat), 0.25, 58))
            for beat in kicks:
                notes.append(NoteEvent(36, float(bar_start + beat), 0.25, 96))
            for beat in snares:
                notes.append(NoteEvent(38, float(bar_start + beat), 0.25, 88))
    return notes


def _chord_pitches(chord_name: str) -> list[int]:
    chord_map = {
        "Cmaj7": [60, 64, 67, 71],
        "Am7": [57, 60, 64, 67],
        "Dm7": [62, 65, 69, 72],
        "Fmaj7": [53, 57, 60, 64],
        "G7": [55, 59, 62, 65],
        "E7": [52, 56, 59, 62],
    }
    return chord_map.get(chord_name, [60, 64, 67])


def _bass_pitch(chord_name: str) -> int:
    root_map = {
        "Cmaj7": 36,
        "Am7": 33,
        "Dm7": 38,
        "Fmaj7": 29,
        "G7": 31,
        "E7": 28,
    }
    return root_map.get(chord_name, 36)
