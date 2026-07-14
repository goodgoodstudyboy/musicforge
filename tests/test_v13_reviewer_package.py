from __future__ import annotations

import json
from pathlib import Path

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.release_check.architecture_ratchet import verify_architecture_ratchet_report
from song_agent.release_check.lts_audit import write_reviewer_package


ROOT = Path(__file__).resolve().parents[1]


def test_reviewer_package_architecture_delta_is_independently_recomputed(tmp_path: Path) -> None:
    package = write_reviewer_package(ROOT, tmp_path / "reviewer", runtime={"status": "passed"})
    report = json.loads((package / "architecture-ratchet.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "architecture-baseline.json").read_text(encoding="utf-8"))

    verification = verify_architecture_ratchet_report(
        ROOT,
        report,
        current_baseline=baseline,
        snapshot=build_architecture_snapshot(ROOT),
    )

    assert verification == {"status": "passed", "mismatches": [], "runtime_status": "passed"}


def test_reviewer_package_rejects_resigned_architecture_delta(tmp_path: Path) -> None:
    package = write_reviewer_package(ROOT, tmp_path / "reviewer", runtime={"status": "passed"})
    report = json.loads((package / "architecture-ratchet.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "architecture-baseline.json").read_text(encoding="utf-8"))
    report["delta"]["active_to_compatibility_import_count"] = 0

    verification = verify_architecture_ratchet_report(
        ROOT,
        report,
        current_baseline=baseline,
        snapshot=build_architecture_snapshot(ROOT),
    )

    assert verification["status"] == "failed"
    assert verification["mismatches"] == ["delta"]
