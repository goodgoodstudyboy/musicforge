from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path


CLASS_NAMES = ("JobStore", "BatchRunner")


def split_runtime(path: Path, *, target_lines: int = 280, source: str | None = None) -> list[Path]:
    source = path.read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in CLASS_NAMES
    }
    if set(classes) != set(CLASS_NAMES):
        raise ValueError(f"Refusing to split an already aggregated runtime module: {path}")

    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assignments = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and "__all__" not in _bound_names(node)
    ]
    helpers = {
        node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    other_classes = [
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name not in CLASS_NAMES
    ]

    root = path.with_name("runtime_parts")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    outputs: list[Path] = []
    outputs.append(_write(root / "__init__.py", '"""Bounded API runtime implementation modules."""\n'))

    import_owner, dependency_modules = _write_dependencies(root, imports, lines, target_lines)
    outputs.extend(dependency_modules)

    core_nodes: list[ast.AST] = [*assignments, *other_classes]
    core_names = {name for core_node in core_nodes for name in _bound_names(core_node)}
    core_source = _module_source(
        core_nodes,
        lines,
        import_owner,
        local_imports=[],
        exports=sorted(core_names),
    )
    outputs.append(_write(root / "core.py", core_source))

    helper_owner, helper_modules = _write_helpers(
        root,
        helpers,
        lines,
        import_owner,
        core_names,
        target_lines,
    )
    outputs.extend(helper_modules)

    job_module, job_parts = _write_class(
        root,
        classes["JobStore"],
        lines,
        import_owner,
        helper_owner,
        core_names,
        target_lines,
    )
    outputs.extend(job_parts)
    outputs.append(job_module)
    batch_module, batch_parts = _write_class(
        root,
        classes["BatchRunner"],
        lines,
        import_owner,
        helper_owner,
        core_names,
        target_lines,
    )
    outputs.extend(batch_parts)
    outputs.append(batch_module)

    dependency_imports = [
        f"from .runtime_parts.dependencies.part_{index:03d} import *"
        for index in range(1, len(dependency_modules) + 1)
    ]
    helper_imports = [
        f"from .runtime_parts.helpers.part_{index:03d} import *"
        for index in range(1, len(helper_modules) + 1)
    ]
    runtime_source = "\n\n".join(
        [
            "from __future__ import annotations",
            "import sys as _sys\nfrom types import ModuleType as _ModuleType",
            *dependency_imports,
            "from .runtime_parts.core import *",
            *helper_imports,
            "from .runtime_parts.job_store import JobStore",
            "from .runtime_parts.batch_runner import BatchRunner",
            """class _RuntimeModule(_ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        prefix = __name__ + ".runtime_parts."
        for module_name, module in tuple(_sys.modules.items()):
            if module_name.startswith(prefix) and hasattr(module, name):
                setattr(module, name, value)


_sys.modules[__name__].__class__ = _RuntimeModule""",
            "__all__ = [name for name in globals() if not name.startswith('__')]",
        ]
    ) + "\n"
    path.write_text(runtime_source, encoding="utf-8")
    outputs.append(path)
    return outputs


def _write_dependencies(
    root: Path,
    imports: list[ast.Import | ast.ImportFrom],
    lines: list[str],
    target_lines: int,
) -> tuple[dict[str, str], list[Path]]:
    directory = root / "dependencies"
    directory.mkdir()
    _write(directory / "__init__.py", '"""Runtime dependency exports."""\n')
    groups = _pack_nodes(imports, target_lines)
    owner: dict[str, str] = {}
    outputs: list[Path] = []
    for index, group in enumerate(groups, start=1):
        module = f"song_agent.interfaces.api.runtime_parts.dependencies.part_{index:03d}"
        names = sorted({name for node in group for name in _bound_names(node)})
        for name in names:
            owner[name] = module
        body = "\n".join(_node_source(node, lines) for node in group)
        document = f"from __future__ import annotations\n\n{body}\n\n__all__ = {names!r}\n"
        outputs.append(_write(directory / f"part_{index:03d}.py", document))
    return owner, outputs


def _write_helpers(
    root: Path,
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    lines: list[str],
    import_owner: dict[str, str],
    core_names: set[str],
    target_lines: int,
) -> tuple[dict[str, str], list[Path]]:
    directory = root / "helpers"
    directory.mkdir()
    _write(directory / "__init__.py", '"""Runtime helper exports."""\n')
    dependencies = {
        name: (_runtime_names(node) & set(helpers)) - {name} for name, node in helpers.items()
    }
    ordered = _dependency_order(helpers, dependencies)
    groups = _pack_named(ordered, helpers, target_lines)
    owner = {
        name: f"song_agent.interfaces.api.runtime_parts.helpers.part_{index:03d}"
        for index, group in enumerate(groups, start=1)
        for name in group
    }
    outputs: list[Path] = []
    for index, group in enumerate(groups, start=1):
        nodes = [helpers[name] for name in group]
        used = set().union(*(_runtime_names(node) for node in nodes))
        local_imports = [
            f"from {module} import {', '.join(sorted(names))}"
            for module, names in _owners_for(used & set(helpers), owner, exclude=index).items()
        ]
        if used & core_names:
            local_imports.append(
                "from song_agent.interfaces.api.runtime_parts.core import "
                + ", ".join(sorted(used & core_names))
            )
        document = _module_source(
            nodes,
            lines,
            import_owner,
            local_imports=local_imports,
            exports=group,
        )
        outputs.append(_write(directory / f"part_{index:03d}.py", document))
    return owner, outputs


def _write_class(
    root: Path,
    node: ast.ClassDef,
    lines: list[str],
    import_owner: dict[str, str],
    helper_owner: dict[str, str],
    core_names: set[str],
    target_lines: int,
) -> tuple[Path, list[Path]]:
    slug = _snake_case(node.name)
    directory = root / f"{slug}_parts"
    directory.mkdir()
    _write(directory / "__init__.py", f'"""{node.name} method mixins."""\n')
    methods = [child for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
    groups = _pack_nodes(methods, target_lines)
    parts: list[Path] = []
    class_names: list[str] = []
    for index, group in enumerate(groups, start=1):
        class_name = f"{node.name}Part{index:03d}"
        class_names.append(class_name)
        used = set().union(*(_runtime_names(child) for child in group))
        imports = _imports_for_names(used, import_owner)
        helper_imports = _owners_for(used & set(helper_owner), helper_owner)
        imports.extend(
            f"from {module} import {', '.join(sorted(names))}"
            for module, names in helper_imports.items()
        )
        if used & core_names:
            imports.append(
                "from song_agent.interfaces.api.runtime_parts.core import "
                + ", ".join(sorted(used & core_names))
            )
        bodies = "\n\n".join(_node_source(child, lines) for child in group)
        document = "\n\n".join(
            [
                "from __future__ import annotations",
                *imports,
                f"class {class_name}:\n{bodies}",
            ]
        ) + "\n"
        parts.append(_write(directory / f"part_{index:03d}.py", document))
    imports = [
        f"from .{slug}_parts.part_{index:03d} import {class_name}"
        for index, class_name in enumerate(class_names, start=1)
    ]
    module = _write(
        root / f"{slug}.py",
        "\n\n".join(
            [
                "from __future__ import annotations",
                *imports,
                f"class {node.name}({', '.join(class_names)}):\n    pass",
                f"__all__ = ['{node.name}']",
            ]
        )
        + "\n",
    )
    return module, parts


def _module_source(
    nodes: Iterable[ast.AST],
    lines: list[str],
    import_owner: dict[str, str],
    *,
    local_imports: list[str],
    exports: Iterable[str],
) -> str:
    node_list = list(nodes)
    used = set().union(*(_runtime_names(node) for node in node_list)) if node_list else set()
    imports = [*_imports_for_names(used, import_owner), *local_imports]
    body = "\n\n".join(_node_source(node, lines) for node in node_list)
    return "\n\n".join(
        [
            "from __future__ import annotations",
            *imports,
            body,
            f"__all__ = {sorted(exports)!r}",
        ]
    ) + "\n"


def _imports_for_names(names: set[str], owner: dict[str, str]) -> list[str]:
    grouped = _owners_for(names & set(owner), owner)
    return [
        f"from {module} import {', '.join(sorted(values))}" for module, values in grouped.items()
    ]


def _owners_for(
    names: set[str],
    owner: dict[str, str],
    *,
    exclude: int | None = None,
) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    excluded_suffix = f"part_{exclude:03d}" if exclude is not None else ""
    for name in sorted(names):
        module = owner[name]
        if excluded_suffix and module.endswith(excluded_suffix):
            continue
        grouped.setdefault(module, set()).add(name)
    return grouped


def _runtime_names(node: ast.AST) -> set[str]:
    annotations = {
        id(item)
        for item in ast.walk(node)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.arg, ast.AnnAssign))
        for item in _annotation_nodes(item)
        if item is not None
    }
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and id(item) not in annotations
    }


def _annotation_nodes(node: ast.AST) -> list[ast.AST | None]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [node.returns]
    if isinstance(node, ast.arg):
        return [node.annotation]
    if isinstance(node, ast.AnnAssign):
        return [node.annotation]
    return []


def _bound_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.asname or alias.name.split(".", 1)[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom):
        return {alias.asname or alias.name for alias in node.names if alias.name != "*"}
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return {item.id for target in targets for item in ast.walk(target) if isinstance(item, ast.Name)}


def _node_source(node: ast.AST, lines: list[str]) -> str:
    return "\n".join(lines[_source_start(node) - 1 : int(node.end_lineno or node.lineno)])


def _pack_nodes(nodes: list[ast.AST], target_lines: int) -> list[list[ast.AST]]:
    groups: list[list[ast.AST]] = []
    current: list[ast.AST] = []
    count = 0
    for node in nodes:
        size = int(node.end_lineno or node.lineno) - _source_start(node) + 2
        if current and count + size > target_lines:
            groups.append(current)
            current, count = [], 0
        current.append(node)
        count += size
    if current:
        groups.append(current)
    return groups


def _pack_named(
    names: list[str],
    nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    target_lines: int,
) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    count = 0
    for name in names:
        node = nodes[name]
        size = int(node.end_lineno or node.lineno) - _source_start(node) + 2
        if current and count + size > target_lines:
            groups.append(current)
            current, count = [], 0
        current.append(name)
        count += size
    if current:
        groups.append(current)
    return groups


def _dependency_order(
    nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    dependencies: dict[str, set[str]],
) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"Runtime helper dependency cycle: {name}")
        visiting.add(name)
        for dependency in sorted(dependencies[name]):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in nodes:
        visit(name)
    return ordered


def _snake_case(value: str) -> str:
    return "".join(("_" + char.lower()) if char.isupper() and index else char.lower() for index, char in enumerate(value))


def _source_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min([node.lineno, *(item.lineno for item in decorators)])


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Split the API runtime into bounded implementation modules.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target-lines", type=int, default=280)
    parser.add_argument("--git-ref")
    args = parser.parse_args()
    path = args.root.resolve() / "song_agent" / "interfaces" / "api" / "runtime.py"
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
    outputs = split_runtime(path, target_lines=args.target_lines, source=source)
    oversized = [output for output in outputs if len(output.read_text(encoding="utf-8").splitlines()) > 400]
    if oversized:
        raise RuntimeError(f"Generated oversized runtime modules: {oversized}")
    print(f"runtime: {len(outputs)} bounded modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
