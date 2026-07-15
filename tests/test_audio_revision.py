from __future__ import annotations

from pathlib import Path

import song_agent.domains.quality.audio_revision as audio_revision_module
from song_agent.audio_revision import CANDIDATE_INTEGRITY_EXCLUDE, _object_hash
from song_agent.projectio import read_json, write_json
from song_agent.release_verifier import verify_release_zip
from tests.test_audio_review_evidence import _signed_audio_project
from tests.audio_fixtures import write_test_wav
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def _fake_revision_render(midi_path: Path, wav_path: Path, config) -> Path:
    return write_test_wav(Path(wav_path), duration_seconds=9, amplitude=0.18)


def test_audio_revision_workbench_full_loop_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(audio_revision_module, "render_audio", _fake_revision_render)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Audio Revision Loop")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Audio Revision Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})

        review_status, review = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-reviews",
            {
                "track_id": "track-000001",
                "status": "needs_fix",
                "review_mode": "manual",
                "rating": 2,
                "playback_confirmed": True,
                "notes": "Drums are too loud.",
                "markers": [{"time_seconds": 2.0, "category": "mix_balance", "severity": "high", "message": "Drums overpower hook."}],
            },
        )
        session_status, session = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {"title": "Fix drums"})
        session_id = session["session"]["session_id"]
        detail_status, detail = request_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")
        issue = detail["issues"][0]
        issue_id = issue["issue_id"]
        generate_status, generated = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/issues/{issue_id}/candidates/generate", {"max_candidates": 2})
        candidate_id = generated["candidates"][0]["candidate_id"]
        midi_status, midi_payload = request_bytes(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/midi")
        review_candidate_status, reviewed = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True, "notes": "A/B preview is better."})
        select_status, selected = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/select")
        apply_status, applied = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/apply", {"version_name": "Audio Revision Applied"})
        assert apply_status == 200, applied
        applied_version = applied["applied_version_id"]
        release_track = applied["release"]["tracks"][0]
        project_detail_status, project_detail = request_json(server, "GET", f"/api/projects/{project_id}")

        old_review_status, old_review = request_json(server, "GET", f"/api/releases/{release_id}/audio-reviews/{review['review']['review_id']}")
        recheck_status, recheck = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Recheck accepted."})
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/refresh")
        close_status, closed = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/close")
        delivery_reset_status, _delivery_reset = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": "audio revision applied"})
        delivery_sign_status, _delivery_sign = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "tester"})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zipped = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_health": True, "require_per_track_audio_review": True, "require_audio_revision_closeout": True})
        verify = verify_release_zip(Path(".musicforge") / "releases" / release_id / "release-export.zip", require_audio=True, require_human_review=True, require_audio_revisions=True)
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert review_status == 201
    assert session_status == 201
    assert detail_status == 200
    assert issue["category"] == "mix_balance"
    assert issue["severity"] == "high"
    assert generate_status == 201
    assert generated["count"] >= 1
    assert midi_status == 200
    assert isinstance(midi_payload, (bytes, bytearray))
    assert review_candidate_status == 200
    assert reviewed["candidate"]["review"]["status"] == "accepted"
    assert select_status == 200
    assert selected["candidate"]["selected"] is True
    assert apply_status == 200
    assert release_track["version_id"] == applied_version
    assert project_detail_status == 200
    assert next(item for item in project_detail["versions"] if item["version_id"] == applied_version)["variant_type"] == "audio_revision_mix_edit"
    assert old_review_status == 200
    assert old_review["review"]["stale"] is True
    assert recheck_status == 201, recheck
    assert recheck["review"]["version_id"] == applied_version
    assert recheck["review"]["stale"] is False, recheck["review"].get("stale_reasons")
    assert refresh_status == 200
    assert refreshed["rechecked_count"] == 1
    assert close_status == 200
    assert closed["closeout"]["status"] == "passed"
    assert delivery_reset_status == 200
    assert delivery_sign_status == 200
    assert export_status == 200, exported
    assert exported["manifest"]["audio_revisions"]["status"] == "passed"
    assert any(row["path"] == "audio-revisions/summary.json" for row in exported["manifest"]["files"])
    assert zip_status == 200
    assert sign_status == 200, signoff
    assert signoff["signoff"]["acceptance_gate"]["audio"]["audio_revision"]["status"] == "passed"
    assert verify["status"] in {"passed", "warning"}, [item for item in [*verify.get("checks", []), *verify.get("track_checks", [])] if item.get("status") == "failed"]
    assert _check(verify, "audio_revision_evidence")["status"] == "passed"


def test_audio_revision_candidate_tamper_and_signed_guard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(audio_revision_module, "render_audio", _fake_revision_render)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Audio Revision Guard")
        _status, created = request_json(server, "POST", "/api/releases", {"name": "Guard Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "needs_fix", "review_mode": "manual", "rating": 2, "playback_confirmed": True, "markers": [{"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "balance"}]})
        session = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {})[1]["session"]
        session_id = session["session_id"]
        issue = request_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")[1]["issues"][0]
        generated = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/issues/{issue['issue_id']}/candidates/generate", {})[1]
        candidate_id = generated["candidates"][0]["candidate_id"]
        candidate_path = Path(".musicforge") / "releases" / release_id / "audio-revisions" / session_id / "candidates" / candidate_id / "candidate.json"
        original_candidate = read_json(candidate_path)
        unsafe_candidate = read_json(candidate_path)
        unsafe_candidate["preview"]["midi_path"] = "../outside.mid"
        unsafe_candidate["integrity_hash"] = _object_hash(unsafe_candidate, CANDIDATE_INTEGRITY_EXCLUDE)
        write_json(candidate_path, unsafe_candidate)
        unsafe_download_status, unsafe_download = request_bytes(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/midi")
        tampered_candidate = dict(original_candidate)
        tampered_candidate["strategy"] = "tampered_strategy"
        write_json(candidate_path, tampered_candidate)
        apply_status, apply_body = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/apply", {})

        clean = _signed_audio_project(server, "Audio Revision Signed Guard")
        signed_created = request_json(server, "POST", "/api/releases", {"name": "Signed Guard", "release_type": "single_pack", "primary_artist": "QA"})[1]
        signed_release_id = signed_created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{signed_release_id}/tracks", {"project_id": clean})
        request_json(server, "POST", f"/api/releases/{signed_release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{signed_release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{signed_release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{signed_release_id}/export")
        request_json(server, "POST", f"/api/releases/{signed_release_id}/export/zip")
        request_json(server, "POST", f"/api/releases/{signed_release_id}/signoff", {"signed_by": "tester", "require_audio_health": True, "require_per_track_audio_review": True})
        signed_write_status, signed_write = request_json(server, "POST", f"/api/releases/{signed_release_id}/audio-revisions", {})
    finally:
        stop_test_server(server)

    assert unsafe_download_status == 409
    assert b"error" in unsafe_download
    assert apply_status == 409
    assert "stale or tampered" in apply_body["error"]
    assert signed_write_status == 409
    assert "Signed releases" in signed_write["error"]


def test_audio_revision_high_issue_force_close_is_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(audio_revision_module, "render_audio", _fake_revision_render)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Audio Revision Force Guard")
        _status, created = request_json(server, "POST", "/api/releases", {"name": "Force Guard Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-reviews",
            {
                "track_id": "track-000001",
                "status": "needs_fix",
                "review_mode": "manual",
                "rating": 2,
                "playback_confirmed": True,
                "markers": [{"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "drums remain too loud"}],
            },
        )
        session = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {})[1]["session"]
        session_id = session["session_id"]
        close_status, close_body = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/close", {"force": True, "override_reason": "reviewed manually"})
        detail_status, detail = request_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")
    finally:
        stop_test_server(server)

    assert close_status == 409
    assert "cannot be force closed" in close_body["error"]
    assert detail_status == 200
    assert detail["session"]["status"] != "closed"
    assert "high_issue_unresolved" in " ".join(detail["closeout"]["force_blockers"])


def test_audio_revision_new_marker_after_closeout_blocks_signoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(audio_revision_module, "render_audio", _fake_revision_render)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Audio Revision Marker Coverage")
        _status, created = request_json(server, "POST", "/api/releases", {"name": "Marker Coverage Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        review = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "needs_fix", "review_mode": "manual", "rating": 2, "playback_confirmed": True, "markers": [{"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "first issue"}]})[1]
        session = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {})[1]["session"]
        session_id = session["session_id"]
        issue = request_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")[1]["issues"][0]
        candidate = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/issues/{issue['issue_id']}/candidates/generate", {})[1]["candidates"][0]
        request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate['candidate_id']}/review", {"status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate['candidate_id']}/select")
        applied = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate['candidate_id']}/apply", {})[1]
        request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "rechecked"})
        request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/refresh")
        close_status, closed = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/close")
        new_marker_status, _new_marker = request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "needs_fix", "review_mode": "manual", "rating": 2, "playback_confirmed": True, "markers": [{"time_seconds": 2.0, "category": "mix_balance", "severity": "high", "message": "new issue after closeout"}]})
        summary_status, summary = request_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/summary")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_audio_revision_closeout": True})
    finally:
        stop_test_server(server)

    assert review["review"]["review_id"]
    assert applied["applied_version_id"]
    assert close_status == 200, closed
    assert new_marker_status == 201
    assert summary_status == 200
    assert "active_markers_uncovered" in summary["summary"]["blockers"]
    assert summary["summary"]["uncovered_marker_ids"]
    assert sign_status == 409
    assert "Audio revision closeout gate failed" in signoff["error"]


def test_audio_revision_renderer_failure_blocks_candidate_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def failing_render(_midi_path: Path, _wav_path: Path, _config) -> Path:
        raise audio_revision_module.RendererError("renderer unavailable")

    monkeypatch.setattr(audio_revision_module, "render_audio", failing_render)
    server = start_test_server()
    try:
        project_id = _signed_audio_project(server, "Audio Revision Renderer Guard")
        _status, created = request_json(server, "POST", "/api/releases", {"name": "Renderer Guard Release", "release_type": "single_pack", "primary_artist": "QA"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "needs_fix", "review_mode": "manual", "rating": 2, "playback_confirmed": True, "markers": [{"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "balance"}]})
        session = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {})[1]["session"]
        session_id = session["session_id"]
        issue = request_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")[1]["issues"][0]
        generated = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/issues/{issue['issue_id']}/candidates/generate", {})[1]
        candidate = generated["candidates"][0]
        review_status, review = request_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate['candidate_id']}/review", {"status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True})
    finally:
        stop_test_server(server)

    assert generated["candidates"][0]["preview"]["audio_status"] == "failed"
    assert review_status == 409
    assert "audio preview" in review["error"]


def _check(report: dict, check_id: str) -> dict:
    for item in [*report.get("checks", []), *report.get("track_checks", [])]:
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)
