from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from song_agent.architecture_guardrails import build_architecture_snapshot, evaluate_architecture
from song_agent.release_check.architecture_ratchet import evaluate_architecture_ratchet, evaluate_interface_limits


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def architecture_state() -> tuple[dict[str, Any], dict[str, Any]]:
    baseline = json.loads((ROOT / "architecture-baseline.json").read_text(encoding="utf-8"))
    return baseline, build_architecture_snapshot(ROOT)


def test_architecture_ratchet_rejects_loosened_mega_limit(
    architecture_state: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    baseline, snapshot = copy.deepcopy(architecture_state)
    path = next(iter(baseline["mega_file_max_lines"]))
    baseline["mega_file_max_lines"][path] += 1

    report = evaluate_architecture_ratchet(ROOT, current_baseline=baseline, snapshot=snapshot)

    assert report["status"] == "failed"
    assert f"architecture_baseline_loosened:mega_file_max_lines:{path}" in report["blockers"]


def test_architecture_ratchet_rejects_unfunded_compatibility_reclassification(
    architecture_state: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    baseline, snapshot = copy.deepcopy(architecture_state)
    module = next(row for row in snapshot["modules"] if row["layer"] == "platform")
    module["layer"] = "compatibility"

    report = evaluate_architecture_ratchet(ROOT, current_baseline=baseline, snapshot=snapshot)

    assert report["status"] == "failed"
    assert f"architecture_compatibility_debt_missing:{module['module']}" in report["blockers"]


def test_architecture_ratchet_rejects_new_active_to_compatibility_import(
    architecture_state: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    baseline, snapshot = copy.deepcopy(architecture_state)
    snapshot["active_to_compatibility_imports"].append(
        {"importer": "song_agent.platform.verification", "imported": "song_agent.projectio"}
    )

    report = evaluate_architecture_ratchet(ROOT, current_baseline=baseline, snapshot=snapshot)

    assert report["status"] == "failed"
    assert any("architecture_compatibility_import_added" in row for row in report["blockers"])


def test_interface_limits_reject_new_thousand_line_route_handler(tmp_path: Path) -> None:
    route = tmp_path / "song_agent" / "interfaces" / "api" / "routes" / "oversized.py"
    route.parent.mkdir(parents=True)
    route.write_text(
        "def _handle_oversized():\n" + "    value = 1\n" * 999 + "    return value\n",
        encoding="utf-8",
    )

    report = evaluate_interface_limits(
        tmp_path,
        previous_tag="v13.0.2",
        debt={
            "interface_limits": {
                "module_max_lines": 600,
                "new_module_max_lines": 400,
                "function_max_lines": 80,
                "route_handler_max_lines": 100,
            }
        },
    )

    assert report["status"] == "failed"
    assert any("architecture_interface_new_module_limit" in row for row in report["blockers"])
    assert any("architecture_interface_function_limit" in row for row in report["blockers"])


def test_current_architecture_ratchet_is_enforced() -> None:
    report = evaluate_architecture(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert report["metrics"]["ratchet"]["delta"]["active_to_compatibility_import_count"] < 0
    assert report["metrics"]["ratchet"]["compatibility_debt_count"] == 245
