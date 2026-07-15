from __future__ import annotations

import argparse
import ast
from pathlib import Path


HELPERS = {
    "_is_safe_zip_entry": "is_safe_zip_entry",
    "_raw_zip_entry_names": "raw_central_directory_entry_names",
    "_zip_has_no_trailing_data": "zip_has_no_trailing_data",
}
ACTIVE_ROOTS = ("domains", "application", "interfaces")


def adopt(root: Path, *, check: bool = False) -> int:
    changed: list[str] = []
    remaining: list[str] = []
    for active_root in ACTIVE_ROOTS:
        for path in sorted((root / "song_agent" / active_root).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            functions = [
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in HELPERS
            ]
            if not functions:
                continue
            if check:
                remaining.extend(f"{path.relative_to(root).as_posix()}:{node.name}" for node in functions)
                continue
            lines = source.splitlines(keepends=True)
            for node in sorted(functions, key=lambda item: item.lineno, reverse=True):
                start = int(node.lineno) - 1
                end = int(node.end_lineno or node.lineno)
                while end < len(lines) and not lines[end].strip():
                    end += 1
                del lines[start:end]
            aliases = sorted((HELPERS[node.name], node.name) for node in functions)
            import_lines = ["from song_agent.platform.verification import (\n"]
            import_lines.extend(f"    {public} as {private},\n" for public, private in aliases)
            import_lines.append(")\n")
            insert_at = _import_position(tree, lines)
            lines[insert_at:insert_at] = import_lines
            path.write_text("".join(lines), encoding="utf-8")
            changed.append(path.relative_to(root).as_posix())
    if remaining:
        print("active ZIP security helpers remain:\n" + "\n".join(remaining))
        return 1
    print(f"v14 ZIP security kernel adoption: {len(changed)} files")
    return 0


def _import_position(tree: ast.Module, lines: list[str]) -> int:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            return int(node.end_lineno or node.lineno)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        return int(tree.body[0].end_lineno or tree.body[0].lineno)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Adopt the shared ZIP security kernel in active v14 modules.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return adopt(Path(args.repo_root).resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
