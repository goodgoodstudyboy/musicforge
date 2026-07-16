from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path


PACKAGE = Path("song_agent")
DOMAINS = PACKAGE / "domains"


def normalize(root: Path, *, check: bool = False) -> int:
    consumers = _external_imports(root)
    stale: list[Path] = []
    for path in sorted((root / DOMAINS).rglob("*.py")):
        module = _module_name(root, path)
        exported = consumers.get(module, set())
        if not exported:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        replacements: list[tuple[int, int, str]] = []
        offsets = _line_offsets(source)
        for node in tree.body:
            changed = False
            if isinstance(node, ast.ImportFrom) and node.module != "__future__":
                for alias in node.names:
                    if alias.name in exported and alias.asname is None:
                        alias.asname = alias.name
                        changed = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    if bound in exported and alias.asname is None and "." not in alias.name:
                        alias.asname = bound
                        changed = True
            if not changed:
                continue
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[int(node.end_lineno or node.lineno) - 1] + int(node.end_col_offset or 0)
            replacements.append((start, end, ast.unparse(node)))
        if not replacements:
            continue
        stale.append(path)
        if check:
            continue
        updated = source
        for start, end, replacement in reversed(replacements):
            updated = f"{updated[:start]}{replacement}{updated[end:]}"
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
    if check and stale:
        print("implicit domain reexports: " + ", ".join(str(path.relative_to(root)) for path in stale))
        return 1
    print(f"explicit domain reexports normalized: {len(stale)}")
    return 0


def _external_imports(root: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for path in sorted((root / PACKAGE).rglob("*.py")):
        source_module = _module_name(root, path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            target = _absolute_import(source_module, path.name == "__init__.py", node)
            result[target].update(alias.name for alias in node.names if alias.name != "*")
    return result


def _absolute_import(source_module: str, source_is_package: bool, node: ast.ImportFrom) -> str:
    if not node.level:
        return str(node.module)
    package = source_module.split(".") if source_is_package else source_module.split(".")[:-1]
    anchor = package[: len(package) - node.level + 1]
    return ".".join([*anchor, *((node.module or "").split("."))])


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for index, character in enumerate(source):
        if character == "\n":
            offsets.append(index + 1)
    return offsets


def main() -> int:
    parser = argparse.ArgumentParser(description="Make v14 domain facade exports explicit for static analysis.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return normalize(args.root.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
