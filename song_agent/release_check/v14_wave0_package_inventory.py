from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import cast

from song_agent.platform.contracts.packages import (
    PACKAGE_WRITER_GUARD_ALIAS,
    PACKAGE_WRITER_GUARD_BINDING_HASH,
    PACKAGE_WRITER_GUARD_SYMBOL,
)
from song_agent.release_check.v14_wave0_catalog_model import module_constants, resolve_string
from song_agent.release_check.v14_wave0_source import source_fragments_hash, source_text_hash


PACKAGE_KEY = "package_type"
WRITER_GUARD = PACKAGE_WRITER_GUARD_SYMBOL.rsplit(".", 1)[-1]
WRITER_GUARD_SYMBOL = PACKAGE_WRITER_GUARD_SYMBOL
WRITER_GUARD_MODULE = "song_agent.platform.contracts.packages"
WRITER_GUARD_ALIAS = PACKAGE_WRITER_GUARD_ALIAS


@dataclass(frozen=True)
class _GuardBinding:
    alias: str
    binding_hash: str
    valid: bool


@dataclass(frozen=True)
class _WriterEffect:
    expression: ast.expr
    line: int
    guard_writer_id: str
    value_parameters: frozenset[str]


def package_writer_contract_observations(
    trees: dict[str, ast.AST],
    sources: dict[str, str],
    source_texts: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for module, tree in trees.items():
        collector = _WriterContractCollector(
            module,
            sources[module],
            source_texts[module],
            module_constants(tree),
            _canonical_guard_binding(tree),
            source_text_hash(source_texts[module]),
        )
        collector.visit(tree)
        rows.extend(collector.rows())
    return sorted(rows, key=lambda row: str(row["writer_id"]))


def package_writer_contract_blockers(
    trees: dict[str, ast.AST],
    sources: dict[str, str],
    source_texts: dict[str, str],
    registry: dict[str, object],
) -> list[str]:
    return package_writer_registry_blockers(
        package_writer_contract_observations(trees, sources, source_texts),
        registry,
    )


def package_writer_registry_blockers(
    observations: list[dict[str, object]],
    registry: dict[str, object],
) -> list[str]:
    observed = {str(row["writer_id"]): row for row in observations}
    declared = {
        str(row.get("writer_id") or ""): row
        for row in cast(list[dict[str, object]], registry.get("writer_contracts") or [])
    }
    blockers: list[str] = []
    for writer_id, row in observed.items():
        contract = declared.get(writer_id)
        if contract is None:
            blockers.append(f"v144_wave0_package_writer_unregistered:{writer_id}")
            continue
        if not row["guarded"]:
            blockers.append(f"v144_wave0_package_writer_unguarded:{writer_id}")
        for field in (
            "source",
            "line",
            "value_parameters",
            "expression_source_hash",
            "module_source_hash",
            "guard_symbol",
            "guard_alias",
            "guard_binding_hash",
        ):
            if row.get(field) != contract.get(field):
                blockers.append(f"v144_wave0_package_writer_contract:{writer_id}:{field}")
    for writer_id in sorted(set(declared) - set(observed)):
        blockers.append(f"v144_wave0_package_writer_missing:{writer_id}")
    return sorted(set(blockers))


def unregistered_package_literal_blockers(
    trees: dict[str, ast.AST],
    registry: dict[str, object],
) -> list[str]:
    allowed = {
        str(value)
        for row in cast(list[dict[str, object]], registry.get("package_type_sets") or [])
        for value in cast(list[object], row.get("package_types") or [])
    }
    blockers: list[str] = []
    for module, tree in trees.items():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith("musicforge_")
                and node.value not in allowed
            ):
                blockers.append(
                    f"v144_wave0_package_literal_unregistered:{module}:{node.lineno}:{node.value}"
                )
    return sorted(set(blockers))


def named_assignment(node: ast.AST) -> tuple[str, ast.expr, int] | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        target, value = node.target, node.value
    else:
        return None
    if not isinstance(target, ast.Name):
        return None
    return target.id, value, int(getattr(node, "lineno", 0))


class _WriterContractCollector(ast.NodeVisitor):
    def __init__(
        self,
        module: str,
        source: str,
        source_text: str,
        constants: dict[str, object],
        guard_binding: _GuardBinding,
        module_source_hash: str,
    ) -> None:
        self.module = module
        self.source = source
        self.source_text = source_text
        self.constants = constants
        self.guard_binding = guard_binding
        self.module_source_hash = module_source_hash
        self._classes: list[str] = []
        self._functions: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda] = []
        self._effects: dict[str, list[_WriterEffect]] = {}
        self._parameters: dict[str, set[str]] = {}
        self._definition_lines: dict[str, int] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._classes.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self._classes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._functions.append(node)
        writer_id = self._writer_id(node)
        self._parameters[writer_id] = _argument_names(node.args)
        self._definition_lines[writer_id] = int(node.lineno)
        self.visit(node.body)
        self._functions.pop()

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if key is not None and resolve_string(key, self.constants) == PACKAGE_KEY:
                self._record(value, node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Subscript) and resolve_string(target.slice, self.constants) == PACKAGE_KEY:
                self._record(node.value, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            node.value is not None
            and isinstance(node.target, ast.Subscript)
            and resolve_string(node.target.slice, self.constants) == PACKAGE_KEY
        ):
            self._record(node.value, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Subscript) and resolve_string(node.target.slice, self.constants) == PACKAGE_KEY:
            self._record(node.value, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            for keyword in node.keywords:
                if keyword.arg == PACKAGE_KEY:
                    self._record(keyword.value, node)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in {"setdefault", "__setitem__"}:
            if len(node.args) >= 2 and resolve_string(node.args[0], self.constants) == PACKAGE_KEY:
                self._record(node.args[1], node)
        self.generic_visit(node)

    def rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for writer_id, effects in self._effects.items():
            parameters = self._parameters[writer_id]
            value_parameters = sorted(
                {
                    name
                    for effect in effects
                    for name in effect.value_parameters
                    if name in parameters
                }
            )
            rows.append(
                {
                    "writer_id": writer_id,
                    "source": self.source,
                    "line": self._definition_lines[writer_id],
                    "write_lines": sorted({effect.line for effect in effects}),
                    "value_parameters": value_parameters,
                    "expression_source_hash": source_fragments_hash(
                        self.source_text,
                        (effect.expression for effect in effects),
                    ),
                    "module_source_hash": self.module_source_hash,
                    "guard_symbol": WRITER_GUARD_SYMBOL,
                    "guard_alias": self.guard_binding.alias,
                    "guard_binding_hash": self.guard_binding.binding_hash,
                    "guarded": self.guard_binding.valid
                    and all(effect.guard_writer_id == writer_id for effect in effects),
                }
            )
        return rows

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._functions.append(node)
        writer_id = self._writer_id(node)
        self._parameters[writer_id] = _argument_names(node.args)
        self._definition_lines[writer_id] = int(node.lineno)
        for statement in node.body:
            self.visit(statement)
        self._functions.pop()

    def _record(self, expression: ast.expr, node: ast.AST) -> None:
        if not self._functions:
            return
        inner, guard_writer_id = _guarded_expression(expression, self.guard_binding)
        if resolve_string(inner, self.constants) is not None:
            return
        dependencies = _loaded_names(inner) & self._parameters[self._writer_id(self._functions[-1])]
        if not dependencies:
            return
        writer_id = self._writer_id(self._functions[-1])
        self._effects.setdefault(writer_id, []).append(
            _WriterEffect(inner, int(getattr(node, "lineno", 0)), guard_writer_id, frozenset(dependencies))
        )

    def _writer_id(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> str:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else f"<lambda@{node.lineno}>"
        return ".".join([self.module, *self._classes, name])


def _guarded_expression(
    expression: ast.expr,
    binding: _GuardBinding,
) -> tuple[ast.expr, str]:
    if (
        not binding.valid
        or not isinstance(expression, ast.Call)
        or not isinstance(expression.func, ast.Name)
        or expression.func.id != binding.alias
        or not expression.args
    ):
        return expression, ""
    writer_id = next(
        (
            str(keyword.value.value)
            for keyword in expression.keywords
            if keyword.arg == "writer_id"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ),
        "",
    )
    return expression.args[0], writer_id


def _canonical_guard_binding(tree: ast.AST) -> _GuardBinding:
    imports = [
        (node, alias)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == WRITER_GUARD_MODULE
        for alias in node.names
        if alias.name == WRITER_GUARD and alias.asname == WRITER_GUARD_ALIAS
    ]
    module_imports = [(node, alias) for node, alias in imports if node in getattr(tree, "body", [])]
    canonical_node, canonical_alias = imports[0] if len(imports) == 1 else (None, None)
    valid = (
        len(imports) == 1
        and len(module_imports) == 1
        and not _guard_alias_rebound(tree, canonical_node, canonical_alias)
    )
    return _GuardBinding(WRITER_GUARD_ALIAS, PACKAGE_WRITER_GUARD_BINDING_HASH, valid)


def _guard_alias_rebound(
    tree: ast.AST,
    canonical_import: ast.ImportFrom | None,
    canonical_alias: ast.alias | None,
) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and WRITER_GUARD_ALIAS in node.names:
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == WRITER_GUARD_ALIAS:
                return True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and WRITER_GUARD_ALIAS in _argument_names(node.args):
                return True
        if isinstance(node, ast.Lambda) and WRITER_GUARD_ALIAS in _argument_names(node.args):
            return True
        if isinstance(node, ast.ExceptHandler) and node.name == WRITER_GUARD_ALIAS:
            return True
        if isinstance(node, ast.MatchAs) and node.name == WRITER_GUARD_ALIAS:
            return True
        if isinstance(node, ast.MatchStar) and node.name == WRITER_GUARD_ALIAS:
            return True
        if isinstance(node, ast.MatchMapping) and node.rest == WRITER_GUARD_ALIAS:
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    return True
                if node is canonical_import and alias is canonical_alias:
                    continue
                bound = alias.asname or alias.name.split(".", 1)[0]
                if bound == WRITER_GUARD_ALIAS:
                    return True
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == WRITER_GUARD_ALIAS:
            return True
    return False


def _argument_names(arguments: ast.arguments) -> set[str]:
    names = {
        argument.arg
        for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _loaded_names(expression: ast.AST) -> set[str]:
    return {
        node.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
