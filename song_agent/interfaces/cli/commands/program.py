from __future__ import annotations

from .program_parts.dependencies import *

from .program_parts.part_001 import *

from .program_parts.part_002 import *

from .program_parts.part_003 import *

from .program_parts.part_004 import *

from .program_parts.part_005 import *

from .program_parts.part_006 import *

from .program_parts.part_007 import *

from .program_parts.part_008 import *

from .program_parts.part_009 import *

from .program_parts.part_010 import *

from .program_parts.part_011 import *

from .program_parts.part_012 import *

from .program_parts.part_013 import *

SPECS = (
    CommandSpec(name='unified-command-center', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center, help='Unified Command Center', group='program'),
    CommandSpec(name='unified-command-center-review', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_review, help='Unified Command Center Review', group='program'),
    CommandSpec(name='unified-command-center-drift-response', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_drift_response, help='Unified Command Center Drift Response', group='program'),
    CommandSpec(name='unified-command-center-evidence-review', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_evidence_review, help='Unified Command Center Evidence Review', group='program'),
    CommandSpec(name='unified-command-center-reviewer-decision-board', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_reviewer_decision_board, help='Unified Command Center Reviewer Decision Board', group='program'),
    CommandSpec(name='unified-command-center-release-train', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train, help='Unified Command Center Release Train', group='program'),
    CommandSpec(name='unified-command-center-release-train-change-control', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train_change_control, help='Unified Command Center Release Train Change Control', group='program'),
    CommandSpec(name='unified-command-center-release-train-lifecycle', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train_lifecycle, help='Unified Command Center Release Train Lifecycle', group='program'),
    CommandSpec(name='unified-command-center-release-train-handoff', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train_handoff, help='Unified Command Center Release Train Handoff', group='program'),
    CommandSpec(name='unified-release-program', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program, help='Unified Release Program', group='program'),
    CommandSpec(name='unified-release-program-operations', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_operations, help='Unified Release Program Operations', group='program'),
    CommandSpec(name='unified-release-program-handoff', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_handoff, help='Unified Release Program Handoff', group='program'),
    CommandSpec(name='unified-release-program-vault', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_vault, help='Unified Release Program Vault', group='program'),
    CommandSpec(name='unified-release-program-vault-ops', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_vault_ops, help='Unified Release Program Vault Ops', group='program'),
    CommandSpec(name='unified-release-program-continuity', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity, help='Unified Release Program Continuity', group='program'),
    CommandSpec(name='unified-release-program-continuity-kit', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_kit, help='Unified Release Program Continuity Kit', group='program'),
    CommandSpec(name='unified-release-program-continuity-acceptance', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_acceptance, help='Unified Release Program Continuity Acceptance', group='program'),
    CommandSpec(name='unified-release-program-continuity-acceptance-change', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_acceptance_change, help='Unified Release Program Continuity Acceptance Change', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center, help='Unified Release Program Continuity Command Center', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center-signoff', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center_signoff, help='Unified Release Program Continuity Command Center Signoff', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center-acceptance', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center_acceptance, help='Unified Release Program Continuity Command Center Acceptance', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center-acceptance-change', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center_acceptance_change, help='Unified Release Program Continuity Command Center Acceptance Change', group='program'),
)

SPECS = tuple(spec for spec in SPECS if not spec.name.startswith("unified-release-program"))

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
