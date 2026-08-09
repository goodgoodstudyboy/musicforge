from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from song_agent.application.http_ports.creation import CreationRouteContext as CreationRouteContext
else:

    class CreationRouteContext:
        """Runtime marker for Creation route mixins."""
