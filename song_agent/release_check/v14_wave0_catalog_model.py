from __future__ import annotations

import ast
import copy
import hashlib
import json
from typing import cast

from song_agent.release_check.v14_wave0_source import (
    source_fragment,
    source_fragment_hash,
    source_site_id,
    source_span,
    source_text_hash,
)


BOUNDED_CONTEXTS = ("creation", "studio", "quality", "delivery", "trust", "program")
INVENTORY_IDENTITIES = {
    "stores": "store_id",
    "cli_commands": "command_id",
    "cli_registration_points": "registration_id",
    "api_routes": "route_id",
    "packages": "package_id",
    "package_types": "package_type",
    "package_sites": "site_id",
    "verifiers": "verifier_id",
    "schemas": "schema_id",
    "studio_panels": "panel_id",
    "release_checks": "release_check_id",
}
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
def attach_capability(
    rows: list[dict[str, object]],
    *,
    inventory_name: str,
    owner: dict[str, str],
    capability_context: dict[str, str],
) -> list[dict[str, object]]:
    identity_key = INVENTORY_IDENTITIES[inventory_name]
    result: list[dict[str, object]] = []
    for row in rows:
        identity = str(row.get(identity_key) or "")
        capability_id = owner.get(identity, "")
        result.append(
            {
                **row,
                "capability_id": capability_id,
                "bounded_context": capability_context.get(capability_id, ""),
            }
        )
    return sorted(result, key=lambda row: str(row[identity_key]))
def inventory_identity_sets(inventory: dict[str, object]) -> dict[str, list[str]]:
    return {
        key: sorted(str(row[INVENTORY_IDENTITIES[key]]) for row in cast(list[dict[str, object]], inventory.get(key) or []))
        for key in INVENTORY_IDENTITIES
    }
def hash_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
def argument_names(arguments: ast.arguments) -> set[str]:
    values = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    if arguments.vararg is not None:
        values.append(arguments.vararg)
    if arguments.kwarg is not None:
        values.append(arguments.kwarg)
    return {value.arg for value in values}
def merge_constants(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in left.items() if right.get(key) == value}
def merge_aliases(
    left: dict[str, tuple[int, int, str]], right: dict[str, tuple[int, int, str]]
) -> dict[str, tuple[int, int, str]]:
    return {key: value for key, value in left.items() if right.get(key) == value}
def mapping_pairs(expression: ast.expr, constants: dict[str, object]) -> dict[str, ast.expr]:
    if not isinstance(expression, (ast.List, ast.Tuple)):
        return {}
    result: dict[str, ast.expr] = {}
    for item in expression.elts:
        if isinstance(item, (ast.List, ast.Tuple)) and len(item.elts) == 2:
            key, value = item.elts
            resolved = resolve_string(key, constants)
            if resolved is not None:
                result[resolved] = value
    return result
def statically_safe_mapping(expression: ast.expr, constants: dict[str, object]) -> bool:
    if isinstance(expression, ast.Dict):
        return all(key is not None and resolve_string(key, constants) not in {None, "package_type"} for key in expression.keys)
    if isinstance(expression, (ast.List, ast.Tuple)):
        return all(
            isinstance(item, (ast.List, ast.Tuple))
            and len(item.elts) == 2
            and resolve_string(item.elts[0], constants) not in {None, "package_type"}
            for item in expression.elts
        )
    return False
def module_constants(tree: ast.AST) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in ast.iter_child_nodes(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        resolved = resolve_scalar(value, values)
        if isinstance(resolved, (str, int)):
            values[target.id] = resolved
        else:
            values.pop(target.id, None)
    return values
def resolve_string(expression: ast.expr, constants: dict[str, object]) -> str | None:
    value = resolve_scalar(expression, constants)
    return value if isinstance(value, str) else None
def resolve_scalar(expression: ast.expr | None, constants: dict[str, object]) -> object:
    unwrapped = unwrap_registered_package_type_guard(expression)
    if unwrapped is not expression:
        return resolve_scalar(unwrapped, constants)
    if isinstance(expression, ast.Constant) and isinstance(expression.value, (str, int)):
        return expression.value
    if isinstance(expression, ast.Name) and isinstance(constants.get(expression.id), (str, int)):
        return constants[expression.id]
    return None
def unwrap_registered_package_type_guard(expression: ast.expr | None) -> ast.expr | None:
    if not isinstance(expression, ast.Call) or not expression.args:
        return expression
    function = expression.func
    if isinstance(function, ast.Name):
        guarded = function.id in {"require_registered_package_type", "_require_registered_package_type"}
    else:
        guarded = isinstance(function, ast.Attribute) and function.attr == "require_registered_package_type"
    return expression.args[0] if guarded else expression
def substitute_expression(expression: ast.expr, bindings: dict[str, ast.expr]) -> ast.expr:
    value = _BindingSubstituter(bindings).visit(copy.deepcopy(expression))
    assert isinstance(value, ast.expr)
    return value
class _BindingSubstituter(ast.NodeTransformer):
    def __init__(self, bindings: dict[str, ast.expr]) -> None:
        self.bindings = bindings

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if isinstance(node.ctx, ast.Load) and node.id in self.bindings:
            return copy.deepcopy(self.bindings[node.id])
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        value = self.visit(node.value)
        key = self.visit(node.slice)
        if isinstance(value, (ast.List, ast.Tuple)) and isinstance(key, ast.Constant) and isinstance(key.value, int):
            index = key.value
            if -len(value.elts) <= index < len(value.elts):
                return copy.deepcopy(value.elts[index])
        if isinstance(value, ast.Dict):
            for item_key, item_value in zip(value.keys, value.values):
                if isinstance(item_key, ast.Constant) and isinstance(key, ast.Constant) and item_key.value == key.value:
                    return copy.deepcopy(item_value)
        node.value, node.slice = value, key
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
        values = [self.visit(value) for value in node.values]
        if isinstance(node.op, ast.Or):
            while len(values) > 1 and _literal_truth(values[0]) is False:
                values.pop(0)
        elif isinstance(node.op, ast.And):
            while len(values) > 1 and _literal_truth(values[0]) is True:
                values.pop(0)
        return values[0] if len(values) == 1 else ast.BoolOp(op=node.op, values=values)
def _literal_truth(expression: ast.expr) -> bool | None:
    if isinstance(expression, ast.Constant):
        return bool(expression.value)
    if isinstance(expression, (ast.List, ast.Tuple, ast.Set)):
        return bool(expression.elts)
    if isinstance(expression, ast.Dict):
        return bool(expression.keys)
    return None
def is_operator_setitem(function: ast.expr, module_aliases: set[str], function_aliases: set[str]) -> bool:
    return (isinstance(function, ast.Name) and function.id in function_aliases) or (
        isinstance(function, ast.Attribute)
        and function.attr == "setitem"
        and isinstance(function.value, ast.Name)
        and function.value.id in module_aliases
    )
def is_getattr_setitem(function: ast.expr, constants: dict[str, object]) -> bool:
    return (
        isinstance(function, ast.Call)
        and isinstance(function.func, ast.Name)
        and function.func.id == "getattr"
        and len(function.args) >= 2
        and resolve_string(function.args[1], constants) == "__setitem__"
    )
def safe_mapping_read(call: ast.Call, values: list[ast.expr], constants: dict[str, object]) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "get"
        and len(values) in {1, 2}
        and resolve_string(values[0], constants) == "package_type"
    )
def mutation_alias(
    expression: ast.expr,
    constants: dict[str, object],
    aliases: dict[str, tuple[int, int, str]],
    operator_modules: set[str],
    operator_setitems: set[str],
) -> tuple[int, int, str] | None:
    if isinstance(expression, ast.Name):
        return (1, 2, "operator.setitem_alias") if expression.id in operator_setitems else aliases.get(expression.id)
    if is_operator_setitem(expression, operator_modules, operator_setitems):
        return 1, 2, "operator.setitem_alias"
    if isinstance(expression, ast.Attribute) and expression.attr in {"__setitem__", "setdefault"}:
        if isinstance(expression.value, ast.Name) and expression.value.id == "dict":
            return 1, 2, f"dict.{expression.attr}_alias"
        return 0, 1, f"bound.{expression.attr}_alias"
    if is_getattr_setitem(expression, constants):
        return 0, 1, "getattr.__setitem___alias"
    return None
def direct_helpers(statements: list[ast.stmt]) -> dict[str, FunctionNode]:
    return {
        statement.name: statement
        for statement in statements
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
def same_string_bindings(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in left.items() if right.get(key) == value}
def expression_contains_string(expression: ast.expr, constants: dict[str, object], expected: str) -> bool:
    return any(
        isinstance(node, ast.expr) and resolve_string(node, constants) == expected
        for node in ast.walk(expression)
    )
def observation_row(
    source: str,
    source_text: str,
    expression: ast.expr,
    site: ast.AST,
    schema_version: object,
    scope: ast.AST,
    candidate_kind: str,
    constants: dict[str, object],
    *,
    force_dynamic: bool,
) -> dict[str, object]:
    unwrapped = unwrap_registered_package_type_guard(expression)
    assert isinstance(unwrapped, ast.expr)
    expression = unwrapped
    try:
        source_span(expression)
        evidence_node: ast.AST = expression
    except ValueError:
        evidence_node = site
    rendered = source_fragment(source_text, evidence_node).strip()
    span = source_span(site)
    evidence_span = source_span(evidence_node)
    source_id = source_site_id(source, site)
    if evidence_span != span:
        source_id += (
            f"@{evidence_span.line}:{evidence_span.column}:"
            f"{evidence_span.end_line}:{evidence_span.end_column}"
        )
    scope_source_hash = (
        source_text_hash(source_text)
        if isinstance(scope, ast.Module)
        else source_fragment_hash(source_text, scope)
    )
    return {
        "source_id": source_id,
        "package_type": "" if force_dynamic else (resolve_string(expression, constants) or ""),
        "expression": rendered,
        "expression_source_hash": source_fragment_hash(source_text, evidence_node),
        "schema_version": schema_version,
        "scope_source_hash": scope_source_hash,
        **span.document(),
        "candidate_kind": candidate_kind,
    }
def bind_constant(target: ast.expr, value: ast.expr, constants: dict[str, object]) -> None:
    if not isinstance(target, ast.Name):
        return
    resolved = resolve_scalar(value, constants)
    if isinstance(resolved, (str, int)):
        constants[target.id] = resolved
    else:
        constants.pop(target.id, None)
def bind_mutation_alias(
    target: ast.expr,
    value: ast.expr,
    constants: dict[str, object],
    aliases: dict[str, tuple[int, int, str]],
    operator_modules: set[str],
    operator_setitems: set[str],
) -> None:
    if not isinstance(target, ast.Name):
        return
    alias = mutation_alias(value, constants, aliases, operator_modules, operator_setitems)
    if alias is None:
        aliases.pop(target.id, None)
    else:
        aliases[target.id] = alias
def helper_name(expression: ast.expr, aliases: dict[str, str]) -> str:
    if not isinstance(expression, ast.Name):
        return ""
    return aliases.get(expression.id, expression.id)
def visible_helpers(scopes: list[dict[str, FunctionNode]]) -> dict[str, FunctionNode]:
    result: dict[str, FunctionNode] = {}
    for scope in scopes:
        result.update(scope)
    return result
def lookup_helper(scopes: list[dict[str, FunctionNode]], name: str) -> FunctionNode | None:
    return next((scope[name] for scope in reversed(scopes) if name in scope), None)
def is_static_method(node: FunctionNode) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
        isinstance(decorator, ast.Name) and decorator.id == "staticmethod" for decorator in node.decorator_list
    )
def add_helper(helpers: dict[str, FunctionNode], aliases: dict[str, str], name: str, node: FunctionNode) -> None:
    helpers[name] = node
    aliases[name] = name
def bound_method(node: FunctionNode) -> FunctionNode:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or is_static_method(node):
        return node
    result = copy.deepcopy(node)
    parameters = result.args.posonlyargs if result.args.posonlyargs else result.args.args
    if parameters:
        parameters.pop(0)
    return result
def bind_helper_alias(
    target: ast.expr,
    value: ast.expr,
    aliases: dict[str, str],
    scopes: list[dict[str, FunctionNode]],
) -> None:
    if isinstance(target, ast.Name) and isinstance(value, ast.Lambda):
        scopes[-1][target.id] = value
        aliases[target.id] = target.id
        return
    if not isinstance(target, ast.Name) or not isinstance(value, ast.Name):
        if isinstance(target, ast.Name):
            aliases.pop(target.id, None)
        return
    name = helper_name(value, aliases)
    if lookup_helper(scopes, name) is None:
        aliases.pop(target.id, None)
    else:
        aliases[target.id] = name
