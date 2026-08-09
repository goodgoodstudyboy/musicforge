from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.v14_baseline import _coverage_totals, build_v14_baseline, verify_v14_baseline


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_v14_baseline_matches_v138_final_architecture() -> None:
    documents = build_v14_baseline(ROOT)
    architecture = documents["architecture.json"]
    retirement = documents["compatibility-retirement.json"]

    assert architecture["baseline_sha"] == "98a7b25cbe505dca9f2f3ab946951adf3ebd1b2a"
    assert architecture["module_count"] == 916
    assert architecture["production_cycle_count"] == 0
    assert architecture["active_to_compatibility_import_count"] == 224
    assert retirement["summary"]["module_count"] == 271
    assert retirement["summary"]["active_edge_count"] == 224
    assert retirement["summary"]["nonblank_source_lines"] == 137_975
    assert sum(retirement["summary"]["context_module_counts"].values()) == 271


def test_v14_tracked_baseline_is_complete_and_reproducible() -> None:
    report = verify_v14_baseline(ROOT)

    assert report["status"] == "passed", report["blockers"]
    tracked = json.loads((ROOT / "architecture-v14-migration.json").read_text(encoding="utf-8"))
    entries = tracked["retirement"]["entries"]
    assert all(row["owner"].startswith("musicforge-") for row in entries)
    assert all(row["target_module"].startswith("song_agent.") for row in entries)
    assert not any(row["context"] == "unknown" for row in entries)


def test_v14_coverage_baseline_separates_active_and_compatibility_paths() -> None:
    report = {
        "files": {
            "song_agent/platform/verification/kernel.py": {
                "summary": {"num_statements": 10, "covered_lines": 9}
            },
            "song_agent/legacy.py": {"summary": {"num_statements": 20, "covered_lines": 5}},
        }
    }

    active = _coverage_totals(report, include_roots=("song_agent/platform/",))
    compatibility = _coverage_totals(report, exclude_roots=("song_agent/platform/",))

    assert active == {"statements": 10, "covered": 9, "missing": 1, "percent": 90.0}
    assert compatibility == {"statements": 20, "covered": 5, "missing": 15, "percent": 25.0}
