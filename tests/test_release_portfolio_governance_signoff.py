from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance import governance_fixture

from song_agent.projectio import write_json
from song_agent.release_portfolio_governance_archive_verifier import verify_release_portfolio_governance_archive_package
from song_agent.release_portfolio_governance_signoff import (
    ReleasePortfolioGovernanceSignoffStateError,
    ReleasePortfolioGovernanceSignoffStore,
    governance_change_request_integrity_ok,
    governance_signoff_integrity_ok,
)
from song_agent.release_portfolio_governance_verifier import verify_release_portfolio_governance_package, write_release_portfolio_governance_verification_report


def _prepared_queue(tmp_path: Path, monkeypatch):
    _release, _second, portfolio, governance_store = governance_fixture(tmp_path, monkeypatch)
    queue = governance_store.create_from_portfolio(portfolio["portfolio_id"])
    queue_id = queue["queue_id"]
    governance_store.run_safe_actions(queue_id)
    governance_store.export_queue(queue_id)
    governance_store.build_zip(queue_id)
    verification = verify_release_portfolio_governance_package(governance_store.zip_path(queue_id), strict=True, require_manual_actions=True)
    write_release_portfolio_governance_verification_report(verification, governance_store.verification_report_path(queue_id))
    store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    return queue_id, governance_store, store


def _manual_acknowledgements(governance_store, queue_id: str) -> list[dict[str, str]]:
    manual = governance_store.read_manual_action_list(queue_id, default={})
    return [
        {
            "item_id": item["item_id"],
            "action_type": item.get("action_type") or "",
            "resolution": "accepted_for_followup",
            "owner": "developer",
            "due_note": "next governance cycle",
        }
        for item in manual.get("items", [])
        if isinstance(item, dict)
    ]


def test_portfolio_governance_signoff_archive_export_verify_and_tamper(tmp_path: Path, monkeypatch) -> None:
    queue_id, governance_store, store = _prepared_queue(tmp_path, monkeypatch)

    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="acknowledgement"):
        store.signoff(queue_id, {"signed_by": "tester"})

    signed = store.signoff(queue_id, {"signed_by": "tester", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})
    manifest = store.export_archive(queue_id)
    zip_info = store.build_archive_zip(queue_id)
    verification = verify_release_portfolio_governance_archive_package(store.archive_zip_path(queue_id), strict=True, require_signed=True)

    assert governance_signoff_integrity_ok(signed)
    assert signed["status"] == "signed"
    assert manifest["sidecars"]["governance_signoff"]["payload_hash"] == signed["integrity_hash"]
    assert zip_info["sha256"]
    assert verification["status"] == "passed"

    tampered_zip = tmp_path / "tampered-governance-archive.zip"
    with zipfile.ZipFile(store.archive_zip_path(queue_id), "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "governance-signoff.json":
                payload = json.loads(data.decode("utf-8"))
                payload["signed_by"] = "tampered"
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    tampered = verify_release_portfolio_governance_archive_package(tampered_zip, require_signed=True)
    assert tampered["status"] == "failed"
    assert any(item["check_id"] == "portfolio_governance_archive_signoff_integrity" for item in tampered["blockers"])

    stale_verification_zip = tmp_path / "stale-verification-governance-archive.zip"
    with zipfile.ZipFile(store.archive_zip_path(queue_id), "r") as src, zipfile.ZipFile(stale_verification_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "queue-verification-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["zip_sha256"] = "0" * 64
                if isinstance(payload.get("zip"), dict):
                    payload["zip"]["sha256"] = "0" * 64
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    stale_verification = verify_release_portfolio_governance_archive_package(stale_verification_zip, require_signed=True)
    assert stale_verification["status"] == "failed"
    assert any(item["check_id"] == "portfolio_governance_archive_queue_verification_zip_sha256" for item in stale_verification["blockers"])


def test_portfolio_governance_signoff_blocks_missing_or_failed_verification(tmp_path: Path, monkeypatch) -> None:
    queue_id, governance_store, store = _prepared_queue(tmp_path, monkeypatch)
    verification_path = governance_store.verification_report_path(queue_id)
    verification_path.unlink()

    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="gate failed"):
        store.signoff(queue_id, {"signed_by": "tester", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})

    write_json(verification_path, {"status": "failed"})
    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="gate failed"):
        store.signoff(queue_id, {"signed_by": "tester", "force": True, "override_reason": "cannot bypass failed verifier", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})


def test_portfolio_governance_signoff_blocks_stale_queue_verification_report(tmp_path: Path, monkeypatch) -> None:
    queue_id, governance_store, store = _prepared_queue(tmp_path, monkeypatch)
    stale_report = governance_store.verification_report_path(queue_id).read_text(encoding="utf-8")
    old_sha = governance_store.get_queue(queue_id)["latest_zip_sha256"]

    governance_store.build_zip(queue_id)
    new_sha = governance_store.get_queue(queue_id)["latest_zip_sha256"]
    governance_store.verification_report_path(queue_id).write_text(stale_report, encoding="utf-8")

    assert old_sha != new_sha
    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="gate failed"):
        store.signoff(queue_id, {"signed_by": "tester", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})

    verification = verify_release_portfolio_governance_package(governance_store.zip_path(queue_id), strict=True, require_manual_actions=True)
    write_release_portfolio_governance_verification_report(verification, governance_store.verification_report_path(queue_id))
    signed = store.signoff(queue_id, {"signed_by": "tester", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})

    assert signed["status"] == "signed"
    assert signed["evidence"]["queue_zip_sha256"] == new_sha
    assert verification["zip_sha256"] == new_sha


def test_portfolio_governance_signed_queue_is_immutable_until_reset(tmp_path: Path, monkeypatch) -> None:
    queue_id, governance_store, store = _prepared_queue(tmp_path, monkeypatch)
    store.signoff(queue_id, {"signed_by": "tester", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})

    for operation in (governance_store.run_safe_actions, governance_store.export_queue, governance_store.build_zip):
        with pytest.raises(Exception, match="immutable"):
            operation(queue_id)

    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="Change Request"):
        store.reset_signoff(queue_id, {"reason": "Reset without approved change request"})

    draft = store.create_change_request(queue_id, {"reason": "Draft reset request", "created_by": "tester"})
    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="approved"):
        store.reset_signoff(queue_id, {"reason": "Reset with draft request", "change_request_id": draft["change_request_id"]})

    approved = store.create_change_request(queue_id, {"reason": "Approved reset request", "created_by": "tester"})
    approved = store.update_change_request_status(queue_id, approved["change_request_id"], "approve", {"approved_by": "reviewer"})
    reset = store.reset_signoff(queue_id, {"reason": "Reset with approved request", "change_request_id": approved["change_request_id"]})
    applied = store.get_change_request(queue_id, approved["change_request_id"])

    assert reset["status"] == "reset"
    assert applied["status"] == "applied"
    assert governance_change_request_integrity_ok(applied)
    with pytest.raises(ReleasePortfolioGovernanceSignoffStateError, match="approved"):
        store.reset_signoff(queue_id, {"reason": "Reuse same request blocked", "change_request_id": approved["change_request_id"]})

    governance_store.export_queue(queue_id)


def test_portfolio_governance_archive_verifier_path_duplicate_spoof_redaction_and_force(tmp_path: Path, monkeypatch) -> None:
    queue_id, governance_store, store = _prepared_queue(tmp_path, monkeypatch)
    signed = store.signoff(
        queue_id,
        {
            "signed_by": "tester",
            "force": True,
            "override_reason": "accept manual governance follow-up",
        },
    )
    store.export_archive(queue_id)
    store.build_archive_zip(queue_id)
    source_zip = store.archive_zip_path(queue_id)

    assert signed["status"] == "force_signed"
    assert any(item["check_id"] == "portfolio_governance_archive_require_no_force" for item in verify_release_portfolio_governance_archive_package(source_zip, require_signed=True, require_no_force=True)["blockers"])

    duplicate_zip = tmp_path / "duplicate-governance-archive.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    dangerous_zip = tmp_path / "dangerous-governance-archive.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../evil.txt", b"x")

    backslash_zip = tmp_path / "backslash-governance-archive.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-governance-archive.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction-governance-archive.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "GOVERNANCE_CLOSEOUT.md":
                data += b'\napi_key="sk-secret-value" C:\\Users\\demo\\githubkey.txt\n'
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "portfolio_governance_archive_zip_duplicate_entries" for item in verify_release_portfolio_governance_archive_package(duplicate_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_archive_zip_entry_path_safe" for item in verify_release_portfolio_governance_archive_package(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_archive_zip_entry_path_safe" for item in verify_release_portfolio_governance_archive_package(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_archive_package(spoof_zip, strict=True)
    assert any(item["check_id"] == "portfolio_governance_archive_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "portfolio_governance_archive_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "portfolio_governance_archive_redaction_scan" for item in verify_release_portfolio_governance_archive_package(redaction_zip)["blockers"])
