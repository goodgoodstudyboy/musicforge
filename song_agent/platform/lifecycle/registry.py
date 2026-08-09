from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document


@dataclass(frozen=True)
class LifecycleCapability:
    component_type: str
    module: str
    store_class: str
    store_type: type[object]
    source_path: Path
    signoff_method: str = ""
    reset_method: str = ""
    archive_method: str = ""
    required_services: tuple[str, ...] = ()

    def inventory(self) -> JsonDocument:
        return normalize_json_document({
            "component_type": self.component_type,
            "module": self.module,
            "store_class": self.store_class,
            "signoff_method": self.signoff_method,
            "reset_method": self.reset_method,
            "archive_method": self.archive_method,
            "required_services": list(self.required_services),
        })


class LifecycleCapabilityRegistry:
    def __init__(self, capabilities: tuple[LifecycleCapability, ...]) -> None:
        self._capabilities = capabilities
        identities = [row.component_type for row in capabilities]
        if len(identities) != len(set(identities)):
            raise ValueError("Lifecycle component identities must be unique.")

    def all(self) -> tuple[LifecycleCapability, ...]:
        return self._capabilities

    def inventory(self) -> list[JsonDocument]:
        return [row.inventory() for row in self._capabilities]

    def adoption_report(self) -> JsonDocument:
        rows = [_adoption_row(capability) for capability in self._capabilities]
        return normalize_json_document({
            "schema_version": 1,
            "status": "passed" if all(row["status"] == "passed" for row in rows) else "failed",
            "rows": rows,
        })

def _adoption_row(capability: LifecycleCapability) -> JsonDocument:
    store = capability.store_type
    source_path = capability.source_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    call_owners = {
        node.func.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
    }
    call_owners.update(
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    missing_methods = [
        name
        for name in (capability.signoff_method, capability.reset_method, capability.archive_method)
        if name and not callable(getattr(store, name, None))
    ]
    missing_services = sorted(set(capability.required_services) - call_owners)
    return normalize_json_document({
        **capability.inventory(),
        "status": "passed" if not missing_methods and not missing_services else "failed",
        "missing_methods": missing_methods,
        "missing_services": missing_services,
    })
