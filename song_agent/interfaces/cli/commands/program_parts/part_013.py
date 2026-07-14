from __future__ import annotations

from .dependencies import *

from .part_001 import _print_release_audio_certification_result

from .part_006 import build_unified_release_program_continuity_acceptance_change_parser, build_unified_release_program_continuity_command_center_acceptance_parser, build_unified_release_program_continuity_command_center_parser, build_unified_release_program_continuity_command_center_signoff_parser

from .part_007 import build_unified_release_program_continuity_command_center_acceptance_change_parser

from .part_011 import _run_unified_release_program_continuity_acceptance_change_command, _run_unified_release_program_continuity_command_center_acceptance_command, _run_unified_release_program_continuity_command_center_command, _run_unified_release_program_continuity_command_center_signoff_command

from .part_012 import _run_unified_release_program_continuity_command_center_acceptance_change_command

def _execute_unified_release_program_continuity_acceptance_change(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-acceptance-change', *argv]
    parser = build_unified_release_program_continuity_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_acceptance_change_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_acceptance_change(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_acceptance_change(argv)

def _execute_unified_release_program_continuity_command_center(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center', *argv]
    parser = build_unified_release_program_continuity_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center(argv)

def _execute_unified_release_program_continuity_command_center_signoff(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-signoff', *argv]
    parser = build_unified_release_program_continuity_command_center_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_signoff_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center_signoff(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_signoff(argv)

def _execute_unified_release_program_continuity_command_center_acceptance(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-acceptance', *argv]
    parser = build_unified_release_program_continuity_command_center_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_acceptance_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center_acceptance(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_acceptance(argv)

def _execute_unified_release_program_continuity_command_center_acceptance_change(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-acceptance-change', *argv]
    parser = build_unified_release_program_continuity_command_center_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_acceptance_change_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center_acceptance_change(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_acceptance_change(argv)

__all__ = ('_execute_unified_release_program_continuity_acceptance_change', 'handle_unified_release_program_continuity_acceptance_change', '_execute_unified_release_program_continuity_command_center', 'handle_unified_release_program_continuity_command_center', '_execute_unified_release_program_continuity_command_center_signoff', 'handle_unified_release_program_continuity_command_center_signoff', '_execute_unified_release_program_continuity_command_center_acceptance', 'handle_unified_release_program_continuity_command_center_acceptance', '_execute_unified_release_program_continuity_command_center_acceptance_change', 'handle_unified_release_program_continuity_command_center_acceptance_change')
