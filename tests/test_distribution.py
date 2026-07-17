from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

from song_agent.distribution import DistributionStore, distribution_signoff_summary
from song_agent.distribution_artwork import import_distribution_artwork
from song_agent.distribution_checklist import initialize_distribution_checklist, update_distribution_checklist_item
from song_agent.distribution_export import (
    build_distribution_export_package,
    build_distribution_package_zip,
    sign_distribution_package,
)
from song_agent.distribution_qa import build_distribution_qa_report
from song_agent.distribution_verifier import verify_distribution_package
from song_agent.distribution_templates import TemplatePackStore
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


def test_template_checklist_export_and_verifier_tamper_guards(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    templates = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")
    template = templates.create_template(
        {
            "slug": "qa-template-basic",
            "name": "QA Template Basic",
            "rules": {"require_artwork": True, "require_upc": True, "require_isrc": True, "csv_formula_escape": True},
            "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}, {"column": "ISRC", "source": "track.isrc", "required": True}]},
            "file_naming": {"artwork": "cover.{ext}", "audio": "{track_number:02d}-{slug_title}.wav"},
            "checklist": [{"item_id": "explicit-confirmed", "label": "Explicit checked", "required": True}],
        }
    )
    target = store.create_target(release_id, {"profile_id": "demo_pitch", "template_pack_id": template["template_pack_id"]})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    checklist = initialize_distribution_checklist(store, release_id, target, template)
    failed_qa = build_distribution_qa_report(store=store, release_id=release_id, target=target)
    checklist = update_distribution_checklist_item(store, release_id, target, template, "explicit-confirmed", {"status": "done", "note": "Checked"})
    target = store.get_target(release_id, target.target_id)
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    zip_path = store.package_zip_path(release_id, manifest["package_id"])
    report = verify_distribution_package(zip_path, require_artwork=True)

    def tamper_template(data: bytes) -> bytes:
        template_doc = json.loads(data.decode("utf-8"))
        template_doc["name"] = "Tampered Template"
        return json.dumps(template_doc, ensure_ascii=False, indent=2).encode("utf-8")

    def tamper_checklist(data: bytes) -> bytes:
        checklist_doc = json.loads(data.decode("utf-8"))
        checklist_doc["items"][0]["status"] = "blocked"
        return json.dumps(checklist_doc, ensure_ascii=False, indent=2).encode("utf-8")

    tampered_template = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "template-tampered.zip", transforms={"template-pack.json": tamper_template}))
    tampered_checklist = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "checklist-tampered.zip", transforms={"docs/checklist.json": tamper_checklist}))

    assert any(item["check_id"] == "checklist_required_pending" for item in failed_qa["blockers"])
    assert checklist["summary"]["status"] == "passed"
    assert manifest["template"]["template_hash"] == template["template_hash"]
    assert manifest["checklist"]["status"] == "passed"
    assert report["status"] == "passed"
    assert _check(tampered_template, "distribution_template_hash_match")["status"] == "failed"
    assert _check(tampered_checklist, "distribution_checklist_payload_hash")["status"] == "failed"


def test_distribution_export_applies_layout_contract_paths(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    templates = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")
    template = templates.create_template(
        {
            "slug": "layout-contract-template",
            "name": "Layout Contract Template",
            "rules": {"require_artwork": True, "require_upc": True, "require_isrc": True},
            "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}]},
            "file_naming": {
                "audio": "tracks/disc-{disc_number}/{track_number:02d}-{slug_title}.{ext}",
                "lyrics": "lyric-sheets/{language}/{track_number:02d}-{slug_title}.txt",
                "artwork": "artwork/{release_slug}-cover.{ext}",
            },
        }
    )
    target = store.create_target(release_id, {"profile_id": "demo_pitch", "template_pack_id": template["template_pack_id"]})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    package_id = manifest["package_id"]
    export_dir = store.export_dir(release_id, package_id)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    paths = {item["path"] for item in manifest["files"]}
    layout_paths = {item["path"] for item in manifest["layout"]["entries"]}

    assert manifest["layout"]["summary"]["status"] == "passed"
    assert "tracks/disc-1/01-distribution-song.wav" in paths
    assert "lyric-sheets/english/01-distribution-song.txt" in paths
    assert "artwork/distribution-pack-cover.png" in paths
    assert manifest["artwork"]["package_path"] == "artwork/distribution-pack-cover.png"
    assert layout_paths <= paths
    assert "layout/manifest-layout.json" in paths
    assert "layout/file-tree.txt" in paths
    assert "C:\\" not in (export_dir / "layout" / "manifest-layout.json").read_text(encoding="utf-8")


def test_distribution_verifier_layout_tamper_guards(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    target = store.create_target(release_id, {"profile_id": "demo_pitch"})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    zip_path = store.package_zip_path(release_id, manifest["package_id"])

    def tamper_layout_sidecar(data: bytes) -> bytes:
        layout = json.loads(data.decode("utf-8"))
        layout["entries"][0]["path"] = "audio/tampered.wav"
        return json.dumps(layout, ensure_ascii=False, indent=2).encode("utf-8")

    def tamper_manifest_layout(data: bytes) -> bytes:
        manifest_doc = json.loads(data.decode("utf-8"))
        manifest_doc["layout"]["entries"][0]["path"] = "audio/tampered.wav"
        return json.dumps(manifest_doc, ensure_ascii=False, indent=2).encode("utf-8")

    def tamper_artwork_path(data: bytes) -> bytes:
        manifest_doc = json.loads(data.decode("utf-8"))
        manifest_doc["artwork"]["package_path"] = "artwork/missing.png"
        return json.dumps(manifest_doc, ensure_ascii=False, indent=2).encode("utf-8")

    def strip_layout(data: bytes) -> bytes:
        manifest_doc = json.loads(data.decode("utf-8"))
        manifest_doc.pop("layout", None)
        manifest_doc.pop("tool", None)
        manifest_doc["files"] = [item for item in manifest_doc.get("files", []) if not str(item.get("path") or "").startswith("layout/")]
        return json.dumps(manifest_doc, ensure_ascii=False, indent=2).encode("utf-8")

    def legacy_signoff(data: bytes) -> bytes:
        signoff_doc = json.loads(data.decode("utf-8"))
        with zipfile.ZipFile(zip_path) as archive:
            manifest_doc = json.loads(strip_layout(archive.read("distribution-manifest.json")).decode("utf-8"))
        signoff_doc["export_manifest_hash"] = __import__("song_agent.releases", fromlist=["stable_hash"]).stable_hash({key: value for key, value in manifest_doc.items() if key != "zip"})
        return json.dumps(signoff_doc, ensure_ascii=False, indent=2).encode("utf-8")

    sidecar_report = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "layout-sidecar.zip", transforms={"layout/manifest-layout.json": tamper_layout_sidecar}))
    manifest_report = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "layout-manifest.zip", transforms={"distribution-manifest.json": tamper_manifest_layout}))
    artwork_report = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "layout-artwork.zip", transforms={"distribution-manifest.json": tamper_artwork_path}))
    legacy_report = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "layout-legacy.zip", transforms={"distribution-manifest.json": strip_layout, "distribution-signoff.json": legacy_signoff}, drop={"layout/manifest-layout.json", "layout/file-tree.txt"}))
    legacy_strict_report = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "layout-legacy-strict.zip", transforms={"distribution-manifest.json": strip_layout, "distribution-signoff.json": legacy_signoff}, drop={"layout/manifest-layout.json", "layout/file-tree.txt"}), strict=True)

    assert _check(sidecar_report, "distribution_layout_hash_match")["status"] == "failed"
    assert _check(manifest_report, "distribution_layout_entries_declared")["status"] == "failed"
    assert _check(artwork_report, "distribution_artwork_package_path_match")["status"] == "failed"
    assert _check(legacy_report, "distribution_layout_legacy_missing")["status"] == "warning"
    assert legacy_report["status"] == "warning"
    assert _check(legacy_strict_report, "distribution_layout_legacy_missing")["status"] == "failed"


def test_distribution_verifier_require_audio_accepts_layout_midi_fallback(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    target = store.create_target(release_id, {"profile_id": "demo_pitch"})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    export_dir = release_store.export_dir(release_id)
    for wav_path in export_dir.glob("tracks/*/song.wav"):
        wav_path.unlink()
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    report = verify_distribution_package(store.package_zip_path(release_id, manifest["package_id"]), require_audio=True, require_artwork=True)

    assert any(entry["kind"] == "audio" and entry["path"].endswith(".mid") for entry in manifest["layout"]["entries"])
    assert report["status"] == "passed"
    assert _check(report, "distribution_audio_file_valid")["status"] == "passed"


def test_distribution_export_rejects_hardcoded_wav_pattern_for_midi_fallback(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    templates = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")
    template = templates.create_template(
        {
            "slug": "hardcoded-wav-template",
            "name": "Hardcoded WAV Template",
            "file_naming": {"audio": "audio/{track_number:02d}-{slug_title}.wav"},
        }
    )
    target = store.create_target(release_id, {"profile_id": "demo_pitch", "template_pack_id": template["template_pack_id"]})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    for wav_path in release_store.export_dir(release_id).glob("tracks/*/song.wav"):
        wav_path.unlink()
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))

    assert qa["summary"]["status"] == "failed"
    assert any(check["check_id"] == "layout_plan_valid" and check["status"] == "failed" for check in qa["checks"])
    try:
        build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    except ValueError as exc:
        assert "qa gate failed" in str(exc).lower()
    else:
        raise AssertionError("Distribution export should reject hardcoded .wav layout for MIDI source.")


def test_distribution_verifier_returns_failed_report_for_bad_template_pack(tmp_path: Path) -> None:
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    templates = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")
    template = templates.create_template(
        {
            "slug": "layout-verifier-template",
            "name": "Layout Verifier Template",
            "file_naming": {"audio": "audio/{track_number:02d}-{slug_title}.{ext}"},
        }
    )
    target = store.create_target(release_id, {"profile_id": "demo_pitch", "template_pack_id": template["template_pack_id"]})
    artwork = import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    target = store.update_target(release_id, target.target_id, {"options": {"artwork_id": artwork["artwork_id"]}})
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    zip_path = store.package_zip_path(release_id, manifest["package_id"])

    def poison_template(data: bytes) -> bytes:
        template_doc = json.loads(data.decode("utf-8"))
        template_doc["file_naming"]["audio"] = "../x.wav"
        return json.dumps(template_doc, ensure_ascii=False, indent=2).encode("utf-8")

    report = verify_distribution_package(_rewrite_zip(zip_path, tmp_path / "bad-template-pack.zip", transforms={"template-pack.json": poison_template}))

    assert report["status"] == "failed"
    assert _check(report, "distribution_layout_template_pattern_parse")["status"] == "failed"


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


def _rewrite_zip(source: Path, target: Path, *, transforms: dict[str, object] | None = None, drop: set[str] | None = None) -> Path:
    transforms = transforms or {}
    drop = drop or set()
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename in drop:
                continue
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
