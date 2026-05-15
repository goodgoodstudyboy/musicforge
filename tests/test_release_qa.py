from __future__ import annotations

from pathlib import Path

from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore
from song_agent.release_qa import build_release_qa_report, release_qa_summary
from song_agent.releases import ReleaseStore
from tests.test_releases import _signed_project


def test_release_qa_fails_empty_ep(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Empty EP", "release_type": "ep", "primary_artist": "Local Artist"})

    report = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)

    assert report["status"] == "failed"
    assert release_qa_summary(report)["blocker_count"] >= 1
    assert _check(report, "track_count")["status"] == "failed"


def test_release_qa_passes_two_signed_projects_and_warns_duplicate_title(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    first = _signed_project(tmp_path, project_store, "Same Title")
    second = _signed_project(tmp_path, project_store, "Same Title")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Demo EP", "release_type": "ep", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": first, "title": "Same Title"})
    release = release_store.add_track(release.release_id, {"project_id": second, "title": "Same Title"})

    report = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)

    assert report["status"] == "warning"
    assert _check(report, "title_duplicates")["status"] == "warning"
    assert all(check["status"] == "passed" for check in report["track_checks"] if check["check_id"] == "delivery_qa_passed")
    assert all(check["status"] == "passed" for check in report["track_checks"] if check["check_id"] == "delivery_signoff_exists")


def test_release_qa_fails_when_project_core_file_removed_after_snapshot(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Broken Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Broken Pack", "release_type": "demo_pack", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": project_id})
    (project_store.project_dir(project_id) / "final-export" / "song.mid").unlink()

    report = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)
    core = next(check for check in report["track_checks"] if check["check_id"] == "final_export_core_files")

    assert report["status"] == "failed"
    assert core["status"] == "failed"


def test_release_qa_scans_raw_release_json_for_sensitive_values(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Redaction Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Redaction Pack", "release_type": "demo_pack", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": project_id})
    release_path = release_store.release_dir(release.release_id) / "release.json"
    raw = read_json(release_path)
    raw["metadata"] = {"local_path": r"C:\Users\demo\release", "note": "safe"}
    write_json(release_path, raw)
    release = release_store.get_release(release.release_id)

    report = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)

    assert report["status"] == "failed"
    assert _check(report, "redaction_scan")["status"] == "failed"


def _check(report: dict, check_id: str) -> dict:
    return next(check for check in report["checks"] if check["check_id"] == check_id)
