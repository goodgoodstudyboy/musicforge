from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    method: str
    path: str
    query: str = ""
    body: ImplementationDocument | None = None
    authorized: bool = False
