from __future__ import annotations

from song_agent.unified_command_center_release_train import DEFAULT_REQUIRED_EVIDENCE, write_external_evidence_manifest
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_unified_command_center_release_train import _fake_evidence


def test_unified_command_center_release_train_lifecycle_api(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/unified-command-center-release-trains", {"train_id": "uct-api-life", "required_evidence": DEFAULT_REQUIRED_EVIDENCE})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/items", {"item_id": "item-001", "center_id": "ucc-api-life"})
        rows = [_fake_evidence(tmp_path, "item-001", "ucc-api-life", evidence_type) for evidence_type in DEFAULT_REQUIRED_EVIDENCE]
        manifest_path = tmp_path / "external-evidence.json"
        write_external_evidence_manifest(manifest_path, train_id="uct-api-life", items=rows)
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/refresh", {"external_evidence_manifest": str(manifest_path)})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/signoff", {"external_evidence_manifest": str(manifest_path), "signed_by": "api train lead"})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/archive/verify", {"strict": True, "require_go": True, "require_signed": True, "external_evidence_manifest": str(manifest_path)})
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/lifecycle/refresh", {"external_evidence_manifest": str(manifest_path)})
        export_status, export_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/lifecycle/export", {})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/lifecycle/zip", {})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-life/lifecycle/verify", {"strict": True, "require_current_train": True, "external_evidence_manifest": str(manifest_path)})
    finally:
        stop_test_server(server)

    assert refresh_status == 200, refresh_body
    assert refresh_body["status"] == "passed"
    assert export_status == 200, export_body
    assert zip_status == 200, zip_body
    assert verify_status == 200, verify_body
    assert verify_body["status"] == "passed", verify_body.get("verification", {}).get("blockers")
