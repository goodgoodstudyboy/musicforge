from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from song_agent.platform.persistence import (
    FileUnitOfWork,
    LegacyWorkspaceMigrator,
    MusicForgeDatabase,
    PersistenceRecovery,
    WorkflowRepository,
)
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


def run_persistence_kernel_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        with tempfile.TemporaryDirectory(prefix="mf-v1217-persistence-") as temp:
            workspace = Path(temp) / ".musicforge"
            database = MusicForgeDatabase.from_workspace(workspace)
            database.initialize()
            with database.session() as connection:
                wal = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
                foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) == 1

            repository = WorkflowRepository(database)
            first = repository.save("command_center", "cc-1", generation=1, status="draft", expected_version=0)
            optimistic_conflict = False
            try:
                repository.save("command_center", "cc-1", generation=1, status="ready", expected_version=0)
            except RuntimeError:
                optimistic_conflict = True

            root_path = workspace / "unified-release-programs"
            code = (
                "from song_agent.unified_release_program import UnifiedReleaseProgramStore;"
                "import pathlib,sys;"
                "print(UnifiedReleaseProgramStore(root=pathlib.Path(sys.argv[1])).create_program({})['program_id'])"
            )
            processes = [
                subprocess.Popen([sys.executable, "-c", code, str(root_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(2)
            ]
            outputs = [process.communicate(timeout=30) for process in processes]
            cross_process = [process.returncode for process in processes] == [0, 0] and sorted(row[0].strip() for row in outputs) == ["urp-000001", "urp-000002"]

            crash_recovery = True
            for stage in ("after_generation", "after_pointer", "before_database_commit", "after_database_commit"):
                transaction_id = f"tx-{stage}"

                def crash(current: str, expected: str = stage) -> None:
                    if current == expected:
                        raise RuntimeError(expected)

                unit = FileUnitOfWork(workspace, f"artifact-{stage}", transaction_id=transaction_id, crash_hook=crash)
                unit.write_json("state.json", {"status": "ready"})
                try:
                    unit.commit()
                except RuntimeError:
                    pass
                report = PersistenceRecovery(workspace).recover()
                crash_recovery = crash_recovery and transaction_id in report["recovered"]

            corrupt = FileUnitOfWork(workspace, "corrupt", transaction_id="tx-corrupt", crash_hook=lambda stage: (_ for _ in ()).throw(RuntimeError(stage)) if stage == "after_pointer" else None)
            corrupt.write_json("state.json", {"status": "ready"})
            try:
                corrupt.commit()
            except RuntimeError:
                pass
            (corrupt.artifacts.generation_dir("corrupt", "tx-corrupt") / "state.json").write_text("tampered", encoding="utf-8")
            corrupt_recovery_blocked = False
            try:
                PersistenceRecovery(workspace).recover()
            except RuntimeError:
                corrupt_recovery_blocked = True

            legacy = workspace / "urpccca" / "urp-000001" / "state.json"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy_document = {"program_id": "urp-000001", "status": "signed", "api_key": "not-indexed-secret"}
            legacy_document["integrity_hash"] = integrity_hash(legacy_document)
            legacy.write_text(json.dumps(legacy_document), encoding="utf-8")
            original = legacy.read_bytes()
            migrator = LegacyWorkspaceMigrator(workspace)
            plan = migrator.dry_run()
            applied = migrator.execute()
            idempotent = migrator.execute()
            rollback = migrator.rollback(str(applied["migration_id"]))
            migration = plan["status"] == "planned" and applied["status"] == "applied" and idempotent["status"] == "already_applied" and rollback["status"] == "rolled_back" and legacy.read_bytes() == original
            secret_not_indexed = b"not-indexed-secret" not in database.path.read_bytes()

        source_root = Path(__file__).resolve().parent
        stores_migrated = all(
            "WorkspaceLock" in (source_root / filename).read_text(encoding="utf-8")
            and "self.lock = threading.RLock()" not in (source_root / filename).read_text(encoding="utf-8")
            for filename in ACTIVE_V12_STORES
        )
        signals = {
            "wal": wal,
            "foreign_keys": foreign_keys,
            "optimistic_conflict": optimistic_conflict,
            "cross_process": cross_process,
            "crash_recovery": crash_recovery,
            "corrupt_recovery_blocked": corrupt_recovery_blocked,
            "migration": migration,
            "secret_not_indexed": secret_not_indexed,
            "active_stores_migrated": stores_migrated,
            "repository_version": first.version == 1,
        }
        return all(signals.values()), "v12.17 persistence kernel: " + ", ".join(f"{key}={value}" for key, value in signals.items())
    except Exception as exc:
        return False, f"v12.17 Persistence Kernel smoke failed: {exc}"
