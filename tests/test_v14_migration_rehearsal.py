from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.platform.persistence import V14MigrationOrchestrator
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.persistence_cli import main as persistence_main


pytestmark = pytest.mark.integration


def _workspace(root: Path) -> Path:
    workspace = root / ".musicforge"
    program = workspace / "unified-release-programs" / "release-001"
    program.mkdir(parents=True)
    (program / "program.json").write_text(
        '{"component_type":"unified_release_program","generation":1,"program_id":"release-001","status":"ready"}\n',
        encoding="utf-8",
    )
    (program / "program-signoff.json").write_text(
        '{"integrity_hash":"signed-source","status":"signed"}\n', encoding="utf-8"
    )
    (program / "program-signoff-history.jsonl").write_text(
        '{"event_hash":"signed-event","event_type":"signed"}\n', encoding="utf-8"
    )
    pointer = workspace / "state" / "current" / "program.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text('{"generation_id":"generation-000001"}\n', encoding="utf-8")
    return workspace


def test_v14_migration_writes_bound_intent_report_and_commit_marker(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    migration = V14MigrationOrchestrator(workspace)
    plan = migration.plan()
    immutable_before = list(plan["immutable_artifacts"])

    report = migration.apply()

    assert report["status"] == "passed"
    assert report["verified_backup"] is True
    assert report["source_preserved"] is True
    assert report["immutable_artifacts_preserved"] is True
    assert report["current_pointers_preserved"] is True
    evidence = workspace / "state" / "migrations" / "v14" / str(plan["migration_id"])
    documents = [json.loads((evidence / name).read_text(encoding="utf-8")) for name in (
        "migration-plan.json", "intent.json", "migration-report.json", "commit-marker.json"
    )]
    assert all(integrity_ok(value) for value in documents)
    assert documents[3]["plan_hash"] == documents[0]["integrity_hash"]
    assert documents[3]["intent_hash"] == documents[1]["integrity_hash"]
    assert documents[3]["report_hash"] == documents[2]["integrity_hash"]
    assert migration.plan()["immutable_artifacts"] == immutable_before
    assert migration.apply()["status"] == "already_applied"


def test_v14_migration_rollback_rehearsal_is_byte_identical(tmp_path: Path) -> None:
    migration = V14MigrationOrchestrator(_workspace(tmp_path))

    result = migration.rollback_rehearsal()

    assert result["status"] == "passed", result
    assert result["file_count"] >= 3
    assert result["verified_backup"] is True
    assert result["byte_identical"] is True
    assert result["immutable_artifacts_identical"] is True
    assert result["current_pointers_identical"] is True
    assert result["logical_state_identical"] is True
    assert integrity_ok(result)


def test_v14_migration_rejects_tampered_commit_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    migration = V14MigrationOrchestrator(workspace)
    plan = migration.plan()
    migration.apply()
    marker = workspace / "state" / "migrations" / "v14" / str(plan["migration_id"]) / "commit-marker.json"
    value = json.loads(marker.read_text(encoding="utf-8"))
    value["report_hash"] = "f" * 64
    marker.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(RuntimeError, match="committed evidence"):
        migration.apply()


def test_v14_migration_rejects_full_resigned_source_binding(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    migration = V14MigrationOrchestrator(workspace)
    plan = migration.plan()
    migration.apply()
    evidence = workspace / "state" / "migrations" / "v14" / str(plan["migration_id"])
    names = ("migration-plan.json", "intent.json", "migration-report.json", "commit-marker.json")
    documents = {name: json.loads((evidence / name).read_text(encoding="utf-8")) for name in names}
    documents["migration-plan.json"]["source_hash"] = "f" * 64
    documents["migration-plan.json"]["integrity_hash"] = integrity_hash(documents["migration-plan.json"])
    plan_hash = documents["migration-plan.json"]["integrity_hash"]
    for name in ("intent.json", "migration-report.json", "commit-marker.json"):
        documents[name]["source_hash"] = "f" * 64
        documents[name]["plan_hash"] = plan_hash
    documents["intent.json"]["integrity_hash"] = integrity_hash(documents["intent.json"])
    documents["migration-report.json"]["intent_hash"] = documents["intent.json"]["integrity_hash"]
    documents["migration-report.json"]["integrity_hash"] = integrity_hash(documents["migration-report.json"])
    documents["commit-marker.json"]["intent_hash"] = documents["intent.json"]["integrity_hash"]
    documents["commit-marker.json"]["report_hash"] = documents["migration-report.json"]["integrity_hash"]
    documents["commit-marker.json"]["integrity_hash"] = integrity_hash(documents["commit-marker.json"])
    for name, document in documents.items():
        (evidence / name).write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeError, match="ledger binding"):
        migration.rollback(str(plan["migration_id"]))


def test_v14_migration_cli_exposes_plan_apply_and_rehearsal(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    assert persistence_main(["--workspace", str(workspace), "v14-plan"]) == 0
    assert persistence_main(["--workspace", str(workspace), "v14-rollback-rehearsal"]) == 0
    assert persistence_main(["--workspace", str(workspace), "v14-apply"]) == 0
