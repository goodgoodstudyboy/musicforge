from __future__ import annotations

from song_agent.interfaces.cli.registry import CommandSpec
from song_agent.interfaces.cli.commands.quality_parts.release_audio_quality_actions import build_acceptance_analytics_parser
from song_agent.interfaces.cli.commands.release_check_parts.ga_check import handle_ga_check
from song_agent.interfaces.cli.commands.release_check_parts.release_check_commands_and_presenter_adapters import (
    build_ga_check_parser,
    build_release_check_parser,
    build_verify_ga_readiness_parser,
    print_ga_readiness_report,
)
from song_agent.interfaces.cli.commands.release_check_parts.verify_ga_readiness import (
    handle_release_check,
    handle_verify_ga_readiness_report,
)

__all__ = ['SPECS', 'build_ga_check_parser', 'build_release_check_parser', 'build_verify_ga_readiness_parser', 'print_ga_readiness_report']

SPECS = (
    CommandSpec(name='ga-check', parser=build_acceptance_analytics_parser, handler=handle_ga_check, help='Ga Check', group='release_check'),
    CommandSpec(name='verify-ga-readiness-report', parser=build_acceptance_analytics_parser, handler=handle_verify_ga_readiness_report, help='Verify Ga Readiness Report', group='release_check'),
    CommandSpec(name='release-check', parser=build_acceptance_analytics_parser, handler=handle_release_check, help='Release Check', group='release_check'),
)
