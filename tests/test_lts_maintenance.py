from __future__ import annotations

import subprocess
from pathlib import Path

from song_agent import __version__
from song_agent.lts_maintenance import LTSMaintenanceStore, maintenance_report_integrity_ok


def _git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (root / ".gitignore").write_text(".musicforge/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, capture_output=True, text=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, text=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, text=True, check=True)
    subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=root, capture_output=True, text=True, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, capture_output=True, text=True, check=True)


def _workspace(root: Path) -> None:
    (root / ".musicforge" / "projects" / "project-001").mkdir(parents=True)
    (root / ".musicforge" / "projects" / "project-001" / "project.json").write_text('{"project_id":"project-001"}\n', encoding="utf-8")


def test_lts_maintenance_status_backup_preflight_and_checks(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    _workspace(tmp_path)
    store = LTSMaintenanceStore(tmp_path)

    status_before = store.status()
    backup = store.backups.create_backup(mode="workspace")
    status_after = store.status()
    preflight = store.run_upgrade_preflight(target_version=__version__, require_verified_backup=True)
    daily = store.run_check(profile="daily")

    assert status_before["package_type"] == "musicforge_lts_maintenance_status"
    assert backup["verification"]["status"] == "passed"
    assert status_after["backups"]["count"] == 1
    assert preflight["status"] in {"ready", "warning"}
    assert daily["status"] in {"passed", "warning"}
    assert maintenance_report_integrity_ok(daily)


def test_lts_migration_registry_is_idempotent(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    _workspace(tmp_path)
    store = LTSMaintenanceStore(tmp_path)

    plan = store.migration_plan()
    first = store.run_migrations()
    second = store.run_migrations()
    status = store.migration_status()

    assert plan["status"] == "pending"
    assert first["status"] == "applied"
    assert second["status"] == "noop"
    assert status["status"] == "ready"
    assert len(status["applied"]) == 1


def test_restore_plan_is_dry_run_until_confirm(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    _workspace(tmp_path)
    store = LTSMaintenanceStore(tmp_path)
    created = store.backups.create_backup(mode="workspace")
    backup_id = created["backup"]["backup_id"]
    target = tmp_path / "restore-target"

    plan = store.backups.restore_plan(backup_id=backup_id, target=target)
    result = store.backups.restore(backup_id=backup_id, target=target, confirm=False)

    assert plan["status"] == "ready"
    assert result["status"] == "planned"
    assert not (target / ".musicforge").exists()
