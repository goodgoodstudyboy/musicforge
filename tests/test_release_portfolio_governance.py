from __future__ import annotations

import json
import zipfile
from pathlib import Path

from tests.test_release_portfolio_audit import portfolio_fixture

from song_agent.projectio import write_json
from song_agent.release_portfolio_governance import (
    ReleasePortfolioGovernanceStore,
    action_plan_integrity_ok,
    execution_report_integrity_ok,
    governance_manifest_integrity_ok,
    manual_action_list_integrity_ok,
    queue_integrity_ok,
)
from song_agent.release_portfolio_governance_verifier import verify_release_portfolio_governance_package


def governance_fixture(tmp_path: Path, monkeypatch):
    release, second, portfolio_store = portfolio_fixture(tmp_path, monkeypatch, second_verified=False)
    change = portfolio_store.signoff_store.create_change_request(release.release_id, {"reason": "Regression reset for governance manual action.", "scope": ["operations_signoff"]})
    portfolio_store.signoff_store.update_change_request_status(release.release_id, change["change_request_id"], "approve", {"approved_by": "reviewer"})
    portfolio_store.signoff_store.reset_signoff(release.release_id, {"reason": "Reset to create applied change request evidence.", "change_request_id": change["change_request_id"]})
    portfolio_store.signoff_store.signoff(release.release_id, {"signed_by": "tester"})
    portfolio = portfolio_store.create({"name": "Governance Portfolio", "release_ids": [release.release_id, second.release_id], "require_reviewer_packs": True, "require_audit": True, "require_archive": True})
    portfolio_store.refresh(portfolio["portfolio_id"])
    store = ReleasePortfolioGovernanceStore(
        portfolio_store=portfolio_store,
        reviewer_pack_store=portfolio_store.reviewer_pack_store,
        audit_store=portfolio_store.audit_store,
        signoff_store=portfolio_store.signoff_store,
    )
    return release, second, portfolio, store


def test_portfolio_governance_create_run_export_zip_and_verify(tmp_path: Path, monkeypatch) -> None:
    _release, second, portfolio, store = governance_fixture(tmp_path, monkeypatch)

    queue = store.create_from_portfolio(portfolio["portfolio_id"])
    queue_id = queue["queue_id"]
    duplicate = store.create_from_portfolio(portfolio["portfolio_id"])
    plan = store.read_action_plan(queue_id)
    manual = store.read_manual_action_list(queue_id)

    assert duplicate["queue_id"] == queue_id
    assert duplicate["existing"] is True
    assert queue_integrity_ok(queue)
    assert action_plan_integrity_ok(plan)
    assert manual_action_list_integrity_ok(manual)
    assert any(item["action_type"] == "reviewer_pack.verify" and item["release_id"] == second.release_id and item["safety"] == "safe" for item in plan["items"])
    assert any(item["action_type"] == "change_request.review" and item["safety"] == "manual_required" for item in plan["items"])

    ran = store.run_safe_actions(queue_id)
    execution = store.read_execution_report(queue_id)
    manifest = store.export_queue(queue_id)
    zip_info = store.build_zip(queue_id)
    verification = verify_release_portfolio_governance_package(store.zip_path(queue_id), strict=True, require_manual_actions=True)
    current_manifest = store.read_export_manifest(queue_id)

    assert ran["status"] == "manual_required"
    assert execution["summary"]["safe_completed"] >= 4
    assert execution["summary"]["manual_required"] >= 1
    assert execution["post_conditions"]["portfolio_refresh_required"] is True
    assert execution_report_integrity_ok(execution)
    assert governance_manifest_integrity_ok(manifest)
    assert zip_info["sha256"]
    assert verification["zip_sha256"] == zip_info["sha256"]
    assert verification["zip_size_bytes"] == zip_info["size_bytes"]
    assert verification["manifest_hash"] == current_manifest["integrity_hash"]
    assert verification["status"] == "passed"


def test_portfolio_governance_stale_guard_blocks_run_safe(tmp_path: Path, monkeypatch) -> None:
    release, _second, portfolio, store = governance_fixture(tmp_path, monkeypatch)
    queue = store.create_from_portfolio(portfolio["portfolio_id"])

    verification_path = store.reviewer_pack_store.verification_report_path(release.release_id)
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["status"] = "failed"
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        store.run_safe_actions(queue["queue_id"])
    except Exception as exc:
        assert "stale" in str(exc).lower()
    else:
        raise AssertionError("stale Governance Queue run-safe was not blocked")


def test_portfolio_governance_stale_guard_blocks_export_and_zip(tmp_path: Path, monkeypatch) -> None:
    release, _second, portfolio, store = governance_fixture(tmp_path, monkeypatch)
    queue = store.create_from_portfolio(portfolio["portfolio_id"])
    queue_id = queue["queue_id"]

    store.export_queue(queue_id)
    store.build_zip(queue_id)
    zip_before = store.zip_path(queue_id).read_bytes()

    verification_path = store.reviewer_pack_store.verification_report_path(release.release_id)
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["status"] = "failed"
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

    for operation in (store.export_queue, store.build_zip):
        try:
            operation(queue_id)
        except Exception as exc:
            assert "stale" in str(exc).lower()
        else:
            raise AssertionError(f"stale Governance Queue {operation.__name__} was not blocked")

    assert store.zip_path(queue_id).read_bytes() == zip_before


def test_portfolio_governance_verifier_tamper_path_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    _release, _second, portfolio, store = governance_fixture(tmp_path, monkeypatch)
    queue = store.create_from_portfolio(portfolio["portfolio_id"])
    queue_id = queue["queue_id"]
    store.run_safe_actions(queue_id)
    store.export_queue(queue_id)
    store.build_zip(queue_id)
    source_zip = store.zip_path(queue_id)

    tampered_zip = tmp_path / "tampered-governance.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "action-plan.json":
                payload = json.loads(data.decode("utf-8"))
                payload["items"][0]["status"] = "completed"
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    execution_tampered_zip = tmp_path / "execution-tampered-governance.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(execution_tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "execution-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["failed"] = 99
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    dangerous_zip = tmp_path / "dangerous-governance.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../evil.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-governance.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-governance.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-governance.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction-governance.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "GOVERNANCE_ACTIONS.md":
                data += b'\napi_key="sk-secret-value" C:\\Users\\demo\\githubkey.txt\n'
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "portfolio_governance_action_plan_integrity" for item in verify_release_portfolio_governance_package(tampered_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_execution_report_integrity" for item in verify_release_portfolio_governance_package(execution_tampered_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_zip_entry_path_safe" for item in verify_release_portfolio_governance_package(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_zip_duplicate_entries" for item in verify_release_portfolio_governance_package(duplicate_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_zip_entry_path_safe" for item in verify_release_portfolio_governance_package(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_package(spoof_zip, strict=True)
    assert any(item["check_id"] == "portfolio_governance_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "portfolio_governance_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "portfolio_governance_redaction_scan" for item in verify_release_portfolio_governance_package(redaction_zip)["blockers"])
