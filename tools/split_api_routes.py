from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path


CONTEXTS = {
    "creation": ("CreationRoutes", {"_handle_project_route"}),
    "quality": ("QualityRoutes", set()),
    "delivery": ("DeliveryRoutes", {"_handle_release_signoff"}),
    "trust": ("TrustRoutes", {"_handle_release_portfolio_audits"}),
    "studio": ("StudioRoutes", {"_handle_request"}),
    "program": ("ProgramRoutes", {"_handle_unified_command_centers_route"}),
}


def split_route(
    path: Path,
    class_name: str,
    anchors: set[str],
    *,
    target_lines: int = 330,
    source: str | None = None,
) -> list[Path]:
    source = path.read_text(encoding="utf-8") if source is None else source
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    route_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    methods = [node for node in route_class.body if isinstance(node, ast.FunctionDef)]
    if not methods:
        raise ValueError(f"Refusing to split an already aggregated route module: {path}")
    anchor_methods = [node for node in methods if node.name in anchors]
    movable = [node for node in methods if node.name not in anchors]
    groups = _pack(movable, target_lines)
    imports = [
        "\n".join(lines[_source_start(node) - 1 : node.end_lineno])
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]

    parts_dir = path.with_name(f"{path.stem}_parts")
    parts_dir.mkdir(exist_ok=True)
    for old in parts_dir.glob("part_*.py"):
        old.unlink()
    (parts_dir / "__init__.py").write_text('"""Route mixins split at method boundaries."""\n', encoding="utf-8")
    outputs: list[Path] = []
    part_classes = []
    for index, group in enumerate(groups, start=1):
        part_class = f"{class_name}Part{index:03d}"
        part_classes.append(part_class)
        bodies = ["\n".join(lines[_source_start(node) - 1 : node.end_lineno]) for node in group]
        document = "\n\n".join(
            [
                "from __future__ import annotations",
                *imports,
                f"class {part_class}:\n" + "\n\n".join(bodies),
            ]
        ) + "\n"
        output = parts_dir / f"part_{index:03d}.py"
        output.write_text(document, encoding="utf-8")
        outputs.append(output)

    part_imports = [
        f"from .{path.stem}_parts.part_{index:03d} import {part_class}"
        for index, part_class in enumerate(part_classes, start=1)
    ]
    bases = ", ".join(part_classes) if part_classes else "object"
    anchor_source = "\n\n".join(
        "\n".join(lines[_source_start(node) - 1 : node.end_lineno]) for node in anchor_methods
    ) or "    pass"
    aggregator = "\n\n".join(
        [
            "from __future__ import annotations",
            *imports,
            *part_imports,
            f"class {class_name}({bases}):\n{anchor_source}",
        ]
    ) + "\n"
    path.write_text(aggregator, encoding="utf-8")
    return outputs


def _pack(methods: list[ast.FunctionDef], target_lines: int) -> list[list[ast.FunctionDef]]:
    groups: list[list[ast.FunctionDef]] = []
    current: list[ast.FunctionDef] = []
    current_lines = 0
    for method in methods:
        size = int(method.end_lineno or method.lineno) - _source_start(method) + 2
        if current and current_lines + size > target_lines:
            groups.append(current)
            current = []
            current_lines = 0
        current.append(method)
        current_lines += size
    if current:
        groups.append(current)
    return groups


def _source_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min([node.lineno, *(item.lineno for item in decorators)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Split API route classes into bounded mixins.")
    parser.add_argument("contexts", nargs="*", default=tuple(CONTEXTS))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target-lines", type=int, default=330)
    parser.add_argument("--git-ref")
    args = parser.parse_args()
    routes = args.root.resolve() / "song_agent" / "interfaces" / "api" / "routes"
    for context in args.contexts:
        class_name, anchors = CONTEXTS[context]
        path = routes / f"{context}.py"
        source = None
        if args.git_ref:
            relative = path.relative_to(args.root.resolve()).as_posix()
            source = subprocess.run(
                ["git", "show", f"{args.git_ref}:{relative}"],
                cwd=args.root.resolve(),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
        outputs = split_route(
            path,
            class_name,
            set(anchors),
            target_lines=args.target_lines,
            source=source,
        )
        print(f"{context}: {len(outputs)} parts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
