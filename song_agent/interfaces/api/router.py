from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from song_agent.interfaces.api.routes.manifest import ACTIVE_DISPATCH_HANDLERS, ACTIVE_ROUTE_ROWS


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

    def dispatch(self, port: object, method: str, path: str, parsed: object) -> bool:
        for handler_name in ACTIVE_DISPATCH_HANDLERS:
            handler = getattr(port, handler_name)
            if handler(method, path, parsed):
                return True
        return False


def explicit_route_specs() -> tuple[RouteSpec, ...]:
    return tuple(RouteSpec(*row) for row in ACTIVE_ROUTE_ROWS)


def route_specs_from_dispatch(_dispatch: Callable[..., object] | None = None) -> tuple[RouteSpec, ...]:
    """Compatibility API for callers migrating from the pre-v13.5 AST registry."""

    return explicit_route_specs()


DEFAULT_ROUTE_REGISTRY = RouteRegistry(explicit_route_specs())


def configure_route_registry(_dispatch: Callable[..., object] | None = None) -> RouteRegistry:
    global DEFAULT_ROUTE_REGISTRY
    DEFAULT_ROUTE_REGISTRY = RouteRegistry(explicit_route_specs())
    return DEFAULT_ROUTE_REGISTRY


def api_inventory() -> list[dict[str, str]]:
    return DEFAULT_ROUTE_REGISTRY.inventory()
