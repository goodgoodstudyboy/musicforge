from __future__ import annotations

from song_agent.unified_command_center_release_train import DEFAULT_REQUIRED_EVIDENCE, write_external_evidence_manifest
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_unified_command_center_release_train import _fake_evidence


def test_unified_command_center_release_train_handoff_api(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/unified-command-center-release-trains", {"train_id": "uct-api-handoff", "required_evidence": DEFAULT_REQUIRED_EVIDENCE})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/items", {"item_id": "item-001", "center_id": "ucc-api-handoff"})
        rows = [_fake_evidence(tmp_path, "item-001", "ucc-api-handoff", evidence_type) for evidence_type in DEFAULT_REQUIRED_EVIDENCE]
        manifest_path = tmp_path / "external-evidence.json"
        write_external_evidence_manifest(manifest_path, train_id="uct-api-handoff", items=rows)
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/refresh", {"external_evidence_manifest": str(manifest_path)})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/signoff", {"external_evidence_manifest": str(manifest_path), "signed_by": "api train lead"})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/archive/verify", {"strict": True, "require_go": True, "require_signed": True, "external_evidence_manifest": str(manifest_path)})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/lifecycle/refresh", {"external_evidence_manifest": str(manifest_path)})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/lifecycle/zip", {})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/lifecycle/verify", {"strict": True, "require_current_train": True, "external_evidence_manifest": str(manifest_path)})
        create_status, create_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/handoffs", {"handoff_id": "rth-api", "external_evidence_manifest": str(manifest_path)})
        sign_status, sign_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/handoffs/rth-api/signoff", {"signed_by": "api handoff chair"})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/handoffs/rth-api/zip", {})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-handoff/handoffs/rth-api/verify", {"strict": True, "require_current": True, "require_lifecycle": True, "require_signed": True})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert create_body["status"] == "ready", create_body
    assert sign_status == 200, sign_body
    assert sign_body["status"] == "signed"
    assert zip_status == 200, zip_body
    assert verify_status == 200, verify_body
    assert verify_body["status"] == "passed", verify_body.get("verification", {}).get("blockers")
