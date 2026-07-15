from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from migrate_v14_domains import _rewrite_imports


TRUST_PACKAGE = "song_agent.domains.trust"


def extract(root: Path, *, plan: bool = False) -> int:
    directory = root / "song_agent" / "domains" / "trust"
    modules = {
        f"{TRUST_PACKAGE}.{path.stem}": path
        for path in directory.glob("*.py")
        if path.name != "__init__.py"
    }
    verifier_modules = {module for module in modules if module.endswith("_verifier")}
    requests: dict[str, set[str]] = defaultdict(set)
    consumers: dict[str, set[Path]] = defaultdict(set)
    for verifier_module in sorted(verifier_modules):
        verifier_path = modules[verifier_module]
        tree = ast.parse(verifier_path.read_text(encoding="utf-8"), filename=str(verifier_path))
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or node.module not in modules:
                continue
            if node.module in verifier_modules or node.module.endswith("_contracts"):
                continue
            requests[node.module].update(alias.name for alias in node.names)
            consumers[node.module].add(verifier_path)

    plans: dict[str, ExtractionPlan] = {}
    for source_module, requested in sorted(requests.items()):
        source_path = modules[source_module]
        source = source_path.read_text(encoding="utf-8")
        plans[source_module] = _build_plan(source_module, source_path, source, requested)

    blocked = {
        module: sorted(plan.store_classes)
        for module, plan in plans.items()
        if plan.store_classes
    }
    if blocked:
        detail = "; ".join(f"{module}: {', '.join(names)}" for module, names in blocked.items())
        raise ValueError(f"Verification contract closure contains Store classes: {detail}")

    print(
        f"trust verification contracts: modules={len(plans)} "
        f"definitions={sum(len(item.selected_names) for item in plans.values())}"
    )
    for module, item in sorted(plans.items()):
        print(f"  {module} -> {item.contract_module} ({len(item.selected_names)} definitions)")
    if plan:
        return 0

    replacements = _contract_replacements(directory)
    for source_module, item in plans.items():
        item.contract_path.write_text(item.contract_source, encoding="utf-8")
        item.source_path.write_text(item.updated_source, encoding="utf-8")
        replacements[source_module] = item.contract_module
    for contract_path in sorted(directory.glob("*_contracts.py")):
        source = contract_path.read_text(encoding="utf-8")
        updated = _rewrite_imports(source, replacements)
        ast.parse(updated, filename=str(contract_path))
        contract_path.write_text(updated, encoding="utf-8")
    for verifier_paths in consumers.values():
        for verifier_path in verifier_paths:
            source = verifier_path.read_text(encoding="utf-8")
            updated = _rewrite_imports(source, replacements)
            ast.parse(updated, filename=str(verifier_path))
            verifier_path.write_text(updated, encoding="utf-8")
    return 0


def _contract_replacements(directory: Path) -> dict[str, str]:
    return {
        f"{TRUST_PACKAGE}.{path.stem.removesuffix('_contracts')}": f"{TRUST_PACKAGE}.{path.stem}"
        for path in directory.glob("*_contracts.py")
    }


class ExtractionPlan:
    def __init__(
        self,
        *,
        source_path: Path,
        contract_module: str,
        contract_path: Path,
        selected_names: set[str],
        store_classes: set[str],
        contract_source: str,
        updated_source: str,
    ) -> None:
        self.source_path = source_path
        self.contract_module = contract_module
        self.contract_path = contract_path
        self.selected_names = selected_names
        self.store_classes = store_classes
        self.contract_source = contract_source
        self.updated_source = updated_source


def _build_plan(
    source_module: str,
    source_path: Path,
    source: str,
    requested: set[str],
) -> ExtractionPlan:
    tree = ast.parse(source, filename=str(source_path))
    definitions = _definitions(tree)
    imports = _import_aliases(tree)
    missing = requested - definitions.keys() - imports.keys()
    if missing:
        raise ValueError(f"Missing contract symbols in {source_module}: {', '.join(sorted(missing))}")

    selected_names = _definition_closure(definitions, requested & definitions.keys())
    selected_nodes = {definitions[name] for name in selected_names}
    store_classes = {
        node.name
        for node in selected_nodes
        if isinstance(node, ast.ClassDef) and node.name.endswith("Store")
    }
    referenced_imports = set(requested & imports.keys())
    for node in selected_nodes:
        referenced_imports.update(_runtime_names(node) & imports.keys())

    import_source = _selected_import_source(tree, referenced_imports)
    definitions_source = [
        ast.get_source_segment(source, node) or ""
        for node in tree.body
        if node in selected_nodes
    ]
    contract_source = "from __future__ import annotations\n"
    if import_source:
        contract_source += "\n" + "\n".join(import_source) + "\n"
    if definitions_source:
        contract_source += "\n\n" + "\n\n\n".join(definitions_source) + "\n"
    ast.parse(contract_source, filename=f"{source_module}_contracts")

    updated_source = _remove_nodes(source, selected_nodes)
    imported_contract_names = selected_names | (requested & imports.keys())
    import_row = (
        f"from {source_module}_contracts import "
        + ", ".join(sorted(imported_contract_names))
    )
    updated_tree = ast.parse(updated_source, filename=str(source_path))
    import_nodes = [
        node for node in updated_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    insert_at = _node_end_offset(updated_source, import_nodes[-1]) if import_nodes else 0
    updated_source = updated_source[:insert_at] + "\n" + import_row + updated_source[insert_at:]
    ast.parse(updated_source, filename=str(source_path))

    contract_module = f"{source_module}_contracts"
    return ExtractionPlan(
        source_path=source_path,
        contract_module=contract_module,
        contract_path=source_path.with_name(f"{source_path.stem}_contracts.py"),
        selected_names=selected_names | (requested & imports.keys()),
        store_classes=store_classes,
        contract_source=contract_source,
        updated_source=updated_source,
    )


def _definitions(tree: ast.Module) -> dict[str, ast.stmt]:
    result: dict[str, ast.stmt] = {}
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [
                child.id
                for target in node.targets
                for child in ast.walk(target)
                if isinstance(child, ast.Name)
            ]
        elif isinstance(node, ast.AnnAssign):
            names = [child.id for child in ast.walk(node.target) if isinstance(child, ast.Name)]
        for name in names:
            result[name] = node
    return result


def _import_aliases(tree: ast.Module) -> dict[str, tuple[ast.stmt, ast.alias]]:
    result: dict[str, tuple[ast.stmt, ast.alias]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                result[alias.asname or alias.name.split(".")[0]] = (node, alias)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                result[alias.asname or alias.name] = (node, alias)
    return result


def _definition_closure(
    definitions: dict[str, ast.stmt],
    roots: Iterable[str],
) -> set[str]:
    selected = set(roots)
    pending = list(selected)
    while pending:
        name = pending.pop()
        node = definitions[name]
        for dependency in _runtime_names(node) & definitions.keys():
            if dependency not in selected:
                selected.add(dependency)
                pending.append(dependency)
    return selected


class _RuntimeNameCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for value in [*node.args.defaults, *[item for item in node.args.kw_defaults if item]]:
            self.visit(value)
        for statement in node.body:
            self.visit(statement)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.target)
        if node.value is not None:
            self.visit(node.value)


def _runtime_names(node: ast.AST) -> set[str]:
    collector = _RuntimeNameCollector()
    collector.visit(node)
    return collector.names


def _selected_import_source(tree: ast.Module, names: set[str]) -> list[str]:
    result: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            aliases = [alias for alias in node.names if (alias.asname or alias.name.split(".")[0]) in names]
            if aliases:
                result.append("import " + ", ".join(_alias_source(alias) for alias in aliases))
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            aliases = [alias for alias in node.names if (alias.asname or alias.name) in names]
            if aliases:
                prefix = "." * node.level + (node.module or "")
                result.append(f"from {prefix} import " + ", ".join(_alias_source(alias) for alias in aliases))
    return result


def _alias_source(alias: ast.alias) -> str:
    return f"{alias.name} as {alias.asname}" if alias.asname else alias.name


def _remove_nodes(source: str, nodes: set[ast.stmt]) -> str:
    result = source
    spans = [(_node_start_offset(source, node), _node_end_offset(source, node)) for node in nodes]
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + result[end:]
    return result


def _node_start_offset(source: str, node: ast.AST) -> int:
    return _offset(source, int(node.lineno), int(node.col_offset))


def _node_end_offset(source: str, node: ast.AST) -> int:
    return _offset(source, int(node.end_lineno or node.lineno), int(node.end_col_offset or 0))


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    return extract(Path.cwd(), plan=args.plan)


if __name__ == "__main__":
    raise SystemExit(main())
