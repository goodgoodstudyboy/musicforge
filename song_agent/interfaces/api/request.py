from __future__ import annotations

from dataclasses import dataclass

from song_agent.platform.contracts.documents import JsonDocument


@dataclass(frozen=True, slots=True)
class RequestContext:
    method: str
    path: str
    query: str = ""
    body: JsonDocument | None = None
    authorized: bool = False
