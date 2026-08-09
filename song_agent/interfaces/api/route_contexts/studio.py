from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from song_agent.application.http_ports.studio import StudioRouteContext as StudioRouteContext
else:

    class StudioRouteContext:
        """Runtime marker for Studio route mixins."""
