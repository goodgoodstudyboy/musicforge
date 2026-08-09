from __future__ import annotations

from pathlib import Path

from song_agent.capabilities import capability_registry
from song_agent.interfaces.bootstrap.api.program import active_verifier_registry
from song_agent.platform.verification.attack_corpus import run_active_verifier_attack_corpus


def test_active_verifier_registry_is_complete_and_product_registered() -> None:
    rows = active_verifier_registry.inventory()
    platform_components = {row["component_type"] for row in rows}
    product_components = {
        row.component_type
        for row in capability_registry.all()
        if row.bounded_context == "program"
    }

    assert len(rows) == 13
    assert platform_components == product_components
    assert len({row["package_type"] for row in rows}) == len(rows)
    assert all(row["manifest_entry"] == "manifest.json" for row in rows)
    assert all(row["required_entries"] for row in rows)
    assert all(row["identity_fields"] for row in rows)
    assert all(row["lifecycle_bindings"] for row in rows)
    assert active_verifier_registry.adoption_report()["status"] == "passed"


def test_all_active_verifiers_share_the_envelope_attack_corpus(tmp_path: Path) -> None:
    report = run_active_verifier_attack_corpus(tmp_path, active_verifier_registry)

    assert report["status"] == "passed"
    assert report["capability_count"] == 13
    for row in report["rows"]:
        assert row["status"] == "passed", row
        assert all(row["results"].values()), row
