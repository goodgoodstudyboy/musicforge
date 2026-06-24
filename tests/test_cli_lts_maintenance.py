from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", "")}


def _repo(root: Path) -> None:
    (root / ".musicforge" / "projects" / "project-001").mkdir(parents=True)
    (root / ".musicforge" / "projects" / "project-001" / "project.json").write_text('{"project_id":"project-001"}\n', encoding="utf-8")


def _repo_with_secret(root: Path) -> None:
    (root / ".musicforge" / "projects" / "project-001").mkdir(parents=True)
    (root / ".musicforge" / "projects" / "project-001" / "project.json").write_text('{"note":"Bearer sk-cli-secret"}\n', encoding="utf-8")


def test_maintenance_cli_status_backup_verify_restore_plan(tmp_path: Path) -> None:
    _repo(tmp_path)

    status = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "status", "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)
    create = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "backup", "create", "--mode", "workspace", "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)
    created = json.loads(create.stdout)
    backup_id = created["backup"]["backup_id"]
    verify = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "backup", "verify", "--backup-id", backup_id, "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)
    plan = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "backup", "restore-plan", "--backup-id", backup_id, "--target", str(tmp_path / "restore"), "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)
    zip_path = tmp_path / ".musicforge" / "maintenance" / "backups" / backup_id / "musicforge-maintenance-backup.zip"
    offline = subprocess.run([sys.executable, "-m", "song_agent.cli", "verify-maintenance-backup", str(zip_path), "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)

    assert status.returncode == 0, status.stderr
    assert create.returncode == 0, create.stderr
    assert verify.returncode == 0, verify.stderr
    assert plan.returncode == 0, plan.stderr
    assert offline.returncode == 0, offline.stderr
    assert json.loads(status.stdout)["package_type"] == "musicforge_lts_maintenance_status"
    assert json.loads(verify.stdout)["verification"]["status"] == "passed"
    assert json.loads(plan.stdout)["restore_plan"]["status"] == "ready"
    assert json.loads(offline.stdout)["status"] == "passed"


def test_maintenance_cli_migration_and_check(tmp_path: Path) -> None:
    _repo(tmp_path)

    migration = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "migration", "run", "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)
    check = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "check", "run", "--profile", "daily", "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)

    assert migration.returncode == 0, migration.stderr
    assert check.returncode == 0, check.stderr
    assert json.loads(migration.stdout)["status"] == "applied"
    assert json.loads(check.stdout)["report"]["status"] in {"passed", "warning"}


def test_maintenance_cli_backup_create_failed_verification_exits_nonzero(tmp_path: Path) -> None:
    _repo_with_secret(tmp_path)

    create = subprocess.run([sys.executable, "-m", "song_agent.cli", "maintenance", "backup", "create", "--mode", "workspace", "--json"], cwd=tmp_path, env=_env(), text=True, capture_output=True)
    payload = json.loads(create.stdout)

    assert create.returncode == 1
    assert payload["status"] == "failed"
    assert payload["verification"]["status"] == "failed"
    assert payload["backup"]["verification_status"] == "failed"
