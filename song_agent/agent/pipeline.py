from __future__ import annotations

from dataclasses import dataclass

from song_agent.providers.base import LLMProvider
from song_agent.schemas.song import SongPlan, SongRequest


@dataclass
class SongAgent:
    provider: LLMProvider

    def generate(self, request: SongRequest) -> SongPlan:
        """Run the fixed songwriting workflow."""
        raise NotImplementedError("Song generation pipeline is not implemented yet.")

