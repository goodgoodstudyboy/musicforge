from __future__ import annotations

from .maintenance_parts.dependencies import *

from .maintenance_parts.part_001 import *

from .maintenance_parts.part_002 import *

from .maintenance_parts.part_003 import *

SPECS = (
    CommandSpec(name='doctor', parser=build_acceptance_analytics_parser, handler=handle_doctor, help='Doctor', group='maintenance'),
    CommandSpec(name='maintenance', parser=build_acceptance_analytics_parser, handler=handle_maintenance, help='Maintenance', group='maintenance'),
    CommandSpec(name='verify-maintenance-backup', parser=build_acceptance_analytics_parser, handler=handle_verify_maintenance_backup, help='Verify Maintenance Backup', group='maintenance'),
)

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
