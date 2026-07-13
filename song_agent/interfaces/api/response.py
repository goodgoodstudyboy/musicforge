from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class APIResponse:
    status: int
    body: dict[str, Any]
    content_type: str = "application/json"
