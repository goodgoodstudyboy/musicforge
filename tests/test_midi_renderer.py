from song_agent.agent.pipeline import SongAgent
from song_agent.renderers.midi import render_midi, render_midi_stem
from song_agent.schemas.song import SongRequest


def test_render_midi_writes_standard_midi_file(tmp_path):
    request = SongRequest.from_dict(
        {
            "title": "Test Song",
            "language": "en",
            "style": "pop",
            "theme": "test",
        }
    )
    plan = SongAgent().generate(request)
    output_path = tmp_path / "song.mid"

    render_midi(plan, output_path)

    midi_bytes = output_path.read_bytes()
    assert midi_bytes.startswith(b"MThd")
    assert b"MTrk" in midi_bytes
    assert output_path.stat().st_size > 100


def test_render_midi_writes_expected_midi_semantics(tmp_path):
    request = SongRequest.from_dict(
        {
            "title": "Test Song",
            "language": "en",
            "style": "pop",
            "theme": "test",
            "tempo_bpm": 120,
        }
    )
    plan = SongAgent().generate(request)
    output_path = tmp_path / "song.mid"

    render_midi(plan, output_path)

    parsed = parse_midi(output_path.read_bytes())
    assert parsed["format"] == 1
    assert parsed["track_count"] == 5
    assert parsed["ppq"] == 480
    assert len(parsed["tracks"]) == 5
    assert all(track["has_eot"] for track in parsed["tracks"])
    assert 500000 in parsed["tracks"][0]["tempos"]

    music_tracks = parsed["tracks"][1:]
    assert [track["program_changes"] for track in music_tracks[:3]] == [
        [(0, 81)],
        [(1, 4)],
        [(2, 33)],
    ]
    assert any(channel == 9 for channel, _pitch in music_tracks[3]["note_on"])
    for track in music_tracks:
        assert sorted(track["note_on"]) == sorted(track["note_off"])


def test_render_midi_stem_writes_meta_and_one_music_track(tmp_path):
    request = SongRequest.from_dict(
        {
            "title": "Test Song",
            "language": "en",
            "style": "pop",
            "theme": "test",
            "tempo_bpm": 120,
        }
    )
    plan = SongAgent().generate(request)
    output_path = tmp_path / "melody.mid"

    render_midi_stem(plan, 0, output_path)

    parsed = parse_midi(output_path.read_bytes())
    assert parsed["format"] == 1
    assert parsed["track_count"] == 2
    assert 500000 in parsed["tracks"][0]["tempos"]
    assert parsed["tracks"][1]["program_changes"] == [(0, 81)]
    assert sorted(parsed["tracks"][1]["note_on"]) == sorted(parsed["tracks"][1]["note_off"])


def parse_midi(data: bytes) -> dict:
    assert data[:4] == b"MThd"
    header_length = int.from_bytes(data[4:8], "big")
    assert header_length == 6
    midi_format = int.from_bytes(data[8:10], "big")
    track_count = int.from_bytes(data[10:12], "big")
    ppq = int.from_bytes(data[12:14], "big")

    offset = 8 + header_length
    tracks = []
    for _ in range(track_count):
        assert data[offset : offset + 4] == b"MTrk"
        track_length = int.from_bytes(data[offset + 4 : offset + 8], "big")
        track_data = data[offset + 8 : offset + 8 + track_length]
        tracks.append(parse_track(track_data))
        offset += 8 + track_length

    return {
        "format": midi_format,
        "track_count": track_count,
        "ppq": ppq,
        "tracks": tracks,
    }


def parse_track(data: bytes) -> dict:
    offset = 0
    running_status = None
    track = {
        "tempos": [],
        "program_changes": [],
        "note_on": [],
        "note_off": [],
        "has_eot": False,
    }
    while offset < len(data):
        _delta, offset = read_var_len(data, offset)
        status = data[offset]
        offset += 1
        if status == 0xFF:
            meta_type = data[offset]
            offset += 1
            length, offset = read_var_len(data, offset)
            payload = data[offset : offset + length]
            offset += length
            if meta_type == 0x51:
                track["tempos"].append(int.from_bytes(payload, "big"))
            if meta_type == 0x2F:
                track["has_eot"] = True
            continue

        if status < 0x80:
            if running_status is None:
                raise AssertionError("MIDI running status without previous status")
            offset -= 1
            status = running_status
        else:
            running_status = status

        event_type = status & 0xF0
        channel = status & 0x0F
        if event_type == 0xC0:
            program = data[offset]
            offset += 1
            track["program_changes"].append((channel, program))
            continue

        first = data[offset]
        second = data[offset + 1]
        offset += 2
        if event_type == 0x90 and second > 0:
            track["note_on"].append((channel, first))
        elif event_type in (0x80, 0x90):
            track["note_off"].append((channel, first))

    return track


def read_var_len(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
