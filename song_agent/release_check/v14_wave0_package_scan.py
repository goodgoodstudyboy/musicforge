from __future__ import annotations

import ast
from collections.abc import Iterable

from song_agent.release_check.v14_wave0_catalog_model import (
    FunctionNode as _FunctionNode,
    argument_names as _argument_names,
    bind_constant as _bind_constant,
    bind_helper_alias as _bind_helper_alias,
    bind_mutation_alias as _bind_mutation_alias,
    direct_helpers as _direct_helpers,
    helper_name as _helper_name,
    is_getattr_setitem as _is_getattr_setitem,
    is_operator_setitem as _is_operator_setitem,
    lookup_helper as _lookup_helper,
    mapping_pairs as _mapping_pairs,
    merge_aliases as _merge_aliases,
    merge_constants as _merge_constants,
    observation_row as _observation_row,
    resolve_scalar as _resolve_scalar,
    resolve_string as _resolve_string,
    safe_mapping_read as _safe_mapping_read,
    statically_safe_mapping as _statically_safe_mapping,
    same_string_bindings as _same_bindings,
    visible_helpers as _visible_helpers,
)
from song_agent.release_check.v14_wave0_package_effects import (
    EffectSummary as _EffectSummary,
    SummaryKey as _SummaryKey,
    call_values as _call_values,
    helper_effect_summary as _helper_effect_summary,
    instantiate_helper_effects as _instantiate_helper_effects,
    resolve_package_mapping_effect as _resolve_package_mapping_effect,
)
PACKAGE_KEY = "package_type"
def package_observations(tree: ast.AST, source: str, source_text: str) -> list[dict[str, object]]:
    collector = _PackageObservationCollector(source, source_text)
    collector.visit(tree)
    return collector.rows
class _PackageObservationCollector(ast.NodeVisitor):
    def __init__(self, source: str, source_text: str) -> None:
        self.source = source
        self.source_text = source_text
        self.rows: list[dict[str, object]] = []
        self._constants: list[dict[str, object]] = [{}]
        self._mutation_aliases: list[dict[str, tuple[int, int, str]]] = [{}]
        self._helper_aliases: list[dict[str, str]] = [{}]
        self._helper_scopes: list[dict[str, _FunctionNode]] = []
        self._helper_effect_cache: dict[_SummaryKey, _EffectSummary] = {}
        self._scopes: list[ast.AST] = []
        self._operator_modules: set[str] = {"operator"}
        self._operator_setitems: set[str] = set()

    @property
    def constants(self) -> dict[str, object]:
        return self._constants[-1]

    @property
    def mutation_aliases(self) -> dict[str, tuple[int, int, str]]:
        return self._mutation_aliases[-1]

    @property
    def helper_aliases(self) -> dict[str, str]:
        return self._helper_aliases[-1]
    def visit_Module(self, node: ast.Module) -> None:
        self._helper_scopes.append(_direct_helpers(node.body))
        self._scopes.append(node)
        self._visit_statements(node.body)
        self._scopes.pop()
        self._helper_scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition_expressions(node.decorator_list, node.args.defaults, node.args.kw_defaults)
        self._visit_nested_scope(node, node.body, _argument_names(node.args))
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition_expressions(node.decorator_list, node.args.defaults, node.args.kw_defaults)
        self._visit_nested_scope(node, node.body, _argument_names(node.args))
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition_expressions(node.decorator_list, node.bases, (keyword.value for keyword in node.keywords))
        self._visit_nested_scope(node, node.body, set())
    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_definition_expressions((), node.args.defaults, node.args.kw_defaults)
        inherited = dict(self.constants)
        inherited_aliases = dict(self.mutation_aliases)
        inherited_helpers = dict(self.helper_aliases)
        for name in _argument_names(node.args):
            inherited.pop(name, None)
            inherited_aliases.pop(name, None)
            inherited_helpers.pop(name, None)
        self._constants.append(inherited)
        self._mutation_aliases.append(inherited_aliases)
        self._helper_aliases.append(inherited_helpers)
        self._helper_scopes.append({})
        self._scopes.append(node)
        self.visit(node.body)
        self._scopes.pop()
        self._helper_scopes.pop()
        self._helper_aliases.pop()
        self._mutation_aliases.pop()
        self._constants.pop()
    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        before = dict(self.constants)
        aliases = dict(self.mutation_aliases)
        helpers = dict(self.helper_aliases)
        body, body_aliases, body_helpers = self._branch(node.body, before, aliases, helpers)
        otherwise, other_aliases, other_helpers = self._branch(node.orelse, before, aliases, helpers)
        self.constants.clear()
        self.constants.update(_merge_constants(body, otherwise))
        self.mutation_aliases.clear()
        self.mutation_aliases.update(_merge_aliases(body_aliases, other_aliases))
        self.helper_aliases.clear()
        self.helper_aliases.update(_same_bindings(body_helpers, other_helpers))
    def visit_Try(self, node: ast.Try) -> None:
        before = dict(self.constants)
        aliases = dict(self.mutation_aliases)
        helpers = dict(self.helper_aliases)
        branches = [self._branch(node.body, before, aliases, helpers)]
        branches.extend(self._branch(handler.body, before, aliases, helpers) for handler in node.handlers)
        merged, merged_aliases, merged_helpers = branches[0]
        for branch, branch_aliases, branch_helpers in branches[1:]:
            merged = _merge_constants(merged, branch)
            merged_aliases = _merge_aliases(merged_aliases, branch_aliases)
            merged_helpers = _same_bindings(merged_helpers, branch_helpers)
        self.constants.clear()
        self.constants.update(merged)
        self.mutation_aliases.clear()
        self.mutation_aliases.update(merged_aliases)
        self.helper_aliases.clear()
        self.helper_aliases.update(merged_helpers)
        self._visit_statements(node.orelse)
        self._visit_statements(node.finalbody)
    def visit_Assign(self, node: ast.Assign) -> None:
        self._observe_assignment(node.targets, node.value, node)
        for target in node.targets:
            if isinstance(target, ast.Name) and "PACKAGE_TYPE" in target.id:
                self._append(node.value, None, node, "package_constant")
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)
        for target in node.targets:
            _bind_constant(target, node.value, self.constants)
            _bind_mutation_alias(
                target,
                node.value,
                self.constants,
                self.mutation_aliases,
                self._operator_modules,
                self._operator_setitems,
            )
            _bind_helper_alias(target, node.value, self.helper_aliases, self._helper_scopes)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._observe_assignment([node.target], node.value, node)
            if isinstance(node.target, ast.Name) and "PACKAGE_TYPE" in node.target.id:
                self._append(node.value, None, node, "package_constant")
            self.visit(node.value)
            _bind_constant(node.target, node.value, self.constants)
            _bind_mutation_alias(
                node.target,
                node.value,
                self.constants,
                self.mutation_aliases,
                self._operator_modules,
                self._operator_setitems,
            )
            _bind_helper_alias(node.target, node.value, self.helper_aliases, self._helper_scopes)
        self.visit(node.annotation)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._observe_assignment([node.target], node.value, node, kind="augmented_assignment")
        self.visit(node.target)
        self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        _bind_constant(node.target, node.value, self.constants)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "operator":
                self._operator_modules.add(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "operator":
            for alias in node.names:
                if alias.name == "setitem":
                    self._operator_setitems.add(alias.asname or alias.name)

    def visit_Dict(self, node: ast.Dict) -> None:
        schema = next(
            (
                value
                for key, value in zip(node.keys, node.values)
                if key is not None and _resolve_string(key, self.constants) == "schema_version"
            ),
            None,
        )
        for key, value in zip(node.keys, node.values):
            if key is not None and _resolve_string(key, self.constants) == PACKAGE_KEY:
                self._append(value, _resolve_scalar(schema, self.constants), node, "mapping_literal")
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        key = _resolve_string(node.key, self.constants)
        if key == PACKAGE_KEY:
            self._append(node.value, None, node, "mapping_comprehension")
        elif key is None:
            self._append(node.value, None, node, "dynamic_key_mapping_comprehension", force_dynamic=True)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._observe_call(node)
        self.generic_visit(node)

    def _visit_statements(self, statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            self.visit(statement)

    def _visit_definition_expressions(self, *groups: Iterable[ast.expr | None]) -> None:
        for group in groups:
            for expression in group:
                if expression is not None:
                    self.visit(expression)

    def _visit_nested_scope(self, scope: ast.AST, body: list[ast.stmt], shadowed: set[str]) -> None:
        inherited = dict(self.constants)
        inherited_aliases = dict(self.mutation_aliases)
        inherited_helpers = dict(self.helper_aliases)
        for name in shadowed:
            inherited.pop(name, None)
            inherited_aliases.pop(name, None)
            inherited_helpers.pop(name, None)
        self._constants.append(inherited)
        self._mutation_aliases.append(inherited_aliases)
        self._helper_aliases.append(inherited_helpers)
        self._helper_scopes.append(_direct_helpers(body))
        self._scopes.append(scope)
        self._visit_statements(body)
        self._scopes.pop()
        self._helper_scopes.pop()
        self._helper_aliases.pop()
        self._mutation_aliases.pop()
        self._constants.pop()

    def _branch(
        self,
        statements: list[ast.stmt],
        inherited: dict[str, object],
        inherited_aliases: dict[str, tuple[int, int, str]],
        inherited_helpers: dict[str, str] | None = None,
    ) -> tuple[dict[str, object], dict[str, tuple[int, int, str]], dict[str, str]]:
        self._constants.append(dict(inherited))
        self._mutation_aliases.append(dict(inherited_aliases))
        self._helper_aliases.append(dict(inherited_helpers or self.helper_aliases))
        self._visit_statements(statements)
        result = dict(self.constants)
        aliases = dict(self.mutation_aliases)
        helpers = dict(self.helper_aliases)
        self._helper_aliases.pop()
        self._mutation_aliases.pop()
        self._constants.pop()
        return result, aliases, helpers

    def _observe_assignment(
        self,
        targets: list[ast.expr],
        value: ast.expr,
        node: ast.AST,
        *,
        kind: str = "assignment",
    ) -> None:
        for target in targets:
            if not isinstance(target, ast.Subscript):
                continue
            key = _resolve_string(target.slice, self.constants)
            if key == PACKAGE_KEY:
                self._append(value, None, node, f"subscript_{kind}")
            elif key is None:
                self._append(value, None, node, f"dynamic_key_{kind}", force_dynamic=True)

    def _observe_call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "dict":
            schema = next((keyword.value for keyword in node.keywords if keyword.arg == "schema_version"), None)
            for keyword in node.keywords:
                if keyword.arg == PACKAGE_KEY:
                    self._append(keyword.value, _resolve_scalar(schema, self.constants), node, "dict_keyword")
            pairs = _mapping_pairs(node.args[0], self.constants) if node.args else {}
            if PACKAGE_KEY in pairs:
                self._append(pairs[PACKAGE_KEY], _resolve_scalar(pairs.get("schema_version"), self.constants), node, "dict_pairs")
            return
        if isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            for keyword in node.keywords:
                if keyword.arg == PACKAGE_KEY:
                    self._append(keyword.value, None, node, "update_keyword")
            pairs = _mapping_pairs(node.args[0], self.constants) if node.args else {}
            if PACKAGE_KEY in pairs:
                self._append(pairs[PACKAGE_KEY], None, node, "update_mapping")
            elif node.args and not _statically_safe_mapping(node.args[0], self.constants):
                self._append(node.args[0], None, node, "dynamic_update_mapping", force_dynamic=True)
            for keyword in node.keywords:
                if keyword.arg is None:
                    self._append(keyword.value, None, node, "dynamic_update_keywords", force_dynamic=True)
            return
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"setdefault", "__setitem__"} and len(node.args) >= 2:
            offset = 1 if isinstance(node.func.value, ast.Name) and node.func.value.id == "dict" else 0
            if len(node.args) >= offset + 2:
                self._observe_keyed_mutation(node.args[offset], node.args[offset + 1], node, node.func.attr)
            return
        if _is_operator_setitem(node.func, self._operator_modules, self._operator_setitems) and len(node.args) >= 3:
            self._observe_keyed_mutation(node.args[1], node.args[2], node, "operator.setitem")
            return
        if _is_getattr_setitem(node.func, self.constants) and len(node.args) >= 2:
            self._observe_keyed_mutation(node.args[0], node.args[1], node, "getattr.__setitem__")
            return
        alias = self.mutation_aliases.get(node.func.id) if isinstance(node.func, ast.Name) else None
        if alias is not None and len(node.args) > max(alias[0], alias[1]):
            self._observe_keyed_mutation(node.args[alias[0]], node.args[alias[1]], node, alias[2])
            return
        helper_name = _helper_name(node.func, self.helper_aliases)
        helper = _lookup_helper(self._helper_scopes, helper_name)
        if helper is not None:
            summary = _helper_effect_summary(
                helper,
                self.constants,
                _visible_helpers(self._helper_scopes),
                self.helper_aliases,
                cache=self._helper_effect_cache,
            )
            effects, unresolved = _instantiate_helper_effects(
                summary,
                helper.args,
                node,
                self.constants,
            )
            for effect in effects:
                if effect.kind.endswith("_dynamic_mapping"):
                    package_value, mapping_unresolved = _resolve_package_mapping_effect(effect.value, self.constants)
                    if package_value is not None:
                        self._observe_keyed_mutation(
                            ast.Constant(PACKAGE_KEY),
                            package_value,
                            node,
                            f"helper_call.{helper_name}.{effect.kind}",
                        )
                    unresolved = unresolved or mapping_unresolved
                    continue
                resolved_key = _resolve_string(effect.key, self.constants)
                if resolved_key == PACKAGE_KEY:
                    self._observe_keyed_mutation(
                        effect.key,
                        effect.value,
                        node,
                        f"helper_call.{helper_name}.{effect.kind}",
                    )
                elif resolved_key is None:
                    unresolved = True
            if unresolved and (summary[0] or summary[1]):
                self._append(node, None, node, f"unresolved_helper_call.{helper_name}", force_dynamic=True)
            return
        values = _call_values(node, self.constants)
        if _safe_mapping_read(node, values, self.constants):
            return
        if any(_resolve_string(value, self.constants) == PACKAGE_KEY for value in values):
            self._append(node, None, node, "unknown_helper_package_key", force_dynamic=True)

    def _observe_keyed_mutation(self, key: ast.expr, value: ast.expr, node: ast.AST, kind: str) -> None:
        resolved = _resolve_string(key, self.constants)
        if resolved == PACKAGE_KEY:
            self._append(value, None, node, kind)
        elif resolved is None:
            self._append(value, None, node, f"dynamic_key_{kind}", force_dynamic=True)

    def _append(
        self,
        expression: ast.expr,
        schema_version: object,
        node: ast.AST,
        candidate_kind: str,
        *,
        force_dynamic: bool = False,
    ) -> None:
        scope = self._scopes[-1] if self._scopes else node
        self.rows.append(
            _observation_row(
                self.source,
                self.source_text,
                expression,
                node,
                schema_version,
                scope,
                candidate_kind,
                self.constants,
                force_dynamic=force_dynamic,
            )
        )
