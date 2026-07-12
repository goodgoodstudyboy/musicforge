from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from song_agent.platform.persistence import LegacyWorkspaceMigrator, PersistenceRecovery, WorkspaceLock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="song-agent-state", description="MusicForge local state maintenance")
    parser.add_argument("--workspace", default=".musicforge", help="MusicForge workspace root")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("migrate-plan")
    subparsers.add_parser("migrate-apply")
    rollback = subparsers.add_parser("migrate-rollback")
    rollback.add_argument("migration_id")
    subparsers.add_parser("recover")
    recover_lock = subparsers.add_parser("recover-lock")
    recover_lock.add_argument("--force", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace)
    try:
        if args.action == "migrate-plan":
            result = LegacyWorkspaceMigrator(workspace).dry_run()
        elif args.action == "migrate-apply":
            result = LegacyWorkspaceMigrator(workspace).execute()
        elif args.action == "migrate-rollback":
            result = LegacyWorkspaceMigrator(workspace).rollback(args.migration_id)
        elif args.action == "recover":
            result = PersistenceRecovery(workspace).recover()
        else:
            result = {"status": "passed", "recovered": WorkspaceLock(workspace).recover(force=args.force)}
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
