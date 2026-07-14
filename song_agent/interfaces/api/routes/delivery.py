from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.application.release_signoff import ReleaseSignoffApplication

from .delivery_parts.part_001 import DeliveryRoutesPart001

from .delivery_parts.part_002 import DeliveryRoutesPart002

from .delivery_parts.part_003 import DeliveryRoutesPart003

from .delivery_parts.part_004 import DeliveryRoutesPart004

from .delivery_parts.part_005 import DeliveryRoutesPart005

from .delivery_parts.part_006 import DeliveryRoutesPart006

from .delivery_parts.part_007 import DeliveryRoutesPart007

from .delivery_parts.part_008 import DeliveryRoutesPart008

class DeliveryRoutes(DeliveryRoutesPart001, DeliveryRoutesPart002, DeliveryRoutesPart003, DeliveryRoutesPart004, DeliveryRoutesPart005, DeliveryRoutesPart006, DeliveryRoutesPart007, DeliveryRoutesPart008):
    def _handle_release_signoff(self, method: str, release_id: str) -> None:
        ReleaseSignoffApplication(self).execute(method, release_id)
