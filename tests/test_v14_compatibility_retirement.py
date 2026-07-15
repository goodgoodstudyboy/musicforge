from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from song_agent.release_check.v14_compatibility import evaluate_v14_compatibility_retirement


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_v14_compatibility_retirement_is_complete() -> None:
    report = evaluate_v14_compatibility_retirement(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert report["summary"] == {
        "baseline_module_count": 271,
        "domain_migration_count": 270,
        "retired_module_count": 271,
        "unresolved_module_count": 0,
        "active_to_compatibility_import_count": 0,
        "active_legacy_dependency_import_count": 0,
        "active_compatibility_implementation_line_count": 0,
        "dynamic_facade_count": 0,
        "wildcard_facade_count": 0,
    }
    assert report["current_profile_legacy_callables"] == []


def test_v14_compatibility_retirement_rejects_resigned_semantic_change(tmp_path: Path) -> None:
    document = json.loads(
        (ROOT / "architecture-v14-compatibility-retirement.json").read_text(encoding="utf-8")
    )
    forged = copy.deepcopy(document)
    forged["entries"][0]["retirement_status"] = "retired"
    forged["entries"][0]["target_module"] = "song_agent.domains.quality.acceptance_analytics"
    from song_agent.platform.verification.hashing import stable_hash

    forged["integrity_hash"] = stable_hash(
        {key: value for key, value in forged.items() if key != "integrity_hash"}
    )
    path = tmp_path / "retirement.json"
    path.write_text(json.dumps(forged), encoding="utf-8")

    report = evaluate_v14_compatibility_retirement(ROOT, retirement_path=path)

    assert report["status"] == "failed"
    assert any("target_binding" in blocker or "target_path" in blocker for blocker in report["blockers"])
