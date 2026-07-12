from __future__ import annotations

import json
from pathlib import Path

from song_agent.architecture_guardrails import (
    build_architecture_snapshot,
    evaluate_architecture,
    update_architecture_release_metrics,
    write_architecture_metrics,
)


ROOT = Path(__file__).resolve().parents[1]


def test_architecture_module_ownership_is_complete() -> None:
    baseline = json.loads((ROOT / "architecture-baseline.json").read_text(encoding="utf-8"))
    snapshot = build_architecture_snapshot(ROOT)
    baseline_modules = {row["module"] for row in baseline["modules"]}
    current_modules = {row["module"] for row in snapshot["modules"]}

    assert current_modules == baseline_modules
    assert all(row["layer"] in {"platform", "domain", "application", "interface", "release_check", "compatibility"} for row in baseline["modules"])
    assert all(row["context"] in {None, "creation", "studio", "quality", "delivery", "trust", "program", "cli", "api", "web"} for row in baseline["modules"])


def test_architecture_ratchets_and_metrics_report(tmp_path: Path) -> None:
    report = evaluate_architecture(ROOT)
    metrics_path = write_architecture_metrics(report, tmp_path / "runs" / "architecture" / "metrics.json")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert report["status"] == "passed", report["blockers"]
    assert metrics["status"] == "passed"
    assert metrics["blockers"] == []
    assert metrics["module_count"] > 0
    assert metrics["total_source_lines"] > 0
    assert set(metrics["mega_files"]) == {
        "song_agent/release_checks.py",
        "song_agent/server.py",
        "song_agent/cli.py",
        "song_agent/webui.py",
    }
    assert set(metrics["security_helper_counts"]) == {
        "_raw_zip_entry_names",
        "_is_safe_zip_entry",
        "_zip_has_no_trailing_data",
    }
    assert metrics["source_file_count"] == metrics["module_count"]
    assert len(metrics["top_largest_files"]) == 20
    assert len(metrics["top_largest_functions"]) == 20
    assert len(metrics["top_largest_classes"]) == 20
    assert metrics["internal_import_edge_count"] == len(metrics["internal_import_edges"])
    assert metrics["domain_interface_violation_count"] == 0
    assert metrics["store_class_count"] > 0
    assert metrics["verifier_module_count"] > 0
    assert metrics["verifier_function_count"] > 0
    assert metrics["dict_str_any_count"] > 0
    assert metrics["cli_argument_count"] > 0
    assert metrics["api_route_count"] > 0
    assert metrics["web_function_count"] > 0
    assert metrics["pytest_test_function_count"] > 0
    assert str(ROOT) not in metrics_path.read_text(encoding="utf-8")

    updated = update_architecture_release_metrics(
        metrics_path,
        profile="v12",
        duration_ms=1234,
        status="passed",
        check_count=26,
    )
    assert updated == metrics_path
    release_check = json.loads(metrics_path.read_text(encoding="utf-8"))["release_check"]
    assert release_check == {
        "profile": "v12",
        "duration_ms": 1234,
        "status": "passed",
        "check_count": 26,
    }
