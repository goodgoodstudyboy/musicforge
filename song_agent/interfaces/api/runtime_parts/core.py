from __future__ import annotations

from song_agent.interfaces.bootstrap.api.creation_quality import MAX_REFERENCE_WAV_BYTES

from song_agent.interfaces.bootstrap.api.core import Path

RUNS_DIR = Path("runs")

REFERENCE_IMPORT_MAX_BODY_BYTES = int(MAX_REFERENCE_WAV_BYTES * 4 / 3) + 1_000_000

VARIATION_REQUEST_FIELDS = {
    "title",
    "language",
    "style",
    "theme",
    "duration_seconds",
    "vocal_mode",
    "tempo_bpm",
    "key",
    "lyrics",
    "generation_mode",
    "pipeline_mode",
}

class JobCancelled(Exception):
    """Raised when a job stops at a stage boundary after cancellation."""

__all__ = ['JobCancelled', 'REFERENCE_IMPORT_MAX_BODY_BYTES', 'RUNS_DIR', 'VARIATION_REQUEST_FIELDS']
