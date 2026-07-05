from __future__ import annotations

from pathlib import Path

from song_agent.unified_command_center_release_train import DEFAULT_REQUIRED_EVIDENCE, write_external_evidence_manifest
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_unified_command_center_release_train import _fake_evidence


def test_unified_command_center_release_train_change_control_api_reset_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/unified-command-center-release-trains", {"train_id": "uct-api-cc", "required_evidence": DEFAULT_REQUIRED_EVIDENCE})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/items", {"item_id": "item-001", "center_id": "ucc-api"})
        rows = [_fake_evidence(tmp_path, "item-001", "ucc-api", evidence_type) for evidence_type in DEFAULT_REQUIRED_EVIDENCE]
        manifest_path = tmp_path / "external-evidence.json"
        write_external_evidence_manifest(manifest_path, train_id="uct-api-cc", items=rows)
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/refresh", {"external_evidence_manifest": str(manifest_path)})
        signoff_status, signoff_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/signoff", {"external_evidence_manifest": str(manifest_path), "signed_by": "api train lead"})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/archive/zip", {})
        request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/archive/verify", {"strict": True, "require_go": True, "require_signed": True, "external_evidence_manifest": str(manifest_path)})
        create_status, create_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/changes", {"external_evidence_manifest": str(manifest_path), "change": ["refresh evidence"]})
        request_id = create_body["change_request"]["change_request_id"]
        approve_status, approve_body = request_json(server, "POST", f"/api/unified-command-center-release-trains/uct-api-cc/changes/{request_id}/approve", {"external_evidence_manifest": str(manifest_path), "approved_by": "api owner"})
        reset_status, reset_body = request_json(server, "POST", f"/api/unified-command-center-release-trains/uct-api-cc/changes/{request_id}/reset", {"external_evidence_manifest": str(manifest_path), "reset_by": "api owner"})
        mutation_status, mutation_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api-cc/refresh", {"external_evidence_manifest": str(manifest_path)})
        second_reset_status, second_reset_body = request_json(server, "POST", f"/api/unified-command-center-release-trains/uct-api-cc/changes/{request_id}/reset", {"external_evidence_manifest": str(manifest_path)})
    finally:
        stop_test_server(server)

    assert signoff_status == 201, signoff_body
    assert create_status == 201, create_body
    assert approve_status == 200, approve_body
    assert reset_status == 200, reset_body
    assert reset_body["status"] == "applied"
    assert mutation_status == 200, mutation_body
    assert mutation_body["status"] == "go"
    assert second_reset_status == 409, second_reset_body
    assert Path(".musicforge/unified-command-trains/uct-api-cc/archive-history").exists()
