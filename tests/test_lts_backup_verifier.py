from __future__ import annotations

import zipfile
from pathlib import Path

from song_agent.lts_backup import LTSBackupStore
from song_agent.lts_backup_verifier import verify_maintenance_backup_zip


def _fixture_repo(root: Path) -> None:
    (root / ".musicforge" / "projects" / "project-001").mkdir(parents=True)
    (root / ".musicforge" / "projects" / "project-001" / "project.json").write_text('{"project_id":"project-001"}\n', encoding="utf-8")
    (root / ".musicforge" / "provider.json").write_text('{"api_key":"sk-test-secret-should-not-ship"}\n', encoding="utf-8")
    (root / ".musicforge" / "renderer.json").write_text('{"soundfont_path":"C:\\\\Users\\\\bad\\\\soundfont.sf2"}\n', encoding="utf-8")


def test_maintenance_backup_excludes_local_configs_and_verifies(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    store = LTSBackupStore(tmp_path)

    created = store.create_backup(mode="workspace")
    zip_path = store.backup_zip_path(created["backup"]["backup_id"])
    report = verify_maintenance_backup_zip(zip_path, strict=True)

    assert report["status"] == "passed", report
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "data/musicforge/provider.json" not in names
    assert "data/musicforge/renderer.json" not in names
    assert "data/musicforge/projects/project-001/project.json" in names


def test_maintenance_backup_verifier_rejects_unsafe_entries(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    store = LTSBackupStore(tmp_path)
    created = store.create_backup(mode="workspace")
    source = store.backup_zip_path(created["backup"]["backup_id"])
    target = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            dst.writestr(name, src.read(name))
        dst.writestr("../outside.txt", b"outside")
        dst.writestr("data/bad.txt", b"bad")
    target.write_bytes(target.read_bytes().replace(b"data/bad.txt", b"data\\bad.txt"))

    report = verify_maintenance_backup_zip(target, strict=True)
    statuses = {check["check_id"]: check["status"] for check in report["checks"]}

    assert report["status"] == "failed"
    assert statuses["lts_backup_zip_path_safe"] == "failed"
    assert statuses["lts_backup_zip_no_backslash_entries"] == "failed"


def test_maintenance_backup_verifier_rejects_redaction_pollution(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    store = LTSBackupStore(tmp_path)
    created = store.create_backup(mode="workspace")
    source = store.backup_zip_path(created["backup"]["backup_id"])
    target = tmp_path / "secret.zip"
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            dst.writestr(name, src.read(name))
        dst.writestr("data/musicforge/projects/secret.txt", b"Bearer sk-release-check-secret-token")

    report = verify_maintenance_backup_zip(target, strict=True)
    statuses = {check["check_id"]: check["status"] for check in report["checks"]}

    assert report["status"] == "failed"
    assert statuses["lts_backup_redaction_scan"] == "failed"
