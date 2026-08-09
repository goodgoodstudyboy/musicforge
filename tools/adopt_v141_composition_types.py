from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from song_agent.platform.verification.hashing import integrity_ok


@dataclass(frozen=True)
class ContextSpec:
    source_dir: str
    context_path: str
    context_module: str
    context_class: str
    recursive: bool = True
    include_classes_with_bases: bool = False


CONTEXT_SPECS = (
    ContextSpec("song_agent/interfaces/api/routes/creation_parts", "song_agent/interfaces/api/route_contexts/creation.py", "song_agent.interfaces.api.route_contexts.creation", "CreationRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/studio_parts", "song_agent/interfaces/api/route_contexts/studio.py", "song_agent.interfaces.api.route_contexts.studio", "StudioRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/studio_dispatch_parts", "song_agent/interfaces/api/route_contexts/studio_dispatch.py", "song_agent.interfaces.api.route_contexts.studio_dispatch", "StudioDispatchRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/quality_parts", "song_agent/interfaces/api/route_contexts/quality.py", "song_agent.interfaces.api.route_contexts.quality", "QualityRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/delivery_parts", "song_agent/interfaces/api/route_contexts/delivery.py", "song_agent.interfaces.api.route_contexts.delivery", "DeliveryRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/trust_parts", "song_agent/interfaces/api/route_contexts/trust.py", "song_agent.interfaces.api.route_contexts.trust", "TrustRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/trust_portfolio_parts", "song_agent/interfaces/api/route_contexts/trust_portfolio.py", "song_agent.interfaces.api.route_contexts.trust_portfolio", "TrustPortfolioRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/program_parts", "song_agent/interfaces/api/route_contexts/program.py", "song_agent.interfaces.api.route_contexts.program", "ProgramRouteContext"),
    ContextSpec("song_agent/interfaces/api/routes/program_ucc_parts", "song_agent/interfaces/api/route_contexts/program_ucc.py", "song_agent.interfaces.api.route_contexts.program_ucc", "ProgramUccRouteContext"),
    ContextSpec("song_agent/application/program/http_routes", "song_agent/application/program/http_context.py", "song_agent.application.program.http_context", "ProgramHttpContext"),
    ContextSpec("song_agent/interfaces/api/runtime_parts/job_store_parts", "song_agent/interfaces/api/runtime_parts/job_store_context.py", "song_agent.interfaces.api.runtime_parts.job_store_context", "JobStoreContext"),
    ContextSpec("song_agent/interfaces/api/runtime_parts/batch_runner_parts", "song_agent/interfaces/api/runtime_parts/batch_runner_context.py", "song_agent.interfaces.api.runtime_parts.batch_runner_context", "BatchRunnerContext"),
    ContextSpec("song_agent/interfaces/api/routes", "song_agent/interfaces/api/route_contexts/core.py", "song_agent.interfaces.api.route_contexts.core", "CoreRouteContext", recursive=False, include_classes_with_bases=True),
)


def adopt_composition_types(root: Path, *, write: bool) -> dict[str, object]:
    if _retired_by_wave1(root):
        return {
            "changed_files": [],
            "contexts": {},
            "status": "retired_by_v14.4_wave1",
        }
    changed: list[str] = []
    contexts: dict[str, int] = {}
    for spec in CONTEXT_SPECS:
        source_dir = root / spec.source_dir
        if not source_dir.is_dir():
            continue
        paths = sorted(source_dir.rglob("*.py") if spec.recursive else source_dir.glob("*.py"))
        paths = [path for path in paths if path.name != "__init__.py"]
        candidates = [
            (path, _leaf_classes(path, spec.context_class, include_classes_with_bases=spec.include_classes_with_bases))
            for path in paths
        ]
        candidates = [(path, classes) for path, classes in candidates if classes]
        attributes = sorted({name for path, classes in candidates for name in _self_attributes(path, classes)})
        context_path = root / spec.context_path
        context_source = _context_source(spec.context_class, attributes)
        contexts[spec.context_class] = len(attributes)
        if not context_path.is_file() or context_path.read_text(encoding="utf-8") != context_source:
            changed.append(context_path.relative_to(root).as_posix())
            if write:
                context_path.parent.mkdir(parents=True, exist_ok=True)
                context_path.write_text(context_source, encoding="utf-8")
                init = context_path.parent / "__init__.py"
                if not init.exists():
                    init.write_text('"""Static composition contracts for API route mixins."""\n', encoding="utf-8")
        for path, classes in candidates:
            source = path.read_text(encoding="utf-8")
            updated = _adopt_context(source, spec.context_module, spec.context_class, classes)
            if updated != source:
                changed.append(path.relative_to(root).as_posix())
                if write:
                    path.write_text(updated, encoding="utf-8")

    for path in _active_interface_files(root):
        source = path.read_text(encoding="utf-8")
        updated = _replace_forwarded_annotation_names(source)
        if updated != source:
            changed.append(path.relative_to(root).as_posix())
            if write:
                path.write_text(updated, encoding="utf-8")
    return {"changed_files": sorted(set(changed)), "contexts": contexts}


def _retired_by_wave1(root: Path) -> bool:
    path = root / "architecture-v14.4-wave1-surface-migration.json"
    if not path.is_file():
        return False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        document.get("package_type") == "musicforge_v144_wave1_surface_migration"
        and document.get("migration_id") == "v14.4-wave1-platform-application-interfaces"
        and document.get("status") == "candidate"
        and integrity_ok(document)
    )


def _leaf_classes(path: Path, context_class: str, *, include_classes_with_bases: bool) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and (
            include_classes_with_bases
            or not node.bases
            or any(isinstance(base, ast.Name) and base.id == context_class for base in node.bases)
        )
        and _class_self_attributes(node)
    )


def _self_attributes(path: Path, classes: tuple[str, ...]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in classes
        for name in _class_self_attributes(node)
    }


def _class_self_attributes(node: ast.ClassDef) -> set[str]:
    return {
        child.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute)
        and isinstance(child.value, ast.Name)
        and child.value.id == "self"
    }


def _context_source(class_name: str, attributes: list[str]) -> str:
    rows = [
        "from __future__ import annotations\n\n",
        "from typing import Any\n\n\n",
        f"class {class_name}:\n",
        '    """Static inventory of members supplied by runtime composition."""\n\n',
    ]
    rows.extend(f"    {name}: Any\n" for name in attributes)
    return "".join(rows)


def _adopt_context(source: str, module: str, class_name: str, classes: tuple[str, ...]) -> str:
    if f"from {module} import {class_name}" in source:
        return source
    tree = ast.parse(source)
    replacements: list[tuple[int, int, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in classes and not node.bases:
            start = _offset(source, node.lineno, node.col_offset)
            marker = f"class {node.name}:"
            replacements.append((start, start + len(marker), f"class {node.name}({class_name}):"))
        elif isinstance(node, ast.ClassDef) and node.name in classes:
            start = _offset(source, node.lineno, node.col_offset)
            line_end = source.find("\n", start)
            line_end = len(source) if line_end < 0 else line_end
            header = source[start:line_end]
            close = header.rfind("):")
            if close < 0:
                raise RuntimeError(f"Multiline class headers are not supported: {node.name}")
            position = start + close
            replacements.append((position, position, f", {class_name}"))
    if not replacements:
        return source
    updated = _apply_replacements(source, replacements)
    return _insert_import(updated, f"from {module} import {class_name}")


def _replace_forwarded_annotation_names(source: str) -> str:
    source = source.replace("_InterfaceType.ArgumentParser", "argparse.ArgumentParser")
    source = source.replace("_InterfaceType.Namespace", "argparse.Namespace")
    tree = ast.parse(source)
    forwarded: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.Tuple, ast.List)):
            continue
        for target in node.targets:
            if isinstance(target, (ast.Tuple, ast.List)):
                forwarded.update(item.id for item in target.elts if isinstance(item, ast.Name))
    replacements: list[tuple[int, int, str]] = []
    for annotation in _annotations(tree):
        parents = {child: parent for parent in ast.walk(annotation) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(annotation):
            if not isinstance(node, ast.Attribute) or isinstance(parents.get(node), ast.Attribute):
                continue
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id == "_interfaces_api_runtime":
                replacements.append(
                    (
                        _offset(source, node.lineno, node.col_offset),
                        _offset(source, int(node.end_lineno or node.lineno), int(node.end_col_offset or node.col_offset)),
                        "_InterfaceType",
                    )
                )
        for node in ast.walk(annotation):
            parent = parents.get(node)
            if (
                isinstance(node, ast.Name)
                and node.id in forwarded
                and not (isinstance(parent, ast.Attribute) and parent.value is node)
            ):
                replacements.append(
                    (
                        _offset(source, node.lineno, node.col_offset),
                        _offset(source, int(node.end_lineno or node.lineno), int(node.end_col_offset or node.col_offset)),
                        "_InterfaceType",
                    )
                )
    if not replacements:
        return source
    updated = _apply_replacements(source, replacements)
    return _insert_import(updated, "from typing import Any as _InterfaceType")


def _annotations(tree: ast.Module) -> list[ast.expr]:
    result: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                result.append(node.returns)
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                if argument.annotation is not None:
                    result.append(argument.annotation)
            if node.args.vararg and node.args.vararg.annotation is not None:
                result.append(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation is not None:
                result.append(node.args.kwarg.annotation)
        elif isinstance(node, ast.AnnAssign):
            result.append(node.annotation)
    return result


def _insert_import(source: str, row: str) -> str:
    if row in source:
        return source
    tree = ast.parse(source)
    future = next(
        (node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"),
        None,
    )
    position = _offset(source, int(future.end_lineno), int(future.end_col_offset)) if future else 0
    return source[:position] + "\n\n" + row + source[position:]


def _apply_replacements(source: str, replacements: list[tuple[int, int, str]]) -> str:
    updated = source
    for start, end, value in sorted(set(replacements), reverse=True):
        updated = updated[:start] + value + updated[end:]
    return updated


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


def _active_interface_files(root: Path) -> list[Path]:
    return sorted((root / "song_agent" / "interfaces").rglob("*.py"))


if __name__ == "__main__":
    result = adopt_composition_types(Path.cwd(), write=True)
    print(f"composition typing: changed={len(result['changed_files'])} contexts={result['contexts']}")
