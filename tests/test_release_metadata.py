from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.projectio import read_json
from song_agent.projects import ProjectStore
from song_agent.release_export import build_release_export_bundle, build_release_export_zip, refresh_release_export_signoff_summary
from song_agent.release_metadata import (
    attach_metadata_export_to_manifest,
    export_release_metadata_files,
    initialize_release_metadata,
    read_release_metadata,
    write_release_metadata,
)
from song_agent.release_metadata_qa import build_release_metadata_qa_report
from song_agent.release_qa import build_release_qa_report, build_release_signoff_record, release_signoff_summary
from song_agent.release_verifier import verify_release_zip
from song_agent.releases import ReleaseStore, stable_hash
from tests.test_releases import _signed_project


def test_release_metadata_init_save_history_and_export(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Metadata Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Metadata Pack", "release_type": "demo_pack", "primary_artist": "Local Artist", "label": "Forge Label", "language": "English"})
    release = release_store.add_track(release.release_id, {"project_id": project_id, "title": "Metadata Song"})

    metadata = initialize_release_metadata(release_store, release.release_id, now="2026-05-16T00:00:00+00:00")
    metadata["release"].update({"upc": "123456789012", "copyright": "2026 Local Artist", "phonographic_copyright": "2026 Forge Label", "confirmed": True})
    metadata["tracks"][0].update(
        {
            "isrc": "USABC2600001",
            "lyrics": "Clean lyric line",
            "credits": [{"role": "composer", "name": "Local Writer", "source": "user"}],
            "confirmed": True,
        }
    )
    saved = write_release_metadata(release_store, release.release_id, metadata, now="2026-05-16T00:01:00+00:00")
    qa = build_release_metadata_qa_report(release=release, metadata=saved, now="2026-05-16T00:02:00+00:00")
    release_qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)
    manifest = build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=release_qa)
    metadata_export = export_release_metadata_files(release_store=release_store, release_id=release.release_id, qa_report=qa, now="2026-05-16T00:03:00+00:00")
    manifest = attach_metadata_export_to_manifest(release_store, release.release_id, metadata_export)
    zip_info = _sign_and_zip_release(release_store, release, release_qa, now="2026-05-16T00:04:00+00:00")
    report = verify_release_zip(release_store.zip_path(release.release_id))

    history = (release_store.release_dir(release.release_id) / "metadata-history.jsonl").read_text(encoding="utf-8")
    release_metadata_export = read_json(release_store.export_dir(release.release_id) / "release-metadata.json")
    with zipfile.ZipFile(release_store.zip_path(release.release_id)) as archive:
        names = archive.namelist()
        zipped_metadata = json.loads(archive.read("release-metadata.json").decode("utf-8"))

    assert read_release_metadata(release_store, release.release_id)["release"]["title"] == "Metadata Pack"
    assert saved["tracks"][0]["isrc"] == "USABC2600001"
    assert "release_metadata_initialized" in history
    assert "release_metadata_saved" in history
    assert qa["status"] == "passed"
    assert manifest["metadata"]["exists"] is True
    assert "release-metadata.json" in {item["path"] for item in manifest["files"]}
    assert "platform-metadata.csv" in names
    assert "credits.csv" in names
    assert "lyrics/01-metadata-song.txt" in names
    assert release_metadata_export["release"]["upc"] == "123456789012"
    assert zipped_metadata["tracks"][0]["credits"][0]["name"] == "Local Writer"
    assert zip_info["entry_count"] == len(names)
    assert report["status"] == "passed"
    assert _check(report, "metadata_payload_hash")["status"] == "passed"


def test_release_metadata_qa_flags_format_duplicate_explicit_and_redaction(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    first = _signed_project(tmp_path, project_store, "Metadata Bad One")
    second = _signed_project(tmp_path, project_store, "Metadata Bad Two")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Bad Metadata EP", "release_type": "ep", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": first, "title": "Bad One"})
    release = release_store.add_track(release.release_id, {"project_id": second, "title": "Bad Two"})
    metadata = initialize_release_metadata(release_store, release.release_id)
    metadata["release"]["upc"] = "bad-upc"
    metadata["release"]["notes"] = r"C:\Users\demo\secret.zip api_key=sk-secret-value"
    metadata["tracks"][0]["isrc"] = "USABC2600001"
    metadata["tracks"][0]["lyrics"] = "this is explicit shit"
    metadata["tracks"][1]["isrc"] = "USABC2600001"
    metadata["tracks"][1]["instrumental"] = True
    metadata["tracks"][1]["lyrics"] = "instrumental notes"

    report = build_release_metadata_qa_report(release=release, metadata=metadata)

    assert report["status"] == "failed"
    assert _check(report, "upc_format")["status"] == "warning"
    assert _track_check(report, "isrc_unique")["status"] == "failed"
    assert _track_check(report, "explicit_flag_consistency")["status"] == "warning"
    assert _track_check(report, "instrumental_lyrics_conflict", track_id=release.tracks[1].track_id)["status"] == "warning"
    assert _check(report, "redaction_scan")["status"] == "failed"


def test_release_verifier_fails_when_declared_metadata_file_missing_or_polluted(tmp_path: Path) -> None:
    zip_path = _build_metadata_zip(tmp_path)
    missing = _rewrite_zip(zip_path, tmp_path / "missing-metadata.zip", remove={"release-metadata.json"})

    def pollute_platform(data: bytes) -> bytes:
        return data + b'\n"1","1","C:\\Users\\demo\\secret.zip api_key=sk-secret-value"\n'

    polluted = _rewrite_zip(zip_path, tmp_path / "polluted-metadata.zip", transforms={"platform-metadata.csv": pollute_platform})

    missing_report = verify_release_zip(missing)
    polluted_report = verify_release_zip(polluted)

    assert missing_report["status"] == "failed"
    assert _check(missing_report, "metadata_files_present")["status"] == "failed"
    assert polluted_report["status"] == "failed"
    assert _check(polluted_report, "manifest_file_hash_match")["status"] == "failed"
    assert _check(polluted_report, "redaction_scan")["status"] == "failed"


def _build_metadata_zip(tmp_path: Path) -> Path:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Verifier Metadata Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Verifier Metadata Pack", "release_type": "demo_pack", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": project_id, "title": "Verifier Metadata Song"})
    metadata = initialize_release_metadata(release_store, release.release_id)
    metadata["release"].update({"upc": "123456789012", "copyright": "2026 Local Artist", "phonographic_copyright": "2026 Local Artist", "confirmed": True})
    metadata["tracks"][0].update({"isrc": "USABC2600001", "lyrics": "Clean line", "credits": [{"role": "composer", "name": "Writer"}], "confirmed": True})
    metadata = write_release_metadata(release_store, release.release_id, metadata)
    metadata_qa = build_release_metadata_qa_report(release=release, metadata=metadata)
    release_qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)
    build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=release_qa)
    metadata_export = export_release_metadata_files(release_store=release_store, release_id=release.release_id, qa_report=metadata_qa)
    attach_metadata_export_to_manifest(release_store, release.release_id, metadata_export)
    _sign_and_zip_release(release_store, release, release_qa)
    return release_store.zip_path(release.release_id)


def _rewrite_zip(source: Path, target: Path, *, transforms: dict[str, object] | None = None, remove: set[str] | None = None) -> Path:
    transforms = transforms or {}
    remove = remove or set()
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename in remove:
                continue
            data = src.read(info)
            transform = transforms.get(info.filename)
            if transform is not None:
                data = transform(data)  # type: ignore[operator]
            dst.writestr(info.filename, data)
    return target


def _check(report: dict, check_id: str) -> dict:
    return next(check for check in report["checks"] if check["check_id"] == check_id)


def _track_check(report: dict, check_id: str, *, track_id: str | None = None) -> dict:
    return next(check for check in report["track_checks"] if check["check_id"] == check_id and (track_id is None or check.get("track_id") == track_id))


def _sign_and_zip_release(release_store: ReleaseStore, release, release_qa: dict, *, now: str = "2026-05-16T00:04:00+00:00") -> dict:
    pending = build_release_signoff_record(release=release, report=release_qa, payload={"signed_by": "metadata-test"}, export_manifest={}, now=now)
    release_store.write_signoff(release.release_id, {**pending, "export_manifest_hash": None})
    final_manifest = refresh_release_export_signoff_summary(release_store, release.release_id)
    final_manifest.pop("zip", None)
    signoff = release_store.write_signoff(release.release_id, {**pending, "export_manifest_hash": stable_hash(final_manifest)})
    refresh_release_export_signoff_summary(release_store, release.release_id)
    release_store.update_signoff_summary(release.release_id, release_signoff_summary(signoff))
    return build_release_export_zip(release_store, release.release_id, now=now)
