from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.capabilities.model import CapabilitySpec, RuntimeIdentitySpec, RuntimeVerificationSpec

# Compatibility export for v12 callers; definitions live in model.py so the
# registry/provider dependency remains acyclic.
__all__ = ["CapabilityRegistry", "CapabilitySpec", "RuntimeIdentitySpec", "RuntimeVerificationSpec", "capability_registry"]


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

    def inventory(self) -> list[DomainDocument]:
        from song_agent.platform.verification.registry import active_verifier_registry

        verifier_by_component = {row.component_type: row for row in active_verifier_registry.all()}
        return [
            {
                "capability_id": item.capability_id,
                "component_type": item.component_type,
                "bounded_context": item.bounded_context,
                "application_service": item.application_service,
                "package_type": item.runtime.package_type,
                "verification_package_type": item.runtime.verification_package_type,
                "required_proofs": list(item.runtime.required_proofs),
                "manifest_entry": (
                    verifier_by_component[item.component_type].package_spec().manifest_entry
                    if item.component_type in verifier_by_component
                    else ""
                ),
                "allowed_entries": (
                    sorted(verifier_by_component[item.component_type].package_spec().allowed_entries)
                    if item.component_type in verifier_by_component
                    else []
                ),
                "allowed_entry_patterns": (
                    list(verifier_by_component[item.component_type].package_spec().allowed_entry_patterns)
                    if item.component_type in verifier_by_component
                    else []
                ),
                "lifecycle_binding_requirements": (
                    list(verifier_by_component[item.component_type].lifecycle_bindings)
                    if item.component_type in verifier_by_component
                    else []
                ),
                "identity_fields": {
                    "component_id": list(item.runtime.identity.component_id_fields),
                    "generation": list(item.runtime.identity.generation_fields),
                    "current_generation": list(item.runtime.identity.current_generation_fields),
                    "source_hash": list(item.runtime.identity.source_hash_fields),
                },
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
