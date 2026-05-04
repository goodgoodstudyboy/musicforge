from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.schemas.song import SongRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a song plan.")
    parser.add_argument("request", type=Path, help="Path to a song request JSON file.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs"),
        help="Output directory. Defaults to ./outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the normalized request without calling an LLM.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    raw = json.loads(args.request.read_text(encoding="utf-8"))
    request = SongRequest.from_dict(raw)

    if args.dry_run:
        print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        return

    args.out.mkdir(parents=True, exist_ok=True)
    raise SystemExit(
        "Generation pipeline is scaffolded but not implemented yet. "
        "Use --dry-run for schema validation."
    )


if __name__ == "__main__":
    main()

