from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from song_agent.application.http_ports.delivery import DeliveryRouteContext as DeliveryRouteContext
else:

    class DeliveryRouteContext:
        """Runtime marker for Delivery route mixins."""
