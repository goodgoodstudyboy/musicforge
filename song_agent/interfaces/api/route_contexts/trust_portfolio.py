from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from song_agent.application.http_ports.trust import TrustPortfolioRouteContext as TrustPortfolioRouteContext
else:

    class TrustPortfolioRouteContext:
        """Runtime marker for Release Portfolio route mixins."""
