from __future__ import annotations
from song_agent.interfaces.cli.registry import CommandSpec
from song_agent.interfaces.cli.commands.creation_parts.generation_commands_and_presenter_adapters import _add_generate_args, build_generate_parser, build_parser, build_serve_parser, generate_from_file, handle_generate, handle_verify_unified_command_center_archive_package, handle_verify_unified_command_center_handoff_package, handle_verify_unified_command_center_package
from song_agent.interfaces.cli.commands.creation_parts.verify_unified_command_center_continuous_review import handle_verify_human_review_pack, handle_verify_unified_command_center_continuous_review_package, handle_verify_unified_command_center_drift_response_package, handle_verify_unified_command_center_evidence_review_package, handle_verify_unified_command_center_reviewer_decision_board_package
from song_agent.interfaces.cli.commands.quality_parts.release_audio_quality_actions import build_acceptance_analytics_parser

__all__ = [ 'SPECS', '_add_generate_args', 'build_generate_parser', 'build_parser', 'build_serve_parser', 'generate_from_file', ]

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
