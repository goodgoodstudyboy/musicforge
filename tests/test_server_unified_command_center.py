from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _release_check_report(path: Path, *, ok: bool = True) -> Path:
    payload = {
        "ok": ok,
        "summary": {"total": 1, "passed": 1 if ok else 0, "failed": 0 if ok else 1},
        "results": [{"check_id": "synthetic.passed" if ok else "synthetic.failed", "status": "passed" if ok else "failed"}],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_unified_command_center_api_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_check = _release_check_report(tmp_path / "release-check.json")
    server = start_test_server()
    try:
        create_status, create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers",
            {
                "center_id": "ucc-api",
                "requirements": {
                    "audio-command-center": False,
                    "trust-operations-hub": False,
                    "public-trust-center": False,
                    "ga-readiness": False,
                    "release-check": True,
                },
            },
        )
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api/refresh", {"release_check_report": str(release_check)})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api/zip", {"release_check_report": str(release_check)})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api/verify", {"strict": True, "require_ready": True, "release_check_report": str(release_check)})
        detail_status, detail_body = request_json(server, "GET", "/api/unified-command-centers/ucc-api")
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert refresh_status == 200, refresh_body
    assert refresh_body["report"]["status"] == "ready"
    assert zip_status == 200, zip_body
    assert Path(zip_body["zip_path"]).exists()
    assert verify_status == 200, verify_body
    assert verify_body["verification"]["status"] == "passed", verify_body["verification"].get("blockers")
    assert detail_status == 200
    assert detail_body["center"]["center_id"] == "ucc-api"


def test_unified_command_center_api_signoff_archive_handoff(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_check = _release_check_report(tmp_path / "release-check.json")
    server = start_test_server()
    try:
        create_status, create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers",
            {
                "center_id": "ucc-api-signoff",
                "requirements": {
                    "audio-command-center": False,
                    "trust-operations-hub": False,
                    "public-trust-center": False,
                    "ga-readiness": False,
                    "release-check": True,
                },
            },
        )
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/zip", {"release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/verify", {"strict": True, "require_ready": True, "release_check_report": str(release_check)})
        signoff_status, signoff_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/signoff", {"signed_by": "release lead", "reason": "ready"})
        archive_zip_status, archive_zip_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/archive/zip", {})
        archive_verify_status, archive_verify_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/archive/verify", {"strict": True})
        handoff_zip_status, handoff_zip_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/handoff/zip", {})
        handoff_verify_status, handoff_verify_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/handoff/verify", {"strict": True})
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-signoff/refresh", {"release_check_report": str(release_check)})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert signoff_status == 200, signoff_body
    assert signoff_body["signoff"]["status"] == "signed"
    assert archive_zip_status == 200, archive_zip_body
    assert Path(archive_zip_body["zip_path"]).exists()
    assert archive_verify_status == 200, archive_verify_body
    assert archive_verify_body["verification"]["status"] == "passed"
    assert handoff_zip_status == 200, handoff_zip_body
    assert Path(handoff_zip_body["zip_path"]).exists()
    assert handoff_verify_status == 200, handoff_verify_body
    assert handoff_verify_body["verification"]["status"] == "passed"
    assert refresh_status == 409, refresh_body


def test_unified_command_center_api_continuous_review_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_check = _release_check_report(tmp_path / "release-check.json")
    server = start_test_server()
    try:
        create_status, create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers",
            {
                "center_id": "ucc-api-review",
                "requirements": {
                    "audio-command-center": False,
                    "trust-operations-hub": False,
                    "public-trust-center": False,
                    "ga-readiness": False,
                    "release-check": True,
                },
            },
        )
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/zip", {"release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/verify", {"strict": True, "require_ready": True, "release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/signoff", {"signed_by": "release lead", "reason": "ready"})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/archive/verify", {"strict": True})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/handoff/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/handoff/verify", {"strict": True})
        review_create_status, review_create_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-review/continuous-reviews", {"created_by": "qa"})
        review_id = review_create_body["plan"]["review_id"]
        review_run_status, review_run_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-review/continuous-reviews/{review_id}/run", {})
        review_zip_status, review_zip_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-review/continuous-reviews/{review_id}/zip", {})
        review_verify_status, review_verify_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-review/continuous-reviews/{review_id}/verify", {"strict": True})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert review_create_status == 201, review_create_body
    assert review_run_status == 200, review_run_body
    assert review_run_body["status"] == "passed"
    assert review_zip_status == 200, review_zip_body
    assert Path(review_zip_body["zip_path"]).exists()
    assert review_verify_status == 200, review_verify_body
    assert review_verify_body["verification"]["status"] == "passed"


def test_unified_command_center_api_evidence_review_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_check = _release_check_report(tmp_path / "release-check.json")
    server = start_test_server()
    try:
        create_status, create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers",
            {
                "center_id": "ucc-api-evidence-review",
                "requirements": {
                    "audio-command-center": False,
                    "trust-operations-hub": False,
                    "public-trust-center": False,
                    "ga-readiness": False,
                    "release-check": True,
                },
            },
        )
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/zip", {"release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/verify", {"strict": True, "require_ready": True, "release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/signoff", {"signed_by": "release lead", "reason": "ready"})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/archive/verify", {"strict": True})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/handoff/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/handoff/verify", {"strict": True})
        review_create_status, review_create_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/continuous-reviews", {"review_id": "uccrv-clear", "created_by": "qa"})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/continuous-reviews/uccrv-clear/run", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/continuous-reviews/uccrv-clear/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/continuous-reviews/uccrv-clear/verify", {"strict": True})
        evidence_create_status, evidence_create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews",
            {"review_id": "uccer-api", "continuous_review_id": "uccrv-clear", "release_check_report": str(release_check)},
        )
        replay_status, replay_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/replay", {"release_check_report": str(release_check)})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/zip", {})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/verify", {"strict": True, "release_check_report": str(release_check)})
        naked_status, naked_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/responses/import", {"response_id": "naked", "result": "accepted"})
        response_status, response_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/responses/import",
            {
                "response_id": "response-001",
                "result": "accepted",
                "review_pack_id": "uccer-api",
                "review_pack_zip_sha256": zip_body["zip_sha256"],
                "review_pack_manifest_hash": verify_body["summary"]["manifest_hash"],
                "review_pack_source_hash": evidence_create_body["review"]["source"]["source_hash"],
                "replay_result_hash": replay_body["replay_result"]["integrity_hash"],
                "reviewer": {"name": "External Reviewer", "organization": "QA", "role": "reviewer"},
                "findings": [],
            },
        )
        acceptance_status, acceptance_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/responses/response-001/accepted-evidence", {})
        evidence_id = acceptance_body["evidence_id"]
        acceptance_verify_status, acceptance_verify_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-evidence-review/evidence-reviews/uccer-api/accepted-evidence/{evidence_id}/verify", {"strict": True})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert review_create_status == 201, review_create_body
    assert evidence_create_status == 201, evidence_create_body
    assert replay_status == 200, replay_body
    assert replay_body["status"] == "passed"
    assert zip_status == 200, zip_body
    assert Path(zip_body["zip_path"]).exists()
    assert verify_status == 200, verify_body
    assert verify_body["verification"]["status"] == "passed", verify_body["verification"].get("blockers")
    assert naked_status == 409, naked_body
    assert response_status == 201, response_body
    assert response_body["response"]["status"] == "current"
    assert acceptance_status == 201, acceptance_body
    assert acceptance_verify_status == 200, acceptance_verify_body
    assert acceptance_verify_body["verification"]["status"] == "passed", acceptance_verify_body["verification"].get("blockers")


def test_unified_command_center_api_continuous_review_blocks_failed_release_check(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_check = _release_check_report(tmp_path / "release-check.json")
    failed_release_check = _release_check_report(tmp_path / "release-check-failed.json", ok=False)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/unified-command-centers",
            {
                "center_id": "ucc-api-review-failed",
                "requirements": {
                    "audio-command-center": False,
                    "trust-operations-hub": False,
                    "public-trust-center": False,
                    "ga-readiness": False,
                    "release-check": True,
                },
            },
        )
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/zip", {"release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/verify", {"strict": True, "require_ready": True, "release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/signoff", {"signed_by": "release lead", "reason": "ready"})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/archive/verify", {"strict": True})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/handoff/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-review-failed/handoff/verify", {"strict": True})
        review_create_status, review_create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers/ucc-api-review-failed/continuous-reviews",
            {"created_by": "qa", "release_check_report": str(release_check)},
        )
        review_id = review_create_body["plan"]["review_id"]
        review_run_status, review_run_body = request_json(
            server,
            "POST",
            f"/api/unified-command-centers/ucc-api-review-failed/continuous-reviews/{review_id}/run",
            {"release_check_report": str(failed_release_check)},
        )
    finally:
        stop_test_server(server)

    assert review_create_status == 201, review_create_body
    assert review_run_status == 200, review_run_body
    assert review_run_body["ok"] is False
    assert review_run_body["status"] == "failed"
    assert review_run_body["drift_report"]["drifts"][0]["component_type"] == "release_check"


def test_unified_command_center_api_drift_response_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_check = _release_check_report(tmp_path / "release-check.json")
    failed_release_check = _release_check_report(tmp_path / "release-check-failed.json", ok=False)
    server = start_test_server()
    try:
        request_json(
            server,
            "POST",
            "/api/unified-command-centers",
            {
                "center_id": "ucc-api-drift-response",
                "requirements": {
                    "audio-command-center": False,
                    "trust-operations-hub": False,
                    "public-trust-center": False,
                    "ga-readiness": False,
                    "release-check": True,
                },
            },
        )
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/zip", {"release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/verify", {"strict": True, "require_ready": True, "release_check_report": str(release_check)})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/signoff", {"signed_by": "release lead", "reason": "ready"})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/archive/verify", {"strict": True})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/handoff/zip", {})
        request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/handoff/verify", {"strict": True})
        failed_create_status, failed_create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers/ucc-api-drift-response/continuous-reviews",
            {"release_check_report": str(release_check)},
        )
        failed_review_id = failed_create_body["plan"]["review_id"]
        failed_run_status, failed_run_body = request_json(
            server,
            "POST",
            f"/api/unified-command-centers/ucc-api-drift-response/continuous-reviews/{failed_review_id}/run",
            {"release_check_report": str(failed_release_check)},
        )
        request_json(
            server,
            "POST",
            f"/api/unified-command-centers/ucc-api-drift-response/continuous-reviews/{failed_review_id}/zip",
            {"release_check_report": str(failed_release_check)},
        )
        request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/continuous-reviews/{failed_review_id}/verify", {"strict": True})
        response_create_status, response_create_body = request_json(
            server,
            "POST",
            "/api/unified-command-centers/ucc-api-drift-response/drift-responses",
            {"source_review_id": failed_review_id, "created_by": "qa"},
        )
        response_id = response_create_body["case"]["response_id"]
        run_status, run_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/drift-responses/{response_id}/run-safe", {})
        manual_ids = [row["item_id"] for row in response_create_body["queue"]["items"] if not row.get("safe")]
        for index, item_id in enumerate(manual_ids, start=1):
            cr_status, cr_body = request_json(
                server,
                "POST",
                f"/api/unified-command-centers/ucc-api-drift-response/drift-responses/{response_id}/bind-cr",
                {"item_id": item_id, "change_request_id": f"cr-{index:03d}", "status": "approved", "approved_by": "reviewer"},
            )
            assert cr_status == 200, cr_body
        clear_create_status, clear_create_body = request_json(server, "POST", "/api/unified-command-centers/ucc-api-drift-response/continuous-reviews", {})
        clear_review_id = clear_create_body["plan"]["review_id"]
        clear_run_status, clear_run_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/continuous-reviews/{clear_review_id}/run", {})
        request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/continuous-reviews/{clear_review_id}/zip", {})
        request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/continuous-reviews/{clear_review_id}/verify", {"strict": True})
        bind_status, bind_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/drift-responses/{response_id}/bind-recheck", {"recheck_review_id": clear_review_id})
        close_status, close_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/drift-responses/{response_id}/closeout", {"closed_by": "qa"})
        zip_status, zip_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/drift-responses/{response_id}/zip", {})
        verify_status, verify_body = request_json(server, "POST", f"/api/unified-command-centers/ucc-api-drift-response/drift-responses/{response_id}/verify", {"strict": True})
    finally:
        stop_test_server(server)

    assert failed_create_status == 201, failed_create_body
    assert failed_run_status == 200, failed_run_body
    assert failed_run_body["status"] == "failed"
    assert response_create_status == 201, response_create_body
    assert run_status == 200, run_body
    assert clear_create_status == 201, clear_create_body
    assert clear_run_status == 200, clear_run_body
    assert clear_run_body["status"] == "passed"
    assert bind_status == 200, bind_body
    assert close_status == 200, close_body
    assert close_body["status"] == "closed"
    assert zip_status == 200, zip_body
    assert Path(zip_body["zip_path"]).exists()
    assert verify_status == 200, verify_body
    assert verify_body["verification"]["status"] == "passed"
