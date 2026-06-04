from __future__ import annotations

import json
from pathlib import Path

from tests.test_release_portfolio_audit import portfolio_fixture
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_portfolio_audit_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release, second, _store = portfolio_fixture(Path(".musicforge"), monkeypatch, second_verified=True)

        create_status, created = request_json(
            server,
            "POST",
            "/api/release-portfolio-audits",
            {"name": "Server Portfolio", "release_ids": [release.release_id, second.release_id], "require_reviewer_packs": True, "require_audit": True, "require_archive": True},
        )
        portfolio_id = created["portfolio"]["portfolio_id"]
        list_status, listed = request_json(server, "GET", "/api/release-portfolio-audits")
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}")
        refresh_status, refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/refresh")
        report_status, report = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/report")
        trends_status, trends = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/trends")
        risks_status, risks = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/risks")
        export_status, exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/export/zip")
        verify_status, verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/verify", {"strict": True, "require_reviewer_packs": True, "require_audit": True, "require_archive": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/download")

        assert create_status == 201
        assert list_status == 200
        assert listed["summary"]["count"] >= 1
        assert detail_status == 200
        assert detail["portfolio"]["portfolio_id"] == portfolio_id
        assert refresh_status == 200
        assert refreshed["summary"]["status"] == "passed"
        assert report_status == 200
        assert report["summary"]["status"] == "passed"
        assert trends_status == 200
        assert trends["trend_report"]["portfolio_id"] == portfolio_id
        assert risks_status == 200
        assert "risk_register" in risks
        assert export_status == 201
        assert exported["manifest"]["portfolio_id"] == portfolio_id
        assert zip_status == 200
        assert zipped["zip"]["sha256"]
        assert verify_status == 200
        assert verified["summary"]["status"] == "passed"
        assert download_status == 200
        assert zip_bytes.startswith(b"PK")
    finally:
        stop_test_server(server)


def test_server_release_portfolio_audit_blocks_stale_export(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release, _second, _store = portfolio_fixture(Path(".musicforge"), monkeypatch, second_verified=True)
        create_status, created = request_json(
            server,
            "POST",
            "/api/release-portfolio-audits",
            {"name": "Server Stale Portfolio", "release_ids": [release.release_id], "require_reviewer_packs": True},
        )
        portfolio_id = created["portfolio"]["portfolio_id"]
        refresh_status, _refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/refresh")

        verification_path = Path(".musicforge") / "releases" / release.release_id / "operations" / "reviewer-pack" / "reviewer-pack-verification-report.json"
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        verification["status"] = "failed"
        verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}")
        export_status, export_error = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/export")
        zip_status, zip_error = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/export/zip")

        assert create_status == 201
        assert refresh_status == 200
        assert detail_status == 200
        assert detail["summary"]["stale"] is True
        assert export_status == 409
        assert "stale" in export_error["error"].lower()
        assert zip_status == 409
        assert "stale" in zip_error["error"].lower()
    finally:
        stop_test_server(server)
