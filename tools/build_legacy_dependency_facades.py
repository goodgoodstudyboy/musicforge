from __future__ import annotations

import argparse
import ast
import re
import shutil
from pathlib import Path

from song_agent.architecture_guardrails import build_architecture_snapshot


def build_facades(root: Path) -> dict[str, str]:
    snapshot = build_architecture_snapshot(root)
    ownership = {str(row["module"]): row for row in snapshot["modules"]}
    directory = root / "song_agent" / "application" / "legacy_dependencies"
    targets = _existing_targets(directory)
    if not targets:
        targets = sorted({str(row["imported"]) for row in snapshot["active_to_compatibility_imports"]})
    mapping = {
        target: "song_agent.application.legacy_dependencies." + target.removeprefix("song_agent.").replace(".", "__")
        for target in targets
    }
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir()
    (directory / "__init__.py").write_text(
        '"""Temporary anti-corruption imports for compatibility modules; removed by v13.8."""\n',
        encoding="utf-8",
    )
    for target, facade in mapping.items():
        source = "\n\n".join(
            [
                '"""Single active import boundary for a pre-v13 compatibility module."""',
                f"import {target} as _implementation",
                "globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith('__')})",
                "__all__ = tuple(name for name in globals() if not name.startswith('__'))",
            ]
        ) + "\n"
        (directory / f"{facade.rsplit('.', 1)[-1]}.py").write_text(source, encoding="utf-8")

    for module, row in ownership.items():
        if row["layer"] not in {"interface", "application", "domain"}:
            continue
        path = root / str(row["path"])
        if not path.is_file() or path.is_relative_to(directory):
            continue
        source = path.read_text(encoding="utf-8")
        updated = source
        for target in sorted(mapping, key=len, reverse=True):
            facade = mapping[target]
            updated = re.sub(
                rf"(?m)^(\s*)from\s+{re.escape(target)}\s+import\s+",
                rf"\1from {facade} import ",
                updated,
            )
            updated = re.sub(
                rf"(?m)^(\s*)import\s+{re.escape(target)}\s+as\s+",
                rf"\1import {facade} as ",
                updated,
            )
        if updated != source:
            ast.parse(updated, filename=str(path))
            path.write_text(updated, encoding="utf-8")
    return mapping


def _existing_targets(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    targets: list[str] = []
    for path in directory.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                targets.extend(alias.name for alias in node.names if alias.asname == "_implementation")
            elif isinstance(node, ast.ImportFrom):
                targets.extend(
                    f"{node.module}.{alias.name}" for alias in node.names if alias.asname == "_implementation"
                )
    return sorted(set(targets))


def main() -> int:
    parser = argparse.ArgumentParser(description="Centralize active imports of compatibility modules.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    mapping = build_facades(args.root.resolve())
    print(f"legacy dependency facades: {len(mapping)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
