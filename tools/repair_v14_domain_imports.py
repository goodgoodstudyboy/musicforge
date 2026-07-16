from __future__ import annotations

import argparse
import ast
from pathlib import Path


DOMAIN_ROOT = Path("song_agent/domains")
REQUIRED_IMPORTS = {
    "Any": "from typing import Any",
    "Path": "from pathlib import Path",
}
PROJECT_DUPLICATE_IMPORTS = {
    "Any",
    "BLOCKED_ASSET_METADATA_KEYS",
    "Path",
    "ProjectDocument",
    "_sanitize_asset_metadata",
    "annotations",
    "json",
    "read_json",
    "sanitize_metadata",
}


def repair(root: Path, *, check: bool = False) -> int:
    stale: list[Path] = []
    for path in sorted((root / DOMAIN_ROOT).rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        bound = _module_bindings(tree)
        required = [
            name
            for name in REQUIRED_IMPORTS
            if name not in bound and any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name for node in ast.walk(tree))
        ]
        if not required:
            continue
        stale.append(path)
        if check:
            continue
        lines = source.splitlines(keepends=True)
        insert_at = _future_import_end(tree)
        rows = [f"{REQUIRED_IMPORTS[name]}\n" for name in required]
        if insert_at < len(lines) and lines[insert_at].strip():
            rows.append("\n")
        lines[insert_at:insert_at] = rows
        updated = "".join(lines)
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
    project_path = root / DOMAIN_ROOT / "studio" / "projects.py"
    if _project_composition_needs_repair(project_path):
        stale.append(project_path)
        if not check:
            _repair_project_composition(project_path)
    if check and stale:
        print("domain type imports missing: " + ", ".join(str(path.relative_to(root)) for path in stale))
        return 1
    print(f"domain type imports repaired: {len(stale)}")
    return 0


def _project_composition_needs_repair(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    repository_import = next(
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "song_agent.domains.studio.project_repository"
    )
    return bool({alias.name for alias in repository_import.names} & PROJECT_DUPLICATE_IMPORTS)


def _repair_project_composition(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    repository_import = next(
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "song_agent.domains.studio.project_repository"
    )
    repository_import.names = [alias for alias in repository_import.names if alias.name not in PROJECT_DUPLICATE_IMPORTS]
    lines = source.splitlines(keepends=True)
    start = repository_import.lineno - 1
    end = int(repository_import.end_lineno or repository_import.lineno)
    lines[start:end] = [ast.unparse(repository_import) + "\n"]
    updated = "".join(lines)
    ast.parse(updated, filename=str(path))
    path.write_text(updated, encoding="utf-8")


def _module_bindings(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            result.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            result.update(name.id for name in ast.walk(node) if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store))
    return result


def _future_import_end(tree: ast.Module) -> int:
    end = 0
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            end = int(node.end_lineno or node.lineno)
    return end


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair type imports lost during the v14 domain split.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return repair(args.root.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
