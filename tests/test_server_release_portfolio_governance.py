from __future__ import annotations

import json
from pathlib import Path

from tests.test_release_portfolio_governance import governance_fixture
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_portfolio_governance_queue_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
        portfolio_id = portfolio["portfolio_id"]

        create_status, created = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-queues", {})
        queue_id = created["queue"]["queue_id"]
        duplicate_status, duplicate = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-queues", {})
        list_status, listed = request_json(server, "GET", f"/api/release-portfolio-governance-queues?portfolio_id={portfolio_id}")
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}")
        plan_status, plan = request_json(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}/plan")
        manual_status, manual = request_json(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}/manual-actions")
        run_status, ran = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/run-safe", {})
        execution_status, execution = request_json(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}/execution")
        export_status, exported = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export/zip")
        verify_status, verified = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/verify", {"strict": True, "require_manual_actions": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}/download")

        assert create_status == 201
        assert duplicate_status == 200
        assert duplicate["queue"]["queue_id"] == queue_id
        assert duplicate["queue"]["existing"] is True
        assert list_status == 200
        assert listed["summary"]["count"] >= 1
        assert detail_status == 200
        assert detail["queue"]["queue_id"] == queue_id
        assert plan_status == 200
        assert plan["summary"]["item_count"] > 0
        assert manual_status == 200
        assert manual["summary"]["count"] >= 1
        assert run_status == 200
        assert ran["summary"]["status"] == "manual_required"
        assert execution_status == 200
        assert execution["summary"]["manual_required"] >= 1
        assert export_status == 201
        assert exported["manifest"]["queue_id"] == queue_id
        assert zip_status == 200
        assert zipped["zip"]["sha256"]
        assert verify_status == 200
        assert verified["summary"]["status"] == "passed"
        assert download_status == 200
        assert zip_bytes.startswith(b"PK")
    finally:
        stop_test_server(server)


def test_server_release_portfolio_governance_stale_run_safe_returns_409(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
        portfolio_id = portfolio["portfolio_id"]
        create_status, created = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-queues", {})
        queue_id = created["queue"]["queue_id"]

        verification_path = Path(".musicforge") / "releases" / release.release_id / "operations" / "reviewer-pack" / "reviewer-pack-verification-report.json"
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        verification["status"] = "failed"
        verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

        run_status, error = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/run-safe", {})

        assert create_status == 201
        assert run_status == 409
        assert "stale" in error["error"].lower()
    finally:
        stop_test_server(server)
