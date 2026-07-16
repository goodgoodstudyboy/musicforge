from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.release_check.v14_contracts import CONTRACT_PATH, build_v14_contract_document


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or check the v14 public contract compatibility policy.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    document = build_v14_contract_document(root)
    target = root / CONTRACT_PATH
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        return 0 if target.is_file() and target.read_text(encoding="utf-8") == payload else 1
    target.write_text(payload, encoding="utf-8")
    print(document["baseline"]["contracts"]["web"]["contract_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
