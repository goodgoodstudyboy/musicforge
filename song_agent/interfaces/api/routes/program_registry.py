from __future__ import annotations

from song_agent.interfaces.api.route_contexts.core import CoreRouteContext

from dataclasses import asdict, dataclass
from typing import Any


PROGRAM_ROOT = "/api/unified-release-programs"


@dataclass(frozen=True, slots=True)
class ProgramRouteSpec:
    method: str
    pattern: str
    handler: str = "program_application.dispatch_http"
    auth: str = "configured"
    request_schema: str = "program-command-v1"
    response_schema: str = "program-result-v1"


class ProgramRouteRegistry(CoreRouteContext):
    def __init__(self) -> None:
        self._specs = tuple(
            ProgramRouteSpec(method, f"{PROGRAM_ROOT}/{{path}}")
            for method in ("GET", "POST", "PATCH", "PUT", "DELETE")
        )

    def matches(self, path: str) -> bool:
        return path == PROGRAM_ROOT or path.startswith(f"{PROGRAM_ROOT}/")

    def dispatch(self, port: Any, method: str, path: str) -> bool:
        if not self.matches(path):
            return False
        port.program_application.dispatch_http(port, method, path)
        return True

    def inventory(self) -> list[dict[str, str]]:
        return [asdict(spec) for spec in self._specs]


PROGRAM_ROUTE_REGISTRY = ProgramRouteRegistry()
