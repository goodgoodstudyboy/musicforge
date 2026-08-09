from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from song_agent.application.http_ports.quality import QualityRouteContext as QualityRouteContext
else:

    class QualityRouteContext:
        """Runtime marker for Quality route mixins."""
