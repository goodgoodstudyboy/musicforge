from __future__ import annotations

from .creation_parts.dependencies import *

from .creation_parts.part_001 import *

from .creation_parts.part_002 import *

from .creation_parts.part_003 import *

from .creation_parts.part_004 import *

SPECS = (
    CommandSpec(name='generate', parser=build_acceptance_analytics_parser, handler=handle_generate, help='Generate', group='creation'),
    CommandSpec(name='verify-unified-command-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_package, help='Verify Unified Command Center Package', group='creation'),
    CommandSpec(name='verify-unified-command-center-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_archive_package, help='Verify Unified Command Center Archive Package', group='creation'),
    CommandSpec(name='verify-unified-command-center-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_handoff_package, help='Verify Unified Command Center Handoff Package', group='creation'),
    CommandSpec(name='verify-unified-command-center-continuous-review-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_continuous_review_package, help='Verify Unified Command Center Continuous Review Package', group='creation'),
    CommandSpec(name='verify-unified-command-center-drift-response-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_drift_response_package, help='Verify Unified Command Center Drift Response Package', group='creation'),
    CommandSpec(name='verify-unified-command-center-evidence-review-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_evidence_review_package, help='Verify Unified Command Center Evidence Review Package', group='creation'),
    CommandSpec(name='verify-unified-command-center-reviewer-decision-board-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_reviewer_decision_board_package, help='Verify Unified Command Center Reviewer Decision Board Package', group='creation'),
    CommandSpec(name='verify-human-review-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_human_review_pack, help='Verify Human Review Pack', group='creation'),
)

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
