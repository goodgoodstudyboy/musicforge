from __future__ import annotations

import argparse
from collections.abc import Callable

from song_agent.interfaces.cli.commands import program as compatibility
from song_agent.interfaces.cli.registry import CommandSpec
from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.contracts.coercion import as_document as _as_document


ParserFactory = Callable[[], argparse.ArgumentParser]
Runner = Callable[[argparse.Namespace], JsonDocument]


def _execute(
    argv: list[str],
    parser_factory: ParserFactory,
    runner: Runner,
) -> None:
    args = parser_factory().parse_args(argv)
    result = runner(args)
    compatibility._print_release_audio_certification_result(
        result,
        json_output=bool(getattr(args, "json", False)),
    )
    status = str(result.get("status") or _as_document(result.get("summary")).get("status") or "")
    if result.get("ok") is False or status in {
        "failed",
        "blocked",
        "stale",
        "no_go",
        "runtime_failed",
        "verification_failed",
    }:
        raise SystemExit(1)


def _handler(
    command: str,
    parser_factory: ParserFactory,
    runner: Runner,
) -> Callable[[list[str]], None]:
    def handle(argv: list[str]) -> None:
        _execute(argv, parser_factory, runner)

    return handle


def _parser(parser_factory: ParserFactory) -> ParserFactory:
    def build() -> argparse.ArgumentParser:
        return parser_factory()

    return build


_COMMANDS: tuple[tuple[str, ParserFactory, Runner, str], ...] = (
    ("unified-release-program", compatibility.build_unified_release_program_parser, compatibility._run_unified_release_program_command, "Unified Release Program"),
    ("unified-release-program-operations", compatibility.build_unified_release_program_operations_parser, compatibility._run_unified_release_program_operations_command, "Unified Release Program Operations"),
    ("unified-release-program-handoff", compatibility.build_unified_release_program_handoff_parser, compatibility._run_unified_release_program_handoff_command, "Unified Release Program Handoff"),
    ("unified-release-program-vault", compatibility.build_unified_release_program_vault_parser, compatibility._run_unified_release_program_vault_command, "Unified Release Program Vault"),
    ("unified-release-program-vault-ops", compatibility.build_unified_release_program_vault_operations_parser, compatibility._run_unified_release_program_vault_operations_command, "Unified Release Program Vault Operations"),
    ("unified-release-program-continuity", compatibility.build_unified_release_program_continuity_parser, compatibility._run_unified_release_program_continuity_command, "Unified Release Program Continuity"),
    ("unified-release-program-continuity-kit", compatibility.build_unified_release_program_continuity_distribution_parser, compatibility._run_unified_release_program_continuity_distribution_command, "Unified Release Program Continuity Kit"),
    ("unified-release-program-continuity-acceptance", compatibility.build_unified_release_program_continuity_acceptance_parser, compatibility._run_unified_release_program_continuity_acceptance_command, "Unified Release Program Continuity Acceptance"),
    ("unified-release-program-continuity-acceptance-change", compatibility.build_unified_release_program_continuity_acceptance_change_parser, compatibility._run_unified_release_program_continuity_acceptance_change_command, "Unified Release Program Continuity Acceptance Change"),
    ("unified-release-program-continuity-command-center", compatibility.build_unified_release_program_continuity_command_center_parser, compatibility._run_unified_release_program_continuity_command_center_command, "Unified Release Program Continuity Command Center"),
    ("unified-release-program-continuity-command-center-signoff", compatibility.build_unified_release_program_continuity_command_center_signoff_parser, compatibility._run_unified_release_program_continuity_command_center_signoff_command, "Unified Release Program Continuity Command Center Signoff"),
    ("unified-release-program-continuity-command-center-acceptance", compatibility.build_unified_release_program_continuity_command_center_acceptance_parser, compatibility._run_unified_release_program_continuity_command_center_acceptance_command, "Unified Release Program Receiver Acceptance"),
    ("unified-release-program-continuity-command-center-acceptance-change", compatibility.build_unified_release_program_continuity_command_center_acceptance_change_parser, compatibility._run_unified_release_program_continuity_command_center_acceptance_change_command, "Unified Release Program Receiver Acceptance Change"),
)


SPECS = tuple(
    CommandSpec(
        name=name,
        parser=_parser(parser),
        handler=_handler(name, parser, runner),
        help=help_text,
        exit_code_policy="program-result-v1",
        group="program",
    )
    for name, parser, runner, help_text in _COMMANDS
)
