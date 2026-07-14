from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from .quality_parts.part_001 import QualityRoutesPart001

from .quality_parts.part_002 import QualityRoutesPart002

from .quality_parts.part_003 import QualityRoutesPart003

from .quality_parts.part_004 import QualityRoutesPart004

from .quality_parts.part_005 import QualityRoutesPart005

from .quality_parts.part_006 import QualityRoutesPart006

from .quality_parts.part_007 import QualityRoutesPart007

from .quality_parts.part_008 import QualityRoutesPart008

from .quality_parts.part_009 import QualityRoutesPart009

from .quality_parts.part_010 import QualityRoutesPart010

from .quality_parts.part_011 import QualityRoutesPart011

from .quality_parts.part_012 import QualityRoutesPart012

from .quality_parts.part_013 import QualityRoutesPart013

from .quality_parts.part_014 import QualityRoutesPart014

from .quality_parts.part_015 import QualityRoutesPart015

from .quality_parts.part_016 import QualityRoutesPart016

from .quality_parts.part_017 import QualityRoutesPart017

class QualityRoutes(QualityRoutesPart001, QualityRoutesPart002, QualityRoutesPart003, QualityRoutesPart004, QualityRoutesPart005, QualityRoutesPart006, QualityRoutesPart007, QualityRoutesPart008, QualityRoutesPart009, QualityRoutesPart010, QualityRoutesPart011, QualityRoutesPart012, QualityRoutesPart013, QualityRoutesPart014, QualityRoutesPart015, QualityRoutesPart016, QualityRoutesPart017):
    pass
