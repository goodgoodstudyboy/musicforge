from __future__ import annotations

from dataclasses import dataclass

from song_agent.platform.contracts.documents import JsonDocument


@dataclass(frozen=True, slots=True)
class APIResponse:
    status: int
    body: JsonDocument
    content_type: str = "application/json"
