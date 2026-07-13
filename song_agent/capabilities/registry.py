from __future__ import annotations

from typing import Any

from song_agent.capabilities.model import CapabilitySpec, RuntimeVerificationSpec

# Compatibility export for v12 callers; definitions live in model.py so the
# registry/provider dependency remains acyclic.
__all__ = ["CapabilityRegistry", "CapabilitySpec", "RuntimeVerificationSpec", "capability_registry"]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, CapabilitySpec] = {}
        self._by_component: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        if spec.capability_id in self._by_id:
            raise ValueError(f"Duplicate capability id: {spec.capability_id}")
        keys = (spec.component_type, *spec.compatibility_aliases)
        duplicates = [key for key in keys if key in self._by_component]
        if duplicates:
            raise ValueError(f"Duplicate capability component type: {duplicates[0]}")
        self._by_id[spec.capability_id] = spec
        for key in keys:
            self._by_component[key] = spec

    def resolve_component(self, component_type: str) -> CapabilitySpec | None:
        return self._by_component.get(component_type)

    def get(self, capability_id: str) -> CapabilitySpec:
        return self._by_id[capability_id]

    def all(self) -> tuple[CapabilitySpec, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def inventory(self) -> list[dict[str, Any]]:
        return [
            {
                "capability_id": item.capability_id,
                "component_type": item.component_type,
                "bounded_context": item.bounded_context,
                "application_service": item.application_service,
                "package_type": item.runtime.package_type,
                "verification_package_type": item.runtime.verification_package_type,
                "gate_policies": list(item.gate_policies),
                "cli_commands": list(item.cli_commands),
                "api_routes": list(item.api_routes),
                "web_panel": item.web_panel,
                "release_checks": list(item.release_checks),
                "compatibility_aliases": list(item.compatibility_aliases),
            }
            for item in self.all()
        ]


capability_registry = CapabilityRegistry()


def _register_builtin_capabilities() -> None:
    from song_agent.capabilities.delivery import DELIVERY_CAPABILITIES
    from song_agent.capabilities.program import PROGRAM_CAPABILITIES
    from song_agent.capabilities.quality import QUALITY_CAPABILITIES

    for spec in (*DELIVERY_CAPABILITIES, *QUALITY_CAPABILITIES, *PROGRAM_CAPABILITIES):
        capability_registry.register(spec)


_register_builtin_capabilities()
