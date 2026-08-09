from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from song_agent.application.http_ports.trust import TrustRouteContext as TrustRouteContext
else:

    class TrustRouteContext:
        """Runtime marker for Trust route mixins."""
