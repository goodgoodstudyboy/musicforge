from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.projectio import read_json, write_json
from song_agent.release_verifier import verify_release_zip
from tests.test_audio_review_evidence import _signed_audio_project
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_server_per_track_audio_review_gate_export_verifier_and_marker_task(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        first = _signed_audio_project(server, "Server Audio Review One")
        second = _signed_audio_project(server, "Server Audio Review Two")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Server Audio Review Release", "release_type": "ep", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first})
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second})
        request_json(server, "POST", f"/api/releases/{release_id}/tracks/track-000001/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/tracks/track-000002/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_status, audio = request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})

        first_review_status, first_review = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "first ok", "markers": [{"time_seconds": 2, "category": "mix_balance", "message": "kick loud"}]})
        missing_gate_status, missing_gate = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True, "require_per_track_audio_review": True})
        synthetic_status, synthetic = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000002", "status": "accepted", "review_mode": "synthetic", "rating": 5, "playback_confirmed": True, "notes": "synthetic second"})
        synthetic_gate_status, synthetic_gate = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True, "require_per_track_audio_review": True})
        second_review_status, second_review = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000002", "status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True, "notes": "second ok"})
        summary_status, summary = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/refresh-summary")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        marker_status, marker_task = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/{first_review['review']['review_id']}/markers/m-000001/create-review-task", {"title": "Fix marker"})
        marker_again_status, marker_again = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/{first_review['review']['review_id']}/markers/m-000001/create-review-task", {"title": "Fix marker duplicate"})
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True, "require_per_track_audio_review": True, "require_human_audio_review": True})
        write_after_sign_status, write_after_sign = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        verify = verify_release_zip(Path(".musicforge") / "releases" / release_id / "release-export.zip", require_audio=True, require_human_review=True)

        tampered_zip = tmp_path / "tampered.zip"
        tampered_zip.write_bytes((Path(".musicforge") / "releases" / release_id / "release-export.zip").read_bytes())
        with zipfile.ZipFile(tampered_zip, "a") as archive:
            review_path = next(name for name in archive.namelist() if name.startswith("audio-reviews/reviews/") and second_review["review"]["review_id"] in name)
            payload = json.loads(archive.read(review_path).decode("utf-8"))
            payload["audio_evidence"]["wav_sha256"] = "0" * 64
            archive.writestr(review_path, json.dumps(payload, ensure_ascii=False))
        tampered = verify_release_zip(tampered_zip, require_audio=True, require_human_review=True)
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert audio_status == 200
    assert audio["summary"]["status"] == "passed"
    assert first_review_status == 201
    assert missing_gate_status == 409
    assert "Per-track" in missing_gate["error"]
    assert synthetic_status == 201
    assert synthetic_gate_status == 409
    assert second_review_status == 201
    assert summary_status == 200
    assert summary["summary"]["status"] == "passed"
    assert export_status == 200
    assert exported["manifest"]["audio_reviews"]["status"] == "passed"
    assert any(file["path"] == "audio-reviews/summary.json" for file in exported["manifest"]["files"])
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert marker_status == 201
    assert marker_task["status"] == "created"
    assert marker_again_status == 200
    assert marker_again["status"] == "existing"
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["audio"]["per_track_review"]["manual_accepted_track_count"] == 2
    assert write_after_sign_status == 409
    assert verify["status"] in {"passed", "warning"}
    assert _check(verify, "per_track_audio_review_evidence")["status"] == "passed"
    assert tampered["status"] == "failed"
    assert _check(tampered, "zip_duplicate_entries")["status"] == "failed"


def test_tampered_review_blocks_signoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Tampered Audio Review")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Tamper Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        review_status, review = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "ok"})
        path = Path(".musicforge") / "releases" / release_id / "audio-reviews" / f"{review['review']['review_id']}.json"
        data = read_json(path)
        data["status"] = "needs_fix"
        write_json(path, data)
        sign_status, sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True, "require_per_track_audio_review": True})
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert review_status == 201
    assert sign_status == 409
    assert "Per-track" in sign["error"]


def test_human_review_pack_import_requires_matching_wav_hash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Import Pack Audio Review")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Import Pack Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})

        suite_status, suite = request_json(server, "POST", "/api/acceptance/suites", {"name": "Import Pack Suite", "require_audio_if_renderer_configured": False})
        suite_id = suite["suite"]["suite_id"]
        case_status, case = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"song_id": "imported_track", "request": {"title": "Imported Track", "language": "English", "style": "pop", "theme": "review", "duration_seconds": 30}})
        case_id = case["case"]["case_id"]
        case_dir = Path(".musicforge") / "acceptance" / suite_id / "cases" / case_id
        track_wav = Path(".musicforge") / "projects" / project_id / "final-export" / "song.wav"
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        (case_dir / "song.wav").write_bytes(track_wav.read_bytes())
        health_status, _health = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "audio_mode": "wav", "review_mode": "manual", "notes": "Manual WAV review imported from external pack."})

        import_status, imported = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/import-human-review-pack", {"suite_id": suite_id, "mapping": [{"track_id": "track-000001", "case_id": case_id}]})
        summary_status, summary = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/refresh-summary")
        from tests.audio_fixtures import write_test_wav

        write_test_wav(case_dir / "song.wav", duration_seconds=30, amplitude=0.1)
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "audio_mode": "wav", "review_mode": "manual", "notes": "Manual WAV review no longer matches release track."})
        mismatch_status, mismatch = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/import-human-review-pack", {"suite_id": suite_id, "mapping": [{"track_id": "track-000001", "case_id": case_id}]})
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert suite_status == 201
    assert case_status == 201
    assert health_status == 200
    assert review_status == 200
    assert import_status == 201
    assert imported["imported_count"] == 1
    assert summary_status == 200
    assert summary["summary"]["status"] == "passed"
    assert mismatch_status == 409
    assert "WAV hash" in mismatch["error"]


def _check(report: dict, check_id: str) -> dict:
    for item in [*report.get("checks", []), *report.get("track_checks", [])]:
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)
