from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from song_agent.release_check.v14_architecture import (
    _context_limit_blockers,
    _limit_blockers,
    evaluate_v14_architecture,
)


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_v14_phase_architecture_ratchet_passes_without_hiding_debt() -> None:
    report = evaluate_v14_architecture(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert report["metrics"]["active_to_compatibility_import_count"] == 224
    assert report["metrics"]["anonymous_part_file_count"] == 0
    assert report["metrics"]["interface_wildcard_import_count"] == 0
    assert report["metrics"]["interface_store_reference_count"] == 0
    assert report["metrics"]["new_flat_module_count"] == 0


def test_v14_ratchet_rejects_growth_and_final_requires_zero() -> None:
    policy = json.loads((ROOT / "architecture-v14-policy.json").read_text(encoding="utf-8"))
    metrics = copy.deepcopy(policy["limits"])
    metrics["active_to_compatibility_import_count"] += 1
    metrics["active_to_compatibility_by_context"]["quality"] += 1

    ratchet = _limit_blockers(metrics, policy["limits"], final=False)
    contexts = _context_limit_blockers(metrics, policy, final=False)

    assert any("active_to_compatibility_import_count" in blocker for blocker in ratchet)
    assert any(":quality:" in blocker for blocker in contexts)
    assert _limit_blockers(metrics, policy["final_targets"], final=True)
