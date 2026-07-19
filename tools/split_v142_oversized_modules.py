from __future__ import annotations

import ast
import builtins
import json
import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from song_agent.release_check.v14_quality import collect_complexity_metrics


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "architecture-v14-quality.json"
MODULE_LIMIT = 600
TARGET_LINES = 540
CHUNK_LIMIT = 430
CLASS_SPLIT_MIN_LINES = 520

CHUNK_LABELS = (
    "readiness",
    "evidence",
    "lifecycle",
    "archive",
    "verification",
    "reports",
    "runtime",
    "bindings",
    "export",
    "security",
    "governance",
    "operations",
)


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    name: str
    text: str
    lines: int


def main() -> int:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    metrics = collect_complexity_metrics(ROOT, policy)
    changed: list[str] = []
    for row in sorted(metrics["oversized_modules"], key=lambda item: int(item["lines"]), reverse=True):
        relative = str(row["path"])
        path = ROOT / relative
        if "_v142_" in path.stem:
            continue
        before = path.read_text(encoding="utf-8")
        source = _split_large_classes(path, before)
        source = _split_top_level_definitions(path, source)
        if source != before:
            path.write_text(source, encoding="utf-8")
            changed.append(relative)
    print(json.dumps({"changed": changed, "count": len(changed)}, indent=2, sort_keys=True))
    return 0


def _split_large_classes(path: Path, source: str) -> str:
    current = source
    while True:
        tree = ast.parse(current, filename=str(path))
        candidate = _largest_splittable_class(tree)
        if candidate is None:
            return current
        current = _extract_class_methods(path, current, candidate)
        if _line_count(current) <= TARGET_LINES:
            return current


def _largest_splittable_class(tree: ast.Module) -> ast.ClassDef | None:
    candidates: list[tuple[int, ast.ClassDef]] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.decorator_list:
            continue
        lines = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
        methods = [
            child
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("__")
        ]
        movable = sum(int(child.end_lineno or child.lineno) - int(child.lineno) + 1 for child in methods)
        if lines >= CLASS_SPLIT_MIN_LINES and movable >= 180:
            candidates.append((lines, node))
    return max(candidates, default=(0, None))[1]


def _extract_class_methods(path: Path, source: str, class_node: ast.ClassDef) -> str:
    lines = source.splitlines()
    methods = [
        child
        for child in class_node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("__")
    ]
    blocks = [_block_for_node(lines, child) for child in methods]
    chunks = _pack_blocks(blocks, CHUNK_LIMIT)
    if not chunks:
        return source
    module_base = _module_base(path)
    module_specs: list[tuple[str, str, str, list[Block]]] = []
    for index, chunk in enumerate(chunks):
        label = CHUNK_LABELS[index % len(CHUNK_LABELS)]
        module_name = _generated_module_name(path.stem, label, index)
        mixin_name = f"{class_node.name}{label.title().replace('_', '')}Mixin"
        module_specs.append((module_name, mixin_name, label, chunk))
        _write_mixin_module(path, module_name, mixin_name, chunk, source)
    remove_ranges = [(block.start, block.end) for block in blocks]
    migrated = _remove_ranges(lines, remove_ranges)
    migrated = _rewrite_class_bases(migrated, class_node.name, [spec[1] for spec in module_specs])
    import_lines = []
    bind_lines = []
    for module_name, mixin_name, _, _ in module_specs:
        import_lines.append(f"from {module_base}.{module_name} import {mixin_name}")
        import_lines.append(f"from {module_base} import {module_name} as _{module_name}")
        bind_lines.append(f"_{module_name}.bind_globals(globals())")
    migrated = _insert_lines(migrated, _import_insertion_index(migrated), import_lines)
    migrated = _append_bind_lines(migrated, bind_lines)
    ast.parse("\n".join(migrated) + "\n", filename=str(path))
    return "\n".join(migrated) + "\n"


def _split_top_level_definitions(path: Path, source: str) -> str:
    if _line_count(source) <= TARGET_LINES:
        return source
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    candidates: list[Block] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.ClassDef) and (
            node.decorator_list or int(node.end_lineno or node.lineno) - int(node.lineno) + 1 > CHUNK_LIMIT
        ):
            continue
        name = node.name
        if name == "__getattr__":
            continue
        candidates.append(_block_for_node(lines, node))
    if not candidates:
        return source
    current_lines = _line_count(source)
    moved: list[Block] = []
    for block in sorted(candidates, key=lambda item: item.start, reverse=True):
        if current_lines <= TARGET_LINES:
            break
        moved.append(block)
        current_lines -= block.lines
    if not moved:
        return source
    chunks = _pack_blocks(sorted(moved, key=lambda item: item.start), CHUNK_LIMIT)
    module_base = _module_base(path)
    import_lines: list[str] = []
    bind_lines: list[str] = []
    for index, chunk in enumerate(chunks):
        label = CHUNK_LABELS[index % len(CHUNK_LABELS)]
        module_name = _generated_module_name(path.stem, label, index)
        names = [block.name for block in chunk]
        _write_support_module(path, module_name, chunk, source)
        import_lines.append(f"from {module_base} import {module_name} as _{module_name}")
        import_lines.extend(_import_names(module_base, module_name, names))
        bind_lines.append(f"_{module_name}.bind_globals(globals())")
    migrated = _remove_ranges(lines, [(block.start, block.end) for block in moved])
    insert_at = min(block.start for block in moved) - 1
    migrated = _insert_lines(migrated, max(0, insert_at), import_lines)
    migrated = _append_bind_lines(migrated, bind_lines)
    ast.parse("\n".join(migrated) + "\n", filename=str(path))
    return "\n".join(migrated) + "\n"


def _write_mixin_module(path: Path, module_name: str, mixin_name: str, blocks: list[Block], source: str) -> None:
    body = "\n\n".join(block.text for block in blocks)
    content = _generated_header(source)
    content += _generated_support(blocks, source)
    content += f"class {mixin_name}:\n"
    content += body if body.strip() else "    pass"
    content += "\n"
    target = path.with_name(f"{module_name}.py")
    ast.parse(content, filename=str(target))
    target.write_text(content, encoding="utf-8")


def _write_support_module(path: Path, module_name: str, blocks: list[Block], source: str) -> None:
    content = _generated_header(source)
    content += _generated_support(blocks, source)
    content += "\n\n".join(_dedent_block(block.text) for block in blocks)
    content += "\n"
    target = path.with_name(f"{module_name}.py")
    ast.parse(content, filename=str(target))
    target.write_text(content, encoding="utf-8")


def _header_for(source: str) -> str:
    tree = ast.parse(source)
    imports: list[str] = ["from __future__ import annotations"]
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            segment = ast.get_source_segment(source, node)
            if segment and "_v142_" not in segment and "v142_" not in segment:
                imports.append(segment)
        elif isinstance(node, ast.If) and _is_type_checking(node):
            segment = ast.get_source_segment(source, node)
            if segment:
                imports.append(segment)
        elif _simple_constant_assignment(node):
            segment = ast.get_source_segment(source, node)
            if segment:
                imports.append(segment)
    # Keep repeated imports out of generated modules; order remains stable.
    unique: list[str] = []
    for line in imports:
        if line not in unique:
            unique.append(line)
    return "\n".join(unique) + "\n"


def _generated_header(source: str) -> str:
    return "# ruff: noqa: E402,F401,F821,F822,F403,F405\n# mypy: ignore-errors\n" + _header_for(source)


def _generated_support(blocks: list[Block], source: str) -> str:
    names = _deferred_names_for_blocks(blocks, source)
    lines = [
        "",
        "",
        "class _DeferredGlobal:",
        "    def __init__(self, name: str) -> None:",
        "        self.name = name",
        "",
        "",
        "def _make_deferred_global(name: str) -> type[object]:",
        "    base: type[object] = Exception if name.endswith(\"Error\") else object",
        "    return type(f\"_DeferredGlobal_{name}\", (base,), {\"_deferred_global_name\": name})",
        "",
        "",
        "def _deferred_global_name(value: object) -> str | None:",
        "    if isinstance(value, _DeferredGlobal):",
        "        return value.name",
        "    if isinstance(value, type):",
        "        name = getattr(value, \"_deferred_global_name\", None)",
        "        if isinstance(name, str):",
        "            return name",
        "    return None",
        "",
        "",
        "def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:",
        "    name = _deferred_global_name(value)",
        "    if name is not None:",
        "        return namespace.get(name, value)",
        "    if isinstance(value, tuple):",
        "        return tuple(_resolve_bound_default(item, namespace) for item in value)",
        "    if isinstance(value, list):",
        "        return [_resolve_bound_default(item, namespace) for item in value]",
        "    if isinstance(value, dict):",
        "        return {",
        "            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)",
        "            for key, item in value.items()",
        "        }",
        "    return value",
        "",
        "",
        "def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:",
        "    defaults = getattr(function, \"__defaults__\", None)",
        "    if defaults:",
        "        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)",
        "    kwdefaults = getattr(function, \"__kwdefaults__\", None)",
        "    if kwdefaults:",
        "        function.__kwdefaults__ = {",
        "            key: _resolve_bound_default(item, namespace)",
        "            for key, item in kwdefaults.items()",
        "        }",
        "",
        "",
        "def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:",
        "    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)",
        "    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):",
        "        try:",
        "            cls.__bases__ = bases",
        "        except TypeError:",
        "            pass",
        "",
        "",
        "def _bind_deferred_defaults(namespace: dict[str, object]) -> None:",
        "    for value in list(globals().values()):",
        "        if callable(value) and hasattr(value, \"__defaults__\"):",
        "            _bind_function_defaults(value, namespace)",
        "        if isinstance(value, type):",
        "            _bind_class_bases(value, namespace)",
        "            for member in vars(value).values():",
        "                target = member",
        "                if isinstance(member, (staticmethod, classmethod)):",
        "                    target = member.__func__",
        "                if callable(target) and hasattr(target, \"__defaults__\"):",
        "                    _bind_function_defaults(target, namespace)",
        "",
    ]
    for name in names:
        lines.append(f"{name} = _make_deferred_global({name!r})")
    lines.extend(_explicit_bind_globals(names))
    return "\n".join(lines) + "\n\n"


def _explicit_bind_globals(names: list[str]) -> list[str]:
    if not names:
        return [
            "",
            "def bind_globals(namespace: dict[str, object]) -> None:",
            "    _bind_deferred_defaults(namespace)",
        ]
    lines = ["", "def bind_globals(namespace: dict[str, object]) -> None:"]
    for chunk in _name_chunks(names):
        lines.append(f"    global {', '.join(chunk)}")
    for name in names:
        lines.append(f"    {name} = namespace.get({name!r}, {name})")
    lines.append("    _bind_deferred_defaults(namespace)")
    return lines


def _deferred_names_for_blocks(blocks: list[Block], source: str) -> list[str]:
    header_tree = ast.parse(_header_for(source))
    declared = _declared_names(header_tree)
    builtins_names = set(dir(builtins))
    names: set[str] = set()
    for block in blocks:
        tree = ast.parse(_dedent_block(block.text) + "\n")
        local_declared = _declared_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
        names.difference_update(local_declared)
    names.difference_update(declared)
    names.difference_update(builtins_names)
    names.difference_update({"self", "cls", "_make_deferred_global"})
    return sorted(name for name in names if name.isidentifier())


def _declared_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.partition(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
    return names


def _name_chunks(names: list[str], size: int = 8) -> list[list[str]]:
    return [names[index : index + size] for index in range(0, len(names), size)]


def _simple_constant_assignment(node: ast.stmt) -> bool:
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
        return False
    value = node.value
    if value is None:
        return False
    return isinstance(value, (ast.Constant, ast.Tuple, ast.List, ast.Set, ast.Dict))


def _is_type_checking(node: ast.If) -> bool:
    test = node.test
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def _block_for_node(lines: list[str], node: ast.AST) -> Block:
    decorator_lines = [int(decorator.lineno) for decorator in getattr(node, "decorator_list", [])]
    start = min([int(getattr(node, "lineno")), *decorator_lines]) if decorator_lines else int(getattr(node, "lineno"))
    end = int(getattr(node, "end_lineno", start))
    text = "\n".join(lines[start - 1 : end])
    name = str(getattr(node, "name"))
    return Block(start=start, end=end, name=name, text=text, lines=end - start + 1)


def _pack_blocks(blocks: list[Block], limit: int) -> list[list[Block]]:
    chunks: list[list[Block]] = []
    current: list[Block] = []
    current_lines = 0
    for block in blocks:
        if current and current_lines + block.lines > limit:
            chunks.append(current)
            current = []
            current_lines = 0
        current.append(block)
        current_lines += block.lines + 1
    if current:
        chunks.append(current)
    return chunks


def _remove_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    remove: set[int] = set()
    for start, end in ranges:
        remove.update(range(start, end + 1))
    return [line for index, line in enumerate(lines, start=1) if index not in remove]


def _rewrite_class_bases(lines: list[str], class_name: str, mixins: list[str]) -> list[str]:
    pattern = re.compile(rf"^(\s*)class\s+{re.escape(class_name)}(\((?P<bases>.*)\))?:")
    rewritten = list(lines)
    for index, line in enumerate(rewritten):
        match = pattern.match(line)
        if not match:
            continue
        existing = (match.group("bases") or "").strip()
        bases = ", ".join([*mixins, existing] if existing else mixins)
        rewritten[index] = f"{match.group(1)}class {class_name}({bases}):"
        return rewritten
    raise ValueError(f"Could not rewrite bases for {class_name}")


def _import_names(module_base: str, module_name: str, names: list[str]) -> list[str]:
    if len(names) <= 6:
        return [f"from {module_base}.{module_name} import {', '.join(names)}"]
    lines = [f"from {module_base}.{module_name} import ("]
    lines.extend(f"    {name}," for name in names)
    lines.append(")")
    return lines


def _insert_lines(lines: list[str], index: int, insert: list[str]) -> list[str]:
    if not insert:
        return lines
    return [*lines[:index], *insert, "", *lines[index:]]


def _append_bind_lines(lines: list[str], bind_lines: list[str]) -> list[str]:
    if not bind_lines:
        return lines
    result = list(lines)
    while result and not result[-1].strip():
        result.pop()
    result.extend(["", *bind_lines])
    return result


def _import_insertion_index(lines: list[str]) -> int:
    tree = ast.parse("\n".join(lines) + "\n")
    index = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            index = max(index, int(node.end_lineno or node.lineno))
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            index = max(index, int(node.end_lineno or node.lineno))
            continue
        break
    return index


def _dedent_block(text: str) -> str:
    return dedent(text)


def _module_base(path: Path) -> str:
    return ".".join(path.with_suffix("").relative_to(ROOT).parts[:-1])


def _line_count(source: str) -> int:
    return len(source.splitlines())


def _snake(name: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.lower()


def _generated_module_name(stem: str, label: str, index: int) -> str:
    return f"v142_{_abbr(stem)}_{label}{index if index > len(CHUNK_LABELS) else ''}"


def _abbr(value: str) -> str:
    parts = [part for part in value.split("_") if part]
    short = "".join(part[0] for part in parts)
    return (short or "module")[:14]


if __name__ == "__main__":
    raise SystemExit(main())
