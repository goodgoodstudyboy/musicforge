from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zipfile
import shutil
from pathlib import Path

import pytest

from song_agent.persistence_cli import main as persistence_main
from song_agent.release_check_persistence_kernel import run_program_persistence_authority_smoke
from song_agent.platform.persistence import (
    FileUnitOfWork,
    LegacyWorkspaceMigrator,
    MusicForgeDatabase,
    PersistenceRecovery,
    ProgramPersistenceError,
    ProgramStateRepository,
    WorkflowRepository,
    WorkspaceLock,
    V13MigrationOrchestrator,
    migration_anchor_path,
    verify_v13_migration_evidence,
)
from song_agent.platform.persistence.repository import sync_active_v12_state
from song_agent.platform.verification.hashing import integrity_hash, sha256_bytes


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


def test_v133_program_persistence_authority_smoke() -> None:
    ok, detail = run_program_persistence_authority_smoke(Path(__file__).resolve().parents[1])

    assert ok is True, detail


def test_database_wal_schema_repository_and_optimistic_concurrency(tmp_path: Path) -> None:
    database = MusicForgeDatabase.from_workspace(tmp_path)
    database.initialize()

    with database.session() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert database.schema_version() == 3

    repository = WorkflowRepository(database)
    first = repository.save("command_center", "cc-1", generation=1, status="draft", expected_version=0)
    second = repository.save("command_center", "cc-1", generation=1, status="ready", expected_version=first.version)
    assert second.version == 2
    assert repository.get("command_center", "cc-1") == second
    with pytest.raises(RuntimeError, match="concurrently"):
        repository.save("command_center", "cc-1", generation=2, status="stale", expected_version=1)
    assert repository.next_id("review", prefix="review-") == "review-000001"
    assert repository.next_id("review", prefix="review-") == "review-000002"


def test_program_repository_is_authority_and_projection_tamper_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    path = workspace / "unified-release-programs" / "urp-000001" / "program-report.json"
    repository = ProgramStateRepository(workspace)
    document = {"program_id": "urp-000001", "status": "ready", "generation": 2}

    repository.write_projection(path, document)
    assert repository.read_projection(path) == document
    aggregate = repository.aggregate("urp-000001")
    assert aggregate.components["program"][0].version == 1
    with repository.database.session() as connection:
        assert connection.execute("SELECT COUNT(*) FROM program_document_events").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM program_document_index").fetchone()[0] == 1
    path.write_text('{"status":"forged"}\n', encoding="utf-8")
    with pytest.raises(ProgramPersistenceError, match="differs from repository authority"):
        repository.read_projection(path)


@pytest.mark.parametrize("stage", ["after_event_append_before_projection", "after_projection_before_index"])
def test_program_repository_recovers_projection_transaction_boundaries(tmp_path: Path, stage: str) -> None:
    workspace = tmp_path / ".musicforge"
    path = workspace / "unified-release-programs" / "urp-000001" / "continuity" / "readiness.json"
    repository = ProgramStateRepository(workspace)

    def crash(current: str) -> None:
        if current == stage:
            raise RuntimeError(f"crash:{stage}")

    document = {"program_id": "urp-000001", "status": "ready", "generation": 3}
    with pytest.raises(RuntimeError, match="crash"):
        repository.write_projection(path, document, crash_hook=crash)
    recovered = PersistenceRecovery(workspace).recover()["program_recovered"]
    assert len(recovered) == 1
    assert repository.read_projection(path) == document
    with repository.database.session() as connection:
        row = connection.execute("SELECT status FROM program_projection_transactions").fetchone()
        assert row[0] == "committed"
        assert connection.execute("SELECT current_version FROM program_document_index").fetchone()[0] == 1


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


def test_persistence_recovery_rejects_resigned_invalid_file_ledger(tmp_path: Path) -> None:
    def crash(stage: str) -> None:
        if stage == "after_generation":
            raise RuntimeError("crash")

    unit = FileUnitOfWork(tmp_path, "command-center", transaction_id="tx-invalid-ledger", crash_hook=crash)
    unit.write_json("state.json", {"status": "ready"})
    with pytest.raises(RuntimeError, match="crash"):
        unit.commit()
    intent_path = unit.artifacts.intent_path(unit.transaction_id)
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    intent["files"] = "forged"
    intent_path.write_text(json.dumps(intent), encoding="utf-8")

    with pytest.raises(RuntimeError, match="file ledger is invalid"):
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


def test_legacy_migration_imports_only_program_roots(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    unrelated = workspace / "other-domain" / "report.json"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text('{"status":"ready"}', encoding="utf-8")

    applied = LegacyWorkspaceMigrator(workspace, legacy_roots=("other-domain",)).execute()

    assert applied["status"] == "applied"
    assert applied["imported_program_document_count"] == 0
    with MusicForgeDatabase.from_workspace(workspace).session() as connection:
        assert connection.execute("SELECT COUNT(*) FROM program_documents").fetchone()[0] == 0


def test_legacy_migration_rollback_rejects_changed_program_authority(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    source = workspace / "unified-release-programs" / "urp-000001" / "program-report.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"program_id":"urp-000001","status":"ready"}', encoding="utf-8")
    migrator = LegacyWorkspaceMigrator(workspace)
    applied = migrator.execute()
    ProgramStateRepository(workspace).write_projection(
        source,
        {"program_id": "urp-000001", "status": "changed"},
    )

    with pytest.raises(RuntimeError, match="changed after import"):
        migrator.rollback(str(applied["migration_id"]))

    with migrator.database.session() as connection:
        row = connection.execute(
            "SELECT status FROM legacy_migrations WHERE migration_id=?",
            (applied["migration_id"],),
        ).fetchone()
    assert row["status"] == "applied"


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


def test_v13_migration_requires_verified_backup_rehearses_rollback_and_archives_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    source = workspace / "unified-release-programs" / "urp-000001" / "program-report.json"
    source.parent.mkdir(parents=True)
    document = {"program_id": "urp-000001", "status": "ready", "reviewer_note": "sk-private-not-exported"}
    document["integrity_hash"] = integrity_hash(document)
    source.write_text(json.dumps(document), encoding="utf-8")
    original = source.read_bytes()
    migration = V13MigrationOrchestrator(workspace)

    plan = migration.dry_run()
    rehearsal = migration.rollback_rehearsal()
    report = migration.execute()
    archive, verification = migration.build_evidence_archive(plan, report, rehearsal, tmp_path / "v13-migration.zip")

    assert plan["verified_backup_required"] is True
    assert rehearsal["status"] == "passed"
    assert report["status"] == "passed"
    assert report["verified_backup"] is True
    assert len(report["target_hash"]) == 64
    assert report["rollback_command"].startswith("song-agent-state migrate-rollback ")
    assert source.read_bytes() == original
    assert verification["status"] == "passed"
    assert b"sk-private-not-exported" not in archive.read_bytes()
    anchor = migration_anchor_path(archive)
    assert anchor.is_file()

    archive_without_anchor = tmp_path / "v13-migration-without-anchor.zip"
    archive_without_anchor.write_bytes(archive.read_bytes())
    missing_anchor = verify_v13_migration_evidence(archive_without_anchor, require_anchor=True)
    assert missing_anchor["status"] == "failed"
    assert "v13_migration_anchor_exists" in missing_anchor["blockers"]

    semantic_tamper = tmp_path / "v13-migration-semantic-tamper.zip"
    with zipfile.ZipFile(archive) as source_archive:
        entries = {info.filename: source_archive.read(info.filename) for info in source_archive.infolist()}
    tampered_report = json.loads(entries["migration-report.json"])
    tampered_report["source_hash"] = "f" * 64
    tampered_report["integrity_hash"] = integrity_hash(tampered_report)
    entries["migration-report.json"] = (json.dumps(tampered_report, indent=2, sort_keys=True) + "\n").encode()
    manifest = json.loads(entries["manifest.json"])
    report_row = next(row for row in manifest["files"] if row["path"] == "migration-report.json")
    report_row.update({"sha256": sha256_bytes(entries["migration-report.json"]), "size_bytes": len(entries["migration-report.json"])})
    manifest["integrity_hash"] = integrity_hash(manifest)
    entries["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    with zipfile.ZipFile(semantic_tamper, "w", compression=zipfile.ZIP_DEFLATED) as target_archive:
        for name, data in entries.items():
            target_archive.writestr(name, data)
    semantic_verification = verify_v13_migration_evidence(
        semantic_tamper,
        anchor_path=anchor,
        require_anchor=True,
    )
    assert semantic_verification["status"] == "failed"
    assert "v13_migration_source_hashes_match" in semantic_verification["blockers"]

    full_resign = tmp_path / "v13-migration-full-resign.zip"
    resigned_entries = dict(entries)
    resigned_report = json.loads(resigned_entries["migration-report.json"])
    resigned_report["source_hash"] = plan["source_hash"]
    resigned_report["target_hash"] = "e" * 64
    resigned_report["integrity_hash"] = integrity_hash(resigned_report)
    resigned_entries["migration-report.json"] = (json.dumps(resigned_report, indent=2, sort_keys=True) + "\n").encode()
    resigned_manifest = json.loads(resigned_entries["manifest.json"])
    resigned_row = next(row for row in resigned_manifest["files"] if row["path"] == "migration-report.json")
    resigned_row.update({"sha256": sha256_bytes(resigned_entries["migration-report.json"]), "size_bytes": len(resigned_entries["migration-report.json"])})
    resigned_manifest["integrity_hash"] = integrity_hash(resigned_manifest)
    resigned_entries["manifest.json"] = (json.dumps(resigned_manifest, indent=2, sort_keys=True) + "\n").encode()
    with zipfile.ZipFile(full_resign, "w", compression=zipfile.ZIP_DEFLATED) as target_archive:
        for name, data in resigned_entries.items():
            target_archive.writestr(name, data)
    resigned_verification = verify_v13_migration_evidence(full_resign, anchor_path=anchor, require_anchor=True)
    assert resigned_verification["status"] == "failed"
    assert {
        "v13_migration_anchor_target_hash",
        "v13_migration_anchor_archive_hash",
    } <= set(resigned_verification["blockers"])

    archive.write_bytes(archive.read_bytes() + b"tamper")
    assert verify_v13_migration_evidence(archive, anchor_path=anchor, require_anchor=True)["status"] == "failed"


def test_v1213_representative_workspace_migrates_and_rolls_back_bit_identical(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "v12_13_program_workspace" / "workspace"
    workspace = tmp_path / ".musicforge"
    shutil.copytree(fixture, workspace)
    before = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for root_name in ("unified-release-programs", "urpccca")
        for path in sorted((workspace / root_name).rglob("*"))
        if path.is_file()
    }
    migration = V13MigrationOrchestrator(workspace)

    plan = migration.dry_run()
    rehearsal = migration.rollback_rehearsal()
    report = migration.execute()
    aggregate = ProgramStateRepository(workspace).aggregate("urp-000001")
    rolled_back = migration.migrator.rollback(str(report["migration_id"]))
    after = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for root_name in ("unified-release-programs", "urpccca")
        for path in sorted((workspace / root_name).rglob("*"))
        if path.is_file()
    }

    assert plan["file_count"] == 6
    assert report["imported_program_document_count"] == 6
    assert rehearsal["status"] == "passed" and rehearsal["source_restored"] is True
    assert {"program", "handoff", "vault", "continuity", "receiver_acceptance", "change_control"} <= set(aggregate.components)
    assert rolled_back["status"] == "rolled_back"
    assert after == before


def test_v13_migration_cli_plan_and_rehearsal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / ".musicforge"

    assert persistence_main(["--workspace", str(workspace), "v13-plan"]) == 0
    assert json.loads(capsys.readouterr().out)["package_type"] == "musicforge_v13_migration_plan"
    assert persistence_main(["--workspace", str(workspace), "v13-rollback-rehearsal"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
