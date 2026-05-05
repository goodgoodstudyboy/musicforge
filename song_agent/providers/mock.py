from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from song_agent.agent.pipeline import deterministic_compose
from song_agent.provider import ProviderRequestError
from song_agent.schemas.song import SongRequest


@dataclass
class MockProviderClient:
    mode: str = "ok"

    def test(self) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        return {"ok": True, "message": "Mock provider test completed."}

    def generate_song_plan_json(self, request: SongRequest, config: Any) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        if self.mode == "invalid_schema":
            return {"title": request.title}
        return deterministic_compose(request).to_dict()
