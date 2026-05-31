from __future__ import annotations

import zipfile
import shutil
from pathlib import Path

from song_agent.audio_encoding import AudioEncoderConfig
from song_agent.distribution_verifier import verify_distribution_package
from song_agent.release_metadata import attach_metadata_export_to_manifest, export_release_metadata_files, initialize_release_metadata, write_release_metadata, write_release_metadata_qa
from song_agent.release_metadata_qa import build_release_metadata_qa_report
from tests.test_mastering_qa import _signed_project
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_distribution_package_uses_encoded_mp3_and_verifier_catches_tamper(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _prepared_encoded_release(server)
        target_status, target = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/distribution/targets",
            {
                "profile_id": "demo_pitch",
                "name": "MP3 Pitch",
                "options": {
                    "require_release_signed": False,
                    "require_release_zip_verified": False,
                    "require_metadata_export": False,
                    "require_artwork": False,
                    "require_encoded_audio": True,
                    "audio_format_profiles": ["mp3_320"],
                },
            },
        )
        target_id = target["target"]["target_id"]
        missing_qa_status, missing_qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        fake_config_status, fake_config = request_json(server, "POST", "/api/audio-encoding/config", {"fake_runner": True})
        server.audio_encoding_store.runner = _FixtureEncoderRunner()
        request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/render", {"profile_ids": ["mp3_320"]})
        request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/health", {"profile_ids": ["mp3_320"]})
        missing_review_status, _missing_review = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "encoded-audio-test", "require_encoded_audio_review": True})
        review_status, review = request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/reviews", {"profile_id": "mp3_320", "track_id": "track-000001", "status": "accepted", "review_mode": "manual", "reviewer": {"name": "encoded reviewer"}, "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/acceptance/refresh", {"profile_ids": ["mp3_320"]})
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        _export_metadata(server, release_id)
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        sign_status, _sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "encoded-audio-test", "require_encoded_audio_review": True})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        package_id = export["manifest"]["package_id"]
        zip_path = Path(".musicforge") / "releases" / release_id / "distribution" / "packages" / package_id / "distribution-package.zip"
        verify = verify_distribution_package(zip_path, require_encoded_audio=True, require_encoded_audio_review=True)
        with zipfile.ZipFile(zip_path) as archive:
            mp3_name = next(name for name in archive.namelist() if name.startswith("audio/") and name.endswith(".mp3"))
        tampered_zip = _rewrite_zip(zip_path, tmp_path / "tampered-encoded.zip", {mp3_name: lambda _data: b"RIFFxxxxWAVEfake"})
        tampered = verify_distribution_package(tampered_zip, require_encoded_audio=True, require_encoded_audio_review=True)
        review_name = next(name for name in zipfile.ZipFile(zip_path).namelist() if name.startswith("encoded-audio-acceptance/reviews/") and name.endswith(".json"))
        tampered_review_zip = _rewrite_zip(zip_path, tmp_path / "tampered-encoded-review.zip", {review_name: lambda data: data.replace(b'"status": "accepted"', b'"status": "rejected"')})
        tampered_review = verify_distribution_package(tampered_review_zip, require_encoded_audio=True, require_encoded_audio_review=True)
    finally:
        stop_test_server(server)

    assert target_status == 201
    assert fake_config_status == 400
    assert "test-only" in fake_config["error"]
    assert missing_review_status == 409
    assert review_status == 201
    assert review["review"]["review_mode"] == "manual"
    assert missing_qa_status == 200
    assert missing_qa["summary"]["status"] == "failed"
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning"}
    assert export_status == 201
    audio_entries = [entry for entry in export["manifest"]["layout"]["entries"] if entry["kind"] == "audio"]
    assert audio_entries[0]["source_kind"] == "encoded_audio"
    assert audio_entries[0]["path"].endswith(".mp3")
    assert export["manifest"]["encoded_audio"]["profiles"][0]["profile_id"] == "mp3_320"
    assert export["manifest"]["encoded_audio_acceptance"]["status"] == "passed"
    assert zip_status == 200
    assert sign_status == 200
    assert verify["status"] in {"passed", "warning"}
    assert _check(verify, "distribution_encoded_audio_evidence")["status"] == "passed"
    assert _check(verify, "distribution_encoded_audio_acceptance_evidence")["status"] == "passed"
    assert tampered["status"] == "failed"
    assert _check(tampered, "distribution_encoded_audio_evidence")["status"] == "failed"
    assert tampered_review["status"] == "failed"
    assert _check(tampered_review, "distribution_encoded_audio_acceptance_evidence")["status"] == "failed"


def test_distribution_verifier_requires_encoded_layout_entries(tmp_path) -> None:
    zip_path = tmp_path / "wav-only-package.zip"
    manifest = {
        "schema_version": 1,
        "package_id": "pkg-000001",
        "release_id": "rel-000001",
        "target_id": "target-000001",
        "profile_id": "demo_pitch",
        "target": {"options": {"require_encoded_audio": True, "audio_format_profiles": ["mp3_320"]}},
        "encoded_audio": {"status": "included", "profiles": [], "summary_path": "encoded-audio/summary.json"},
        "layout": {
            "entries": [
                {
                    "entry_id": "audio:track-000001",
                    "kind": "audio",
                    "track_id": "track-000001",
                    "source_kind": "release_export",
                    "path": "audio/01-song.wav",
                    "ext": "wav",
                    "audio_format": {"profile_id": "wav_master", "format": "wav", "extension": "wav"},
                    "size_bytes": 12,
                    "sha256": "fake",
                }
            ]
        },
        "files": [{"path": "audio/01-song.wav", "size_bytes": 12, "sha256": "fake"}],
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("distribution-manifest.json", json_dumps(manifest))
        archive.writestr("distribution-signoff.json", "{}")
        archive.writestr("package.json", "{}")
        archive.writestr("release.json", "{}")
        archive.writestr("tracklist.json", '{"tracks":[{"track_id":"track-000001"}]}')
        archive.writestr("README.txt", "test")
        archive.writestr("encoded-audio/summary.json", "{}")
        archive.writestr("audio/01-song.wav", b"RIFFxxxxWAVE")

    report = verify_distribution_package(zip_path, require_encoded_audio=True)

    assert report["status"] == "failed"
    assert _check(report, "distribution_encoded_audio_evidence")["status"] == "failed"
    assert "encoded_layout_entries_missing" in _check(report, "distribution_encoded_audio_evidence")["message"]


def _export_metadata(server, release_id: str) -> None:
    release = server.release_store.get_release(release_id)
    metadata = initialize_release_metadata(server.release_store, release_id)
    metadata["release"].update({"copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
    for index, track in enumerate(metadata.get("tracks", []), start=1):
        track.update({"isrc": f"USABC260{index:04d}", "credits": [{"role": "composer", "name": "Tester"}], "confirmed": True})
    metadata = write_release_metadata(server.release_store, release_id, metadata)
    qa = write_release_metadata_qa(server.release_store, release_id, build_release_metadata_qa_report(release=release, metadata=metadata))
    exported = export_release_metadata_files(release_store=server.release_store, release_id=release_id, qa_report=qa)
    attach_metadata_export_to_manifest(server.release_store, release_id, exported)


def _prepared_encoded_release(server) -> str:
    project_id = _signed_project(server, "Distribution Encoded Track")
    _add_final_export_audio(server, project_id, duration_seconds=30)
    _, release = request_json(server, "POST", "/api/releases", {"name": "Distribution Encoded Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
    release_id = release["release"]["release_id"]
    request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
    request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
    request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
    request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
    request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
    _, candidate = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
    candidate_id = candidate["candidate"]["candidate_id"]
    request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
    request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
    request_json(server, "POST", f"/api/releases/{release_id}/export")
    request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
    return release_id


def _rewrite_zip(source: Path, target: Path, transforms: dict[str, object]) -> Path:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            transform = transforms.get(info.filename)
            if transform is not None:
                data = transform(data)
            dst.writestr(info.filename, data)
    return target


def _check(report: dict, check_id: str) -> dict:
    for item in report.get("checks", []):
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)


class _FixtureEncoderRunner:
    def encode(self, *, source: Path, target: Path, profile, config: AudioEncoderConfig) -> dict:
        target.parent.mkdir(parents=True, exist_ok=True)
        if profile.format == "mp3":
            target.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x15MusicForgeFixtureMP3" + (b"\0" * 20000))
        elif profile.format == "flac":
            target.write_bytes(b"fLaC\x00\x00\x00\"MusicForgeFixtureFLAC" + (b"\0" * 20000))
        elif profile.format == "aac":
            target.write_bytes(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A isommp42" + (b"\0" * 20000))
        elif profile.format == "wav":
            shutil.copy2(source, target)
        else:
            return {"status": "failed", "returncode": None, "message": "Unsupported fixture format."}
        return {"status": "completed", "returncode": 0, "message": "Fixture encoder completed."}


def json_dumps(value: dict) -> str:
    import json

    return json.dumps(value)
