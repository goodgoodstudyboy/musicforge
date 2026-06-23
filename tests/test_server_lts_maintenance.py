from __future__ import annotations

from pathlib import Path

from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _workspace(root: Path) -> None:
    (root / ".musicforge" / "projects" / "project-001").mkdir(parents=True)
    (root / ".musicforge" / "projects" / "project-001" / "project.json").write_text('{"project_id":"project-001"}\n', encoding="utf-8")


def test_server_lts_maintenance_routes(tmp_path: Path, monkeypatch) -> None:
    _workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status_code, status = request_json(server, "GET", "/api/maintenance/status")
        assert status_code == 200
        assert status["status"]["package_type"] == "musicforge_lts_maintenance_status"

        create_code, created = request_json(server, "POST", "/api/maintenance/backups", {"mode": "workspace"})
        assert create_code == 201
        backup_id = created["backup"]["backup_id"]

        list_code, listing = request_json(server, "GET", "/api/maintenance/backups")
        assert list_code == 200
        assert listing["summary"]["count"] == 1

        verify_code, verified = request_json(server, "POST", f"/api/maintenance/backups/{backup_id}/verify")
        assert verify_code == 200
        assert verified["verification"]["status"] == "passed"

        plan_code, plan = request_json(server, "POST", f"/api/maintenance/backups/{backup_id}/restore-plan", {"target": str(tmp_path / "restore")})
        assert plan_code == 200
        assert plan["restore_plan"]["status"] == "ready"

        preflight_code, preflight = request_json(server, "POST", "/api/maintenance/upgrade/preflight", {"target_version": "10.1.0", "require_verified_backup": True, "allow_dirty": True})
        assert preflight_code == 201
        assert preflight["preflight"]["status"] in {"ready", "warning"}

        migration_code, migration = request_json(server, "POST", "/api/maintenance/migrations", {"require_backup": False})
        assert migration_code == 201
        assert migration["status"] in {"applied", "noop"}

        check_code, check = request_json(server, "POST", "/api/maintenance/checks", {"profile": "daily"})
        assert check_code == 201
        assert check["report"]["status"] in {"passed", "warning"}
    finally:
        stop_test_server(server)
