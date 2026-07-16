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


def test_architecture_snapshot_cache_isolated_and_invalidated(tmp_path: Path) -> None:
    package = tmp_path / "song_agent"
    package.mkdir()
    source = package / "sample.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    first = build_architecture_snapshot(tmp_path)
    first["modules"].clear()
    cached = build_architecture_snapshot(tmp_path)
    source.write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
    changed = build_architecture_snapshot(tmp_path)

    assert len(cached["modules"]) == 1
    assert changed["total_source_lines"] > cached["total_source_lines"]


def test_architecture_module_ownership_is_complete() -> None:
    baseline = json.loads((ROOT / "architecture-baseline.json").read_text(encoding="utf-8"))
    snapshot = build_architecture_snapshot(ROOT)
    baseline_modules = {row["module"] for row in baseline["modules"]}
    current_modules = {row["module"] for row in snapshot["modules"]}

    assert current_modules == baseline_modules
    assert all(row["layer"] in {"platform", "domain", "application", "interface", "release_check", "compatibility"} for row in baseline["modules"])
    assert all(row["context"] in {None, "creation", "studio", "quality", "delivery", "trust", "program", "registry", "cli", "api", "web"} for row in baseline["modules"])
    assert baseline["active_to_compatibility_import_max_count"] == 0
    assert baseline["allowed_active_to_compatibility_imports"] == snapshot["active_to_compatibility_imports"]


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
        "song_agent/interfaces/api/runtime.py",
        "song_agent/interfaces/api/routes/creation.py",
        "song_agent/interfaces/api/routes/studio.py",
        "song_agent/interfaces/api/routes/quality.py",
        "song_agent/interfaces/api/routes/delivery.py",
        "song_agent/interfaces/api/routes/trust.py",
        "song_agent/interfaces/api/routes/program.py",
        "song_agent/interfaces/api/routes/maintenance.py",
        "song_agent/interfaces/cli/commands/creation.py",
        "song_agent/interfaces/cli/commands/studio.py",
        "song_agent/interfaces/cli/commands/quality.py",
        "song_agent/interfaces/cli/commands/delivery.py",
        "song_agent/interfaces/cli/commands/trust.py",
        "song_agent/interfaces/cli/commands/program.py",
        "song_agent/interfaces/cli/commands/maintenance.py",
        "song_agent/interfaces/cli/commands/release_check.py",
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
    assert metrics["active_to_compatibility_import_count"] == len(metrics["active_to_compatibility_imports"])
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
