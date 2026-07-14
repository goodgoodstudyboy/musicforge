from __future__ import annotations

from .quality_parts.dependencies import *

from .quality_parts.part_001 import *

from .quality_parts.part_002 import *

from .quality_parts.part_003 import *

from .quality_parts.part_004 import *

from .quality_parts.part_005 import *

from .quality_parts.part_006 import *

from .quality_parts.part_007 import *

from .quality_parts.part_008 import *

from .quality_parts.part_009 import *

from .quality_parts.part_010 import *

from .quality_parts.part_011 import *

from .quality_parts.part_012 import *

from .quality_parts.part_013 import *

from .quality_parts.part_014 import *

SPECS = (
    CommandSpec(name='audio-lab', parser=build_acceptance_analytics_parser, handler=handle_audio_lab, help='Audio Lab', group='quality'),
    CommandSpec(name='audio-fix-sprint', parser=build_acceptance_analytics_parser, handler=handle_audio_fix_sprint, help='Audio Fix Sprint', group='quality'),
    CommandSpec(name='audio-campaign', parser=build_acceptance_analytics_parser, handler=handle_audio_campaign, help='Audio Campaign', group='quality'),
    CommandSpec(name='release-audio-certification', parser=build_acceptance_analytics_parser, handler=handle_release_audio_certification, help='Release Audio Certification', group='quality'),
    CommandSpec(name='release-audio-timeline', parser=build_acceptance_analytics_parser, handler=handle_release_audio_timeline, help='Release Audio Timeline', group='quality'),
    CommandSpec(name='release-audio-regression', parser=build_acceptance_analytics_parser, handler=handle_release_audio_regression, help='Release Audio Regression', group='quality'),
    CommandSpec(name='release-audio-baseline', parser=build_acceptance_analytics_parser, handler=handle_release_audio_baseline, help='Release Audio Baseline', group='quality'),
    CommandSpec(name='release-audio-regression-response', parser=build_acceptance_analytics_parser, handler=handle_release_audio_regression_response, help='Release Audio Regression Response', group='quality'),
    CommandSpec(name='release-audio-quality-observatory', parser=build_acceptance_analytics_parser, handler=handle_release_audio_quality_observatory, help='Release Audio Quality Observatory', group='quality'),
    CommandSpec(name='release-audio-quality-actions', parser=build_acceptance_analytics_parser, handler=handle_release_audio_quality_actions, help='Release Audio Quality Actions', group='quality'),
    CommandSpec(name='release-audio-command-center', parser=build_acceptance_analytics_parser, handler=handle_release_audio_command_center, help='Release Audio Command Center', group='quality'),
    CommandSpec(name='verify-release-audio-baseline-registry-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_baseline_registry_package, help='Verify Release Audio Baseline Registry Package', group='quality'),
    CommandSpec(name='verify-release-audio-regression-response-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_regression_response_package, help='Verify Release Audio Regression Response Package', group='quality'),
    CommandSpec(name='verify-release-audio-quality-observatory-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_quality_observatory_package, help='Verify Release Audio Quality Observatory Package', group='quality'),
    CommandSpec(name='verify-release-audio-quality-action-queue-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_quality_action_queue_package, help='Verify Release Audio Quality Action Queue Package', group='quality'),
    CommandSpec(name='verify-release-audio-quality-action-queue-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_quality_action_queue_signoff_archive_package, help='Verify Release Audio Quality Action Queue Signoff Archive Package', group='quality'),
    CommandSpec(name='verify-release-audio-command-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_command_center_package, help='Verify Release Audio Command Center Package', group='quality'),
    CommandSpec(name='verify-unified-command-center-evidence-review-acceptance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_evidence_review_acceptance_package, help='Verify Unified Command Center Evidence Review Acceptance Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-acceptance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_acceptance_package, help='Verify Unified Release Program Continuity Acceptance Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-acceptance-change-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_acceptance_change_package, help='Verify Unified Release Program Continuity Acceptance Change Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-acceptance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_acceptance_package, help='Verify Unified Release Program Continuity Command Center Acceptance Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-acceptance-change-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_acceptance_change_package, help='Verify Unified Release Program Continuity Command Center Acceptance Change Package', group='quality'),
    CommandSpec(name='verify-audio-campaign-package', parser=build_acceptance_analytics_parser, handler=handle_verify_audio_campaign_package, help='Verify Audio Campaign Package', group='quality'),
    CommandSpec(name='verify-audio-campaign-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_audio_campaign_archive_package, help='Verify Audio Campaign Archive Package', group='quality'),
    CommandSpec(name='verify-audio-campaign-remediation-package', parser=build_acceptance_analytics_parser, handler=handle_verify_audio_campaign_remediation_package, help='Verify Audio Campaign Remediation Package', group='quality'),
    CommandSpec(name='verify-release-audio-certification-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_certification_package, help='Verify Release Audio Certification Package', group='quality'),
    CommandSpec(name='verify-release-audio-timeline-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_timeline_package, help='Verify Release Audio Timeline Package', group='quality'),
    CommandSpec(name='verify-release-audio-regression-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_regression_package, help='Verify Release Audio Regression Package', group='quality'),
    CommandSpec(name='acceptance-check', parser=build_acceptance_analytics_parser, handler=handle_acceptance_check, help='Acceptance Check', group='quality'),
    CommandSpec(name='audio-health', parser=build_acceptance_analytics_parser, handler=handle_audio_health, help='Audio Health', group='quality'),
    CommandSpec(name='audio-profile', parser=build_acceptance_analytics_parser, handler=handle_audio_profile, help='Audio Profile', group='quality'),
    CommandSpec(name='release-audio-review', parser=build_acceptance_analytics_parser, handler=handle_release_audio_review, help='Release Audio Review', group='quality'),
    CommandSpec(name='encoded-audio-acceptance', parser=build_acceptance_analytics_parser, handler=handle_encoded_audio_acceptance, help='Encoded Audio Acceptance', group='quality'),
    CommandSpec(name='format-decision', parser=build_acceptance_analytics_parser, handler=handle_format_decision, help='Format Decision', group='quality'),
    CommandSpec(name='acceptance-diff', parser=build_acceptance_analytics_parser, handler=handle_acceptance_diff, help='Acceptance Diff', group='quality'),
    CommandSpec(name='acceptance-analytics', parser=build_acceptance_analytics_parser, handler=handle_acceptance_analytics, help='Acceptance Analytics', group='quality'),
    CommandSpec(name='acceptance-fix-sprint', parser=build_acceptance_fix_plan_parser, handler=handle_acceptance_fix_sprint, help='Acceptance Fix Sprint', group='quality'),
    CommandSpec(name='acceptance-fix-plan', parser=build_acceptance_fix_plan_parser, handler=handle_acceptance_fix_plan, help='Acceptance Fix Plan', group='quality'),
    CommandSpec(name='planning-ruleset', parser=build_acceptance_kb_parser, handler=handle_planning_ruleset, help='Planning Ruleset', group='quality'),
    CommandSpec(name='planning-simulation', parser=build_acceptance_kb_parser, handler=handle_planning_simulation, help='Planning Simulation', group='quality'),
    CommandSpec(name='planning-rule-governance', parser=build_acceptance_kb_parser, handler=handle_planning_rule_governance, help='Planning Rule Governance', group='quality'),
    CommandSpec(name='planning-rule-impact', parser=build_acceptance_kb_parser, handler=handle_planning_rule_impact, help='Planning Rule Impact', group='quality'),
    CommandSpec(name='acceptance-kb', parser=build_acceptance_kb_parser, handler=handle_acceptance_kb, help='Acceptance Kb', group='quality'),
)

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
