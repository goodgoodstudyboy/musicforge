from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

from song_agent.distribution import DistributionStore, distribution_signoff_summary
from song_agent.distribution_artwork import import_distribution_artwork
from song_agent.distribution_export import (
    build_distribution_export_package,
    build_distribution_package_zip,
    sign_distribution_package,
)
from song_agent.distribution_qa import build_distribution_qa_report
from song_agent.distribution_verifier import verify_distribution_package
from song_agent.projectio import read_json, write_json
from song_agent.release_export import build_release_export_bundle
from song_agent.release_metadata import attach_metadata_export_to_manifest, export_release_metadata_files, initialize_release_metadata, write_release_metadata
from song_agent.release_metadata import write_release_metadata_qa
from song_agent.release_metadata_qa import build_release_metadata_qa_report
from song_agent.release_qa import build_release_qa_report
from song_agent.releases import ReleaseStore
from tests.test_release_metadata import _sign_and_zip_release
from tests.test_releases import _signed_project


def test_distribution_package_export_signoff_and_verify(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    target = store.create_target(release_id, {"profile_id": "demo_pitch", "name": "Pitch Package"})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"], "submission_note": "=needs escaping"}})
    qa = build_distribution_qa_report(store=store, release_id=release_id, target=target)
    qa = store.write_qa(release_id, target.target_id, qa)
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    zip_info = build_distribution_package_zip(store, release_id, target)
    signoff = sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    target = store.get_target(release_id, target.target_id)
    report = verify_distribution_package(store.package_zip_path(release_id, manifest["package_id"]), require_artwork=True)

    with zipfile.ZipFile(store.package_zip_path(release_id, manifest["package_id"])) as archive:
        names = set(archive.namelist())
        zipped_signoff = json.loads(archive.read("distribution-signoff.json").decode("utf-8"))
        zipped_manifest = json.loads(archive.read("distribution-manifest.json").decode("utf-8"))
        notes = archive.read("docs/submission-notes.md").decode("utf-8")

    assert qa["status"] in {"passed", "warning"}
    assert manifest["summary"]["status"] == "exported"
    assert zip_info["sha256"]
    assert signoff["status"] == "signed"
    assert distribution_signoff_summary(signoff)["status"] == "signed"
    assert target.status == "signed"
    assert report["status"] == "passed"
    assert "release-metadata.json" in names
    assert "platform-metadata.csv" in names
    assert "artwork/cover.png" in names
    assert zipped_signoff["export_manifest_hash"] == signoff["export_manifest_hash"]
    assert zipped_manifest["sidecars"]["distribution_signoff"]["payload_hash"]
    assert "=needs escaping" in notes


def test_distribution_verifier_fails_tampered_signoff_and_formula_csv(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path, formula_title=True)
    store = DistributionStore(release_store)
    target = store.create_target(release_id, {"profile_id": "demo_pitch"})
    import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    zip_path = store.package_zip_path(release_id, manifest["package_id"])

    def tamper_signoff(data: bytes) -> bytes:
        signoff = json.loads(data.decode("utf-8"))
        signoff["signed_by"] = "tampered"
        return json.dumps(signoff, ensure_ascii=False, indent=2).encode("utf-8")

    def unescape_platform(data: bytes) -> bytes:
        return data.replace(b"'=formula", b"=formula")

    tampered = _rewrite_zip(zip_path, tmp_path / "tampered.zip", transforms={"distribution-signoff.json": tamper_signoff})
    formula = _rewrite_zip(zip_path, tmp_path / "formula.zip", transforms={"platform-metadata.csv": unescape_platform})
    backslash = _backslash_zip(tmp_path / "backslash.zip")

    tampered_report = verify_distribution_package(tampered)
    formula_report = verify_distribution_package(formula)
    backslash_report = verify_distribution_package(backslash)

    assert _check(tampered_report, "distribution_signoff_sidecar_payload_hash")["status"] == "failed"
    assert _check(formula_report, "distribution_manifest_file_hash_match")["status"] == "failed"
    assert _check(formula_report, "distribution_csv_formula_safe")["status"] == "failed"
    assert _check(backslash_report, "zip_entry_path_safe")["status"] == "failed"


def _signed_release_with_metadata(tmp_path: Path, *, formula_title: bool = False):
    from song_agent.projects import ProjectStore

    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Distribution Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Distribution Pack", "release_type": "demo_pack", "primary_artist": "Local Artist", "label": "Forge Label", "language": "English"})
    release = release_store.add_track(release.release_id, {"project_id": project_id, "title": "Distribution Song"})
    metadata = initialize_release_metadata(release_store, release.release_id)
    metadata["release"].update({"upc": "123456789012", "copyright": "2026 Local Artist", "phonographic_copyright": "2026 Local Artist", "confirmed": True})
    metadata["tracks"][0].update({"title": "=formula" if formula_title else "Distribution Song", "isrc": "USABC2600001", "lyrics": "Clean line", "credits": [{"role": "composer", "name": "Writer"}], "confirmed": True})
    metadata = write_release_metadata(release_store, release.release_id, metadata)
    metadata_qa = build_release_metadata_qa_report(release=release, metadata=metadata)
    metadata_qa = write_release_metadata_qa(release_store, release.release_id, metadata_qa)
    release_qa = build_release_qa_report(release=release, release_store=release_store, project_store=project_store)
    build_release_export_bundle(release=release, release_store=release_store, project_store=project_store, qa_report=release_qa)
    metadata_export = export_release_metadata_files(release_store=release_store, release_id=release.release_id, qa_report=metadata_qa)
    attach_metadata_export_to_manifest(release_store, release.release_id, metadata_export)
    _sign_and_zip_release(release_store, release, release_qa)
    return release_store, release.release_id


def _png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + b"\x00" * 16


def _rewrite_zip(source: Path, target: Path, *, transforms: dict[str, object] | None = None) -> Path:
    transforms = transforms or {}
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info)
            transform = transforms.get(info.filename)
            if transform is not None:
                data = transform(data)  # type: ignore[operator]
            dst.writestr(info.filename, data)
    return target


def _backslash_zip(target: Path) -> Path:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    target.write_bytes(target.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))
    return target


def _check(report: dict, check_id: str) -> dict:
    return next(check for check in report["checks"] if check["check_id"] == check_id)
