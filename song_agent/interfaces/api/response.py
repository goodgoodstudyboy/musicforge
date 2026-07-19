from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class APIResponse:
    status: int
    body: ImplementationDocument
    content_type: str = "application/json"
