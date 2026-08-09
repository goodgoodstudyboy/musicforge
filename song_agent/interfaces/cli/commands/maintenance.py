from __future__ import annotations

from song_agent.interfaces.cli.commands.maintenance_parts import maintenance_commands_and_presenter_adapters as _maintenance
from song_agent.interfaces.cli.registry import CommandSpec
from song_agent.interfaces.cli.commands.quality_parts.release_audio_quality_actions import build_acceptance_analytics_parser

_print_maintenance_result = _maintenance._print_maintenance_result
_run_maintenance_command = _maintenance._run_maintenance_command
build_doctor_parser, build_maintenance_parser = _maintenance.build_doctor_parser, _maintenance.build_maintenance_parser
build_verify_maintenance_backup_parser, run_doctor = _maintenance.build_verify_maintenance_backup_parser, _maintenance.run_doctor

__all__ = ['SPECS', '_print_maintenance_result', '_run_maintenance_command', 'build_doctor_parser', 'build_maintenance_parser', 'build_verify_maintenance_backup_parser', 'run_doctor']

SPECS = (
    CommandSpec(name='doctor', parser=build_acceptance_analytics_parser, handler=_maintenance.handle_doctor, help='Doctor', group='maintenance'),
    CommandSpec(name='maintenance', parser=build_acceptance_analytics_parser, handler=_maintenance.handle_maintenance, help='Maintenance', group='maintenance'),
    CommandSpec(name='verify-maintenance-backup', parser=build_acceptance_analytics_parser, handler=_maintenance.handle_verify_maintenance_backup, help='Verify Maintenance Backup', group='maintenance'),
)
