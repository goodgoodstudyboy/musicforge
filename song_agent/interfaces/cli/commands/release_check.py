from __future__ import annotations

from .release_check_parts.dependencies import *

from .release_check_parts.part_001 import *

from .release_check_parts.part_002 import *

from .release_check_parts.part_003 import *

from .release_check_parts.part_004 import *

from .release_check_parts.part_005 import *

SPECS = (
    CommandSpec(name='ga-check', parser=build_acceptance_analytics_parser, handler=handle_ga_check, help='Ga Check', group='release_check'),
    CommandSpec(name='verify-ga-readiness-report', parser=build_acceptance_analytics_parser, handler=handle_verify_ga_readiness_report, help='Verify Ga Readiness Report', group='release_check'),
    CommandSpec(name='release-check', parser=build_acceptance_analytics_parser, handler=handle_release_check, help='Release Check', group='release_check'),
)

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
