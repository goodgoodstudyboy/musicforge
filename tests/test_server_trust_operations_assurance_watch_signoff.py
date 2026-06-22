from __future__ import annotations

import os
from pathlib import Path

from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
from song_agent.trust_operations_assurance_watch_signoff import TrustOperationsAssuranceWatchSignoffStore
from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_trust_operations_assurance_watch import _watch_fixture


def test_trust_operations_assurance_watch_signoff_api_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, "require_current": True, **payload})
    source_payload = {
        "watch_package_path": str(watch_store.watch_zip_path(queue_id)),
        "watch_verification_report_path": str(watch_store.verification_report_path(queue_id)),
        "hub_package_path": str(payload["hub_package_path"]),
        "hub_verification_report_path": str(payload["hub_verification_report_path"]),
        "continuous_assurance_report_path": str(payload["assurance_verification_report_path"]),
    }
    server = start_test_server()
    server.trust_operations_hub_store = watch_store.hub_store
    server.trust_operations_assurance_store = TrustOperationsAssuranceStore(
        tmp_path / ".musicforge" / "server-trust-operations-assurance",
        hub_store=watch_store.hub_store,
    )
    server.trust_operations_assurance_watch_store = watch_store
    server.trust_operations_assurance_watch_signoff_store = TrustOperationsAssuranceWatchSignoffStore(
        tmp_path / ".musicforge" / "server-trust-operations-assurance-watch-signoffs",
        watch_store=watch_store,
        assurance_store=watch_store.assurance_store,
        hub_store=watch_store.hub_store,
    )
    try:
        closeout_status, closeout = request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/closeout", source_payload)
        sign_status, signoff = request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/sign", {"signed_by": "reviewer", "role": "owner", "reason": "Watch queue clear and verified."})
        export_status, exported = request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/export", source_payload)
        zip_status, zipped = request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/zip", {})
        verify_status, verified = request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/verify", {"strict": True, "require_signed": True, "require_current": True, **source_payload})
        detail_status, detail = request_json(server, "GET", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}")
    finally:
        stop_test_server(server)

    assert closeout_status == 201
    assert closeout["closeout"]["status"] == "passed"
    assert sign_status == 201
    assert signoff["signoff"]["status"] == "signed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_assurance_watch_signoff_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert detail_status == 200
    assert detail["signoff"]["status"] == "signed"


def test_trust_operations_assurance_watch_signoff_api_delete_bypass_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, "require_current": True, **payload})
    source_payload = {
        "watch_package_path": str(watch_store.watch_zip_path(queue_id)),
        "watch_verification_report_path": str(watch_store.verification_report_path(queue_id)),
        "hub_package_path": str(payload["hub_package_path"]),
        "hub_verification_report_path": str(payload["hub_verification_report_path"]),
        "continuous_assurance_report_path": str(payload["assurance_verification_report_path"]),
    }
    server = start_test_server()
    server.trust_operations_hub_store = watch_store.hub_store
    server.trust_operations_assurance_watch_store = watch_store
    signoff_store = TrustOperationsAssuranceWatchSignoffStore(
        tmp_path / ".musicforge" / "server-trust-operations-assurance-watch-signoffs",
        watch_store=watch_store,
        assurance_store=watch_store.assurance_store,
        hub_store=watch_store.hub_store,
    )
    server.trust_operations_assurance_watch_signoff_store = signoff_store
    try:
        request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/closeout", source_payload)
        request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/sign", {"signed_by": "reviewer", "role": "owner", "reason": "Watch queue clear and verified."})
        os.remove(signoff_store.signoff_path(queue_id))
        export_status, exported = request_json(server, "POST", f"/api/trust-operations/assurance-watch/signoffs/{queue_id}/export", source_payload)
    finally:
        stop_test_server(server)

    assert export_status == 409
    assert "reset" in exported["error"].lower() or "signed" in exported["error"].lower()
