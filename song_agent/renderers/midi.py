from __future__ import annotations

from pathlib import Path

from song_agent.schemas.song import SongPlan


def render_midi(plan: SongPlan, output_path: Path) -> Path:
    """Render a SongPlan to a MIDI file.

    This placeholder defines the boundary. The first real implementation should
    use a small MIDI writer or a dependency such as mido/pretty_midi.
    """
    raise NotImplementedError("MIDI rendering is not implemented yet.")

