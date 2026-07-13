from __future__ import annotations

import json
from pathlib import Path

from song_agent.release_check.lts_audit import build_lts_audit, write_reviewer_package
from song_agent.release_check.lts_cutover import run_lts_cutover_smoke


ROOT = Path(__file__).resolve().parents[1]


def test_v13_lts_audit_enforces_cutover_invariants() -> None:
    audit = build_lts_audit(ROOT)

    assert audit["status"] == "passed", audit
    assert all(audit["checks"].values())
    assert audit["source"]["production_cycle_count"] == 0
    assert not any(audit["source"]["active_security_helpers"].values())
    assert not any(audit["source"]["active_lifecycle_algorithms"].values())
    assert audit["comparison"]["v13.0"]["lines"] <= audit["comparison"]["v12.13"]["lines"]


def test_v13_reviewer_package_is_complete_and_path_safe(tmp_path: Path) -> None:
    output = write_reviewer_package(ROOT, tmp_path / "reviewer", runtime={"status": "passed"})
    documents = {path.name for path in output.iterdir() if path.is_file()}
    rendered = b"\n".join(path.read_bytes() for path in output.iterdir() if path.is_file())

    assert documents == {
        "README.md", "architecture.json", "cli-api-compatibility.json", "compatibility.json",
        "debt.json", "deprecations.json", "duplicate-helpers.json", "import-graph.json",
        "lifecycle-migration.json", "migration-rollback.json", "persistence-migration.json",
        "ci-matrix.json", "performance.json", "release-alignment.json", "release-check-reports.json",
        "runtime-verification.json", "security-attack-matrix.json", "source-comparison.json",
        "verifier-migration.json",
    }
    assert str(ROOT).encode() not in rendered
    assert str(tmp_path).encode() not in rendered
    assert json.loads((output / "architecture.json").read_text(encoding="utf-8"))["status"] == "passed"


def test_v13_lts_cutover_smoke() -> None:
    ok, detail = run_lts_cutover_smoke(ROOT)

    assert ok is True, detail
    assert all(json.loads(detail).values())
