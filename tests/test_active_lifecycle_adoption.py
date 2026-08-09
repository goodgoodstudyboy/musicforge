from __future__ import annotations

from pathlib import Path

from song_agent.interfaces.bootstrap.api.program import active_lifecycle_registry
from song_agent.platform.lifecycle.attack_corpus import run_active_lifecycle_attack_corpus


def test_active_lifecycle_registry_requires_shared_services() -> None:
    report = active_lifecycle_registry.adoption_report()

    assert report["status"] == "passed", report
    assert len(report["rows"]) == 13
    assert all(not row["missing_methods"] for row in report["rows"])
    assert all(not row["missing_services"] for row in report["rows"])


def test_active_lifecycle_attack_corpus(tmp_path: Path) -> None:
    report = run_active_lifecycle_attack_corpus(tmp_path, active_lifecycle_registry)

    assert report["status"] == "passed"
    assert report["results"] == {
        "signoff_pair": True,
        "history_binding": True,
        "delete_signoff_file": True,
        "full_resign_signed_by": True,
        "stale_source": True,
        "change_request_reuse": True,
        "active_adoption": True,
    }
