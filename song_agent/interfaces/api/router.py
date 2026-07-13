from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import asdict, dataclass
from typing import Callable, Iterable


HTTP_METHODS = {"GET", "POST", "PATCH", "PUT", "DELETE"}


@dataclass(frozen=True, slots=True)
class RouteSpec:
    method: str
    pattern: str
    handler: str
    auth: str
    request_schema: str
    response_schema: str


class RouteRegistry:
    def __init__(self, specs: Iterable[RouteSpec]) -> None:
        self._specs: dict[tuple[str, str], RouteSpec] = {}
        for spec in specs:
            key = (spec.method, spec.pattern)
            if key in self._specs:
                raise ValueError(f"Route conflict: {spec.method} {spec.pattern}")
            self._specs[key] = spec

    def inventory(self) -> list[dict[str, str]]:
        return [asdict(self._specs[key]) for key in sorted(self._specs)]


def _attribute_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _route_patterns(test: ast.AST, matcher_variables: dict[str, str]) -> list[str]:
    paths = sorted(
        {
            str(node.value)
            for node in ast.walk(test)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("/")
        }
    )
    if paths:
        return paths
    matchers = sorted(
        {
            name
            for node in ast.walk(test)
            if isinstance(node, ast.Call)
            and (name := _attribute_name(node.func)) is not None
            and name.startswith("_match_")
        }
    )
    matchers.extend(
        matcher_variables[node.id]
        for node in ast.walk(test)
        if isinstance(node, ast.Name) and node.id in matcher_variables
    )
    return [f"matcher:{name}" for name in matchers]


def _route_methods(test: ast.AST) -> list[str]:
    methods = sorted(
        {
            str(node.value)
            for node in ast.walk(test)
            if isinstance(node, ast.Constant) and node.value in HTTP_METHODS
        }
    )
    return methods or ["*"]


def route_specs_from_dispatch(dispatch: Callable[..., object]) -> tuple[RouteSpec, ...]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(dispatch)))
    matcher_variables: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.NamedExpr)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        matcher = _attribute_name(value.func)
        if matcher is None or not matcher.startswith("_match_"):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                matcher_variables[target.id] = matcher
    rows: dict[tuple[str, str], RouteSpec] = {}
    for branch in sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.If)),
        key=lambda node: node.lineno,
    ):
        handlers = sorted(
            {
                node.func.attr
                for statement in branch.body
                for node in ast.walk(statement)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr.startswith("_handle_")
            }
        )
        patterns = _route_patterns(branch.test, matcher_variables)
        if not handlers or not patterns:
            continue
        methods = _route_methods(branch.test)
        for method in methods:
            for pattern in patterns:
                for handler in handlers:
                    key = (method, pattern)
                    candidate = RouteSpec(
                        method=method,
                        pattern=pattern,
                        handler=handler,
                        auth="configured",
                        request_schema="legacy-compatible",
                        response_schema="legacy-compatible",
                    )
                    current = rows.get(key)
                    if current is not None and current.handler != candidate.handler:
                        raise ValueError(
                            f"Route conflict: {method} {pattern} maps to "
                            f"{current.handler} and {candidate.handler}"
                        )
                    rows[key] = candidate
    return tuple(rows[key] for key in sorted(rows))


DEFAULT_ROUTE_REGISTRY = RouteRegistry(())


def configure_route_registry(dispatch: Callable[..., object]) -> RouteRegistry:
    global DEFAULT_ROUTE_REGISTRY
    DEFAULT_ROUTE_REGISTRY = RouteRegistry(route_specs_from_dispatch(dispatch))
    return DEFAULT_ROUTE_REGISTRY


def api_inventory() -> list[dict[str, str]]:
    return DEFAULT_ROUTE_REGISTRY.inventory()
