from __future__ import annotations

from pathlib import Path

from song_agent.unified_release_program import write_external_evidence_manifest
from song_agent.unified_release_program_handoff import UnifiedReleaseProgramHandoffStore, write_handoff_external_evidence_manifest
from song_agent.unified_release_program_operations import UnifiedReleaseProgramOperationsStore
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_unified_release_program import _signed_handoff_fixture
from tests.test_unified_release_program_handoff import _accepted_manifest_row, _review_response


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


def _handoff_manifest(tmp_path: Path, store: UnifiedReleaseProgramHandoffStore, ops_store: UnifiedReleaseProgramOperationsStore, program_id: str, program_manifest_path: Path, accepted: list[dict] | None = None) -> Path:
    manifest_path = tmp_path / "handoff-external-evidence.json"
    rows = [
        {
            "evidence_id": "program-current",
            "evidence_type": "unified_release_program",
            "component_id": program_id,
            "program_zip": str(store.program_store.zip_path(program_id)),
            "program_verification_report": str(store.program_store.verification_report_path(program_id)),
            "program_signoff_binding": str(store.program_store.signoff_binding_path(program_id)),
            "program_external_evidence_manifest": str(program_manifest_path),
        },
        {
            "evidence_id": "program-operations",
            "evidence_type": "unified_release_program_operations",
            "component_id": program_id,
            "operations_zip": str(ops_store.archive_zip_path(program_id)),
            "operations_verification_report": str(ops_store.archive_verification_report_path(program_id)),
            "program_zip": str(store.program_store.zip_path(program_id)),
            "program_verification_report": str(store.program_store.verification_report_path(program_id)),
            "program_signoff_binding": str(store.program_store.signoff_binding_path(program_id)),
            "program_external_evidence_manifest": str(program_manifest_path),
        },
    ]
    rows.extend(accepted or [])
    write_handoff_external_evidence_manifest(manifest_path, program_id=program_id, handoff_id="uph-000001", items=rows)
    return manifest_path


def test_unified_release_program_handoff_api_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    handoff = _signed_handoff_fixture(tmp_path)
    program_manifest_path = _program_manifest(tmp_path, "urp-handoff-api", "train-a", handoff)
    store = UnifiedReleaseProgramHandoffStore()
    ops_store = UnifiedReleaseProgramOperationsStore(store.program_store)
    server = start_test_server()
    try:
        create_status, create_body = request_json(server, "POST", "/api/unified-release-programs", {"program_id": "urp-handoff-api", "name": "API Handoff Program"})
        add_status, add_body = request_json(
            server,
            "POST",
            "/api/unified-release-programs/urp-handoff-api/items",
            {
                "item_id": "train-a",
                "train_id": handoff["train_id"],
                "handoff_id": handoff["handoff_id"],
                "handoff_zip": str(handoff["handoff_zip"]),
                "handoff_verification_report": str(handoff["handoff_verification_report"]),
                "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
            },
        )
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/refresh", {"external_evidence_manifest": str(program_manifest_path)})
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/signoff", {"external_evidence_manifest": str(program_manifest_path), "signed_by": "program owner"})
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/zip", {})
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/verify", {"strict": True, "require_current": True, "require_signed": True, "external_evidence_manifest": str(program_manifest_path)})
        program_payload = {
            "external_evidence_manifest": str(program_manifest_path),
            "program_zip": str(store.program_store.zip_path("urp-handoff-api")),
            "program_verification_report": str(store.program_store.verification_report_path("urp-handoff-api")),
            "program_signoff_binding": str(store.program_store.signoff_binding_path("urp-handoff-api")),
        }
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/operations/continuous-review/refresh", program_payload)
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/operations/lifecycle/refresh", program_payload)
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/operations/archive/zip", program_payload)
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/operations/archive/verify", program_payload)
        handoff_manifest_path = _handoff_manifest(tmp_path, store, ops_store, "urp-handoff-api", program_manifest_path)
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/refresh", {"external_evidence_manifest": str(handoff_manifest_path)})
        pack_status, pack_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/review-pack", {"audience": "release_owner"})
        pack_id = pack_body["review_pack"]["review_pack_id"]
        pack_zip_status, _pack_zip_body = request_json(server, "POST", f"/api/unified-release-programs/urp-handoff-api/handoff/review-packs/{pack_id}/zip", {})
        response_status, response_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/responses/import", _review_response(store, "urp-handoff-api", pack_id))
        response_id = response_body["response"]["response_id"]
        accepted_status, accepted_body = request_json(server, "POST", f"/api/unified-release-programs/urp-handoff-api/handoff/responses/{response_id}/accepted-evidence", {})
        evidence_id = accepted_body["evidence"]["evidence_id"]
        accepted_manifest = _accepted_manifest_row(store, "urp-handoff-api", evidence_id, response_id)
        handoff_manifest_path = _handoff_manifest(tmp_path, store, ops_store, "urp-handoff-api", program_manifest_path, [accepted_manifest])
        request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/refresh", {"external_evidence_manifest": str(handoff_manifest_path)})
        board_status, board_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/decision-board/refresh", {})
        signoff_status, signoff_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/signoff", {"signed_by": "handoff chair", "role": "release_owner"})
        zip_status, _zip_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/archive/zip", {})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-release-programs/urp-handoff-api/handoff/archive/verify", {"external_evidence_manifest": str(handoff_manifest_path), "handoff_signoff_binding": str(store.signoff_binding_path("urp-handoff-api"))})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert add_status == 201, add_body
    assert refresh_status == 200, refresh_body
    assert refresh_body["report"]["status"] == "ready_for_review"
    assert pack_status == 201, pack_body
    assert pack_zip_status == 200
    assert response_status == 201, response_body
    assert accepted_status == 201, accepted_body
    assert board_status == 200, board_body
    assert board_body["decision_board"]["status"] == "ready_for_signoff"
    assert signoff_status == 201, signoff_body
    assert signoff_body["signoff"]["status"] == "signed"
    assert zip_status == 200
    assert verify_status == 200, verify_body
    assert verify_body["verification"]["status"] == "passed", verify_body["verification"].get("blockers")
