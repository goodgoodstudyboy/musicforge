from __future__ import annotations

import struct

import pytest

from song_agent.midi_analysis import MidiParseError, midi_summary, notes_for_slice, parse_midi, render_slice_midi, suggest_slices


def vlq(value: int) -> bytes:
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80
        value >>= 7
    out = bytearray()
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            return bytes(out)


def track(events: list[tuple[int, bytes]]) -> bytes:
    body = bytearray()
    for delta, payload in events:
        body.extend(vlq(delta))
        body.extend(payload)
    body.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def midi_file(tracks: list[bytes], *, midi_format: int = 1, ppq: int = 480) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, midi_format, len(tracks), ppq) + b"".join(tracks)


def sample_midi() -> bytes:
    meta = track([(0, b"\xff\x51\x03\x07\xa1\x20"), (0, b"\xff\x58\x04\x04\x02\x18\x08")])
    melody = track([(0, b"\xc0\x51"), (0, b"\x90\x40\x64"), (480, b"\x40\x00"), (0, b"\x43\x64"), (480, b"\x80\x43\x00")])
    bass = track([(0, b"\xc2\x21"), (0, b"\x92\x24\x58"), (960, b"\x82\x24\x00")])
    drums = track([(0, b"\x99\x24\x60"), (120, b"\x89\x24\x00"), (360, b"\x99\x26\x60"), (120, b"\x89\x26\x00")])
    return midi_file([meta, melody, bass, drums])


def test_parse_midi_summary_running_status_and_roles() -> None:
    parsed = parse_midi(sample_midi())
    summary = midi_summary(parsed)

    assert summary["format"] == 1
    assert summary["track_count"] == 4
    assert summary["ppq"] == 480
    assert summary["tempo_bpm"] == 120
    assert summary["time_signature"] == "4/4"
    assert summary["note_count"] == 5
    assert summary["drum_note_count"] == 2
    roles = {track["likely_role"] for track in summary["track_summaries"]}
    assert {"melody", "bass", "drums"} <= roles


def test_parse_format0_and_velocity_zero_note_off() -> None:
    data = midi_file([track([(0, b"\x90\x3c\x40"), (240, b"\x3c\x00")])], midi_format=0)
    parsed = parse_midi(data)

    assert parsed.midi_format == 0
    assert len(parsed.notes) == 1
    assert parsed.notes[0].end_tick == 240


def test_malformed_midi_returns_clear_error() -> None:
    with pytest.raises(MidiParseError, match="MThd"):
        parse_midi(b"bad")
    with pytest.raises(MidiParseError, match="variable-length"):
        parse_midi(midi_file([b"MTrk" + struct.pack(">I", 5) + b"\x81\x82\x83\x84\x00"]))


def test_suggest_slices_render_and_extract_notes(tmp_path) -> None:
    parsed = parse_midi(sample_midi())
    slices = suggest_slices(parsed)
    motif = next(item for item in slices if item["slice_type"] == "motif")
    notes = notes_for_slice(parsed, motif)
    output = tmp_path / "slice.mid"

    render_slice_midi(parsed, motif, output)

    assert motif["slice_id"].startswith("slice-")
    assert notes[0]["start_beat"] == 0
    assert output.read_bytes().startswith(b"MThd")
