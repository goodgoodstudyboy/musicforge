from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RequestContext:
    method: str
    path: str
    query: str = ""
    body: dict[str, Any] | None = None
    authorized: bool = False
