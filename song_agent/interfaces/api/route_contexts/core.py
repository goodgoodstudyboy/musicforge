from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from song_agent.platform.contracts import JsonDocument

if TYPE_CHECKING:
    from song_agent.interfaces.api.router import RouteRegistry


class _CoreRouteContextTyping(Protocol):
    path: str
    route_registry: RouteRegistry

    def _optional_json_body(self) -> JsonDocument: ...

    def _read_json_body(self) -> JsonDocument: ...

    def _send_error(self, status: HTTPStatus, message: str) -> None: ...

    def _send_file(
        self,
        path: Path,
        content_type: str | None = None,
        *,
        filename: str | None = None,
    ) -> None: ...

    def _send_json(self, data: JsonDocument, status: HTTPStatus = HTTPStatus.OK) -> None: ...


if TYPE_CHECKING:
    CoreRouteContext = _CoreRouteContextTyping
else:

    class CoreRouteContext:
        """Runtime marker shared by top-level API route groups."""
