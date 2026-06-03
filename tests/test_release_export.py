from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore
from song_agent.release_export import ReleaseExportError, build_release_export_bundle, build_release_export_zip, read_release_export_manifest, release_export_summary
from song_agent.release_qa import build_release_qa_report
from song_agent.releases import ReleaseStore
from tests.test_releases import _signed_project


def test_release_export_blocks_failed_qa(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Empty Pack", "release_type": "ep", "primary_artist": "Local Artist"})
    qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)

    with pytest.raises(ReleaseExportError, match="Release QA gate failed"):
        build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=qa)


def test_release_export_copies_two_tracks_and_builds_safe_zip(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    first = _signed_project(tmp_path, project_store, "First Export")
    second = _signed_project(tmp_path, project_store, "Second Export")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Export EP", "release_type": "ep", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": first, "title": "First Export"})
    release = release_store.add_track(release.release_id, {"project_id": second, "title": "Second Export"})
    qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)

    manifest = build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=qa)
    zip_info = build_release_export_zip(release_store, release.release_id, now="2026-05-15T00:10:00+00:00")
    disk_manifest = read_release_export_manifest(release_store, release.release_id)
    with zipfile.ZipFile(release_store.zip_path(release.release_id)) as archive:
        names = archive.namelist()
        zipped_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    serialized = json.dumps({"manifest": disk_manifest, "zip_manifest": zipped_manifest, "zip": zip_info}, ensure_ascii=False)

    assert manifest["summary"]["track_count"] == 2
    assert release_export_summary(disk_manifest)["status"] == "exported"
    assert zip_info["entry_count"] > 8
    assert "manifest.json" in names
    assert "tracklist.json" in names
    assert any(name.endswith("/song.mid") for name in names)
    assert all(file.get("path") and not str(file.get("path")).startswith(("/", "\\")) for file in disk_manifest["files"])
    assert any(file["path"].endswith("/song.mid") for file in disk_manifest["files"])
    assert any(file["path"] == "release.json" for file in disk_manifest["files"])
    assert any(file["path"].endswith("/song.mid") for file in zipped_manifest["files"])
    assert all(not name.startswith(("/", "\\")) and ".." not in name.split("/") for name in names)
    assert "path" not in disk_manifest.get("zip", {})
    assert str(tmp_path) not in serialized
    assert str(tmp_path).replace("\\", "/") not in serialized


def test_release_export_helpers_block_signed_release_mutations_by_default(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Signed Export Guard")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Signed Export Pack", "release_type": "demo_pack", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": project_id})
    qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)
    build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=qa)
    build_release_export_zip(release_store, release.release_id)
    zip_before = release_store.zip_path(release.release_id).read_bytes()

    release_store.write_signoff(release.release_id, {"status": "signed", "signed_by": "test"})
    release_store.update_signoff_summary(release.release_id, {"status": "signed"})
    signed_release = release_store.get_release(release.release_id)

    with pytest.raises(ReleaseExportError, match="Signed releases cannot rebuild export or ZIP"):
        build_release_export_bundle(release=signed_release, release_store=release_store, project_store=project_store, qa_report=qa)
    with pytest.raises(ReleaseExportError, match="Signed releases cannot rebuild export or ZIP"):
        build_release_export_zip(release_store, release.release_id)

    assert release_store.zip_path(release.release_id).read_bytes() == zip_before

    allowed_zip = build_release_export_zip(release_store, release.release_id, allow_signed=True)

    assert allowed_zip["sha256"]
    assert release_store.zip_path(release.release_id).read_bytes() != b""
    assert zip_before != b""


def test_release_export_rejects_polluted_project_manifest_path(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Polluted Export")
    project_dir = project_store.project_dir(project_id)
    manifest_path = project_dir / "final-export" / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"].append({"kind": "midi", "path": "../outside.mid", "exists": True, "required": True})
    write_json(manifest_path, manifest)
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Polluted Pack", "release_type": "demo_pack", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": project_id})
    qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)

    assert qa["status"] == "failed"
    with pytest.raises(ReleaseExportError):
        build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=qa)
