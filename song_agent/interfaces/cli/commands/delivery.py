from __future__ import annotations

from .delivery_parts.dependencies import *

from .delivery_parts.part_001 import *

from .delivery_parts.part_002 import *

from .delivery_parts.part_003 import *

from .delivery_parts.part_004 import *

from .delivery_parts.part_005 import *

from .delivery_parts.part_006 import *

SPECS = (
    CommandSpec(name='verify-unified-command-center-release-train-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_package, help='Verify Unified Command Center Release Train Package', group='delivery'),
    CommandSpec(name='verify-unified-command-center-release-train-change-control-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_change_control_package, help='Verify Unified Command Center Release Train Change Control Package', group='delivery'),
    CommandSpec(name='verify-unified-command-center-release-train-lifecycle-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_lifecycle_package, help='Verify Unified Command Center Release Train Lifecycle Package', group='delivery'),
    CommandSpec(name='verify-unified-command-center-release-train-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_handoff_package, help='Verify Unified Command Center Release Train Handoff Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_package, help='Verify Unified Release Program Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-operations-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_operations_package, help='Verify Unified Release Program Operations Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_handoff_package, help='Verify Unified Release Program Handoff Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-vault-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_vault_package, help='Verify Unified Release Program Vault Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-vault-operations-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_vault_operations_package, help='Verify Unified Release Program Vault Operations Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_package, help='Verify Unified Release Program Continuity Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-kit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_kit_package, help='Verify Unified Release Program Continuity Kit Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_package, help='Verify Unified Release Program Continuity Command Center Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-signoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_signoff_package, help='Verify Unified Release Program Continuity Command Center Signoff Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_handoff_package, help='Verify Unified Release Program Continuity Command Center Handoff Package', group='delivery'),
    CommandSpec(name='verify-release', parser=build_acceptance_analytics_parser, handler=handle_verify_release, help='Verify Release', group='delivery'),
    CommandSpec(name='verify-distribution-package', parser=build_acceptance_analytics_parser, handler=handle_verify_distribution_package, help='Verify Distribution Package', group='delivery'),
    CommandSpec(name='verify-submission-package', parser=build_acceptance_analytics_parser, handler=handle_verify_submission_package, help='Verify Submission Package', group='delivery'),
    CommandSpec(name='verify-submission-evidence-package', parser=build_acceptance_analytics_parser, handler=handle_verify_submission_evidence_package, help='Verify Submission Evidence Package', group='delivery'),
    CommandSpec(name='verify-release-operations-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_package, help='Verify Release Operations Package', group='delivery'),
    CommandSpec(name='verify-release-operations-runbook-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_runbook_package, help='Verify Release Operations Runbook Package', group='delivery'),
    CommandSpec(name='verify-release-operations-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_archive_package, help='Verify Release Operations Archive Package', group='delivery'),
    CommandSpec(name='verify-release-operations-audit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_audit_package, help='Verify Release Operations Audit Package', group='delivery'),
    CommandSpec(name='verify-release-operations-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_reviewer_pack, help='Verify Release Operations Reviewer Pack', group='delivery'),
    CommandSpec(name='release-operations', parser=build_acceptance_analytics_parser, handler=handle_release_operations, help='Release Operations', group='delivery'),
    CommandSpec(name='release-operations-runbook', parser=build_acceptance_analytics_parser, handler=handle_release_operations_runbook, help='Release Operations Runbook', group='delivery'),
    CommandSpec(name='release-operations-signoff', parser=build_acceptance_analytics_parser, handler=handle_release_operations_signoff, help='Release Operations Signoff', group='delivery'),
    CommandSpec(name='release-operations-archive', parser=build_acceptance_analytics_parser, handler=handle_release_operations_archive, help='Release Operations Archive', group='delivery'),
    CommandSpec(name='release-operations-audit', parser=build_acceptance_analytics_parser, handler=handle_release_operations_audit, help='Release Operations Audit', group='delivery'),
    CommandSpec(name='release-operations-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_release_operations_reviewer_pack, help='Release Operations Reviewer Pack', group='delivery'),
    CommandSpec(name='release-encode', parser=build_acceptance_analytics_parser, handler=handle_release_encode, help='Release Encode', group='delivery'),
)

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
