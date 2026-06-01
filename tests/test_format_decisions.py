from __future__ import annotations

import json
import zipfile

from song_agent.format_decisions import FormatDecisionStore, format_report_integrity_ok
from tests.test_server_audio_encoding import _FixtureEncoderRunner
from tests.test_server_audio_encoding import _check as _verify_check
from song_agent.distribution_verifier import verify_distribution_package
from song_agent.release_verifier import verify_release_zip
from tests.test_distribution_encoded_audio import _export_metadata
from tests.test_distribution_encoded_audio import _rewrite_zip
from tests.test_mastering_qa import _signed_project
from tests.test_release_audio import _add_final_export_audio
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_format_decision_store_blocks_stale_report_after_new_review(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _prepared_release(server, profiles=["mp3_320"])
        store = FormatDecisionStore(server.release_store, project_store=server.project_store, encoding_store=server.audio_encoding_store, distribution_store=server.distribution_store)
        session = store.create_session(release_id, {"profiles": ["mp3_320"]})
        matrix = store.build_matrix(release_id, session["session_id"])
        recommendation = store.build_recommendation(release_id, session["session_id"])
        selected = store.select_profiles(release_id, session["session_id"], {"selected_profiles": ["mp3_320"], "reason": "MP3 delivery accepted."})
        report = store.build_report(release_id, session["session_id"])
        request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/reviews", {"profile_id": "mp3_320", "track_id": "track-000001", "status": "accepted", "review_mode": "manual", "reviewer": {"name": "second reviewer"}, "rating": 5, "playback_confirmed": True})
        stale_report = store.read_report(release_id, session["session_id"])
    finally:
        stop_test_server(server)

    assert matrix["profiles"][0]["profile_id"] == "mp3_320"
    assert recommendation["selected_defaults"] == ["mp3_320"]
    assert selected["selected_profiles"] == ["mp3_320"]
    assert report["status"] == "passed"
    assert format_report_integrity_ok(report)
    assert stale_report["stale"] is True
    assert "source_changed" in stale_report["stale_reasons"] or "matrix_stale" in stale_report["stale_reasons"]


def test_format_decision_api_release_signoff_and_verifier(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _prepared_release(server, profiles=["mp3_320", "flac_lossless"])
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions", {"profiles": ["mp3_320", "flac_lossless"]})
        session_id = created["session"]["session_id"]
        matrix_status, matrix = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/matrix")
        recommend_status, recommendation = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/recommend")
        select_status, _selected = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/select", {"selected_profiles": ["mp3_320"], "archive_profiles": ["flac_lossless"], "reason": "MP3 delivery plus FLAC archive."})
        report_status, report = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/report")
        active_status, _active = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/activate")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        missing_selection_status, missing_selection = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "require_encoded_audio_review": True, "require_format_decision": True, "required_audio_format_profiles": ["flac_lossless"]})
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_encoded_audio": True, "require_encoded_audio_review": True, "require_format_decision": True, "required_audio_format_profiles": ["mp3_320"]})
        verify = verify_release_zip(server.release_store.zip_path(release_id), require_encoded_audio=True, require_encoded_audio_review=True, require_format_decision=True, required_audio_format_profiles=["mp3_320"])
        tampered_zip = _rewrite_zip(server.release_store.zip_path(release_id), tmp_path / "tampered-format-decision.zip", {"format-decision/decision-report.json": _tamper_decision_report})
        tampered = verify_release_zip(tampered_zip, require_format_decision=True, required_audio_format_profiles=["mp3_320"])
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert matrix_status == 200
    assert matrix["matrix"]["profiles"][0]["profile_id"] in {"flac_lossless", "mp3_320"}
    assert recommend_status == 200
    assert recommendation["recommendation"]["recommendations"]
    assert select_status == 200
    assert report_status == 200
    assert report["report"]["status"] == "passed"
    assert active_status == 200
    assert export_status == 200
    assert export["manifest"]["format_decision"]["status"] == "passed"
    assert missing_selection_status == 409
    assert "format decision" in missing_selection["error"].lower()
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["format_decision"]["status"] == "passed"
    assert verify["status"] in {"passed", "warning"}
    assert _verify_check(verify, "format_decision_evidence")["status"] == "passed"
    assert tampered["status"] == "failed"
    assert _verify_check(tampered, "format_decision_evidence")["status"] == "failed"


def test_format_decision_distribution_target_gate_and_verifier(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _prepared_release(server, profiles=["mp3_320", "flac_lossless", "aac_256"])
        _export_metadata(server, release_id)
        _session_id = _activate_decision(server, release_id, selected=["mp3_320"], archive=["flac_lossless"], rejected=["aac_256"])
        ok_target_status, ok_target = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/distribution/targets",
            {
                "profile_id": "demo_pitch",
                "name": "MP3 Target",
                "options": {
                    "require_release_signed": False,
                    "require_release_zip_verified": False,
                    "require_metadata_export": False,
                    "require_artwork": False,
                    "require_encoded_audio": True,
                    "require_encoded_audio_review": True,
                    "require_format_decision": True,
                    "audio_format_profiles": ["mp3_320"],
                },
            },
        )
        ok_target_id = ok_target["target"]["target_id"]
        _activate_decision(server, release_id, selected=["mp3_320"], archive=["flac_lossless"], rejected=["aac_256"])
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{ok_target_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{ok_target_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{ok_target_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{ok_target_id}/signoff", {"signed_by": "tester", "require_encoded_audio_review": True, "require_format_decision": True})
        package_id = export["manifest"]["package_id"]
        verify = verify_distribution_package(server.distribution_store.package_zip_path(release_id, package_id), require_encoded_audio=True, require_encoded_audio_review=True, require_format_decision=True)
        bad_target_status, bad_target = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/distribution/targets",
            {
                "profile_id": "demo_pitch",
                "name": "AAC Target",
                "options": {
                    "require_release_signed": False,
                    "require_release_zip_verified": False,
                    "require_metadata_export": False,
                    "require_artwork": False,
                    "require_encoded_audio": True,
                    "require_encoded_audio_review": True,
                    "require_format_decision": True,
                    "audio_format_profiles": ["aac_256"],
                },
            },
        )
        bad_target_id = bad_target["target"]["target_id"]
        _activate_decision(server, release_id, selected=["mp3_320"], archive=["flac_lossless"], rejected=["aac_256"])
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{bad_target_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{bad_target_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{bad_target_id}/export/zip")
        bad_sign_status, bad_sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{bad_target_id}/signoff", {"signed_by": "tester", "require_encoded_audio_review": True, "require_format_decision": True})
    finally:
        stop_test_server(server)

    assert ok_target_status == 201
    assert export_status == 201
    assert export["manifest"]["format_decision"]["status"] == "passed"
    assert sign_status == 200
    assert signoff["signoff"]["format_decision"]["status"] == "passed"
    assert verify["status"] in {"passed", "warning"}
    assert _verify_check(verify, "distribution_format_decision_evidence")["status"] == "passed"
    assert bad_target_status == 201
    assert bad_sign_status == 409
    assert "format decision" in bad_sign["error"].lower()


def _prepared_release(server, *, profiles: list[str]) -> str:
    project_id = _signed_project(server, "Format Decision Track")
    _add_final_export_audio(server, project_id, duration_seconds=30)
    _, release = request_json(server, "POST", "/api/releases", {"name": "Format Decision Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
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
    server.audio_encoding_store.runner = _FixtureEncoderRunner()
    request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/render", {"profile_ids": profiles})
    request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/health", {"profile_ids": profiles})
    for profile_id in profiles:
        request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/reviews", {"profile_id": profile_id, "track_id": "track-000001", "status": "accepted", "review_mode": "manual", "reviewer": {"name": f"{profile_id} reviewer"}, "rating": 5, "playback_confirmed": True})
    request_json(server, "POST", f"/api/releases/{release_id}/encoded-audio/acceptance/refresh", {"profile_ids": profiles})
    return release_id


def _activate_decision(server, release_id: str, *, selected: list[str], archive: list[str] | None = None, rejected: list[str] | None = None) -> str:
    profiles = sorted(set([*selected, *(archive or []), *(rejected or [])]))
    _status, created = request_json(server, "POST", f"/api/releases/{release_id}/format-decisions", {"profiles": profiles})
    session_id = created["session"]["session_id"]
    request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/matrix")
    request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/recommend")
    request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/select", {"selected_profiles": selected, "archive_profiles": archive or [], "rejected_profiles": rejected or [], "reason": "Distribution format coverage."})
    request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/report")
    request_json(server, "POST", f"/api/releases/{release_id}/format-decisions/{session_id}/activate")
    return session_id


def _tamper_decision_report(data: bytes) -> bytes:
    payload = json.loads(data.decode("utf-8"))
    payload.setdefault("decision", {})["selected_profiles"] = ["flac_lossless"]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
