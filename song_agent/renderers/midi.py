from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from song_agent.schemas.song import NoteEvent, SongPlan


TICKS_PER_BEAT = 480
CHANNELS_BY_ROLE = {
    "melody": 0,
    "chords": 1,
    "bass": 2,
    "drums": 9,
}
PROGRAMS_BY_ROLE = {
    "melody": 81,
    "chords": 4,
    "bass": 33,
}


@dataclass(frozen=True)
class MidiEvent:
    tick: int
    priority: int
    payload: bytes


def render_midi(plan: SongPlan, output_path: Path) -> Path:
    """Render a SongPlan to a type-1 Standard MIDI file."""
    plan.validate()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tracks = [_meta_track(plan)]
    for track in plan.tracks:
        role = _track_role(track.name)
        channel = CHANNELS_BY_ROLE.get(role, 0)
        program = PROGRAMS_BY_ROLE.get(role)
        tracks.append(_music_track(track.notes, channel=channel, program=program))

    data = _header_chunk(len(tracks)) + b"".join(tracks)
    output_path.write_bytes(data)
    return output_path


def render_midi_stem(plan: SongPlan, track_index: int, output_path: Path) -> Path:
    """Render one SongPlan track to a type-1 Standard MIDI stem file."""
    if track_index < 0 or track_index >= len(plan.tracks):
        raise ValueError("track_index is out of range.")
    track = plan.tracks[track_index]
    if not track.notes:
        raise ValueError("Cannot render an empty MIDI stem.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    role = _track_role(track.name)
    channel = CHANNELS_BY_ROLE.get(role, 0)
    program = PROGRAMS_BY_ROLE.get(role)
    tracks = [
        _meta_track(plan),
        _music_track(track.notes, channel=channel, program=program),
    ]
    output_path.write_bytes(_header_chunk(len(tracks)) + b"".join(tracks))
    return output_path


def _header_chunk(track_count: int) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, 1, track_count, TICKS_PER_BEAT)


def _meta_track(plan: SongPlan) -> bytes:
    tempo_microseconds = int(60_000_000 / plan.tempo_bpm)
    title = plan.title.encode("utf-8")
    events = [
        MidiEvent(0, 0, b"\xff\x03" + _var_len(len(title)) + title),
        MidiEvent(0, 1, b"\xff\x58\x04\x04\x02\x18\x08"),
        MidiEvent(0, 2, b"\xff\x51\x03" + tempo_microseconds.to_bytes(3, "big")),
    ]
    return _track_chunk(events)


def _music_track(
    notes: list[NoteEvent],
    *,
    channel: int,
    program: int | None,
) -> bytes:
    events: list[MidiEvent] = []
    if program is not None:
        events.append(MidiEvent(0, 0, bytes([0xC0 | channel, program])))

    for note in notes:
        start_tick = round(note.start_beat * TICKS_PER_BEAT)
        end_tick = round((note.start_beat + note.duration_beats) * TICKS_PER_BEAT)
        events.append(
            MidiEvent(
                tick=start_tick,
                priority=1,
                payload=bytes([0x90 | channel, note.pitch, note.velocity]),
            )
        )
        events.append(
            MidiEvent(
                tick=end_tick,
                priority=0,
                payload=bytes([0x80 | channel, note.pitch, 0]),
            )
        )

    return _track_chunk(events)


def _track_chunk(events: list[MidiEvent]) -> bytes:
    body = bytearray()
    last_tick = 0
    for event in sorted(events, key=lambda item: (item.tick, item.priority)):
        delta = event.tick - last_tick
        body.extend(_var_len(delta))
        body.extend(event.payload)
        last_tick = event.tick

    body.extend(_var_len(0))
    body.extend(b"\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _var_len(value: int) -> bytes:
    if value < 0:
        raise ValueError("MIDI delta times cannot be negative.")
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
        value >>= 7

    result = bytearray()
    while True:
        result.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(result)


def _track_role(name: str) -> str:
    lower_name = name.lower()
    for role in CHANNELS_BY_ROLE:
        if role in lower_name:
            return role
    return lower_name.strip()
