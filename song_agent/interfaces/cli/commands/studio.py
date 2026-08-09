
from song_agent.interfaces.cli.commands.creation_parts.generation_commands_and_presenter_adapters import build_serve_parser

import argparse
import os
from pathlib import Path
from song_agent.platform.auth import build_auth_config

from song_agent.interfaces.cli.registry import CommandSpec

def build_verify_human_review_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Human Review Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Human Review Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def _writable_status(path: Path) -> str:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".musicforge-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return "failed"
    return "ok"

def _execute_serve(argv: list[str]) -> None:
    raw_args = ['serve', *argv]
    parser = build_serve_parser()
    args = parser.parse_args(raw_args[1:])
    from song_agent.server import serve
    auth_config = build_auth_config(args.host, args.access_token, os.environ)
    serve(args.host, args.port, auth_config=auth_config)
    return

def handle_serve(argv: list[str]) -> None:
    _execute_serve(argv)

SPECS = (
    CommandSpec(name='serve', parser=build_serve_parser, handler=handle_serve, help='Serve', group='studio'),
)
