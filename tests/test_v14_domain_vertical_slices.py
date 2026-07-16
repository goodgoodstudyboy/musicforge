from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.release_check.v14_certification import (
    DOMAIN_CONTRACTS,
    evaluate_v14_domain_vertical_slices,
    evaluate_v14_verification_lifecycle_security,
)


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_all_v14_domain_vertical_slices_are_current_and_contract_bound() -> None:
    report = evaluate_v14_domain_vertical_slices(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert set(report["summary"]["context_module_counts"]) == set(DOMAIN_CONTRACTS)
    assert report["summary"]["context_count"] == 6
    assert report["summary"]["module_count"] == 270
    assert report["summary"]["facade_contract_count"] == 270
    assert report["summary"]["contract_context_count"] == 6
    assert report["summary"]["active_to_compatibility_import_count"] == 0


@pytest.mark.security
def test_v14_verification_and_lifecycle_attack_corpora_pass() -> None:
    report = evaluate_v14_verification_lifecycle_security(ROOT)

    assert report["status"] == "passed", report
    assert all(report["signals"].values())
