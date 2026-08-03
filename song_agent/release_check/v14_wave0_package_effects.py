from __future__ import annotations

import ast
from dataclasses import dataclass

from song_agent.release_check.v14_wave0_catalog_model import (
    FunctionNode,
    mapping_pairs,
    resolve_string,
    safe_mapping_read,
    statically_safe_mapping,
    substitute_expression,
)
@dataclass(frozen=True)
class PackageWriteEffect:
    key: ast.expr
    value: ast.expr
    kind: str

EffectSummary = tuple[list[PackageWriteEffect], bool]
SummaryKey = tuple[int, tuple[tuple[str, object], ...], tuple[tuple[str, str], ...]]
CallableEnvironment = tuple[dict[str, object], dict[str, FunctionNode], dict[str, str]]
def bind_call_arguments(arguments: ast.arguments, call: ast.Call, constants: dict[str, object]) -> dict[str, ast.expr] | None:
    positional: list[ast.expr] = []
    for value in call.args:
        if isinstance(value, ast.Starred):
            expanded = _sequence_items(value.value)
            if expanded is None:
                return None
            positional.extend(expanded)
        else:
            positional.append(value)
    keywords: dict[str, ast.expr] = {}
    for keyword in call.keywords:
        if keyword.arg is not None:
            if keyword.arg in keywords:
                return None
            keywords[keyword.arg] = keyword.value
            continue
        expanded_keywords = _keyword_items(keyword.value, constants)
        if expanded_keywords is None or set(expanded_keywords) & set(keywords):
            return None
        keywords.update(expanded_keywords)
    positional_parameters = [*arguments.posonlyargs, *arguments.args]
    positional_only = {parameter.arg for parameter in arguments.posonlyargs}
    if len(positional) > len(positional_parameters) and arguments.vararg is None:
        return None
    bound: dict[str, ast.expr] = {
        parameter.arg: value for parameter, value in zip(positional_parameters, positional)
    }
    if arguments.vararg is not None:
        bound[arguments.vararg.arg] = ast.Tuple(
            elts=positional[len(positional_parameters) :],
            ctx=ast.Load(),
        )
    extra_keywords: dict[str, ast.expr] = {}
    parameter_names = {parameter.arg for parameter in [*positional_parameters, *arguments.kwonlyargs]}
    for name, value in keywords.items():
        if name in positional_only or name in bound:
            return None
        if name in parameter_names:
            bound[name] = value
        elif arguments.kwarg is not None:
            extra_keywords[name] = value
        else:
            return None
    default_offset = len(positional_parameters) - len(arguments.defaults)
    for index, parameter in enumerate(positional_parameters):
        if parameter.arg in bound:
            continue
        if index < default_offset:
            return None
        bound[parameter.arg] = arguments.defaults[index - default_offset]
    for parameter, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if parameter.arg in bound:
            continue
        if default is None:
            return None
        bound[parameter.arg] = default
    if arguments.kwarg is not None:
        bound[arguments.kwarg.arg] = ast.Dict(
            keys=[ast.Constant(value=name) for name in extra_keywords],
            values=list(extra_keywords.values()),
        )
    return bound
def call_values(call: ast.Call, constants: dict[str, object]) -> list[ast.expr]:
    values: list[ast.expr] = []
    for value in call.args:
        if isinstance(value, ast.Starred):
            values.extend(_sequence_items(value.value) or [value.value])
        else:
            values.append(value)
    for keyword in call.keywords:
        if keyword.arg is None:
            expanded = _keyword_items(keyword.value, constants)
            values.extend(expanded.values() if expanded is not None else [keyword.value])
        else:
            values.append(keyword.value)
    return values

def resolve_package_mapping_effect(
    expression: ast.expr,
    constants: dict[str, object],
) -> tuple[ast.expr | None, bool]:
    pairs = mapping_pairs(expression, constants)
    if "package_type" in pairs:
        return pairs["package_type"], False
    if statically_safe_mapping(expression, constants):
        return None, False
    dynamic = (ast.Name, ast.Call, ast.Attribute, ast.Subscript, ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)
    return None, any(isinstance(node, dynamic) for node in ast.walk(expression))

def helper_effect_summary(
    function: FunctionNode,
    constants: dict[str, object],
    helpers: dict[str, FunctionNode],
    helper_aliases: dict[str, str],
    *,
    cache: dict[SummaryKey, EffectSummary] | None = None,
    active: set[int] | None = None,
    environments: dict[int, CallableEnvironment] | None = None,
) -> tuple[list[PackageWriteEffect], bool]:
    summaries = cache if cache is not None else {}
    identity = id(function)
    summary_key = identity, tuple(sorted(constants.items())), tuple(sorted(helper_aliases.items()))
    if summary_key in summaries:
        return summaries[summary_key]
    ancestry = set(active or ())
    if identity in ancestry:
        return [], False
    parameters = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    if function.args.vararg is not None:
        parameters.append(function.args.vararg)
    if function.args.kwarg is not None:
        parameters.append(function.args.kwarg)
    bindings: dict[str, ast.expr] = {
        parameter.arg: ast.Name(id=parameter.arg, ctx=ast.Load()) for parameter in parameters
    }
    collector = _HelperEffectCollector(
        bindings,
        constants,
        helpers,
        helper_aliases,
        summaries=summaries,
        active={*ancestry, identity},
        environments=environments or {},
    )
    if isinstance(function, ast.Lambda):
        collector.visit(function.body)
    else:
        for statement in function.body:
            collector.visit(statement)
    result = collector.effects, collector.unresolved
    summaries[summary_key] = result
    return result

def instantiate_helper_effects(
    summary: EffectSummary,
    arguments: ast.arguments,
    call: ast.Call,
    constants: dict[str, object],
) -> tuple[list[PackageWriteEffect], bool]:
    bindings = bind_call_arguments(arguments, call, constants)
    if bindings is None:
        return [], True
    effects, unresolved = summary
    return [
        PackageWriteEffect(
            substitute_expression(effect.key, bindings),
            substitute_expression(effect.value, bindings),
            effect.kind,
        )
        for effect in effects
    ], unresolved
class _HelperEffectCollector(ast.NodeVisitor):
    def __init__(
        self,
        bindings: dict[str, ast.expr],
        constants: dict[str, object],
        helpers: dict[str, FunctionNode],
        helper_aliases: dict[str, str],
        *,
        summaries: dict[SummaryKey, EffectSummary],
        active: set[int],
        environments: dict[int, CallableEnvironment],
    ) -> None:
        self.bindings = dict(bindings)
        self.constants = constants
        self.helpers = helpers
        self.helper_aliases = dict(helper_aliases)
        self.summaries = summaries
        self.active = active
        self.environments = environments
        self.dependent_names = {
            item.id
            for value in bindings.values()
            for item in ast.walk(value)
            if isinstance(item, ast.Name)
        }
        self.effects: list[PackageWriteEffect] = []
        self.unresolved = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        value = substitute_expression(node.value, self.bindings)
        for target in node.targets:
            self._record_target(target, value, "helper_assignment")
            if isinstance(target, ast.Name):
                self._bind_name(target.id, value)
                helper = self._helper_name(node.value)
                if helper is None:
                    self.helper_aliases.pop(target.id, None)
                else:
                    self.helper_aliases[target.id] = helper

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            return
        self.visit(node.value)
        value = substitute_expression(node.value, self.bindings)
        self._record_target(node.target, value, "helper_annotated_assignment")
        if isinstance(node.target, ast.Name):
            self._bind_name(node.target.id, value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        value = substitute_expression(node.value, self.bindings)
        self._record_target(node.target, value, "helper_augmented_assignment")

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if key is None:
                self._record_dynamic_mapping(value, "helper_mapping_unpack_dynamic_mapping")
            else:
                self._record_key(key, value, "helper_mapping_literal")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        resolved = substitute_expression(node, self.bindings)
        assert isinstance(resolved, ast.Call)
        if self._record_package_call(resolved):
            self.generic_visit(node)
            return
        helper_name = self._helper_name(node.func)
        helper = self.helpers.get(helper_name or "")
        if helper is not None:
            constants, helpers, aliases = self.environments.get(
                id(helper), (self.constants, self.helpers, self.helper_aliases)
            )
            summary = helper_effect_summary(
                helper,
                constants,
                helpers,
                aliases,
                cache=self.summaries,
                active=self.active,
                environments=self.environments,
            )
            effects, unresolved = instantiate_helper_effects(
                summary,
                helper.args,
                resolved,
                self.constants,
            )
            self.effects.extend(effects)
            self.unresolved = self.unresolved or (unresolved and bool(summary[0] or summary[1]))
            return
        values = call_values(resolved, self.constants)
        if safe_mapping_read(resolved, values, self.constants):
            return
        for index, key in enumerate(values):
            if resolve_string(key, self.constants) == "package_type":
                value = values[index + 1] if index + 1 < len(values) else resolved
                self.effects.append(PackageWriteEffect(key, value, "helper_unknown_call"))
                return
        self.generic_visit(node)

    def _record_target(self, target: ast.expr, value: ast.expr, kind: str) -> None:
        if isinstance(target, ast.Subscript):
            key = substitute_expression(target.slice, self.bindings)
            self._record_key(key, value, kind)

    def _record_key(self, key: ast.expr, value: ast.expr, kind: str) -> None:
        resolved_key = substitute_expression(key, self.bindings)
        resolved_value = substitute_expression(value, self.bindings)
        package_key = resolve_string(resolved_key, self.constants)
        if (package_key == "package_type" and self._depends_on_call(resolved_value)) or (
            package_key is None
            and (self._depends_on_call(resolved_key) or self._depends_on_call(resolved_value))
        ):
            self.effects.append(
                PackageWriteEffect(
                    resolved_key,
                    resolved_value,
                    kind,
                )
            )

    def _record_package_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Name) and node.func.id == "dict":
            for keyword in node.keywords:
                if keyword.arg == "package_type":
                    self._record_key(ast.Constant("package_type"), keyword.value, "helper_dict_keyword")
                elif keyword.arg is None:
                    self._record_dynamic_mapping(keyword.value, "helper_dict_keywords_dynamic_mapping")
            self._record_mapping_argument(node, "helper_dict_mapping")
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            for keyword in node.keywords:
                if keyword.arg == "package_type":
                    self._record_key(ast.Constant("package_type"), keyword.value, "helper_update_keyword")
                elif keyword.arg is None:
                    self._record_dynamic_mapping(keyword.value, "helper_update_keywords_dynamic_mapping")
            self._record_mapping_argument(node, "helper_update_mapping")
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"setdefault", "__setitem__"}:
            offset = 1 if isinstance(node.func.value, ast.Name) and node.func.value.id == "dict" else 0
            if len(node.args) >= offset + 2:
                self._record_key(node.args[offset], node.args[offset + 1], f"helper_{node.func.attr}")
            else:
                self.unresolved = True
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "setitem":
            if len(node.args) >= 3:
                self._record_key(node.args[1], node.args[2], "helper_operator_setitem")
            else:
                self.unresolved = True
            return True
        return False

    def _record_mapping_argument(self, node: ast.Call, kind: str) -> None:
        if not node.args:
            return
        pairs = mapping_pairs(node.args[0], self.constants)
        for key, value in pairs.items():
            self._record_key(ast.Constant(key), value, kind)
        if (
            not pairs
            and not statically_safe_mapping(node.args[0], self.constants)
            and self._depends_on_call(node.args[0])
        ):
            self._record_dynamic_mapping(node.args[0], f"{kind}_dynamic_mapping")

    def _record_dynamic_mapping(self, value: ast.expr, kind: str) -> None:
        resolved = substitute_expression(value, self.bindings)
        if self._depends_on_call(resolved):
            self.effects.append(PackageWriteEffect(ast.Constant(""), resolved, kind))

    def _depends_on_call(self, expression: ast.expr) -> bool:
        return any(isinstance(node, ast.Name) and node.id in self.dependent_names for node in ast.walk(expression))

    def _bind_name(self, name: str, value: ast.expr) -> None:
        dependent = self._depends_on_call(value)
        if dependent:
            self.dependent_names.add(name)
        else:
            self.dependent_names.discard(name)
        if sum(1 for _ in ast.walk(value)) <= 64:
            self.bindings[name] = value
        else:
            self.bindings.pop(name, None)

    def _helper_name(self, expression: ast.expr) -> str | None:
        rendered = _qualified_name(expression)
        if rendered is None:
            return None
        return self.helper_aliases.get(rendered, rendered)
def _qualified_name(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        owner = _qualified_name(expression.value)
        return f"{owner}.{expression.attr}" if owner else None
    return None
def _sequence_items(expression: ast.expr) -> list[ast.expr] | None:
    return list(expression.elts) if isinstance(expression, (ast.List, ast.Tuple)) else None
def _keyword_items(expression: ast.expr, constants: dict[str, object]) -> dict[str, ast.expr] | None:
    if not isinstance(expression, ast.Dict):
        return None
    result: dict[str, ast.expr] = {}
    for key, value in zip(expression.keys, expression.values):
        if key is None:
            return None
        name = resolve_string(key, constants)
        if name is None or name in result:
            return None
        result[name] = value
    return result
