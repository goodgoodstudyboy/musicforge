from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import statistics as statistics
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan


class MidiParseError(ValueError):
    pass


MAX_MIDI_EVENTS = 100_000
MAX_MIDI_NOTES = 20_000
SUPPORTED_FORMATS = {0, 1}


@dataclass(frozen=True)
class MidiNote:
    track_index: int
    channel: int
    pitch: int
    start_tick: int
    end_tick: int
    velocity: int

    def to_dict(self, ppq: int, *, start_beat_offset: float = 0.0) -> dict[str, Any]:
        start = self.start_tick / ppq - start_beat_offset
        duration = max(1 / ppq, (self.end_tick - self.start_tick) / ppq)
        return {
            "pitch": self.pitch,
            "start_beat": round(max(0.0, start), 3),
            "duration_beats": round(duration, 3),
            "velocity": self.velocity,
            "channel": self.channel,
            "track_index": self.track_index,
        }


@dataclass(frozen=True)
class MidiTrack:
    track_index: int
    name: str = ""
    notes: list[MidiNote] = field(default_factory=list)
    programs: list[dict[str, int]] = field(default_factory=list)
    channels: list[int] = field(default_factory=list)
    end_tick: int = 0
    has_eot: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MidiFile:
    midi_format: int
    track_count: int
    ppq: int
    tracks: list[MidiTrack]
    tempos: list[dict[str, int]] = field(default_factory=list)
    time_signatures: list[dict[str, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def notes(self) -> list[MidiNote]:
        return [note for track in self.tracks for note in track.notes]


def parse_midi(data: bytes, *, max_events: int = MAX_MIDI_EVENTS, max_notes: int = MAX_MIDI_NOTES) -> MidiFile:
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiParseError("MIDI data must start with MThd.")
    header_length = _u32(data, 4)
    if header_length < 6:
        raise MidiParseError("MIDI header length is invalid.")
    if len(data) < 8 + header_length:
        raise MidiParseError("MIDI header is truncated.")
    midi_format = _u16(data, 8)
    if midi_format not in SUPPORTED_FORMATS:
        raise MidiParseError("Only MIDI format 0 and 1 are supported.")
    track_count = _u16(data, 10)
    division = _u16(data, 12)
    if division & 0x8000:
        raise MidiParseError("SMPTE MIDI division is not supported.")
    if division <= 0:
        raise MidiParseError("MIDI PPQ division must be positive.")

    offset = 8 + header_length
    tracks: list[MidiTrack] = []
    tempos: list[dict[str, int]] = []
    time_signatures: list[dict[str, int]] = []
    warnings: list[str] = []
    event_count = 0
    note_count = 0

    for track_index in range(track_count):
        if offset + 8 > len(data) or data[offset : offset + 4] != b"MTrk":
            raise MidiParseError("MIDI track chunk is missing or truncated.")
        track_length = _u32(data, offset + 4)
        offset += 8
        track_data = data[offset : offset + track_length]
        if len(track_data) != track_length:
            raise MidiParseError("MIDI track data is truncated.")
        offset += track_length
        parsed, track_events, track_notes, track_tempos, track_sigs = _parse_track(track_data, track_index, division, max_events=max_events - event_count)
        event_count += track_events
        note_count += track_notes
        if event_count > max_events:
            raise MidiParseError(f"MIDI event count exceeds {max_events}.")
        if note_count > max_notes:
            raise MidiParseError(f"MIDI note count exceeds {max_notes}.")
        tempos.extend(track_tempos)
        time_signatures.extend(track_sigs)
        tracks.append(parsed)

    if offset != len(data):
        warnings.append("Trailing bytes after MIDI tracks were ignored.")
    return MidiFile(
        midi_format=midi_format,
        track_count=track_count,
        ppq=division,
        tracks=tracks,
        tempos=tempos,
        time_signatures=time_signatures,
        warnings=warnings,
    )


def midi_summary(midi: MidiFile) -> dict[str, Any]:
    notes = midi.notes
    tempo = midi.tempos[0]["microseconds_per_quarter"] if midi.tempos else 500_000
    tempo_bpm = round(60_000_000 / tempo, 2) if tempo else 120.0
    duration_ticks = max([note.end_tick for note in notes] + [track.end_tick for track in midi.tracks] + [0])
    duration_beats = round(duration_ticks / midi.ppq, 3)
    channels = sorted({note.channel for note in notes} | {program["channel"] for track in midi.tracks for program in track.programs})
    programs = _unique_programs([program for track in midi.tracks for program in track.programs])
    pitches = [note.pitch for note in notes]
    track_summaries = [_track_summary(track, midi.ppq) for track in midi.tracks]
    time_signature = "4/4"
    if midi.time_signatures:
        sig = midi.time_signatures[0]
        time_signature = f"{sig['numerator']}/{sig['denominator']}"
    return {
        "format": midi.midi_format,
        "track_count": midi.track_count,
        "ppq": midi.ppq,
        "duration_beats": duration_beats,
        "duration_seconds": round(duration_beats * (60 / tempo_bpm), 3) if tempo_bpm else 0.0,
        "tempo_bpm": tempo_bpm,
        "time_signature": time_signature,
        "channels": channels,
        "programs": programs,
        "note_count": len(notes),
        "pitch_min": min(pitches) if pitches else None,
        "pitch_max": max(pitches) if pitches else None,
        "drum_note_count": sum(1 for note in notes if note.channel == 9),
        "track_summaries": track_summaries,
    }


def suggest_slices(midi: MidiFile, *, max_slices: int = 24) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for track in midi.tracks:
        if not track.notes:
            continue
        role = infer_track_role(track)
        if role == "unknown":
            continue
        duration = max(note.end_tick for note in track.notes) / midi.ppq
        window = 8.0 if duration >= 8.0 else 4.0
        start = 0.0
        while start < duration and len(candidates) < max_slices * 3:
            end = start + window
            notes = _notes_in_window(track.notes, midi.ppq, start, end)
            if _slice_note_count_ok(role, len(notes)):
                pitches = [note.pitch for note in notes]
                slice_type = _slice_type_for_role(role)
                candidates.append(
                    {
                        "slice_type": slice_type,
                        "name": f"Track {track.track_index} {role} {start:g}-{end:g} beats",
                        "track_index": track.track_index,
                        "channel": _primary_channel(notes),
                        "start_beat": round(start, 3),
                        "duration_beats": round(min(window, max(0.25, duration - start)), 3),
                        "note_count": len(notes),
                        "pitch_min": min(pitches) if pitches else None,
                        "pitch_max": max(pitches) if pitches else None,
                        "quality_hint": _quality_hint(role, notes),
                        "midi_status": "not_started",
                        "midi_url": None,
                        "midi_size_bytes": 0,
                        "midi_error": None,
                        "audio_status": "not_started",
                        "audio_url": None,
                        "audio_size_bytes": 0,
                        "audio_error": None,
                    }
                )
            start += window

    candidates.sort(key=lambda item: (-int(item["quality_hint"]), int(item["track_index"]), float(item["start_beat"])))
    selected: list[dict[str, Any]] = []
    per_type: dict[str, int] = {}
    for item in candidates:
        if len(selected) >= max_slices:
            break
        count = per_type.get(str(item["slice_type"]), 0)
        if count >= 8:
            continue
        per_type[str(item["slice_type"])] = count + 1
        item = dict(item)
        item["slice_id"] = f"slice-{len(selected) + 1:03d}"
        selected.append(item)
    return sorted(selected, key=lambda item: item["slice_id"])


def notes_for_slice(midi: MidiFile, slice_item: dict[str, Any]) -> list[dict[str, Any]]:
    track_index = int(slice_item.get("track_index", -1))
    start_beat = float(slice_item.get("start_beat") or 0)
    duration_beats = float(slice_item.get("duration_beats") or 0)
    end_beat = start_beat + duration_beats
    track = next((item for item in midi.tracks if item.track_index == track_index), None)
    if track is None:
        raise MidiParseError("Slice track is missing.")
    notes = _notes_in_window(track.notes, midi.ppq, start_beat, end_beat)
    normalized: list[dict[str, Any]] = []
    for note in notes:
        start = max(start_beat, note.start_tick / midi.ppq)
        end = min(end_beat, note.end_tick / midi.ppq)
        if end <= start:
            continue
        normalized.append(
            {
                "pitch": note.pitch,
                "start_beat": round(start - start_beat, 3),
                "duration_beats": round(end - start, 3),
                "velocity": note.velocity,
                "channel": note.channel,
            }
        )
    return normalized


def render_slice_midi(midi: MidiFile, slice_item: dict[str, Any], output_path: Path, *, title: str = "Reference Slice") -> Path:
    notes = [NoteEvent(int(note["pitch"]), float(note["start_beat"]), float(note["duration_beats"]), int(note["velocity"])) for note in notes_for_slice(midi, slice_item)]
    if not notes:
        raise MidiParseError("Slice has no notes.")
    slice_type = str(slice_item.get("slice_type") or "motif")
    track_name = {
        "motif": "melody",
        "bass_pattern": "bass",
        "drum_pattern": "drums",
        "chord_progression": "chords",
    }.get(slice_type, "melody")
    instrument = {
        "motif": "lead",
        "bass_pattern": "electric bass",
        "drum_pattern": "gm drums",
        "chord_progression": "electric piano",
    }.get(slice_type, "lead")
    duration_beats = max(float(slice_item.get("duration_beats") or 4.0), max(note.start_beat + note.duration_beats for note in notes))
    bars = max(1, int((duration_beats + 3.999) // 4))
    tempo = int(round(float(midi_summary(midi).get("tempo_bpm") or 120)))
    filler = [NoteEvent(60, 0.0, 0.25, 1)]
    track_notes = {
        "melody": filler,
        "chords": [NoteEvent(60, 0.0, 0.25, 1), NoteEvent(64, 0.0, 0.25, 1), NoteEvent(67, 0.0, 0.25, 1)],
        "bass": [NoteEvent(36, 0.0, 0.25, 1)],
        "drums": [NoteEvent(42, 0.0, 0.25, 1)],
    }
    track_notes[track_name] = notes
    plan = SongPlan(
        title=title,
        key="C",
        tempo_bpm=max(40, min(240, tempo)),
        meter=str(midi_summary(midi).get("time_signature") or "4/4"),
        sections=[SongSection(name="slice", start_bar=1, bars=bars, chords=["Cmaj7"])],
        tracks=[
            TrackPlan(name="melody", instrument=instrument if track_name == "melody" else "lead", notes=track_notes["melody"]),
            TrackPlan(name="chords", instrument=instrument if track_name == "chords" else "electric piano", notes=track_notes["chords"]),
            TrackPlan(name="bass", instrument=instrument if track_name == "bass" else "electric bass", notes=track_notes["bass"]),
            TrackPlan(name="drums", instrument=instrument if track_name == "drums" else "gm drums", notes=track_notes["drums"]),
        ],
    )
    return render_midi(plan, output_path)


def infer_track_role(track: MidiTrack) -> str:
    if not track.notes:
        return "unknown"
    channels = [note.channel for note in track.notes]
    pitches = [note.pitch for note in track.notes]
    if channels.count(9) >= max(1, int(len(channels) * 0.4)) or ("drum" in track.name.lower() and _drum_pitch_ratio(pitches) > 0.55):
        return "drums"
    polyphony = _polyphony_score(track.notes)
    median_pitch = statistics.median(pitches)
    if polyphony >= 2.4:
        return "chords"
    if median_pitch < 52:
        return "bass"
    if median_pitch >= 56 and len(track.notes) >= 2:
        return "melody"
    return "unknown"


def _parse_track(
    data: bytes,
    track_index: int,
    ppq: int,
    *,
    max_events: int,
) -> tuple[MidiTrack, int, int, list[dict[str, int]], list[dict[str, int]]]:
    offset = 0
    tick = 0
    running_status: int | None = None
    active: dict[tuple[int, int], list[tuple[int, int]]] = {}
    notes: list[MidiNote] = []
    programs: list[dict[str, int]] = []
    channels: set[int] = set()
    tempos: list[dict[str, int]] = []
    time_signatures: list[dict[str, int]] = []
    warnings: list[str] = []
    name = ""
    has_eot = False
    events = 0

    while offset < len(data):
        if events >= max_events:
            raise MidiParseError(f"MIDI event count exceeds {MAX_MIDI_EVENTS}.")
        delta, offset = _read_vlq(data, offset)
        tick += delta
        if offset >= len(data):
            raise MidiParseError("MIDI event is truncated.")
        status = data[offset]
        offset += 1
        events += 1

        if status == 0xFF:
            if offset >= len(data):
                raise MidiParseError("MIDI meta event is truncated.")
            meta_type = data[offset]
            offset += 1
            length, offset = _read_vlq(data, offset)
            payload = _read_bytes(data, offset, length, "MIDI meta payload")
            offset += length
            running_status = None
            if meta_type == 0x03:
                name = payload.decode("utf-8", errors="replace")[:120]
            elif meta_type == 0x2F:
                has_eot = True
            elif meta_type == 0x51 and len(payload) == 3:
                tempos.append({"tick": tick, "microseconds_per_quarter": int.from_bytes(payload, "big")})
            elif meta_type == 0x58 and len(payload) >= 2:
                time_signatures.append({"tick": tick, "numerator": payload[0], "denominator": 2 ** payload[1]})
            continue

        if status in {0xF0, 0xF7}:
            length, offset = _read_vlq(data, offset)
            _read_bytes(data, offset, length, "MIDI sysex payload")
            offset += length
            running_status = None
            continue

        if status < 0x80:
            if running_status is None:
                raise MidiParseError("MIDI running status without previous status.")
            offset -= 1
            status = running_status
        else:
            running_status = status

        event_type = status & 0xF0
        channel = status & 0x0F
        channels.add(channel)
        if event_type in {0xC0, 0xD0}:
            value = _read_bytes(data, offset, 1, "MIDI channel event")[0]
            offset += 1
            if event_type == 0xC0:
                programs.append({"tick": tick, "channel": channel, "program": value})
            continue
        if event_type not in {0x80, 0x90, 0xA0, 0xB0, 0xE0}:
            raise MidiParseError(f"Unsupported MIDI event status: 0x{status:02x}.")
        first, second = _read_bytes(data, offset, 2, "MIDI channel event")
        offset += 2
        if event_type == 0x90 and second > 0:
            active.setdefault((channel, first), []).append((tick, second))
        elif event_type in {0x80, 0x90}:
            key = (channel, first)
            if active.get(key):
                start_tick, velocity = active[key].pop(0)
                if tick > start_tick:
                    notes.append(MidiNote(track_index, channel, first, start_tick, tick, velocity))

    for (channel, pitch), starts in active.items():
        for start_tick, velocity in starts:
            if tick > start_tick:
                warnings.append("Unclosed note was ended at track end.")
                notes.append(MidiNote(track_index, channel, pitch, start_tick, tick, velocity))

    return (
        MidiTrack(
            track_index=track_index,
            name=name or f"Track {track_index}",
            notes=notes,
            programs=programs,
            channels=sorted(channels),
            end_tick=tick,
            has_eot=has_eot,
            warnings=warnings,
        ),
        events,
        len(notes),
        tempos,
        time_signatures,
    )


def _track_summary(track: MidiTrack, ppq: int) -> ImplementationDocument:
    pitches = [note.pitch for note in track.notes]
    duration_ticks = max([note.end_tick for note in track.notes] + [track.end_tick, 0])
    return {
        "track_index": track.track_index,
        "name": track.name,
        "channel": _primary_channel(track.notes),
        "channels": sorted({note.channel for note in track.notes} | set(track.channels)),
        "programs": _unique_programs(track.programs),
        "note_count": len(track.notes),
        "pitch_min": min(pitches) if pitches else None,
        "pitch_max": max(pitches) if pitches else None,
        "duration_beats": round(duration_ticks / ppq, 3),
        "likely_role": infer_track_role(track),
        "has_eot": track.has_eot,
    }


def _notes_in_window(notes: list[MidiNote], ppq: int, start_beat: float, end_beat: float) -> list[MidiNote]:
    start_tick = round(start_beat * ppq)
    end_tick = round(end_beat * ppq)
    return [note for note in notes if note.end_tick > start_tick and note.start_tick < end_tick]


def _slice_note_count_ok(role: str, count: int) -> bool:
    if role == "chords":
        return count >= 3
    return count >= 2


def _slice_type_for_role(role: str) -> str:
    return {
        "melody": "motif",
        "bass": "bass_pattern",
        "drums": "drum_pattern",
        "chords": "chord_progression",
    }.get(role, "motif")


def _quality_hint(role: str, notes: list[MidiNote]) -> int:
    base = {"melody": 72, "bass": 68, "drums": 66, "chords": 70}.get(role, 60)
    count_bonus = min(18, len(notes) * 2)
    range_bonus = 0
    if notes:
        pitches = [note.pitch for note in notes]
        pitch_range = max(pitches) - min(pitches)
        range_bonus = min(10, pitch_range)
    return max(0, min(100, base + count_bonus + range_bonus))


def _polyphony_score(notes: list[MidiNote]) -> float:
    if not notes:
        return 0.0
    starts: dict[int, int] = {}
    for note in notes:
        starts[note.start_tick] = starts.get(note.start_tick, 0) + 1
    return sum(starts.values()) / len(starts)


def _drum_pitch_ratio(pitches: list[int]) -> float:
    if not pitches:
        return 0.0
    drum_like = sum(1 for pitch in pitches if 35 <= pitch <= 81)
    return drum_like / len(pitches)


def _primary_channel(notes: list[MidiNote]) -> int | None:
    if not notes:
        return None
    counts: dict[int, int] = {}
    for note in notes:
        counts[note.channel] = counts.get(note.channel, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _unique_programs(programs: list[dict[str, int]]) -> list[dict[str, int]]:
    seen = set()
    unique = []
    for program in programs:
        key = (int(program["channel"]), int(program["program"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append({"channel": key[0], "program": key[1]})
    return unique


def _read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if offset >= len(data):
            raise MidiParseError("MIDI variable-length quantity is truncated.")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
    raise MidiParseError("MIDI variable-length quantity is too long.")


def _read_bytes(data: bytes, offset: int, length: int, label: str) -> bytes:
    if length < 0 or offset + length > len(data):
        raise MidiParseError(f"{label} is truncated.")
    return data[offset : offset + length]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_read_bytes(data, offset, 2, "MIDI uint16"), "big")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_read_bytes(data, offset, 4, "MIDI uint32"), "big")
