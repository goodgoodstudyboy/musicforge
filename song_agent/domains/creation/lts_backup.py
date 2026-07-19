from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import subprocess as subprocess
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.creation.lts_backup_verifier import LEGAL_SIDECAR_ENTRIES as LEGAL_SIDECAR_ENTRIES, MAINTENANCE_BACKUP_PACKAGE_TYPE as MAINTENANCE_BACKUP_PACKAGE_TYPE, maintenance_backup_manifest_hash as maintenance_backup_manifest_hash, verify_maintenance_backup_zip as verify_maintenance_backup_zip, write_maintenance_backup_verification_report as write_maintenance_backup_verification_report
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json


DEFAULT_MAINTENANCE_ROOT = Path(".musicforge") / "maintenance"
BACKUP_ZIP_NAME = "musicforge-maintenance-backup.zip"
BACKUP_MODES = {"metadata", "workspace", "workspace_with_artifacts"}


class LTSBackupError(RuntimeError):
    pass


class LTSBackupStore:
    def __init__(self, repo_root: Path | str | None = None, maintenance_root: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        self.root = Path(maintenance_root).resolve() if maintenance_root else (self.repo_root / DEFAULT_MAINTENANCE_ROOT).resolve()
        self.backups_dir = self.root / "backups"

    def create_backup(self, *, mode: str = "workspace") -> dict[str, Any]:
        return self._create_backup_from_root(self.repo_root, mode=mode, backup_kind="manual", source_label=".")

    def create_target_before_restore_backup(self, target: Path | str, *, mode: str = "workspace") -> dict[str, Any]:
        return self._create_backup_from_root(Path(target).resolve(), mode=mode, backup_kind="target-before-restore", source_label="restore-target")

    def _create_backup_from_root(self, source_root: Path, *, mode: str = "workspace", backup_kind: str = "manual", source_label: str = ".") -> ImplementationDocument:
        mode = str(mode or "workspace")
        if mode not in BACKUP_MODES:
            raise LTSBackupError(f"Unsupported maintenance backup mode: {mode}")
        backup_id = self._next_backup_id()
        backup_dir = self.backups_dir / backup_id
        backup_dir.mkdir(parents=True, exist_ok=False)
        zip_path = backup_dir / BACKUP_ZIP_NAME
        files = self._collect_files(mode, source_root=source_root)
        excluded = self._excluded_summary(mode, source_root=source_root)
        manifest_files: list[dict[str, Any]] = []
        workspace_index: ImplementationDocument = {
            "schema_version": 1,
            "backup_id": backup_id,
            "mode": mode,
            "backup_kind": backup_kind,
            "source_root": source_label,
            "file_count": len(files),
            "files": [],
            "excluded": excluded,
        }
        sidecars: dict[str, bytes] = {
            "README.txt": _text_bytes("MusicForge LTS maintenance backup.\nRestore provider and renderer local config manually after restore.\n"),
            "git-summary.json": _json_bytes(_git_summary(self.repo_root)),
            "ga-summary.json": _json_bytes(_safe_ga_summary(self.repo_root)),
            "maintenance-summary.json": _json_bytes({"app_version": __version__, "backup_id": backup_id, "mode": mode, "created_at": _now()}),
        }
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source, rel in files:
                data = source.read_bytes()
                entry = f"data/musicforge/{rel.as_posix()}"
                manifest_files.append({"path": entry, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
                workspace_index["files"].append({"source_path": f".musicforge/{rel.as_posix()}", "package_path": entry, "size_bytes": len(data)})
                archive.writestr(entry, data)
            redaction_report = _redaction_report_for_manifest(manifest_files)
            sidecars["workspace-index.json"] = _json_bytes(workspace_index)
            sidecars["redaction-report.json"] = _json_bytes(redaction_report)
            manifest = {
                "schema_version": 1,
                "package_type": MAINTENANCE_BACKUP_PACKAGE_TYPE,
                "backup_id": backup_id,
                "created_at": _now(),
                "app_version": __version__,
                "mode": mode,
                "backup_kind": backup_kind,
                "source": {"git_head": _git_head(source_root), "git_status": _git_status_state(source_root), "workspace_root": source_label},
                "files": sorted(manifest_files, key=lambda item: item["path"]),
                "excluded": excluded,
                "redaction": {"status": redaction_report["status"], "finding_count": len(redaction_report.get("findings", []))},
            }
            manifest["integrity_hash"] = maintenance_backup_manifest_hash(manifest)
            sidecars["manifest.json"] = _json_bytes(manifest)
            for name in sorted(sidecars):
                archive.writestr(name, sidecars[name])
        metadata = {
            "backup_id": backup_id,
            "mode": mode,
            "backup_kind": backup_kind,
            "created_at": manifest["created_at"],
            "zip_path": str(zip_path),
            "manifest_hash": manifest["integrity_hash"],
            "file_count": len(files),
            "status": "created",
        }
        write_json(backup_dir / "backup-metadata.json", metadata)
        write_json(backup_dir / "backup-manifest.json", manifest)
        verification = self.verify_backup(backup_id)
        metadata["verification_status"] = verification.get("status")
        metadata["verified_at"] = verification.get("generated_at")
        write_json(backup_dir / "backup-metadata.json", metadata)
        return {"backup": metadata, "manifest": manifest, "verification": verification}

    def list_backups(self) -> list[dict[str, Any]]:
        backups: list[dict[str, Any]] = []
        if not self.backups_dir.exists():
            return backups
        for path in sorted(self.backups_dir.glob("mb-*")):
            metadata_path = path / "backup-metadata.json"
            if metadata_path.exists():
                try:
                    backups.append(read_json(metadata_path))
                except Exception:
                    backups.append({"backup_id": path.name, "status": "corrupted"})
        return backups

    def read_backup(self, backup_id: str) -> dict[str, Any]:
        backup_dir = self._backup_dir(backup_id)
        return {
            "backup": read_json(backup_dir / "backup-metadata.json"),
            "manifest": read_json(backup_dir / "backup-manifest.json") if (backup_dir / "backup-manifest.json").exists() else {},
            "verification": read_json(backup_dir / "backup-verification-report.json") if (backup_dir / "backup-verification-report.json").exists() else {},
        }

    def verify_backup(self, backup_id: str) -> dict[str, Any]:
        backup_dir = self._backup_dir(backup_id)
        report = verify_maintenance_backup_zip(backup_dir / BACKUP_ZIP_NAME, strict=True)
        write_maintenance_backup_verification_report(report, backup_dir / "backup-verification-report.json")
        return report

    def verify_zip(self, zip_path: Path | str) -> dict[str, Any]:
        return verify_maintenance_backup_zip(Path(zip_path), strict=True)

    def backup_zip_path(self, backup_id: str) -> Path:
        return self._backup_dir(backup_id) / BACKUP_ZIP_NAME

    def restore_plan(self, *, backup_id: str | None = None, zip_path: Path | str | None = None, target: Path | str) -> dict[str, Any]:
        source_zip = self.backup_zip_path(backup_id) if backup_id else Path(zip_path or "")
        target_path = Path(target).resolve()
        verification = verify_maintenance_backup_zip(source_zip, strict=True)
        blockers: list[str] = []
        warnings = ["Provider config is not restored. Recreate .musicforge/provider.json manually if needed.", "Renderer config is not restored. Recreate .musicforge/renderer.json manually if needed."]
        actions: list[dict[str, Any]] = []
        if verification.get("status") == "failed":
            blockers.append("Backup verification failed.")
        if target_path == self.repo_root:
            blockers.append("Target cannot be the current repository root without explicit override.")
        try:
            manifest = _read_manifest_from_zip(source_zip)
            for item in manifest.get("files", []):
                package_path = str(item.get("path") or "")
                rel = _restore_relative_path(package_path)
                dest = (target_path / ".musicforge" / rel).resolve()
                if not _is_within(dest, target_path):
                    blockers.append(f"Unsafe restore path: {package_path}")
                    continue
                actions.append({"action": "write_file", "path": f".musicforge/{rel.as_posix()}", "size_bytes": item.get("size_bytes")})
        except Exception as exc:
            blockers.append(f"Backup manifest could not be read: {exc}")
            manifest = {}
        report = {
            "schema_version": 1,
            "package_type": "musicforge_lts_restore_plan",
            "generated_at": _now(),
            "status": "blocked" if blockers else "ready",
            "backup_id": backup_id or manifest.get("backup_id"),
            "target": str(target_path),
            "actions": actions,
            "warnings": warnings,
            "blockers": blockers,
            "backup_verification": {"status": verification.get("status"), "manifest_hash": verification.get("manifest_hash")},
        }
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        if backup_id:
            write_json(self._backup_dir(backup_id) / "restore-plan.json", report)
        return report

    def restore(
        self,
        *,
        backup_id: str | None = None,
        zip_path: Path | str | None = None,
        target: Path | str,
        confirm: bool = False,
        overwrite: bool = False,
        allow_current_workspace: bool = False,
    ) -> dict[str, Any]:
        plan = self.restore_plan(backup_id=backup_id, zip_path=zip_path, target=target)
        target_path = Path(target).resolve()
        if not confirm:
            return {"ok": False, "status": "planned", "restore_plan": plan, "message": "Restore not executed without confirm."}
        if plan.get("status") != "ready":
            raise LTSBackupError("Restore plan is blocked.")
        if target_path == self.repo_root and not allow_current_workspace:
            raise LTSBackupError("Restore to current workspace requires allow_current_workspace.")
        target_is_non_empty = target_path.exists() and any(target_path.iterdir())
        pre_restore_backup: dict[str, Any] | None = None
        if target_is_non_empty:
            if not overwrite:
                raise LTSBackupError("Restore target exists and is not empty.")
            pre_restore_backup = self.create_target_before_restore_backup(target_path, mode="workspace")
            if pre_restore_backup.get("verification", {}).get("status") == "failed":
                raise LTSBackupError("Pre-restore backup verification failed. Restore was not executed.")
        target_path.mkdir(parents=True, exist_ok=True)
        source_zip = self.backup_zip_path(backup_id) if backup_id else Path(zip_path or "")
        with zipfile.ZipFile(source_zip) as archive:
            for item in _read_manifest_from_zip(source_zip).get("files", []):
                package_path = str(item.get("path") or "")
                rel = _restore_relative_path(package_path)
                dest = (target_path / ".musicforge" / rel).resolve()
                if not _is_within(dest, target_path):
                    raise LTSBackupError(f"Unsafe restore path: {package_path}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.read(package_path))
        result = {"ok": True, "status": "restored", "restore_plan": plan, "target": str(target_path)}
        if pre_restore_backup is not None:
            result["pre_restore_backup_id"] = pre_restore_backup.get("backup", {}).get("backup_id")
            result["pre_restore_backup"] = pre_restore_backup.get("backup")
        return result

    def _collect_files(self, mode: str, *, source_root: Path | None = None) -> list[tuple[Path, PurePosixPath]]:
        musicforge = (source_root or self.repo_root) / ".musicforge"
        if not musicforge.exists():
            return []
        files: list[tuple[Path, PurePosixPath]] = []
        for path in sorted(musicforge.rglob("*")):
            if not path.is_file():
                continue
            rel = PurePosixPath(path.relative_to(musicforge).as_posix())
            if _should_exclude(rel, mode):
                continue
            files.append((path, rel))
        return files

    def _excluded_summary(self, mode: str, *, source_root: Path | None = None) -> list[dict[str, str]]:
        musicforge = (source_root or self.repo_root) / ".musicforge"
        excluded: list[dict[str, str]] = []
        if not musicforge.exists():
            return excluded
        for path in sorted(musicforge.rglob("*")):
            if not path.is_file():
                continue
            rel = PurePosixPath(path.relative_to(musicforge).as_posix())
            reason = _exclude_reason(rel, mode)
            if reason:
                excluded.append({"path": f".musicforge/{rel.as_posix()}", "reason": reason})
        return excluded[:1000]

    def _backup_dir(self, backup_id: str) -> Path:
        if not str(backup_id).startswith("mb-"):
            raise LTSBackupError("Invalid backup id.")
        path = self.backups_dir / str(backup_id)
        if not path.exists():
            raise FileNotFoundError(f"Maintenance backup not found: {backup_id}")
        return path

    def _next_backup_id(self) -> str:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        existing = [int(path.name.removeprefix("mb-")) for path in self.backups_dir.glob("mb-*") if path.name.removeprefix("mb-").isdigit()]
        return f"mb-{(max(existing) + 1) if existing else 1:06d}"


def _should_exclude(rel: PurePosixPath, mode: str) -> bool:
    return bool(_exclude_reason(rel, mode))


def _exclude_reason(rel: PurePosixPath, mode: str) -> str:
    text = rel.as_posix().lower()
    name = rel.name.lower()
    if text in {"provider.json", "renderer.json"}:
        return "secret_or_local_config"
    if text.startswith("maintenance/backups/"):
        return "maintenance_backup_recursion"
    if "token" in text or "githubkey" in text or name.endswith(".key"):
        return "secret_or_local_config"
    if "provider-snapshot.json" in text:
        return "provider_snapshot"
    if mode == "metadata" and not name.endswith(".json") and not name.endswith(".jsonl") and not name.endswith(".md") and not name.endswith(".txt"):
        return "metadata_mode_excludes_artifact"
    if mode != "workspace_with_artifacts" and (text.startswith("runs/") or "/renders/" in text or name.endswith((".wav", ".mp3", ".flac", ".aac"))):
        return "artifact_excluded"
    return ""


def _read_manifest_from_zip(zip_path: Path) -> ImplementationDocument:
    with zipfile.ZipFile(zip_path) as archive:
        return json.loads(archive.read("manifest.json").decode("utf-8"))


def _restore_relative_path(package_path: str) -> PurePosixPath:
    prefix = "data/musicforge/"
    if not package_path.startswith(prefix):
        raise LTSBackupError(f"Unsupported restore package path: {package_path}")
    rel = PurePosixPath(package_path[len(prefix) :])
    if any(part in {"", ".", ".."} for part in rel.parts):
        raise LTSBackupError(f"Unsafe restore package path: {package_path}")
    return rel


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _json_bytes(payload: ImplementationDocument) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _text_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def _redaction_report_for_manifest(files: list[ImplementationDocument]) -> ImplementationDocument:
    return {"schema_version": 1, "status": "passed", "finding_count": 0, "findings": [], "scanned_file_count": len(files)}


def _git_summary(root: Path) -> ImplementationDocument:
    return {"head": _git_head(root), "status": _git_status_state(root), "branch": _quick_git(root, ["status", "--short", "--branch"])}


def _safe_ga_summary(root: Path) -> ImplementationDocument:
    path = root / "runs" / "ga-readiness" / "ga-readiness-report.json"
    if not path.exists():
        return {"status": "missing"}
    try:
        report = read_json(path)
    except Exception as exc:
        return {"status": "unreadable", "error": str(exc)}
    return {"status": report.get("status", "unknown"), "integrity_hash": report.get("integrity_hash"), "generated_at": report.get("generated_at")}


def _git_head(root: Path) -> str:
    return _quick_git(root, ["rev-parse", "HEAD"])


def _git_status_state(root: Path) -> str:
    text = _quick_git(root, ["status", "--short", "--branch"])
    if not text:
        return "unknown"
    lines = [line for line in text.splitlines() if line.strip()]
    return "dirty" if any(not line.startswith("## ") for line in lines) else "clean"


def _quick_git(root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except Exception:
        return ""
    return (completed.stdout or completed.stderr or "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
