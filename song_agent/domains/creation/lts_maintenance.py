from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.creation.lts_backup import LTSBackupStore
from song_agent.domains.quality.music_acceptance import stable_hash
from song_agent.domains.studio.projectio import read_json, write_json


DEFAULT_MAINTENANCE_ROOT = Path(".musicforge") / "maintenance"
MAINTENANCE_CHECK_PACKAGE_TYPE = "musicforge_lts_maintenance_check_report"
UPGRADE_PREFLIGHT_PACKAGE_TYPE = "musicforge_lts_upgrade_preflight_report"
MIGRATION_STATE_PACKAGE_TYPE = "musicforge_lts_migration_state"
INIT_MIGRATION_ID = "2026-06-24-v10.1-maintenance-state"
MAINTENANCE_PROFILES = {"daily", "weekly", "release", "emergency"}


class LTSMaintenanceError(RuntimeError):
    pass


class LTSMaintenanceStore:
    def __init__(self, repo_root: Path | str | None = None, maintenance_root: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        self.root = Path(maintenance_root).resolve() if maintenance_root else (self.repo_root / DEFAULT_MAINTENANCE_ROOT).resolve()
        self.check_runs_dir = self.root / "check-runs"
        self.preflights_dir = self.root / "upgrade-preflights"
        self.migrations_dir = self.root / "migrations"
        self.backups = LTSBackupStore(self.repo_root, self.root)

    def status(self) -> dict[str, Any]:
        backups = self.backups.list_backups()
        latest_backup = backups[-1] if backups else {}
        migration = self.migration_status()
        git = _git_summary(self.repo_root)
        configs = _config_summary(self.repo_root)
        musicforge = self.repo_root / ".musicforge"
        backup_status = str(latest_backup.get("verification_status") or latest_backup.get("status") or "missing")
        warnings: list[str] = []
        blockers: list[str] = []
        if not musicforge.exists():
            warnings.append(".musicforge is missing.")
        if git.get("state") != "clean":
            warnings.append("Working tree is not clean.")
        if not backups:
            warnings.append("No verified maintenance backup exists.")
        elif backup_status != "passed":
            blockers.append("Latest maintenance backup is not verified.")
        for key, item in configs.items():
            if item.get("tracked"):
                blockers.append(f"{key} is tracked by git.")
        if migration.get("status") == "corrupted":
            blockers.append("Migration state is corrupted.")
        status = "blocked" if blockers else "warning" if warnings else "ready"
        report = {
            "schema_version": 1,
            "package_type": "musicforge_lts_maintenance_status",
            "generated_at": _now(),
            "status": status,
            "version": __version__,
            "git": git,
            "configs": configs,
            "musicforge": {"exists": musicforge.exists(), "size_bytes": _dir_size(musicforge) if musicforge.exists() else 0},
            "backups": {"count": len(backups), "latest": latest_backup},
            "migration": migration,
            "ga": _latest_ga_summary(self.repo_root),
            "checks": {"latest": self.latest_check_report_summary(), "profiles": sorted(MAINTENANCE_PROFILES)},
            "warnings": warnings,
            "blockers": blockers,
        }
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        return report

    def run_upgrade_preflight(
        self,
        *,
        target_version: str,
        require_verified_backup: bool = False,
        allow_dirty: bool = False,
    ) -> dict[str, Any]:
        preflight_id = self._next_id(self.preflights_dir, "up")
        git = _git_summary(self.repo_root)
        configs = _config_summary(self.repo_root)
        backups = self.backups.list_backups()
        latest_backup = backups[-1] if backups else {}
        checks: list[dict[str, Any]] = []
        _add_check(checks, "upgrade.version_order", "passed" if _version_key(__version__) <= _version_key(target_version) else "failed", "blocking", "Current version is not newer than target version.")
        _add_check(checks, "upgrade.git_clean", "passed" if git.get("state") == "clean" or allow_dirty else "failed", "blocking", "Working tree is clean." if git.get("state") == "clean" else "Working tree is dirty.")
        tracked = [key for key, value in configs.items() if value.get("tracked")]
        _add_check(checks, "upgrade.local_configs_untracked", "passed" if not tracked else "failed", "blocking", "Local config files are not tracked by git." if not tracked else "Local config files are tracked by git.", {"tracked": tracked})
        backup_ok = latest_backup.get("verification_status") == "passed"
        backup_status = "passed" if backup_ok or not require_verified_backup else "failed"
        _add_check(checks, "upgrade.verified_backup", backup_status, "blocking" if require_verified_backup else "warning", "A verified backup exists." if backup_ok else "A verified backup is missing.", {"latest_backup_id": latest_backup.get("backup_id")})
        migration = self.migration_status()
        _add_check(checks, "upgrade.migration_state", "passed" if migration.get("status") != "corrupted" else "failed", "blocking", "Migration state is readable." if migration.get("status") != "corrupted" else "Migration state is corrupted.")
        blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
        warnings = [check for check in checks if check.get("status") == "warning" or check.get("severity") == "warning"]
        report = {
            "schema_version": 1,
            "package_type": UPGRADE_PREFLIGHT_PACKAGE_TYPE,
            "preflight_id": preflight_id,
            "generated_at": _now(),
            "current_version": __version__,
            "target_version": target_version,
            "status": "blocked" if blockers else "warning" if warnings else "ready",
            "checks": checks,
            "summary": {"blocker_count": len(blockers), "warning_count": len(warnings), "latest_backup_id": latest_backup.get("backup_id")},
        }
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        write_json(self.preflights_dir / preflight_id / "upgrade-preflight-report.json", report)
        return report

    def list_preflights(self) -> list[dict[str, Any]]:
        if not self.preflights_dir.exists():
            return []
        rows = []
        for path in sorted(self.preflights_dir.glob("up-*")):
            report_path = path / "upgrade-preflight-report.json"
            if report_path.exists():
                rows.append(read_json(report_path))
        return rows

    def migration_status(self) -> dict[str, Any]:
        path = self.migrations_dir / "migration-state.json"
        if not path.exists():
            return {"package_type": MIGRATION_STATE_PACKAGE_TYPE, "schema_version": 1, "status": "empty", "applied": []}
        try:
            state = read_json(path)
        except Exception as exc:
            return {"package_type": MIGRATION_STATE_PACKAGE_TYPE, "schema_version": 1, "status": "corrupted", "error": str(exc), "applied": []}
        applied = state.get("applied") if isinstance(state.get("applied"), list) else []
        state["status"] = "ready"
        state["pending"] = [item for item in self.migration_plan()["pending"] if item["migration_id"] not in {row.get("migration_id") for row in applied}]
        return state

    def migration_plan(self) -> dict[str, Any]:
        applied_ids = {str(row.get("migration_id")) for row in self._read_migration_state().get("applied", []) if isinstance(row, dict)}
        migrations = [{"migration_id": INIT_MIGRATION_ID, "title": "Initialize LTS maintenance state", "destructive": False}]
        pending = [item for item in migrations if item["migration_id"] not in applied_ids]
        return {"schema_version": 1, "status": "pending" if pending else "noop", "pending": pending, "applied_count": len(applied_ids)}

    def run_migrations(self, *, require_backup: bool = False) -> dict[str, Any]:
        if require_backup and not any(item.get("verification_status") == "passed" for item in self.backups.list_backups()):
            raise LTSMaintenanceError("A verified maintenance backup is required before running migrations.")
        state = self._read_migration_state()
        applied = state.setdefault("applied", [])
        applied_ids = {str(row.get("migration_id")) for row in applied if isinstance(row, dict)}
        events: list[dict[str, Any]] = []
        if INIT_MIGRATION_ID not in applied_ids:
            self.root.mkdir(parents=True, exist_ok=True)
            status_doc = self.status()
            write_json(self.root / "maintenance-state.json", {"schema_version": 1, "initialized_at": _now(), "status_hash": status_doc["integrity_hash"]})
            record = {
                "migration_id": INIT_MIGRATION_ID,
                "status": "applied",
                "applied_at": _now(),
                "source_hash": stable_hash({"version": __version__, "migration_id": INIT_MIGRATION_ID}),
                "result_hash": stable_hash({"maintenance_state": "initialized", "status_hash": status_doc["integrity_hash"]}),
                "notes": "Initialized maintenance state.",
            }
            applied.append(record)
            events.append(record)
            self._append_migration_event({"event_type": "migration_applied", **record})
        state.update({"package_type": MIGRATION_STATE_PACKAGE_TYPE, "schema_version": 1, "app_version": __version__, "updated_at": _now()})
        state["integrity_hash"] = stable_hash({key: value for key, value in state.items() if key != "integrity_hash"})
        write_json(self.migrations_dir / "migration-state.json", state)
        return {"status": "applied" if events else "noop", "applied": events, "state": state}

    def run_check(self, *, profile: str = "daily") -> dict[str, Any]:
        profile = str(profile or "daily")
        if profile not in MAINTENANCE_PROFILES:
            raise LTSMaintenanceError(f"Unknown maintenance check profile: {profile}")
        check_id = self._next_id(self.check_runs_dir, "mc")
        checks = self._profile_checks(profile)
        if not checks:
            raise LTSMaintenanceError("Maintenance check profile selected no checks.")
        blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
        warnings = [check for check in checks if check.get("status") == "warning" or check.get("severity") == "warning"]
        report = {
            "schema_version": 1,
            "package_type": MAINTENANCE_CHECK_PACKAGE_TYPE,
            "check_id": check_id,
            "profile": profile,
            "started_at": _now(),
            "finished_at": _now(),
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "checks": checks,
            "artifacts": [],
            "warnings": [check["message"] for check in warnings],
            "blockers": [check["message"] for check in blockers],
        }
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        write_json(self.check_runs_dir / check_id / "maintenance-check-report.json", report)
        return report

    def list_check_runs(self) -> list[dict[str, Any]]:
        if not self.check_runs_dir.exists():
            return []
        rows = []
        for path in sorted(self.check_runs_dir.glob("mc-*")):
            report_path = path / "maintenance-check-report.json"
            if report_path.exists():
                rows.append(read_json(report_path))
        return rows

    def latest_check_report_summary(self) -> dict[str, Any]:
        rows = self.list_check_runs()
        if not rows:
            return {"status": "missing"}
        latest = rows[-1]
        return {"check_id": latest.get("check_id"), "profile": latest.get("profile"), "status": latest.get("status"), "finished_at": latest.get("finished_at")}

    def _profile_checks(self, profile: str) -> list[dict[str, Any]]:
        status = self.status()
        checks = [
            _check("maintenance.status", "passed" if status.get("status") != "blocked" else "failed", "blocking", "Maintenance status has no blockers.", {"status": status.get("status")}),
            _check("maintenance.git_status", "passed" if status.get("git", {}).get("state") == "clean" else "warning", "warning", "Working tree status checked.", status.get("git", {})),
            _check("maintenance.config_ignored", "passed" if not any(value.get("tracked") for value in status.get("configs", {}).values()) else "failed", "blocking", "Local configs are not tracked by git.", status.get("configs", {})),
        ]
        backups = self.backups.list_backups()
        verified_backup = any(item.get("verification_status") == "passed" for item in backups)
        checks.append(_check("maintenance.verified_backup", "passed" if verified_backup else "warning", "warning", "Verified backup exists." if verified_backup else "Verified backup is missing."))
        if profile in {"weekly", "release"}:
            backup = self.backups.create_backup(mode="workspace")
            checks.append(_check("maintenance.backup_create", "passed" if backup.get("verification", {}).get("status") == "passed" else "failed", "blocking", "Workspace backup created and verified.", {"backup_id": backup.get("backup", {}).get("backup_id")}))
        if profile == "release":
            preflight = self.run_upgrade_preflight(target_version=__version__, require_verified_backup=True)
            checks.append(_check("maintenance.upgrade_preflight", "passed" if preflight.get("status") in {"ready", "warning"} else "failed", "blocking", "Upgrade preflight completed.", {"preflight_id": preflight.get("preflight_id"), "status": preflight.get("status")}))
        if profile == "emergency":
            diff = _quick_git(self.repo_root, ["diff", "--check"])
            checks.append(_check("maintenance.git_diff_check", "passed" if not diff else "failed", "blocking", "git diff --check has no errors." if not diff else diff))
        return checks

    def _read_migration_state(self) -> dict[str, Any]:
        path = self.migrations_dir / "migration-state.json"
        if not path.exists():
            return {"package_type": MIGRATION_STATE_PACKAGE_TYPE, "schema_version": 1, "app_version": __version__, "applied": []}
        return read_json(path)

    def _append_migration_event(self, event: dict[str, Any]) -> None:
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        with (self.migrations_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps({"timestamp": _now(), **event}, ensure_ascii=False, sort_keys=True) + "\n")

    def _next_id(self, root: Path, prefix: str) -> str:
        root.mkdir(parents=True, exist_ok=True)
        existing = [int(path.name.removeprefix(f"{prefix}-")) for path in root.glob(f"{prefix}-*") if path.name.removeprefix(f"{prefix}-").isdigit()]
        return f"{prefix}-{(max(existing) + 1) if existing else 1:06d}"


def maintenance_report_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def _check(check_id: str, status: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "status": status, "severity": severity, "message": message, "detail": detail or {}}


def _add_check(checks: list[dict[str, Any]], check_id: str, status: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> None:
    checks.append(_check(check_id, status, severity, message, detail))


def _git_summary(root: Path) -> dict[str, Any]:
    status = _quick_git(root, ["status", "--short", "--branch"])
    lines = [line for line in status.splitlines() if line.strip()]
    branch = lines[0] if lines else ""
    dirty = any(not line.startswith("## ") for line in lines)
    return {"state": "dirty" if dirty else "clean" if status else "unknown", "branch": branch, "head": _quick_git(root, ["rev-parse", "HEAD"]), "dirty": dirty}


def _config_summary(root: Path) -> dict[str, dict[str, Any]]:
    config_paths = {
        "provider": ".musicforge/provider.json",
        "renderer": ".musicforge/renderer.json",
        "edit_presets": ".musicforge/edit-presets.json",
        "prompt_templates": ".musicforge/prompt-templates.json",
    }
    tracked = set(_quick_git(root, ["ls-files", ".musicforge/provider.json", ".musicforge/renderer.json", ".musicforge/edit-presets.json", ".musicforge/prompt-templates.json"]).splitlines())
    result = {}
    for key, rel in config_paths.items():
        path = root / rel
        result[key] = {"path": rel, "exists": path.exists(), "tracked": rel in tracked, "status": "tracked" if rel in tracked else "local" if path.exists() else "missing"}
    return result


def _latest_ga_summary(root: Path) -> dict[str, Any]:
    path = root / "runs" / "ga-readiness" / "ga-readiness-report.json"
    if not path.exists():
        return {"status": "missing"}
    try:
        report = read_json(path)
        return {"status": report.get("status", "unknown"), "generated_at": report.get("generated_at"), "integrity_hash": report.get("integrity_hash")}
    except Exception as exc:
        return {"status": "unreadable", "error": str(exc)}


def _dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def _version_key(value: str) -> tuple[int, ...]:
    text = str(value or "").strip().lower().removeprefix("v")
    parts: list[int] = []
    for part in text.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _quick_git(root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except Exception:
        return ""
    return (completed.stdout or completed.stderr or "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
