from __future__ import annotations

from pathlib import Path

from song_agent.unified_release_program import write_external_evidence_manifest
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_unified_release_program import _signed_handoff_fixture


def _program_manifest(tmp_path: Path, program_id: str, item_id: str, handoff: dict) -> Path:
    manifest_path = tmp_path / f"{program_id}-external-evidence.json"
    write_external_evidence_manifest(
        manifest_path,
        program_id=program_id,
        items=[
            {
                "item_id": item_id,
                "train_id": handoff["train_id"],
                "handoff_id": handoff["handoff_id"],
                "handoff_zip": str(handoff["handoff_zip"]),
                "handoff_verification_report": str(handoff["handoff_verification_report"]),
                "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
            }
        ],
    )
    return manifest_path


def test_unified_release_program_api_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    handoff = _signed_handoff_fixture(tmp_path)
    manifest_path = _program_manifest(tmp_path, "urp-api", "train-a", handoff)
    server = start_test_server()
    try:
        create_status, create_body = request_json(server, "POST", "/api/unified-release-programs", {"program_id": "urp-api", "name": "API Program"})
        add_status, add_body = request_json(
            server,
            "POST",
            "/api/unified-release-programs/urp-api/items",
            {
                "item_id": "train-a",
                "train_id": handoff["train_id"],
                "handoff_id": handoff["handoff_id"],
                "handoff_zip": str(handoff["handoff_zip"]),
                "handoff_verification_report": str(handoff["handoff_verification_report"]),
                "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
            },
        )
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-release-programs/urp-api/refresh", {"external_evidence_manifest": str(manifest_path)})
        signoff_status, signoff_body = request_json(server, "POST", "/api/unified-release-programs/urp-api/signoff", {"external_evidence_manifest": str(manifest_path), "signed_by": "program owner"})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-release-programs/urp-api/zip", {})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-release-programs/urp-api/verify", {"strict": True, "require_current": True, "require_signed": True, "external_evidence_manifest": str(manifest_path)})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert add_status == 201, add_body
    assert refresh_status == 200, refresh_body
    assert refresh_body["report"]["status"] == "ready"
    assert signoff_status == 201, signoff_body
    assert signoff_body["signoff"]["status"] == "signed"
    assert zip_status == 200, zip_body
    assert verify_status == 200, verify_body
    assert verify_body["verification"]["status"] == "passed", verify_body["verification"].get("blockers")


def test_unified_release_program_api_deferred_only_signoff_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        create_status, create_body = request_json(server, "POST", "/api/unified-release-programs", {"program_id": "urp-deferred"})
        add_status, add_body = request_json(server, "POST", "/api/unified-release-programs/urp-deferred/items", {"item_id": "train-deferred", "train_id": "uct-deferred", "handoff_id": "rth-deferred", "type": "deferred"})
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-release-programs/urp-deferred/refresh", {})
        signoff_status, signoff_body = request_json(server, "POST", "/api/unified-release-programs/urp-deferred/signoff", {"signed_by": "program owner"})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert add_status == 201, add_body
    assert refresh_status == 200, refresh_body
    assert refresh_body["report"]["status"] == "blocked"
    assert signoff_status == 409
    assert "ready" in signoff_body["error"]
