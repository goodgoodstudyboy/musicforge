from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _release_check_report(path: Path) -> Path:
    payload = {
        "ok": True,
        "summary": {"total": 1, "passed": 1, "failed": 0},
        "results": [{"check_id": "synthetic.passed", "status": "passed"}],
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
