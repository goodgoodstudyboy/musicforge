from __future__ import annotations

import pytest

from song_agent.capabilities import CapabilityRegistry, CapabilitySpec, RuntimeVerificationSpec, capability_registry


def test_builtin_capability_inventory_is_unique_and_complete() -> None:
    rows = capability_registry.inventory()

    assert len(rows) >= 16
    assert len({row["capability_id"] for row in rows}) == len(rows)
    assert len({row["component_type"] for row in rows}) == len(rows)
    assert all(row["bounded_context"] in {"delivery", "quality", "program"} for row in rows)
    assert all(row["application_service"] for row in rows)
    assert all(row["verification_package_type"] for row in rows)


def test_capability_registry_rejects_duplicate_component_and_alias() -> None:
    registry = CapabilityRegistry()
    runtime = RuntimeVerificationSpec("module", "function", "package", "verification")
    registry.register(CapabilitySpec("one", "component", "test", "service", runtime, compatibility_aliases=("legacy",)))

    with pytest.raises(ValueError):
        registry.register(CapabilitySpec("two", "component", "test", "service", runtime))
    with pytest.raises(ValueError):
        registry.register(CapabilitySpec("three", "other", "test", "service", runtime, compatibility_aliases=("legacy",)))
