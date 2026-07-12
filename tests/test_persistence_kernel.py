from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from song_agent.persistence_cli import main as persistence_main
from song_agent.platform.persistence import (
    FileUnitOfWork,
    LegacyWorkspaceMigrator,
    MusicForgeDatabase,
    PersistenceRecovery,
    WorkflowRepository,
    WorkspaceLock,
    WorkspaceLockError,
)
from song_agent.platform.persistence.repository import sync_active_v12_state
from song_agent.platform.verification.hashing import integrity_hash


ACTIVE_V12_STORES = (
    "unified_release_program.py",
    "unified_release_program_operations.py",
    "unified_release_program_handoff.py",
    "unified_release_program_vault.py",
    "unified_release_program_vault_operations.py",
    "unified_release_program_continuity.py",
    "unified_release_program_continuity_distribution.py",
    "unified_release_program_continuity_acceptance.py",
    "unified_release_program_continuity_acceptance_change.py",
    "unified_release_program_continuity_command_center.py",
    "unified_release_program_continuity_command_center_signoff.py",
    "unified_release_program_continuity_command_center_acceptance.py",
    "unified_release_program_continuity_command_center_acceptance_change.py",
)


def test_database_wal_schema_repository_and_optimistic_concurrency(tmp_path: Path) -> None:
    database = MusicForgeDatabase.from_workspace(tmp_path)
    database.initialize()

    with database.session() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert database.schema_version() == 1

    repository = WorkflowRepository(database)
    first = repository.save("command_center", "cc-1", generation=1, status="draft", expected_version=0)
    second = repository.save("command_center", "cc-1", generation=1, status="ready", expected_version=first.version)
    assert second.version == 2
    assert repository.get("command_center", "cc-1") == second
    with pytest.raises(RuntimeError, match="concurrently"):
        repository.save("command_center", "cc-1", generation=2, status="stale", expected_version=1)
    assert repository.next_id("review", prefix="review-") == "review-000001"
    assert repository.next_id("review", prefix="review-") == "review-000002"


def test_workspace_lock_is_reentrant_cross_process_and_does_not_break_live_lease(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    callbacks: list[str] = []
    with WorkspaceLock(workspace, operation="outer", lease_seconds=1, on_commit=lambda: callbacks.append("outer")):
        with WorkspaceLock(workspace, operation="inner", lease_seconds=1, on_commit=lambda: callbacks.append("inner")):
            assert (workspace / "state" / "locks" / "workspace-write.lock").is_file()

        code = (
            "from song_agent.platform.persistence import WorkspaceLock,WorkspaceLockError;"
            "import pathlib,sys;"
            "root=pathlib.Path(sys.argv[1]);"
            "\ntry:\n WorkspaceLock(root,timeout_seconds=.2).acquire()\nexcept WorkspaceLockError:\n raise SystemExit(7)\nraise SystemExit(0)"
        )
        time.sleep(1.05)
        result = subprocess.run([sys.executable, "-c", code, str(workspace)], cwd=Path.cwd(), check=False)
        assert result.returncode == 7
    assert callbacks == ["outer"]
    with WorkspaceLock(workspace, timeout_seconds=1):
        pass


def test_workspace_lock_serializes_active_program_store_subprocesses(tmp_path: Path) -> None:
    root = tmp_path / ".musicforge" / "unified-release-programs"
    code = (
        "from song_agent.unified_release_program import UnifiedReleaseProgramStore;"
        "import pathlib,sys;"
        "store=UnifiedReleaseProgramStore(root=pathlib.Path(sys.argv[1]));"
        "print(store.create_program({'name':'concurrent'})['program_id'])"
    )
    processes = [
        subprocess.Popen([sys.executable, "-c", code, str(root)], cwd=Path.cwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=30) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], results
    assert sorted(stdout.strip() for stdout, _ in results) == ["urp-000001", "urp-000002"]


def test_workspace_lock_recovers_only_confirmed_dead_owner(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    lock = WorkspaceLock(workspace, timeout_seconds=1)
    lock.lock_path.parent.mkdir(parents=True)
    lock.lock_path.write_text(
        json.dumps({"owner_pid": 2_147_483_647, "token": "stale", "operation": "dead", "lease_seconds": 1}),
        encoding="utf-8",
    )
    with lock:
        current = json.loads(lock.lock_path.read_text(encoding="utf-8"))
        assert current["owner_pid"] != 2_147_483_647


def test_workspace_lock_write_failure_does_not_leave_live_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / ".musicforge"
    lock = WorkspaceLock(workspace, timeout_seconds=1)

    def fail_write(descriptor: int, data: bytes) -> int:
        del descriptor, data
        raise OSError("disk full")

    monkeypatch.setattr(os, "write", fail_write)
    with pytest.raises(OSError, match="disk full"):
        lock.acquire()
    assert not lock.lock_path.exists()


@pytest.mark.parametrize("stage", ["after_generation", "after_pointer", "before_database_commit", "after_database_commit"])
def test_file_unit_of_work_recovers_crash_boundaries(tmp_path: Path, stage: str) -> None:
    def crash(current: str) -> None:
        if current == stage:
            raise RuntimeError(f"crash:{stage}")

    unit = FileUnitOfWork(tmp_path, "receiver-acceptance", transaction_id=f"tx-{stage}", crash_hook=crash)
    unit.write_json("state.json", {"generation": 1, "status": "ready"})
    unit.write_bytes("evidence.bin", b"immutable")
    with pytest.raises(RuntimeError, match="crash"):
        unit.commit()

    report = PersistenceRecovery(tmp_path).recover()
    assert unit.transaction_id in report["recovered"]
    pointer = unit.artifacts.read_pointer("receiver-acceptance")
    assert pointer["generation_id"] == unit.transaction_id
    assert unit.artifacts.marker_path(unit.transaction_id).is_file()


def test_file_unit_of_work_rolls_back_pre_generation_and_blocks_corrupt_recovery(tmp_path: Path) -> None:
    def crash(stage: str) -> None:
        if stage == "after_intent":
            raise RuntimeError("crash")

    unit = FileUnitOfWork(tmp_path, "command-center", transaction_id="tx-pre-generation", crash_hook=crash)
    unit.write_json("state.json", {"status": "draft"})
    with pytest.raises(RuntimeError):
        unit.commit()
    report = PersistenceRecovery(tmp_path).recover()
    assert report["rolled_back"] == ["tx-pre-generation"]
    assert not unit.artifacts.current_pointer_path("command-center").exists()

    corrupt = FileUnitOfWork(tmp_path, "command-center", transaction_id="tx-corrupt", crash_hook=lambda stage: (_ for _ in ()).throw(RuntimeError("crash")) if stage == "after_pointer" else None)
    corrupt.write_json("state.json", {"status": "ready"})
    with pytest.raises(RuntimeError):
        corrupt.commit()
    generation_file = corrupt.artifacts.generation_dir("command-center", "tx-corrupt") / "state.json"
    generation_file.write_text("tampered", encoding="utf-8")
    with pytest.raises(RuntimeError, match="integrity failure"):
        PersistenceRecovery(tmp_path).recover()


def test_legacy_migration_is_dry_run_backed_up_idempotent_and_reversible(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    source = workspace / "unified-release-programs" / "urp-000001" / "continuity-command-center" / "command-center-report.json"
    source.parent.mkdir(parents=True)
    source_document = {"program_id": "urp-000001", "status": "ready", "source_hash": "source-1", "token": "not-indexed"}
    source_document["integrity_hash"] = integrity_hash(source_document)
    source.write_text(json.dumps(source_document), encoding="utf-8")
    original = source.read_bytes()
    migrator = LegacyWorkspaceMigrator(workspace)

    plan = migrator.dry_run()
    assert plan["status"] == "planned"
    assert plan["source_preserved"] is True
    assert not (workspace / "state" / "migrations" / "backups").exists()

    applied = migrator.execute()
    assert applied["status"] == "applied"
    assert applied["imported_workflow_count"] == 1
    record = WorkflowRepository(migrator.database).get("continuity_command_center", "urp-000001")
    assert record is not None and record.status == "ready"
    assert source.read_bytes() == original
    assert migrator.execute()["status"] == "already_applied"
    backup_file = workspace / str(applied["backup_path"]) / source.relative_to(workspace)
    backup_original = backup_file.read_bytes()
    backup_file.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="backup verification"):
        migrator.rollback(str(applied["migration_id"]))
    backup_file.write_bytes(backup_original)
    rolled_back = migrator.rollback(str(applied["migration_id"]))
    assert rolled_back["status"] == "rolled_back"
    assert source.read_bytes() == original


def test_active_v12_state_index_contains_only_public_workflow_metadata(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    report = workspace / "unified-release-programs" / "urp-000001" / "continuity-command-center" / "command-center-report.json"
    report.parent.mkdir(parents=True)
    document = {"program_id": "urp-000001", "status": "ready", "source_hash": "source-hash", "reviewer_notes": "sk-secret"}
    document["integrity_hash"] = integrity_hash(document)
    report.write_text(json.dumps(document), encoding="utf-8")
    assert sync_active_v12_state(workspace) == 1
    database = MusicForgeDatabase.from_workspace(workspace)
    record = WorkflowRepository(database).get("continuity_command_center", "urp-000001")
    assert record is not None and record.payload_hash == document["integrity_hash"]
    assert b"sk-secret" not in database.path.read_bytes()
    document["status"] = "forged"
    report.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RuntimeError, match="integrity failed"):
        sync_active_v12_state(workspace)


def test_legacy_migration_backup_failure_blocks_import_and_cli_supports_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / ".musicforge"
    source = workspace / "urpccca" / "urp-000001" / "state.json"
    source.parent.mkdir(parents=True)
    source.write_text("{}", encoding="utf-8")
    migrator = LegacyWorkspaceMigrator(workspace)
    with pytest.raises(RuntimeError, match="Injected"):
        migrator.execute(fail_after_backup=True)
    with migrator.database.session() as connection:
        assert connection.execute("SELECT COUNT(*) FROM legacy_migrations").fetchone()[0] == 0

    clean_workspace = tmp_path / "clean"
    assert persistence_main(["--workspace", str(clean_workspace), "migrate-plan"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "no_changes"


def test_active_v12_stores_use_cross_process_lock_facade() -> None:
    source_root = Path(__file__).resolve().parents[1] / "song_agent"
    for filename in ACTIVE_V12_STORES:
        source = (source_root / filename).read_text(encoding="utf-8")
        assert "WorkspaceLock" in source, filename
        assert "self.lock = threading.RLock()" not in source, filename
        verifier = source_root / filename.replace(".py", "_verifier.py")
        if verifier.is_file():
            assert "WorkspaceLock" not in verifier.read_text(encoding="utf-8"), verifier.name
    for filename in (
        "unified_release_program_continuity_command_center.py",
        "unified_release_program_continuity_command_center_signoff.py",
        "unified_release_program_continuity_command_center_acceptance.py",
        "unified_release_program_continuity_command_center_acceptance_change.py",
    ):
        assert "on_commit=lambda: sync_active_v12_state" in (source_root / filename).read_text(encoding="utf-8")
