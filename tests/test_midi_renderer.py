from song_agent.agent.pipeline import SongAgent
from song_agent.renderers.midi import render_midi
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
