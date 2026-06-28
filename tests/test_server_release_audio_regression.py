from __future__ import annotations

import json

from song_agent.projectio import read_json
from song_agent.releases import stable_hash
from tests.test_release_audio_regression import _configure_regression, _prepare_signed_timeline
from tests.test_release_audio_timeline import _append_unexpected_file_to_zip
from tests.test_server_releases import request_json, start_test_server, stop_test_server


def test_release_audio_regression_api_refresh_signoff_zip_verify(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression API Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression API Track")
        config_status, config = request_json(
            server,
            "POST",
            f"/api/releases/{current_release_id}/audio-regression/configure",
            {
                "baseline_release_id": baseline_release_id,
                "baseline_timeline": str(baseline_store.zip_path(baseline_release_id, baseline_timeline_id)),
                "baseline_timeline_verification_report": str(baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id)),
                "baseline_certification": str(baseline_store.certification_store.zip_path(baseline_release_id)),
                "baseline_certification_verification_report": str(baseline_store.certification_store.verification_report_path(baseline_release_id)),
                "current_timeline": str(current_store.zip_path(current_release_id, current_timeline_id)),
                "current_timeline_verification_report": str(current_store.verification_report_path(current_release_id, current_timeline_id)),
                "current_certification": str(current_store.certification_store.zip_path(current_release_id)),
                "current_certification_verification_report": str(current_store.certification_store.verification_report_path(current_release_id)),
            },
        )
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{current_release_id}/audio-regression/refresh")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{current_release_id}/audio-regression/signoff", {"signed_by": "QA", "role": "developer"})
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{current_release_id}/audio-regression/zip")
        verify_status, verified = request_json(server, "POST", f"/api/releases/{current_release_id}/audio-regression/verify", {"strict": True, "require_passed": True, "require_signed": True, "require_current": True, "require_baseline_current": True})
        detail_status, detail = request_json(server, "GET", f"/api/releases/{current_release_id}/audio-regression")
    finally:
        stop_test_server(server)

    assert config_status == 201
    assert config["config"]["baseline"]["release_id"] == baseline_release_id
    assert refresh_status == 200
    assert refreshed["report"]["status"] == "passed"
    assert sign_status == 201
    assert signed["status"] == "signed"
    assert zip_status == 200
    assert zipped["zip_sha256"]
    assert verify_status == 200
    assert verified["status"] == "passed", verified.get("blockers")
    assert detail_status == 200
    assert detail["report"]["status"] == "passed"


def test_release_signoff_requires_audio_regression_even_when_forced(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression Force Gate Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression Force Gate Track")
        _configure_regression(server.release_audio_regression_store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        server.release_audio_regression_store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        request_json(server, "POST", f"/api/releases/{current_release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{current_release_id}/export")
        request_json(server, "POST", f"/api/releases/{current_release_id}/export/zip")
        _append_unexpected_file_to_zip(current_store.certification_store.zip_path(current_release_id))
        signoff_status, signoff = request_json(
            server,
            "POST",
            f"/api/releases/{current_release_id}/signoff",
            {
                "signed_by": "QA",
                "force": True,
                "override_reason": "force must not bypass audio regression",
                "require_release_audio_regression_guard": True,
                "require_release_audio_regression_signed": True,
            },
        )
    finally:
        stop_test_server(server)

    assert signoff_status == 409
    gate = signoff["acceptance_gate"]["release_audio_regression_guard"]
    assert gate["status"] == "failed"
    assert gate["hard_block"] is True


def test_release_audio_regression_api_export_rejects_signed_report_tamper(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression API Signed Tamper")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression API Signed Tamper")
        _configure_regression(server.release_audio_regression_store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        server.release_audio_regression_store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        report_path = server.release_audio_regression_store.report_path(current_release_id)
        report = read_json(report_path)
        report["summary"]["blocker_count"] = 42
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        export_status, export_body = request_json(server, "POST", f"/api/releases/{current_release_id}/audio-regression/export")
        zip_status, zip_body = request_json(server, "POST", f"/api/releases/{current_release_id}/audio-regression/zip")
    finally:
        stop_test_server(server)

    assert export_status == 409
    assert "regression_report_hash" in export_body["error"]
    assert zip_status == 409
    assert "regression_report_hash" in zip_body["error"]
