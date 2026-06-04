from __future__ import annotations

import json
import zipfile
from pathlib import Path

from tests.test_release_operations_reviewer_pack import accepted_reviewer_fixture

from song_agent.release_operations_reviewer_pack_verifier import verify_release_operations_reviewer_pack, write_release_operations_reviewer_pack_verification_report
from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore, portfolio_manifest_integrity_ok, portfolio_report_integrity_ok, portfolio_risk_register_integrity_ok, portfolio_trend_integrity_ok
from song_agent.release_portfolio_audit_verifier import verify_release_portfolio_audit_package


def portfolio_fixture(tmp_path: Path, monkeypatch=None, *, second_verified: bool = False):
    release, operations_store, runbook_store, signoff_store, audit_store, reviewer_store = accepted_reviewer_fixture(tmp_path, monkeypatch)
    reviewer_store.refresh(release.release_id)
    reviewer_store.export_pack(release.release_id)
    reviewer_store.build_zip(release.release_id)
    reviewer_verification = verify_release_operations_reviewer_pack(reviewer_store.zip_path(release.release_id), strict=True, require_audit=True, require_signed=True, require_archive=True)
    write_release_operations_reviewer_pack_verification_report(reviewer_verification, reviewer_store.verification_report_path(release.release_id))

    second, *_ = accepted_reviewer_fixture(tmp_path, monkeypatch)
    if second_verified:
        reviewer_store.refresh(second.release_id)
        reviewer_store.export_pack(second.release_id)
        reviewer_store.build_zip(second.release_id)
        second_verification = verify_release_operations_reviewer_pack(reviewer_store.zip_path(second.release_id), strict=True, require_audit=True, require_signed=True, require_archive=True)
        write_release_operations_reviewer_pack_verification_report(second_verification, reviewer_store.verification_report_path(second.release_id))

    portfolio_store = ReleasePortfolioAuditStore(release_store=operations_store.release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    return release, second, portfolio_store


def test_portfolio_audit_refresh_export_zip_and_verify(tmp_path: Path, monkeypatch) -> None:
    release, second, store = portfolio_fixture(tmp_path, monkeypatch, second_verified=True)
    portfolio = store.create({"name": "Portfolio Smoke", "release_ids": [release.release_id, second.release_id], "require_reviewer_packs": True, "require_audit": True, "require_archive": True})

    report = store.refresh(portfolio["portfolio_id"])
    trend = store.read_trend_report(portfolio["portfolio_id"])
    risks = store.read_risk_register(portfolio["portfolio_id"])
    manifest = store.export_portfolio(portfolio["portfolio_id"])
    zip_info = store.build_zip(portfolio["portfolio_id"])
    verification = verify_release_portfolio_audit_package(store.zip_path(portfolio["portfolio_id"]), strict=True, require_reviewer_packs=True, require_audit=True, require_archive=True)

    assert report["status"] == "passed"
    assert report["summary"]["release_count"] == 2
    assert report["summary"]["reviewer_pack_passed_count"] == 2
    assert portfolio_report_integrity_ok(report)
    assert portfolio_trend_integrity_ok(trend)
    assert portfolio_risk_register_integrity_ok(risks)
    assert portfolio_manifest_integrity_ok(manifest)
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert "Portfolio Smoke" in (store.export_dir(portfolio["portfolio_id"]) / "PORTFOLIO_REVIEW.md").read_text(encoding="utf-8")


def test_portfolio_audit_requirements_and_risk_register(tmp_path: Path, monkeypatch) -> None:
    release, second, store = portfolio_fixture(tmp_path, monkeypatch, second_verified=False)
    portfolio = store.create({"name": "Portfolio Risk", "release_ids": [release.release_id, second.release_id], "require_reviewer_packs": True, "require_audit": True})

    report = store.refresh(portfolio["portfolio_id"])
    risks = store.read_risk_register(portfolio["portfolio_id"])
    store.export_portfolio(portfolio["portfolio_id"])
    store.build_zip(portfolio["portfolio_id"])
    verification = verify_release_portfolio_audit_package(store.zip_path(portfolio["portfolio_id"]), require_reviewer_packs=True, require_audit=True)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "reviewer_pack_required" for item in report["blockers"])
    assert any(risk["category"] == "reviewer_pack" for risk in risks["risks"])
    assert any(item["check_id"] == "portfolio_audit_require_reviewer_packs" and item["status"] == "failed" for item in verification["checks"])


def test_portfolio_audit_export_blocks_stale_release_evidence(tmp_path: Path, monkeypatch) -> None:
    release, _second, store = portfolio_fixture(tmp_path, monkeypatch, second_verified=True)
    portfolio = store.create({"name": "Portfolio Stale", "release_ids": [release.release_id], "require_reviewer_packs": True})
    store.refresh(portfolio["portfolio_id"])
    store.export_portfolio(portfolio["portfolio_id"])
    store.build_zip(portfolio["portfolio_id"])

    verification_path = store.reviewer_pack_store.verification_report_path(release.release_id)
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["status"] = "failed"
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

    assert store.report_is_stale(portfolio["portfolio_id"]) is True
    try:
        store.export_portfolio(portfolio["portfolio_id"])
    except Exception as exc:
        assert "stale" in str(exc).lower()
    else:
        raise AssertionError("stale Portfolio Audit export was not blocked")

    try:
        store.build_zip(portfolio["portfolio_id"])
    except Exception as exc:
        assert "stale" in str(exc).lower()
    else:
        raise AssertionError("stale Portfolio Audit ZIP rebuild was not blocked")


def test_portfolio_audit_verifier_tamper_path_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    release, second, store = portfolio_fixture(tmp_path, monkeypatch, second_verified=True)
    portfolio = store.create({"name": "Portfolio Verify", "release_ids": [release.release_id, second.release_id]})
    store.refresh(portfolio["portfolio_id"])
    store.export_portfolio(portfolio["portfolio_id"])
    store.build_zip(portfolio["portfolio_id"])
    source_zip = store.zip_path(portfolio["portfolio_id"])

    tampered_zip = tmp_path / "tampered-portfolio.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "portfolio-audit-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["release_count"] = 99
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    dangerous_zip = tmp_path / "dangerous-portfolio.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../evil.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-portfolio.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-portfolio.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-portfolio.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction-portfolio.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "PORTFOLIO_REVIEW.md":
                data += b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n"
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "portfolio_audit_report_integrity" for item in verify_release_portfolio_audit_package(tampered_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_audit_zip_entry_path_safe" for item in verify_release_portfolio_audit_package(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_audit_zip_duplicate_entries" for item in verify_release_portfolio_audit_package(duplicate_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_audit_zip_entry_path_safe" for item in verify_release_portfolio_audit_package(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_audit_package(spoof_zip, strict=True)
    assert any(item["check_id"] == "portfolio_audit_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "portfolio_audit_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "portfolio_audit_redaction_scan" for item in verify_release_portfolio_audit_package(redaction_zip)["blockers"])
