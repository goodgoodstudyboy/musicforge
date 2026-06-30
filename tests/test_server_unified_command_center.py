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
